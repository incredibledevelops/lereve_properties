"""
============================================================
PAYSTACK ROUTES
============================================================
"""
import hmac
import hashlib
import logging

from flask import (
    Blueprint, request, jsonify, redirect, url_for,
    current_app, flash,
)
from flask_login import current_user, login_required

from extensions import csrf, limiter
from models import Booking, Property, utcnow
from services import (
    initialize_transaction, verify_transaction, generate_reference,
    to_pesewas, from_pesewas, calculate_nights, is_valid_range,
)
from services.mailer import send_booking_confirmation
from services.analytics import track as track_event


log = logging.getLogger(__name__)
paystack_bp = Blueprint('paystack', __name__)


# ============================================================
# INITIALIZE
# ============================================================
@paystack_bp.route('/initialize', methods=['POST'])
@login_required
@limiter.limit('20 per minute')
def initialize():
    data = request.get_json(silent=True) or request.form
    property_id = (data.get('property_id') or '').strip()
    check_in    = (data.get('check_in')    or '').strip()
    check_out   = (data.get('check_out')   or '').strip()
    guests      = (data.get('guests')      or '1-2 Guests').strip()

    if not property_id or not check_in or not check_out:
        return jsonify({'success': False, 'error': 'Missing fields.'}), 400

    prop = Property.get(property_id)
    if not prop:
        return jsonify({'success': False, 'error': 'Property not found.'}), 404

    valid, err = is_valid_range(
        check_in, check_out,
        current_app.config['MIN_BOOKING_NIGHTS'],
        current_app.config['MAX_BOOKING_NIGHTS'],
    )
    if not valid:
        return jsonify({'success': False, 'error': err}), 400

    nights = calculate_nights(check_in, check_out)
    if nights < 1:
        return jsonify({'success': False, 'error': 'Invalid stay range.'}), 400

    if Booking.has_overlap(property_id, check_in, check_out):
        return jsonify({
            'success': False,
            'error': 'This property is already booked for the selected dates.'
        }), 409

    nightly = float(prop.get('price', 0))
    if nightly <= 0:
        return jsonify({'success': False, 'error': 'Invalid property price.'}), 400

    total_ghs      = round(nightly * nights, 2)
    amount_pesewas = to_pesewas(total_ghs)
    if amount_pesewas < 100:
        return jsonify({'success': False, 'error': 'Amount below minimum.'}), 400

    reference = generate_reference()

    booking_id = Booking.create({
        'user_id':           current_user.id,
        'user_email':        current_user.email,
        'user_name':         current_user.name,
        'property_id':       property_id,
        'property':          prop.get('title'),
        'location':          prop.get('location'),
        'image':             prop.get('image'),
        'check_in':          check_in,
        'check_out':         check_out,
        'guests':            guests,
        'nights':            nights,
        'nightly_rate':      nightly,
        'total':             total_ghs,
        'currency':          'GHS',
        'status':            'pending',
        'payment_reference': reference,
        'payment_status':    'pending',
        'confirmation_id':   reference,
    })

    track_event('booking_started', {'property_id': property_id, 'total': total_ghs})

    # ---- Build the callback URL -------------------------------------
    # IMPORTANT: include `reference` as well as `booking_id`, because
    # Paystack's `verify/<reference>` endpoint needs the reference and
    # the callback handler uses it to verify the transaction. If we
    # omit it, the callback has to guess from booking metadata.
    callback_base = (current_app.config.get('PAYSTACK_CALLBACK_URL') or '').rstrip('/')
    if not callback_base:
        log.error('PAYSTACK_CALLBACK_URL is not configured — aborting initialization')
        Booking.update(booking_id, {
            'payment_status': 'failed',
            'payment_error':  'PAYSTACK_CALLBACK_URL not configured',
        })
        return jsonify({
            'success': False,
            'error': 'Payment provider not configured. Please contact the concierge.',
        }), 500

    callback_url = (
        f"{callback_base}"
        f"?booking_id={booking_id}"
        f"&reference={reference}"
    )

    payload = {
        'email':        current_user.email,
        'amount':       amount_pesewas,
        'currency':     'GHS',
        'reference':    reference,
        'callback_url': callback_url,
        'metadata': {
            'booking_id':  booking_id,
            'property_id': property_id,
            'user_id':     current_user.id,
            'nights':      nights,
        },
    }

    result = initialize_transaction(payload)

    if not result.get('status'):
        err = result.get('message', 'Paystack error')
        Booking.update(booking_id, {'payment_status': 'failed', 'payment_error': err})
        return jsonify({'success': False, 'error': err}), 400

    return jsonify({
        'success':           True,
        'authorization_url': result['data']['authorization_url'],
        'reference':         reference,
        'booking_id':        booking_id,
        'amount':            total_ghs,
    })


