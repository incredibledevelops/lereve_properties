"""
============================================================
REVIEW MODEL
============================================================
"""
import logging

from extensions import db
from .base import utcnow, safe_oid, oid_to_str


log = logging.getLogger(__name__)


class Review:
    collection = 'reviews'

    @staticmethod
    def all(filters=None, sort=None, skip=0, limit=0):
        q = filters or {}
        cursor = db.db[Review.collection].find(q)
        cursor = cursor.sort(sort or [('created_at', -1)])
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def get(rid):
        oid = safe_oid(rid)
        if not oid:
            return None
        doc = db.db[Review.collection].find_one({'_id': oid})
        return oid_to_str(doc) if doc else None

    @staticmethod
    def create(data):
        data = {k: v for k, v in data.items() if k != '_id'}
        data['created_at'] = utcnow()
        data.setdefault('status', 'pending')
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
        data = {k: v for k, v in data.items() if k != '_id'}
        db.db[Review.collection].update_one({'_id': oid}, {'$set': data})
        return True

    @staticmethod
    def delete(rid):
        oid = safe_oid(rid)
        if not oid:
            return False
        db.db[Review.collection].delete_one({'_id': oid})
        return True

    @staticmethod
    def count(filters=None):
        return db.db[Review.collection].count_documents(filters or {})