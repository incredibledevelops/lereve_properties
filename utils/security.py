"""
Security helpers — open-redirect protection, CSRF-safe URL checks.
"""
from urllib.parse import urlparse, urljoin

from flask import request, redirect


def is_safe_url(target):
    """Only allow same-host relative or absolute URLs."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def safe_redirect(target, fallback_endpoint='auth.login'):
    from flask import url_for
    if target and is_safe_url(target):
        return redirect(target)
    return redirect(url_for(fallback_endpoint))