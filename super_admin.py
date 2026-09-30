"""
============================================================
LE RÊVE PROPERTIES — SUPER ADMIN ROUTES
All admin actions logged. All statuses validated.
No public estate submissions — admins manage the portfolio.
============================================================
"""
import json
import logging
import re
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import quote as url_quote

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, jsonify, current_app, Response, g,
)
from flask_login import login_required, current_user

from models import (
    Property, Booking, Inquiry, Review, Category,
    JournalSubscriber, Settings, db, utcnow,
)
from forms import (
    PropertyForm, SettingsForm, AdminReviewForm, CategoryForm,
)


log = logging.getLogger(__name__)

super_admin_bp = Blueprint(
    'super_admin',
    __name__,
    template_folder='templates/super-admin',
)


# ============================================================
# CONSTANTS
# ============================================================
INQUIRY_STATUSES = {'new', 'contacted', 'booked', 'archived'}
REVIEW_STATUSES = {'published', 'pending', 'rejected'}
BOOKING_STATUSES = {
    'pending', 'confirmed', 'completed',
    'cancelled', 'cancellation-requested',
}
PAGE_SIZE = 20
MAX_PAGE = 10_000


# ============================================================
# DECORATORS
# ============================================================
def admin_required(f):
    """Guard: only authenticated super-admins may proceed."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# HELPERS
# ============================================================
def _safe_page():
    """Parse page number from query string safely (capped)."""
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    return max(1, min(page, MAX_PAGE))


def _paginate(items, page, per_page=PAGE_SIZE):
    """In-memory pagination with proper page clamping."""
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    end = start + per_page
    return {
        'items': items[start:end],
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'has_prev': page > 1,
        'has_next': page < pages,
    }


def _badge_counts():
    """Nav badge counts, cached per-request via Flask's `g`."""
    cached = getattr(g, '_admin_badges', None)
    if cached is not None:
        return cached
    try:
        counts = {
            'pending_inquiries': Inquiry.count({'status': 'new'}),
            'pending_reviews': Review.count({'status': 'pending'}),
        }
    except Exception:
        log.exception('Failed to compute badge counts')
        counts = {'pending_inquiries': 0, 'pending_reviews': 0}
    g._admin_badges = counts
    return counts


def _render(template, **ctx):
    """Wrapper injecting shared context (badges, dates, section)."""
    ctx.setdefault('active_section', 'dashboard')
    ctx.update(_badge_counts())
    ctx.setdefault('now', utcnow())
    ctx.setdefault(
        'now_year_month',
        datetime.now(timezone.utc).strftime('%Y-%m'),
    )
    return render_template(template, **ctx)


def _escape_regex(text):
    """Escape user input for safe $regex use."""
    return re.escape(text or '')


def _normalize_iso(value):
    """Return ISO 8601 string from datetime/str/None."""
    if not value:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _clean(value, max_len=2000):
    """Strip and truncate a string safely."""
    if not value:
        return ''
    return str(value).strip()[:max_len]


def _rating_int(value, default=5):
    """Clamp a rating to 1–5."""
    try:
        n = int(value or default)
    except (TypeError, ValueError):
        n = default
    return max(1, min(5, n))


def _avatar_for(name, provided=''):
    """
    Return a working avatar URL.
    If `provided` is non-empty, use it. Otherwise generate from initials.
    Uses urllib quote so names with spaces/special chars work correctly.
    """
    provided = _clean(provided, 500)
    if provided:
        return provided
    name = _clean(name, 120) or 'Guest'
    safe_name = url_quote(name, safe='')
    return (
        f"https://ui-avatars.com/api/?name={safe_name}"
        "&background=c9a84c&color=1a3a2a"
    )


def _preserve_created_at(new_payload, existing, key='created_at'):
    """
    Copy `existing[key]` onto `new_payload` if present.
    Prevents update from dropping the original timestamp.
    """
    if existing and key in existing and key not in new_payload:
        new_payload[key] = existing[key]
    return new_payload


def _audit(action, target=None, extra=None):
    """Lightweight audit log with client IP."""
    try:
        actor = current_user.email if current_user.is_authenticated else 'anonymous'
        ip = request.remote_addr or 'unknown'
        log.info(
            f'[AUDIT] {actor}@{ip} → {action}'
            f'{f" target={target}" if target else ""}'
            f'{f" extra={extra}" if extra else ""}'
        )
    except Exception:
        pass


