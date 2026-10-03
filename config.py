"""
============================================================
LE RÊVE PROPERTIES — CONFIGURATION
Environment-driven. Fail-fast validation. Production-safe.
============================================================
"""
import logging
import os
from datetime import timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================
def _env_bool(key, default=False):
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(key, default=0):
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (ValueError, TypeError):
        log.warning(f"Invalid integer for {key}={raw!r}, using {default}")
        return default


def _env_str(key, default=''):
    raw = os.getenv(key)
    return (raw or default).strip()


def _get_scheme(url):
    if not url:
        return 'http'
    try:
        return urlparse(url).scheme or 'http'
    except Exception:
        return 'http'


# ============================================================
# BASE CONFIG
# ============================================================
class Config:
    # ---------- Core ----------
    SECRET_KEY = _env_str('SECRET_KEY', 'dev-secret-key-change-me')
    FLASK_ENV = _env_str('FLASK_ENV', 'production').lower()
    DEBUG = _env_bool('FLASK_DEBUG', default=FLASK_ENV == 'development')
    TESTING = False

    # ---------- Site ----------
    SITE_NAME = _env_str('SITE_NAME', 'Le Rêve Properties')
    SITE_URL = _env_str('SITE_URL', 'https://lereve-properties.com').rstrip('/')
    PUBLIC_SITE_URL = _env_str('PUBLIC_SITE_URL', 'https://lereve-properties.com').rstrip('/')
    PREFERRED_URL_SCHEME = _get_scheme(SITE_URL)
    PORT = _env_int('PORT', 5007)

    # ---------- Sessions ----------
    SESSION_COOKIE_NAME = 'lereve_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = (PREFERRED_URL_SCHEME == 'https')
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_NAME = 'lereve_remember'
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # ---------- MongoDB ----------
    MONGO_URI = _env_str('MONGO_URI')
    MONGO_DB_NAME = _env_str('MONGO_DB_NAME')
    MONGO_CONNECT_TIMEOUT_MS = _env_int('MONGO_CONNECT_TIMEOUT_MS')

    # ---------- Paystack ----------
    PAYSTACK_SECRET_KEY = _env_str('PAYSTACK_SECRET_KEY')
    PAYSTACK_PUBLIC_KEY = _env_str('PAYSTACK_PUBLIC_KEY')
    PAYSTACK_BASE_URL = _env_str('PAYSTACK_BASE_URL', 'https://api.paystack.co').rstrip('/')
    PAYSTACK_WEBHOOK_SECRET = _env_str('PAYSTACK_WEBHOOK_SECRET', '')
    PAYSTACK_CALLBACK_URL = _env_str(
        'PAYSTACK_CALLBACK_URL',
        f'{SITE_URL}/paystack/callback',
    ).rstrip('/')
    PAYSTACK_MODE = (
        'live' if PAYSTACK_SECRET_KEY.startswith('sk_live')
        else 'test' if PAYSTACK_SECRET_KEY.startswith('sk_test')
        else 'unconfigured'
    )

    # ---------- Mail ----------
    MAIL_SERVER = _env_str('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = _env_int('MAIL_PORT', 587)
    MAIL_USE_TLS = _env_bool('MAIL_USE_TLS', default=True)
    MAIL_USE_SSL = _env_bool('MAIL_USE_SSL', default=False)
    MAIL_USERNAME = _env_str('MAIL_USERNAME', '')
    MAIL_PASSWORD = _env_str('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = _env_str('MAIL_DEFAULT_SENDER', 'concierge@lereve-properties.com')
    MAIL_SUPPRESS_SEND = not (MAIL_USERNAME and MAIL_PASSWORD)

    # ---------- Super Admin ----------
    SUPER_ADMIN_EMAIL = _env_str('SUPER_ADMIN_EMAIL', 'admin@lereve-properties.com').lower()
    SUPER_ADMIN_PASSWORD = _env_str('SUPER_ADMIN_PASSWORD', 'lereve2026')
    SUPER_ADMIN_NAME = _env_str('SUPER_ADMIN_NAME', 'Super Admin')

    # ---------- Currency ----------
    DEFAULT_CURRENCY = _env_str('DEFAULT_CURRENCY', 'GHS').upper()
    DEFAULT_CURRENCY_SYMBOL = _env_str('DEFAULT_CURRENCY_SYMBOL', '₵')

    # ---------- Pagination ----------
    ITEMS_PER_PAGE = _env_int('ITEMS_PER_PAGE', 12)
    ADMIN_PAGE_SIZE = _env_int('ADMIN_PAGE_SIZE', 20)

    # ---------- Business rules ----------
    MAX_BOOKING_NIGHTS = 90
    MIN_BOOKING_NIGHTS = 1
    BOOKING_STATUSES = [
        'pending', 'confirmed', 'completed',
        'cancelled', 'cancellation-requested',
    ]
    INQUIRY_STATUSES = ['new', 'contacted', 'booked', 'archived']
    REVIEW_STATUSES = ['published', 'pending', 'rejected']
    USER_TIERS = ['Silver', 'Gold', 'Platinum', 'Black']
    USER_ROLES = ['client', 'super_admin']

    # ---------- JSON ----------
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = False

    # ---------- Security ----------
    WTF_CSRF_TIME_LIMIT = None
    WTF_CSRF_SSL_STRICT = True
    MAX_CONTENT_LENGTH = _env_int('MAX_CONTENT_LENGTH', 8 * 1024 * 1024)

    # ---------- Rate Limiting ----------
    RATELIMIT_ENABLED = _env_bool('RATELIMIT_ENABLED', default=True)
    RATELIMIT_STORAGE_URI = _env_str('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_DEFAULT = '300 per day;100 per hour'
    RATELIMIT_LOGIN = '10 per minute'
    RATELIMIT_REGISTER = '5 per hour'
    RATELIMIT_INQUIRY = '10 per hour'
    RATELIMIT_API = '120 per minute'

    # ---------- Analytics ----------
    ANALYTICS_TRACK_SECRET = _env_str('ANALYTICS_TRACK_SECRET')

    # ---------- Logging ----------
    LOG_LEVEL = _env_str('LOG_LEVEL', 'INFO').upper()

    # ---------- Templates ----------
    TEMPLATES_AUTO_RELOAD = DEBUG
    EXPLAIN_TEMPLATE_LOADING = False

    # ============================================================
    # VALIDATION
    # ============================================================
    @classmethod
    def validate(cls):
        warnings, errors = [], []

        if cls.SECRET_KEY == 'dev-secret-key-change-me':
            errors.append("SECRET_KEY is using the default value")
        elif len(cls.SECRET_KEY) < 32:
            warnings.append(f"SECRET_KEY is only {len(cls.SECRET_KEY)} chars; use 32+")

        if not cls.MONGO_URI:
            errors.append("MONGO_URI is empty")

        if cls.FLASK_ENV == 'production':
            if not cls.PAYSTACK_SECRET_KEY:
                errors.append("PAYSTACK_SECRET_KEY is required in production")
            elif cls.PAYSTACK_SECRET_KEY.startswith('sk_test'):
                warnings.append("PAYSTACK_SECRET_KEY is a TEST key while FLASK_ENV=production")
            if cls.SUPER_ADMIN_PASSWORD == 'lereve2026':
                errors.append("SUPER_ADMIN_PASSWORD is still the default — change it in .env")
            if cls.SITE_URL.startswith('http://'):
                errors.append("SITE_URL must be HTTPS in production")

        if not cls.MAIL_USERNAME:
            warnings.append("MAIL_USERNAME not set — emails will be suppressed")

        for w in warnings:
            log.warning(f"[config] {w}")
        if errors:
            raise RuntimeError(
                "[config] Fatal configuration errors:\n  - " + "\n  - ".join(errors)
            )
        return True


class DevelopmentConfig(Config):
    FLASK_ENV = 'development'
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    FLASK_ENV = 'production'
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    WTF_CSRF_SSL_STRICT = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    MAIL_SUPPRESS_SEND = True
    SESSION_COOKIE_SECURE = False
    RATELIMIT_ENABLED = False
    MONGO_URI = _env_str('MONGO_TEST_URI', 'mongodb://localhost:27017/lereve_test')


def get_config(name=None):
    name = (name or os.getenv('FLASK_ENV', 'production')).strip().lower()
    mapping = {
        'development': DevelopmentConfig, 'dev': DevelopmentConfig,
        'production': ProductionConfig,  'prod': ProductionConfig,
        'testing': TestingConfig,        'test': TestingConfig,
    }
    config_class = mapping.get(name, ProductionConfig)
    config_class.validate()
    return config_class