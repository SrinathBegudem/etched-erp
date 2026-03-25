# System Design — Etched ERP

**Author:** Srinath Begudem
**Built in:** ~4 hours
**Why this exists:** To show how I think about systems before I write a single line of code.

---

## The Problem I Was Solving

Etched is moving from R&D into real manufacturing. That means:

- Chips going to fabrication → need to track components and materials
- Suppliers sending invoices → need to know what's paid, what's pending
- Stock running low → someone needs to know before it's too late
- Finance team asking "where did the money go?" → needs a real answer

None of this works if data lives in spreadsheets. And none of it works if the system is so complicated that one person leaving breaks everything.

So the design goal was simple: **build something that works today and doesn't need to be thrown away when you're 10x bigger.**

---

## Flow Diagram

```mermaid
flowchart TD
    A([Supplier]) -->|delivers goods| B[Purchase Order]
    B -->|created in system| C{PO Status}
    C -->|draft| D[Awaiting Approval]
    D -->|receive| E[PO Received ⭐]
    C -->|cancelled| F[Cancelled]

    E -->|auto triggers| G[Inventory Updated]
    E -->|auto triggers| H[Cost Recalculated]
    E -->|auto triggers| I[Audit Trail Logged]
    E -->|auto triggers| J[Invoice Created]

    G --> K[(Inventory DB)]
    H --> K
    I --> L[(Movement Log)]
    J --> M[(Finance DB)]

    K --> N[Inventory Summary API]
    M --> O[Finance Summary API]
    L --> P[Audit Trail API]

    N --> Q([Dashboard / Reporting])
    O --> Q
    P --> Q

    style E fill:#ff6b35,color:#fff
    style G fill:#4CAF50,color:#fff
    style H fill:#4CAF50,color:#fff
    style I fill:#4CAF50,color:#fff
    style J fill:#4CAF50,color:#fff
```

**The star is the most important part.** When a PO is received, four things happen automatically with no manual steps. That's the core of ERP thinking — one real-world event triggers a chain of system consequences.

---

## Architecture Decisions

### Why FastAPI and not Django or Flask

I've used all three. Here's the honest breakdown:

**Django** is great when you need everything — auth, admin panel, ORM, templating. We don't need any of that yet. Django would add 3x setup time for features we won't use for months.

**Flask** is simple but you have to wire up validation, serialization, and docs yourself. That's fine for a quick script but annoying when you're building actual APIs.

**FastAPI** hits the sweet spot — you get automatic request validation through Pydantic, auto-generated interactive docs at `/docs`, and it's async-ready for when we need it. I can move fast and the API is self-documenting from day one.

---

### Why SQLite and not Postgres

Honest answer: SQLite is fine until it isn't.

For a team of under 50 people with a few thousand records, SQLite handles everything without needing a server, connection pooling, or any infrastructure. You can back it up by copying one file.

When it becomes a problem — concurrent writes at high volume, replication needs, team size justifying a real database — the migration is **one line:**

```python
# Today
DATABASE_URL = "sqlite:///./etched_erp.db"

# When you need it — nothing else changes
DATABASE_URL = "postgresql://user:password@host/etched_erp"
```

SQLAlchemy abstracts everything else. This is the right decision at this scale, not a lazy one.

---

### Why a separate InventoryMovement table

I could have just updated `quantity_on_hand` directly and been done with it. But then you'd have no way to answer questions like:

- "When did our wafer stock drop below threshold?"
- "Which PO caused the spike in component costs in Q2?"
- "Did the adjustment last Tuesday match the physical count?"

Every stock change creates a movement record with a timestamp, a delta, a reason, and a reference back to the source document. It's a few extra rows per transaction. The payoff is full traceability forever.

This is standard practice in any real warehouse or manufacturing system. It's not over-engineering — it's the minimum you need to be trustworthy.

---

### Why weighted average cost and not FIFO or LIFO

Three common inventory valuation methods:

| Method | How it works | When to use |
|---|---|---|
| **FIFO** | First stock in, first stock out | Perishables, goods that expire |
| **LIFO** | Last stock in, first stock out | Tax purposes in certain jurisdictions |
| **Weighted Average** | Blend cost across all stock | Manufacturing components, chips |

For semiconductor components, the cost per unit doesn't change based on which physical unit you're consuming — a 300mm wafer from batch A costs essentially the same as one from batch B. Weighted average reflects reality better and is simpler to implement correctly.

Formula used:
```
new_unit_cost = (existing_qty × old_cost + incoming_qty × po_price)
                / (existing_qty + incoming_qty)
```

---

## What Happens When You Scale

### Current state (today)

```
Single server → FastAPI app → SQLite file → everything in one process
```

