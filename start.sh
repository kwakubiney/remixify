#!/usr/bin/env sh
set -e

# Default to prod settings if not provided
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-main.settings.prod_settings}
export PORT=${PORT:-8000}
export WEB_CONCURRENCY=${WEB_CONCURRENCY:-2}

# Run migrations (optional)
if [ "$RUN_MIGRATIONS" != "false" ]; then
  echo "Running migrations..."
  python manage.py migrate --noinput || echo "Migrations failed or DB unavailable; continuing"
fi

# Collect static at runtime
if [ "$SKIP_COLLECTSTATIC" = "true" ]; then
  echo "Skipping collectstatic"
else
  echo "Collecting static files..."
  python manage.py collectstatic --noinput || echo "collectstatic failed; continuing"
fi

# Start Gunicorn
echo "Starting Gunicorn on port $PORT..."
exec gunicorn main.wsgi:application --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY}
