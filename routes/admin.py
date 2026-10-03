"""
============================================================
ADMIN ROUTES
============================================================
"""
import csv
import io
import json
import logging
import re
from datetime import datetime, timezone, timedelta

from bson import ObjectId

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, jsonify, current_app, Response, g,
)
from flask_login import login_required, current_user

from extensions import db
from models import (
    Property, Booking, Inquiry, Review, Category,
    JournalSubscriber, Settings, User, Message, AnalyticsEvent,
    utcnow,
)
from forms import (
    PropertyForm, CategoryForm, AdminReviewForm,
    SettingsForm, UserEditForm, UserCreateForm,
)
from utils import admin_required
from utils.pagination import get_page, paginate_mongo


log = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__, template_folder='templates/admin')

PAGE_SIZE = 20


# ============================================================
# HELPERS
# ============================================================
def _clean(v, max_len=2000):
    if not v:
        return ''
    return str(v).strip()[:max_len]


def _badge_counts():
    cached = getattr(g, '_admin_badges', None)
    if cached is not None:
        return cached
    try:
        counts = {
            'pending_inquiries': Inquiry.count({'status': 'new'}),
            'pending_reviews': Review.count({'status': 'pending'}),
            'unread_messages': Message.count({'sender': 'client', 'read_by_admin': False}),
        }
    except Exception:
        counts = {'pending_inquiries': 0, 'pending_reviews': 0, 'unread_messages': 0}
    g._admin_badges = counts
    return counts


def _render(template, **ctx):
    ctx.setdefault('active_section', 'dashboard')
    ctx.update(_badge_counts())
    ctx.setdefault('now', utcnow())
    ctx.setdefault('now_year_month', datetime.now(timezone.utc).strftime('%Y-%m'))
    return render_template(template, **ctx)


def _audit(action, target=None, extra=None):
    try:
        actor = current_user.email if current_user.is_authenticated else 'anonymous'
        ip = request.remote_addr or 'unknown'
        log.info(f'[AUDIT] {actor}@{ip} → {action}'
                 f'{" target=" + str(target) if target else ""}'
                 f'{" extra=" + str(extra) if extra else ""}')
    except Exception:
        pass


def _normalize_iso(v):
    """Convert datetimes to ISO strings; leave other values alone."""
    if not v:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _oid_to_str_list(docs):
    """Convert a list of raw Mongo docs to JSON-safe dicts."""
    return [__import__('models').oid_to_str(d) for d in docs]


def _paginate(collection, filters, page, projection=None):
    """Small wrapper around paginate_mongo that also normalizes items."""
    raw = paginate_mongo(
        collection, filters, [('created_at', -1)], page, PAGE_SIZE, projection,
    )
    return {
        'items': _oid_to_str_list(raw['items']),
        **{k: v for k, v in raw.items() if k != 'items'},
    }


