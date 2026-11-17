"""
Gunicorn production configuration for NHT-SMS on Ubuntu VPS / Containers.
Northern Highways Transporters SACCO Management System.
"""

import multiprocessing
import os

# Server socket
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
backlog = 2048

# Worker processes
# Standard formula: 2 * CPU cores + 1
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
worker_connections = 1000
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
keepalive = 5

# Process management & recycling (mitigate memory fragmentation)
max_requests = 1000
max_requests_jitter = 50
preload_app = True
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" (%(D)s µs)'

# Security process naming
proc_name = "nht_sms_gunicorn"
