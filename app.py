"""
============================================================
LE RÊVE PROPERTIES — APPLICATION ENTRY POINT
============================================================
"""
import logging
import os
from datetime import datetime, timezone

from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect

from config import Config
from models import (
    db,
    User,
    Category,
    Property,
    Review,
)
from auth import auth_bp, login_manager
from routes import public_bp
from client import client_bp
from super_admin import super_admin_bp
from paystack import paystack_bp


# Global CSRF protector — initialized in create_app
csrf = CSRFProtect()


# ============================================================
# APP FACTORY
# ============================================================
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ---------- Logging ----------
    logging.basicConfig(
        level=logging.INFO if not app.config['DEBUG'] else logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )
    app.logger.info(
        f"Starting {app.config['SITE_NAME']} in {app.config['FLASK_ENV']} mode"
    )

    # ---------- Mongo ----------
    db.init_app(app)

    # ---------- CSRF ----------
    csrf.init_app(app)

    # ---------- Login Manager ----------
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.login_message_category = 'info'

    # ---------- Blueprints ----------
    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(client_bp, url_prefix='/client')
    app.register_blueprint(super_admin_bp, url_prefix='/super-admin')
    app.register_blueprint(paystack_bp, url_prefix='/paystack')

    # Exempt Paystack webhook — uses HMAC signature instead of CSRF
    csrf.exempt('paystack.webhook')

    # ============================================================
    # TEMPLATE FILTERS
    # ============================================================
    @app.template_filter('relative_time')
    def relative_time(value):
        """Convert ISO string or datetime to 'a moment ago' style."""
        if not value:
            return '—'
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, datetime):
                dt = value
            else:
                return str(value)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            diff = (now - dt).total_seconds()

            if diff < 0:
                diff = abs(diff)
                if diff < 60:
                    return 'in a moment'
                if diff < 3600:
                    m = int(diff // 60)
                    return f'in {m} min'
                if diff < 86400:
                    h = int(diff // 3600)
                    return f'in {h} hr'
                if diff < 604800:
                    d = int(diff // 86400)
                    return f'in {d} day{"s" if d != 1 else ""}'
                return dt.strftime('%b %d, %Y')

            if diff < 60:
                return 'just now'
            if diff < 3600:
                m = int(diff // 60)
                return f'{m} min ago' if m != 1 else '1 min ago'
            if diff < 86400:
                h = int(diff // 3600)
                return f'{h} hr ago' if h != 1 else '1 hr ago'
            if diff < 604800:
                d = int(diff // 86400)
                return f'{d} day{"s" if d != 1 else ""} ago'
            if diff < 2592000:  # ~30 days
                w = int(diff // 604800)
                return f'{w} week{"s" if w != 1 else ""} ago'
            return dt.strftime('%b %d, %Y')
        except Exception:
            return str(value)

    @app.template_filter('format_date')
    def format_date(value, fmt='%b %d, %Y'):
        """Format a datetime or ISO string as a readable date."""
        if not value:
            return '—'
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            elif isinstance(value, datetime):
                dt = value
            else:
                return str(value)
            return dt.strftime(fmt)
        except Exception:
            return str(value)

    @app.template_filter('format_currency')
    def format_currency(value, symbol=None):
        """Format a number as GHS currency."""
        sym = symbol or app.config.get('DEFAULT_CURRENCY_SYMBOL', '₵')
        try:
            return f"{sym}{float(value or 0):,.2f}"
        except (TypeError, ValueError):
            return f"{sym}0.00"

    # ---------- Context Processors ----------
    @app.context_processor
    def inject_globals():
        return {
            'SITE_NAME': app.config['SITE_NAME'],
            'CURRENCY': app.config['DEFAULT_CURRENCY'],
            'CURRENCY_SYMBOL': app.config['DEFAULT_CURRENCY_SYMBOL'],
            'now': datetime.now(timezone.utc),
            # NOTE: PROPERTY_CATEGORIES removed — categories are now DB-driven
            # and injected per-route via the `categories` context variable.
        }

    # ---------- Error Handlers ----------
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception('Internal server error')
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/404.html'), 403

    # ---------- Bootstrap ----------
    with app.app_context():
        bootstrap_database(app)

    return app


# ============================================================
# BOOTSTRAP — seed super-admin, demo client, default categories
# (single, canonical definition — no duplicate!)
# ============================================================
def bootstrap_database(app):
    """
    Ensure indexes + super-admin + demo client + default categories.

    Properties and reviews are intentionally NOT seeded — the platform
    is fully dynamic: admins add properties, users/admins add reviews.
    """
    try:
        # ---------- Indexes ----------
        db.db['users'].create_index('email', unique=True)
        db.db['properties'].create_index([('category', 1), ('price', 1)])
        db.db['properties'].create_index([('created_at', -1)])
        db.db['bookings'].create_index([('user_id', 1), ('created_at', -1)])
        db.db['bookings'].create_index('payment_reference', sparse=True)
        db.db['inquiries'].create_index([('status', 1), ('created_at', -1)])
        db.db['inquiries'].create_index('email')
        db.db['reviews'].create_index([('status', 1), ('created_at', -1)])
        db.db['journal_subscribers'].create_index('email', unique=True)
        db.db['messages'].create_index([('user_id', 1), ('timestamp', 1)])
        db.db['wishlists'].create_index('user_id', unique=True)
        db.db['categories'].create_index('name', unique=True)
        db.db['categories'].create_index('slug', unique=True)
        db.db['categories'].create_index('order')
        app.logger.info('[bootstrap] Mongo indexes ensured.')

        # ---------- Super admin ----------
        existing_admin = db.db['users'].find_one(
            {'email': app.config['SUPER_ADMIN_EMAIL'].lower()}
        )
        if not existing_admin:
            admin = User(
                email=app.config['SUPER_ADMIN_EMAIL'],
                name=app.config['SUPER_ADMIN_NAME'],
                role='super_admin',
            )
            admin.set_password(app.config['SUPER_ADMIN_PASSWORD'])
            db.db['users'].insert_one(admin.to_dict())
            app.logger.info(
                f"[bootstrap] Super admin created: {app.config['SUPER_ADMIN_EMAIL']}"
            )

        # ---------- Demo client ----------
        demo = db.db['users'].find_one({'email': 'guest@lereve.com'})
        if not demo:
            demo_user = User(
                email='guest@lereve.com',
                name='Alexandra Whitmore',
                phone='+233 30 000 0000',
                country='Ghana',
                bio='Frequent traveler seeking architectural sanctuaries and quiet luxury.',
                role='client',
                tier='Gold',
            )
            demo_user.set_password('guest2026')
            db.db['users'].insert_one(demo_user.to_dict())
            app.logger.info(
                "[bootstrap] Demo client created: guest@lereve.com / guest2026"
            )

        # ---------- Default categories (only if empty) ----------
        if db.db['categories'].count_documents({}) == 0:
            defaults = [
                {
                    'name': 'Oceanfront Villas',
                    'icon': 'fa-water',
                    'order': 1,
                    'description': 'Cliffside and beachfront villas with direct ocean access.',
                },
                {
                    'name': 'Penthouses',
                    'icon': 'fa-building',
                    'order': 2,
                    'description': 'Metropolitan skyline residences with private elevators.',
                },
                {
                    'name': 'Country Estates',
                    'icon': 'fa-tree',
                    'order': 3,
                    'description': 'Vineyards, olive groves, and private acreage.',
                },
                {
                    'name': 'Alpine Chalets',
                    'icon': 'fa-mountain-sun',
                    'order': 4,
                    'description': 'Ski-in/ski-out mountain sanctuaries.',
                },
            ]
            for c in defaults:
                cid = Category.create(c)
                if not cid:
                    app.logger.warning(
                        f"[bootstrap] Failed to seed category: {c['name']}"
                    )
            app.logger.info('[bootstrap] Default categories seeded.')

        # NOTE: No default properties or reviews — the platform is fully dynamic.

    except Exception as e:
        app.logger.warning(f'[bootstrap] Warning: {e}')
        app.logger.warning(
            '[bootstrap] Is MongoDB running? Check MONGO_URI in .env'
        )


# ---------- WSGI entrypoint ----------
app = create_app()


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5006))  # matches .env PAYSTACK_CALLBACK_URL
    app.run(
        host='0.0.0.0',
        port=port,
        debug=app.config['DEBUG'],
        use_reloader=app.config['DEBUG'],
    )