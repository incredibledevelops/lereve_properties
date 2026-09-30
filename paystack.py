"""
============================================================
LE RÊVE PROPERTIES — PAYSTACK INTEGRATION
All amounts processed in GHS (₵). Paystack smallest unit: pesewas.
============================================================
"""
import hmac
import hashlib
import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from flask import (
    Blueprint, request, jsonify, redirect, url_for,
    current_app, flash,
)
from flask_login import current_user, login_required

import requests

from models import Booking, Property, db, utcnow

log = logging.getLogger(__name__)

paystack_bp = Blueprint('paystack', __name__)

PAYSTACK_BASE = 'https://api.paystack.co'


# ============================================================
# HELPERS
# ============================================================
def _to_pesewas(amount_ghs):
    """Convert GHS amount to pesewas (integer), rounding half-up to avoid fp errors."""
    d = Decimal(str(amount_ghs)) * Decimal('100')
    return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _from_pesewas(amount_pesewas):
    """Convert pesewas back to GHS float for display."""
    return float(Decimal(str(amount_pesewas)) / Decimal('100'))


def _paystack_headers():
    return {
        'Authorization': f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
        'Content-Type': 'application/json',
    }


def _generate_reference():
    return f"LR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


# ============================================================
# INITIALIZE TRANSACTION
# ============================================================
@paystack_bp.route('/initialize', methods=['POST'])
@login_required
def initialize():
    data = request.get_json(silent=True) or request.form
    property_id = (data.get('property_id') or '').strip()
    check_in = (data.get('check_in') or '').strip()
    check_out = (data.get('check_out') or '').strip()
    guests = (data.get('guests') or '1-2 Guests').strip()

    # ---------- Validation ----------
    if not property_id or not check_in or not check_out:
        return jsonify({'success': False, 'error': 'Missing booking fields.'}), 400

    prop = Property.get(property_id)
    if not prop:
        return jsonify({'success': False, 'error': 'Property not found.'}), 404

    try:
        ci = datetime.fromisoformat(check_in).date()
        co = datetime.fromisoformat(check_out).date()
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid dates.'}), 400

    if co <= ci:
        return jsonify({'success': False, 'error': 'Check-out must be after check-in.'}), 400

    nights = max(1, (co - ci).days)

    nightly = float(prop.get('price', 0))
    if nightly <= 0:
        return jsonify({'success': False, 'error': 'Property has no valid price.'}), 400

    total_ghs = round(nightly * nights, 2)
    amount_pesewas = _to_pesewas(total_ghs)

    # Paystack GHS minimum is 100 pesewas (₵1)
    if amount_pesewas < 100:
        return jsonify({'success': False, 'error': 'Amount below Paystack minimum.'}), 400

    reference = _generate_reference()

    # ---------- Create pending booking ----------
    booking_id = Booking.create({
        'user_id': current_user.id,
        'user_email': current_user.email,
        'user_name': current_user.name,
        'property_id': property_id,
        'property': prop.get('title'),
        'location': prop.get('location'),
        'image': prop.get('image'),
        'check_in': check_in,
        'check_out': check_out,
        'guests': guests,
        'nights': nights,
        'nightly_rate': nightly,
        'total': total_ghs,
        'currency': 'GHS',
        'status': 'pending',
        'payment_reference': reference,
        'payment_status': 'pending',
        'confirmation_id': reference,
    })

    # ---------- Build Paystack payload ----------
    callback_base = current_app.config.get('PAYSTACK_CALLBACK_URL', '').rstrip('/')
    payload = {
        'email': current_user.email,
        'amount': amount_pesewas,
        'currency': 'GHS',
        'reference': reference,
        'callback_url': f"{callback_base}?booking_id={booking_id}",
        'metadata': {
            'booking_id': booking_id,
            'property_id': property_id,
            'user_id': current_user.id,
            'nights': nights,
            'custom_fields': [
                {'display_name': 'Property', 'variable_name': 'property', 'value': prop.get('title')},
                {'display_name': 'Check-In', 'variable_name': 'check_in', 'value': check_in},
                {'display_name': 'Check-Out', 'variable_name': 'check_out', 'value': check_out},
                {'display_name': 'Guests', 'variable_name': 'guests', 'value': guests},
            ],
        },
    }

    # ---------- Call Paystack ----------
    try:
        resp = requests.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            json=payload,
            headers=_paystack_headers(),
            timeout=20,
        )
        result = resp.json()
    except requests.RequestException as e:
        log.exception('Paystack init network error')
        Booking.update(booking_id, {'payment_status': 'failed', 'payment_error': str(e)})
        return jsonify({'success': False, 'error': 'Payment gateway unreachable. Try again.'}), 502

    if not result.get('status'):
        err = result.get('message', 'Paystack error')
        log.warning(f'Paystack init rejected: {err}')
        Booking.update(booking_id, {'payment_status': 'failed', 'payment_error': err})
        return jsonify({'success': False, 'error': err}), 400

    return jsonify({
        'success': True,
        'authorization_url': result['data']['authorization_url'],
        'access_code': result['data'].get('access_code'),
        'reference': reference,
        'booking_id': booking_id,
        'amount': total_ghs,
        'currency': 'GHS',
    })


