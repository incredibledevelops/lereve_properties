"""
============================================================
ADMIN ROUTES
============================================================
Admin console: dashboard, analytics, users, properties,
categories, bookings, inquiries, reviews, messages, journal,
settings, plus JSON endpoints for the dashboard and threads.

Message threading convention (see models.Message):
    thread_id = f"user-{user_id}"
Both sides (client.py and this module) MUST agree on that format.
"""
import csv
import io
import json
import logging
import re
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from bson.errors import InvalidId

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, jsonify, current_app, Response, g, abort,
)
from flask_login import login_required, current_user

from extensions import db
from models import (
    Property, Booking, Inquiry, Review, Category,
    JournalSubscriber, Settings, User, Message, AnalyticsEvent,
    utcnow, oid_to_str,
)
from forms import (
    PropertyForm, CategoryForm, AdminReviewForm,
    SettingsForm, UserEditForm, UserCreateForm,
)
from utils import admin_required
from utils.pagination import get_page, paginate_mongo
from utils.uploads import (
    save_image, save_images, delete_image, delete_images,
)


log = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__, template_folder='templates/admin')

PAGE_SIZE = 20

# Simple in-process cache for the dashboard stats endpoint.
# In a multi-worker deployment this is per-worker, so we keep the TTL
# short — 30s is enough to absorb a dashboard's 60s poll cadence.
_STATS_CACHE = {'value': None, 'expires_at': 0, 'refreshed_at': None}
_STATS_TTL_SECONDS = 30


# ============================================================
# HELPERS
# ============================================================
def _clean(v, max_len=2000):
    """Trim + truncate a form value to a safe string."""
    if v is None:
        return ''
    return str(v).strip()[:max_len]


def _safe_next(default_endpoint, **kwargs):
    """
    Return a redirect target guaranteed to be on this host.

    Uses `next` from the query string only when it starts with a single
    '/' and not '//' (which would be protocol-relative). Otherwise falls
    back to the provided endpoint.
    """
    candidate = request.values.get('next') or request.form.get('next')
    if candidate and candidate.startswith('/') and not candidate.startswith('//'):
        return candidate
    return url_for(default_endpoint, **kwargs)


def _badge_counts():
    """Sidebar badge counts (cached per-request via `g`)."""
    cached = getattr(g, '_admin_badges', None)
    if cached is not None:
        return cached
    try:
        counts = {
            'pending_inquiries': Inquiry.count({'status': 'new'}),
            'pending_reviews':   Review.count({'status': 'pending'}),
            'unread_messages':   Message.count({
                'sender': 'client', 'read_by_admin': False,
            }),
        }
    except Exception:
        log.exception('Badge counts failed')
        counts = {'pending_inquiries': 0, 'pending_reviews': 0, 'unread_messages': 0}
    g._admin_badges = counts
    return counts


def _render(template, **ctx):
    """Render a template with admin defaults injected."""
    ctx.setdefault('active_section', 'dashboard')
    ctx.update(_badge_counts())
    ctx.setdefault('now', utcnow())
    ctx.setdefault('now_year_month', datetime.now(timezone.utc).strftime('%Y-%m'))
    return render_template(template, **ctx)


def _audit(action, target=None, extra=None):
    """Log an admin action to the app log for later review."""
    try:
        actor = current_user.email if current_user.is_authenticated else 'anonymous'
        ip = request.remote_addr or 'unknown'
        log.info(
            f'[AUDIT] {actor}@{ip} → {action}'
            f'{" target=" + str(target) if target else ""}'
            f'{" extra=" + str(extra) if extra else ""}'
        )
    except Exception:
        log.exception('Audit log failed')


def _normalize_iso(v):
    """Convert datetimes to ISO strings; leave other values alone."""
    if not v:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _paginate(collection, filters, page, projection=None, sort_field='created_at'):
    """
    Wrapper around paginate_mongo that normalizes items and adds a
    stable `_id` tiebreaker to the sort so pagination is deterministic
    when several docs share the same timestamp.
    """
    raw = paginate_mongo(
        collection, filters,
        [(sort_field, -1), ('_id', -1)],
        page, PAGE_SIZE, projection,
    )
    return {
        'items': [oid_to_str(d) for d in raw['items']],
        **{k: v for k, v in raw.items() if k != 'items'},
    }


def _daterange_or_none(from_str, to_str, field='created_at', as_datetime=True):
    """
    Build a Mongo range filter from two ISO date strings.
    When `field` stores a datetime, uses datetime objects (default).
    When `field` stores 'YYYY-MM-DD' strings, pass as_datetime=False.
    """
    if not from_str and not to_str:
        return None

    rng = {}
    if as_datetime:
        if from_str:
            try:
                rng['$gte'] = datetime.fromisoformat(from_str)
            except (ValueError, TypeError):
                pass
        if to_str:
            try:
                rng['$lt'] = datetime.fromisoformat(to_str) + timedelta(days=1)
            except (ValueError, TypeError):
                pass
    else:
        if from_str:
            rng['$gte'] = from_str
        if to_str:
            rng['$lte'] = to_str

    return {field: rng} if rng else None


def _parse_iso_or_none(v):
    """Best-effort ISO 8601 parse for stored dates."""
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None
    return None


def _csv_response(rows, header, filename_prefix):
    """
    Build a UTF-8 CSV Response with BOM (so Excel opens it correctly)
    and a timestamped filename.
    """
    buf = io.StringIO()
    buf.write('\ufeff')  # BOM for Excel
    w = csv.writer(buf)
    w.writerow(header)
    for row in rows:
        w.writerow(row)

    filename = (
        f"{filename_prefix}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    )
    return Response(
        buf.getvalue().encode('utf-8'),
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-store',
        },
    )


def _is_valid_oid(v):
    """Return True if `v` can be parsed as an ObjectId."""
    try:
        ObjectId(str(v))
        return True
    except (InvalidId, TypeError, ValueError):
        return False


