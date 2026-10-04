"""
utils/uploads.py

Helpers for saving and deleting user-uploaded images.
Keeps filenames safe, enforces extensions and size, and returns
web-relative paths suitable for storing in Mongo.
"""
import logging
import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename


log = logging.getLogger(__name__)


# Canonical image extensions we accept for uploads.
# Used as a fallback when config doesn't define ALLOWED_IMAGE_EXTENSIONS.
DEFAULT_ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


# ============================================================
# INTERNAL HELPERS
# ============================================================
def _ext_ok(filename, allowed):
    """Return True if `filename` has an extension in `allowed`."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed


def _upload_root():
    """Absolute path to the configured upload root."""
    root = current_app.config.get('UPLOAD_FOLDER')
    if not root:
        # Fallback: <project_root>/static/uploads
        root = os.path.join(current_app.root_path, 'static', 'uploads')
    return Path(root)


def _resolve_allowed(allowed):
    """Resolve the allowed-extension set.

    Priority:
        1. Explicit `allowed` argument
        2. current_app.config['ALLOWED_IMAGE_EXTENSIONS']
        3. DEFAULT_ALLOWED_EXT module constant
    """
    if allowed:
        return allowed
    try:
        from_config = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS')
        if from_config:
            return set(from_config)
    except Exception:
        pass
    return DEFAULT_ALLOWED_EXT


def _resolve_max_bytes(max_bytes):
    """Resolve the per-file size cap in bytes."""
    if max_bytes:
        return max_bytes
    try:
        return current_app.config.get('MAX_CONTENT_LENGTH') or (8 * 1024 * 1024)
    except Exception:
        return 8 * 1024 * 1024


# ============================================================
# SINGULAR — save/delete one image
# ============================================================
def save_image(file_storage, subdir, allowed=None, max_bytes=None):
    """Save an uploaded image and return its web-relative path.

    Parameters
    ----------
    file_storage : werkzeug.datastructures.FileStorage
        The object from `request.files[...]` (i.e. `form.avatar.data`).
    subdir : str
        Subfolder under UPLOAD_FOLDER (e.g. "reviews", "properties").
    allowed : set[str] | None
        Allowed extensions; defaults to config ALLOWED_IMAGE_EXTENSIONS.
    max_bytes : int | None
        Hard size cap; defaults to config MAX_CONTENT_LENGTH or 8 MB.

    Returns
    -------
    str | None
        The web path like "/static/uploads/reviews/ab12cd34.jpg",
        or None if the upload was invalid or empty.
    """
    if file_storage is None:
        return None

    filename = getattr(file_storage, 'filename', None) or ''
    filename = filename.strip()
    if not filename:
        return None  # empty file input — no upload

    allowed = _resolve_allowed(allowed)
    if not _ext_ok(filename, allowed):
        log.warning('Upload rejected — bad extension: %s', filename)
        return None

    # Size check (best-effort — stream position may already be at end).
    max_bytes = _resolve_max_bytes(max_bytes)
    try:
        file_storage.stream.seek(0, os.SEEK_END)
        size = file_storage.stream.tell()
        file_storage.stream.seek(0)
        if size > max_bytes:
            log.warning('Upload rejected — too large: %s bytes', size)
            return None
    except Exception:
        # Stream may not support seek; skip the size check.
        pass

    # Safe unique filename.
    safe_base = secure_filename(filename) or 'upload'
    ext = safe_base.rsplit('.', 1)[1].lower() if '.' in safe_base else 'jpg'
    token = uuid.uuid4().hex[:16]
    new_name = f"{token}.{ext}"

    target_dir = _upload_root() / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / new_name

    try:
        file_storage.save(str(target_path))
    except Exception:
        log.exception('Failed to save upload to %s', target_path)
        return None

    # Web-relative path — matches where Flask serves static files.
    return f"/static/uploads/{subdir}/{new_name}"


def delete_image(web_path):
    """Delete a previously uploaded image.

    Silently ignores missing files or paths that aren't under our
    upload root (so we never accidentally delete arbitrary files).
    """
    if not web_path:
        return

    # Only touch files we know we wrote.
    prefix = '/static/uploads/'
    if not web_path.startswith(prefix):
        return

    rel = web_path[len(prefix):]
    # _upload_root() is <project>/static/uploads, so joining with
    # 'reviews/x.jpg' gives <project>/static/uploads/reviews/x.jpg.
    target = _upload_root() / rel

    try:
        if target.is_file():
            target.unlink()
    except Exception:
        log.exception('Failed to delete upload %s', target)


# ============================================================
# PLURAL — save/delete many images (used by the gallery upload)
# ============================================================
def save_images(file_storages, subdir, allowed=None, max_bytes=None, max_count=20):
    """Save a list of uploaded images.

    Used by the property form's multi-file gallery input.

    Parameters
    ----------
    file_storages : list[werkzeug.datastructures.FileStorage]
        The list from `form.gallery.data` (a `MultipleFileField`).
    subdir : str
        Subfolder under UPLOAD_FOLDER (e.g. "properties").
    allowed : set[str] | None
        Allowed extensions; defaults to config ALLOWED_IMAGE_EXTENSIONS.
    max_bytes : int | None
        Per-file size cap. Defaults to MAX_CONTENT_LENGTH.
    max_count : int
        Hard cap on how many images to accept in one call.

    Returns
    -------
    list[str]
        Web-relative paths of the images that were saved successfully.
        Empty list if none were valid or none were uploaded.
    """
    if not file_storages:
        return []

    saved = []
    for fs in file_storages[:max_count]:
        path = save_image(fs, subdir=subdir, allowed=allowed, max_bytes=max_bytes)
        if path:
            saved.append(path)
    return saved


def delete_images(web_paths):
    """Delete a list of previously uploaded images.

    Best-effort — missing files are silently ignored, and only paths
    under /static/uploads/ are ever touched.
    """
    if not web_paths:
        return
    for p in web_paths:
        delete_image(p)