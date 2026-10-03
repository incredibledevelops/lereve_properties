"""
Gunicorn configuration for Le Rêve Properties.
"""
import multiprocessing
import os

bind = f"127.0.0.1:{os.getenv('PORT', '5007')}"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 60
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

accesslog = 'logs/access.log'
errorlog = 'logs/error.log'
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

proc_name = 'lereve'
preload_app = True