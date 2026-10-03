"""
Helpers to track analytics events from routes.
"""
from flask import request
from flask_login import current_user

from models import AnalyticsEvent


def track(event_type, payload=None, user_id=None):
    try:
        uid = user_id
        if uid is None and current_user.is_authenticated:
            uid = current_user.id
        AnalyticsEvent.track(
            event_type=event_type,
            payload=payload or {},
            user_id=uid,
            ip=request.remote_addr,
            ua=request.headers.get('User-Agent', ''),
        )
    except Exception:
        pass