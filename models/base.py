"""
============================================================
SHARED MONGO HELPERS
============================================================
"""
import logging
import re
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId


log = logging.getLogger(__name__)


def utcnow():
    """Timezone-aware UTC datetime (Python 3.12 compatible)."""
    return datetime.now(timezone.utc)


def safe_oid(value):
    """Convert value to ObjectId or return None."""
    if isinstance(value, ObjectId):
        return value
    if not value:
        return None
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError, ValueError):
        return None


def oid_to_str(doc):
    """Recursively stringify ObjectIds and ISO-format datetimes."""
    if not doc:
        return doc
    if isinstance(doc, list):
        return [oid_to_str(d) for d in doc]
    if isinstance(doc, dict):
        out = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                out[k] = str(v)
                if k == '_id':
                    out['id'] = str(v)
            elif isinstance(v, datetime):
                out[k] = v.isoformat()
            elif isinstance(v, (list, dict)):
                out[k] = oid_to_str(v)
            else:
                out[k] = v
        return out
    return doc


def strip_internal_keys(data):
    """Remove keys starting with underscore (defensive)."""
    return {k: v for k, v in (data or {}).items() if not k.startswith('_')}


def safe_sort_cursor(cursor, sort_spec, fallback=None):
    try:
        return cursor.sort(sort_spec)
    except Exception:
        log.warning(f'Sort failed ({sort_spec}); falling back')
        return cursor.sort(fallback or [('_id', -1)])


def slugify(text):
    text = (text or '').strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-') or 'item'