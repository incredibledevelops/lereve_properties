# Le Rêve Properties — Portal

Client portal & admin console for **lereve-properties.com**.

## Stack
- Flask 3 · MongoDB (PyMongo) · Paystack · Gmail SMTP
- Deploy: **gunicorn + nginx + systemd**
- Python 3.12 · Port **5007**

## Directory
app.py # App factory
wsgi.py # Gunicorn entry
config.py # Env-driven config
extensions.py # Flask extensions
bootstrap.py # DB indexes + seeding
models/ # Mongo models
services/ # Mailer, Paystack, Analytics
routes/ # auth / client / admin / paystack / api
forms/ # WTForms
utils/ # Decorators, pagination, formatting
templates/ # Jinja2 (base, auth, client, admin, errors)
static/ # CSS + JS
logs/ # Gunicorn logs
tests/ # Pytest smoke tests


## Setup
```bash
git clone <repo> && cd lereve-properties
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: SECRET_KEY, MONGO_URI, PAYSTACK_*, MAIL_*, SUPER_ADMIN_*

python app.py          # http://localhost:5007

[Unit]
Description=Le Rêve Properties (gunicorn)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/lereve-properties
Environment="PATH=/var/www/lereve-properties/venv/bin"
ExecStart=/var/www/lereve-properties/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target





server {
    listen 80;
    server_name lereve-properties.com www.lereve-properties.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name lereve-properties.com www.lereve-properties.com;

    ssl_certificate     /etc/letsencrypt/live/lereve-properties.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lereve-properties.com/privkey.pem;

    client_max_body_size 10M;

    location /static/ {
        alias /var/www/lereve-properties/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:5007;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}


sudo systemctl daemon-reload
sudo systemctl enable --now lereve
sudo ln -s /etc/nginx/sites-available/lereve-properties.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

fetch('https://lereve-properties.com/api/track', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Track-Secret': 'YOUR_ANALYTICS_TRACK_SECRET'
  },
  body: JSON.stringify({
    type: 'page_view',
    payload: { url: location.pathname }
  })
});






---

## ✅ Summary

**Total files: 91** across all 9 parts.

**To run locally:**
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your MONGO_URI, SECRET_KEY, PAYSTACK keys, MAIL creds, and admin password
python app.py
