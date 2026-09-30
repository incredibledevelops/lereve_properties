"""
============================================================
LE RÊVE PROPERTIES — MODELS (MongoDB via PyMongo)
All prices in GHS (₵). Timezone-aware UTC datetimes.

NOTE: OwnerSubmission is DEPRECATED — the public cannot
submit estate listings. Admins use PropertyForm directly.
The class is retained for legacy data migration/export.
============================================================
"""
import logging
import re
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError, OperationFailure

from flask_pymongo import PyMongo
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


log = logging.getLogger(__name__)

db = PyMongo()


# ============================================================
# HELPERS
# ============================================================
def utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def safe_oid(value):
    """Convert a value to ObjectId, or return None if invalid."""
    if isinstance(value, ObjectId):
        return value
    if not value:
        return None
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError, ValueError):
        return None


def oid_to_str(doc):
    """
    Recursively convert ObjectId and datetime fields for templates/JSON.
    Also adds a top-level `id` alias for `_id`.
    """
    if not doc:
        return doc
    if isinstance(doc, list):
        return [oid_to_str(d) for d in doc]
    if isinstance(doc, dict):
        out = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                out[k] = str(v)
                if k == '_id':
                    out['id'] = str(v)
            elif isinstance(v, datetime):
                out[k] = v.isoformat()
            elif isinstance(v, (list, dict)):
                out[k] = oid_to_str(v)
            else:
                out[k] = v
        return out
    return doc


def _safe_sort_cursor(cursor, sort_spec):
    """Apply sort, falling back to _id if the sort key is missing (defensive)."""
    try:
        return cursor.sort(sort_spec)
    except OperationFailure:
        log.warning(f'Sort failed ({sort_spec}); falling back to _id')
        return cursor.sort([('_id', -1)])


def _strip_underscore_keys(data: dict) -> dict:
    """Remove internal `_`-prefixed keys from a dict (defensive copy)."""
    return {k: v for k, v in (data or {}).items() if not k.startswith('_')}


def _slugify(text: str) -> str:
    """Convert 'Oceanfront Villas' → 'oceanfront-villas'."""
    text = (text or '').strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-') or 'category'


# ============================================================
# USER
# ============================================================
class User(UserMixin):
    """Application user — client or super-admin."""
    collection = 'users'

    VALID_TIERS = {'Silver', 'Gold', 'Platinum', 'Black'}

    def __init__(self, **kwargs):
        _id = kwargs.get('_id')
        self.id = str(_id) if _id else None
        self.email = (kwargs.get('email') or '').lower().strip()
        self.name = kwargs.get('name') or ''
        self.phone = kwargs.get('phone') or ''
        self.country = kwargs.get('country') or ''
        self.bio = kwargs.get('bio') or ''
        self.password_hash = kwargs.get('password_hash') or ''
        self.role = kwargs.get('role') or 'client'
        self.avatar = kwargs.get('avatar') or ''

        tier = kwargs.get('tier') or 'Silver'
        self.tier = tier if tier in self.VALID_TIERS else 'Silver'

        prefs = kwargs.get('preferences') or {}
        comm = prefs.get('comm') or {}
        self.preferences = {
            'type': prefs.get('type', 'Oceanfront Villas'),
            'diet': prefs.get('diet', ''),
            'amenities': list(prefs.get('amenities') or []),
            'comm': {
                'newsletter': comm.get('newsletter', True),
                'sms': comm.get('sms', False),
                'promo': comm.get('promo', True),
            },
        }

        self.is_active_flag = kwargs.get('is_active', True)
        self.created_at = kwargs.get('created_at') or utcnow()
        self.member_since = kwargs.get('member_since') or self.created_at

    # ---------- Password ----------
    def set_password(self, raw):
        if not raw:
            raise ValueError('Password cannot be empty')
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        if not raw or not self.password_hash:
            return False
        try:
            return check_password_hash(self.password_hash, raw)
        except (ValueError, TypeError):
            return False

    # ---------- Flask-Login / role helpers ----------
    @property
    def is_active(self):
        return self.is_active_flag

    @property
    def is_admin(self):
        return self.role == 'super_admin'

    @property
    def is_client(self):
        return self.role == 'client'

    @property
    def initials(self):
        if not self.name:
            return '?'
        parts = [p for p in self.name.split() if p]
        return ''.join(p[0] for p in parts[:2]).upper() or '?'

    @property
    def avatar_url(self):
        """Return provided avatar or generate a fallback from initials."""
        if self.avatar:
            return self.avatar
        if not self.name:
            return ''
        safe_name = self.name.replace(' ', '+')
        return f"https://ui-avatars.com/api/?name={safe_name}&background=c9a84c&color=1a3a2a"

    # ---------- Serialization ----------
    def to_dict(self, include_id: bool = False) -> dict:
        """
        Serialize to dict for MongoDB.
        By default, excludes `_id` so it's safe for `$set` updates.
        """
        data = {
            'email': self.email,
            'name': self.name,
            'phone': self.phone,
            'country': self.country,
            'bio': self.bio,
            'password_hash': self.password_hash,
            'role': self.role,
            'tier': self.tier,
            'avatar': self.avatar,
            'preferences': self.preferences,
            'is_active': self.is_active_flag,
            'created_at': self.created_at,
            'member_since': self.member_since,
        }
        if include_id and self.id:
            oid = safe_oid(self.id)
            if oid:
                data['_id'] = oid
        return data

    # ---------- Finders ----------
    @classmethod
    def find_by_email(cls, email):
        if not email or not isinstance(email, str):
            return None
        try:
            doc = db.db[cls.collection].find_one({'email': email.lower().strip()})
            return cls(**doc) if doc else None
        except Exception:
            log.exception('User.find_by_email failed')
            return None

    @classmethod
    def find_by_id(cls, uid):
        oid = safe_oid(uid)
        if not oid:
            return None
        try:
            doc = db.db[cls.collection].find_one({'_id': oid})
            return cls(**doc) if doc else None
        except Exception:
            log.exception('User.find_by_id failed')
            return None

    @classmethod
    def create(cls, email, name, password, **extra):
        """Atomic create with unique-email guarantee."""
        user = cls(email=email, name=name, **extra)
        user.set_password(password)
        try:
            result = db.db[cls.collection].insert_one(user.to_dict())
            user.id = str(result.inserted_id)
            return user
        except DuplicateKeyError:
            log.warning(f'Attempted to create duplicate user: {email}')
            return None


