"""
Etched ERP — Lightweight, scalable, zero-bloat.

Architecture decisions documented here:
- FastAPI: async-ready, auto-docs, minimal overhead
- SQLite → Postgres-ready: swap one connection string, nothing else changes
- SQLAlchemy ORM: clean models, no raw SQL scattered everywhere
- Modular routes: each domain (inventory, suppliers, finance) is independent
- No heavy frameworks, no external queues, no microservices overhead — yet.
  When scale demands it, each module can be extracted into its own service.
"""

from fastapi import FastAPI
from app.core.database import engine, Base
from app.routes import inventory, suppliers, finance

# Create all tables on startup — no migration tool needed at this scale
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Etched ERP",
    description="""
## Lightweight ERP core built for manufacturing scale.

### Modules
- **Inventory** — stock management, movements, low-stock alerts
- **Suppliers & POs** — supplier management, purchase orders, auto-inventory update on receipt
- **Finance** — invoice tracking, accounts payable, financial summary

### Design Philosophy
- No over-engineering. No external dependencies beyond what's needed.
- Every stock change is audited via InventoryMovement records.
- PO receipt automatically syncs inventory — no manual steps.
- Financial summary endpoint is designed to feed dashboards or forecasting tools directly.
- SQLite today → Postgres tomorrow. One line change.
    """,
    version="0.1.0",
)

app.include_router(inventory.router)
app.include_router(suppliers.router)
app.include_router(finance.router)


@app.get("/", tags=["Health"])
def root():
    return {
        "system": "Etched ERP",
        "status": "running",
        "version": "0.1.0",
        "modules": ["inventory", "suppliers", "purchase-orders", "finance"],
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    # Basic liveness + DB connectivity check.
    # In production, extend this to check each critical dependency
    # (external APIs, cache, queue) and return per-service status —
    # so load balancers and monitoring tools get a real signal, not a hardcoded one.
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "down", "error": str(e)}
