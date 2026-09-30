"""
============================================================
LE RÊVE PROPERTIES — SEED DATA
============================================================
Empty by design.

The platform is fully dynamic:
  • Properties are added by admins via /super-admin/properties/new
  • Categories are managed via /super-admin/categories
  • Reviews come from the public form (moderated) or admins

Nothing is hardcoded. `bootstrap_database()` seeds only the
super-admin user + default categories.
============================================================
"""

# Kept as empty lists for backward compatibility with
# `from seeds import DEFAULT_PROPERTIES, DEFAULT_REVIEWS`
DEFAULT_PROPERTIES = []
DEFAULT_REVIEWS = []