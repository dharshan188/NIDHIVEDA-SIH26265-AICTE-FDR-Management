# FDR Trust Ledger — Backend (SIH 2026 · PS 26265)

FastAPI service that runs the **trust-ledger-kernel** (unchanged, in `../trust-ledger-kernel`) as its service layer, stores
the kernel's hash-chained events in a database, and adds authentication, the portal API and a **simulated** bank layer.

> **All banks are simulated.** Every bank message carries `"simulated": true` inside its signed payload, and the UI shows a
> SIMULATED badge wherever bank data appears. Nothing here talks to a real bank, SMS gateway, DSC issuer or e-Pramaan.

## Architecture in one paragraph

Each request that changes money or rules calls a kernel command through `app/ledger.py`. The kernel validates and emits
events; the backend writes those events (including rejection events) and the matching projection rows in **one database
transaction**. The database enforces the money invariants a second time (CHECK, UNIQUE, and triggers for
Σ allocations ≤ credit and Σ allocations ≤ required). If storage refuses a write, the in-memory kernel is discarded and
rebuilt from the database. On start-up the kernel is rebuilt with `Kernel.replay()`.

```
app/
  ledger.py          kernel as service layer: replay, run, persist, checkpoint
  projections.py     kernel state -> SQL tables (and FDR status rules)
  invariants.py      DB triggers (SQLite + PostgreSQL)
  bank/interface.py  one abstract class per bank channel
  bank/simulator.py  simulated banks: Ed25519 keys derived from TL_SIM_BANK_SEED, core-banking "books"
  bank/deliver.py    every bank message -> kernel; logged in bank_messages; Bank Authority Registry
  security.py        Argon2id, sessions, OTP, TOTP, DSC certificate checks
  routers/           auth, data (dashboards/FDRs), ledger_api (releases, payments, holds, rules, audit...), sim, oidc_mock
  domain/            FDR, release/payment, Table 1.4 and penalty proposals
  seed.py            482 institutions, 821 FDRs, online deposits, users — all built through the kernel
scripts/             seed.py, run_scenarios.py, mutants.py
tests/               pytest + Hypothesis (SQLite), test_postgres.py (needs TL_TEST_PG_URL)
```

## Setup

Python 3.11+ (Pillow 13 security fixes require it). The container uses Python 3.12.

```bash
python -m venv ../.venv && ../.venv/bin/pip install -r requirements.txt
cp .env.example .env          # fill in; never commit .env
../.venv/bin/python scripts/seed.py --reset     # SQLite: migrate + seed (≈3 s)
../.venv/bin/uvicorn app.main:app --port 8000
```

Then run the frontend (`cd ../frontend && npm install && npm run dev`) and open http://localhost:5173.
Vite proxies `/api` to port 8000, so the session cookie is first-party.

In dev, demo passwords are random and written to `backend/.dev-credentials.json` (gitignored, mode 600), unless you set
`TL_DEMO_PASSWORD`. The dev build of the login page has a **Use demo credentials** button that reads them from
`/api/sim/demo-accounts` (dev only). OTP codes are printed to the console by the mock SMS provider.

| Account | Role | Can do |
|---|---|---|
| meera@aicte-india.org | AICTE_OFFICIAL · deputy_director | approve releases (DSC), gate preview |
| kiran@aicte-india.org | AICTE_OFFICIAL · section_officer | scrutiny (maker) |
| ravi@aicte-india.org | AICTE_OFFICIAL · finance_officer | initiate / re-issue payments |
| anil@aicte-india.org | AICTE_OFFICIAL · finance_reconciliation_officer | holds, legacy import, name look-up |
| legal@aicte-india.org | AICTE_OFFICIAL · legal_cell | confirm rule packs, rulings |
| sharma@aicte-india.org | AICTE_OFFICIAL · director | approvals |
| auditor@aicte-india.org | AUDITOR · internal_audit | read, holds, audit verification |
| 1-12345678 | INSTITUTION (ABC Engineering College) | own records only |
| 1-xyz-demo | INSTITUTION (XYZ Institute of Technology) | own records only |

