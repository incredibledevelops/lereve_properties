"""
============================================================
API ROUTES
JSON endpoints for wishlist, inquiries, reviews, journal,
analytics tracking — all called via fetch() from the front-end.
============================================================
"""
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user, login_required

from extensions import db, limiter, csrf

log = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ============================================================
# CSRF EXEMPT FOR JSON API (uses X-CSRFToken header instead)
# ============================================================
@api_bp.before_request
def _verify_csrf_from_header():
    """Validate CSRF from the X-CSRFToken header for JSON POSTs."""
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        token = request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
        if not token:
            # Also accept from JSON body (some clients send it there)
            try:
                body = request.get_json(silent=True) or {}
                token = body.get('csrf_token') or body.get('_csrf_token')
            except Exception:
                token = None

        if not token:
            return jsonify({'success': False, 'error': 'Missing CSRF token'}), 400

        # Compare against Flask-WTF's session token
        from flask_wtf.csrf import validate_csrf
        try:
            validate_csrf(token)
        except Exception as e:
            log.warning(f"CSRF validation failed: {e}")
            return jsonify({'success': False, 'error': 'Invalid CSRF token'}), 400


# ============================================================
# HELPERS
# ============================================================
def _clean(value, max_len=None):
    s = (value or '').strip() if isinstance(value, str) else ''
    if max_len and len(s) > max_len:
        s = s[:max_len]
    return s


def _now():
    return datetime.now(timezone.utc)


# ============================================================
# WISHLIST TOGGLE  →  POST /api/wishlist
# ============================================================
def wishlist_toggle():
    """Toggle a property in the current user's wishlist."""
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'error': 'Sign in to save favorites'}), 401

    body = request.get_json(silent=True) or {}
    property_id = _clean(body.get('property_id'), 64)
    if not property_id:
        return jsonify({'success': False, 'error': 'Missing property_id'}), 400

    user_id = str(current_user.id)
    try:
        wl = db.db['wishlists'].find_one({'user_id': user_id})
        if not wl:
            db.db['wishlists'].insert_one({
                'user_id': user_id,
                'property_ids': [property_id],
                'updated_at': _now(),
            })
            return jsonify({'success': True, 'added': True})

        ids = set(wl.get('property_ids', []))
        if property_id in ids:
            ids.discard(property_id)
            added = False
        else:
            ids.add(property_id)
            added = True

        db.db['wishlists'].update_one(
            {'user_id': user_id},
            {'$set': {'property_ids': list(ids), 'updated_at': _now()}}
        )
        return jsonify({'success': True, 'added': added})
    except Exception as e:
        log.exception(f"wishlist toggle failed: {e}")
        return jsonify({'success': False, 'error': 'Could not update wishlist'}), 500


# ============================================================
# CREATE INQUIRY  →  POST /api/inquiries
# Called by stays.html, index.html, contact.html booking forms
# ============================================================
def create_inquiry():
    """Accept a booking/inquiry form submission and store it."""
    body = request.get_json(silent=True) or {}

    name      = _clean(body.get('name'),  120)
    email     = _clean(body.get('email'), 200).lower()
    phone     = _clean(body.get('phone'), 40)
    prop      = _clean(body.get('property'), 200) or 'General Inquiry'
    check_in  = _clean(body.get('check_in'), 20)
    check_out = _clean(body.get('check_out'), 20)
    guests    = _clean(body.get('guests'), 40) or '—'
    message   = _clean(body.get('message'), 2000)

    # ---- Validation ----
    errors = []
    if not name:  errors.append('Name is required.')
    if not email or '@' not in email: errors.append('Valid email is required.')
    if not phone: errors.append('Phone is required.')
    if errors:
        return jsonify({'success': False, 'error': ' '.join(errors)}), 400

    doc = {
        'name':      name,
        'email':     email,
        'phone':     phone,
        'property':  prop,
        'check_in':  check_in,
        'check_out': check_out,
        'guests':    guests,
        'message':   message,
        'status':    'new',
        'source':    'web-form',
        'ip':        request.headers.get('X-Forwarded-For', request.remote_addr),
        'user_agent': request.headers.get('User-Agent', '')[:250],
        'user_id':   str(current_user.id) if current_user.is_authenticated else None,
        'created_at': _now(),
    }

    try:
        db.db['inquiries'].insert_one(doc)
    except Exception as e:
        log.exception(f"inquiry insert failed: {e}")
        return jsonify({'success': False, 'error': 'Could not save inquiry'}), 500

    # Best-effort: notify admin via mailer (non-blocking)
    try:
        from services.mailer import notify_new_inquiry
        notify_new_inquiry(doc)
    except Exception as e:
        log.warning(f"inquiry notification skipped: {e}")

    return jsonify({'success': True, 'message': 'Inquiry received'})


