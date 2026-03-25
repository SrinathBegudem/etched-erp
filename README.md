# Etched ERP — Lightweight Manufacturing ERP Core

> Built as a working prototype to show how I think architecturally — not as a cover letter, but as actual code.

---

## Quick Setup & Run

```bash
# 1. Clone
git clone https://github.com/SrinathBegudem/etched-erp
cd etched-erp

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run automated tests — proves full workflow in one command
pytest -v

# 5. Start the server
uvicorn app.main:app --reload

# 6. Open interactive API docs
open http://localhost:8000/docs
```

That's it. No database setup. No environment variables. No external services. Just clone, install, and run.

---

## What This Does

A working ERP core built for manufacturing — covering the three systems that matter most when a chip company scales from R&D into real production.

| Module | Endpoints | What it does |
|---|---|---|
| **Inventory** | 5 | Stock tracking, movement audit trail, low-stock alerts, live valuation |
| **Suppliers & POs** | 4 | Supplier directory, purchase orders, auto-inventory sync on receipt |
| **Finance** | 4 | Invoice tracking, accounts payable, financial summary |
| **External API normalizer** | script | Handles inconsistent vendor formats — no manual cleanup |

### The core event chain

When a PO is received, four things happen automatically:

```
POST /purchase-orders/{id}/receive
  → inventory quantity updated
  → unit cost recalculated (weighted average)
  → inventory valuation updated
  → audit movement recorded with full trail
```

One action. Four consequences. No manual steps. No sync scripts. This is ERP thinking.

---

## Project Structure

```
etched-erp/
├── app/
│   ├── core/database.py       — SQLite today, Postgres tomorrow (one line change)
│   ├── models/models.py       — Suppliers, Inventory, POs, Invoices
│   ├── routes/
│   │   ├── inventory.py       — stock management + audit trail
│   │   ├── suppliers.py       — suppliers + full PO lifecycle
│   │   └── finance.py         — invoices + AP summary
│   └── main.py                — FastAPI app entry point
├── scripts/
│   └── external_api.py        — messy vendor API normalizer
├── tests/
│   └── test_erp.py            — end-to-end flow test
├── SYSTEM_DESIGN.md           — architecture decisions + tradeoffs + scaling plan
├── requirements.txt
└── README.md
```

---

## Run the Tests

```bash
pytest -v
```

Expected output:
```
tests/test_erp.py::test_full_erp_flow PASSED    [100%]
1 passed in 0.66s
```

The test simulates a full real-world workflow — supplier creation → inventory item → purchase order → PO receipt → inventory verification → invoice → payment → financial summary. Everything verified automatically.

---

## Run the External API Demo

```bash
python scripts/external_api.py
```

Shows three vendors returning the same data in completely different formats — strings with currency, nested objects, Unix timestamps — all normalized to a clean internal schema before touching the database. Directly demonstrates handling "APIs not well defined" from the job description.

---

## Switching to Postgres When You Need It

```python
# app/core/database.py — change one line
DATABASE_URL = "postgresql://user:password@host/etched_erp"
```

Nothing else changes. SQLAlchemy handles the rest.

---

## About Me

I'm Srinath Begudem — I just finished my Master's in Applied Data Science at USC (3.96 GPA) and I want to work at Etched.

Not because it's a good resume line. Because I genuinely think what you're building is one of the most important bets in hardware right now, and I want to be in the room when it works.

**My background is unusually broad for this kind of role:**

- 🎓 **Triple-discipline undergrad** — Mechanical Engineering, Computer Science, and Economics. I took Operations and Manufacturing Systems as part of my ME degree. I understand how manufacturing actually works — BOM structures, production scheduling, supplier lead times, quality control loops — not just as abstract concepts but as things I studied formally and find genuinely interesting.
- 📊 **MS Applied Data Science, USC** — 3.96 GPA, top of class in Machine Learning, Data Mining, and Python/DSA. [LeetCode 500+ solved](https://leetcode.com/u/3Puic29G9Y/) if you want proof of fundamentals.
- 🤖 **Agentic AI Intern, Nethermind (Web3 startup, London)** — Designed and built AgenticNews entirely alone. No team handoffs, no existing architecture to copy. I identified the problem, designed the system, built it, shipped it. Scraper reliability went from 30% to 98%. That's what I do when there's no one to ask — I figure it out.
- 🏥 **Data Engineering Intern, USC Alzheimer's Research Institute** — Designed and built the entire data pipeline migration solo. 30GB+ datasets, benchmarked Parquet vs Feather, presented to 200+ researchers, got adopted org-wide. Again — designed it alone, communicated it broadly.
- 🏢 **Full-time Data Engineer, Cognizant** — 1.5 years building enterprise ETL pipelines across 50+ source systems, cloud migration to AWS, ML models for ICICI Lombard insurance analytics at 87% accuracy. Real production systems, real stakes.
- 🏆 **2nd place, USC Data Mining Competition** — 200+ participants, RMSE of 0.9728 against a TA benchmark of 0.98. Lost first place by 0.0001. I'll take that.

**On working style:**

I built this entire ERP prototype — architecture, models, routes, tests, docs, design doc — in a few hours. That's not unusual for me. I work fast, I work alone when needed, and I communicate clearly when working with a team. At Nethermind I was fully remote across timezones and shipped without supervision. I'm comfortable with ambiguity and I don't need hand-holding to get things done.

I'm also the kind of person who works weekends on things I care about. Not because anyone asked me to — because the problem is interesting and I want to solve it. If Etched is building what I think it's building, that's exactly the environment I want to be in.

**On Etched specifically:**

The bet that model-specific hardware beats general-purpose GPUs is a strong one. An order of magnitude more throughput at lower latency isn't incremental — it's a category shift. When Sohu gets into production at scale, the products people build on top change completely. Real-time video generation, deep chain-of-thought agents that can actually run in production, inference at a price point that makes current use cases economical at 100x the volume — none of that is possible today at scale on GPUs.

I want to be part of making that real. I'm not precious about the role — software engineering, data engineering, systems engineering, ML infrastructure, whatever the company needs. I care about the outcome, not the title.

The best way I know how to show that is to build something, not write a paragraph about how excited I am. So I did.

**Links:**
- 📧 begudem@usc.edu
- 📱 (213) 756-9701
- 🔗 [LinkedIn](https://linkedin.com/in/srinathbegudem)
- 💻 [GitHub](https://github.com/SrinathBegudem) — see my other projects
- 🧠 [LeetCode 500+ solved](https://leetcode.com/u/3Puic29G9Y/) — proof of fundamentals