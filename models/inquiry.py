"""
============================================================
INQUIRY MODEL
============================================================
"""
import logging

from extensions import db
from .base import utcnow, safe_oid, oid_to_str


log = logging.getLogger(__name__)


class Inquiry:
    collection = 'inquiries'

    @staticmethod
    def all(filters=None, sort=None, skip=0, limit=0):
        q = filters or {}
        cursor = db.db[Inquiry.collection].find(q)
        cursor = cursor.sort(sort or [('created_at', -1)])
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def get(iid):
        oid = safe_oid(iid)
        if not oid:
            return None
        doc = db.db[Inquiry.collection].find_one({'_id': oid})
        return oid_to_str(doc) if doc else None

    @staticmethod
    def by_email(email):
        if not email:
            return []
        cursor = db.db[Inquiry.collection].find({'email': email.lower().strip()})
        cursor = cursor.sort([('created_at', -1)])
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def create(data):
        data = {k: v for k, v in data.items() if k != '_id'}
        data['created_at'] = utcnow()
        data.setdefault('status', 'new')
        result = db.db[Inquiry.collection].insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    def update(iid, data):
        oid = safe_oid(iid)
        if not oid:
            return False
        data = {k: v for k, v in data.items() if k != '_id'}
        data['updated_at'] = utcnow()
        db.db[Inquiry.collection].update_one({'_id': oid}, {'$set': data})
        return True

    @staticmethod
    def delete(iid):
        oid = safe_oid(iid)
        if not oid:
            return False
        db.db[Inquiry.collection].delete_one({'_id': oid})
        return True

    @staticmethod
    def count(filters=None):
        return db.db[Inquiry.collection].count_documents(filters or {})