"""
============================================================
CATEGORY MODEL — dynamic estate categories
============================================================
"""
import logging

from pymongo.errors import DuplicateKeyError

from extensions import db
from .base import utcnow, safe_oid, oid_to_str, slugify


log = logging.getLogger(__name__)


class Category:
    collection = 'categories'
    DEFAULT_ICON = 'fa-house-chimney'

    @staticmethod
    def all(sort=None):
        cursor = db.db[Category.collection].find()
        cursor = cursor.sort(sort or [('order', 1), ('name', 1)])
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def names():
        cursor = db.db[Category.collection].find({}, {'name': 1}).sort([('order', 1), ('name', 1)])
        return [d['name'] for d in cursor if d.get('name')]

    @staticmethod
    def get(cid):
        oid = safe_oid(cid)
        if not oid:
            return None
        doc = db.db[Category.collection].find_one({'_id': oid})
        return oid_to_str(doc) if doc else None

    @staticmethod
    def find_by_name(name):
        if not name:
            return None
        doc = db.db[Category.collection].find_one({'name': name.strip()})
        return oid_to_str(doc) if doc else None

    @staticmethod
    def create(data):
        data = {k: v for k, v in data.items() if k != '_id'}
        name = (data.get('name') or '').strip()
        if not name:
            return None
        data['name'] = name
        data['slug'] = data.get('slug') or slugify(name)
        data['icon'] = data.get('icon') or Category.DEFAULT_ICON
        try:
            data['order'] = int(data.get('order') or 0)
        except (TypeError, ValueError):
            data['order'] = 0
        data['description'] = (data.get('description') or '').strip()
        data['created_at'] = utcnow()
        data['updated_at'] = utcnow()
        try:
            result = db.db[Category.collection].insert_one(data)
            return str(result.inserted_id)
        except DuplicateKeyError:
            log.warning(f'Duplicate category: {name}')
            return None

    @staticmethod
    def update(cid, data):
        oid = safe_oid(cid)
        if not oid:
            return False
        data = {k: v for k, v in data.items() if k != '_id'}
        if 'name' in data:
            data['name'] = (data['name'] or '').strip()
            if not data['name']:
                return False
            data['slug'] = slugify(data['name'])
        if 'order' in data:
            try:
                data['order'] = int(data['order'])
            except (TypeError, ValueError):
                data['order'] = 0
        data['updated_at'] = utcnow()
        db.db[Category.collection].update_one({'_id': oid}, {'$set': data})
        return True

    @staticmethod
    def delete(cid):
        oid = safe_oid(cid)
        if not oid:
            return False
        db.db[Category.collection].delete_one({'_id': oid})
        return True

    @staticmethod
    def count(filters=None):
        return db.db[Category.collection].count_documents(filters or {})