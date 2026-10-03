from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, TextAreaField,
    SelectField, SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, EqualTo


def _category_choices():
    try:
        from models import Category
        names = Category.names()
        if not names:
            return [('', 'No categories available')]
        return [(n, n) for n in names]
    except Exception:
        return [('', 'Categories unavailable')]


class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone', validators=[Length(max=40)])
    country = StringField('Country', validators=[Length(max=100)])
    bio = TextAreaField('Bio', validators=[Length(max=1000)])
    submit = SubmitField('Save Changes')


class PreferencesForm(FlaskForm):
    type = SelectField('Preferred Estate Type', choices=[])
    diet = StringField('Dietary Requirements', validators=[Length(max=300)])
    amenities = StringField('Preferred Amenities', validators=[Length(max=500)])
    newsletter = BooleanField('Newsletter')
    sms = BooleanField('SMS Alerts')
    promo = BooleanField('Seasonal Promotions')
    submit = SubmitField('Save Preferences')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type.choices = _category_choices()


class ChangePasswordForm(FlaskForm):
    current = PasswordField('Current Password', validators=[DataRequired()])
    new = PasswordField('New Password', validators=[DataRequired(), Length(min=6, max=200)])
    confirm = PasswordField('Confirm', validators=[DataRequired(), EqualTo('new')])
    submit = SubmitField('Update Password')