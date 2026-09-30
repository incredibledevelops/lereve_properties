"""
============================================================
LE RÊVE PROPERTIES — MAILER
SMTP-based transactional email. HTML templates are inline
for zero-dependency simplicity. All user-supplied data is
HTML-escaped before injection.
============================================================
"""
import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app


log = logging.getLogger(__name__)


# ============================================================
# HELPERS
# ============================================================
_TAG_RE = re.compile(r'<[^<]+?>')


def _strip_html(html: str) -> str:
    """Crude HTML → text fallback for email clients without HTML support."""
    return _TAG_RE.sub('', html or '')


def _safe(value) -> str:
    """Escape HTML-sensitive characters in user-provided strings."""
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


def _fmt_currency(amount, symbol: str = '₵') -> str:
    """Format a number as GHS currency."""
    try:
        return f"{symbol}{float(amount or 0):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"


def _send(to: str, subject: str, html: str, text: str = None) -> bool:
    """
    Send an HTML (with plain-text fallback) email via SMTP.

    Returns:
        True if sent, False otherwise (never raises).
    """
    cfg = current_app.config

    # --- Guards -------------------------------------------------
    if not to:
        log.warning('Mailer: empty recipient — skipping send.')
        return False

    if cfg.get('MAIL_SUPPRESS_SEND'):
        log.info(f'Mailer: suppressed send to {to} (MAIL_SUPPRESS_SEND=True)')
        return False

    if not cfg.get('MAIL_USERNAME') or not cfg.get('MAIL_PASSWORD'):
        log.warning('Mailer: not configured (missing MAIL_USERNAME/PASSWORD) — skipping send.')
        return False

    # --- Build message ------------------------------------------
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = cfg.get('MAIL_DEFAULT_SENDER', 'concierge@lereveproperties.com')
    msg['To'] = to
    msg.attach(MIMEText(text or _strip_html(html), 'plain'))
    msg.attach(MIMEText(html, 'html'))

    # --- Send ---------------------------------------------------
    try:
        server_cls = smtplib.SMTP_SSL if cfg.get('MAIL_USE_SSL') else smtplib.SMTP
        with server_cls(cfg['MAIL_SERVER'], cfg['MAIL_PORT'], timeout=20) as server:
            if cfg.get('MAIL_USE_TLS') and not cfg.get('MAIL_USE_SSL'):
                server.starttls()
            server.login(cfg['MAIL_USERNAME'], cfg['MAIL_PASSWORD'])
            server.send_message(msg)
        return True
    except Exception:
        log.exception(f'Mailer: failed to send to {to} (subject: {subject!r})')
        return False


# ============================================================
# HTML WRAPPER
# ============================================================
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
    © 2026 Le Rêve Properties — Private &amp; Confidential Hospitality
  </div>
</div></body></html>
"""


def _wrap(content: str) -> str:
    return _WRAP.format(content=content)


# ============================================================
# PUBLIC SENDERS
# ============================================================
def send_inquiry_notification(data: dict) -> bool:
    """
    Notify the super admin that a new guest inquiry has been submitted.
    """
    admin = current_app.config.get('SUPER_ADMIN_EMAIL')
    if not admin:
        log.warning('Mailer: SUPER_ADMIN_EMAIL not configured — cannot send inquiry alert.')
        return False

    html = _wrap(f"""
        <h2 style="font-family:Georgia,serif;color:#1a3a2a;margin:0 0 12px;">New Confidential Inquiry</h2>
        <p style="font-size:14px;line-height:1.7;">
            <strong>{_safe(data.get('name'))}</strong> has submitted an inquiry.<br>
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

    subject = f"New Inquiry — {data.get('property') or 'General'}"
    return _send(admin, subject, html)


def send_journal_welcome(email: str) -> bool:
    """
    Welcome email after subscribing to the private journal.
    """
    html = _wrap("""
        <h2 style="font-family:Georgia,serif;color:#1a3a2a;margin:0 0 12px;">Welcome to the Private Journal</h2>
        <p style="font-size:14px;line-height:1.7;">
            You now have access to off-market luxury listings before public release.
            Watch your inbox for curated estates, member-only pricing, and seasonal privileges.
        </p>
    """)
    return _send(email, 'Welcome to Le Rêve Journal', html)


def send_booking_confirmation(email: str, booking: dict) -> bool:
    """
    Send booking confirmation after a successful Paystack payment.
    """
    if not email or not booking:
        log.warning('Mailer: booking confirmation skipped — missing email or booking data.')
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

    subject = f"Reservation Confirmed — {booking.get('property') or 'Your Stay'}"
    return _send(email, subject, html)