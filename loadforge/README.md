# LoadForge

LoadForge simulates large-scale multi-tenant backend systems and dynamically optimizes performance under heavy load.

## Architecture

```
[Locust Load Generator]
        ↓
[FastAPI Backend]  ←→  [Redis Cache]
        ↓
[PostgreSQL DB]
(100k+ rows, 5 tenants)
```

| Component | Tech |
|-----------|------|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Load Testing | Locust |

## Database Schema

- **tenants** — 5 tenants
- **users** — 20 per tenant (100 total)
- **transactions** — 25,000 per tenant (125,000 total)
- **events** — 20,000 per tenant (100,000 total)

## Quick Start

### 1. Start infrastructure (free, all local)

```bash
cd docker
docker compose up -d postgres redis
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Seed the database

```bash
cd loadforge
python -m scripts.seed_data
```

### 4. Run the backend

```bash
# Phase 1: No indexes, no cache (SLOW)
USE_CACHE=false USE_INDEXES=false uvicorn loadforge.backend.main:app --reload

# Phase 2: Add cache only
USE_CACHE=true uvicorn loadforge.backend.main:app --reload

# Phase 3: Add indexes (run optimize_indexes.sql first) + cache
USE_CACHE=true USE_INDEXES=true uvicorn loadforge.backend.main:app --reload
```

### 5. Run load test

```bash
locust -f load_test/locustfile.py --host=http://localhost:8000
# Open http://localhost:8089
# Start with 10 users, ramp to 100+
```

## Optimization Steps

### Step 1 — Baseline (slow)
No indexes, no cache. Run load test and note response times.

### Step 2 — Add Redis cache
```bash
USE_CACHE=true uvicorn ...
```
Dashboard and report responses are cached for 30-60 seconds.

### Step 3 — Add indexes
```sql
-- Run in psql
CREATE INDEX idx_transactions_tenant_created ON transactions(tenant_id, created_at);
CREATE INDEX idx_transactions_tenant_status ON transactions(tenant_id, status);
CREATE INDEX idx_events_tenant_ts ON events(tenant_id, timestamp);
```
Then set `USE_INDEXES=true`.

## Before vs After Results

| Endpoint | No Index / No Cache | + Cache | + Index + Cache |
|----------|--------------------:|--------:|----------------:|
| /dashboard | ~800ms | ~5ms (cached) | ~120ms (cold) |
| /report | ~1200ms | ~5ms (cached) | ~200ms (cold) |
| /transactions | ~400ms | — | ~50ms |

## Example Queries

```bash
# Dashboard
curl "http://localhost:8000/dashboard?tenant_id=1"

# Filtered transactions with cursor pagination
curl "http://localhost:8000/transactions?tenant_id=1&status=success&limit=20"

# Heavy report
curl "http://localhost:8000/report?tenant_id=1"
```

## What I Learned

- Full table scans on 125k-row tables with per-tenant filters are expensive without a `(tenant_id, created_at)` composite index
- Redis caching with a 30-60s TTL eliminates repeat heavy queries under load
- Cursor-based pagination is more efficient than OFFSET at large page depths
- The optimizer module detects slow queries at runtime and logs actionable suggestions

