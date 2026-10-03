from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, TextAreaField,
    SelectField, IntegerField, FloatField, DecimalField, SubmitField,
)
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange, URL


def _category_choices():
    try:
        from models import Category
        names = Category.names()
        if not names:
            return [('', 'No categories — add one first')]
        return [(n, n) for n in names]
    except Exception:
        return [('', 'Categories unavailable')]


class PropertyForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    category = SelectField('Category', validators=[DataRequired()], choices=[])
    location = StringField('Location', validators=[DataRequired(), Length(max=200)])
    original_price = DecimalField('Original Price (GHS)', validators=[DataRequired(), NumberRange(min=0)])
    price = DecimalField('Member Price (GHS)', validators=[DataRequired(), NumberRange(min=0)])
    beds = IntegerField('Beds', validators=[DataRequired(), NumberRange(min=1)])
    baths = FloatField('Baths', validators=[DataRequired(), NumberRange(min=1)])
    guests = IntegerField('Guests', validators=[DataRequired(), NumberRange(min=1)])
    rating = FloatField('Rating', validators=[Optional(), NumberRange(min=0, max=5)], default=5.0)
    reviews_count = IntegerField('Reviews Count', validators=[Optional(), NumberRange(min=0)], default=0)
    image = StringField('Main Image URL', validators=[DataRequired(), URL(), Length(max=500)])
    gallery = TextAreaField('Gallery URLs (one per line)', validators=[Optional()])
    amenities = StringField('Amenities (comma-separated)', validators=[Optional(), Length(max=500)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=3000)])
    submit = SubmitField('Save Property')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category.choices = _category_choices()


class CategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=80)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    icon = StringField('Icon', validators=[Optional(), Length(max=80)], default='fa-house-chimney')
    order = IntegerField('Display Order', validators=[Optional(), NumberRange(min=0)], default=0)
    submit = SubmitField('Save Category')


class AdminReviewForm(FlaskForm):
    name = StringField('Guest Name', validators=[DataRequired(), Length(min=2, max=120)])
    property = StringField('Property', validators=[DataRequired(), Length(min=2, max=200)])
    rating = SelectField(
        'Rating',
        choices=[(str(i), f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)],
        default='5', validators=[DataRequired()],
    )
    text = TextAreaField('Review', validators=[DataRequired(), Length(min=10, max=2000)])
    avatar = StringField('Avatar URL', validators=[Optional(), Length(max=500)])
    status = SelectField(
        'Status',
        choices=[
            ('pending', 'Pending'),
            ('published', 'Published'),
            ('rejected', 'Rejected'),
        ],
        default='published', validators=[DataRequired()],
    )
    submit = SubmitField('Save Review')


class SettingsForm(FlaskForm):
    site_name = StringField('Site Name', validators=[DataRequired(), Length(max=120)])
    contact_email = StringField('Contact Email', validators=[DataRequired(), Email(), Length(max=200)])
    whatsapp = StringField('WhatsApp', validators=[Optional(), Length(max=40)])
    instagram = StringField('Instagram', validators=[Optional(), Length(max=60)])
    submit = SubmitField('Save Settings')


class UserEditForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone', validators=[Optional(), Length(max=40)])
    country = StringField('Country', validators=[Optional(), Length(max=100)])
    tier = SelectField('Tier', choices=[(t, t) for t in ('Silver', 'Gold', 'Platinum', 'Black')])
    role = SelectField('Role', choices=[('client', 'Client'), ('super_admin', 'Super Admin')])
    is_active = BooleanField('Active')
    new_password = PasswordField('New Password (leave blank to keep)', validators=[Optional(), Length(min=6, max=200)])
    submit = SubmitField('Save User')


class UserCreateForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone', validators=[Optional(), Length(max=40)])
    country = StringField('Country', validators=[Optional(), Length(max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=200)])
    tier = SelectField('Tier', choices=[(t, t) for t in ('Silver', 'Gold', 'Platinum', 'Black')])
    role = SelectField('Role', choices=[('client', 'Client'), ('super_admin', 'Super Admin')])
    submit = SubmitField('Create User')