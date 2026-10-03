"""
============================================================
AUTH / PUBLIC ROUTES
Public-facing pages: home, stays, why us, reviews, contact,
login, register, logout, password reset.
============================================================
"""
import logging
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash

from extensions import db, limiter
from models import User
from forms import LoginForm, RegisterForm, ForgotForm, ResetForm

log = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


# ============================================================
# DATABASE AVAILABILITY GUARD
# ============================================================
def _db_available():
    """Return True only if the Mongo database handle is usable."""
    try:
        if db is None:
            return False
        if not hasattr(db, 'db'):
            return False
        if db.db is None:
            return False
        _ = db.db.name
        return True
    except Exception as e:
        log.warning(f"[auth] DB availability check failed: {e}")
        return False


# ============================================================
# SERIALIZERS — must return JSON-safe primitives only
# ============================================================
def _iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        return str(value)
    except Exception:
        return None


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _serialize_property(p):
    try:
        return {
            'id':             str(p.get('_id', '')),
            'title':          p.get('title') or '',
            'category':       p.get('category') or '',
            'location':       p.get('location') or '',
            'price':          _safe_float(p.get('price'), 0.0),
            'original_price': _safe_float(p.get('original_price'), 0.0),
            'rating':         _safe_float(
                                  p.get('rating') if p.get('rating') is not None else 5,
                                  5.0
                              ),
            'reviews_count':  _safe_int(p.get('reviews_count'), 0),
            'beds':           _safe_int(p.get('beds'), 0),
            'baths':          _safe_int(p.get('baths'), 0),
            'guests':         _safe_int(p.get('guests'), 0),
            'image':          p.get('image') or '',
            'gallery':        list(p.get('gallery') or []),
            'amenities':      list(p.get('amenities') or []),
            'description':    p.get('description') or '',
            'created_at':     _iso(p.get('created_at')),
        }
    except Exception as e:
        log.warning(f"[auth] bad property doc {p.get('_id', '?')}: {e}")
        return None


def _serialize_category(c):
    try:
        return {
            'id':          str(c.get('_id', '')),
            'name':        c.get('name') or '',
            'slug':        c.get('slug') or '',
            'icon':        c.get('icon') or 'fa-house-chimney',
            'description': c.get('description') or '',
            'order':       _safe_int(c.get('order'), 0),
        }
    except Exception as e:
        log.warning(f"[auth] bad category doc {c.get('_id', '?')}: {e}")
        return None


def _serialize_review(r):
    try:
        return {
            'id':         str(r.get('_id', '')),
            'name':       r.get('name') or 'Anonymous',
            'property':   r.get('property') or '—',
            'rating':     _safe_int(r.get('rating'), 0),
            'text':       r.get('text') or '',
            'avatar':     r.get('avatar') or '',
            'created_at': _iso(r.get('created_at')),
        }
    except Exception as e:
        log.warning(f"[auth] bad review doc {r.get('_id', '?')}: {e}")
        return None


# ============================================================
# DATA LOADERS — every loader gracefully degrades to []
# ============================================================
def _load_reviews(limit=None):
    if not _db_available():
        log.warning("[auth] reviews load skipped — DB unavailable")
        return []
    try:
        q = db.db['reviews'].find({'status': 'published'}).sort('created_at', -1)
        if limit:
            q = q.limit(limit)
        docs = list(q)
    except Exception as e:
        log.exception(f"[auth] reviews load failed: {e}")
        return []
    out = []
    for r in docs:
        s = _serialize_review(r)
        if s is not None:
            out.append(s)
    return out


def _load_categories():
    if not _db_available():
        log.warning("[auth] categories load skipped — DB unavailable")
        return []
    try:
        docs = list(db.db['categories'].find().sort('order', 1))
    except Exception as e:
        log.exception(f"[auth] categories load failed: {e}")
        return []
    out = []
    for c in docs:
        s = _serialize_category(c)
        if s is not None:
            out.append(s)
    return out


def _load_properties(limit=None):
    if not _db_available():
        log.warning("[auth] properties load skipped — DB unavailable")
        return []
    try:
        q = db.db['properties'].find().sort('created_at', -1)
        if limit:
            q = q.limit(limit)
        docs = list(q)
    except Exception as e:
        log.exception(f"[auth] properties load failed: {e}")
        return []
    out = []
    for p in docs:
        s = _serialize_property(p)
        if s is not None:
            out.append(s)
    return out


