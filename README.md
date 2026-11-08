<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0B3D91,50:1565C0,100:00A86B&height=220&section=header&text=NIDHIVEDA&fontSize=72&fontColor=ffffff&fontAlignY=38&desc=Security%20Deposit%20%26%20FDR%20Management%20Portal%20%E2%80%A2%20AICTE&descAlignY=60&descSize=18&animation=fadeIn" width="100%" alt="NIDHIVEDA banner"/>

<a href="https://git.io/typing-svg"><img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&duration=3200&pause=900&color=1565C0&center=true&vCenter=true&multiline=false&width=760&lines=Every+rupee+backed+by+evidence%2C+not+by+a+status+field.;Hash-chained+ledger+%E2%80%A2+Maker-checker+%E2%80%A2+DSC+approvals;Bank-confirmed+facts+%E2%89%A0+institution+declarations;Smart+India+Hackathon+2026+%E2%80%A2+PS+SIH26265" alt="Typing SVG" /></a>

<p>
  <img src="https://img.shields.io/badge/SIH%202026-PS%2026265-FF6F00?style=for-the-badge&logo=gov.uk&logoColor=white" />
  <img src="https://img.shields.io/badge/Organisation-AICTE-0B3D91?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Theme-Smart%20Automation-00A86B?style=for-the-badge" />
</p>
<p>
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/TypeScript-6-3178C6?style=flat-square&logo=typescript&logoColor=white" />
  <img src="https://img.shields.io/badge/Vite-8-646CFF?style=flat-square&logo=vite&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Python%203.11+-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/SQLite-dev-003B57?style=flat-square&logo=sqlite&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-147%20passing-2EA44F?style=flat-square&logo=pytest&logoColor=white" />
  <img src="https://img.shields.io/badge/a11y-0%20axe%20violations-8A2BE2?style=flat-square" />
</p>

<sub><b>Treat every FDR as a case with independent evidence for each stage — so a document, a UTR or an approval is never mistaken for proof that money is actually available, released or received.</b></sub>

<br/><br/>

