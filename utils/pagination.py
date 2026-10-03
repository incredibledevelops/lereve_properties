"""
Mongo-native pagination helpers.
"""
from flask import request


def get_page():
    try:
        page = int(request.args.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    return max(1, page)


def paginate_mongo(collection, query, sort, page, per_page=20, projection=None):
    """
    Returns a dict with items + pagination metadata.
    Uses Mongo skip/limit — no in-memory slicing.
    """
    total = collection.count_documents(query)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    skip = (page - 1) * per_page

    cursor = collection.find(query, projection).sort(sort).skip(skip).limit(per_page)
    items = list(cursor)

    return build_pagination(items, page, per_page, total, pages)


def build_pagination(items, page, per_page, total, pages=None):
    if pages is None:
        pages = max(1, (total + per_page - 1) // per_page)
    return {
        'items': items,
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'has_prev': page > 1,
        'has_next': page < pages,
    }