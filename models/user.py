"""
============================================================
USER MODEL — client + super_admin
============================================================
"""
import logging
from datetime import datetime

from flask_login import UserMixin
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from .base import utcnow, safe_oid, oid_to_str


log = logging.getLogger(__name__)


class User(UserMixin):
    collection = 'users'

    VALID_TIERS = {'Silver', 'Gold', 'Platinum', 'Black'}
    VALID_ROLES = {'client', 'super_admin'}

    def __init__(self, **kwargs):
        _id = kwargs.get('_id')
        self.id = str(_id) if _id else None
        self.email = (kwargs.get('email') or '').lower().strip()
        self.name = kwargs.get('name') or ''
        self.phone = kwargs.get('phone') or ''
        self.country = kwargs.get('country') or ''
        self.bio = kwargs.get('bio') or ''
        self.password_hash = kwargs.get('password_hash') or ''
        self.role = kwargs.get('role') if kwargs.get('role') in self.VALID_ROLES else 'client'
        self.avatar = kwargs.get('avatar') or ''

        tier = kwargs.get('tier') or 'Silver'
        self.tier = tier if tier in self.VALID_TIERS else 'Silver'

        prefs = kwargs.get('preferences') or {}
        comm = prefs.get('comm') or {}
        self.preferences = {
            'type': prefs.get('type', ''),
            'diet': prefs.get('diet', ''),
            'amenities': list(prefs.get('amenities') or []),
            'comm': {
                'newsletter': comm.get('newsletter', True),
                'sms': comm.get('sms', False),
                'promo': comm.get('promo', True),
            },
        }

        self._is_active = kwargs.get('is_active', True)
        self.created_at = kwargs.get('created_at') or utcnow()
        self.member_since = kwargs.get('member_since') or self.created_at
        self.last_login = kwargs.get('last_login')

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

    # ---------- Flask-Login ----------
    @property
    def is_active(self):
        return self._is_active

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
        if self.avatar:
            return self.avatar
        if not self.name:
            return ''
        safe = self.name.replace(' ', '+')
        return f"https://ui-avatars.com/api/?name={safe}&background=c9a84c&color=1a3a2a"

    # ---------- Serialization ----------
    def to_dict(self, include_password=False, include_id=False):
        data = {
            'email': self.email,
            'name': self.name,
            'phone': self.phone,
            'country': self.country,
            'bio': self.bio,
            'role': self.role,
            'tier': self.tier,
            'avatar': self.avatar,
            'preferences': self.preferences,
            'is_active': self._is_active,
            'created_at': self.created_at,
            'member_since': self.member_since,
        }
        if include_password:
            data['password_hash'] = self.password_hash
        if self.last_login:
            data['last_login'] = self.last_login
        if include_id and self.id:
            oid = safe_oid(self.id)
            if oid:
                data['_id'] = oid
        return data

    def to_json(self):
        d = oid_to_str(self.to_dict(include_password=False, include_id=True))
        return d

    # ---------- Finders ----------
    @classmethod
    def find_by_email(cls, email):
        if not email or not isinstance(email, str):
            return None
        doc = db.db[cls.collection].find_one({'email': email.lower().strip()})
        return cls(**doc) if doc else None

    @classmethod
    def find_by_id(cls, uid):
        oid = safe_oid(uid)
        if not oid:
            return None
        doc = db.db[cls.collection].find_one({'_id': oid})
        return cls(**doc) if doc else None

    @classmethod
    def find_by_id_raw(cls, uid):
        oid = safe_oid(uid)
        if not oid:
            return None
        return db.db[cls.collection].find_one({'_id': oid})

    @classmethod
    def create(cls, email, name, password, **extra):
        user = cls(email=email, name=name, **extra)
        user.set_password(password)
        try:
            result = db.db[cls.collection].insert_one(
                user.to_dict(include_password=True)
            )
            user.id = str(result.inserted_id)
            return user
        except DuplicateKeyError:
            log.warning(f'Duplicate user: {email}')
            return None

    @classmethod
    def all(cls, filters=None, sort=None, skip=0, limit=0, projection=None):
        q = filters or {}
        cursor = db.db[cls.collection].find(q, projection)
        cursor = cursor.sort(sort or [('created_at', -1)])
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [oid_to_str(d) for d in cursor]

    @classmethod
    def count(cls, filters=None):
        return db.db[cls.collection].count_documents(filters or {})

    @classmethod
    def update(cls, uid, data):
        oid = safe_oid(uid)
        if not oid:
            return False
        data = strip_internal_keys(data) if False else {k: v for k, v in data.items() if k != '_id'}
        data['updated_at'] = utcnow()
        db.db[cls.collection].update_one({'_id': oid}, {'$set': data})
        return True

    @classmethod
    def soft_delete(cls, uid):
        return cls.update(uid, {'is_active': False})

    @classmethod
    def delete(cls, uid):
        oid = safe_oid(uid)
        if not oid:
            return False
        db.db[cls.collection].delete_one({'_id': oid})
        return True