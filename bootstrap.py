"""
============================================================
DATABASE BOOTSTRAP — indexes + seed data
No circular imports. Imported by app.py and admin reset.
============================================================
"""
import logging

from extensions import db
from models import User, Category


log = logging.getLogger(__name__)


def ensure_indexes():
    db.db['users'].create_index('email', unique=True)
    db.db['users'].create_index([('role', 1), ('created_at', -1)])

    db.db['properties'].create_index([('category', 1), ('price', 1)])
    db.db['properties'].create_index([('created_at', -1)])
    db.db['properties'].create_index('slug', unique=True, sparse=True)

    db.db['bookings'].create_index([('user_id', 1), ('created_at', -1)])
    db.db['bookings'].create_index('payment_reference', sparse=True)
    db.db['bookings'].create_index([('property_id', 1), ('check_in', 1), ('check_out', 1)])

    db.db['inquiries'].create_index([('status', 1), ('created_at', -1)])
    db.db['inquiries'].create_index('email')

    db.db['reviews'].create_index([('status', 1), ('created_at', -1)])

    db.db['journal_subscribers'].create_index('email', unique=True)

    db.db['messages'].create_index([('thread_id', 1), ('created_at', 1)])
    db.db['messages'].create_index([('sender', 1), ('read_by_admin', 1)])

    db.db['wishlists'].create_index('user_id', unique=True)

    db.db['categories'].create_index('name', unique=True)
    db.db['categories'].create_index('slug', unique=True)

    db.db['analytics_events'].create_index([('type', 1), ('created_at', -1)])
    db.db['analytics_events'].create_index('created_at')

    db.db['password_resets'].create_index('token', unique=True)
    db.db['password_resets'].create_index('expires_at', expireAfterSeconds=3600)

    log.info('[bootstrap] Indexes ensured')


def seed_super_admin(config):
    email = config['SUPER_ADMIN_EMAIL'].lower()
    if db.db['users'].find_one({'email': email}):
        return
    admin = User(
        email=email,
        name=config['SUPER_ADMIN_NAME'],
        role='super_admin',
    )
    admin.set_password(config['SUPER_ADMIN_PASSWORD'])
    db.db['users'].insert_one(admin.to_dict(include_password=True))
    log.info(f'[bootstrap] Super admin created: {email}')


def seed_categories():
    if db.db['categories'].count_documents({}) > 0:
        return
    defaults = [
        {'name': 'Oceanfront Villas', 'icon': 'fa-water', 'order': 1,
         'description': 'Cliffside and beachfront villas with direct ocean access.'},
        {'name': 'Penthouses', 'icon': 'fa-building', 'order': 2,
         'description': 'Metropolitan skyline residences with private elevators.'},
        {'name': 'Country Estates', 'icon': 'fa-tree', 'order': 3,
         'description': 'Vineyards, olive groves, and private acreage.'},
        {'name': 'Alpine Chalets', 'icon': 'fa-mountain-sun', 'order': 4,
         'description': 'Ski-in/ski-out mountain sanctuaries.'},
    ]
    for c in defaults:
        Category.create(c)
    log.info('[bootstrap] Default categories seeded')


def bootstrap_database(config):
    """Run once per app start."""
    ensure_indexes()
    seed_super_admin(config)
    seed_categories()