# ============================================================
# DASHBOARD
# ============================================================
@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        paid = Booking.all(
            {'payment_status': 'paid'},
            sort=[('paid_at', -1)],
            limit=1000,
        )
        confirmed = Booking.count({'status': 'confirmed'})
        pending   = Booking.count({'status': 'pending'})
        cancelled = Booking.count({'status': 'cancelled'})

        # `paid_at` may be stored as either a string (ISO) or a datetime.
        revenue_month = 0.0
        for b in paid:
            paid_at = _parse_iso_or_none(b.get('paid_at'))
            if paid_at and paid_at >= month_start:
                revenue_month += float(b.get('total') or 0)

        props = Property.all(limit=500)
        props_by_cat = {}
        for p in props:
            cat = p.get('category') or 'Other'
            props_by_cat.setdefault(cat, []).append(p.get('id'))

        occupancy = {}
        for cat, ids in props_by_cat.items():
            if not ids:
                occupancy[cat] = 0
                continue
            booked = sum(1 for b in paid if b.get('property_id') in ids)
            occupancy[cat] = min(100, round((booked / len(ids)) * 100))

        avg_occupancy = (
            f"{round(sum(occupancy.values()) / len(occupancy))}%"
            if occupancy else '0%'
        )

        stats = {
            'properties':         Property.count(),
            'inquiries':          Inquiry.count(),
            'reviews':            Review.count(),
            'categories':         Category.count(),
            'users':              User.count({'role': 'client'}),
            'new_inquiries':      Inquiry.count({'status': 'new'}),
            'pending_reviews':    Review.count({'status': 'pending'}),
            'revenue_month':      revenue_month,
            'confirmed_bookings': confirmed,
            'pending_bookings':   pending,
            'cancelled_bookings': cancelled,
            'occupancy':          occupancy,
            'avg_occupancy':      avg_occupancy,
            'unread_messages':    Message.count({
                'sender': 'client', 'read_by_admin': False,
            }),
        }

        recent_inquiries = Inquiry.all(sort=[('created_at', -1)], limit=4)
        recent_bookings  = Booking.all(sort=[('created_at', -1)], limit=5)

        return _render(
            'admin/dashboard.html',
            stats=stats,
            recent_inquiries=recent_inquiries,
            recent_bookings=recent_bookings,
            active_section='dashboard',
        )
    except Exception:
        log.exception('Dashboard failed')
        flash('Could not load dashboard.', 'error')
        return _render(
            'admin/dashboard.html',
            stats={k: 0 for k in [
                'properties', 'inquiries', 'reviews', 'categories', 'users',
                'new_inquiries', 'pending_reviews', 'revenue_month',
                'confirmed_bookings', 'pending_bookings', 'cancelled_bookings',
                'unread_messages',
            ]} | {'occupancy': {}, 'avg_occupancy': '0%'},
            recent_inquiries=[],
            recent_bookings=[],
        )