# ============================================================
# SUBMIT REVIEW  →  POST /api/reviews
# Called by reviews.html
# ============================================================
def submit_review():
    """Accept a guest review (pending moderation)."""
    # Accept both JSON and form-encoded posts
    if request.is_json:
        body = request.get_json(silent=True) or {}
    else:
        body = request.form.to_dict()

    name     = _clean(body.get('name'), 120)
    prop     = _clean(body.get('property'), 200)
    text     = _clean(body.get('text'), 2000)
    try:
        rating = int(body.get('rating', 5))
    except (TypeError, ValueError):
        rating = 5
    rating = max(1, min(5, rating))

    if not name or not prop or not text:
        return jsonify({'success': False, 'error': 'All fields are required.'}), 400

    doc = {
        'name':       name,
        'property':   prop,
        'rating':     rating,
        'text':       text,
        'status':     'pending',
        'avatar':     '',
        'user_id':    str(current_user.id) if current_user.is_authenticated else None,
        'created_at': _now(),
    }

    try:
        db.db['reviews'].insert_one(doc)
    except Exception as e:
        log.exception(f"review insert failed: {e}")
        return jsonify({'success': False, 'error': 'Could not save review'}), 500

    return jsonify({'success': True, 'message': 'Review submitted for moderation'})


# ============================================================
# JOURNAL SUBSCRIBE  →  POST /api/journal
# Called by base.html footer form
# ============================================================
def journal_subscribe():
    """Add an email to the private journal subscriber list."""
    body  = request.get_json(silent=True) or {}
    email = _clean(body.get('email'), 200).lower()

    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Valid email required.'}), 400

    try:
        db.db['journal_subscribers'].update_one(
            {'email': email},
            {'$setOnInsert': {'email': email, 'created_at': _now()},
             '$set':         {'updated_at': _now()}},
            upsert=True,
        )
    except Exception as e:
        log.exception(f"journal subscribe failed: {e}")
        return jsonify({'success': False, 'error': 'Could not subscribe'}), 500

    return jsonify({'success': True, 'message': 'Subscribed to the private journal.'})


# ============================================================
# ANALYTICS TRACK  →  POST /api/track
# Requires X-Track-Secret header matching config
# ============================================================
def track_event():
    """Record an analytics event (page view, click, etc.)."""
    secret = request.headers.get('X-Track-Secret') or ''
    expected = current_app.config.get('ANALYTICS_TRACK_SECRET', '')
    if expected and secret != expected:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    body = request.get_json(silent=True) or {}
    event_type = _clean(body.get('type'), 64) or 'unknown'
    payload    = body.get('payload') or {}

    doc = {
        'type':       event_type,
        'payload':    payload,
        'ip':         request.headers.get('X-Forwarded-For', request.remote_addr),
        'user_agent': request.headers.get('User-Agent', '')[:250],
        'user_id':    str(current_user.id) if current_user.is_authenticated else None,
        'created_at': _now(),
    }

    try:
        db.db['analytics_events'].insert_one(doc)
    except Exception as e:
        log.warning(f"analytics insert failed: {e}")
        return jsonify({'success': False}), 500

    return jsonify({'success': True})


# ============================================================
# REGISTER ROUTES
# NOTE: NO dots in endpoint names — Flask prefixes them with
# the blueprint name, so 'create_inquiry' becomes
# 'api.create_inquiry' automatically.
# ============================================================
api_bp.add_url_rule(
    '/wishlist', endpoint='wishlist_toggle',
    view_func=wishlist_toggle, methods=['POST'],
)

api_bp.add_url_rule(
    '/inquiries', endpoint='create_inquiry',
    view_func=create_inquiry, methods=['POST'],
)

api_bp.add_url_rule(
    '/reviews', endpoint='submit_review',
    view_func=submit_review, methods=['POST'],
)

api_bp.add_url_rule(
    '/journal', endpoint='journal_subscribe',
    view_func=journal_subscribe, methods=['POST'],
)

api_bp.add_url_rule(
    '/track', endpoint='track_event',
    view_func=track_event, methods=['POST'],
)