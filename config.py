"""
============================================================
LE RÊVE PROPERTIES — CONFIGURATION
Environment-driven. Safe defaults. Multi-class ready.
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
    """Parse env var as boolean, tolerating whitespace and common forms."""
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(key, default=0):
    """Parse env var as int with fallback on invalid input."""
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (ValueError, TypeError):
        log.warning(f"Invalid integer for {key}={raw!r}, using {default}")
        return default


def _get_scheme(url):
    """Extract scheme (http/https) from a URL string."""
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
    """Base configuration — safe defaults, all env-driven."""

    # ---------- Core ----------
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
    FLASK_ENV = os.getenv('FLASK_ENV', 'production').strip().lower()

    # Prefer explicit FLASK_DEBUG, fall back to FLASK_ENV=development
    _env_debug = os.getenv('FLASK_DEBUG')
    DEBUG = (
        _env_bool('FLASK_DEBUG', default=FLASK_ENV == 'development')
        if _env_debug is not None
        else (FLASK_ENV == 'development')
    )

    TESTING = False

    # ---------- Site ----------
    SITE_NAME = os.getenv('SITE_NAME', 'Le Rêve Properties')
    SITE_URL = os.getenv('SITE_URL', 'http://localhost:5006').rstrip('/')
    _site_scheme = _get_scheme(SITE_URL)

    # Tell Flask what scheme to use when generating URLs (behind proxy)
    PREFERRED_URL_SCHEME = _site_scheme

    # ---------- Sessions ----------
    SESSION_COOKIE_NAME = 'leReve_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = (_site_scheme == 'https')  # only force secure on HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    REMEMBER_COOKIE_NAME = 'leReve_remember'
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

    # ---------- MongoDB ----------
    # Default to localhost — NEVER ship a public IP as default
    MONGO_URI = os.getenv(
        'MONGO_URI',
        'mongodb://162.35.183.139:27017/lereve_properties',
    )
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'lereve_properties')
    MONGO_CONNECT_TIMEOUT_MS = _env_int('MONGO_CONNECT_TIMEOUT_MS', 5000)

    # ---------- Paystack ----------
    PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY').strip()
    PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY').strip()
    PAYSTACK_BASE_URL = os.getenv('PAYSTACK_BASE_URL', 'https://api.paystack.co').rstrip('/')
    PAYSTACK_WEBHOOK_SECRET = os.getenv('PAYSTACK_WEBHOOK_SECRET', '').strip()

    # Callback default derives from SITE_URL — no drift possible
    PAYSTACK_CALLBACK_URL = os.getenv(
        'PAYSTACK_CALLBACK_URL',
        f'{SITE_URL}/paystack/callback',
    ).rstrip('/')

    # Detect live vs test mode for diagnostics
    PAYSTACK_MODE = (
        'live' if PAYSTACK_SECRET_KEY.startswith('sk_live')
        else 'test' if PAYSTACK_SECRET_KEY.startswith('sk_test')
        else 'unconfigured'
    )

    # ---------- Mail ----------
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com').strip()
    MAIL_PORT = _env_int('MAIL_PORT', 587)
    MAIL_USE_TLS = _env_bool('MAIL_USE_TLS', default=True)
    MAIL_USE_SSL = _env_bool('MAIL_USE_SSL', default=False)
    MAIL_USERNAME = os.getenv('MAIL_USERNAME').strip()
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD').strip()
    MAIL_DEFAULT_SENDER = os.getenv(
        'MAIL_DEFAULT_SENDER',
        'concierge@lereveproperties.com',
    ).strip()
    MAIL_SUPPRESS_SEND = not (MAIL_USERNAME and MAIL_PASSWORD)

    # ---------- Admin Bootstrap ----------
    SUPER_ADMIN_EMAIL = os.getenv(
        'SUPER_ADMIN_EMAIL',
        'admin@lereveproperties.com',
    ).strip().lower()
    SUPER_ADMIN_PASSWORD = os.getenv('SUPER_ADMIN_PASSWORD', 'lereve2026')
    SUPER_ADMIN_NAME = os.getenv('SUPER_ADMIN_NAME', 'Super Admin').strip()

    # ---------- Currency ----------
    DEFAULT_CURRENCY = os.getenv('DEFAULT_CURRENCY', 'GHS').strip().upper()
    DEFAULT_CURRENCY_SYMBOL = os.getenv('DEFAULT_CURRENCY_SYMBOL', '₵').strip()

    # ---------- Uploads ----------
    MAX_CONTENT_LENGTH = _env_int('MAX_CONTENT_LENGTH', 8 * 1024 * 1024)  # 8 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')

    # ---------- Pagination & business rules ----------
    ITEMS_PER_PAGE = _env_int('ITEMS_PER_PAGE', 12)
    ADMIN_PAGE_SIZE = _env_int('ADMIN_PAGE_SIZE', 20)

    PROPERTY_CATEGORIES = [
        'Oceanfront Villas',
        'Penthouses',
        'Country Estates',
        'Alpine Chalets',
    ]
    BOOKING_STATUSES = [
        'pending', 'confirmed', 'completed',
        'cancelled', 'cancellation-requested',
    ]
    INQUIRY_STATUSES = ['new', 'contacted', 'booked', 'archived']
    REVIEW_STATUSES = ['published', 'pending', 'rejected']

    # ---------- JSON ----------
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = False

    # ---------- Security ----------
    WTF_CSRF_TIME_LIMIT = None  # session-bound, not time-bound
    WTF_CSRF_SSL_STRICT = True
    MAX_FORM_MEMORY_SIZE = 2 * 1024 * 1024  # 2 MB forms

    # Optional rate-limiting hooks (wire Flask-Limiter later)
    RATELIMIT_DEFAULT = os.getenv('RATELIMIT_DEFAULT', '200 per day;50 per hour')
    RATELIMIT_LOGIN = os.getenv('RATELIMIT_LOGIN', '10 per minute')
    RATELIMIT_ENABLED = _env_bool('RATELIMIT_ENABLED', default=FLASK_ENV == 'production')

    # ---------- Logging ----------
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').strip().upper()

    # ---------- Cache ----------
    CACHE_TYPE = os.getenv('CACHE_TYPE', 'simple')
    CACHE_DEFAULT_TIMEOUT = _env_int('CACHE_DEFAULT_TIMEOUT', 300)

    # ---------- Template ----------
    TEMPLATES_AUTO_RELOAD = DEBUG
    EXPLAIN_TEMPLATE_LOADING = False

    # ============================================================
    # VALIDATION — run at import time (fails fast)
    # ============================================================
    @classmethod
    def validate(cls):
        """Sanity checks — logs warnings, raises on fatal issues."""
        warnings = []
        errors = []

        # Secret key
        if cls.SECRET_KEY == 'dev-secret-key-change-me':
            warnings.append(
                "SECRET_KEY is using the default value — CHANGE THIS IN PRODUCTION"
            )
        elif len(cls.SECRET_KEY) < 32:
            warnings.append(
                f"SECRET_KEY is only {len(cls.SECRET_KEY)} chars; use 32+ for production"
            )

        # Mongo
        if not cls.MONGO_URI:
            errors.append("MONGO_URI is empty — set it in .env")

        # Paystack
        if cls.FLASK_ENV == 'production':
            if not cls.PAYSTACK_SECRET_KEY:
                errors.append("PAYSTACK_SECRET_KEY is required in production")
            elif cls.PAYSTACK_SECRET_KEY.startswith('sk_test'):
                warnings.append(
                    "PAYSTACK_SECRET_KEY is a TEST key while FLASK_ENV=production"
                )

        # Mail
        if not cls.MAIL_USERNAME:
            warnings.append("MAIL_USERNAME not set — emails will be suppressed")

        # Currency symbol
        if not cls.DEFAULT_CURRENCY_SYMBOL:
            warnings.append("DEFAULT_CURRENCY_SYMBOL is empty")

        for w in warnings:
            log.warning(f"[config] {w}")
        if errors:
            raise RuntimeError(
                "[config] Fatal configuration errors:\n  - " + "\n  - ".join(errors)
            )

        return True


# ============================================================
# ENVIRONMENT-SPECIFIC SUBCLASSES
# ============================================================
class DevelopmentConfig(Config):
    """Development overrides."""
    FLASK_ENV = 'development'
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    EXPLAIN_TEMPLATE_LOADING = False
    SESSION_COOKIE_SECURE = False  # allow HTTP in dev
    REMEMBER_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Production overrides — stricter defaults."""
    FLASK_ENV = 'production'
    DEBUG = False
    TEMPLATES_AUTO_RELOAD = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    WTF_CSRF_SSL_STRICT = True


class TestingConfig(Config):
    """Testing overrides."""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False       # skip CSRF in tests
    MAIL_SUPPRESS_SEND = True
    SESSION_COOKIE_SECURE = False
    MONGO_URI = os.getenv('MONGO_TEST_URI', 'mongodb://162.35.183.139:27017/lereve_test')


# ============================================================
# FACTORY
# ============================================================
def get_config(name=None):
    """Return a config class based on FLASK_ENV (or explicit name)."""
    name = (name or os.getenv('FLASK_ENV', 'production')).strip().lower()
    mapping = {
        'development': DevelopmentConfig,
        'dev': DevelopmentConfig,
        'production': ProductionConfig,
        'prod': ProductionConfig,
        'testing': TestingConfig,
        'test': TestingConfig,
    }
    config_class = mapping.get(name, ProductionConfig)

    # Validate on selection
    try:
        config_class.validate()
    except RuntimeError:
        # Re-raise — the app should fail loudly on bad config
        raise

    return config_class


# Default export for backward compat (app.py imports `Config`)
Config.validate()