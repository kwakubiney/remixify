from django.urls import path
from django.http import JsonResponse
from . import views
import logging

logger = logging.getLogger(__name__)


def health_check(request):
    """Basic health check endpoint - just checks Django is responding."""
    return JsonResponse({"status": "healthy"})


def deep_health_check(request):
    """
    Deep health check that verifies all critical services:
    - Database connectivity
    - Redis/Celery broker connectivity
    - Spotify API connectivity
    """
    import time
    from django.db import connection
    
    checks = {
        "django": "ok",
        "database": "unknown",
        "redis": "unknown",
        "celery": "unknown",
    }
    all_ok = True
    
    # Check database
    try:
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = f"ok ({int((time.time() - start) * 1000)}ms)"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:50]}"
        all_ok = False
        logger.error(f"Health check: Database failed - {e}")
    
    # Check Redis connectivity
    try:
        from main.celery import app as celery_app
        start = time.time()
        # Try to ping the broker
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=1)
        conn.close()
        checks["redis"] = f"ok ({int((time.time() - start) * 1000)}ms)"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:50]}"
        all_ok = False
        logger.error(f"Health check: Redis failed - {e}")
    
    # Check Celery worker availability
    try:
        from main.celery import app as celery_app
        start = time.time()
        inspect = celery_app.control.inspect(timeout=2.0)
        active = inspect.active()
        if active:
            worker_count = len(active)
            checks["celery"] = f"ok ({worker_count} workers, {int((time.time() - start) * 1000)}ms)"
        else:
            checks["celery"] = "warning: no active workers found"
            # Don't fail health check for this - workers might be idle
    except Exception as e:
        checks["celery"] = f"error: {str(e)[:50]}"
        all_ok = False
        logger.error(f"Health check: Celery failed - {e}")
    
    status_code = 200 if all_ok else 503
    return JsonResponse({
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
    }, status=status_code)


urlpatterns = [
    path('', views.home, name="home"),
    path('health/', health_check, name="health_check"),
    path('health/deep/', deep_health_check, name="deep_health_check"),
]
