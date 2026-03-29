import logging
from fastapi import FastAPI
from loadforge.backend.routes.dashboard import router as dashboard_router
from loadforge.backend.routes.transactions import router as transactions_router
from loadforge.backend.routes.reports import router as reports_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(
    title="LoadForge",
    description="Multi-tenant backend with adaptive performance optimization",
    version="1.0.0",
)

app.include_router(dashboard_router)
app.include_router(transactions_router)
app.include_router(reports_router)


@app.get("/health")
def health():
    return {"status": "ok"}
