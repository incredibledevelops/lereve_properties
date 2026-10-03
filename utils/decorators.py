"""
Role-based access decorators.
"""
from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper


def client_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.is_admin:
            flash('Client access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper