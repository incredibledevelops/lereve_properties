"""
============================================================
LE RÊVE PROPERTIES — AUTHENTICATION
============================================================
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from models import User, db
from forms import LoginForm, RegisterForm

login_manager = LoginManager()
auth_bp = Blueprint('auth', __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.find_by_id(user_id)


# ============================================================
# UNIFIED LOGIN (client + admin)
# ============================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        user = User.find_by_email(form.email.data)
        if not user or not user.check_password(form.password.data):
            flash('Invalid email or password.', 'error')
            return render_template('auth/login.html', form=form)

        if not user.is_active:
            flash('Your account has been deactivated.', 'error')
            return render_template('auth/login.html', form=form)

        login_user(user, remember=form.remember.data)
        session.permanent = True
        flash(f'Welcome back, {user.name.split(" ")[0]}!', 'success')

        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return _redirect_by_role(user)

    return render_template('auth/login.html', form=form)


def _redirect_by_role(user):
    if user.is_admin:
        return redirect(url_for('super_admin.dashboard'))
    return redirect(url_for('client.dashboard'))


# ============================================================
# REGISTER (client only)
# ============================================================
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    form = RegisterForm()
    if form.validate_on_submit():
        if User.find_by_email(form.email.data):
            flash('An account with that email already exists.', 'error')
            return render_template('auth/register.html', form=form)

        user = User(
            email=form.email.data,
            name=form.name.data,
            phone=form.phone.data or '',
            role='client',
            tier='Silver',
        )
        user.set_password(form.password.data)
        db.db[User.collection].insert_one(user.to_dict())
        flash('Account created. Welcome to Le Rêve.', 'success')

        created = User.find_by_email(form.email.data)
        login_user(created)
        return redirect(url_for('client.dashboard'))

    return render_template('auth/register.html', form=form)


# ============================================================
# LOGOUT
# ============================================================
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('public.home'))