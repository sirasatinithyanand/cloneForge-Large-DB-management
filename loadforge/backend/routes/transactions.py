from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from loadforge.backend.db.database import get_db, timed_query
from loadforge.backend.services.optimizer import analyze_query

router = APIRouter()


@router.get("/transactions")
def search_transactions(
    tenant_id: int = Query(...),
    status: Optional[str] = Query(None),
    cursor: Optional[int] = Query(None, description="Last seen transaction ID for cursor pagination"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    params = {"tid": tenant_id, "limit": limit}

    if status and cursor:
        query = """
            SELECT id, tenant_id, amount, status, created_at
            FROM transactions
            WHERE tenant_id = :tid AND status = :status AND id > :cursor
            ORDER BY id
            LIMIT :limit
        """
        params["status"] = status
        params["cursor"] = cursor
    elif status:
        query = """
            SELECT id, tenant_id, amount, status, created_at
            FROM transactions
            WHERE tenant_id = :tid AND status = :status
            ORDER BY id
            LIMIT :limit
        """
        params["status"] = status
    elif cursor:
        query = """
            SELECT id, tenant_id, amount, status, created_at
            FROM transactions
            WHERE tenant_id = :tid AND id > :cursor
            ORDER BY id
            LIMIT :limit
        """
        params["cursor"] = cursor
    else:
        query = """
            SELECT id, tenant_id, amount, status, created_at
            FROM transactions
            WHERE tenant_id = :tid
            ORDER BY id
            LIMIT :limit
        """

    rows, elapsed_ms = timed_query(db, query, params)
    analyze_query("transactions_search", elapsed_ms, tenant_id)

    data = [
        {"id": r[0], "tenant_id": r[1], "amount": float(r[2]), "status": r[3], "created_at": str(r[4])}
        for r in rows
    ]

    next_cursor = data[-1]["id"] if data else None

    return {
        "tenant_id": tenant_id,
        "results": data,
        "count": len(data),
        "next_cursor": next_cursor,
        "query_time_ms": round(elapsed_ms, 2),
    }
