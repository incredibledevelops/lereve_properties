"""
============================================================
MAILER — async SMTP
============================================================
"""
import logging
import re
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


log = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='mailer')


_TAG_RE = re.compile(r'<[^<]+?>')


def _strip_html(html):
    return _TAG_RE.sub('', html or '')


def _safe(value):
    if value is None:
        return '—'
    return (
        str(value)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;')
    )


def _sanitize_subject(s):
    """Strip header-injection characters from subjects."""
    return re.sub(r'[\r\n]+', ' ', str(s or ''))[:200]


def _fmt_currency(amount, symbol='₵'):
    try:
        return f"{symbol}{float(amount or 0):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"


_WRAP = """
<!doctype html>
<html><body style="margin:0;background:#f7f3ed;font-family:Inter,Arial,sans-serif;color:#2c2c2a;">
<div style="max-width:600px;margin:32px auto;background:#fff;border:1px solid #c9a84c33;border-radius:20px;overflow:hidden;">
  <div style="background:#1a3a2a;padding:28px 32px;color:#c9a84c;">
    <div style="font-family:Georgia,serif;font-size:22px;letter-spacing:4px;">LE RÊVE</div>
    <div style="font-size:11px;letter-spacing:4px;text-transform:uppercase;color:#c9a84c;opacity:.7;">Properties</div>
  </div>
  <div style="padding:32px;">{content}</div>
  <div style="background:#f7f3ed;padding:20px 32px;font-size:11px;color:#2c2c2a99;text-align:center;">
    © 2026 Le Rêve Properties
  </div>
</div></body></html>
"""


def _wrap(content):
    return _WRAP.format(content=content)


def _send_sync(to, subject, html, text=None):
    cfg = current_app.config
    if not to:
        return False
    if cfg.get('MAIL_SUPPRESS_SEND'):
        log.info(f'Mailer suppressed: {to}')
        return False
    if not cfg.get('MAIL_USERNAME') or not cfg.get('MAIL_PASSWORD'):
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = _sanitize_subject(subject)
    msg['From'] = cfg.get('MAIL_DEFAULT_SENDER', 'concierge@lereveproperties.com')
    msg['To'] = to
    msg.attach(MIMEText(text or _strip_html(html), 'plain'))
    msg.attach(MIMEText(html, 'html'))

    try:
        server_cls = smtplib.SMTP_SSL if cfg.get('MAIL_USE_SSL') else smtplib.SMTP
        with server_cls(cfg['MAIL_SERVER'], cfg['MAIL_PORT'], timeout=20) as server:
            if cfg.get('MAIL_USE_TLS') and not cfg.get('MAIL_USE_SSL'):
                server.starttls()
            server.login(cfg['MAIL_USERNAME'], cfg['MAIL_PASSWORD'])
            server.send_message(msg)
        return True
    except Exception:
        log.exception(f'Mailer failed to send to {to}')
        return False


def send_async(to, subject, html, text=None):
    _executor.submit(_send_sync, to, subject, html, text)


# ============================================================
# HIGH-LEVEL SENDERS
# ============================================================
def send_inquiry_notification(data):
    admin = current_app.config.get('SUPER_ADMIN_EMAIL')
    if not admin:
        return False
    html = _wrap(f"""
        <h2 style="font-family:Georgia,serif;color:#1a3a2a;margin:0 0 12px;">New Confidential Inquiry</h2>
        <p style="font-size:14px;line-height:1.7;">
            <strong>{_safe(data.get('name'))}</strong><br>
            <strong>Email:</strong> {_safe(data.get('email'))}<br>
            <strong>Phone:</strong> {_safe(data.get('phone'))}<br>
            <strong>Property:</strong> {_safe(data.get('property'))}<br>
            <strong>Dates:</strong> {_safe(data.get('check_in'))} → {_safe(data.get('check_out'))}<br>
            <strong>Guests:</strong> {_safe(data.get('guests'))}<br>
        </p>
        <p style="font-size:14px;line-height:1.7;background:#f7f3ed;padding:14px;border-radius:12px;white-space:pre-wrap;">
            {_safe(data.get('message')) or 'No additional notes.'}
        </p>
    """)
    send_async(admin, f"New Inquiry — {_sanitize_subject(data.get('property') or 'General')}", html)


def send_journal_welcome(email):
    html = _wrap("""
        <h2 style="font-family:Georgia,serif;color:#1a3a2a;margin:0 0 12px;">Welcome to the Private Journal</h2>
        <p style="font-size:14px;line-height:1.7;">
            You now have access to off-market luxury listings before public release.
        </p>
    """)
    send_async(email, 'Welcome to Le Rêve Journal', html)


def send_booking_confirmation(email, booking):
    if not email or not booking:
        return False
    html = _wrap(f"""
        <h2 style="font-family:Georgia,serif;color:#1a3a2a;margin:0 0 12px;">Reservation Confirmed</h2>
        <p style="font-size:14px;line-height:1.7;">
            <strong>{_safe(booking.get('property'))}</strong><br>
            {_safe(booking.get('location'))}<br><br>
            <strong>Check-In:</strong> {_safe(booking.get('check_in'))}<br>
            <strong>Check-Out:</strong> {_safe(booking.get('check_out'))}<br>
            <strong>Guests:</strong> {_safe(booking.get('guests'))}<br>
            <strong>Total:</strong> {_fmt_currency(booking.get('total'))}<br>
            <strong>Confirmation:</strong> {_safe(booking.get('confirmation_id'))}
        </p>
    """)
    send_async(email, f"Reservation Confirmed — {_sanitize_subject(booking.get('property') or 'Your Stay')}", html)


def send_password_reset(email, token, base_url):
    reset_url = f"{base_url}/auth/reset?token={token}"
    html = _wrap(f"""
        <h2 style="font-family:Georgia,serif;color:#1a3a2a;margin:0 0 12px;">Reset Your Password</h2>
        <p style="font-size:14px;line-height:1.7;">
            Click the link below to reset your password. This link expires in 1 hour.
        </p>
        <p style="text-align:center;margin:24px 0;">
            <a href="{_safe(reset_url)}" style="background:#1a3a2a;color:#c9a84c;padding:14px 28px;text-decoration:none;border-radius:12px;font-weight:bold;">
                Reset Password
            </a>
        </p>
        <p style="font-size:12px;color:#2c2c2a99;">
            If you didn't request this, you can safely ignore this email.
        </p>
    """)
    send_async(email, 'Reset Your Le Rêve Password', html)


def send_new_message_notification(admin_email, client_name, preview):
    html = _wrap(f"""
        <h2 style="font-family:Georgia,serif;color:#1a3a2a;margin:0 0 12px;">New Concierge Message</h2>
        <p style="font-size:14px;line-height:1.7;">
            <strong>{_safe(client_name)}</strong> sent you a message:<br><br>
            <em>"{_safe(preview)}"</em>
        </p>
        <p style="font-size:14px;">
            <a href="{current_app.config['SITE_URL']}/admin/messages" style="color:#c9a84c;">
                View in Admin Inbox →
            </a>
        </p>
    """)
    send_async(admin_email, f"New message from {_sanitize_subject(client_name)}", html)