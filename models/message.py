"""
============================================================
MESSAGE MODEL — threaded concierge chat
============================================================

Thread ID convention (IMPORTANT — keep both sides in sync):
    thread_id = f"user-{user_id}"

`user_id` is the stringified Mongo `_id` of the user document,
so a thread id looks like "user-6650a1b2c3d4e5f6a7b8c9d0".

Both the client portal (client.py) and the admin inbox (admin.py)
MUST use this same format. Never use a raw ObjectId as the
thread_id for a user thread — that mismatch is what caused the
admin inbox to appear empty while the client kept sending.
"""
import logging

from extensions import db
from .base import utcnow, safe_oid, oid_to_str


log = logging.getLogger(__name__)


class Message:
    """Threaded concierge chat between clients and admins."""

    collection = 'messages'

    # 'client' = sent by the guest; 'admin' = sent by concierge
    VALID_SENDERS = {'client', 'admin'}

    # ============================================================
    # Thread-id helpers (single source of truth)
    # ============================================================
    @staticmethod
    def thread_id_for_user(user_id):
        """Canonical thread id for a user's concierge conversation.

        Use this everywhere on both the client and admin side. If you
        ever change the format, you change it here and nowhere else.
        """
        if user_id is None:
            return None
        return f"user-{user_id}"

    @staticmethod
    def _normalize_thread_id(thread_id):
        """Accept either a raw user id or a prefixed thread id.

        Returns the canonical 'user-<id>' form, or None if empty.
        """
        if not thread_id:
            return None
        s = str(thread_id)
        return s if s.startswith('user-') else f"user-{s}"

    # ============================================================
    # Read APIs
    # ============================================================
    @staticmethod
    def by_user(user_id, limit=500):
        """All messages for a user, oldest first (kept for compatibility)."""
        if not user_id:
            return []
        try:
            cursor = (
                db.db[Message.collection]
                .find({'user_id': str(user_id)})
                .sort([('created_at', 1), ('_id', 1)])
                .limit(limit)
            )
            return [oid_to_str(d) for d in cursor]
        except Exception:
            log.exception('Message.by_user failed')
            return []

    @staticmethod
    def by_thread(thread_id, limit=None):
        """Return messages in a thread, oldest first.

        When `limit` is provided, returns the *newest* N messages but
        still ordered oldest-first inside the returned list — that is
        what the UI expects (so the last item is the most recent one).
        """
        thread_id = Message._normalize_thread_id(thread_id)
        if not thread_id:
            return []
        try:
            if limit:
                docs = list(
                    db.db[Message.collection]
                    .find({'thread_id': thread_id})
                    .sort([('created_at', -1), ('_id', -1)])
                    .limit(limit)
                )
                docs.reverse()
            else:
                docs = list(
                    db.db[Message.collection]
                    .find({'thread_id': thread_id})
                    .sort([('created_at', 1), ('_id', 1)])
                )
            return [oid_to_str(d) for d in docs]
        except Exception:
            log.exception('Message.by_thread failed')
            return []

    @staticmethod
    def latest_per_user():
        """One latest message per thread, for the admin inbox list.

        The returned `_id` field is the **thread_id** string
        (e.g. "user-<user_id>"), NOT the raw user ObjectId. This is
        what `admin.message_thread(thread_id)` expects in its URL.
        """
        pipeline = [
            # Only user conversations — skip stray system threads.
            {'$match': {'thread_id': {'$regex': r'^user-'}}},
            # Newest first so $first gives us the latest per thread.
            {'$sort': {'created_at': -1, '_id': -1}},
            {'$group': {
                '_id':          '$thread_id',
                'user_id':      {'$first': '$user_id'},
                'user_name':    {'$first': '$user_name'},
                'user_email':   {'$first': '$user_email'},
                'last_message': {'$first': '$text'},
                'last_sender':  {'$first': '$sender'},
                'last_at':      {'$first': '$created_at'},
            }},
            # Most recent conversation first.
            {'$sort': {'last_at': -1}},
        ]
        try:
            return list(db.db[Message.collection].aggregate(pipeline))
        except Exception:
            log.exception('Message.latest_per_user failed')
            return []

    # ============================================================
    # Unread counts
    # ============================================================
    @staticmethod
    def unread_for_admin(thread_id):
        """Count client messages in a thread the admin hasn't read yet."""
        thread_id = Message._normalize_thread_id(thread_id)
        if not thread_id:
            return 0
        try:
            return db.db[Message.collection].count_documents({
                'thread_id':     thread_id,
                'sender':        'client',
                'read_by_admin': {'$ne': True},
            })
        except Exception:
            log.exception('Message.unread_for_admin failed')
            return 0

    @staticmethod
    def unread_for_client(user_id):
        """Count admin messages in a user's thread the client hasn't read."""
        if not user_id:
            return 0
        thread_id = Message.thread_id_for_user(user_id)
        try:
            return db.db[Message.collection].count_documents({
                'thread_id':      thread_id,
                'sender':         'admin',
                'read_by_client': {'$ne': True},
            })
        except Exception:
            log.exception('Message.unread_for_client failed')
            return 0

    # ============================================================
    # Write APIs
    # ============================================================
    @staticmethod
    def create(data):
        """Insert a message and return its string id (or None on failure).

        - Strips `_id` so callers can't clobber it.
        - Normalizes `thread_id` (accepts raw id or 'user-<id>' form).
        - Normalizes `user_id` to a string.
        - Stamps `created_at` if absent.
        - Validates `sender` and sets the read flags accordingly.
        """
        data = {k: v for k, v in (data or {}).items() if k != '_id'}

        if data.get('thread_id'):
            data['thread_id'] = Message._normalize_thread_id(data['thread_id'])

        if data.get('user_id') is not None:
            data['user_id'] = str(data['user_id'])

        data.setdefault('created_at', utcnow())

        sender = data.get('sender', 'client')
        if sender not in Message.VALID_SENDERS:
            sender = 'client'
        data['sender'] = sender

        # A message is read by its own sender immediately.
        data.setdefault('read_by_admin',  sender == 'admin')
        data.setdefault('read_by_client', sender == 'client')

        try:
            result = db.db[Message.collection].insert_one(data)
            return str(result.inserted_id)
        except Exception:
            log.exception('Message.create failed')
            return None

    @staticmethod
    def mark_read(thread_id, by='admin'):
        """Mark every message in a thread as read by the given side."""
        thread_id = Message._normalize_thread_id(thread_id)
        if not thread_id:
            return

        if by == 'admin':
            field = 'read_by_admin'
            cond = {'sender': 'client'}
        else:
            field = 'read_by_client'
            cond = {'sender': 'admin'}

        try:
            db.db[Message.collection].update_many(
                {'thread_id': thread_id, field: {'$ne': True}, **cond},
                {'$set': {field: True}},
            )
        except Exception:
            log.exception('Message.mark_read failed')

    # ============================================================
    # Misc
    # ============================================================
    @staticmethod
    def count(filters=None):
        """Count messages matching `filters` (defaults to all)."""
        try:
            return db.db[Message.collection].count_documents(filters or {})
        except Exception:
            log.exception('Message.count failed')
            return 0