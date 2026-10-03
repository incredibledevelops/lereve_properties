"""
============================================================
LE RÊVE PROPERTIES — APPLICATION FACTORY
============================================================
"""
import logging
import os
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import current_user

from config import get_config
from extensions import db, login_manager, csrf, limiter
from models import User
from utils import format_currency, format_date, relative_time
from routes import register_blueprints
from bootstrap import bootstrap_database


# ============================================================
# HELPERS — safe DB access for template context
# ============================================================
def _safe_load_categories():
    """
    Load categories for the global template context.
    Never raises — returns [] on any failure.
    This is what makes base.html's footer category loop safe
    on EVERY page (including /why-us, /contact, /admin/*).
    """
    logger = logging.getLogger(__name__)
    try:
        if db is None:
            return []
        mongo_db = getattr(db, 'db', None)
        if mongo_db is None:
            return []
        docs = list(mongo_db['categories'].find().sort('order', 1))
        out = []
        for c in docs:
            try:
                out.append({
                    'id':    str(c.get('_id', '')),
                    'name':  c.get('name') or '',
                    'slug':  c.get('slug') or '',
                    'icon':  c.get('icon') or 'fa-house-chimney',
                    'order': int(c.get('order') or 0),
                })
            except Exception:
                continue
        return out
    except Exception as e:
        logger.warning(f"[context] categories load failed: {e}")
        return []


# ============================================================
# APP FACTORY
# ============================================================
def create_app(config_name=None):
    app = Flask(__name__)
    config_class = get_config(config_name)
    app.config.from_object(config_class)

    # ---------- Logging ----------
    logging.basicConfig(
        level=getattr(logging, app.config['LOG_LEVEL'], logging.INFO),
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )
    app.logger.info(f"Starting {app.config['SITE_NAME']} on port {app.config['PORT']}")

    # ---------- Extensions ----------
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.login_message_category = 'info'
    limiter.init_app(app)
    limiter.storage_uri = app.config['RATELIMIT_STORAGE_URI']
    if not app.config['RATELIMIT_ENABLED']:
        limiter.enabled = False

    # ---------- User loader ----------
    @login_manager.user_loader
    def load_user(user_id):
        return User.find_by_id(user_id)

    # ---------- Blueprints ----------
    register_blueprints(app)

    # ---------- Template filters ----------
    @app.template_filter('format_currency')
    def _format_currency(value, symbol=None):
        return format_currency(value, symbol or app.config['DEFAULT_CURRENCY_SYMBOL'])

    @app.template_filter('format_date')
    def _format_date(value, fmt='%b %d, %Y'):
        return format_date(value, fmt)

    @app.template_filter('relative_time')
    def _relative_time(value):
        return relative_time(value)

    # ---------- Context processor ----------
    # IMPORTANT: 'categories' MUST be provided here, because
    # base.html's footer iterates it on EVERY page. Missing it
    # caused 500 errors on /why-us, /contact, etc.
    @app.context_processor
    def inject_globals():
        return {
            'SITE_NAME':        app.config['SITE_NAME'],
            'SITE_URL':         app.config['SITE_URL'],
            'PUBLIC_SITE_URL':  app.config['PUBLIC_SITE_URL'],
            'CURRENCY':         app.config['DEFAULT_CURRENCY'],
            'CURRENCY_SYMBOL':  app.config['DEFAULT_CURRENCY_SYMBOL'],
            'categories':       _safe_load_categories(),   # ← THE FIX
            'now':              datetime.now(timezone.utc),
            'current_year':     datetime.now(timezone.utc).year,
        }

    # ---------- Security headers ----------
    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=()',
        )
        if app.config['FLASK_ENV'] == 'production':
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        return response

    # ---------- Error handlers ----------
    @app.errorhandler(400)
    def err_400(e):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def err_403(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def err_404(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def err_429(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def err_500(e):
        # Log the FULL traceback so we can see exactly what broke
        import traceback
        app.logger.error("=" * 70)
        app.logger.error(f"500 ERROR on {request.path}")
        app.logger.error(traceback.format_exc())
        app.logger.error("=" * 70)
        return render_template('errors/500.html'), 500

    # ---------- SEO ----------
    @app.route('/robots.txt')
    def robots():
        from flask import make_response
        body = render_template('robots.txt')
        resp = make_response(body)
        resp.headers['Content-Type'] = 'text/plain'
        return resp

    @app.route('/sitemap.xml')
    def sitemap():
        from flask import make_response
        body = render_template('sitemap.xml')
        resp = make_response(body)
        resp.headers['Content-Type'] = 'application/xml'
        return resp

    @app.route('/healthz')
    def healthz():
        return jsonify({'status': 'ok', 'time': datetime.now(timezone.utc).isoformat()})

    # ---------- Boot ----------
    with app.app_context():
        try:
            bootstrap_database(app.config)
        except Exception as e:
            app.logger.warning(f'Bootstrap failed: {e}')

    return app


# ---------- WSGI ----------
app = create_app()


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=app.config['PORT'],
        debug=app.config['DEBUG'],
        use_reloader=app.config['DEBUG'],
    )