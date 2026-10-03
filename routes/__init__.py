"""
============================================================
ROUTES REGISTRY
============================================================
"""
from .auth     import auth_bp
from .client   import client_bp
from .admin    import admin_bp
from .api      import api_bp
from .paystack import paystack_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)                       # /, /stays, /why-us, /reviews, /contact, /login ...
    app.register_blueprint(client_bp,   url_prefix='/client')
    app.register_blueprint(admin_bp,    url_prefix='/admin')
    app.register_blueprint(api_bp,      url_prefix='/api')
    app.register_blueprint(paystack_bp, url_prefix='/paystack')