def _daterange_or_none(from_str, to_str, field='created_at', as_datetime=True):
    """
    Build a Mongo range filter from two ISO strings.
    When field is a datetime field (default), uses datetime objects.
    When field stores 'YYYY-MM-DD' strings, pass as_datetime=False.
    """
    if not from_str and not to_str:
        return None

    rng = {}
    if as_datetime:
        if from_str:
            try:
                rng['$gte'] = datetime.fromisoformat(from_str)
            except ValueError:
                pass
        if to_str:
            try:
                # Inclusive of the entire "to" day
                rng['$lt'] = datetime.fromisoformat(to_str) + timedelta(days=1)
            except ValueError:
                pass
    else:
        if from_str:
            rng['$gte'] = from_str
        if to_str:
            rng['$lte'] = to_str

    return {field: rng} if rng else None


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
        paid = Booking.all({'payment_status': 'paid'}, sort=[('paid_at', -1)], limit=1000)
        confirmed = Booking.count({'status': 'confirmed'})
        pending = Booking.count({'status': 'pending'})
        cancelled = Booking.count({'status': 'cancelled'})

        revenue_month = sum(
            float(b.get('total') or 0)
            for b in paid
            if (b.get('paid_at') or '') >= month_start.isoformat()
        )

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
            'properties': Property.count(),
            'inquiries': Inquiry.count(),
            'reviews': Review.count(),
            'categories': Category.count(),
            'users': User.count({'role': 'client'}),
            'new_inquiries': Inquiry.count({'status': 'new'}),
            'pending_reviews': Review.count({'status': 'pending'}),
            'revenue_month': revenue_month,
            'confirmed_bookings': confirmed,
            'pending_bookings': pending,
            'cancelled_bookings': cancelled,
            'occupancy': occupancy,
            'avg_occupancy': avg_occupancy,
            'unread_messages': Message.count({'sender': 'client', 'read_by_admin': False}),
        }

        recent_inquiries = Inquiry.all(sort=[('created_at', -1)], limit=4)
        recent_bookings = Booking.all(sort=[('created_at', -1)], limit=5)

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

            csv_bytes = buf.getvalue().encode('utf-8')
            filename = (
                f"lereve-analytics-{days}d-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
            )
            _audit('analytics.export', extra=filename)
            return Response(
                csv_bytes,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={filename}'},
            )
        except Exception:
            log.exception('Analytics CSV export failed')
            flash('Could not export analytics.', 'error')
            return redirect(url_for('admin.analytics', days=days))

    try:
        events = AnalyticsEvent.count_by_type(days=days)
        # Previous-period comparison (double window, subtract current)
        events_all = AnalyticsEvent.count_by_type(days=days * 2)
        events_prev = {
            k: max(0, (events_all.get(k, 0) - events.get(k, 0)))
            for k in events_all.keys()
        }

        page_views = AnalyticsEvent.daily_series('page_view', days=days)
        bookings_daily = Booking.bookings_by_day(days=days)
        status_breakdown = Booking.status_breakdown()
        top_searches = AnalyticsEvent.top_searches(days=days, limit=10)
        top_props_raw = AnalyticsEvent.top_properties(days=days, limit=10)

        top_props = []
        for t in top_props_raw:
            p = Property.get(t['_id']) if t.get('_id') else None
            top_props.append({
                'title': p.get('title') if p else 'Unknown',
                'count': t['count'],
            })

        since = datetime.now(timezone.utc) - timedelta(days=days)
        user_pipeline = [
            {'$match': {'created_at': {'$gte': since}, 'role': 'client'}},
            {'$group': {
                '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
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

    return _render(
        'admin/users.html',
        users=pagination['items'],
        pagination=pagination,
        q=q,
        role_filter=role_filter,
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
            db.db['users'].insert_one(user.to_dict(include_password=True))
            _audit('user.create', extra=form.email.data)
            flash(f'User {form.email.data} created.', 'success')
            return redirect(url_for('admin.users'))

    return _render(
        'admin/user_form.html', form=form, user=None, mode='create',
        active_section='users',
    )


@admin_bp.route('/users/<uid>', methods=['GET', 'POST'])
@login_required
@admin_required
def user_detail(uid):
    user = User.find_by_id(uid)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))

    is_self = (user.id == current_user.id)

    form = UserEditForm(data={
        'name': user.name,
        'email': user.email,
        'phone': user.phone,
        'country': user.country,
        'tier': user.tier,
        'role': user.role,
        'is_active': user._is_active,
    })

    if form.validate_on_submit():
        if is_self and form.role.data != 'super_admin':
            flash('You cannot change your own admin role.', 'error')
            return redirect(url_for('admin.user_detail', uid=uid))
        if is_self and not form.is_active.data:
            flash('You cannot deactivate your own account.', 'error')
            return redirect(url_for('admin.user_detail', uid=uid))

        updates = {
            'name': form.name.data.strip(),
            'email': form.email.data.lower().strip(),
            'phone': form.phone.data or '',
            'country': form.country.data or '',
            'tier': form.tier.data,
            'role': form.role.data,
            'is_active': form.is_active.data,
        }

        if form.email.data.lower() != user.email:
            existing = User.find_by_email(form.email.data)
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
            return redirect(url_for('admin.users'))
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
    if uid == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.users'))

    user = User.find_by_id(uid)
    if not user:
        flash('User not found.', 'error')
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
    rows = [['Name', 'Email', 'Phone', 'Country', 'Tier', 'Role', 'Active', 'Member Since']]
    for u in db.db['users'].find({}, {'password_hash': 0}):
        rows.append([
            u.get('name', ''), u.get('email', ''), u.get('phone', ''),
            u.get('country', ''), u.get('tier', ''), u.get('role', ''),
            str(u.get('is_active', True)),
            _normalize_iso(u.get('member_since')) or '',
        ])

    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)

    filename = f"lereve-users-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    _audit('users.export', extra=filename)
    return Response(
        buf.getvalue().encode('utf-8'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
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
        q=q,
        cat_filter=cat_filter,
        active_section='properties',
    )


@admin_bp.route('/properties/new', methods=['GET', 'POST'])
@login_required
@admin_required
def property_create():
    form = PropertyForm()
    if form.validate_on_submit():
        try:
            Property.create(_property_payload(form))
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
    prop = Property.get(pid)
    if not prop:
        flash('Property not found.', 'error')
        return redirect(url_for('admin.properties'))

    form = PropertyForm(data={
        'title': prop.get('title', ''),
        'category': prop.get('category', ''),
        'location': prop.get('location', ''),
        'original_price': prop.get('original_price', 0),
        'price': prop.get('price', 0),
        'beds': prop.get('beds', 1),
        'baths': prop.get('baths', 1),
        'guests': prop.get('guests', 1),
        'rating': prop.get('rating', 5),
        'reviews_count': prop.get('reviews_count', 0),
        'image': prop.get('image', ''),
        'gallery': '\n'.join(prop.get('gallery') or []),
        'amenities': ', '.join(prop.get('amenities') or []),
        'description': prop.get('description', ''),
    })

    if form.validate_on_submit():
        try:
            payload = _property_payload(form)
            if prop.get('created_at'):
                payload['created_at'] = prop['created_at']
            Property.update(pid, payload)
            _audit('property.update', target=pid, extra=form.title.data)
            flash('Property updated.', 'success')
            return redirect(url_for('admin.properties'))
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
    prop = Property.get(pid)
    if prop:
        Property.delete(pid)
        _audit('property.delete', target=pid, extra=prop.get('title'))
        flash(f'Property "{prop.get("title")}" deleted.', 'info')
    else:
        flash('Property not found.', 'error')
    return redirect(url_for('admin.properties'))


def _property_payload(form):
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
        'image':          _clean(form.image.data, 500),
        'gallery':        [u.strip() for u in (form.gallery.data or '').splitlines() if u.strip()],
        'amenities':      [a.strip() for a in (form.amenities.data or '').split(',') if a.strip()],
        'description':    _clean(form.description.data, 3000),
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

    counts = {}
    for r in db.db['properties'].aggregate([
        {'$group': {'_id': '$category', 'count': {'$sum': 1}}},
    ]):
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
        cid = Category.create({
            'name':        _clean(form.name.data, 80),
            'description': _clean(form.description.data, 500),
            'icon':        _clean(form.icon.data, 80) or 'fa-house-chimney',
            'order':       int(form.order.data or 0),
        })
        if cid:
            _audit('category.create', target=cid)
            flash('Category created.', 'success')
            return redirect(url_for('admin.categories'))
        flash('Could not create — name may exist.', 'error')
    return _render(
        'admin/category_form.html', form=form, category=None, mode='create',
        active_section='categories',
    )


@admin_bp.route('/categories/<cid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def category_edit(cid):
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
            return redirect(url_for('admin.categories'))
        flash('Could not update.', 'error')

    return _render(
        'admin/category_form.html', form=form, category=cat, mode='edit',
        active_section='categories',
    )


@admin_bp.route('/categories/<cid>/delete', methods=['POST'])
@login_required
@admin_required
def category_delete(cid):
    cat = Category.get(cid)
    if not cat:
        flash('Category not found.', 'error')
        return redirect(url_for('admin.categories'))

    in_use = Property.count_by_category(cat.get('name'))
    if in_use > 0:
        flash(f'Cannot delete — {in_use} properties use it.', 'error')
        return redirect(url_for('admin.categories'))

    Category.delete(cid)
    _audit('category.delete', target=cid)
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

    # check_in is stored as ISO "YYYY-MM-DD" string
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

            csv_bytes = buf.getvalue().encode('utf-8')
            filename = (
                f"lereve-bookings-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
            )
            _audit('bookings.export', extra=filename)
            return Response(
                csv_bytes,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={filename}'},
            )
        except Exception:
            log.exception('Bookings CSV export failed')
            flash('Could not export bookings.', 'error')
            return redirect(url_for('admin.bookings'))

    pagination = _paginate(db.db['bookings'], filters, page)

    total_revenue = Booking.revenue_total({'payment_status': 'paid'})
    pending_count = Booking.count({'payment_status': 'pending'})

    return _render(
        'admin/bookings.html',
        bookings=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        total_revenue=total_revenue,
        pending_count=pending_count,
        q=q,
        from_date=from_date,
        to_date=to_date,
        active_section='bookings',
    )


@admin_bp.route('/bookings/<bid>')
@login_required
@admin_required
def booking_detail(bid):
    b = Booking.get(bid)
    if not b:
        flash('Booking not found.', 'error')
        return redirect(url_for('admin.bookings'))
    return _render('admin/booking_detail.html', booking=b, active_section='bookings')


@admin_bp.route('/bookings/<bid>/status', methods=['POST'])
@login_required
@admin_required
def booking_status(bid):
    status = _clean(request.form.get('status'), 50)
    if status not in current_app.config['BOOKING_STATUSES']:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.bookings'))

    booking = Booking.get(bid)
    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('admin.bookings'))

    update = {'status': status}

    reason = _clean(request.form.get('cancellation_reason'), 500)
    if status == 'cancelled' and reason:
        update['cancellation_reason'] = reason

    if status == 'cancelled' and booking.get('payment_status') == 'paid':
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

    # created_at is a datetime
    rng = _daterange_or_none(from_date, to_date, field='created_at', as_datetime=True)
    if rng:
        filters.update(rng)

    pagination = _paginate(db.db['inquiries'], filters, page)

    new_count       = Inquiry.count({'status': 'new'})
    contacted_count = Inquiry.count({'status': 'contacted'})
    booked_count    = Inquiry.count({'status': 'booked'})

    return _render(
        'admin/inquiries.html',
        inquiries=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        q=q,
        from_date=from_date,
        to_date=to_date,
        new_count=new_count,
        contacted_count=contacted_count,
        booked_count=booked_count,
        active_section='inquiries',
    )


@admin_bp.route('/inquiries/<iid>/status', methods=['POST'])
@login_required
@admin_required
def inquiry_status(iid):
    status = _clean(request.form.get('status'), 50)
    if status not in current_app.config['INQUIRY_STATUSES']:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.inquiries'))
    Inquiry.update(iid, {'status': status})
    _audit('inquiry.status', target=iid, extra=status)
    flash(f'Inquiry marked as {status}.', 'success')
    return redirect(url_for('admin.inquiries'))


@admin_bp.route('/inquiries/<iid>/delete', methods=['POST'])
@login_required
@admin_required
def inquiry_delete(iid):
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

    pagination = _paginate(db.db['reviews'], filters, page)

    return _render(
        'admin/reviews.html',
        reviews=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        q=q,
        active_section='reviews',
    )


@admin_bp.route('/reviews/new', methods=['GET', 'POST'])
@login_required
@admin_required
def review_create():
    form = AdminReviewForm()
    if form.validate_on_submit():
        Review.create({
            'name':     _clean(form.name.data, 120),
            'property': _clean(form.property.data, 200),
            'rating':   int(form.rating.data),
            'text':     _clean(form.text.data, 2000),
            'avatar':   _clean(form.avatar.data, 500),
            'status':   form.status.data,
            'source':   'admin',
        })
        _audit('review.create')
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
    review = Review.get(rid)
    if not review:
        flash('Review not found.', 'error')
        return redirect(url_for('admin.reviews'))

    form = AdminReviewForm(data={
        'name':     review.get('name', ''),
        'property': review.get('property', ''),
        'rating':   str(review.get('rating', 5)),
        'text':     review.get('text', ''),
        'avatar':   review.get('avatar', ''),
        'status':   review.get('status', 'pending'),
    })

    if form.validate_on_submit():
        Review.update(rid, {
            'name':     _clean(form.name.data, 120),
            'property': _clean(form.property.data, 200),
            'rating':   int(form.rating.data),
            'text':     _clean(form.text.data, 2000),
            'avatar':   _clean(form.avatar.data, 500),
            'status':   form.status.data,
        })
        _audit('review.update', target=rid)
        flash('Review updated.', 'success')
        return redirect(url_for('admin.reviews'))

    return _render(
        'admin/review_form.html', form=form, review=review, mode='edit',
        active_section='reviews',
    )


@admin_bp.route('/reviews/<rid>/status', methods=['POST'])
@login_required
@admin_required
def review_status(rid):
    status = _clean(request.form.get('status'), 50)
    if status not in current_app.config['REVIEW_STATUSES']:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.reviews'))
    Review.update(rid, {'status': status})
    _audit('review.status', target=rid, extra=status)
    flash(f'Review {status}.', 'success')
    return redirect(url_for('admin.reviews'))


@admin_bp.route('/reviews/<rid>/delete', methods=['POST'])
@login_required
@admin_required
def review_delete(rid):
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
        tid = t.get('_id')
        t['unread'] = Message.unread_for_admin(tid) if tid else 0
    return _render(
        'admin/messages.html',
        threads=threads,
        active_section='messages',
    )


@admin_bp.route('/messages/<path:thread_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def message_thread(thread_id):
    if request.method == 'POST':
        text = (request.form.get('text') or '').strip()
        if text:
            msgs       = Message.by_thread(thread_id, limit=1)
            user_id    = msgs[0].get('user_id')    if msgs else None
            user_name  = msgs[0].get('user_name')  if msgs else 'Guest'
            user_email = msgs[0].get('user_email') if msgs else ''

            Message.create({
                'thread_id':  thread_id,
                'user_id':    user_id,
                'user_name':  user_name,
                'user_email': user_email,
                'sender':     'admin',
                'text':       text[:2000],
            })
            _audit('message.reply', target=thread_id)
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
    page = get_page()
    pagination = _paginate(db.db['journal_subscribers'], {}, page)

    this_month = JournalSubscriber.count({
        'subscribed_at': {
            '$gte': datetime.now(timezone.utc).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        }
    })

    return _render(
        'admin/journal.html',
        subscribers=pagination['items'],
        pagination=pagination,
        total_count=pagination['total'],
        this_month_count=this_month,
        active_section='journal',
    )


@admin_bp.route('/journal/<sid>/delete', methods=['POST'])
@login_required
@admin_required
def journal_delete(sid):
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
        Settings.update({
            'site_name':     _clean(form.site_name.data, 120),
            'contact_email': _clean(form.contact_email.data, 200),
            'whatsapp':      _clean(form.whatsapp.data, 40),
            'instagram':     _clean(form.instagram.data, 60),
        })
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
        body, mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


# ============================================================
# API (dashboard live stats)
# ============================================================
@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    try:
        return jsonify({
            'success': True,
            'stats': {
                'properties':      Property.count(),
                'inquiries':       Inquiry.count(),
                'reviews':         Review.count(),
                'users':           User.count({'role': 'client'}),
                'new_inquiries':   Inquiry.count({'status': 'new'}),
                'pending_reviews': Review.count({'status': 'pending'}),
                'unread_messages': Message.count({'sender': 'client', 'read_by_admin': False}),
            },
            'refreshed_at': utcnow().isoformat(),
        })
    except Exception:
        return jsonify({'success': False, 'error': 'Stats unavailable'}), 500