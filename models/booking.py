"""
============================================================
BOOKING MODEL
============================================================
"""
import logging

from extensions import db
from .base import utcnow, safe_oid, oid_to_str


log = logging.getLogger(__name__)


class Booking:
    collection = 'bookings'

    @staticmethod
    def all(filters=None, sort=None, skip=0, limit=0):
        q = filters or {}
        cursor = db.db[Booking.collection].find(q)
        cursor = cursor.sort(sort or [('created_at', -1)])
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def get(bid):
        oid = safe_oid(bid)
        if not oid:
            return None
        doc = db.db[Booking.collection].find_one({'_id': oid})
        return oid_to_str(doc) if doc else None

    @staticmethod
    def by_user(user_id, skip=0, limit=0):
        if not user_id:
            return []
        cursor = db.db[Booking.collection].find({'user_id': user_id})
        cursor = cursor.sort([('created_at', -1)])
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def by_reference(reference):
        if not reference:
            return None
        doc = db.db[Booking.collection].find_one({
            'payment_reference': reference.strip().upper(),
        })
        return oid_to_str(doc) if doc else None

    @staticmethod
    def has_overlap(property_id, check_in, check_out, exclude_id=None):
        """Return True if any confirmed/pending booking overlaps."""
        q = {
            'property_id': property_id,
            'status': {'$in': ['pending', 'confirmed']},
            'check_in': {'$lt': check_out},
            'check_out': {'$gt': check_in},
        }
        if exclude_id:
            oid = safe_oid(exclude_id)
            if oid:
                q['_id'] = {'$ne': oid}
        return db.db[Booking.collection].find_one(q) is not None

    @staticmethod
    def create(data):
        data = {k: v for k, v in data.items() if k != '_id'}
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
        allowed = {
            'status', 'payment_status', 'payment_reference', 'payment_error',
            'paid_at', 'payment_amount', 'payment_channel', 'updated_at',
            'check_in', 'check_out', 'guests', 'total', 'nights',
            'nightly_rate', 'confirmation_id', 'notes', 'cancellation_reason',
        }
        data = {k: v for k, v in data.items() if k in allowed}
        data['updated_at'] = utcnow()
        db.db[Booking.collection].update_one({'_id': oid}, {'$set': data})
        return True

    @staticmethod
    def delete(bid):
        oid = safe_oid(bid)
        if not oid:
            return False
        db.db[Booking.collection].delete_one({'_id': oid})
        return True

    @staticmethod
    def count(filters=None):
        return db.db[Booking.collection].count_documents(filters or {})

    @staticmethod
    def revenue_total(filters=None):
        pipeline = [
            {'$match': filters or {'payment_status': 'paid'}},
            {'$group': {'_id': None, 'total': {'$sum': '$total'}}},
        ]
        result = list(db.db[Booking.collection].aggregate(pipeline))
        return float(result[0]['total']) if result else 0.0

    @staticmethod
    def status_breakdown():
        pipeline = [
            {'$group': {'_id': '$status', 'count': {'$sum': 1}}},
        ]
        return {r['_id']: r['count'] for r in db.db[Booking.collection].aggregate(pipeline)}

    @staticmethod
    def bookings_by_day(days=30):
        from datetime import datetime, timezone, timedelta
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {'$match': {'created_at': {'$gte': since}}},
            {'$group': {
                '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
                'count': {'$sum': 1},
                'revenue': {'$sum': '$total'},
            }},
            {'$sort': {'_id': 1}},
        ]
        return list(db.db[Booking.collection].aggregate(pipeline))