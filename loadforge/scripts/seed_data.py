"""
Seed 100k+ rows across tenants, users, transactions, events.
Run: python -m scripts.seed_data
"""
import os
import random
import time
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch

DB_URL = os.getenv("DATABASE_URL", "postgresql://loadforge:loadforge@localhost:5432/loadforge")

TENANTS = 5
USERS_PER_TENANT = 20
TRANSACTIONS_PER_TENANT = 25000   # 5 tenants * 25k = 125k rows
EVENTS_PER_TENANT = 20000         # 5 tenants * 20k = 100k rows

STATUSES = ["success", "pending", "failed", "refunded"]
EVENT_TYPES = ["login", "purchase", "view", "click", "logout", "error"]


def random_ts(days_back=90):
    delta = random.randint(0, days_back * 86400)
    return datetime.now() - timedelta(seconds=delta)


def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("Seeding tenants...")
    tenant_ids = []
    for i in range(1, TENANTS + 1):
        cur.execute("INSERT INTO tenants (name) VALUES (%s) RETURNING id", (f"Tenant_{i}",))
        tenant_ids.append(cur.fetchone()[0])
    conn.commit()

    print("Seeding users...")
    user_rows = [
        (tid, f"user{j}@tenant{tid}.com")
        for tid in tenant_ids
        for j in range(USERS_PER_TENANT)
    ]
    execute_batch(cur, "INSERT INTO users (tenant_id, email) VALUES (%s, %s)", user_rows, page_size=500)
    conn.commit()

    print(f"Seeding {TRANSACTIONS_PER_TENANT * TENANTS:,} transactions...")
    start = time.time()
    for tid in tenant_ids:
        rows = [
            (tid, round(random.uniform(1, 5000), 2), random.choice(STATUSES), random_ts())
            for _ in range(TRANSACTIONS_PER_TENANT)
        ]
        execute_batch(
            cur,
            "INSERT INTO transactions (tenant_id, amount, status, created_at) VALUES (%s, %s, %s, %s)",
            rows,
            page_size=1000,
        )
        conn.commit()
        print(f"  tenant {tid} done")

    print(f"Transactions seeded in {time.time()-start:.1f}s")

    print(f"Seeding {EVENTS_PER_TENANT * TENANTS:,} events...")
    start = time.time()
    for tid in tenant_ids:
        rows = [
            (tid, random.choice(EVENT_TYPES), f'{{"session": "{random.randint(1000,9999)}"}}', random_ts())
            for _ in range(EVENTS_PER_TENANT)
        ]
        execute_batch(
            cur,
            "INSERT INTO events (tenant_id, type, metadata, timestamp) VALUES (%s, %s, %s::jsonb, %s)",
            rows,
            page_size=1000,
        )
        conn.commit()
        print(f"  tenant {tid} done")

    print(f"Events seeded in {time.time()-start:.1f}s")

    cur.close()
    conn.close()
    print("\nDone! Database seeded.")


if __name__ == "__main__":
    main()
