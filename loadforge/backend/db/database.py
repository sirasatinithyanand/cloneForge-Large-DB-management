import os
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import redis

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://loadforge:loadforge@localhost:5432/loadforge")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis client (optional - app works without it)
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    redis_client.ping()
    REDIS_AVAILABLE = True
    logger.info("Redis connected")
except Exception:
    redis_client = None
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - caching disabled")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def timed_query(db, query: str, params: dict = None):
    """Execute a query and return (results, elapsed_ms)."""
    start = time.perf_counter()
    result = db.execute(text(query), params or {})
    rows = result.fetchall()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return rows, elapsed_ms
