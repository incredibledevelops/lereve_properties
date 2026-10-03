"""
============================================================
CLIENT PORTAL ROUTES
============================================================
"""
import logging
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, abort,
)
from flask_login import login_required, current_user

from extensions import db
from models import (
    Booking, Inquiry, Message, Wishlist, Property,
    User, utcnow,
)
from forms import ProfileForm, PreferencesForm, ChangePasswordForm
from utils import client_required
from services import track_event


log = logging.getLogger(__name__)
client_bp = Blueprint('client', __name__, template_folder='templates/client')


def _to_date(s):
    """Return a date or None (never silently defaults to today)."""
    if not s:
        return None
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s).date()
        except ValueError:
            return None
    if hasattr(s, 'date'):
        return s.date()
    return None


def _bucket_bookings(bookings):
    today = datetime.now(timezone.utc).date()
    upcoming, past = [], []
    for b in bookings:
        ci = _to_date(b.get('check_in'))
        status = b.get('status')
        if status == 'confirmed' and ci and ci >= today:
            upcoming.append(b)
        elif (ci and ci < today) or status in ('completed', 'cancelled', 'cancellation-requested'):
            past.append(b)
        else:
            upcoming.append(b)
    # Sort upcoming by check_in ascending, past by check_in descending
    upcoming.sort(key=lambda b: b.get('check_in') or '')
    past.sort(key=lambda b: b.get('check_in') or '', reverse=True)
    return upcoming, past


def _build_recent_activity(bookings, wish_ids, message_count):
    items = []
    for b in bookings[:3]:
        items.append({
            'icon': 'fa-check-circle' if b.get('status') == 'completed' else 'fa-calendar-check',
            'color': 'emerald' if b.get('status') == 'completed' else 'primary',
            'text': f"{'Completed stay at' if b.get('status') == 'completed' else 'Booked'} {b.get('property')}",
            'date': b.get('created_at'),
        })
    if wish_ids:
        items.append({
            'icon': 'fa-heart', 'color': 'gold',
            'text': f'Saved {len(wish_ids)} estate(s) to wishlist',
            'date': utcnow().isoformat(),
        })
    if message_count:
        items.append({
            'icon': 'fa-comments', 'color': 'primary',
            'text': f'{message_count} message(s) from concierge',
            'date': utcnow().isoformat(),
        })
    return items


# ============================================================
# DASHBOARD
# ============================================================
@client_bp.route('/')
@client_bp.route('/dashboard')
@login_required
@client_required
def dashboard():
    bookings = Booking.by_user(current_user.id, limit=100)
    upcoming, past = _bucket_bookings(bookings)
    wish_ids = Wishlist.get(current_user.id)
    unread = Message.unread_for_client(current_user.id)

    recent_activity = _build_recent_activity(bookings, wish_ids, unread)

    return render_template(
        'client/dashboard.html',
        upcoming=upcoming,
        past=past,
        bookings=bookings,
        wishlist_count=len(wish_ids),
        recent_activity=recent_activity,
        upcoming_count=len(upcoming),
        unread_messages=unread,
        active_section='overview',
    )


# ============================================================
# BOOKINGS
# ============================================================
@client_bp.route('/bookings')
@login_required
@client_required
def bookings():
    all_bookings = Booking.by_user(current_user.id, limit=200)
    upcoming, past = _bucket_bookings(all_bookings)
    return render_template(
        'client/bookings.html',
        bookings=all_bookings, upcoming=upcoming, past=past,
        active_section='bookings',
    )


@client_bp.route('/bookings/<bid>')
@login_required
@client_required
def booking_detail(bid):
    b = Booking.get(bid)
    if not b or b.get('user_id') != current_user.id:
        abort(404)
    return render_template(
        'client/booking_detail.html', booking=b,
        active_section='bookings',
    )


@client_bp.route('/bookings/<bid>/cancel', methods=['POST'])
@login_required
@client_required
def cancel_booking(bid):
    b = Booking.get(bid)
    if not b or b.get('user_id') != current_user.id:
        abort(404)
    if b.get('status') not in ('pending', 'confirmed'):
        flash('This booking cannot be cancelled.', 'error')
        return redirect(url_for('client.bookings'))

    Booking.update(bid, {'status': 'cancellation-requested'})

    # Notify admin via message thread
    thread_id = f"user-{current_user.id}"
    Message.create({
        'thread_id': thread_id,
        'user_id': current_user.id,
        'user_name': current_user.name,
        'user_email': current_user.email,
        'sender': 'client',
        'text': f'[System] Cancellation requested for {b.get("property")} '
                f'({b.get("confirmation_id") or b.get("id")}).',
    })

    flash('Cancellation request sent to concierge.', 'info')
    return redirect(url_for('client.bookings'))


# ============================================================
# WISHLIST
# ============================================================
@client_bp.route('/wishlist')
@login_required
@client_required
def wishlist():
    ids = Wishlist.get(current_user.id)
    items = []
    for pid in ids:
        p = Property.get(pid)
        if p:
            items.append(p)
    return render_template(
        'client/wishlist.html', items=items,
        active_section='wishlist',
    )


@client_bp.route('/wishlist/remove/<pid>', methods=['POST'])
@login_required
@client_required
def remove_wishlist(pid):
    Wishlist.toggle(current_user.id, pid)
    flash('Removed from wishlist.', 'info')
    return redirect(url_for('client.wishlist'))


# ============================================================
# INQUIRIES
# ============================================================
@client_bp.route('/inquiries')
@login_required
@client_required
def inquiries():
    items = Inquiry.by_email(current_user.email)
    return render_template(
        'client/inquiries.html', inquiries=items,
        active_section='inquiries',
    )


