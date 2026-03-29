import os
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from loadforge.backend.db.database import get_db, timed_query
from loadforge.backend.services.optimizer import cache_get, cache_set, analyze_query

router = APIRouter()

USE_CACHE = os.getenv("USE_CACHE", "false").lower() == "true"
USE_INDEXES = os.getenv("USE_INDEXES", "false").lower() == "true"


@router.get("/dashboard")
def get_dashboard(tenant_id: int = Query(...), db: Session = Depends(get_db)):
    cache_key = f"dashboard:{tenant_id}"

    # Try cache first
    if USE_CACHE:
        cached = cache_get(cache_key)
        if cached:
            cached["cache_hit"] = True
            return cached

    # Total transactions (no index = full table scan)
    total_rows, t1 = timed_query(
        db,
        "SELECT COUNT(*) FROM transactions WHERE tenant_id = :tid",
        {"tid": tenant_id},
    )
    total_transactions = total_rows[0][0]

    # Last 7 days stats
    stats_rows, t2 = timed_query(
        db,
        """
        SELECT status, COUNT(*), SUM(amount)
        FROM transactions
        WHERE tenant_id = :tid
          AND created_at >= NOW() - INTERVAL '7 days'
        GROUP BY status
        """,
        {"tid": tenant_id},
    )

    # Event counts
    event_rows, t3 = timed_query(
        db,
        "SELECT type, COUNT(*) FROM events WHERE tenant_id = :tid GROUP BY type",
        {"tid": tenant_id},
    )

    total_ms = t1 + t2 + t3
    analyze_query("dashboard", total_ms, tenant_id)

    result = {
        "tenant_id": tenant_id,
        "total_transactions": total_transactions,
        "last_7_days": [
            {"status": r[0], "count": r[1], "total_amount": float(r[2] or 0)}
            for r in stats_rows
        ],
        "event_counts": [{"type": r[0], "count": r[1]} for r in event_rows],
        "query_time_ms": round(total_ms, 2),
        "cache_hit": False,
        "indexes_active": USE_INDEXES,
        "cache_active": USE_CACHE,
    }

    if USE_CACHE:
        cache_set(cache_key, result, ttl=30)

    return result