# ============================================================
# ANALYTICS
# ============================================================
@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    days = request.args.get('days', 30, type=int)
    days = max(7, min(days, 365))

    # ---- CSV export branch ----
    if request.args.get('format') == 'csv':
        try:
            events = AnalyticsEvent.count_by_type(days=days)
            bookings_daily = Booking.bookings_by_day(days=days)

            buf = io.StringIO()
            buf.write('\ufeff')
            w = csv.writer(buf)

            w.writerow(['Metric', 'Value'])
            w.writerow(['Days', days])
            for k, v in (events or {}).items():
                w.writerow([k, v])

            w.writerow([])
            w.writerow(['Date', 'Bookings', 'Revenue'])
            for row in bookings_daily:
                w.writerow([
                    row.get('_id', ''),
                    row.get('count', 0),
                    row.get('revenue', 0),
                ])

            filename = (
                f"lereve-analytics-{days}d-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
            )
            _audit('analytics.export', extra=filename)
            return Response(
                buf.getvalue().encode('utf-8'),
                mimetype='text/csv; charset=utf-8',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Cache-Control': 'no-store',
                },
            )
        except Exception:
            log.exception('Analytics CSV export failed')
            flash('Could not export analytics.', 'error')
            return redirect(url_for('admin.analytics', days=days))

    try:
        events = AnalyticsEvent.count_by_type(days=days)

        # Previous-period comparison.
        events_all = AnalyticsEvent.count_by_type(days=days * 2)
        events_prev = {
            k: max(0, (events_all.get(k, 0) - events.get(k, 0)))
            for k in events_all.keys()
        }

        page_views       = AnalyticsEvent.daily_series('page_view', days=days)
        bookings_daily   = Booking.bookings_by_day(days=days)
        status_breakdown = Booking.status_breakdown()
        top_searches     = AnalyticsEvent.top_searches(days=days, limit=10)
        top_props_raw    = AnalyticsEvent.top_properties(days=days, limit=10)

        # Batch-fetch properties instead of one-by-one.
        prop_ids = [t['_id'] for t in top_props_raw if t.get('_id')]
        prop_map = {}
        if prop_ids:
            for p in db.db['properties'].find(
                {'_id': {'$in': [ObjectId(pid) for pid in prop_ids if _is_valid_oid(pid)]}},
                {'title': 1},
            ):
                prop_map[str(p['_id'])] = p.get('title') or 'Unknown'

        top_props = [
            {
                'title': prop_map.get(str(t.get('_id')), 'Unknown'),
                'count': t['count'],
            }
            for t in top_props_raw
        ]

        since = datetime.now(timezone.utc) - timedelta(days=days)
        user_pipeline = [
            {'$match': {'created_at': {'$gte': since}, 'role': 'client'}},
            {'$group': {
                '_id':   {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
                'count': {'$sum': 1},
            }},
            {'$sort': {'_id': 1}},
        ]
        user_growth = list(db.db['users'].aggregate(user_pipeline))

        return _render(
            'admin/analytics.html',
            days=days,
            events=events,
            events_prev=events_prev,
            page_views=page_views,
            bookings_daily=bookings_daily,
            status_breakdown=status_breakdown,
            top_searches=top_searches,
            top_props=top_props,
            user_growth=user_growth,
            active_section='analytics',
        )
    except Exception:
        log.exception('Analytics failed')
        flash('Could not load analytics.', 'error')
        return redirect(url_for('admin.dashboard'))


# ============================================================
# USERS CRUD
# ============================================================
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    page        = get_page()
    q           = _clean(request.args.get('q'), 100)
    role_filter = _clean(request.args.get('role'), 20)

    filters = {}
    if q:
        safe = re.escape(q)
        filters['$or'] = [
            {'name':  {'$regex': safe, '$options': 'i'}},
            {'email': {'$regex': safe, '$options': 'i'}},
        ]
    if role_filter in ('client', 'super_admin'):
        filters['role'] = role_filter

    pagination = _paginate(
        db.db['users'], filters, page,
        projection={'password_hash': 0},
    )

    global_total = User.count({})

    return _render(
        'admin/users.html',
        users=pagination['items'],
        pagination=pagination,
        global_total=global_total,
        q=q,
        role_filter=role_filter,
        has_filters=bool(q or role_filter),
        active_section='users',
    )


@admin_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
@admin_required
def user_create():
    form = UserCreateForm()
    if form.validate_on_submit():
        if User.find_by_email(form.email.data):
            flash('Email already exists.', 'error')
        else:
            user = User(
                email=form.email.data,
                name=form.name.data,
                phone=form.phone.data or '',
                country=form.country.data or '',
                role=form.role.data,
                tier=form.tier.data,
            )
            user.set_password(form.password.data)
            try:
                db.db['users'].insert_one(user.to_dict(include_password=True))
                _audit('user.create', extra=form.email.data)
                flash(f'User {form.email.data} created.', 'success')
                return redirect(url_for('admin.users'))
            except Exception:
                log.exception('User create failed')
                flash('Could not create user — email may be in use.', 'error')

    return _render(
        'admin/user_form.html', form=form, user=None, mode='create',
        active_section='users',
    )


@admin_bp.route('/users/<uid>', methods=['GET', 'POST'])
@login_required
@admin_required
def user_detail(uid):
    if not _is_valid_oid(uid):
        abort(404)

    user = User.find_by_id(uid)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))

    is_self = (user.id == current_user.id)

    form = UserEditForm(data={
        'name':      user.name,
        'email':     user.email,
        'phone':     user.phone,
        'country':   user.country,
        'tier':      user.tier,
        'role':      user.role,
        'is_active': user._is_active,
    })

    if form.validate_on_submit():
        # Guard: self-role / self-deactivate
        if is_self and form.role.data != 'super_admin':
            flash('You cannot change your own admin role.', 'error')
            return redirect(url_for('admin.user_detail', uid=uid))
        if is_self and not form.is_active.data:
            flash('You cannot deactivate your own account.', 'error')
            return redirect(url_for('admin.user_detail', uid=uid))

        # Guard: don't let the last super_admin be demoted or deactivated.
        if user.role == 'super_admin' and (
            form.role.data != 'super_admin' or not form.is_active.data
        ):
            remaining = User.count({
                'role': 'super_admin',
                'is_active': True,
                '_id': {'$ne': ObjectId(uid)},
            })
            if remaining == 0:
                flash('Cannot remove the last active super admin.', 'error')
                return redirect(url_for('admin.user_detail', uid=uid))

        updates = {
            'name':      _clean(form.name.data, 200),
            'email':     _clean(form.email.data, 200).lower(),
            'phone':     _clean(form.phone.data, 40),
            'country':   _clean(form.country.data, 80),
            'tier':      form.tier.data,
            'role':      form.role.data,
            'is_active': bool(form.is_active.data),
        }

        if updates['email'] != user.email:
            existing = User.find_by_email(updates['email'])
            if existing and existing.id != user.id:
                flash('Email already in use.', 'error')
                return redirect(url_for('admin.user_detail', uid=uid))

        if form.new_password.data:
            from werkzeug.security import generate_password_hash
            updates['password_hash'] = generate_password_hash(form.new_password.data)

        try:
            db.db['users'].update_one({'_id': ObjectId(uid)}, {'$set': updates})
            _audit('user.update', target=uid)
            flash('User updated.', 'success')
            return redirect(_safe_next('admin.users'))
        except Exception:
            log.exception('User update failed')
            flash('Could not update user.', 'error')

    user_bookings  = Booking.by_user(uid, limit=20)
    user_inquiries = Inquiry.by_email(user.email)[:10] if user.email else []

    return _render(
        'admin/user_detail.html',
        form=form, user=user, is_self=is_self,
        user_bookings=user_bookings, user_inquiries=user_inquiries,
        active_section='users',
    )


@admin_bp.route('/users/<uid>/delete', methods=['POST'])
@login_required
@admin_required
def user_delete(uid):
    if not _is_valid_oid(uid):
        abort(404)
    if uid == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.users'))

    user = User.find_by_id(uid)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))

    # Guard: never delete the last super admin.
    if user.role == 'super_admin':
        remaining = User.count({
            'role': 'super_admin',
            'is_active': True,
            '_id': {'$ne': ObjectId(uid)},
        })
        if remaining == 0:
            flash('Cannot delete the last active super admin.', 'error')
            return redirect(url_for('admin.users'))

    confirm_email = _clean(request.form.get('confirm_email'), 200).lower()
    if confirm_email and confirm_email != user.email.lower():
        flash('Delete confirmation did not match the user email.', 'error')
        return redirect(url_for('admin.user_detail', uid=uid))

    if User.delete(uid):
        _audit('user.delete', target=uid, extra=user.email)
        flash(f'User {user.email} deleted.', 'info')
    else:
        flash('Could not delete user.', 'error')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/export')
@login_required
@admin_required
def users_export():
    rows = []
    for u in db.db['users'].find({}, {'password_hash': 0}):
        rows.append([
            u.get('name', ''),
            u.get('email', ''),
            u.get('phone', ''),
            u.get('country', ''),
            u.get('tier', ''),
            u.get('role', ''),
            str(u.get('is_active', True)),
            _normalize_iso(u.get('member_since')) or '',
        ])

    _audit('users.export')
    return _csv_response(
        rows,
        ['Name', 'Email', 'Phone', 'Country', 'Tier', 'Role', 'Active', 'Member Since'],
        'lereve-users',
    )


# ============================================================
# PROPERTIES
# ============================================================
@admin_bp.route('/properties')
@login_required
@admin_required
def properties():
    page       = get_page()
    q          = _clean(request.args.get('q'), 100)
    cat_filter = _clean(request.args.get('category'), 100)

    filters = {}
    if q:
        safe = re.escape(q)
        filters['$or'] = [
            {'title':    {'$regex': safe, '$options': 'i'}},
            {'location': {'$regex': safe, '$options': 'i'}},
            {'category': {'$regex': safe, '$options': 'i'}},
        ]
    if cat_filter and cat_filter != 'all':
        filters['category'] = cat_filter

    pagination = _paginate(db.db['properties'], filters, page)

    return _render(
        'admin/properties.html',
        properties=pagination['items'],
        pagination=pagination,
        categories=Category.all(),
        global_total=Property.count({}),
        q=q,
        cat_filter=cat_filter,
        has_filters=bool(q or (cat_filter and cat_filter != 'all')),
        active_section='properties',
    )