# ============================================================
# MESSAGES (Concierge chat)
# ============================================================
@client_bp.route('/messages')
@login_required
@client_required
def messages():
    thread_id = f"user-{current_user.id}"
    msgs = Message.by_thread(thread_id)
    Message.mark_read(thread_id, by='client')
    return render_template(
        'client/messages.html',
        messages=msgs,
        thread_id=thread_id,
        active_section='messages',
    )


@client_bp.route('/messages/send', methods=['POST'])
@login_required
@client_required
def send_message():
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'success': False, 'error': 'Empty message'}), 400
    if len(text) > 2000:
        return jsonify({'success': False, 'error': 'Message too long'}), 400

    thread_id = f"user-{current_user.id}"
    Message.create({
        'thread_id': thread_id,
        'user_id': current_user.id,
        'user_name': current_user.name,
        'user_email': current_user.email,
        'sender': 'client',
        'text': text,
    })

    # Notify admin by email (best-effort, async)
    try:
        from flask import current_app
        from services.mailer import send_new_message_notification
        admin_email = current_app.config.get('SUPER_ADMIN_EMAIL')
        if admin_email:
            send_new_message_notification(admin_email, current_user.name, text[:120])
    except Exception:
        log.exception('Failed to notify admin about message')

    return jsonify({'success': True, 'message': 'Message sent'})


@client_bp.route('/messages/poll')
@login_required
@client_required
def poll_messages():
    """Returns messages created since a given timestamp (for live chat)."""
    since = request.args.get('since', '')
    thread_id = f"user-{current_user.id}"
    all_msgs = Message.by_thread(thread_id)
    if since:
        all_msgs = [m for m in all_msgs if (m.get('created_at') or '') > since]
        Message.mark_read(thread_id, by='client')
    return jsonify({'success': True, 'messages': all_msgs})


# ============================================================
# PROFILE
# ============================================================
@client_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@client_required
def profile():
    form = ProfileForm(obj=current_user)
    pw_form = ChangePasswordForm()

    if form.submit.data and form.validate_on_submit():
        new_email = form.email.data.lower().strip()

        # Check email collision
        if new_email != current_user.email:
            existing = User.find_by_email(new_email)
            if existing and existing.id != current_user.id:
                flash('That email is already in use.', 'error')
                return redirect(url_for('client.profile'))

        try:
            db.db['users'].update_one(
                {'_id': __import__('bson').ObjectId(current_user.id)},
                {'$set': {
                    'name': form.name.data.strip(),
                    'email': new_email,
                    'phone': form.phone.data or '',
                    'country': form.country.data or '',
                    'bio': form.bio.data or '',
                }}
            )
            flash('Profile updated.', 'success')
        except Exception:
            log.exception('Profile update failed')
            flash('Could not update profile.', 'error')

        return redirect(url_for('client.profile'))

    bookings = Booking.by_user(current_user.id, limit=200)
    today = datetime.now(timezone.utc).date()
    completed = [b for b in bookings if (_to_date(b.get('check_in')) and _to_date(b['check_in']) < today)
                 or b.get('status') == 'completed']

    nights = 0
    countries = set()
    for b in completed:
        ci = _to_date(b.get('check_in'))
        co = _to_date(b.get('check_out'))
        if ci and co:
            nights += max(1, (co - ci).days)
        loc = (b.get('location') or '').split(',')
        if loc and loc[-1].strip():
            countries.add(loc[-1].strip())

    stats = {
        'member_since': current_user.member_since,
        'total_stays': len(completed),
        'total_nights': nights,
        'total_countries': len(countries),
    }
    return render_template(
        'client/profile.html',
        form=form, pw_form=pw_form, stats=stats,
        active_section='profile',
    )


@client_bp.route('/profile/password', methods=['POST'])
@login_required
@client_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current.data):
            flash('Current password is incorrect.', 'error')
        else:
            from werkzeug.security import generate_password_hash
            db.db['users'].update_one(
                {'_id': __import__('bson').ObjectId(current_user.id)},
                {'$set': {'password_hash': generate_password_hash(form.new.data)}}
            )
            flash('Password updated successfully.', 'success')
    else:
        flash('Please check the password fields.', 'error')
    return redirect(url_for('client.profile'))


# ============================================================
# PREFERENCES
# ============================================================
@client_bp.route('/preferences', methods=['GET', 'POST'])
@login_required
@client_required
def preferences():
    prefs = current_user.preferences or {}
    form = PreferencesForm(data={
        'type': prefs.get('type', ''),
        'diet': prefs.get('diet', ''),
        'amenities': ', '.join(prefs.get('amenities', [])),
        'newsletter': prefs.get('comm', {}).get('newsletter', True),
        'sms': prefs.get('comm', {}).get('sms', False),
        'promo': prefs.get('comm', {}).get('promo', True),
    })

    if form.validate_on_submit():
        new_prefs = {
            'type': form.type.data,
            'diet': form.diet.data or '',
            'amenities': [a.strip() for a in (form.amenities.data or '').split(',') if a.strip()],
            'comm': {
                'newsletter': form.newsletter.data,
                'sms': form.sms.data,
                'promo': form.promo.data,
            },
        }
        db.db['users'].update_one(
            {'_id': __import__('bson').ObjectId(current_user.id)},
            {'$set': {'preferences': new_prefs}}
        )
        flash('Preferences saved.', 'success')
        return redirect(url_for('client.preferences'))

    return render_template(
        'client/preferences.html', form=form,
        active_section='preferences',
    )