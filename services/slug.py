import re


def slugify(text):
    text = (text or '').strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-') or 'item'