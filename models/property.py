"""
============================================================
PROPERTY MODEL
============================================================
"""
import logging

from extensions import db
from .base import utcnow, safe_oid, oid_to_str, slugify


log = logging.getLogger(__name__)


class Property:
    collection = 'properties'

    LIST_PROJECTION = {
        '_id': 1, 'title': 1, 'slug': 1, 'category': 1, 'location': 1,
        'price': 1, 'original_price': 1, 'beds': 1, 'baths': 1, 'guests': 1,
        'rating': 1, 'reviews_count': 1, 'image': 1, 'amenities': 1,
        'created_at': 1,
    }

    @staticmethod
    def all(filters=None, sort=None, skip=0, limit=0, projection=None):
        q = filters or {}
        cursor = db.db[Property.collection].find(q, projection)
        cursor = cursor.sort(sort or [('created_at', -1)])
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def get(pid):
        oid = safe_oid(pid)
        if not oid:
            return None
        doc = db.db[Property.collection].find_one({'_id': oid})
        return oid_to_str(doc) if doc else None

    @staticmethod
    def get_by_slug(slug):
        if not slug:
            return None
        doc = db.db[Property.collection].find_one({'slug': slug})
        return oid_to_str(doc) if doc else None

    @staticmethod
    def create(data):
        data = {k: v for k, v in data.items() if k != '_id'}
        data['slug'] = data.get('slug') or slugify(data.get('title', ''))
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
        data = {k: v for k, v in data.items() if k != '_id'}
        if 'title' in data:
            data['slug'] = slugify(data['title'])
        data['updated_at'] = utcnow()
        db.db[Property.collection].update_one({'_id': oid}, {'$set': data})
        return True

    @staticmethod
    def delete(pid):
        oid = safe_oid(pid)
        if not oid:
            return False
        db.db[Property.collection].delete_one({'_id': oid})
        return True

    @staticmethod
    def count(filters=None):
        return db.db[Property.collection].count_documents(filters or {})

    @staticmethod
    def count_by_category(name):
        if not name:
            return 0
        return db.db[Property.collection].count_documents({'category': name.strip()})

    @staticmethod
    def distinct_categories():
        return db.db[Property.collection].distinct('category')

    @staticmethod
    def top_by_bookings(limit=5):
        """Return top-N properties by confirmed booking count."""
        pipeline = [
            {'$match': {'status': 'confirmed'}},
            {'$group': {'_id': '$property_id', 'bookings': {'$sum': 1},
                        'revenue': {'$sum': '$total'}}},
            {'$sort': {'bookings': -1}},
            {'$limit': limit},
        ]
        return list(db.db['bookings'].aggregate(pipeline))