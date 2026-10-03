"""
============================================================
JOURNAL SUBSCRIBER MODEL
============================================================
"""
import logging

from pymongo.errors import DuplicateKeyError

from extensions import db
from .base import utcnow, safe_oid, oid_to_str


log = logging.getLogger(__name__)


class JournalSubscriber:
    collection = 'journal_subscribers'

    @staticmethod
    def all(skip=0, limit=0):
        cursor = db.db[JournalSubscriber.collection].find()
        cursor = cursor.sort([('subscribed_at', -1)])
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def get(sid):
        oid = safe_oid(sid)
        if not oid:
            return None
        doc = db.db[JournalSubscriber.collection].find_one({'_id': oid})
        return oid_to_str(doc) if doc else None

    @staticmethod
    def add(email):
        if not email:
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

    @staticmethod
    def delete(sid):
        oid = safe_oid(sid)
        if not oid:
            return False
        db.db[JournalSubscriber.collection].delete_one({'_id': oid})
        return True

    @staticmethod
    def count(filters=None):
        return db.db[JournalSubscriber.collection].count_documents(filters or {})