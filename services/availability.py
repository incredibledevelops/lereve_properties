"""
Date overlap logic — checks if a property is bookable for a range.
"""
from datetime import datetime


def parse_date(s):
    if not s:
        return None
    if isinstance(s, datetime):
        return s.date()
    try:
        return datetime.fromisoformat(str(s)[:10]).date()
    except (ValueError, TypeError):
        return None


def calculate_nights(check_in, check_out):
    ci = parse_date(check_in)
    co = parse_date(check_out)
    if not ci or not co:
        return 0
    return max(0, (co - ci).days)


def is_valid_range(check_in, check_out, min_nights=1, max_nights=90):
    nights = calculate_nights(check_in, check_out)
    if nights < min_nights or nights > max_nights:
        return False, f'Stay must be between {min_nights} and {max_nights} nights.'
    return True, ''