# ============================================================
# DASHBOARD
# ============================================================
@super_admin_bp.route('/')
@super_admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    try:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # ---------- Bookings aggregates ----------
        all_bookings = Booking.all(sort=[('created_at', -1)])
        recent_bookings = all_bookings[:5]

        paid = [b for b in all_bookings if b.get('payment_status') == 'paid']
        confirmed = [b for b in all_bookings if b.get('status') == 'confirmed']
        pending = [b for b in all_bookings if b.get('status') == 'pending']
        cancelled = [b for b in all_bookings if b.get('status') == 'cancelled']

        # ---------- Revenue this month ----------
        revenue_month = 0.0
        for b in paid:
            ts_raw = b.get('paid_at') or b.get('created_at')
            if not ts_raw:
                continue
            try:
                ts = (datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                      if isinstance(ts_raw, str) else ts_raw)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= month_start:
                    revenue_month += float(b.get('total') or 0)
            except Exception:
                continue

        # ---------- Occupancy per category ----------
        props = Property.all()
        props_by_cat = {}
        for p in props:
            cat = p.get('category') or 'Other'
            props_by_cat.setdefault(cat, []).append(p.get('id'))

        occupancy = {}
        for cat, ids in props_by_cat.items():
            if not ids:
                occupancy[cat] = 0
                continue
            booked = sum(1 for b in confirmed if b.get('property_id') in ids)
            occupancy[cat] = min(100, round((booked / len(ids)) * 100))

        avg_occupancy = (
            f"{round(sum(occupancy.values()) / len(occupancy))}%"
            if occupancy else '0%'
        )

        # ---------- Stats dict ----------
        stats = {
            'properties': Property.count(),
            'inquiries': Inquiry.count(),
            'reviews': Review.count(),
            'categories': Category.count(),
            'new_inquiries': Inquiry.count({'status': 'new'}),
            'pending_reviews': Review.count({'status': 'pending'}),
            'revenue_month': revenue_month,
            'confirmed_bookings': len(confirmed),
            'pending_bookings': len(pending),
            'cancelled_bookings': len(cancelled),
            'occupancy': occupancy,
            'avg_occupancy': avg_occupancy,
        }

        recent_inquiries = Inquiry.all()[:4]

        return _render(
            'super-admin/dashboard.html',
            stats=stats,
            recent_inquiries=recent_inquiries,
            recent_bookings=recent_bookings,
            active_section='dashboard',
        )

    except Exception:
        log.exception('Dashboard render failed')
        flash('Could not load dashboard data. Check server logs.', 'error')
        return _render(
            'super-admin/dashboard.html',
            stats={
                'properties': 0,
                'inquiries': 0,
                'reviews': 0,
                'categories': 0,
                'new_inquiries': 0,
                'pending_reviews': 0,
                'revenue_month': 0,
                'confirmed_bookings': 0,
                'pending_bookings': 0,
                'cancelled_bookings': 0,
                'occupancy': {},
                'avg_occupancy': '0%',
            },
            recent_inquiries=[],
            recent_bookings=[],
            active_section='dashboard',
        )


# ============================================================
# STATS API (for live refresh)
# ============================================================
@super_admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """Lightweight JSON endpoint for dashboard auto-refresh."""
    try:
        return jsonify({
            'success': True,
            'stats': {
                'properties': Property.count(),
                'inquiries': Inquiry.count(),
                'reviews': Review.count(),
                'categories': Category.count(),
                'new_inquiries': Inquiry.count({'status': 'new'}),
                'pending_reviews': Review.count({'status': 'pending'}),
            },
            'refreshed_at': utcnow().isoformat(),
        })
    except Exception:
        log.exception('api_stats failed')
        return jsonify({'success': False, 'error': 'Stats unavailable'}), 500


# ============================================================
# PROPERTIES
# ============================================================
@super_admin_bp.route('/properties')
@login_required
@admin_required
def properties():
    q = _clean(request.args.get('q'), 100)
    category_filter = _clean(request.args.get('category'), 100)
    page = _safe_page()

    filters = {}
    if q:
        safe = _escape_regex(q)
        filters['$or'] = [
            {'title': {'$regex': safe, '$options': 'i'}},
            {'location': {'$regex': safe, '$options': 'i'}},
            {'category': {'$regex': safe, '$options': 'i'}},
        ]
    if category_filter and category_filter != 'all':
        filters['category'] = category_filter

    try:
        all_props = Property.all(filters, sort=[('created_at', -1)])
    except Exception:
        log.exception('Property list fetch failed')
        all_props = []

    pagination = _paginate(all_props, page)

    return _render(
        'super-admin/properties.html',
        properties=pagination['items'],
        pagination=pagination,
        q=q,
        active_section='properties',
    )


