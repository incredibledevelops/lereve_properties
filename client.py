"""
============================================================
LE RÊVE PROPERTIES — CLIENT (GUEST) PORTAL ROUTES
============================================================
"""
from datetime import datetime
from bson import ObjectId
from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, jsonify, current_app, abort
)
from flask_login import login_required, current_user

from models import (
    Property, Booking, Inquiry, Message, Wishlist, Review,
    db, utcnow, oid_to_str
)
from forms import ProfileForm, PreferencesForm, ChangePasswordForm
from mailer import send_booking_confirmation

client_bp = Blueprint('client', __name__, template_folder='templates/client')


def client_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_admin:
            flash('Client access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# DASHBOARD
# ============================================================
@client_bp.route('/')
@client_bp.route('/dashboard')
@login_required
@client_required
def dashboard():
    bookings = Booking.by_user(current_user.id)
    today = datetime.utcnow().date()
    upcoming = [b for b in bookings if _to_date(b.get('check_in')) >= today and b.get('status') == 'confirmed']
    past = [b for b in bookings if _to_date(b.get('check_in')) < today or b.get('status') == 'completed']
    wish_ids = Wishlist.get(current_user.id)

    recent_activity = _build_recent_activity(bookings, wish_ids)

    return render_template(
        'client/dashboard.html',
        upcoming=upcoming,
        past=past,
        bookings=bookings,
        wishlist_count=len(wish_ids),
        recent_activity=recent_activity,
        upcoming_count=len(upcoming),
    )


def _to_date(s):
    if not s:
        return datetime.utcnow().date()
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s).date()
        except ValueError:
            return datetime.utcnow().date()
    return s.date() if hasattr(s, 'date') else s


def _build_recent_activity(bookings, wish_ids):
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
    return items


# ============================================================
# BOOKINGS
# ============================================================
@client_bp.route('/bookings')
@login_required
@client_required
def bookings():
    all_bookings = Booking.by_user(current_user.id)
    today = datetime.utcnow().date()
    upcoming = [b for b in all_bookings if _to_date(b.get('check_in')) >= today and b.get('status') == 'confirmed']
    past = [b for b in all_bookings if _to_date(b.get('check_in')) < today or b.get('status') == 'completed']
    return render_template('client/bookings.html', bookings=all_bookings,
                           upcoming=upcoming, past=past)


@client_bp.route('/bookings/<bid>')
@login_required
@client_required
def booking_detail(bid):
    b = Booking.get(bid)
    if not b or b.get('user_id') != current_user.id:
        abort(404)
    return render_template('client/booking_detail.html', booking=b)


@client_bp.route('/bookings/<bid>/cancel', methods=['POST'])
@login_required
@client_required
def cancel_booking(bid):
    b = Booking.get(bid)
    if not b or b.get('user_id') != current_user.id:
        abort(404)
    Booking.update(bid, {'status': 'cancellation-requested'})
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
    return render_template('client/wishlist.html', items=items)


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
    return render_template('client/inquiries.html', inquiries=items)


# ============================================================
# MESSAGES (Concierge Chat)
# ============================================================
@client_bp.route('/messages')
@login_required
@client_required
def messages():
    msgs = Message.by_user(current_user.id)
    return render_template('client/messages.html', messages=msgs)


@client_bp.route('/messages/send', methods=['POST'])
@login_required
@client_required
def send_message():
    data = request.get_json() or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'success': False, 'error': 'Empty message'}), 400

    Message.create({
        'user_id': current_user.id,
        'from': 'me',
        'text': text,
    })

    # Auto-reply (mock) — replace with real concierge queue
    from random import choice
    reply = choice([
        'Thank you for your message. I will look into this and revert within the hour.',
        'Noted with pleasure. I will coordinate the details and confirm shortly.',
        'Excellent choice. Let me arrange that for you right away.',
        'I have flagged this with our estate team and will follow up with options.',
    ])
    Message.create({
        'user_id': current_user.id,
        'from': 'concierge',
        'text': reply,
    })

    return jsonify({'success': True, 'reply': reply})


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
        db.db['users'].update_one(
            {'_id': ObjectId(current_user.id)},
            {'$set': {
                'name': form.name.data.strip(),
                'email': form.email.data.lower().strip(),
                'phone': form.phone.data or '',
                'country': form.country.data or '',
                'bio': form.bio.data or '',
            }}
        )
        flash('Profile updated.', 'success')
        return redirect(url_for('client.profile'))

    bookings = Booking.by_user(current_user.id)
    today = datetime.utcnow().date()
    completed = [b for b in bookings if _to_date(b.get('check_in')) < today or b.get('status') == 'completed']
    nights = 0
    countries = set()
    for b in completed:
        try:
            ci = datetime.fromisoformat(b['check_in']) if isinstance(b['check_in'], str) else b['check_in']
            co = datetime.fromisoformat(b['check_out']) if isinstance(b['check_out'], str) else b['check_out']
            nights += max(1, (co - ci).days)
        except Exception:
            pass
        loc = (b.get('location') or '').split(',')
        if loc:
            countries.add(loc[-1].strip())

    stats = {
        'member_since': current_user.member_since,
        'total_stays': len(completed),
        'total_nights': nights,
        'total_countries': len(countries),
    }
    return render_template('client/profile.html', form=form, pw_form=pw_form, stats=stats)


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
                {'_id': ObjectId(current_user.id)},
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
        'type': prefs.get('type', 'Oceanfront Villas'),
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
            {'_id': ObjectId(current_user.id)},
            {'$set': {'preferences': new_prefs}}
        )
        flash('Preferences saved.', 'success')
        return redirect(url_for('client.preferences'))

    return render_template('client/preferences.html', form=form)