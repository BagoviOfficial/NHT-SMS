# ==============================================================================
# NHT-SMS DOCKERFILE — PRODUCTION CONTAINER SPECIFICATION
# Northern Highways Transporters SACCO Management System
# ==============================================================================

FROM python:3.15-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# Install essential system dependencies and security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user and group (Least Privilege)
RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --shell /bin/bash --create-home appuser

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements/production.txt

# Copy application source code
COPY . /app/

# Ensure directories for static and private/public media exist with correct permissions
RUN mkdir -p /app/staticfiles /app/media/public /app/media/private /app/backups && \
    chown -R appuser:appgroup /app && \
    chmod +x /app/docker/entrypoint.sh /app/scripts/*.sh

# Switch to non-root execution
USER appuser

# Expose internal WSGI application port
EXPOSE 8000

# Docker healthcheck against active liveness probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live/ || exit 1

# Entrypoint manages database readiness, migrations, and static collection
ENTRYPOINT ["/app/docker/entrypoint.sh"]

# Default command launches production Gunicorn server
CMD ["gunicorn", "-c", "/app/docker/gunicorn.conf.py", "nht_sacco.config.wsgi:application"]
