"""
============================================================
LE RÊVE PROPERTIES — PUBLIC ROUTES
Travelers-only. No public estate submission.
============================================================
"""
import re
import logging

from flask import (
    Blueprint, render_template, request, jsonify, flash,
    redirect, url_for, make_response, current_app,
)
from flask_login import current_user

from models import (
    Property, Review, Inquiry, Category,
    JournalSubscriber, Wishlist, Settings,
)
from forms import InquiryForm, JournalForm, ReviewForm
from mailer import send_inquiry_notification, send_journal_welcome

log = logging.getLogger(__name__)

public_bp = Blueprint('public', __name__)


# ============================================================
# CONSTANTS
# ============================================================
MAX_TEXT_LENGTH = 2000
MAX_NAME_LENGTH = 120
MAX_EMAIL_LENGTH = 200
MAX_PHONE_LENGTH = 40


# ============================================================
# HELPERS
# ============================================================
def _flatten_errors(errors):
    if not errors:
        return []
    out = []
    for field, errs in errors.items():
        if isinstance(errs, list):
            for e in errs:
                out.append(f"{field}: {e}" if field != 'csrf_token' else str(e))
        else:
            out.append(str(errs))
    return out


def _is_email_valid(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    if len(email) > MAX_EMAIL_LENGTH:
        return False
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))


def _clean(value, max_len=MAX_TEXT_LENGTH):
    if not value:
        return ''
    return str(value).strip()[:max_len]


# ============================================================
# HOME
# ============================================================
@public_bp.route('/')
def home():
    try:
        properties = Property.all(sort=[('created_at', -1)])
        reviews = Review.all({'status': 'published'})  # ← ALL published reviews
        settings = Settings.get()
        categories = Category.all()
    except Exception:
        log.exception('Error loading home data')
        properties, reviews, settings, categories = [], [], {}, []

    wishlist_ids = []
    if current_user.is_authenticated and not current_user.is_admin:
        try:
            wishlist_ids = Wishlist.get(current_user.id)
        except Exception:
            wishlist_ids = []

    return render_template(
        'index.html',
        properties=properties,
        reviews=reviews,
        settings=settings,
        categories=categories,
        wishlist_ids=wishlist_ids,
    )


# ============================================================
# LISTINGS API
# ============================================================
@public_bp.route('/api/properties')
def api_properties():
    category = _clean(request.args.get('category') or 'all', 100)
    max_price = request.args.get('max_price', type=float)
    location = _clean(request.args.get('location') or '', 200)

    filters = {}
    if category and category != 'all':
        filters['category'] = category
    if max_price and max_price > 0:
        filters['price'] = {'$lte': max_price}
    if location:
        safe_loc = re.escape(location)
        filters['$or'] = [
            {'location': {'$regex': safe_loc, '$options': 'i'}},
            {'title': {'$regex': safe_loc, '$options': 'i'}},
        ]

    try:
        properties = Property.all(filters, sort=[('created_at', -1)])
    except Exception:
        log.exception('api_properties query failed')
        return jsonify({'success': False, 'error': 'Query failed.'}), 500

    return jsonify({'success': True, 'properties': properties, 'count': len(properties)})


@public_bp.route('/api/properties/<pid>')
def api_property_detail(pid):
    try:
        prop = Property.get(pid)
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid ID'}), 400
    if not prop:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return jsonify({'success': True, 'property': prop})


# ============================================================
# INQUIRY SUBMISSION
# ============================================================
@public_bp.route('/inquiry', methods=['POST'])
def submit_inquiry():
    """Accepts both JSON (fetch) and form-encoded submissions."""
    if request.is_json:
        data = request.get_json(silent=True) or {}
        required = ['name', 'email', 'phone']
        missing = [f for f in required if not _clean(data.get(f))]
        if missing:
            return jsonify({
                'success': False,
                'error': f"Missing fields: {', '.join(missing)}",
            }), 400
        if not _is_email_valid(data.get('email', '')):
            return jsonify({'success': False, 'error': 'Invalid email address.'}), 400

        payload = {
            'name': _clean(data['name'], MAX_NAME_LENGTH),
            'email': _clean(data['email'], MAX_EMAIL_LENGTH).lower(),
            'phone': _clean(data.get('phone'), MAX_PHONE_LENGTH),
            'property': _clean(data.get('property') or 'General Inquiry', 200),
            'check_in': _clean(data.get('check_in'), 20),
            'check_out': _clean(data.get('check_out'), 20),
            'guests': _clean(data.get('guests') or '1-2 Guests', 50),
            'message': _clean(data.get('message')),
        }
        try:
            Inquiry.create(payload)
        except Exception:
            log.exception('Inquiry.create failed')
            return jsonify({'success': False, 'error': 'Could not save inquiry.'}), 500

        try:
            send_inquiry_notification(payload)
        except Exception as e:
            log.warning(f'Inquiry mail failed: {e}')

        return jsonify({'success': True, 'message': 'Inquiry submitted successfully.'})

    form = InquiryForm()
    if form.validate_on_submit():
        payload = {
            'name': _clean(form.name.data, MAX_NAME_LENGTH),
            'email': _clean(form.email.data, MAX_EMAIL_LENGTH).lower(),
            'phone': _clean(form.phone.data, MAX_PHONE_LENGTH),
            'property': _clean(form.property.data or 'General Inquiry', 200),
            'check_in': form.check_in.data.isoformat() if form.check_in.data else '',
            'check_out': form.check_out.data.isoformat() if form.check_out.data else '',
            'guests': form.guests.data,
            'message': _clean(form.message.data),
        }
        try:
            Inquiry.create(payload)
            send_inquiry_notification(payload)
        except Exception as e:
            log.warning(f'Inquiry processing failed: {e}')

        flash('Your confidential inquiry has been dispatched to our concierge desk.', 'success')
        return redirect(url_for('public.home') + '#contact')

    for err in _flatten_errors(form.errors):
        flash(err, 'error')
    return redirect(url_for('public.home') + '#contact')


