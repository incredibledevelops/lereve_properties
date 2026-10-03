"""
============================================================
MESSAGE MODEL — threaded concierge chat
============================================================
"""
import logging

from extensions import db
from .base import utcnow, safe_oid, oid_to_str


log = logging.getLogger(__name__)


class Message:
    collection = 'messages'

    # 'client' = sent by the guest; 'admin' = sent by concierge
    VALID_SENDERS = {'client', 'admin'}

    @staticmethod
    def by_user(user_id, limit=500):
        if not user_id:
            return []
        cursor = db.db[Message.collection].find({'user_id': user_id})
        cursor = cursor.sort([('created_at', 1), ('_id', 1)]).limit(limit)
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def by_thread(thread_id, limit=500):
        if not thread_id:
            return []
        cursor = db.db[Message.collection].find({'thread_id': thread_id})
        cursor = cursor.sort([('created_at', 1), ('_id', 1)]).limit(limit)
        return [oid_to_str(d) for d in cursor]

    @staticmethod
    def create(data):
        data = {k: v for k, v in data.items() if k != '_id'}
        data['created_at'] = utcnow()
        sender = data.get('sender', 'client')
        if sender not in Message.VALID_SENDERS:
            sender = 'client'
        data['sender'] = sender
        data.setdefault('read_by_admin', sender == 'admin')
        data.setdefault('read_by_client', sender == 'client')
        result = db.db[Message.collection].insert_one(data)
        return str(result.inserted_id)

    @staticmethod
    def mark_read(thread_id, by='admin'):
        field = 'read_by_admin' if by == 'admin' else 'read_by_client'
        db.db[Message.collection].update_many(
            {'thread_id': thread_id, field: False},
            {'$set': {field: True}},
        )

    @staticmethod
    def unread_for_admin(thread_id):
        return db.db[Message.collection].count_documents({
            'thread_id': thread_id,
            'sender': 'client',
            'read_by_admin': False,
        })

    @staticmethod
    def unread_for_client(user_id):
        return db.db[Message.collection].count_documents({
            'user_id': user_id,
            'sender': 'admin',
            'read_by_client': False,
        })

    @staticmethod
    def count(filters=None):
        return db.db[Message.collection].count_documents(filters or {})

    @staticmethod
    def latest_per_user():
        """Return one latest message per user (for admin inbox list)."""
        pipeline = [
            {'$sort': {'created_at': -1}},
            {'$group': {
                '_id': '$thread_id',
                'user_id': {'$first': '$user_id'},
                'user_name': {'$first': '$user_name'},
                'user_email': {'$first': '$user_email'},
                'last_message': {'$first': '$text'},
                'last_sender': {'$first': '$sender'},
                'last_at': {'$first': '$created_at'},
            }},
            {'$sort': {'last_at': -1}},
        ]
        return list(db.db[Message.collection].aggregate(pipeline))