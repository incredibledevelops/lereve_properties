"""
Formatting helpers for templates and JSON output.
"""
from datetime import datetime, timezone


def format_currency(value, symbol='₵'):
    try:
        return f"{symbol}{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"


def format_date(value, fmt='%b %d, %Y'):
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


def relative_time(value):
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
            if diff < 60: return 'in a moment'
            if diff < 3600: return f'in {int(diff // 60)} min'
            if diff < 86400: return f'in {int(diff // 3600)} hr'
            if diff < 604800: return f'in {int(diff // 86400)} day(s)'
            return dt.strftime('%b %d, %Y')

        if diff < 60: return 'just now'
        if diff < 3600: return f'{int(diff // 60)} min ago'
        if diff < 86400: return f'{int(diff // 3600)} hr ago'
        if diff < 604800: return f'{int(diff // 86400)} day(s) ago'
        if diff < 2592000: return f'{int(diff // 604800)} week(s) ago'
        return dt.strftime('%b %d, %Y')
    except Exception:
        return str(value)