from __future__ import absolute_import, unicode_literals
import os
import logging
from celery import Celery
from celery.signals import task_failure, task_retry, worker_ready, worker_shutdown
from django.conf import settings
from decouple import config

logger = logging.getLogger(__name__)

# Use prod_settings as fallback for production deployments (Fly.io sets REMIXIFY=prod)
# In development, explicitly set DJANGO_SETTINGS_MODULE=main.settings.dev_settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.prod_settings")
app = Celery("main" ,)
app.config_from_object("django.conf.settings", namespace="CELERY")

app.autodiscover_tasks()


@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, **kw):
    """Log and report task failures to Sentry."""
    import sentry_sdk
    
    # Filter out expected user input errors
    if isinstance(exception, ValueError):
        error_msg = str(exception).lower()
        user_input_errors = [
            "playlist is private or doesn't exist",
            "spotify-generated playlist",
            "authentication error",
            "access denied",
            "unable to load this playlist",
            "too many requests",
            "something went wrong",
            "original playlist not found",
        ]
        if any(err in error_msg for err in user_input_errors):
            logger.warning(
                f"Celery task failed (user input error): {sender.name if sender else 'unknown'} "
                f"(task_id={task_id}) - {exception}"
            )
            return  # Don't report to Sentry
    
    logger.error(
        f"Celery task failed: {sender.name if sender else 'unknown'} "
        f"(task_id={task_id}) - {exception}"
    )
    
    # Capture to Sentry with context
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("celery_task", sender.name if sender else "unknown")
        scope.set_tag("task_id", task_id)
        scope.set_context("celery", {
            "task_name": sender.name if sender else "unknown",
            "task_id": task_id,
            "args": str(args)[:500] if args else None,
            "kwargs": str(kwargs)[:500] if kwargs else None,
        })
        sentry_sdk.capture_exception(exception)


@task_retry.connect
def handle_task_retry(sender=None, request=None, reason=None, **kw):
    """Log task retries."""
    logger.warning(
        f"Celery task retrying: {sender.name if sender else 'unknown'} "
        f"(task_id={request.id if request else 'unknown'}) - {reason}"
    )


@worker_ready.connect
def handle_worker_ready(sender=None, **kw):
    """Log when a worker comes online."""
    import sentry_sdk
    logger.info(f"Celery worker ready: {sender}")
    sentry_sdk.capture_message(f"Celery worker started: {sender}", level="info")


@worker_shutdown.connect
def handle_worker_shutdown(sender=None, **kw):
    """Log when a worker shuts down."""
    import sentry_sdk
    logger.warning(f"Celery worker shutting down: {sender}")
    sentry_sdk.capture_message(f"Celery worker shutdown: {sender}", level="warning")


@app.task(bind=True)
def debug_task(self):
    print(f"Request : {self.request!r}")