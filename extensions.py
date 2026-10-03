"""
============================================================
LE RÊVE PROPERTIES — FLASK EXTENSIONS
Single source of truth for extension singletons.
============================================================
"""
from flask_pymongo import PyMongo
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


db = PyMongo()
login_manager = LoginManager()
csrf = CSRFProtect()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri='memory://',
    headers_enabled=True,
)