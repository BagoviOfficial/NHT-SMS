#!/bin/sh
set -e

# ==============================================================================
# NHT-SMS DOCKER CONTAINER ENTRYPOINT SCRIPT
# Northern Highways Transporters SACCO Management System
# ==============================================================================

echo "=== [NHT-SMS] Initializing Application Container ==="

# Wait for PostgreSQL database readiness if DATABASE_URL or DB_HOST is set
if [ -n "$DB_HOST" ]; then
    DB_PORT=${DB_PORT:-5432}
    echo "Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."
    while ! nc -z "$DB_HOST" "$DB_PORT"; do
        sleep 1
    done
    echo "PostgreSQL is reachable."
fi

# Run database migrations automatically when starting web service
if [ "$1" = 'gunicorn' ] || [ "$1" = 'runserver' ]; then
    echo "Applying database schema migrations..."
    python manage.py migrate --noinput

    echo "Collecting static assets into staticfiles root..."
    python manage.py collectstatic --noinput --clear
fi

echo "=== [NHT-SMS] Starting Command: $@ ==="
exec "$@"
