from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=200)])
    remember = BooleanField('Remember me')
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone', validators=[Length(max=40)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=200)])
    confirm = PasswordField('Confirm', validators=[DataRequired(), EqualTo('password')])
    agree = BooleanField('I agree', validators=[DataRequired()])
    submit = SubmitField('Create Account')


class ForgotForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    submit = SubmitField('Send Reset Link')


class ResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6, max=200)])
    confirm = PasswordField('Confirm', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')