@admin_bp.route('/properties/new', methods=['GET', 'POST'])
@login_required
@admin_required
def property_create():
    form = PropertyForm()

    if form.validate_on_submit():
        try:
            subdir = current_app.config.get('UPLOAD_SUBDIR_PROPERTIES', 'properties')

            # Save the main image first (required on create).
            main_image = save_image(form.image.data, subdir=subdir)

            if not main_image:
                flash('Please upload a main image.', 'error')
                return _render(
                    'admin/property_form.html',
                    form=form, property=None, mode='create',
                    active_section='properties',
                )

            # Save the gallery (optional, multiple files).
            gallery_paths = save_images(form.gallery.data, subdir=subdir)

            payload = _property_payload(form)
            payload['image'] = main_image
            payload['gallery'] = gallery_paths

            Property.create(payload)
            _audit('property.create', extra=form.title.data)
            action = (request.form.get('action') or 'save').strip()
            if action == 'save_and_new':
                flash('Property added. Ready for the next one.', 'success')
                return redirect(url_for('admin.property_create'))
            flash('Property added successfully.', 'success')
            return redirect(url_for('admin.properties'))
        except Exception as e:
            log.exception('Property create failed')
            flash(f'Could not save: {e}', 'error')

    return _render(
        'admin/property_form.html',
        form=form, property=None, mode='create',
        active_section='properties',
    )


