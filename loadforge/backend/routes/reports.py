import os
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from loadforge.backend.db.database import get_db, timed_query
from loadforge.backend.services.optimizer import cache_get, cache_set, analyze_query

router = APIRouter()

USE_CACHE = os.getenv("USE_CACHE", "false").lower() == "true"


@router.get("/report")
def get_report(tenant_id: int = Query(...), db: Session = Depends(get_db)):
    cache_key = f"report:{tenant_id}"

    if USE_CACHE:
        cached = cache_get(cache_key)
        if cached:
            cached["cache_hit"] = True
            return cached

    # Heavy aggregation query - intentionally slow
    rows, elapsed_ms = timed_query(
        db,
        """
        SELECT
            DATE_TRUNC('day', t.created_at) AS day,
            t.status,
            COUNT(t.id) AS txn_count,
            SUM(t.amount) AS total_amount,
            AVG(t.amount) AS avg_amount,
            COUNT(DISTINCT e.id) AS event_count
        FROM transactions t
        LEFT JOIN events e
            ON e.tenant_id = t.tenant_id
            AND DATE_TRUNC('day', e.timestamp) = DATE_TRUNC('day', t.created_at)
        WHERE t.tenant_id = :tid
        GROUP BY DATE_TRUNC('day', t.created_at), t.status
        ORDER BY day DESC
        LIMIT 30
        """,
        {"tid": tenant_id},
    )

    analyze_query("heavy_report", elapsed_ms, tenant_id)

    data = [
        {
            "day": str(r[0]),
            "status": r[1],
            "txn_count": r[2],
            "total_amount": float(r[3] or 0),
            "avg_amount": float(r[4] or 0),
            "event_count": r[5],
        }
        for r in rows
    ]

    result = {
        "tenant_id": tenant_id,
        "report": data,
        "rows": len(data),
        "query_time_ms": round(elapsed_ms, 2),
        "cache_hit": False,
        "cache_active": USE_CACHE,
    }

    if USE_CACHE:
        cache_set(cache_key, result, ttl=60)

    return result