def _load_wishlist_ids():
    if not current_user.is_authenticated:
        return []
    if not _db_available():
        log.warning("[auth] wishlist load skipped — DB unavailable")
        return []
    try:
        wl = db.db['wishlists'].find_one({'user_id': str(current_user.id)})
        return list(wl.get('property_ids', [])) if wl else []
    except Exception as e:
        log.warning(f"[auth] wishlist load failed: {e}")
        return []


# ============================================================
# HOME
# ============================================================
@auth_bp.route('/')
def index():
    return render_template(
        'index.html',
        properties=_load_properties(limit=12),
        categories=_load_categories(),
        reviews=_load_reviews(limit=10),
        wishlist_ids=_load_wishlist_ids(),
    )


# ============================================================
# STAYS
# ============================================================
@auth_bp.route('/stays')
def stays():
    return render_template(
        'stays.html',
        properties=_load_properties(),
        categories=_load_categories(),
        wishlist_ids=_load_wishlist_ids(),
    )


# ============================================================
# WHY US
# ============================================================
@auth_bp.route('/why-us')
def why_us():
    return render_template(
        'why_us.html',
        reviews=_load_reviews(limit=8),
        categories=_load_categories(),
    )


# ============================================================
# REVIEWS
# ============================================================
@auth_bp.route('/reviews')
def reviews_page():
    return render_template(
        'reviews.html',
        properties=_load_properties(limit=50),
        categories=_load_categories(),
        reviews=_load_reviews(limit=50),
    )


# ============================================================
# CONTACT
# ============================================================
@auth_bp.route('/contact')
def contact():
    return render_template(
        'contact.html',
        properties=_load_properties(limit=50),
        categories=_load_categories(),
    )


# ============================================================
# LOGIN
# ============================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('RATELIMIT_LOGIN', '10 per minute'))
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard') if current_user.is_admin
                        else url_for('client.dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.find_by_email(email)

        if not user or not user.check_password(form.password.data):
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html', form=form), 401

        if not getattr(user, 'is_active', True):
            flash('This account has been deactivated.', 'error')
            return render_template('auth/login.html', form=form), 403

        login_user(user, remember=form.remember.data)
        if hasattr(user, 'update_last_login'):
            user.update_last_login()

        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)

        return redirect(url_for('admin.dashboard') if user.is_admin
                        else url_for('client.dashboard'))

    return render_template('auth/login.html', form=form)


# ============================================================
# REGISTER
# ============================================================
@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit(lambda: current_app.config.get('RATELIMIT_REGISTER', '5 per hour'))
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    form = RegisterForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        name  = form.name.data.strip()
        phone = (form.phone.data or '').strip()

        if User.find_by_email(email):
            flash('An account with this email already exists.', 'error')
            return render_template('auth/register.html', form=form), 400

        user = User(email=email, name=name, phone=phone, role='client')
        user.set_password(form.password.data)

        try:
            db.db['users'].insert_one(user.to_dict(include_password=True))
            flash('Account created. Please sign in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            log.exception("Registration failed")
            flash('Something went wrong. Please try again.', 'error')
            return render_template('auth/register.html', form=form), 500

    return render_template('auth/register.html', form=form)


# ============================================================
# LOGOUT
# ============================================================
@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('auth.index'))


# ============================================================
# PASSWORD RESET
# ============================================================
@auth_bp.route('/forgot', methods=['GET', 'POST'])
@limiter.limit('5 per hour')
def forgot_password():
    form = ForgotForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.find_by_email(email)

        # Always show the same message — do not leak whether the email exists
        if user:
            try:
                s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
                token = s.dumps(user.email, salt='password-reset')

                from services.mailer import send_password_reset
                send_password_reset(
                    user.email,
                    token,
                    current_app.config['PUBLIC_SITE_URL'].rstrip('/'),
                )
            except Exception:
                log.exception("Password reset email failed")

        flash('If an account exists for that email, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forget.html', form=form)


@auth_bp.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Validate the token BEFORE showing the form
    try:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email = s.loads(token, salt='password-reset', max_age=3600)
    except SignatureExpired:
        flash('This reset link has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash('Invalid reset link.', 'error')
        return redirect(url_for('auth.forgot_password'))

    form = ResetForm()

    if form.validate_on_submit():
        user = User.find_by_email(email)
        if not user:
            flash('Account no longer exists.', 'error')
            return redirect(url_for('auth.login'))

        try:
            from bson import ObjectId
            db.db['users'].update_one(
                {'_id': ObjectId(user.id)},
                {'$set': {'password_hash': generate_password_hash(form.password.data)}},
            )
            flash('Password updated. Please sign in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            log.exception("Password reset failed")
            flash('Could not reset password. Please try again.', 'error')

    return render_template('auth/reset.html', form=form, token=token)