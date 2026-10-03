"""
============================================================
WISHLIST MODEL
============================================================
"""
import logging

from extensions import db
from .base import safe_oid


log = logging.getLogger(__name__)


class Wishlist:
    collection = 'wishlists'

    @staticmethod
    def get(user_id):
        if not user_id:
            return []
        doc = db.db[Wishlist.collection].find_one({'user_id': user_id})
        return list(doc.get('property_ids', [])) if doc else []

    @staticmethod
    def toggle(user_id, property_id):
        """Atomic toggle. Returns True if added, False if removed."""
        if not user_id or not property_id:
            return False
        pid = str(property_id)
        result = db.db[Wishlist.collection].update_one(
            {'user_id': user_id, 'property_ids': pid},
            {'$pull': {'property_ids': pid}},
        )
        if result.modified_count:
            return False
        db.db[Wishlist.collection].update_one(
            {'user_id': user_id},
            {'$addToSet': {'property_ids': pid}},
            upsert=True,
        )
        return True

    @staticmethod
    def clear(user_id):
        if not user_id:
            return False
        db.db[Wishlist.collection].delete_one({'user_id': user_id})
        return True