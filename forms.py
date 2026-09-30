"""
============================================================
LE RÊVE PROPERTIES — WTForms
All forms used by public, client, and admin routes.
Category choices are loaded dynamically from the database.
============================================================
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    TextAreaField, SelectField, IntegerField, FloatField, DecimalField,
    DateField,
)
from wtforms.validators import (
    DataRequired, Email, Length, Optional, NumberRange, EqualTo, URL,
)


def _category_choices():
    """Fetch dynamic category names from MongoDB."""
    try:
        from models import Category
        names = Category.names()
        if not names:
            return [('', 'No categories — add one in admin')]
        return [(n, n) for n in names]
    except Exception:
        return [('', 'Categories unavailable')]


# ============================================================
# AUTH
# ============================================================
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=200)])
    remember = BooleanField('Remember me')
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone', validators=[Optional(), Length(max=40)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=200)])
    confirm = PasswordField('Confirm', validators=[DataRequired(), EqualTo('password')])
    agree = BooleanField('I agree to the Terms of Privilege', validators=[DataRequired()])
    submit = SubmitField('Create Account')


class ChangePasswordForm(FlaskForm):
    current = PasswordField('Current Password', validators=[DataRequired()])
    new = PasswordField('New Password', validators=[DataRequired(), Length(min=6, max=200)])
    confirm = PasswordField('Confirm', validators=[DataRequired(), EqualTo('new')])
    submit = SubmitField('Update Password')


# ============================================================
# PROPERTY (admin-only)
# ============================================================
class PropertyForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    category = SelectField(
        'Category',
        validators=[DataRequired()],
        choices=[],  # populated dynamically in __init__
    )
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


# ============================================================
# INQUIRY (public)
# ============================================================
class InquiryForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone', validators=[Optional(), Length(max=40)])
    property = StringField('Estate of Interest', validators=[Optional(), Length(max=200)])
    check_in = DateField('Check-In', validators=[Optional()])
    check_out = DateField('Check-Out', validators=[Optional()])
    guests = SelectField('Guests', choices=[
        ('1-2 Guests', '1-2 Guests'),
        ('3-5 Guests', '3-5 Guests'),
        ('6-10 Guests', '6-10 Guests'),
        ('10+ Guests', '10+ Guests (Private Charter)'),
    ])
    message = TextAreaField('Special Requests', validators=[Optional(), Length(max=2000)])
    submit = SubmitField('Submit Confidential Reservation Request')


# ============================================================
# REVIEW — PUBLIC & ADMIN
# ============================================================
class ReviewForm(FlaskForm):
    """Public review submission (moderated)."""
    name = StringField('Your Name', validators=[DataRequired(), Length(min=2, max=120)])
    property = StringField('Property', validators=[DataRequired(), Length(min=2, max=200)])
    rating = SelectField(
        'Rating',
        choices=[(str(i), f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)],
        default='5',
        validators=[DataRequired()],
    )
    text = TextAreaField('Review', validators=[DataRequired(), Length(min=10, max=2000)])
    avatar = StringField('Avatar URL', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Submit Review')


class AdminReviewForm(FlaskForm):
    """Admin review form (bypasses moderation)."""
    name = StringField('Guest Name', validators=[DataRequired(), Length(min=2, max=120)])
    property = StringField(
        'Property / Location',
        validators=[DataRequired(), Length(min=2, max=200)],
        description='e.g. The Royal Azure Villa • Amalfi',
    )
    rating = SelectField(
        'Rating',
        choices=[(str(i), f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)],
        default='5',
        validators=[DataRequired()],
    )
    text = TextAreaField('Review Text', validators=[DataRequired(), Length(min=10, max=2000)])
    avatar = StringField('Avatar URL', validators=[Optional(), Length(max=500)])
    status = SelectField(
        'Publication Status',
        choices=[
            ('pending', 'Pending (requires approval)'),
            ('published', 'Published (live immediately)'),
            ('rejected', 'Rejected (hidden)'),
        ],
        default='published',
        validators=[DataRequired()],
    )
    submit = SubmitField('Save Review')


# ============================================================
# CATEGORY (admin)
# ============================================================
class CategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=80)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    icon = StringField(
        'Icon (Font Awesome class)',
        validators=[Optional(), Length(max=80)],
        default='fa-house-chimney',
    )
    order = IntegerField('Display Order', validators=[Optional(), NumberRange(min=0)], default=0)
    submit = SubmitField('Save Category')


# ============================================================
# JOURNAL
# ============================================================
class JournalForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    submit = SubmitField('Subscribe')


# ============================================================
# PROFILE / PREFERENCES
# ============================================================
class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=200)])
    phone = StringField('Phone', validators=[Optional(), Length(max=40)])
    country = StringField('Country', validators=[Optional(), Length(max=100)])
    bio = TextAreaField('Bio / Travel Notes', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Save Changes')


class PreferencesForm(FlaskForm):
    type = SelectField('Preferred Estate Type', choices=[])
    diet = StringField('Dietary Requirements', validators=[Optional(), Length(max=300)])
    amenities = StringField('Preferred Amenities (comma-separated)', validators=[Optional(), Length(max=500)])
    newsletter = BooleanField('Private Journal Newsletter')
    sms = BooleanField('SMS Alerts')
    promo = BooleanField('Seasonal Promotions')
    submit = SubmitField('Save Preferences')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.type.choices = _category_choices()


# ============================================================
# SETTINGS
# ============================================================
class SettingsForm(FlaskForm):
    site_name = StringField('Site Name', validators=[DataRequired(), Length(max=120)])
    contact_email = StringField('Contact Email', validators=[DataRequired(), Email(), Length(max=200)])
    whatsapp = StringField('WhatsApp Number', validators=[Optional(), Length(max=40)])
    instagram = StringField('Instagram Handle', validators=[Optional(), Length(max=60)])
    submit = SubmitField('Save Settings')