[**Overview**](#-overview) · [**Flow**](#-how-it-works) · [**Features**](#-features) · [**Screens**](#-screenshots) · [**Architecture**](#-architecture) · [**Quick start**](#-quick-start) · [**Testing**](#-verification--testing) · [**Roadmap**](#-roadmap)

</div>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

## 🎯 Overview

**NIDHIVEDA** is a working prototype portal for AICTE's Regulation Bureau, institutions, finance officers and auditors to manage **Security Deposits and Fixed Deposit Receipts (FDRs)** end to end — submission, verification, maturity & renewal tracking, release, refund, notifications and audit.

A conventional portal keeps **one status per record** (`Submitted → Verified → Released`). That single field silently collapses five different questions. NIDHIVEDA keeps separate evidence for each:

| ❓ Question | ⚠️ What wrongly stands in for the answer | ✅ NIDHIVEDA's evidence |
|---|---|---|
| **Entitlement** — is a deposit required / release allowed? | A request form | Obligation from the rule edition in force + scrutiny of Affidavit-6 |
| **Attribution** — whose money is it? | A matching pool total | Explicit allocation records with confidence levels |
| **Availability** — does the instrument exist now? | An uploaded scan | A valid, current, **signed bank confirmation** that matches the declaration |
| **Authorisation** — who approved? | An officer clicking "approve" | **Maker-checker**, conflict-of-interest check, **DSC signature** over the exact gate decision |
| **Completion** — did the money arrive? | A debit and a UTR | Beneficiary bank's **positive credit confirmation** |

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

## 🔄 How it works

### Lifecycle of a deposit

```mermaid
flowchart LR
    A([🏫 Institution<br/>uploads FDR PDF]) --> B{🛡️ 6 content checks<br/>+ malware scan}
    B -- rejected --> X[[❌ Refused & audited<br/>nothing stored]]
    B -- clean --> C[🔐 SHA-256 +<br/>AES-256-GCM envelope]
    C --> D[🏦 Bank confirmation<br/>Ed25519-signed]
    D -- mismatch --> M[[⚠️ Flagged:<br/>declared ≠ confirmed]]
    D -- match --> E[📅 Maturity & renewal<br/>tracking + nudges]
    E --> F[📝 Release request<br/>+ Affidavit-6]
    F --> G[🔎 Scrutiny<br/>section officer · maker]
    G --> H[✍️ DSC approval<br/>deputy director · checker]
    H --> I[💸 Finance initiates<br/>payment]
    I --> J{🏦 Beneficiary bank}
    J -- returned --> K[[↩️ Still owed<br/>re-issue required]]
    K --> I
    J -- positive credit --> L([✅ Completed])

    classDef good fill:#E8F5E9,stroke:#00A86B,color:#0B3D2E;
    classDef warn fill:#FFF3E0,stroke:#FF6F00,color:#5D2E00;
    classDef core fill:#E3F2FD,stroke:#1565C0,color:#0B2B5C;
    class A,L good; class X,M,K warn; class B,C,D,E,F,G,H,I,J core;
```

### Release gate — maker-checker with signed evidence

```mermaid
sequenceDiagram
    autonumber
    actor Inst as 🏫 Institution
    actor SO as 👩‍💼 Section Officer (Maker)
    actor DD as 🧑‍⚖️ Deputy Director (Checker)
    actor FO as 💼 Finance Officer
    participant K as ⛓️ Trust-Ledger Kernel
    participant B as 🏦 Bank (SIMULATED)

    Inst->>K: Request release (+ Affidavit-6)
    SO->>K: Scrutiny — entitlement verified
    K-->>DD: Gate preview (rule edition, holds, conflicts)
    DD->>K: Approve with DSC signature over gate decision
    FO->>B: Initiate payment
    B-->>K: Debit + UTR  → "Sent", NOT complete
    alt Payment returned
        B-->>K: Return notice → ₹ still owed
        FO->>B: Re-issue payment
    end
    B-->>K: Positive credit confirmation
    K-->>Inst: ✅ Completed (hash-chained event)
```

### Event integrity

```mermaid
flowchart LR
    E1["Event #1<br/>hash = H(payload)"] --> E2["Event #2<br/>hash = H(prev ‖ payload)"] --> E3["Event #3<br/>hash = H(prev ‖ payload)"] --> E4["…"]
    E4 -.-> V{{"🔍 Auditor: verify chain<br/>+ Kernel.replay()"}}
```

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🗂️ Centralised repository
Institutions, obligations, FDRs (bank, branch, amount, rate, issue/maturity, renewal links), documents and release requests — searchable, filterable and **scoped per role**. Out-of-scope access returns `404`.

### 🛡️ Secure documents
PDF-only uploads with **six content checks**, malware scanning (ClamAV), **SHA-256** fingerprinting and **AES-256-GCM** envelope encryption. Integrity re-checked on every download.

### 🏦 Bank verification
Every bank fact is an **Ed25519-signed** message. Declared vs. bank-confirmed values are compared field-by-field; mismatches are surfaced instantly.

</td>
<td width="50%" valign="top">

### ✍️ Maker-checker approvals
Scrutiny → DSC-signed approval → finance. Conflict-of-interest checks, and the signature covers the **exact gate decision**.

### 🔔 Smart nudges
Maturity & renewal reminders, escalation ladders, notification centre, health dashboard and one-time action links across email / SMS / WhatsApp / push.

### ⛓️ Tamper-evident audit
Every financial event lives in a **SHA-256 hash chain**. Auditors re-verify and replay the full ledger from the UI. Exports to PDF with labels.

</td>
</tr>
</table>

**Also:** APH 2024-27 Table 1.4 amount rules with dated rule editions · policy diff editor with legal confirmation · command palette · guided tour · light & dark themes · WCAG-checked (0 axe violations across 42 routes per theme).

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

## 🖼️ Screenshots

<div align="center">

| 🔐 Login | 🏛️ AICTE Dashboard |
|:---:|:---:|
| <img src="docs/screenshots/nidhiveda/01-login.png" width="420"/> | <img src="docs/screenshots/nidhiveda/02-dashboard-aicte.png" width="420"/> |
| **🏫 Institution Dashboard** | **🔎 Auditor Dashboard** |
| <img src="docs/screenshots/nidhiveda/03-dashboard-institution.png" width="420"/> | <img src="docs/screenshots/nidhiveda/04-dashboard-auditor.png" width="420"/> |

</div>

<details>
<summary><b>📸 More screens — uploads, bank verification, release flow, audit (click to expand)</b></summary>
<br/>

| Upload checks & malware scan | Encryption status |
|:---:|:---:|
| <img src="docs/screenshots/nidhiveda/05-upload-checks-and-scan.png" width="420"/> | <img src="docs/screenshots/nidhiveda/06-upload-encryption-status.png" width="420"/> |
| **Bank-confirmed** | **Bank mismatch detected** |
| <img src="docs/screenshots/nidhiveda/16-bank-verification-confirmed.png" width="420"/> | <img src="docs/screenshots/nidhiveda/17-bank-verification-mismatch.png" width="420"/> |
| **Release gate** | **Sent ≠ complete** |
| <img src="docs/screenshots/nidhiveda/s01-1-release-gate.png" width="420"/> | <img src="docs/screenshots/nidhiveda/s01-2-sent-not-complete.png" width="420"/> |
| **Returned — still owed** | **Completed on positive credit** |
| <img src="docs/screenshots/nidhiveda/s01-3-returned-still-owed.png" width="420"/> | <img src="docs/screenshots/nidhiveda/s01-4-completed.png" width="420"/> |
| **Notification centre** | **Escalations** |
| <img src="docs/screenshots/nidhiveda/09-notification-centre.png" width="420"/> | <img src="docs/screenshots/nidhiveda/10-escalations.png" width="420"/> |
| **Rules & policy editor** | **Audit trail verification** |
| <img src="docs/screenshots/nidhiveda/13-rules-policy-editor.png" width="420"/> | <img src="docs/screenshots/nidhiveda/15-audit-trail-verify.png" width="420"/> |

</details>

🎬 **Demo video:** [`NIDHIVEDA_Demo_Final.mp4`](NIDHIVEDA_Demo_Final.mp4)

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

## 🏗️ Architecture

```mermaid
flowchart TB
    subgraph FE["🖥️ Frontend — React 19 · TypeScript · Vite"]
        UI[Role dashboards<br/>AICTE · Institution · Auditor]
        CH[Recharts · Framer Motion<br/>Command palette · Tour]
    end
    subgraph BE["⚙️ Backend — FastAPI"]
        R[Routers<br/>auth · data · ledger_api · records · nudge · exports]
        L[ledger.py<br/>kernel as service layer]
        D[documents.py · crypto.py<br/>checks · scan · encrypt]
        N[nudge/<br/>reminders · escalation · outbox]
        BK[bank/<br/>interface · simulator · deliver]
    end
    subgraph KR["⛓️ trust-ledger-kernel (hash-locked)"]
        KE[Commands → validated,<br/>hash-chained events]
    end
    subgraph ST["💾 Storage"]
        DB[(PostgreSQL 16 / SQLite<br/>+ invariant triggers)]
        S3[(S3-compatible<br/>ciphertext only)]
        AV[[ClamAV]]
    end
    UI -->|/api via Vite proxy| R
    R --> L --> KE
    L --> DB
    R --> D --> S3
    D --> AV
    R --> N
    BK -->|signed messages| L
```

Every money-changing request calls a kernel command. The kernel validates and emits events; the backend writes those events **and** the projection rows in **one transaction**. The database enforces money invariants a second time (CHECK, UNIQUE, triggers for `Σ allocations ≤ credit`). On start-up the kernel is rebuilt with `Kernel.replay()`.

<details>
<summary><b>📁 Repository layout</b></summary>

```
.
├── backend/                 FastAPI service
│   ├── app/
│   │   ├── ledger.py        kernel as service layer: replay, run, persist, checkpoint
│   │   ├── projections.py   kernel state → SQL tables
│   │   ├── invariants.py    DB triggers (SQLite + PostgreSQL)
│   │   ├── documents.py     PDF checks, scan, encrypt, integrity
│   │   ├── security.py      Argon2id, sessions, OTP, TOTP, DSC checks
│   │   ├── bank/            simulated banks (Ed25519) + delivery
│   │   ├── nudge/           reminders, escalation ladder, outbox, channels
│   │   ├── domain/          FDR, release/payment, Table 1.4 amounts
│   │   └── routers/         REST API
│   ├── migrations/          Alembic
│   ├── scripts/             seed, scenarios, mutants
│   └── tests/               pytest + Hypothesis
├── frontend/                React + Vite portal
├── trust-ledger-kernel/     unchanged, hash-locked control kernel
├── docs/                    security, notifications, scenario reports, screenshots, verification logs
└── design/                  UI design references
```

</details>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

## 🚀 Quick start

> **Prerequisites:** Python 3.11+, Node.js 20+, (optional) Docker for PostgreSQL.

```bash
# 1 — clone
git clone https://github.com/dharshan188/NIDHIVEDA-SIH26265-AICTE-FDR-Management.git
cd NIDHIVEDA-SIH26265-AICTE-FDR-Management

# 2 — backend
python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
cd backend
cp .env.example .env                              # fill in; never commit .env
../.venv/bin/python scripts/seed.py --reset       # migrate + seed (~3 s)
../.venv/bin/uvicorn app.main:app --port 8000

# 3 — frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173** 🎉 — Vite proxies `/api` to port 8000.

In dev mode, demo passwords are generated randomly and written to `backend/.dev-credentials.json` (gitignored). The dev login page has a **Use demo credentials** button; OTP codes are printed to the backend console.

<details>
<summary><b>👥 Demo roles (synthetic accounts)</b></summary>

| Account | Role | Can do |
|---|---|---|
| `meera@aicte-india.org` | AICTE · deputy director | approve releases (DSC), gate preview |
| `kiran@aicte-india.org` | AICTE · section officer | scrutiny (maker) |
| `ravi@aicte-india.org` | AICTE · finance officer | initiate / re-issue payments |
| `anil@aicte-india.org` | AICTE · reconciliation officer | holds, legacy import |
| `legal@aicte-india.org` | AICTE · legal cell | confirm rule packs, rulings |
| `auditor@aicte-india.org` | Auditor · internal audit | read, holds, audit verification |
| `1-12345678` | Institution (ABC Engineering College) | own records only |

</details>

<details>
<summary><b>🐘 Run on PostgreSQL</b></summary>

```bash
export TL_PG_PASSWORD=...        # your own
cd backend && docker compose up -d
export TL_DATABASE_URL=postgresql+psycopg://trustledger:$TL_PG_PASSWORD@localhost:5432/trustledger
../.venv/bin/python scripts/seed.py
```

See [`backend/README.md`](backend/README.md) for all environment variables.

</details>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

## 🧪 Verification & testing

<div align="center">

| ✅ Backend tests | 🧬 Kernel | 🎭 Scenarios | ♿ Accessibility | 🔒 Dependencies |
|:---:|:---:|:---:|:---:|:---:|
| **147** pass on SQLite **and** PostgreSQL 16 | **67** tests · **32/33** mutants killed | R1–R6 · **52** checks<br/>S01–S09 · **115** checks | **0** axe violations<br/>42 routes × 2 themes | **0** known Python advisories |

</div>

```bash
cd backend && ../.venv/bin/pytest -q                 # unit + property tests
../.venv/bin/python scripts/run_scenarios.py         # end-to-end scenarios
```

Detailed evidence: [`TEST_REPORT.md`](TEST_REPORT.md) · [`docs/scenario-report.md`](docs/scenario-report.md) · [`docs/security.md`](docs/security.md) · [`CHANGELOG.md`](CHANGELOG.md)

> [!IMPORTANT]
> **All external integrations in this prototype are SIMULATED and labelled as such** — bank channels, DSC certificate issuer, government SSO (e-Pramaan), OTP delivery and notification providers. Every bank message carries `"simulated": true` inside its signed payload and the UI shows a **SIMULATED** badge. All data is synthetic.

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

## 🗺️ Roadmap

- [x] Hash-chained ledger with replay and auditor verification
- [x] Secure PDF pipeline — checks, ClamAV, AES-256-GCM, S3 ciphertext
- [x] Maker-checker release with DSC-signed gate decisions
- [x] Maturity / renewal nudges with escalation ladder
- [x] PostgreSQL 16 parity and Alembic migrations
- [ ] Authorised bank / SFMS channels and JFDR registry access
- [ ] CCA-trusted DSC certificates with CRL/OCSP; e-Pramaan / DigiLocker OIDC
- [ ] DLT-registered SMS, WhatsApp Business, FCM
- [ ] Government HSM / managed KMS, S3 Object Lock (WORM)
- [ ] CERT-In empanelled penetration test

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif" width="100%" alt="divider"/>

<div align="center">

### 🇮🇳 Built for Smart India Hackathon 2026

**Problem Statement SIH26265 · Streamline of Security Deposit / FDR Portal · AICTE**

<sub>If this project helped you, consider giving it a ⭐</sub>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:00A86B,50:1565C0,100:0B3D91&height=120&section=footer" width="100%" alt="footer"/>

</div>
