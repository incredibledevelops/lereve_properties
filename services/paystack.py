"""
============================================================
PAYSTACK WRAPPER
============================================================
"""
import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import requests
from flask import current_app


log = logging.getLogger(__name__)


def to_pesewas(amount_ghs):
    d = Decimal(str(amount_ghs)) * Decimal('100')
    return int(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def from_pesewas(amount_pesewas):
    return float(Decimal(str(amount_pesewas)) / Decimal('100'))


def generate_reference():
    return f"LR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def _headers():
    return {
        'Authorization': f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
        'Content-Type': 'application/json',
    }


def initialize_transaction(payload):
    url = f"{current_app.config['PAYSTACK_BASE_URL']}/transaction/initialize"
    try:
        resp = requests.post(url, json=payload, headers=_headers(), timeout=20)
        return resp.json()
    except requests.RequestException as e:
        log.exception('Paystack initialize network error')
        return {'status': False, 'message': str(e)}


def verify_transaction(reference):
    url = f"{current_app.config['PAYSTACK_BASE_URL']}/transaction/verify/{reference}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=20)
        return resp.json()
    except (requests.RequestException, ValueError):
        log.exception('Paystack verify failed')
        return None