Works fine for: small team, hundreds of daily transactions, one region.

---

### First scaling step (~6 months, team 50+)

```
FastAPI app → PostgreSQL (same server or RDS)
```

One config change. Add connection pooling. Done. Handles millions of rows and concurrent writes without touching application code.

---

### Serious scale (manufacturing at volume, multi-region)

The modular design matters here. Right now inventory, suppliers, and finance are separate route files with clear boundaries. When the time comes, each can become its own service:

```
API Gateway
    ├── Inventory Service  (its own DB)
    ├── Supplier Service   (its own DB)
    └── Finance Service    (its own DB)
```

Each service owns its data. Cross-service communication goes through APIs or an event bus (Kafka, SQS). You don't have to redesign anything — you extract what already exists.

I didn't build microservices today because that would be premature. But I designed the code so that extracting them later is a refactor, not a rewrite.

---

### What I'd add next if this were a real product

**Short term:**
- Authentication (JWT, API keys per team)
- Pagination on list endpoints (inventory list at 100k items gets slow)
- Background job for overdue invoice detection (check daily, flip status automatically)

**Medium term:**
- Webhook support — so external systems can subscribe to events like `po_received` or `low_stock_alert` instead of polling
- Multi-currency support — already have `currency` field on invoices, just need conversion logic
- Bulk import endpoint — for migrating existing data from spreadsheets

**Longer term:**
- Read replicas for reporting queries so they don't slow down transactional writes
- Event sourcing for finance — full immutable ledger instead of mutable status fields
- NetSuite integration — the actual ERP this system would feed into

---

## The Messy API Problem

One thing I wanted to specifically demonstrate is what happens when external supplier APIs don't follow a standard format — because they never do in real manufacturing.

`scripts/external_api.py` shows three vendors returning the same data in completely different shapes:

```python
# Vendor A — cost as string with currency
{"cost": "148.50 USD", "qty": "500"}

# Vendor B — nested pricing object
{"pricing": {"amount": 151.0}, "quantity": 500.0}

# Vendor C — flat, unix timestamp for date
{"unit_price": 149.99, "unit_count": 500, "deliver_by_ts": 1757894400}
```

All three normalize to the same internal schema before anything touches the database. The normalizer tries multiple known field patterns, parses types explicitly, and flags warnings instead of crashing when something's missing.

This is the real work in integrations — not the happy path, but the "every vendor does it differently" path.

---

## Tradeoffs I Made Deliberately

| Decision | What I chose | What I gave up | Why it was worth it |
|---|---|---|---|
| SQLite over Postgres | Zero infra setup | Concurrent write performance | Right for this scale, trivial to change |
| REST over GraphQL | Simple, standard | Flexible client queries | GraphQL complexity isn't justified here |
| Sync over async | Easier to reason about | Max throughput | Async matters at scale, not now |
| No auth | Faster demo | Real security | Sprint 2 problem, not sprint 1 |
| In-process DB | No external deps | True isolation | Correct tradeoff for a prototype |
| Weighted avg cost | Simpler, accurate | FIFO tax optimization | Manufacturing use case fits perfectly |

---

## A Note on AI Usage

I used Claude and Claude Code to build this project. I want to be upfront about what that means and what it doesn't mean.

**What AI helped with:**
- Boilerplate code — SQLAlchemy model setup, FastAPI router scaffolding, Pydantic schema structure. This is the kind of repetitive structural code that follows well-known patterns. AI generates it correctly and quickly, and I verified every line.
- Initial file structure suggestions
- Catching syntax issues during iteration

**What I did myself:**
- Every architectural decision in this document — FastAPI vs Django, SQLite vs Postgres, movement table design, weighted average cost formula, modular route structure, the normalizer approach for messy APIs. None of that came from AI. Those are judgment calls that require understanding the problem.
- The external API normalizer logic — the field extraction patterns, the fallback strategy, the warning system. That's domain-specific thinking.
- The test design — what to assert, what the full flow should look like, using an in-memory DB override so tests don't pollute production data.
- Identifying that the original scraper architecture at Nethermind was wrong and needed a full redesign. That was observation and judgment, not code generation.

**My honest view on AI-assisted development:**

I think the engineers who will be most effective in the next few years are the ones who use AI to move faster on the mechanical parts and spend their own judgment on the parts that actually require thinking. Copy-pasting AI output without understanding it is how you get systems that work until they don't, with nobody who knows why.

I test everything I build. I can explain every design decision in this repo. If something doesn't work or a decision was wrong, I own that — not the tool I used.

I'm still learning how to use these tools well. But I'd rather be honest about that than pretend I typed every character by hand.

---

*Built by Srinath Begudem — begudem@usc.edu — github.com/SrinathBegudem*
