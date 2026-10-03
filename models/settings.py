"""
============================================================
SETTINGS MODEL — singleton
============================================================
"""
import logging

from extensions import db


log = logging.getLogger(__name__)


class Settings:
    collection = 'settings'
    DOC_ID = 'site'

    DEFAULTS = {
        'site_name': 'Le Rêve Properties',
        'contact_email': 'concierge@lereveproperties.com',
        'whatsapp': '+233 54 797 5252',
        'instagram': '@lereveproperties',
    }

    @staticmethod
    def get():
        doc = db.db[Settings.collection].find_one({'_id': Settings.DOC_ID})
        if not doc:
            defaults = {'_id': Settings.DOC_ID, **Settings.DEFAULTS}
            db.db[Settings.collection].insert_one(defaults)
            return dict(Settings.DEFAULTS)
        return {k: v for k, v in doc.items() if k != '_id'}

    @staticmethod
    def update(data):
        if not data:
            return False
        data = {k: v for k, v in data.items() if k != '_id'}
        db.db[Settings.collection].update_one(
            {'_id': Settings.DOC_ID}, {'$set': data}, upsert=True,
        )
        return True