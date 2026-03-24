"""
Etched ERP — Lightweight, scalable, zero-bloat.
- FastAPI: async-ready, auto-docs, minimal overhead
- SQLite → Postgres-ready: swap one connection string, nothing else changes
- Modular routes: each domain is independent and extractable
"""

from fastapi import FastAPI
from app.core.database import engine, Base
from app.routes import inventory, suppliers, finance

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
    return {"status": "healthy"}