# ============================================================
# JOURNAL SUBSCRIBE
# ============================================================
@public_bp.route('/journal/subscribe', methods=['POST'])
def journal_subscribe():
    if request.is_json:
        data = request.get_json(silent=True) or {}
        email = _clean(data.get('email'), MAX_EMAIL_LENGTH).lower()
        if not _is_email_valid(email):
            return jsonify({'success': False, 'error': 'Valid email required.'}), 400

        try:
            added = JournalSubscriber.add(email)
        except Exception:
            log.exception('JournalSubscriber.add failed')
            return jsonify({'success': False, 'error': 'Could not subscribe.'}), 500

        if added:
            try:
                send_journal_welcome(email)
            except Exception:
                pass
            return jsonify({'success': True, 'message': 'Subscribed to the private journal.'})
        return jsonify({'success': True, 'message': 'You are already subscribed.'})

    form = JournalForm()
    if form.validate_on_submit():
        email = _clean(form.email.data, MAX_EMAIL_LENGTH).lower()
        added = JournalSubscriber.add(email)
        if added:
            try:
                send_journal_welcome(email)
            except Exception:
                pass
            flash('Subscribed to the private journal.', 'success')
        else:
            flash('You are already subscribed.', 'info')
    else:
        for err in _flatten_errors(form.errors):
            flash(err, 'error')
    return redirect(url_for('public.home') + '#footer')


# ============================================================
# WISHLIST TOGGLE
# ============================================================
@public_bp.route('/api/wishlist/toggle', methods=['POST'])
def wishlist_toggle():
    if not current_user.is_authenticated or current_user.is_admin:
        return jsonify({'success': False, 'error': 'Please sign in to save favorites.'}), 401

    data = request.get_json(silent=True) or {}
    property_id = _clean(data.get('property_id'), 64)
    if not property_id:
        return jsonify({'success': False, 'error': 'Missing property_id'}), 400

    try:
        prop = Property.get(property_id)
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid property ID'}), 400
    if not prop:
        return jsonify({'success': False, 'error': 'Property not found'}), 404

    try:
        added = Wishlist.toggle(current_user.id, property_id)
    except Exception:
        log.exception('Wishlist.toggle failed')
        return jsonify({'success': False, 'error': 'Could not update wishlist.'}), 500

    return jsonify({
        'success': True,
        'added': added,
        'message': 'Saved to wishlist.' if added else 'Removed from wishlist.',
    })


# ============================================================
# REVIEW SUBMIT (public, moderated)
# ============================================================
@public_bp.route('/review', methods=['POST'])
def submit_review():
    form = ReviewForm()
    if form.validate_on_submit():
        name = _clean(form.name.data, MAX_NAME_LENGTH) or 'Anonymous Guest'
        avatar = _clean(form.avatar.data, 500) or (
            f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}"
            "&background=c9a84c&color=1a3a2a"
        )
        try:
            Review.create({
                'name': name,
                'property': _clean(form.property.data, 200),
                'rating': int(form.rating.data or 5),
                'text': _clean(form.text.data),
                'avatar': avatar,
                'status': 'pending',
            })
            flash('Thank you! Your review is pending moderation.', 'success')
        except Exception:
            log.exception('Review.create failed')
            flash('Could not save review. Please try again.', 'error')
    else:
        for err in _flatten_errors(form.errors):
            flash(err, 'error')
    return redirect(url_for('public.home') + '#reviews')


# ============================================================
# SEO
# ============================================================
@public_bp.route('/robots.txt')
def robots():
    response = make_response(render_template('robots.txt'))
    response.headers['Content-Type'] = 'text/plain'
    return response


@public_bp.route('/sitemap.xml')
def sitemap():
    try:
        properties = Property.all()
    except Exception:
        properties = []
    response = make_response(render_template('sitemap.xml', properties=properties))
    response.headers['Content-Type'] = 'application/xml'
    return response