# ============================================================
# CATEGORY  (dynamic estate categories)
# ============================================================
class Category:
    """
    Dynamic estate categories. Managed by admins via
    /super-admin/categories. Referenced by Property.category
    and PreferencesForm via display name.
    """
    collection = 'categories'

    DEFAULT_ICON = 'fa-house-chimney'

    @staticmethod
    def all(sort=None):
        try:
            cursor = db.db[Category.collection].find()
            cursor = _safe_sort_cursor(cursor, sort or [('order', 1), ('name', 1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Category.all failed')
            return []

    @staticmethod
    def names():
        """Return just the display names (used in form dropdowns)."""
        try:
            docs = (
                db.db[Category.collection]
                .find({}, {'name': 1})
                .sort([('order', 1), ('name', 1)])
            )
            return [d['name'] for d in docs if d.get('name')]
        except Exception:
            log.exception('Category.names failed')
            return []

    @staticmethod
    def get(cid):
        oid = safe_oid(cid)
        if not oid:
            return None
        try:
            doc = db.db[Category.collection].find_one({'_id': oid})
            return oid_to_str(doc) if doc else None
        except Exception:
            log.exception('Category.get failed')
            return None

    @staticmethod
    def find_by_name(name):
        if not name or not isinstance(name, str):
            return None
        try:
            doc = db.db[Category.collection].find_one({'name': name.strip()})
            return oid_to_str(doc) if doc else None
        except Exception:
            return None

    @staticmethod
    def create(data):
        """
        Create a category. Returns the new ID, or None if:
          - name is blank
          - a category with the same name already exists
        """
        data = _strip_underscore_keys(dict(data))
        name = (data.get('name') or '').strip()
        if not name:
            log.warning('Category.create called with empty name')
            return None

        data['name'] = name
        data['slug'] = data.get('slug') or _slugify(name)
        data['icon'] = data.get('icon') or Category.DEFAULT_ICON
        try:
            data['order'] = int(data.get('order') or 0)
        except (TypeError, ValueError):
            data['order'] = 0
        data['description'] = (data.get('description') or '').strip()
        data['property_count'] = 0
        data['created_at'] = utcnow()
        data['updated_at'] = utcnow()

        try:
            result = db.db[Category.collection].insert_one(data)
            return str(result.inserted_id)
        except DuplicateKeyError:
            log.warning(f'Duplicate category name: {name}')
            return None
        except Exception:
            log.exception('Category.create failed')
            return None

    @staticmethod
    def update(cid, data):
        oid = safe_oid(cid)
        if not oid:
            return False
        data = _strip_underscore_keys(dict(data))

        if 'name' in data:
            name = (data['name'] or '').strip()
            if not name:
                log.warning('Category.update rejected: empty name')
                return False
            data['name'] = name
            data['slug'] = _slugify(name)

        if 'order' in data:
            try:
                data['order'] = int(data['order'])
            except (TypeError, ValueError):
                data['order'] = 0

        if 'icon' in data:
            data['icon'] = data['icon'] or Category.DEFAULT_ICON

        if 'description' in data:
            data['description'] = (data['description'] or '').strip()

        data['updated_at'] = utcnow()

        try:
            db.db[Category.collection].update_one({'_id': oid}, {'$set': data})
            return True
        except Exception:
            log.exception('Category.update failed')
            return False

    @staticmethod
    def delete(cid):
        oid = safe_oid(cid)
        if not oid:
            return False
        try:
            db.db[Category.collection].delete_one({'_id': oid})
            return True
        except Exception:
            log.exception('Category.delete failed')
            return False

    @staticmethod
    def count(filters=None):
        try:
            return db.db[Category.collection].count_documents(filters or {})
        except Exception:
            return 0


# ============================================================
# PROPERTY
# ============================================================
class Property:
    """Luxury estate listing (admin-managed only)."""
    collection = 'properties'

    @staticmethod
    def all(filters=None, sort=None, limit=None):
        q = filters or {}
        try:
            cursor = db.db[Property.collection].find(q)
            cursor = _safe_sort_cursor(cursor, sort or [('created_at', -1)])
            if limit:
                cursor = cursor.limit(int(limit))
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Property.all failed')
            return []

    @staticmethod
    def get(pid):
        oid = safe_oid(pid)
        if not oid:
            return None
        try:
            doc = db.db[Property.collection].find_one({'_id': oid})
            return oid_to_str(doc) if doc else None
        except Exception:
            log.exception('Property.get failed')
            return None

    @staticmethod
    def create(data):
        data = _strip_underscore_keys(dict(data))
        data['created_at'] = utcnow()
        data['updated_at'] = utcnow()
        for field in ('price', 'original_price'):
            if field in data:
                try:
                    data[field] = float(data[field] or 0)
                except (TypeError, ValueError):
                    data[field] = 0.0
        result = db.db[Property.collection].insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    def update(pid, data):
        oid = safe_oid(pid)
        if not oid:
            return False
        data = _strip_underscore_keys(dict(data))
        data['updated_at'] = utcnow()
        try:
            db.db[Property.collection].update_one({'_id': oid}, {'$set': data})
            return True
        except Exception:
            log.exception('Property.update failed')
            return False

    @staticmethod
    def delete(pid):
        oid = safe_oid(pid)
        if not oid:
            return False
        try:
            db.db[Property.collection].delete_one({'_id': oid})
            return True
        except Exception:
            log.exception('Property.delete failed')
            return False

    @staticmethod
    def count(filters=None):
        try:
            return db.db[Property.collection].count_documents(filters or {})
        except Exception:
            return 0

    @staticmethod
    def count_by_category(name):
        """Count properties referencing a given category name."""
        if not name or not isinstance(name, str):
            return 0
        try:
            return db.db[Property.collection].count_documents({'category': name.strip()})
        except Exception:
            log.exception('Property.count_by_category failed')
            return 0

    @staticmethod
    def categories():
        """Return distinct category names in use (legacy helper)."""
        try:
            return db.db[Property.collection].distinct('category')
        except Exception:
            return []


# ============================================================
# BOOKING
# ============================================================
class Booking:
    """Client reservation, linked to a Paystack payment reference."""
    collection = 'bookings'

    @staticmethod
    def all(filters=None, sort=None):
        q = filters or {}
        try:
            cursor = db.db[Booking.collection].find(q)
            cursor = _safe_sort_cursor(cursor, sort or [('created_at', -1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Booking.all failed')
            return []

    @staticmethod
    def get(bid):
        oid = safe_oid(bid)
        if not oid:
            return None
        try:
            doc = db.db[Booking.collection].find_one({'_id': oid})
            return oid_to_str(doc) if doc else None
        except Exception:
            log.exception('Booking.get failed')
            return None

    @staticmethod
    def by_user(user_id):
        if not user_id:
            return []
        try:
            cursor = db.db[Booking.collection].find({'user_id': user_id})
            cursor = _safe_sort_cursor(cursor, [('created_at', -1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Booking.by_user failed')
            return []

    @staticmethod
    def by_reference(reference):
        """Lookup by Paystack reference (case-insensitive)."""
        if not reference or not isinstance(reference, str):
            return None
        try:
            doc = db.db[Booking.collection].find_one({
                'payment_reference': reference.strip().upper(),
            })
            return oid_to_str(doc) if doc else None
        except Exception:
            log.exception('Booking.by_reference failed')
            return None

    @staticmethod
    def create(data):
        data = _strip_underscore_keys(dict(data))
        data['created_at'] = utcnow()
        data.setdefault('status', 'pending')
        data.setdefault('payment_status', 'pending')
        data.setdefault('currency', 'GHS')
        result = db.db[Booking.collection].insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    def update(bid, data):
        oid = safe_oid(bid)
        if not oid:
            return False
        data = _strip_underscore_keys(dict(data))
        data['updated_at'] = utcnow()
        try:
            db.db[Booking.collection].update_one({'_id': oid}, {'$set': data})
            return True
        except Exception:
            log.exception('Booking.update failed')
            return False

    @staticmethod
    def delete(bid):
        oid = safe_oid(bid)
        if not oid:
            return False
        try:
            db.db[Booking.collection].delete_one({'_id': oid})
            return True
        except Exception:
            log.exception('Booking.delete failed')
            return False

    @staticmethod
    def count(filters=None):
        try:
            return db.db[Booking.collection].count_documents(filters or {})
        except Exception:
            return 0


# ============================================================
# INQUIRY
# ============================================================
class Inquiry:
    """Guest inquiry submitted via the public contact form."""
    collection = 'inquiries'

    @staticmethod
    def all(filters=None, sort=None):
        q = filters or {}
        try:
            cursor = db.db[Inquiry.collection].find(q)
            cursor = _safe_sort_cursor(cursor, sort or [('created_at', -1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Inquiry.all failed')
            return []

    @staticmethod
    def get(iid):
        oid = safe_oid(iid)
        if not oid:
            return None
        try:
            doc = db.db[Inquiry.collection].find_one({'_id': oid})
            return oid_to_str(doc) if doc else None
        except Exception:
            log.exception('Inquiry.get failed')
            return None

    @staticmethod
    def by_email(email):
        if not email or not isinstance(email, str):
            return []
        try:
            cursor = db.db[Inquiry.collection].find({'email': email.lower().strip()})
            cursor = _safe_sort_cursor(cursor, [('created_at', -1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Inquiry.by_email failed')
            return []

    @staticmethod
    def create(data):
        data = _strip_underscore_keys(dict(data))
        data['created_at'] = utcnow()
        data.setdefault('status', 'new')
        result = db.db[Inquiry.collection].insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    def update(iid, data):
        oid = safe_oid(iid)
        if not oid:
            return False
        data = _strip_underscore_keys(dict(data))
        data['updated_at'] = utcnow()
        try:
            db.db[Inquiry.collection].update_one({'_id': oid}, {'$set': data})
            return True
        except Exception:
            log.exception('Inquiry.update failed')
            return False

    @staticmethod
    def delete(iid):
        oid = safe_oid(iid)
        if not oid:
            return False
        try:
            db.db[Inquiry.collection].delete_one({'_id': oid})
            return True
        except Exception:
            log.exception('Inquiry.delete failed')
            return False

    @staticmethod
    def count(filters=None):
        try:
            return db.db[Inquiry.collection].count_documents(filters or {})
        except Exception:
            return 0


# ============================================================
# REVIEW
# ============================================================
class Review:
    """Guest testimonial (moderated)."""
    collection = 'reviews'

    @staticmethod
    def all(filters=None, sort=None):
        q = filters or {}
        try:
            cursor = db.db[Review.collection].find(q)
            cursor = _safe_sort_cursor(cursor, sort or [('created_at', -1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Review.all failed')
            return []

    @staticmethod
    def get(rid):
        oid = safe_oid(rid)
        if not oid:
            return None
        try:
            doc = db.db[Review.collection].find_one({'_id': oid})
            return oid_to_str(doc) if doc else None
        except Exception:
            log.exception('Review.get failed')
            return None

    @staticmethod
    def create(data):
        data = _strip_underscore_keys(dict(data))
        data['created_at'] = utcnow()
        data.setdefault('status', 'pending')
        # Coerce rating to int, clamp 1–5
        try:
            data['rating'] = max(1, min(5, int(data.get('rating', 5))))
        except (TypeError, ValueError):
            data['rating'] = 5
        result = db.db[Review.collection].insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    def update(rid, data):
        oid = safe_oid(rid)
        if not oid:
            return False
        data = _strip_underscore_keys(dict(data))
        try:
            db.db[Review.collection].update_one({'_id': oid}, {'$set': data})
            return True
        except Exception:
            log.exception('Review.update failed')
            return False

    @staticmethod
    def delete(rid):
        oid = safe_oid(rid)
        if not oid:
            return False
        try:
            db.db[Review.collection].delete_one({'_id': oid})
            return True
        except Exception:
            log.exception('Review.delete failed')
            return False

    @staticmethod
    def count(filters=None):
        try:
            return db.db[Review.collection].count_documents(filters or {})
        except Exception:
            return 0


# ============================================================
# OWNER SUBMISSION  (DEPRECATED)
# ============================================================
class OwnerSubmission:
    """
    DEPRECATED — public owner submissions are no longer accepted.
    Admins manage the entire portfolio via `Property` + PropertyForm.

    This class is retained ONLY for:
      1. Legacy data export via `super_admin.export_data()`
      2. One-off migrations or archival scripts

    Do NOT use it in new code. It is NOT wired to any route.
    """
    collection = 'owner_submissions'
    __deprecated__ = True

    @staticmethod
    def all(filters=None, sort=None):
        log.warning('OwnerSubmission.all called — this model is deprecated.')
        q = filters or {}
        try:
            cursor = db.db[OwnerSubmission.collection].find(q)
            cursor = _safe_sort_cursor(cursor, sort or [('created_at', -1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('OwnerSubmission.all failed')
            return []

    @staticmethod
    def get(oid_str):
        log.warning('OwnerSubmission.get called — this model is deprecated.')
        oid = safe_oid(oid_str)
        if not oid:
            return None
        try:
            doc = db.db[OwnerSubmission.collection].find_one({'_id': oid})
            return oid_to_str(doc) if doc else None
        except Exception:
            log.exception('OwnerSubmission.get failed')
            return None

    @staticmethod
    def create(data):
        log.warning('OwnerSubmission.create called — this model is deprecated.')
        data = _strip_underscore_keys(dict(data))
        data['created_at'] = utcnow()
        data.setdefault('status', 'pending')
        result = db.db[OwnerSubmission.collection].insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    def update(oid_str, data):
        log.warning('OwnerSubmission.update called — this model is deprecated.')
        oid = safe_oid(oid_str)
        if not oid:
            return False
        data = _strip_underscore_keys(dict(data))
        data['updated_at'] = utcnow()
        try:
            db.db[OwnerSubmission.collection].update_one({'_id': oid}, {'$set': data})
            return True
        except Exception:
            log.exception('OwnerSubmission.update failed')
            return False

    @staticmethod
    def delete(oid_str):
        log.warning('OwnerSubmission.delete called — this model is deprecated.')
        oid = safe_oid(oid_str)
        if not oid:
            return False
        try:
            db.db[OwnerSubmission.collection].delete_one({'_id': oid})
            return True
        except Exception:
            log.exception('OwnerSubmission.delete failed')
            return False

    @staticmethod
    def count(filters=None):
        try:
            return db.db[OwnerSubmission.collection].count_documents(filters or {})
        except Exception:
            return 0

    @staticmethod
    def delete_all():
        """Wipe the entire deprecated collection. Returns count removed."""
        try:
            result = db.db[OwnerSubmission.collection].delete_many({})
            log.warning(f'OwnerSubmission.delete_all removed {result.deleted_count} docs.')
            return result.deleted_count
        except Exception:
            log.exception('OwnerSubmission.delete_all failed')
            return 0


# ============================================================
# JOURNAL SUBSCRIBER
# ============================================================
class JournalSubscriber:
    """Email list for the private journal newsletter."""
    collection = 'journal_subscribers'

    @staticmethod
    def all():
        try:
            cursor = db.db[JournalSubscriber.collection].find()
            cursor = _safe_sort_cursor(cursor, [('subscribed_at', -1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('JournalSubscriber.all failed')
            return []

    @staticmethod
    def get(sid):
        oid = safe_oid(sid)
        if not oid:
            return None
        try:
            doc = db.db[JournalSubscriber.collection].find_one({'_id': oid})
            return oid_to_str(doc) if doc else None
        except Exception:
            return None

    @staticmethod
    def add(email):
        """
        Atomic add with unique-index guarantee.
        Returns True if newly added, False if already present or invalid.
        """
        if not email or not isinstance(email, str):
            return False
        email = email.lower().strip()
        try:
            db.db[JournalSubscriber.collection].insert_one({
                'email': email,
                'subscribed_at': utcnow(),
            })
            return True
        except DuplicateKeyError:
            return False
        except Exception:
            log.exception('JournalSubscriber.add failed')
            return False

    @staticmethod
    def delete(sid):
        oid = safe_oid(sid)
        if not oid:
            return False
        try:
            db.db[JournalSubscriber.collection].delete_one({'_id': oid})
            return True
        except Exception:
            log.exception('JournalSubscriber.delete failed')
            return False

    @staticmethod
    def count():
        try:
            return db.db[JournalSubscriber.collection].count_documents({})
        except Exception:
            return 0


# ============================================================
# MESSAGE  (Concierge Chat)
# ============================================================
class Message:
    """Chat message between a client and the concierge team."""
    collection = 'messages'

    @staticmethod
    def by_user(user_id):
        if not user_id:
            return []
        try:
            cursor = db.db[Message.collection].find({'user_id': user_id})
            # Sort by timestamp, then _id for stable same-millisecond ordering
            cursor = _safe_sort_cursor(cursor, [('timestamp', 1), ('_id', 1)])
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Message.by_user failed')
            return []

    @staticmethod
    def create(data):
        data = _strip_underscore_keys(dict(data))
        data['timestamp'] = utcnow()
        data.setdefault('from', 'me')
        result = db.db[Message.collection].insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    def count(filters=None):
        try:
            return db.db[Message.collection].count_documents(filters or {})
        except Exception:
            return 0


# ============================================================
# WISHLIST
# ============================================================
class Wishlist:
    """Per-user set of saved property IDs."""
    collection = 'wishlists'

    @staticmethod
    def get(user_id):
        if not user_id:
            return []
        try:
            doc = db.db[Wishlist.collection].find_one({'user_id': user_id})
            return list(doc.get('property_ids', [])) if doc else []
        except Exception:
            log.exception('Wishlist.get failed')
            return []

    @staticmethod
    def toggle(user_id, property_id):
        """
        Atomic toggle using $addToSet / $pull.
        Returns True if added, False if removed or on error.
        """
        if not user_id or not property_id:
            return False

        property_id = str(property_id)

        try:
            result = db.db[Wishlist.collection].update_one(
                {'user_id': user_id, 'property_ids': property_id},
                {'$pull': {'property_ids': property_id}},
            )
            if result.modified_count:
                return False  # removed

            db.db[Wishlist.collection].update_one(
                {'user_id': user_id},
                {'$addToSet': {'property_ids': property_id}},
                upsert=True,
            )
            return True  # added

        except Exception:
            log.exception('Wishlist.toggle failed')
            return False

    @staticmethod
    def clear(user_id):
        if not user_id:
            return False
        try:
            db.db[Wishlist.collection].delete_one({'user_id': user_id})
            return True
        except Exception:
            return False


# ============================================================
# SETTINGS  (singleton)
# ============================================================
class Settings:
    """Site-wide settings document, stored as a singleton."""
    collection = 'settings'
    DOC_ID = 'site'

    DEFAULTS = {
        'site_name': 'Le Rêve Properties',
        'contact_email': 'concierge@lereveproperties.com',
        'whatsapp': '+233 30 000 0000',
        'instagram': '@lereveproperties',
    }

    @staticmethod
    def get():
        try:
            doc = db.db[Settings.collection].find_one({'_id': Settings.DOC_ID})
            if not doc:
                defaults = {'_id': Settings.DOC_ID, **Settings.DEFAULTS}
                db.db[Settings.collection].insert_one(defaults)
                return dict(Settings.DEFAULTS)
            return {k: v for k, v in doc.items() if k != '_id'}
        except Exception:
            log.exception('Settings.get failed')
            return dict(Settings.DEFAULTS)

    @staticmethod
    def update(data):
        if not data:
            return False
        data = _strip_underscore_keys(dict(data))
        try:
            db.db[Settings.collection].update_one(
                {'_id': Settings.DOC_ID},
                {'$set': data},
                upsert=True,
            )
            return True
        except Exception:
            log.exception('Settings.update failed')
            return False

    @staticmethod
    def reset():
        """Restore default settings."""
        try:
            db.db[Settings.collection].delete_one({'_id': Settings.DOC_ID})
            Settings.get()
            return True
        except Exception:
            log.exception('Settings.reset failed')
            return False