# ============================================================
# CALLBACK
# ============================================================
@paystack_bp.route('/callback')
def callback():
    reference  = (request.args.get('reference')  or '').strip()
    booking_id = (request.args.get('booking_id') or '').strip()

    if not reference:
        flash('Missing payment reference.', 'error')
        return _safe_redirect()

    verify = verify_transaction(reference)
    if not verify:
        flash('Could not verify payment. Contact concierge.', 'error')
        return _safe_redirect()

    # Defensive: verify may be {"status": False, "message": "..."} without `data`
    ps_data = verify.get('data') or {}
    if not verify.get('status') or ps_data.get('status') != 'success':
        if booking_id:
            Booking.update(booking_id, {
                'payment_status': 'failed',
                'payment_error':  verify.get('message', 'not_successful'),
            })
        flash('Payment was not successful.', 'error')
        return _safe_redirect()

    # Recover the booking id from metadata if the callback URL didn't carry it
    if not booking_id:
        booking_id = (ps_data.get('metadata') or {}).get('booking_id')

    if booking_id:
        booking = Booking.get(booking_id)
        if booking and booking.get('payment_status') != 'paid':
            # Amount sanity check
            expected = float(booking.get('total') or 0)
            actual   = from_pesewas(ps_data.get('amount', 0))
            if abs(expected - actual) > 0.5:
                log.warning(
                    f'Amount mismatch booking={booking_id}: '
                    f'expected={expected} actual={actual}'
                )
                flash('Payment amount mismatch. Contact concierge.', 'error')
                return _safe_redirect()

            Booking.update(booking_id, {
                'status':            'confirmed',
                'payment_status':    'paid',
                'paid_at':           utcnow().isoformat(),
                'payment_amount':    actual,
                'payment_channel':   ps_data.get('channel', ''),
                'payment_reference': ps_data.get('reference', reference),
            })
            track_event('booking_completed', {'booking_id': booking_id})

            updated = Booking.get(booking_id)
            if updated and updated.get('user_email'):
                try:
                    send_booking_confirmation(updated['user_email'], updated)
                except Exception:
                    log.exception('Confirmation email failed')

    flash('Payment successful! Reservation confirmed.', 'success')
    return _safe_redirect()


def _safe_redirect():
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('client.bookings'))
    return redirect(url_for('auth.login'))


# ============================================================
# WEBHOOK
# ============================================================
@paystack_bp.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    secret = current_app.config.get('PAYSTACK_SECRET_KEY', '')
    if not secret:
        return jsonify({'status': 'not configured'}), 500

    signature = request.headers.get('x-paystack-signature', '')
    computed  = hmac.new(secret.encode(), request.data, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(computed, signature):
        return jsonify({'status': 'invalid signature'}), 400

    event      = request.get_json(silent=True) or {}
    event_type = event.get('event')
    log.info(f'Paystack webhook: {event_type}')

    if event_type == 'charge.success':
        data        = event.get('data', {}) or {}
        meta        = data.get('metadata') or {}
        booking_id  = meta.get('booking_id')
        reference   = data.get('reference')

        if booking_id:
            booking = Booking.get(booking_id)
            if booking and booking.get('payment_status') != 'paid':
                expected = float(booking.get('total') or 0)
                actual   = from_pesewas(data.get('amount', 0))
                if abs(expected - actual) > 0.5:
                    log.warning(f'Webhook amount mismatch booking={booking_id}')
                else:
                    Booking.update(booking_id, {
                        'status':            'confirmed',
                        'payment_status':    'paid',
                        'paid_at':           utcnow().isoformat(),
                        'payment_amount':    actual,
                        'payment_channel':   data.get('channel', ''),
                        'payment_reference': reference,
                    })

    elif event_type in ('charge.failed', 'transfer.failed'):
        data = event.get('data', {}) or {}
        bid  = (data.get('metadata') or {}).get('booking_id')
        if bid:
            Booking.update(bid, {
                'payment_status': 'failed',
                'payment_error':  data.get('gateway_response', event_type),
            })

    return jsonify({'status': 'ok'}), 200