### PostgreSQL

```bash
export TL_PG_PASSWORD=...        # your own
docker compose up -d             # or: docker run -d -e POSTGRES_DB=trustledger -e POSTGRES_USER=trustledger -e POSTGRES_PASSWORD=$TL_PG_PASSWORD -p 5432:5432 postgres:16-alpine
export TL_DATABASE_URL=postgresql+psycopg://trustledger:$TL_PG_PASSWORD@localhost:5432/trustledger
../.venv/bin/python scripts/seed.py           # runs `alembic upgrade head`, then seeds
```

## Environment variables

| Variable | Meaning |
|---|---|
| `TL_ENV` | `dev` mounts `/api/sim/*` and the mock OIDC issuer; anything else disables both |
| `TL_DATABASE_URL` | SQLAlchemy URL (SQLite default; PostgreSQL via psycopg) |
| `TL_SECRET_KEY` | HMAC key for OTP hashes (required outside dev) |
| `TL_DATA_KEY` | Fernet key encrypting TOTP secrets (required outside dev) |
| `TL_SIM_BANK_SEED` | seed from which simulated banks' Ed25519 keys are derived |
| `TL_DEMO_PASSWORD` | dev: fixed password for demo accounts |
| `TL_COOKIE_SECURE` | keep `true` (browsers treat http://localhost as secure) |
| `TL_CHECKPOINT_PATH` | off-host audit checkpoint file (demo grade) |
| `TL_KERNEL_PATH` | path to trust-ledger-kernel |
| `TL_OIDC_ISSUER`, `TL_OIDC_CLIENT_ID`, `TL_OIDC_CLIENT_SECRET` | Government SSO; empty issuer in dev = local mock |
| `TL_PUBLIC_URL`, `TL_API_URL` | where the browser reaches the UI and API (for SSO redirects) |
| `TL_DEVCERTS_DIR` | dev: where the simulated DSC CA and test certificates live (gitignored) |

In dev, empty secrets are generated once into `backend/.dev-secrets.json` (gitignored, mode 600).

## Tests

The current reproducible baseline uses real services with mandatory-service
checks. From `sih2/`, run `.venv/bin/python tools/baseline/backend_check.py sqlite`
and `.venv/bin/python tools/baseline/backend_check.py postgres`. The latter runs
application fixtures on PostgreSQL too. See `../tools/baseline/README.md` for
setup and failure checks, and `../TEST_REPORT.md` for measured counts. Earlier
coverage counts in this README are historical.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest -q -p hypothesis.extra.pytestplugin tests
TL_TEST_PG_URL=postgresql+psycopg://... (same command)     # adds the 4 PostgreSQL tests
../.venv/bin/python scripts/run_scenarios.py               # S01–S09 with the kernel's runner
../.venv/bin/python scripts/mutants.py                     # hand-seeded mutants of the backend controls
```

(`PYTEST_DISABLE_PLUGIN_AUTOLOAD` only matters on machines where other pytest plugins are installed system-wide, such as ROS.)

## API map

`/api/auth/*` login, otp/send, otp/verify, totp/verify, dsc/challenge, dsc/verify, sso/start, sso/callback, logout, me ·
`/api/dashboard/{aicte,auditor,institution/{id}}` · `/api/fdrs` (list, upload, `{id}`, `bank-confirmation`, `verify`,
`discrepancy`, `renewal-check`, documents) · `/api/institutions` · `/api/obligations` · `/api/release-requests` (create,
scrutiny, gate, approve with DSC, override, reject, lien-discharge) · `/api/payments` (initiate, reissue) · `/api/payees` ·
`/api/holds` · `/api/rules` (packs, resolve, confirm, rulings, table-1-4, penalty-proposal) · `/api/policy` ·
`/api/reconciliation` · `/api/bank/messages`, `/api/bank/signers` · `/api/legacy/import` · `/api/reports/summary`,
`/api/reports/export.csv` · `/api/audit-trail`, `/api/audit-trail/verify` · `/api/sim/*` (dev only) · OpenAPI at `/api/docs` (dev only).