# ============================================================
# CALLBACK
# ============================================================
@paystack_bp.route('/callback')
def callback():
    reference = (request.args.get('reference') or '').strip()
    booking_id = (request.args.get('booking_id') or '').strip()

    if not reference:
        flash('Missing payment reference.', 'error')
        return _safe_redirect()

    verify = _verify_transaction(reference)

    if not verify:
        if booking_id:
            Booking.update(booking_id, {'payment_status': 'failed', 'payment_error': 'verify_failed'})
        flash('Could not verify payment. Please contact concierge.', 'error')
        return _safe_redirect()

    if not verify.get('status') or verify.get('data', {}).get('status') != 'success':
        if booking_id:
            Booking.update(booking_id, {
                'payment_status': 'failed',
                'payment_error': verify.get('message', 'not_successful'),
            })
        flash('Payment was not successful. You have not been charged.', 'error')
        return _safe_redirect()

    # ---------- Success ----------
    ps_data = verify['data']

    # Fallback: get booking_id from metadata if not in query
    if not booking_id:
        booking_id = (ps_data.get('metadata') or {}).get('booking_id')

    if booking_id:
        booking = Booking.get(booking_id)

        # Idempotency: if already paid, don't double-update
        if booking and booking.get('payment_status') != 'paid':
            Booking.update(booking_id, {
                'status': 'confirmed',
                'payment_status': 'paid',
                'paid_at': utcnow().isoformat(),
                'payment_amount': _from_pesewas(ps_data.get('amount', 0)),
                'payment_channel': ps_data.get('channel', ''),
                'payment_reference': ps_data.get('reference', reference),
            })

            # Send confirmation email (best-effort)
            try:
                from mailer import send_booking_confirmation
                updated = Booking.get(booking_id)
                if updated and updated.get('user_email'):
                    send_booking_confirmation(updated['user_email'], updated)
            except Exception as e:
                log.warning(f'Booking confirmation mail failed: {e}')

    flash('Payment successful! Your reservation is confirmed.', 'success')
    return _safe_redirect()


def _safe_redirect():
    """Redirect to client bookings if logged in, otherwise login page."""
    if current_user.is_authenticated and not current_user.is_admin:
        return redirect(url_for('client.bookings'))
    return redirect(url_for('auth.login'))


# ============================================================
# VERIFY
# ============================================================
def _verify_transaction(reference):
    """Returns parsed JSON or None on network failure."""
    try:
        resp = requests.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers=_paystack_headers(),
            timeout=20,
        )
        return resp.json()
    except (requests.RequestException, ValueError):
        log.exception('Paystack verify failed')
        return None


# ============================================================
# WEBHOOK
# ============================================================
@paystack_bp.route('/webhook', methods=['POST'])
def webhook():
    secret = current_app.config.get('PAYSTACK_SECRET_KEY', '')
    if not secret:
        log.error('Webhook called but PAYSTACK_SECRET_KEY not configured')
        return jsonify({'status': 'not configured'}), 500

    signature = request.headers.get('x-paystack-signature', '')
    computed = hmac.new(
        secret.encode('utf-8'),
        request.data,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(computed, signature):
        log.warning('Webhook signature mismatch')
        return jsonify({'status': 'invalid signature'}), 400

    event = request.get_json(silent=True) or {}
    event_type = event.get('event')

    log.info(f'Paystack webhook received: {event_type}')

    if event_type == 'charge.success':
        data = event.get('data', {}) or {}
        meta = data.get('metadata') or {}
        booking_id = meta.get('booking_id')
        reference = data.get('reference')

        if booking_id:
            booking = Booking.get(booking_id)
            # Idempotency guard
            if booking and booking.get('payment_status') != 'paid':
                Booking.update(booking_id, {
                    'status': 'confirmed',
                    'payment_status': 'paid',
                    'paid_at': utcnow().isoformat(),
                    'payment_amount': _from_pesewas(data.get('amount', 0)),
                    'payment_channel': data.get('channel', ''),
                    'payment_reference': reference,
                })
                log.info(f'Booking {booking_id} confirmed via webhook')
            else:
                log.info(f'Booking {booking_id} already paid — webhook ignored')
        else:
            log.warning('Webhook charge.success missing booking_id in metadata')

    elif event_type in ('charge.failed', 'transfer.failed'):
        data = event.get('data', {}) or {}
        booking_id = (data.get('metadata') or {}).get('booking_id')
        if booking_id:
            Booking.update(booking_id, {
                'payment_status': 'failed',
                'payment_error': data.get('gateway_response', event_type),
            })
            log.info(f'Booking {booking_id} marked failed via webhook')

    else:
        log.info(f'Unhandled webhook event: {event_type}')

    # Always return 200 quickly so Paystack doesn't retry
    return jsonify({'status': 'ok'}), 200