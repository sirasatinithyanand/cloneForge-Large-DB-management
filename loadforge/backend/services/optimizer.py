import json
import logging
import time
from typing import Optional
from loadforge.backend.db.database import redis_client, REDIS_AVAILABLE

logger = logging.getLogger(__name__)

SLOW_QUERY_THRESHOLD_MS = 500


def cache_get(key: str) -> Optional[dict]:
    if not REDIS_AVAILABLE or redis_client is None:
        return None
    try:
        data = redis_client.get(key)
        return json.loads(data) if data else None
    except Exception as e:
        logger.warning(f"Cache GET failed for {key}: {e}")
        return None


def cache_set(key: str, value: dict, ttl: int = 30):
    if not REDIS_AVAILABLE or redis_client is None:
        return
    try:
        redis_client.setex(key, ttl, json.dumps(value, default=str))
    except Exception as e:
        logger.warning(f"Cache SET failed for {key}: {e}")


def analyze_query(query_name: str, elapsed_ms: float, tenant_id: int):
    """Log slow queries and suggest optimizations."""
    if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
        logger.warning(
            f"[SLOW QUERY] {query_name} took {elapsed_ms:.1f}ms for tenant={tenant_id}. "
            f"Suggestion: Add index on (tenant_id, created_at) or enable Redis cache."
        )
    else:
        logger.info(f"[QUERY OK] {query_name} took {elapsed_ms:.1f}ms for tenant={tenant_id}")
