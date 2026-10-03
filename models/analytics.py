"""
============================================================
ANALYTICS EVENT MODEL
Tracks page views, searches, wishlist adds, etc. from the
public site and the portal itself.
============================================================
"""
import logging
from datetime import datetime, timezone, timedelta

from extensions import db
from .base import utcnow


log = logging.getLogger(__name__)


class AnalyticsEvent:
    collection = 'analytics_events'

    VALID_TYPES = {
        'page_view', 'property_view', 'search', 'wishlist_add',
        'inquiry', 'journal_subscribe', 'booking_started',
        'booking_completed', 'login', 'register',
    }

    @staticmethod
    def track(event_type, payload=None, user_id=None, ip=None, ua=None):
        if event_type not in AnalyticsEvent.VALID_TYPES:
            log.warning(f'Unknown analytics event: {event_type}')
            return None
        doc = {
            'type': event_type,
            'payload': payload or {},
            'user_id': user_id,
            'ip': ip,
            'ua': (ua or '')[:300],
            'created_at': utcnow(),
        }
        try:
            result = db.db[AnalyticsEvent.collection].insert_one(doc)
            return str(result.inserted_id)
        except Exception:
            log.exception('Analytics track failed')
            return None

    @staticmethod
    def count_by_type(days=30):
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {'$match': {'created_at': {'$gte': since}}},
            {'$group': {'_id': '$type', 'count': {'$sum': 1}}},
        ]
        return {r['_id']: r['count'] for r in db.db[AnalyticsEvent.collection].aggregate(pipeline)}

    @staticmethod
    def daily_series(event_type, days=30):
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {'$match': {'type': event_type, 'created_at': {'$gte': since}}},
            {'$group': {
                '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
                'count': {'$sum': 1},
            }},
            {'$sort': {'_id': 1}},
        ]
        return list(db.db[AnalyticsEvent.collection].aggregate(pipeline))

    @staticmethod
    def top_searches(days=30, limit=10):
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {'$match': {'type': 'search', 'created_at': {'$gte': since}}},
            {'$group': {'_id': '$payload.q', 'count': {'$sum': 1}}},
            {'$match': {'_id': {'$ne': None, '$ne': ''}}},
            {'$sort': {'count': -1}},
            {'$limit': limit},
        ]
        return list(db.db[AnalyticsEvent.collection].aggregate(pipeline))

    @staticmethod
    def top_properties(days=30, limit=10):
        since = datetime.now(timezone.utc) - timedelta(days=days)
        pipeline = [
            {'$match': {'type': 'property_view', 'created_at': {'$gte': since}}},
            {'$group': {'_id': '$payload.property_id', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}},
            {'$limit': limit},
        ]
        return list(db.db[AnalyticsEvent.collection].aggregate(pipeline))

    @staticmethod
    def purge_older_than(days=180):
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = db.db[AnalyticsEvent.collection].delete_many({'created_at': {'$lt': cutoff}})
        return result.deleted_count