@admin_bp.route('/properties/<pid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def property_edit(pid):
    if not _is_valid_oid(pid):
        abort(404)

    prop = Property.get(pid)
    if not prop:
        flash('Property not found.', 'error')
        return redirect(url_for('admin.properties'))

    # NOTE: do NOT pass `image` or `gallery` into data= — they're FileFields.
    form = PropertyForm(data={
        'title':          prop.get('title', ''),
        'category':       prop.get('category', ''),
        'location':       prop.get('location', ''),
        'original_price': prop.get('original_price', 0),
        'price':          prop.get('price', 0),
        'beds':           prop.get('beds', 1),
        'baths':          prop.get('baths', 1),
        'guests':         prop.get('guests', 1),
        'rating':         prop.get('rating', 5),
        'reviews_count':  prop.get('reviews_count', 0),
        'amenities':      ', '.join(prop.get('amenities') or []),
        'description':    prop.get('description', ''),
    })

    if form.validate_on_submit():
        try:
            subdir = current_app.config.get('UPLOAD_SUBDIR_PROPERTIES', 'properties')

            old_image   = prop.get('image') or ''
            old_gallery = list(prop.get('gallery') or [])

            # New main image? Fall back to the old one.
            new_image = save_image(form.image.data, subdir=subdir)

            # New gallery images (appended to the existing ones).
            new_gallery = save_images(form.gallery.data, subdir=subdir)

            # Gallery removal flag — comma-separated paths the user
            # chose to delete. Submitted by the template's remove buttons.
            remove_raw = request.form.get('gallery_remove') or ''
            remove_paths = [p.strip() for p in remove_raw.split(',') if p.strip()]

            # Build the final gallery.
            final_gallery = [p for p in old_gallery if p not in remove_paths]
            final_gallery.extend(new_gallery)

            payload = _property_payload(form)
            payload['image'] = new_image or old_image
            payload['gallery'] = final_gallery

            if prop.get('created_at'):
                payload['created_at'] = prop['created_at']

            Property.update(pid, payload)

            # Delete files that are no longer referenced.
            if new_image and old_image and old_image != new_image:
                delete_image(old_image)
            if remove_paths:
                delete_images(remove_paths)

            _audit('property.update', target=pid, extra=form.title.data)
            flash('Property updated.', 'success')
            return redirect(_safe_next('admin.properties'))
        except Exception as e:
            log.exception('Property update failed')
            flash(f'Could not update: {e}', 'error')

    return _render(
        'admin/property_form.html',
        form=form, property=prop, mode='edit',
        active_section='properties',
    )


@admin_bp.route('/properties/<pid>/delete', methods=['POST'])
@login_required
@admin_required
def property_delete(pid):
    if not _is_valid_oid(pid):
        abort(404)

    prop = Property.get(pid)
    if prop:
        # Clean up any files on disk before deleting the doc.
        delete_image(prop.get('image'))
        delete_images(prop.get('gallery') or [])

        Property.delete(pid)
        _audit('property.delete', target=pid, extra=prop.get('title'))
        flash(f'Property "{prop.get("title")}" deleted.', 'info')
    else:
        flash('Property not found.', 'error')
    return redirect(url_for('admin.properties'))


def _property_payload(form):
    """Extract a safe payload from a PropertyForm.

    NOTE: `image` and `gallery` are FileFields — the route saves them
    separately and injects the resulting paths into the payload.
    """
    def _float(v, d=0.0):
        try:
            return float(v or d)
        except (TypeError, ValueError):
            return d

    def _int(v, d=1):
        try:
            return int(v or d)
        except (TypeError, ValueError):
            return d

    return {
        'title':          _clean(form.title.data, 200),
        'category':       _clean(form.category.data, 100),
        'location':       _clean(form.location.data, 200),
        'original_price': _float(form.original_price.data),
        'price':          _float(form.price.data),
        'beds':           _int(form.beds.data, 1),
        'baths':          _float(form.baths.data, 1.0),
        'guests':         _int(form.guests.data, 1),
        'rating':         _float(form.rating.data, 5.0),
        'reviews_count':  _int(form.reviews_count.data, 0),
        'amenities':      [a.strip() for a in (form.amenities.data or '').split(',') if a.strip()],
        'description':    _clean(form.description.data, 3000),
        # 'image' and 'gallery' are added by the caller.
    }


# ============================================================
# CATEGORIES
# ============================================================
@admin_bp.route('/categories')
@login_required
@admin_required
def categories():
    q = _clean(request.args.get('q'), 100)

    items = Category.all()

    if q:
        needle = q.lower()
        items = [
            c for c in items
            if needle in (c.get('name') or '').lower()
            or needle in (c.get('description') or '').lower()
        ]

    names = [c.get('name') for c in items if c.get('name')]
    counts = {}
    if names:
        pipeline = [
            {'$match': {'category': {'$in': names}}},
            {'$group': {'_id': '$category', 'count': {'$sum': 1}}},
        ]
        for r in db.db['properties'].aggregate(pipeline):
            counts[r['_id']] = r['count']

    for c in items:
        c['property_count'] = counts.get(c.get('name'), 0)

    return _render(
        'admin/categories.html',
        categories=items,
        q=q,
        active_section='categories',
    )


@admin_bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
@admin_required
def category_create():
    form = CategoryForm()
    if form.validate_on_submit():
        try:
            cid = Category.create({
                'name':        _clean(form.name.data, 80),
                'description': _clean(form.description.data, 500),
                'icon':        _clean(form.icon.data, 80) or 'fa-house-chimney',
                'order':       int(form.order.data or 0),
            })
            if cid:
                _audit('category.create', target=cid)
                flash('Category created.', 'success')
                if (request.form.get('action') or '') == 'save_and_new':
                    return redirect(url_for('admin.category_create'))
                return redirect(url_for('admin.categories'))
            flash('Could not create — name may already exist.', 'error')
        except Exception:
            log.exception('Category create failed')
            flash('Could not create category.', 'error')

    return _render(
        'admin/category_form.html', form=form, category=None, mode='create',
        active_section='categories',
    )


@admin_bp.route('/categories/<cid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def category_edit(cid):
    if not _is_valid_oid(cid):
        abort(404)

    cat = Category.get(cid)
    if not cat:
        flash('Category not found.', 'error')
        return redirect(url_for('admin.categories'))

    form = CategoryForm(data={
        'name':        cat.get('name', ''),
        'description': cat.get('description', ''),
        'icon':        cat.get('icon', 'fa-house-chimney'),
        'order':       cat.get('order', 0),
    })

    if form.validate_on_submit():
        ok = Category.update(cid, {
            'name':        _clean(form.name.data, 80),
            'description': _clean(form.description.data, 500),
            'icon':        _clean(form.icon.data, 80) or 'fa-house-chimney',
            'order':       int(form.order.data or 0),
        })
        if ok:
            _audit('category.update', target=cid)
            flash('Category updated.', 'success')
            return redirect(_safe_next('admin.categories'))
        flash('Could not update.', 'error')

    return _render(
        'admin/category_form.html', form=form, category=cat, mode='edit',
        active_section='categories',
    )


@admin_bp.route('/categories/<cid>/delete', methods=['POST'])
@login_required
@admin_required
def category_delete(cid):
    if not _is_valid_oid(cid):
        abort(404)

    cat = Category.get(cid)
    if not cat:
        flash('Category not found.', 'error')
        return redirect(url_for('admin.categories'))

    in_use = Property.count_by_category(cat.get('name'))
    if in_use > 0:
        flash(f'Cannot delete — {in_use} propert{"y" if in_use == 1 else "ies"} use it.', 'error')
        return redirect(url_for('admin.categories'))

    Category.delete(cid)
    _audit('category.delete', target=cid, extra=cat.get('name'))
    flash('Category deleted.', 'info')
    return redirect(url_for('admin.categories'))


# ============================================================
# BOOKINGS
# ============================================================
@admin_bp.route('/bookings')
@login_required
@admin_required
def bookings():
    page          = get_page()
    status_filter = _clean(request.args.get('status'), 50)
    q             = _clean(request.args.get('q'), 100)
    from_date     = _clean(request.args.get('from'), 20)
    to_date       = _clean(request.args.get('to'), 20)

    filters = {}

    if status_filter in current_app.config['BOOKING_STATUSES']:
        filters['status'] = status_filter

    if q:
        safe = re.escape(q)
        filters['$or'] = [
            {'user_name':       {'$regex': safe, '$options': 'i'}},
            {'user_email':      {'$regex': safe, '$options': 'i'}},
            {'property':        {'$regex': safe, '$options': 'i'}},
            {'confirmation_id': {'$regex': safe, '$options': 'i'}},
        ]

    rng = _daterange_or_none(from_date, to_date, field='check_in', as_datetime=False)
    if rng:
        filters.update(rng)

    # ---- CSV export branch ----
    if request.args.get('format') == 'csv':
        try:
            rows = list(
                db.db['bookings']
                .find(filters)
                .sort('created_at', -1)
                .limit(5000)
            )
            buf = io.StringIO()
            buf.write('\ufeff')
            w = csv.writer(buf)
            w.writerow([
                'Confirmation', 'Guest', 'Email', 'Property', 'Location',
                'Check-In', 'Check-Out', 'Nights', 'Guests', 'Total',
                'Payment Status', 'Booking Status', 'Payment Reference',
                'Paid At', 'Created At',
            ])
            for b in rows:
                w.writerow([
                    b.get('confirmation_id', ''),
                    b.get('user_name', ''),
                    b.get('user_email', ''),
                    b.get('property', ''),
                    b.get('location', ''),
                    b.get('check_in', ''),
                    b.get('check_out', ''),
                    b.get('nights', ''),
                    b.get('guests', ''),
                    b.get('total', ''),
                    b.get('payment_status', ''),
                    b.get('status', ''),
                    b.get('payment_reference', ''),
                    _normalize_iso(b.get('paid_at')) or '',
                    _normalize_iso(b.get('created_at')) or '',
                ])

            filename = (
                f"lereve-bookings-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
            )
            _audit('bookings.export', extra=filename)
            return Response(
                buf.getvalue().encode('utf-8'),
                mimetype='text/csv; charset=utf-8',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Cache-Control': 'no-store',
                },
            )
        except Exception:
            log.exception('Bookings CSV export failed')
            flash('Could not export bookings.', 'error')
            return redirect(url_for('admin.bookings'))

    pagination = _paginate(db.db['bookings'], filters, page)

    total_revenue = Booking.revenue_total({'payment_status': 'paid'})
    pending_count = Booking.count({'payment_status': 'pending'})
    global_total  = Booking.count({})

    return _render(
        'admin/bookings.html',
        bookings=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        total_revenue=total_revenue,
        pending_count=pending_count,
        global_total=global_total,
        q=q,
        from_date=from_date,
        to_date=to_date,
        has_filters=bool(status_filter or q or from_date or to_date),
        active_section='bookings',
    )


@admin_bp.route('/bookings/<bid>')
@login_required
@admin_required
def booking_detail(bid):
    if not _is_valid_oid(bid):
        abort(404)
    b = Booking.get(bid)
    if not b:
        flash('Booking not found.', 'error')
        return redirect(url_for('admin.bookings'))
    return _render('admin/booking_detail.html', booking=b, active_section='bookings')


@admin_bp.route('/bookings/<bid>/status', methods=['POST'])
@login_required
@admin_required
def booking_status(bid):
    if not _is_valid_oid(bid):
        abort(404)

    status = _clean(request.form.get('status'), 50)
    if status not in current_app.config['BOOKING_STATUSES']:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.bookings'))

    booking_doc = Booking.get(bid)
    if not booking_doc:
        flash('Booking not found.', 'error')
        return redirect(url_for('admin.bookings'))

    update = {'status': status}

    reason = _clean(request.form.get('cancellation_reason'), 500)
    if reason:
        update['cancellation_reason'] = reason

    if status == 'cancelled' and booking_doc.get('payment_status') == 'paid':
        update['payment_status'] = 'refund-pending'

    Booking.update(bid, update)
    _audit('booking.status', target=bid, extra=status)
    flash(f'Booking marked as {status}.', 'success')

    referer = request.form.get('return_to') or request.referrer or ''
    if f'/bookings/{bid}' in referer:
        return redirect(url_for('admin.booking_detail', bid=bid))
    return redirect(url_for('admin.bookings'))


# ============================================================
# INQUIRIES
# ============================================================
@admin_bp.route('/inquiries')
@login_required
@admin_required
def inquiries():
    page          = get_page()
    status_filter = _clean(request.args.get('status'), 50)
    q             = _clean(request.args.get('q'), 100)
    from_date     = _clean(request.args.get('from'), 20)
    to_date       = _clean(request.args.get('to'), 20)

    filters = {}

    if status_filter in current_app.config['INQUIRY_STATUSES']:
        filters['status'] = status_filter

    if q:
        safe = re.escape(q)
        filters['$or'] = [
            {'name':     {'$regex': safe, '$options': 'i'}},
            {'email':    {'$regex': safe, '$options': 'i'}},
            {'phone':    {'$regex': safe, '$options': 'i'}},
            {'property': {'$regex': safe, '$options': 'i'}},
            {'message':  {'$regex': safe, '$options': 'i'}},
        ]

    rng = _daterange_or_none(from_date, to_date, field='created_at', as_datetime=True)
    if rng:
        filters.update(rng)

    pagination = _paginate(db.db['inquiries'], filters, page)

    new_count       = Inquiry.count({'status': 'new'})
    contacted_count = Inquiry.count({'status': 'contacted'})
    booked_count    = Inquiry.count({'status': 'booked'})
    archived_count  = Inquiry.count({'status': 'archived'})
    global_total    = Inquiry.count({})

    return _render(
        'admin/inquiries.html',
        inquiries=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        new_count=new_count,
        contacted_count=contacted_count,
        booked_count=booked_count,
        archived_count=archived_count,
        global_total=global_total,
        q=q,
        from_date=from_date,
        to_date=to_date,
        has_filters=bool(status_filter or q or from_date or to_date),
        active_section='inquiries',
    )


@admin_bp.route('/inquiries/<iid>/status', methods=['POST'])
@login_required
@admin_required
def inquiry_status(iid):
    if not _is_valid_oid(iid):
        abort(404)

    status = _clean(request.form.get('status'), 50)
    if status not in current_app.config['INQUIRY_STATUSES']:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.inquiries'))
    Inquiry.update(iid, {'status': status})
    _audit('inquiry.status', target=iid, extra=status)
    flash(f'Inquiry marked as {status}.', 'success')
    return redirect(_safe_next('admin.inquiries'))


@admin_bp.route('/inquiries/<iid>/delete', methods=['POST'])
@login_required
@admin_required
def inquiry_delete(iid):
    if not _is_valid_oid(iid):
        abort(404)
    Inquiry.delete(iid)
    _audit('inquiry.delete', target=iid)
    flash('Inquiry deleted.', 'info')
    return redirect(url_for('admin.inquiries'))


# ============================================================
# REVIEWS
# ============================================================
@admin_bp.route('/reviews')
@login_required
@admin_required
def reviews():
    page          = get_page()
    status_filter = _clean(request.args.get('status'), 50)
    q             = _clean(request.args.get('q'), 100)
    from_date     = _clean(request.args.get('from'), 20)
    to_date       = _clean(request.args.get('to'), 20)

    filters = {}
    if status_filter in current_app.config['REVIEW_STATUSES']:
        filters['status'] = status_filter
    if q:
        safe = re.escape(q)
        filters['$or'] = [
            {'name':     {'$regex': safe, '$options': 'i'}},
            {'property': {'$regex': safe, '$options': 'i'}},
            {'text':     {'$regex': safe, '$options': 'i'}},
        ]

    rng = _daterange_or_none(from_date, to_date, field='created_at', as_datetime=True)
    if rng:
        filters.update(rng)

    pagination = _paginate(db.db['reviews'], filters, page)

    return _render(
        'admin/reviews.html',
        reviews=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        global_total=Review.count({}),
        q=q,
        from_date=from_date,
        to_date=to_date,
        has_filters=bool(status_filter or q or from_date or to_date),
        active_section='reviews',
    )


@admin_bp.route('/reviews/new', methods=['GET', 'POST'])
@login_required
@admin_required
def review_create():
    form = AdminReviewForm()

    if form.validate_on_submit():
        # Save the uploaded avatar (if any) BEFORE creating the doc.
        subdir = current_app.config.get('UPLOAD_SUBDIR_REVIEWS', 'reviews')
        avatar_path = save_image(form.avatar.data, subdir=subdir)

        Review.create({
            'name':     _clean(form.name.data, 120),
            'property': _clean(form.property.data, 200),
            'rating':   int(form.rating.data),
            'text':     _clean(form.text.data, 2000),
            'avatar':   avatar_path or '',
            'status':   form.status.data,
            'source':   'admin',
        })
        _audit('review.create', extra=form.name.data)
        flash('Review created.', 'success')
        if (request.form.get('action') or '') == 'save_and_new':
            return redirect(url_for('admin.review_create'))
        return redirect(url_for('admin.reviews'))

    return _render(
        'admin/review_form.html', form=form, review=None, mode='create',
        active_section='reviews',
    )


@admin_bp.route('/reviews/<rid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def review_edit(rid):
    if not _is_valid_oid(rid):
        abort(404)

    review = Review.get(rid)
    if not review:
        flash('Review not found.', 'error')
        return redirect(url_for('admin.reviews'))

    form = AdminReviewForm(data={
        'name':     review.get('name', ''),
        'property': review.get('property', ''),
        'rating':   str(review.get('rating', 5)),
        'text':     review.get('text', ''),
        'status':   review.get('status', 'pending'),
        # NOTE: avatar is a FileField — do NOT pass a value here.
    })

    if form.validate_on_submit():
        old_avatar = review.get('avatar') or ''
        subdir     = current_app.config.get('UPLOAD_SUBDIR_REVIEWS', 'reviews')

        # Save new upload if one was provided.
        new_avatar = save_image(form.avatar.data, subdir=subdir)
        clear_flag = request.form.get('avatar__clear') == '1'

        updates = {
            'name':     _clean(form.name.data, 120),
            'property': _clean(form.property.data, 200),
            'rating':   int(form.rating.data),
            'text':     _clean(form.text.data, 2000),
            'status':   form.status.data,
        }

        if new_avatar:
            # New file uploaded — replace.
            updates['avatar'] = new_avatar
        elif clear_flag:
            # Explicit removal — no replacement.
            updates['avatar'] = ''

        Review.update(rid, updates)

        # Clean up the old file only after the DB write succeeds.
        if old_avatar and (new_avatar or clear_flag) and old_avatar != new_avatar:
            delete_image(old_avatar)

        _audit('review.update', target=rid)
        flash('Review updated.', 'success')
        return redirect(_safe_next('admin.reviews'))

    return _render(
        'admin/review_form.html', form=form, review=review, mode='edit',
        active_section='reviews',
    )


@admin_bp.route('/reviews/<rid>/status', methods=['POST'])
@login_required
@admin_required
def review_status(rid):
    if not _is_valid_oid(rid):
        abort(404)

    status = _clean(request.form.get('status'), 50)
    if status not in current_app.config['REVIEW_STATUSES']:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.reviews'))
    Review.update(rid, {'status': status})
    _audit('review.status', target=rid, extra=status)
    flash(f'Review {status}.', 'success')
    return redirect(_safe_next('admin.reviews'))


@admin_bp.route('/reviews/<rid>/delete', methods=['POST'])
@login_required
@admin_required
def review_delete(rid):
    if not _is_valid_oid(rid):
        abort(404)

    # Delete the avatar file too, best-effort.
    review = Review.get(rid)
    if review and review.get('avatar'):
        delete_image(review['avatar'])

    Review.delete(rid)
    _audit('review.delete', target=rid)
    flash('Review deleted.', 'info')
    return redirect(url_for('admin.reviews'))


# ============================================================
# MESSAGES (Admin Inbox)
# ============================================================
@admin_bp.route('/messages')
@login_required
@admin_required
def messages():
    threads = Message.latest_per_user()
    for t in threads:
        tid = t.get('_id')             # canonical thread_id string
        t['unread'] = Message.unread_for_admin(tid) if tid else 0
    return _render(
        'admin/messages.html',
        threads=threads,
        active_section='messages',
    )


def _thread_identity(thread_id):
    """Look up {user_id, user_name, user_email} for a thread.

    Prefers the newest message that already carries the metadata;
    falls back to a Guest record so callers can still create a reply.
    """
    try:
        doc = (
            db.db['messages']
            .find_one({'thread_id': thread_id}, sort=[('created_at', -1)])
        )
    except Exception:
        log.exception('thread identity lookup failed')
        doc = None

    if not doc:
        return {'user_id': None, 'user_name': 'Guest', 'user_email': ''}

    return {
        'user_id':    doc.get('user_id'),
        'user_name':  doc.get('user_name') or 'Guest',
        'user_email': doc.get('user_email') or '',
    }


@admin_bp.route('/messages/<path:thread_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def message_thread(thread_id):
    if request.method == 'POST':
        text = _clean(request.form.get('text'), 2000)
        if text:
            identity = _thread_identity(thread_id)
            Message.create({
                'thread_id':  thread_id,
                'user_id':    identity['user_id'],
                'user_name':  identity['user_name'],
                'user_email': identity['user_email'],
                'sender':     'admin',
                'text':       text,
            })
            _audit('message.reply', target=thread_id)
            flash('Reply sent.', 'success')
        else:
            flash('Message cannot be empty.', 'error')
        return redirect(url_for('admin.message_thread', thread_id=thread_id))

    msgs = Message.by_thread(thread_id)
    Message.mark_read(thread_id, by='admin')

    return _render(
        'admin/message_thread.html',
        messages=msgs,
        thread_id=thread_id,
        active_section='messages',
    )


# ============================================================
# JOURNAL
# ============================================================
@admin_bp.route('/journal')
@login_required
@admin_required
def journal():
    page      = get_page()
    q         = _clean(request.args.get('q'), 100)
    from_date = _clean(request.args.get('from'), 20)
    to_date   = _clean(request.args.get('to'), 20)

    filters = {}

    if q:
        safe = re.escape(q)
        filters['email'] = {'$regex': safe, '$options': 'i'}

    rng = _daterange_or_none(from_date, to_date, field='subscribed_at', as_datetime=True)
    if rng:
        filters.update(rng)

    # ---- CSV export branch ----
    if request.args.get('format') == 'csv':
        try:
            rows = list(
                db.db['journal_subscribers']
                .find(filters)
                .sort('subscribed_at', -1)
                .limit(50000)
            )
            buf = io.StringIO()
            buf.write('\ufeff')
            w = csv.writer(buf)
            w.writerow(['Email', 'Subscribed At'])
            for r in rows:
                w.writerow([
                    r.get('email', ''),
                    _normalize_iso(r.get('subscribed_at')) or '',
                ])
            filename = (
                f"lereve-journal-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
            )
            _audit('journal.export', extra=filename)
            return Response(
                buf.getvalue().encode('utf-8'),
                mimetype='text/csv; charset=utf-8',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Cache-Control': 'no-store',
                },
            )
        except Exception:
            log.exception('Journal CSV export failed')
            flash('Could not export subscribers.', 'error')
            return redirect(url_for('admin.journal'))

    pagination = _paginate(
        db.db['journal_subscribers'], filters, page,
        sort_field='subscribed_at',
    )

    global_total = JournalSubscriber.count({})

    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    this_month = JournalSubscriber.count({
        'subscribed_at': {'$gte': month_start},
    })

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    last_7_days = JournalSubscriber.count({
        'subscribed_at': {'$gte': seven_days_ago},
    })

    return _render(
        'admin/journal.html',
        subscribers=pagination['items'],
        pagination=pagination,
        global_total=global_total,
        total_count=pagination['total'],
        this_month_count=this_month,
        last_7_days=last_7_days,
        q=q,
        from_date=from_date,
        to_date=to_date,
        has_filters=bool(q or from_date or to_date),
        active_section='journal',
    )


@admin_bp.route('/journal/<sid>/delete', methods=['POST'])
@login_required
@admin_required
def journal_delete(sid):
    if not _is_valid_oid(sid):
        abort(404)
    JournalSubscriber.delete(sid)
    _audit('journal.delete', target=sid)
    flash('Subscriber removed.', 'info')
    return redirect(url_for('admin.journal'))


# ============================================================
# SETTINGS
# ============================================================
@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    site_settings = Settings.get()
    form = SettingsForm(data=site_settings)

    if form.validate_on_submit():
        updates = {
            'site_name':     _clean(form.site_name.data, 120),
            'contact_email': _clean(form.contact_email.data, 200),
            'whatsapp':      _clean(form.whatsapp.data, 40),
            'instagram':     _clean(form.instagram.data, 60),
        }
        Settings.update(updates)
        _audit('settings.update')
        flash('Settings saved.', 'success')
        return redirect(url_for('admin.settings'))

    return _render('admin/settings.html', form=form, active_section='settings')


@admin_bp.route('/settings/export')
@login_required
@admin_required
def export_data():
    payload = {
        'exported_at': utcnow().isoformat(),
        'version':     '2.0',
        'exported_by': current_user.email if current_user.is_authenticated else 'unknown',
        'site':        Settings.get(),
        'categories':  Category.all(),
        'properties':  Property.all(limit=10000),
        'inquiries':   Inquiry.all(limit=10000),
        'reviews':     Review.all(limit=10000),
        'bookings':    Booking.all(limit=10000),
        'subscribers': JournalSubscriber.all(limit=10000),
    }
    body = json.dumps(payload, indent=2, default=_normalize_iso, ensure_ascii=False)
    filename = f"lereve-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    _audit('settings.export', extra=filename)
    return Response(
        body,
        mimetype='application/json; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-store',
        },
    )


# ============================================================
# API (dashboard live stats)
# ============================================================
@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """
    Lightweight stats endpoint polled every 60s by the dashboard.

    Results are cached for 30 seconds, so a dashboard reload + manual
    refresh do not hammer Mongo.
    """
    now_ts = datetime.now(timezone.utc).timestamp()
    cached = _STATS_CACHE.get('value')
    if cached and _STATS_CACHE.get('expires_at', 0) > now_ts:
        return jsonify({
            'success': True,
            'stats': cached,
            'refreshed_at': _STATS_CACHE.get('refreshed_at'),
            'cached': True,
        })

    try:
        stats = {
            'properties':          Property.count(),
            'inquiries':           Inquiry.count(),
            'reviews':             Review.count(),
            'categories':          Category.count(),
            'users':               User.count({'role': 'client'}),
            'new_inquiries':       Inquiry.count({'status': 'new'}),
            'pending_reviews':     Review.count({'status': 'pending'}),
            'unread_messages':     Message.count({
                'sender': 'client', 'read_by_admin': False,
            }),
            'confirmed_bookings':  Booking.count({'status': 'confirmed'}),
            'pending_bookings':    Booking.count({'status': 'pending'}),
            'cancelled_bookings':  Booking.count({'status': 'cancelled'}),
        }
    except Exception:
        log.exception('API stats failed')
        return jsonify({'success': False, 'error': 'Stats unavailable'}), 500

    refreshed_at = utcnow().isoformat()
    _STATS_CACHE['value'] = stats
    _STATS_CACHE['expires_at'] = now_ts + _STATS_TTL_SECONDS
    _STATS_CACHE['refreshed_at'] = refreshed_at

    return jsonify({
        'success': True,
        'stats': stats,
        'refreshed_at': refreshed_at,
        'cached': False,
    })


# ============================================================
# MESSAGES — JSON endpoints for the thread view
# ============================================================
@admin_bp.route('/messages/<path:thread_id>/poll')
@login_required
@admin_required
def message_poll(thread_id):
    """Return messages created since ?since=<iso> for the live thread."""
    since = _clean(request.args.get('since'), 40)
    all_msgs = Message.by_thread(thread_id)

    if since:
        all_msgs = [
            m for m in all_msgs
            if (m.get('created_at') or '') > since
        ]
        if all_msgs:
            Message.mark_read(thread_id, by='admin')

    return jsonify({
        'success': True,
        'messages': all_msgs,
        'server_time': utcnow().isoformat(),
    })


@admin_bp.route('/messages/<path:thread_id>/send', methods=['POST'])
@login_required
@admin_required
def message_send(thread_id):
    """JSON reply endpoint — used by the admin thread page."""
    body = request.get_json(silent=True) or {}
    text = _clean(body.get('text'), 2000)
    if not text:
        return jsonify({'success': False, 'error': 'Empty message'}), 400
    if len(text) > 2000:
        return jsonify({'success': False, 'error': 'Message too long'}), 400

    identity = _thread_identity(thread_id)
    Message.create({
        'thread_id':  thread_id,
        'user_id':    identity['user_id'],
        'user_name':  identity['user_name'],
        'user_email': identity['user_email'],
        'sender':     'admin',
        'text':       text,
    })
    _audit('message.reply', target=thread_id)

    # Return the just-created message so the client can render it.
    created = Message.by_thread(thread_id, limit=1)
    return jsonify({
        'success': True,
        'message': created[-1] if created else None,
    })