@super_admin_bp.route('/properties/new', methods=['GET', 'POST'])
@login_required
@admin_required
def property_create():
    form = PropertyForm()

    if form.validate_on_submit():
        try:
            Property.create(_property_payload(form))
            _audit('property.create', target=form.title.data)

            action = (request.form.get('action') or 'save').strip()
            if action == 'save_and_new':
                flash('Property added. Ready for the next one.', 'success')
                return redirect(url_for('super_admin.property_create'))

            flash('Property added successfully.', 'success')
            return redirect(url_for('super_admin.properties'))
        except Exception as e:
            log.exception('Property create failed')
            flash(f'Could not save property: {e}', 'error')

    return _render(
        'super-admin/property_form.html',
        form=form,
        property=None,
        mode='create',
        active_section='properties',
    )


@super_admin_bp.route('/properties/<pid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def property_edit(pid):
    prop = Property.get(pid)
    if not prop:
        flash('Property not found.', 'error')
        return redirect(url_for('super_admin.properties'))

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
            _preserve_created_at(payload, prop)
            Property.update(pid, payload)
            _audit('property.update', target=pid, extra=form.title.data)
            flash('Property updated successfully.', 'success')
            return redirect(url_for('super_admin.properties'))
        except Exception as e:
            log.exception('Property update failed')
            flash(f'Could not update property: {e}', 'error')

    return _render(
        'super-admin/property_form.html',
        form=form,
        property=prop,
        mode='edit',
        active_section='properties',
    )


@super_admin_bp.route('/properties/<pid>/delete', methods=['POST'])
@login_required
@admin_required
def property_delete(pid):
    prop = Property.get(pid)
    if not prop:
        flash('Property not found.', 'error')
    else:
        title = prop.get('title', 'Unknown')
        Property.delete(pid)
        _audit('property.delete', target=pid, extra=title)
        flash(f'Property "{title}" deleted.', 'info')
    return redirect(url_for('super_admin.properties'))


def _property_payload(form):
    """Convert form to Mongo-ready payload with type coercion."""
    def _float(v, default=0.0):
        try:
            return float(v or default)
        except (TypeError, ValueError):
            return default

    def _int(v, default=1):
        try:
            return int(v or default)
        except (TypeError, ValueError):
            return default

    return {
        'title': _clean(form.title.data, 200),
        # Do NOT hardcode a default category — respect admin's choice.
        # If the form failed to populate categories, this will be empty
        # and the admin will see the error on next render.
        'category': _clean(form.category.data, 100),
        'location': _clean(form.location.data, 200),
        'original_price': _float(form.original_price.data, 0.0),
        'price': _float(form.price.data, 0.0),
        'beds': _int(form.beds.data, 1),
        'baths': _float(form.baths.data, 1.0),
        'guests': _int(form.guests.data, 1),
        'rating': _float(form.rating.data, 5.0),
        'reviews_count': _int(form.reviews_count.data, 0),
        'image': _clean(form.image.data, 500),
        'gallery': [
            u.strip() for u in (form.gallery.data or '').splitlines() if u.strip()
        ],
        'amenities': [
            a.strip() for a in (form.amenities.data or '').split(',') if a.strip()
        ],
        'description': _clean(form.description.data, 3000),
    }


# ============================================================
# CATEGORIES
# ============================================================
@super_admin_bp.route('/categories')
@login_required
@admin_required
def categories():
    items = Category.all()
    # Enrich with live property counts
    for c in items:
        c['property_count'] = Property.count_by_category(c.get('name'))
    return _render(
        'super-admin/categories.html',
        categories=items,
        active_section='categories',
    )


@super_admin_bp.route('/categories/new', methods=['GET', 'POST'])
@login_required
@admin_required
def category_create():
    form = CategoryForm()
    if form.validate_on_submit():
        try:
            cid = Category.create({
                'name': _clean(form.name.data, 80),
                'description': _clean(form.description.data, 500),
                'icon': _clean(form.icon.data, 80) or 'fa-house-chimney',
                'order': int(form.order.data or 0),
            })
            if cid:
                _audit('category.create', target=cid, extra=form.name.data)
                flash(f'Category "{form.name.data}" created.', 'success')
                return redirect(url_for('super_admin.categories'))

            flash(
                'Could not create category — the name may be blank, '
                'or a category with that name already exists.',
                'error'
            )
        except Exception as e:
            log.exception('Category create failed')
            flash(f'Could not create category: {e}', 'error')

    return _render(
        'super-admin/category_form.html',
        form=form,
        category=None,
        mode='create',
        active_section='categories',
    )


@super_admin_bp.route('/categories/<cid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def category_edit(cid):
    cat = Category.get(cid)
    if not cat:
        flash('Category not found.', 'error')
        return redirect(url_for('super_admin.categories'))

    form = CategoryForm(data={
        'name': cat.get('name', ''),
        'description': cat.get('description', ''),
        'icon': cat.get('icon', 'fa-house-chimney'),
        'order': cat.get('order', 0),
    })

    if form.validate_on_submit():
        try:
            ok = Category.update(cid, {
                'name': _clean(form.name.data, 80),
                'description': _clean(form.description.data, 500),
                'icon': _clean(form.icon.data, 80) or 'fa-house-chimney',
                'order': int(form.order.data or 0),
            })
            if ok:
                _audit('category.update', target=cid, extra=form.name.data)
                flash('Category updated.', 'success')
                return redirect(url_for('super_admin.categories'))

            flash('Could not update category — the name is required.', 'error')
        except Exception as e:
            log.exception('Category update failed')
            flash(f'Could not update category: {e}', 'error')

    return _render(
        'super-admin/category_form.html',
        form=form,
        category=cat,
        mode='edit',
        active_section='categories',
    )


@super_admin_bp.route('/categories/<cid>/delete', methods=['POST'])
@login_required
@admin_required
def category_delete(cid):
    cat = Category.get(cid)
    if not cat:
        flash('Category not found.', 'error')
        return redirect(url_for('super_admin.categories'))

    # Guard: prevent deletion if properties reference this category
    in_use = Property.count_by_category(cat.get('name'))
    if in_use > 0:
        flash(
            f'Cannot delete — {in_use} propert{"y" if in_use == 1 else "ies"} '
            f'still use this category. Reassign them first.',
            'error'
        )
        return redirect(url_for('super_admin.categories'))

    if Category.delete(cid):
        _audit('category.delete', target=cid, extra=cat.get('name'))
        flash('Category deleted.', 'info')
    else:
        flash('Could not delete category.', 'error')
    return redirect(url_for('super_admin.categories'))


# ============================================================
# INQUIRIES
# ============================================================
@super_admin_bp.route('/inquiries')
@login_required
@admin_required
def inquiries():
    page = _safe_page()
    status_filter = _clean(request.args.get('status'), 50)

    filters = {}
    if status_filter in INQUIRY_STATUSES:
        filters['status'] = status_filter

    items = Inquiry.all(filters)
    pagination = _paginate(items, page)

    return _render(
        'super-admin/inquiries.html',
        inquiries=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        active_section='inquiries',
    )


@super_admin_bp.route('/inquiries/<iid>/status', methods=['POST'])
@login_required
@admin_required
def inquiry_status(iid):
    status = _clean(request.form.get('status'), 50)
    if status not in INQUIRY_STATUSES:
        flash('Invalid status.', 'error')
        return redirect(url_for('super_admin.inquiries'))

    if Inquiry.update(iid, {'status': status}):
        _audit('inquiry.status', target=iid, extra=status)
        flash(f'Inquiry marked as {status}.', 'success')
    else:
        flash('Could not update inquiry.', 'error')
    return redirect(url_for('super_admin.inquiries'))


@super_admin_bp.route('/inquiries/<iid>/delete', methods=['POST'])
@login_required
@admin_required
def inquiry_delete(iid):
    if Inquiry.delete(iid):
        _audit('inquiry.delete', target=iid)
        flash('Inquiry deleted.', 'info')
    else:
        flash('Could not delete inquiry.', 'error')
    return redirect(url_for('super_admin.inquiries'))


# ============================================================
# REVIEWS
# ============================================================
@super_admin_bp.route('/reviews')
@login_required
@admin_required
def reviews():
    page = _safe_page()
    status_filter = _clean(request.args.get('status'), 50)

    filters = {}
    if status_filter in REVIEW_STATUSES:
        filters['status'] = status_filter

    items = Review.all(filters)
    pagination = _paginate(items, page)

    return _render(
        'super-admin/reviews.html',
        reviews=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        active_section='reviews',
    )


@super_admin_bp.route('/reviews/new', methods=['GET', 'POST'])
@login_required
@admin_required
def review_create():
    """Admin creates a review directly (bypasses public moderation)."""
    form = AdminReviewForm()

    if form.validate_on_submit():
        try:
            name = _clean(form.name.data, 120) or 'Anonymous'
            payload = {
                'name': name,
                'property': _clean(form.property.data, 200),
                'rating': _rating_int(form.rating.data, 5),
                'text': _clean(form.text.data, 2000),
                'avatar': _avatar_for(name, form.avatar.data),
                'status': form.status.data or 'published',
                'source': 'admin',
            }

            Review.create(payload)

            _audit('review.create', target=name, extra=form.status.data)
            flash(f'Review from "{name}" created successfully.', 'success')

            action = (request.form.get('action') or 'save').strip()
            if action == 'save_and_new':
                return redirect(url_for('super_admin.review_create'))

            return redirect(url_for('super_admin.reviews'))

        except Exception as e:
            log.exception('Review create failed')
            flash(f'Could not create review: {e}', 'error')

    return _render(
        'super-admin/review_form.html',
        form=form,
        review=None,
        mode='create',
        active_section='reviews',
    )


@super_admin_bp.route('/reviews/<rid>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def review_edit(rid):
    """Admin edits an existing review."""
    review = Review.get(rid)
    if not review:
        flash('Review not found.', 'error')
        return redirect(url_for('super_admin.reviews'))

    form = AdminReviewForm(data={
        'name': review.get('name', ''),
        'property': review.get('property', ''),
        'rating': str(review.get('rating', 5)),
        'text': review.get('text', ''),
        'avatar': review.get('avatar', ''),
        'status': review.get('status', 'pending'),
    })

    if form.validate_on_submit():
        try:
            name = _clean(form.name.data, 120) or 'Anonymous'
            payload = {
                'name': name,
                'property': _clean(form.property.data, 200),
                'rating': _rating_int(form.rating.data, 5),
                'text': _clean(form.text.data, 2000),
                'avatar': _avatar_for(name, form.avatar.data),
                'status': form.status.data or 'pending',
            }
            _preserve_created_at(payload, review)

            Review.update(rid, payload)

            _audit('review.update', target=rid, extra=form.status.data)
            flash('Review updated successfully.', 'success')
            return redirect(url_for('super_admin.reviews'))

        except Exception as e:
            log.exception('Review update failed')
            flash(f'Could not update review: {e}', 'error')

    return _render(
        'super-admin/review_form.html',
        form=form,
        review=review,
        mode='edit',
        active_section='reviews',
    )


@super_admin_bp.route('/reviews/<rid>/status', methods=['POST'])
@login_required
@admin_required
def review_status(rid):
    status = _clean(request.form.get('status'), 50)
    if status not in REVIEW_STATUSES:
        flash('Invalid status.', 'error')
        return redirect(url_for('super_admin.reviews'))

    if Review.update(rid, {'status': status}):
        _audit('review.status', target=rid, extra=status)
        flash(f'Review {status}.', 'success')
    else:
        flash('Could not update review.', 'error')
    return redirect(url_for('super_admin.reviews'))


@super_admin_bp.route('/reviews/<rid>/delete', methods=['POST'])
@login_required
@admin_required
def review_delete(rid):
    if Review.delete(rid):
        _audit('review.delete', target=rid)
        flash('Review deleted.', 'info')
    else:
        flash('Could not delete review.', 'error')
    return redirect(url_for('super_admin.reviews'))


# ============================================================
# JOURNAL SUBSCRIBERS
# ============================================================
@super_admin_bp.route('/journal')
@login_required
@admin_required
def journal():
    page = _safe_page()
    items = JournalSubscriber.all()

    now_ym = datetime.now(timezone.utc).strftime('%Y-%m')
    this_month = sum(
        1 for s in items
        if (s.get('subscribed_at') or '')[:7] == now_ym
    )

    pagination = _paginate(items, page)

    return _render(
        'super-admin/journal.html',
        subscribers=pagination['items'],
        pagination=pagination,
        total_count=len(items),
        this_month_count=this_month,
        active_section='journal',
    )


@super_admin_bp.route('/journal/<sid>/delete', methods=['POST'])
@login_required
@admin_required
def journal_delete(sid):
    if JournalSubscriber.delete(sid):
        _audit('journal.delete', target=sid)
        flash('Subscriber removed.', 'info')
    else:
        flash('Could not remove subscriber.', 'error')
    return redirect(url_for('super_admin.journal'))


# ============================================================
# BOOKINGS
# ============================================================
@super_admin_bp.route('/bookings')
@login_required
@admin_required
def bookings():
    page = _safe_page()
    status_filter = _clean(request.args.get('status'), 50)

    filters = {}
    if status_filter in BOOKING_STATUSES:
        filters['status'] = status_filter

    items = Booking.all(filters, sort=[('created_at', -1)])
    pagination = _paginate(items, page)

    total_revenue = sum(
        float(b.get('total') or 0)
        for b in items if b.get('payment_status') == 'paid'
    )

    return _render(
        'super-admin/bookings.html',
        bookings=pagination['items'],
        pagination=pagination,
        status_filter=status_filter,
        total_revenue=total_revenue,
        active_section='bookings',
    )


@super_admin_bp.route('/bookings/<bid>/status', methods=['POST'])
@login_required
@admin_required
def booking_status(bid):
    status = _clean(request.form.get('status'), 50)
    if status not in BOOKING_STATUSES:
        flash('Invalid booking status.', 'error')
        return redirect(url_for('super_admin.bookings'))

    booking = Booking.get(bid)
    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('super_admin.bookings'))

    update = {'status': status}

    # Sync refund only for bookings that were actually paid
    if status == 'cancelled' and booking.get('payment_status') == 'paid':
        update['payment_status'] = 'refunded'

    if Booking.update(bid, update):
        _audit('booking.status', target=bid, extra=status)
        flash(f'Booking marked as {status}.', 'success')
    else:
        flash('Could not update booking.', 'error')
    return redirect(url_for('super_admin.bookings'))


# ============================================================
# SETTINGS
# ============================================================
@super_admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    site_settings = Settings.get()
    form = SettingsForm(data=site_settings)

    if form.validate_on_submit():
        try:
            Settings.update({
                'site_name': _clean(form.site_name.data, 120),
                'contact_email': _clean(form.contact_email.data, 200),
                'whatsapp': _clean(form.whatsapp.data, 40),
                'instagram': _clean(form.instagram.data, 60),
            })
            _audit('settings.update')
            flash('Settings saved.', 'success')
            return redirect(url_for('super_admin.settings'))
        except Exception as e:
            log.exception('Settings save failed')
            flash(f'Could not save settings: {e}', 'error')

    return _render(
        'super-admin/settings.html',
        form=form,
        active_section='settings',
    )


# ============================================================
# EXPORT
# ============================================================
@super_admin_bp.route('/settings/export')
@login_required
@admin_required
def export_data():
    """Download a full JSON backup of all active collections."""
    try:
        payload = {
            'exported_at': utcnow().isoformat(),
            'version': '1.0',
            'site': Settings.get(),
            'categories': Category.all(),
            'properties': Property.all(),
            'inquiries': Inquiry.all(),
            'reviews': Review.all(),
            'bookings': Booking.all(),
            'subscribers': JournalSubscriber.all(),
        }
        body = json.dumps(payload, indent=2, default=_normalize_iso, ensure_ascii=False)
        filename = f"lereve-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"

        _audit('settings.export', extra=filename)

        return Response(
            body,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={filename}'},
        )
    except Exception:
        log.exception('Export failed')
        flash('Could not export data.', 'error')
        return redirect(url_for('super_admin.settings'))


# ============================================================
# RESET
# ============================================================
@super_admin_bp.route('/settings/reset', methods=['POST'])
@login_required
@admin_required
def reset_data():
    """
    Destructive: wipe active collections and re-bootstrap defaults.

    NOTE: The `categories` collection is intentionally NOT wiped —
    it holds the taxonomy used by every property. Wiping it would
    leave the app in a broken state. Delete categories individually
    from /super-admin/categories if needed.
    """
    confirm = _clean(request.form.get('confirm'), 20).upper()
    if confirm != 'RESET':
        flash('Type RESET to confirm. Action cancelled.', 'error')
        return redirect(url_for('super_admin.settings'))

    try:
        for col in [
            'properties', 'inquiries',
            'reviews', 'journal_subscribers', 'bookings',
            'messages', 'wishlists',
            # 'categories'    intentionally preserved — see docstring
            # 'owner_submissions' omitted — deprecated
        ]:
            db.db[col].delete_many({})

        from app import bootstrap_database
        bootstrap_database(current_app)

        _audit('settings.reset')
        flash('All data reset to defaults (categories preserved).', 'info')
    except Exception:
        log.exception('Reset failed')
        flash('Could not reset data. Check server logs.', 'error')

    return redirect(url_for('super_admin.settings'))