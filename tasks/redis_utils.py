"""
Redis utilities for Remixify.
Uses the same Redis instance as Celery (Upstash).
"""
import os
import redis
from decouple import config
from django.conf import settings


def get_redis_client():
    """Get a Redis client using the same URL as Celery."""
    redis_url = getattr(settings, 'CELERY_BROKER_URL', None) or \
                os.environ.get('REDIS_URL') or \
                config('REDIS_URL', default='redis://localhost:6379/0')
    return redis.from_url(redis_url)


PLAYLIST_COUNT_KEY = "remixify:playlist_count"


def get_playlist_count():
    """
    Get the current playlist count from Redis.
    """
    client = get_redis_client()
    count = client.get(PLAYLIST_COUNT_KEY)
    return int(count) if count else 0


def increment_playlist_count():
    """
    Increment the playlist count in Redis.
    Returns the new count.
    """
    client = get_redis_client()
    return client.incr(PLAYLIST_COUNT_KEY)
