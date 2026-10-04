"""
============================================================
FORMS — public API
============================================================
Re-exports every form class so callers can do:

    from forms import PropertyForm, AdminReviewForm, ...

The actual definitions live in submodules.
"""
from .auth_forms import LoginForm, RegisterForm, ForgotForm, ResetForm
from .client_forms import ProfileForm, PreferencesForm, ChangePasswordForm
from .admin_forms import (
    PropertyForm, CategoryForm, AdminReviewForm,
    SettingsForm, UserEditForm, UserCreateForm,
)


__all__ = [
    'LoginForm', 'RegisterForm', 'ForgotForm', 'ResetForm',
    'ProfileForm', 'PreferencesForm', 'ChangePasswordForm',
    'PropertyForm', 'CategoryForm', 'AdminReviewForm',
    'SettingsForm', 'UserEditForm', 'UserCreateForm',
]