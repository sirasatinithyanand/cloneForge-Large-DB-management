# LoadForge

I built this to understand what actually happens to a backend when you throw real load at it. The short answer: without indexes and caching, things fall apart fast.

The project simulates a multi-tenant SaaS backend — 5 tenants, 225k+ rows across transactions and events — and lets you watch query times go from seconds to milliseconds as you layer on optimizations.

---

## How it's structured

```
[Locust Load Generator]
        ↓
[FastAPI Backend]  ←→  [Redis Cache]
        ↓
[PostgreSQL DB]
(225k+ rows, 5 tenants)
```

| Component | Tech |
|-----------|------|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| Load Testing | Locust |

---

## Database

| Table | Rows |
|-------|------|
| tenants | 5 |
| users | 100 (20 per tenant) |
| transactions | 125,000 (25k per tenant) |
| events | 100,000 (20k per tenant) |

The tables are intentionally created without indexes first — that's the whole point. You feel the pain before you fix it.

---

## Running it locally

Everything runs locally, nothing paid.

### 1. Start Postgres and Redis

```bash
cd docker
docker compose up -d postgres redis
```

### 2. Install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Seed the database

```bash
cd loadforge
python -m scripts.seed_data
# takes ~60s, loads 225k+ rows
```

### 4. Start the backend

```bash
# from the project root (cloneForge Large DB management/)

# Phase 1 — no cache, no indexes
USE_CACHE=false USE_INDEXES=false uvicorn loadforge.backend.main:app --reload

# Phase 2 — cache on
USE_CACHE=true uvicorn loadforge.backend.main:app --reload

# Phase 3 — indexes + cache
USE_CACHE=true USE_INDEXES=true uvicorn loadforge.backend.main:app --reload
```

### 5. Run the load test (separate terminal)

```bash
locust -f loadforge/load_test/locustfile.py --host=http://localhost:8000
# open http://localhost:8089
# 100 users, spawn rate 10
```

---

## The three optimization phases

### Phase 1 — Baseline
No indexes, no cache. Every request does a full table scan across 125k transactions and 100k events filtered by tenant. Under 100 concurrent users, this breaks.

### Phase 2 — Redis cache
```bash
USE_CACHE=true uvicorn loadforge.backend.main:app --reload
```
Dashboard and report endpoints cache results for 30-60 seconds. Repeated hits skip the database entirely.

### Phase 3 — Composite indexes
```sql
CREATE INDEX idx_transactions_tenant_created ON transactions(tenant_id, created_at);
CREATE INDEX idx_transactions_tenant_status ON transactions(tenant_id, status);
CREATE INDEX idx_events_tenant_ts ON events(tenant_id, timestamp);
```
These make cold (uncached) queries fast too, so the cache warming period stops causing failures.

---

## Results (measured, not estimated)

These are real numbers from the load test at 100 concurrent users.

| Endpoint | No cache / No index | Cache enabled |
|----------|--------------------:|--------------:|
| /dashboard median | 1600ms | 3ms |
| /dashboard 95th %ile | 17000ms | 11ms |
| /report median | 28000ms | 4ms |
| /transactions median | 1600ms | 11ms |
| Overall RPS | 6.9 | 79.4 |
| Failure rate | 26% | 3% |

The `/report` endpoint went from 28 seconds median to 4ms. The throughput went from 6.9 to 79.4 requests/second.

### Load test screenshots

**Phase 1 — no cache, no indexes (26% failure rate, system under stress)**

![Phase 1 baseline](docs/phase1_baseline.png)

**Phase 2 — Redis cache enabled (3% failures, 11x throughput)**

![Phase 2 cache](docs/phase2_cache.png)

---

## Try the APIs

```bash
# dashboard (heavy — hits 3 queries)
curl "http://localhost:8000/dashboard?tenant_id=1"

# filtered transactions with cursor pagination
curl "http://localhost:8000/transactions?tenant_id=1&status=success&limit=20"

# heavy report (aggregation + join)
curl "http://localhost:8000/report?tenant_id=1"

# auto-generated API docs
open http://localhost:8000/docs
```

Every response includes a `query_time_ms` field so you can see the database time directly.

---

## What I learned

The `/report` endpoint does a JOIN between 125k transactions and 100k events grouped by day — without an index, Postgres scans every row for every request. Under load, connections queue up and timeouts cascade.

Adding a composite index on `(tenant_id, created_at)` gives Postgres a way to jump directly to the rows it needs. Redis caching means repeat requests in the same 30-60s window never touch the database at all.

The optimizer module (`backend/services/optimizer.py`) logs a `[SLOW QUERY]` warning with an index suggestion whenever any query exceeds 500ms — a simple version of what real observability tools do.

Cursor-based pagination (`WHERE id > :cursor`) also matters at scale — OFFSET forces Postgres to count through skipped rows, which gets expensive fast on large tables.
