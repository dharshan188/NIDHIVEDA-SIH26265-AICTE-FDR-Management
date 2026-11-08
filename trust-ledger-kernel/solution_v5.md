# SIH 2026 · PS 26265 — FDR Trust Ledger (v5: design plus a working, tested kernel)

**Problem Statement:** 26265 — Streamline of security deposit / FDR portal
**Organisation:** AICTE, Regulation Bureau · **Category:** Software · **Theme:** Smart Automation
**Version:** v5. v4 scored 88/100 at the design stage. The round-4 reviewer said the next real increase "must come from a working application and test results", and told us to stop adding modules. So v5 adds **no new modules**. It fixes the three P0 and four P1 findings, and ships a **running control kernel** with real test results (§13).
**Date:** 23 October 2026

> **How to read the claims in this file.**
> - ✅ **Verified**: we read it ourselves in the cited source.
> - 🟡 **Reported**: a reviewer says it is in an official source; we could not open that source ourselves.
> - ❓ **Unknown**: an open question for the AICTE mentor.
> - 🧪 **Measured**: produced by running our code. Synthetic data is labelled as synthetic.
>
> We cannot promise a score. A reviewer gives it. What we can do is make every claim checkable: you can run `pytest` and the scenario runner yourself.

---

## 0. The solution in one page

**FDR Trust Ledger** is a control module for AICTE's existing JFDR workflow. It does not replace JFDR. For every security deposit, it answers five questions separately, each with its own evidence:

| Question | Name | What answers it |
| --- | --- | --- |
| How much must be deposited? | **Entitlement** | Edition-aware rules, with the clause cited |
| Which money or instrument belongs to this obligation? | **Attribution** | Many-to-many allocations from bank-evidenced credits, each with a confidence level |
| Is it there today? | **Availability** | Bank-signed balance or instrument confirmation |
| Has the competent authority approved the action? | **Authorisation** | Sanction order (online) or NOC (FDR/RPGF), APH 2024-27 Cl. 6.46 |
| Did the money actually reach the institution, or the lien actually get discharged? | **Completion** | Positive credit confirmation (RTGS acknowledgement / NEFT N10), or the bank's lien-discharge confirmation |

**What v5 proves by running code** 🧪 (full output in §13):
- **The decisive round-4 scenario (₹35 lakh RTGS refund debited with a UTR, then returned):** the refund is never shown as *Completed*. After the return, the liability is reopened, Finance and the institution are alerted with a named owner and a target date, and nothing is deleted.
- **One ₹50 lakh UTR split across ₹35 lakh and ₹15 lakh obligations:** both are funded, nothing is flagged as a duplicate, and over-allocation is refused.
- **An unprovable ₹20 lakh attribution:** it is shown as *declared, not certified*, never as verified.
- **A 2019 auto-renewed FDR released in 2026:** the NOC names the **current** instrument number, after the rule for the renewal date and a fresh bank confirmation are both checked.
- **Totals:** 13 scenarios with 161 checks, and 43 automated tests (including property-based tests over 1,500 random payment sequences), all passing. 20 seeded mutants were run against the suite (result in §13.4).
- **The 13th scenario** was written *after* we recorded a hash of the code, and it ran with the code unchanged.

**What it cannot do:** make a paper FDR genuine, force a bank to reply, or stop three officials who collude.

### What changed in v5 (round-4 findings → fix → proof)

| Priority | Round-4 finding | v5 fix | Proof |
| --- | --- | --- | --- |
| 🔴 P0 | UTR + debit marked *Completed*; returned RTGS/NEFT payments not handled | Completion needs **positive credit confirmation**. A return, even one after settlement, reopens the liability, keeps the original attempt, alerts Finance and the institution, and sets a re-issue target | S01, S02, S13; property test (1,500 sequences) |
| 🔴 P0 | "One credit → one obligation" rejects valid payments | **Many-to-many allocations**. Invariants: allocated ≤ received per credit; allocated ≤ required per obligation; amount > 0 | S03; property test (300 random allocation sets) |
| 🔴 P0 | Misattribution cannot always be detected | Six **confidence levels**. Only bank-evidenced levels count toward release. If the bank shows the money came from *another registered institution*, the item turns UNCERTAIN automatically | S04, S12; 10,200-record synthetic run |
| 🟠 P1 | Historical renewal rules | Rules resolved for the **date of the act**. An unverified edition (APH 2018-19, reviewer-reported) is never applied silently: the legal cell confirms it or rules on the case | S06, S07; rule tests |
| 🟠 P1 | Unconditional attribution holds | Holds apply **only to named items**, placed by named roles, with a recorded basis and a 30-day review date (policy data, for AICTE to approve). The undisputed amount can be released | S05 |
| 🟠 P1 | Stale bank evidence at release | The NOC can name only an instrument confirmed by the bank within 90 days (policy data) **and** after its last maturity. Renumbering, auto-renewal and unexpected discharge are all handled | S06, S08; boundary tests |
| 🟠 P1 | Operating costs unverified | Cost drivers listed, with what is and is not known; bank-side checks preferred over institution letters (§12) | §12 |
| 🟡 P2 | Novelty overstated | Reworded: any good team *could* build this. Our claim is narrower and measurable (§15, Q2) | §13.3 |
| — | Annual balance confirmations are a burden | **Dropped.** Institutions are contacted only when bank evidence conflicts with the register. Non-response changes nothing | S04; synthetic run: 1,988 institutions (v4) vs 163 (v5) |
| — | A 13th scenario without code changes | Scenarios, rules and policy are JSON data | S13, plus code hash before and after |
| — | 10,000 legacy records | Import never marks anything verified, blocks nothing, and asks nobody to resubmit. Verification happens just in time, at release | S12; 10,200-record synthetic run |

---

## 1. Problem statement, decoded

AICTE's Regulation Bureau wants one system of record for security deposits and FDRs, covering submission through release, with alerts and an audit trail. Three requirements matter most:

1. **Provenance.** The system must distinguish what an institution submitted from what a bank or financial source independently confirmed.
2. **Legitimate verification channels "wherever supported".** Coverage will be partial, and the design must accept that.
3. **Measurable improvement**, tested on six named scenarios: new submission, validity tracking, approaching maturity, renewal, discrepancy, and authorised release.

---

## 2. Organizer background — the rules (✅ verified in APH 2024-27 unless marked; carried from v4)

| Rule | Source | What the system must do |
| --- | --- | --- |
| New non-government institutions recommended for LoA must create a security deposit | APH 2024-27 Cl. 1.12 ✅ | Trigger at LoA |
| Exempt: government and government-aided institutions; institutions under Cl. 1.3.3 that have existed for more than 5 years with their regulator | Cl. 1.12(i) ✅ | Exemption with evidence |
| **Table 1.4 amounts (₹ lakh), by level (Diploma / UG / PG):** Engineering & Technology 15 / **35** / 15; Planning, Applied Arts, Design and HMCT 15 / 15 / 15; Computer Applications – / 5 / 15; Management – / 5 / 15 | Table 1.4 ✅ | Required amount per programme and level |
| Amount is **doubled** for a private leased building or land | Table 1.4 note ✅ | Doubling rule |
| Multi-programme institutions pay the sum across programmes | AICTE FAQ ✅ | Programme-wise ledger |
| The deposit stays with the Council for **10 years**; **interest is retained by the Council**; the principal is returned to the Trust/Society/Company at term end; the term may be extended case by case, and the deposit **forfeited** for violations or complaints | Cl. 1.12(iv)–(v) ✅ | Lifecycle including *Extended* and *Forfeited* |
| No new deposit is needed where an **NOC was already issued for release of the earlier FDR** | Cl. 1.12(iii) ✅ | An NOC is the instrument that releases an FDR |
| Deposits are credited "in AICTE bank account" through the institute portal; **part payments are allowed**; status changes to "Deposit Received" | Cl. 1.10(b)(i) ✅; AICTE online deposit steps ✅ | Several credits can belong to one obligation |
| All uploaded documents must be **digitally signed (DSC)** by the Trust's Chairman or Secretary | Cl. 1.4.3, 1.4.6, 2.3.4 ✅ | Institution claims are signed and non-repudiable |
| Changing bank details is a formal process (TER ₹6,000; **Affidavit-9**); release needs **Affidavit-6** | Cl. 2.3.2 note iv ✅; AICTE attachments ✅ | Payee record changes only through that process |
| Release conditions: universities converted from institutions need no pending complaints or disciplinary proceedings; progressive closure and merger need a university certificate that no students remain (not needed if the deposit has matured) | Cl. **6.46** (g)–(i) ✅ | Mandatory clearances |
| For FDR/RPGF, AICTE issues an **NOC** after clearances; for RTGS deposits, the Council issues a **sanction order** | Cl. 6.46 (earlier sub-clauses) 🟡 | Two release paths |
| Late-creation penalties: 10% and 20% (APH 2024-27); 10% and 50% (APH 2020-21); separate 10% or 50% penalties before release in certain closure cases | APH texts ✅ | Edition-aware rules |
| 2026-27 addendum (21 pages) exists | Careers360 ✅ | Edition loaded as a test case |
| Within it: a 50% deposit provision for certain categories and regions; "private leased" changed to "leased" | 🟡 (official PDF not opened) | Must be confirmed before going live |
| RPGF stands for Refundable Performance Guaranty Fund | APH abbreviations ✅ | A separate instrument class |

**JFDR exists.** AICTE's portal manual has had a "JFDR Details" section since 2011-12 ✅. AICTE's March 2018 e-Gov tender lists JFDR as an application to revamp (§7.2.2) ✅. Who maintains it today, and under what contract, is ❓.

---

## 3. Customers and why AICTE posted this

| Customer | Role | Fear |
| --- | --- | --- |
| Regulation Bureau officers (primary) | Scrutiny, renewals, release | Approving a fake or misattributed deposit |
| Competent authority | Approves release, rules on conflicts and disputes | An audit query with no evidence behind the answer |
| AICTE Finance | Holds the money, reconciles, pays refunds | Books not matching the bank, or the wrong payee |
| Institutions | Deposit, renew, request release | Their own money stuck after 10 years |
| Banks | Confirm instruments, discharge liens | Blame for forged advices |
| Auditors | Verify deposits | Unverified, government-held instruments |

---

## 4. Why now (context, not cause)

**IDFC FIRST Bank, Chandigarh, 2026** ✅
- The bank paid ₹645 crore in claims. KPMG found that staff issued fake fixed-deposit advices and altered letters and statements, while the bank's core system stayed accurate.
- The fraud surfaced only when a department tried to close its deposits.
- Nothing links this case to PS 26265.

**Audit response** ✅
- A Kerala AG (Audit-II) circular dated 20 Jul 2026 forwards a CAG Synchronisation Wing letter of 19 May 2026.
- It tells auditors to check four things:
  - independent bank confirmation through official channels;
  - periodic reconciliation;
  - interest consistent with principal and tenure;
  - segregation of duties.
- It is a regional instruction; keep a downloaded copy.

**Confirmation risk** ✅
- In September 2022, ICAI warned that some banks route audit confirmations through third-party vendors.
- Their information may be neither authentic nor complete, and no one is clearly responsible for it.
- ICAI advises obtaining confirmation directly from the bank.

---

## 5. Impact on AICTE today

- Instruments can be fake, or closed early, without anyone noticing.
- Deadlines and penalty clocks run unobserved.
- Release can be slow for honest institutions and unsafe against dishonest ones.
- Money can be misattributed inside pooled balances.
- When auditors ask what was confirmed, by whom and when, there is no ready answer.
- Portfolio size (number of instruments, banks, rupees) is ❓.

---

## 6–7. Competitors and existing solutions

| Player | What it does | Gap for AICTE |
| --- | --- | --- |
| NeSL e-BG | Digital bank guarantees, with lifecycle management | Bank guarantees only |
| SFMS IFN 760COV (used by GeM, NSE Clearing, CTUIL) | Bank-guarantee advice sent bank to bank | Bank guarantees only; no standard message for FDRs was found |
| Nomentia (treasury software) | Registers guarantees for the issuer | Built for the issuer side; foreign SaaS |
| `ayus0109/AICTE-FDR-portal` (built for PS 26265; repo claims, tests not run) | Officer scrutiny, maturity notices, renewal lineage, release workflow, isolation between institutions, 11 tests | One status per record; simulated verification; no attribution, completion or authority model; no rule logic; hosted in AWS Sydney |
| Account Aggregator | Consent-based sharing of financial data | AICTE is not eligible as a Financial Information User (FIU) |

---

## 8. The gap

1. Verification is treated as a one-off event, not a state that can go stale.
2. The institution delivers its own evidence.
3. "Verified" is a single coarse flag.
4. Rules differ by edition and situation.
5. Release checks who is asking, not who is paid.
6. A matching total is treated as proof of individual ownership.
7. An authorisation is treated as if the money had moved.

---

## 9. Investment and business model (proposed)

- **Investment signal:** money is going into the rails for bank guarantees (NeSL e-BG has 38 banks and Entity Locker access since May 2026), not into portals for regulators. No venture round was found for deposit assurance aimed at regulators.
- **Year 1:** a module on JFDR for AICTE, built on an open-source core and hosted in India (NIC or an empanelled cloud).
- **Year 2+:** the same engine for other public bodies that hold third-party deposits, such as contractor security deposits, EMDs and other regulators.
- **Pricing:** per active instrument per year.
- **Revenue figures:** none claimed until portfolio size is known.

---

---

## 10. The solution, v5

**Core rule (unchanged):** a value is only as good as its evidence. Evidence counts only if it arrives through a channel the institution does not control. Entitlement, attribution, availability, authorisation and completion are never merged.

**What carries over from v4 without change:** DSC-signed institution claims; the claim / evidence / sufficiency model; SA 505-*inspired* (not SA 505-compliant) confirmation campaigns; the Bank Authority Registry; mandatory versus administrative clearances; conflict-of-interest blocking of prior handlers; registered payee plus name look-up; hash-chained audit with RFC 3161 time-stamps held by Internal Audit; the JFDR adapter route. This section covers only what v5 changes. Every rule below is **implemented and tested** in the kernel (§13).

### 10.1 Payment lifecycle: completion means the money arrived

```
AUTHORISED (sanction order) → INITIATED (Finance, ≠ approver) → DEBITED (bank debit + UTR)
      → SETTLED       only on positive credit confirmation (RTGS acknowledgement / NEFT N10)
      → RETURNED      return advice → REISSUE_REQUIRED (liability reopened)
SETTLED → RETURNED_AFTER_SETTLEMENT (rare; flagged for investigation) → REISSUE_REQUIRED
```

- **Debit + UTR means "sent", not "complete".** The institution sees: *"Sent from AICTE's bank on … via RTGS, UTR …. Waiting for your bank's credit confirmation. NOT yet complete."*
- **Why positive confirmation is the right evidence** ✅. RBI's NEFT refinement circular (DPSS CO EPPD No.168, 5 Feb 2010) introduced return within 2 hours of batch completion (B+2) and the N10 credit acknowledgement sent to the remitting bank. RBI's page lists this circular under withdrawn notifications, so the *current* timelines must be confirmed with AICTE's bank. For RTGS, the beneficiary bank credits within 30 minutes or returns within 1 hour of receipt (SBI RTGS FAQ) ✅. Both windows are **policy data** (`confirmation_window_minutes`), not code.
- **If no confirmation arrives within the window:** Finance receives one *confirmation overdue* alert, and the status stays *awaiting confirmation*. It never moves to *Completed* by default.
- **On a return**, four things happen:
  1. The attempt is marked RETURNED, with its debit, confirmation (if any) and return evidence all kept.
  2. The returned money is booked as a **return credit** linked to the original UTR. It can never be re-allocated as a new deposit (tested).
  3. The liability register shows the amount as outstanding again.
  4. If the return reason is account-related (`ACCOUNT_CLOSED`, `NAME_MISMATCH` and others in the policy list), the payee becomes unverified. Re-issue is then blocked until a new account goes through Affidavit-9 and a fresh name look-up.
- **Liability register per obligation:** held, in transit, settled, outstanding. One identity is checked after every step of every property test: **book balance = outstanding liabilities + unallocated credits − money in transit**.

### 10.2 Attribution: many-to-many allocation with confidence levels

Old v4 rule: one credit → one obligation. **Removed.** AICTE allows part payments (APH 2024-27 Cl. 1.10(b)(i)) ✅, and one remittance can cover several programmes.

New invariants, enforced by the kernel and tested with random inputs:
1. Σ allocations on a credit ≤ the credit amount.
2. Σ allocations to an obligation ≤ the required amount.
3. Every allocation names its basis and the person or rule that made it.
4. Returned-payment credits cannot be allocated.
5. Any excess stays visible as *unallocated* and refundable.

**Confidence levels** (derived from evidence at the moment of the question; never stored as a flag):

| Level | Meaning | Counts toward release? |
| --- | --- | --- |
| TRACEABLE | Bank-evidenced credit whose remittance carries this obligation's application reference | Yes |
| CORROBORATED | Bank-evidenced credit whose remitter account (per the bank) is the institution's registered account, or a competent-authority ruling | Yes |
| DECLARED | Bank-evidenced credit, linked only by the institution's or officer's statement | No (just-in-time check first) |
| LEGACY_DECLARED | From migration, with no bank link proving ownership | No (just-in-time check first) |
| UNCERTAIN | Competing claims, an open dispute, or the bank says another registered institution sent it | No |
| UNVERIFIED_SOURCE | The bank evidence came through a revoked or compromised signer | No |

Which levels count is policy (`online_sufficient_confidence`), so AICTE can tighten or relax it without code changes. Competing claims on one credit **move no money**: the claim is recorded, a dispute opens, and only allocations on that credit are affected.

### 10.3 What can honestly be certified (the trust test)

The certification report states two things separately:
- **The pool:** the bank-confirmed pooled balance compared with the ledger's expected pool (outstanding liabilities − in transit + unallocated). If they match, *aggregate availability* is certified.
- **Each institution:** certified only up to its TRACEABLE + CORROBORATED amounts. DECLARED, LEGACY, UNCERTAIN and held amounts are reported as such.

Run against the reviewer's case (S04): the pool matches, and A's certifiable amount is ₹0, with ₹20 lakh *declared, not certifiable*. That is the honest answer the reviewer predicted: we cannot prove ownership, and the system says so.

### 10.4 Holds: scoped, authorised, time-boxed (policy, not regulation)

- A hold can target only **named allocations, credits or instruments**. A hold on a whole institution is refused by policy (tested).
- Only `finance_reconciliation_officer` or `internal_audit` may place one, and a basis is mandatory.
- At **30 days** (policy) the hold goes to the competent authority to continue or lift. It is never silently extended.
- The **undisputed amount can be released** (`allow_partial_release_of_undisputed_amount`, policy). AICTE can switch this off, and a test proves the switch works.
- `data/policy.json` is marked `proposed_requires_AICTE_approval`. We do not present any of it as an AICTE regulation.

### 10.5 FDR release: the NOC names the current instrument

The `M_CURRENT_INSTRUMENT` gate requires a bank-signed confirmation that meets all of these:
- it comes from a currently valid signer;
- it is no older than 90 days (policy);
- it is dated **after the instrument's last maturity**, since the bank may have renewed or paid it;
- it shows status ACTIVE with the lien in AICTE's favour.

Three changes the bank can report:
- **Auto-renewal** to a new number. A new instrument is linked to the old one, and the renewal is judged by the rule in force on the *renewal date*.
- **Renumbering** (for example, after a core-banking migration). Linked, with no renewal rule applied.
- **Discharge or lien removal with no NOC.** An alert goes to Internal Audit, and release is blocked.

The NOC records the instrument number from the gate decision. A lien-discharge message for the *old* number is rejected (S06).

### 10.6 Renewal rules by edition

| Act | Edition used | Kernel outcome |
| --- | --- | --- |
| Manual renewal after maturity, Dec 2018 | APH 2018-19 (🟡 reviewer-reported Cl. 5.34.2) | Escalated to the legal cell until it confirms the pack; then **REJECTED** with the clause cited |
| Auto-renewal on maturity, Feb 2019 | APH 2018-19 (🟡) | Accepted only with a bank remark, after legal-cell confirmation |
| Manual renewal after maturity, Jun 2025 | APH 2024-27 ✅ (we found no clause) | NOT_SPECIFIED → escalated; a case ruling (`LC/2025/88`) decides |
| Renewal before maturity | Any | Treated as a replacement, pending bank confirmation |
| Two editions in force that disagree | Any | CONFLICT → escalated, never silently resolved (tested with a synthetic addendum) |
| A date no loaded edition covers (for example 2021) | None | Blocked. The system does not guess |

### 10.7 Legacy migration (the 10,000-record question)

1. **AICTE's own bank comes first.** Historical statement lines from AICTE's banker are loaded as bank evidence. No institution is involved.
2. **Import never upgrades a record.** A legacy record whose UTR matches exactly one statement line of the same amount gets a `legacy_register` allocation. Its confidence comes only from bank evidence: CORROBORATED if the bank's remitter is the institution's own account, otherwise LEGACY_DECLARED. Import can never produce TRACEABLE.
3. **Duplicates are flagged, not added** to the liability register. Two institutions claiming one UTR open a dispute.
4. **Nothing is blocked at import, and nobody resubmits.** Verification happens **just in time**, at release: for an FDR, a fresh bank confirmation; for online deposits, the bank's remitter details for that UTR. The institution is contacted only if the bank cannot resolve it.

Synthetic run (10,200 records, error rates assumed, not AICTE data) 🧪:

| Measure | Status-field baseline | Trust Ledger |
| --- | --- | --- |
| Records shown as verified | 10,200 | 3,419 certified by bank evidence |
| Verified or certified, but recorded against the wrong institution | 190 | **0** |
| Verified with no bank trace at all | 3,024 | 0 (shown as declared) |
| Liability overstated by duplicate records | ₹1,800 lakh | 0 (100 flagged) |
| Wrong-owner records flagged automatically | — | 74 of 190 (the bank showed another institution's account); the other 116 stay uncertified |
| Blocked at import / resubmissions requested | — | 0 / 0 |
| Institutions asked to confirm balances | 1,988 (v4 annual plan) | 163 |

Why it is 0, honestly: certification requires the bank's own remitter data to match. It could go wrong only if the bank data itself were wrong. That is the residual risk.

---

## 11. Technology stack

| Layer | Tool | Status |
| --- | --- | --- |
| **Control kernel** | Python 3.13, event-sourced; integer paise; JSON rule packs and policy | **Built and tested** (1,532 lines) |
| Bank evidence signatures | Ed25519 (`cryptography`) as a stand-in for DSC / PKCS#7 / SFMS-authenticated messages | Built; real DSC parsing (`pyHanko`) not yet built |
| Audit | SHA-256 hash chain over every event; full state rebuilt by replay | Built; RFC 3161 anchoring not yet built |
| Tests | pytest, Hypothesis, scenario runner, hand-seeded mutants | Built |
| Web | Next.js + TypeScript, Tailwind, ECharts, next-intl (English/Hindi) | Planned (finale) |
| API | FastAPI + Pydantic wrapping the kernel | Planned |
| Database | PostgreSQL 16, insert-only event table, row-level security | Planned; the kernel's event store maps 1:1 |
| Documents | MinIO with object lock | Planned |
| Identity | Keycloak; the kernel already enforces roles, segregation of duties and conflict of interest | Planned |

---

## 12. Business case and operating costs

**Work removed:** the v4 table still applies (clocks, rule computation, confirmation batches, checklists, status queries, audit packets). v5 removes one burden that v4 had *added*: blanket annual balance confirmations.

**Operating cost drivers.** Figures are ❓ until AICTE shares its portfolio size and bank arrangements, so we list drivers rather than invent rupee amounts.

| Driver | v5 design choice that keeps it low | Known? |
| --- | --- | --- |
| Bank confirmations | Just-in-time at release, not periodic for every FDR; batch requests per bank | Bank charges for confirmations ❓ |
| Institution correspondence | Only on conflict (163 of 1,988 institutions in the synthetic run) | Synthetic estimate 🧪 |
| Legal-cell time | Only for editions that are unverified, unspecified or in conflict; a confirmed pack is reused | ❓ |
| Hosting | One small API and a PostgreSQL instance; the kernel processed 10,200 records (29,377 events) in about 2–3 s on one CPU | Measured 🧪 |
| Maintenance | Rules and policy are JSON; a new edition is a data file plus test vectors | — |

**Value is still proved before scaling:** a baseline time study, then shadow mode (read-only on real legacy data, with flags compared against officers' judgement), then a 6-month pilot with go/no-go thresholds AICTE sets in advance. If the thresholds are missed, AICTE stops.

---

## 13. Testing: real results

Run it yourself: `pip install pytest hypothesis cryptography`, then `python -m pytest -q tests` and `python -m trustledger.scenario`.

### 13.1 Scenario runner: 13 scenarios, 161 checks, 0 failures 🧪

| ID | Scenario | Answers | Checks |
| --- | --- | --- | --- |
| S01 | ₹35 lakh RTGS refund debited with UTR, then returned | Issue 1, Q4, Q9, §9 decisive | 20 ✅ |
| S02 | Confirmation overdue → settled → late return reverses settlement | §9 follow-up | 13 ✅ |
| S03 | One ₹50 lakh UTR → ₹35 + 15 lakh; part payments; excess kept visible | Issue 3, Q1 | 13 ✅ |
| S04 | ₹20 lakh unprovable attribution; silent institutions; pool matches | Issue 2, Q7, Q8 | 18 ✅ |
| S05 | Scoped holds, partial release, 30-day review | Issue 8, Q6, Q10 | 12 ✅ |
| S06 | FDR matured 2019, auto-renewed, NOC in 2026 | Issue 5, 7, Q5 | 12 ✅ |
| S07 | Manual renewal after maturity under two editions | Issue 5 | 9 ✅ |
| S08 | Ten-year-old evidence; renumbered FDR; discharge without NOC | Issue 7 | 6 ✅ |
| S09 | Signer ended vs compromised; back-dating; tampered message | Registry | 12 ✅ |
| S10 | Mandatory vs administrative override; conflict of interest; maker-checker | Gates | 13 ✅ |
| S11 | Direct database edit of a stored credit | Audit | 2 ✅ |
| S12 | Legacy migration: no false verification, no blocking, no resubmission | Final AICTE question | 18 ✅ |
| S13 | **Judge's 13th**: NEFT returned *account closed* → Affidavit-9 → name mismatch → fixed → N10 → settled | Q3 | 13 ✅ |

**Decisive scenario, actual runner output (S01, abridged)** 🧪
```
 16 PASS refund R1 state=DEBITED
 17 PASS Sent from AICTE's bank on 2026-09-10T11:05 via RTGS, UTR SBINR52026091000077.
         Waiting for your bank's credit confirmation. NOT yet complete.
 18 PASS O1: held=35.00 lakh, in_transit=35.00 lakh, outstanding_liability=35.00 lakh
      # 35 minutes later the beneficiary bank rejects the credit and the money comes back.
 21 PASS refund R1 state=REISSUE_REQUIRED
 22 PASS O1: in_transit=0.00, outstanding_liability=35.00 lakh, cash_with_aicte=35.00 lakh
 23 PASS Payment UTR SBINR52026091000077 was returned by your bank on 2026-09-10 (BENEFICIARY_BANK_REJECT).
         NOT complete: AICTE still owes you Rs 35.00 lakh. Owner: AICTE Finance. Target re-issue: 2026-09-17.
 24 PASS [Finance] RTGS UTR … RETURNED. Liability of Rs 35.00 lakh reopened. Re-issue target 2026-09-17.
 26 PASS refund.attempts.0.status = RETURNED      (original attempt kept, not deleted)
 29 PASS raised StateError: a returned-payment credit cannot be allocated as a new deposit
 34 PASS refund R1 state=SETTLED                   (after re-issue + positive credit confirmation)
 39 PASS chain valid=True      40 PASS replayed 16 events, state identical
```

**13th scenario without code changes** 🧪: we recorded the SHA-256 of all kernel source files, then wrote S13 as a JSON file, ran it (13/13 pass), and re-hashed: `CODE UNCHANGED`. The limit: a 13th scenario that needs a *new kind of action* (for example, a new instrument class) does need code. A new combination of existing actions, rules or policy values does not.

### 13.2 Automated tests: 43 passed 🧪

| File | What it proves |
| --- | --- |
| `test_ledger_props.py` | **Hypothesis**, 300 random allocation sets: allocated ≤ received, allocated ≤ required, cash identity, replay identical. **1,500 random payment sequences** (pay, confirm, return before or after settlement, account-closed return, re-verify, tick): *Completed* only with confirmation evidence; never settled twice; liability = amount − settled; cash identity after every step. Coverage measured: about 11% of sequences end SETTLED and about 13% reach a return *after* settlement |
| `test_audit.py` | 200 random single-field edits are each detected at the exact event; deletions detected; delete-and-relink detected; deleting the *last* event is caught only by external anchoring (stated as a limit) |
| `test_rules.py` | Edition by date of act, inclusive boundaries, gaps not guessed, conflict escalation, legal confirmation, case rulings |
| `test_gates.py`, `test_controls_extra.py` | 90 vs 91-day evidence boundary; evidence before maturity rejected even when recent; policy-only changes take effect; bank remark required for auto-renewal; NOC names the current number; holds on proven items; payee name mismatch; Affidavit-9 needed for account change; a compromised name-look-up key stops payment |
| `test_scenarios.py` | Runs all 13 scenario files |

### 13.3 Same inputs, two designs 🧪

The baseline is a status-field workflow **we wrote ourselves** to represent the common design. It is **not JFDR**, whose internals we have not seen.

| Situation | Correct outcome | Status-field baseline | Trust Ledger |
| --- | --- | --- | --- |
| RTGS refund returned after debit + UTR | Liability reopened | Shows *Completed* | S01 pass |
| One ₹50 lakh UTR, two obligations | Both funded | Second rejected as duplicate | S03 pass |
| Legacy ₹20 lakh, owner unprovable | Declared, not certified | *Verified* | S04 pass |
| Contested item at A; A's other ₹35 lakh proven | A's ₹35 lakh releasable | All of A blocked | S05 pass |
| FDR auto-renewed to a new number | NOC names PNB-FD-2207 | NOC names superseded PNB-FD-1001 | S06 pass |
| Manual renewal after maturity, prohibiting edition | Rejected with clause | Accepted | S07 pass |
| Bank key compromised from a past date | Payment stopped | Evidence still trusted | S09 pass |
| 2,000 refunds, 67 returned (synthetic) | 0 false completions | **67** false completions | **0** |

### 13.4 Mutation testing 🧪

Each mutant re-inserts one control failure into a copy of the code, and the full suite must fail. First run: **15/20 killed**. The 5 survivors showed real gaps: holds, evidence predating maturity, payee re-verification after an account-closed return, delete-and-relink of the hash chain, and trust in the name-look-up key. We added tests for each, and that work exposed one real bug, which we fixed: payee verification was a stored flag and did not re-check the look-up signer. Second run: **19/20 killed**. The one survivor (*payment re-issue skips the evidence re-check*) survives because two other controls, payee verification and attribution sufficiency, independently block the same failure. We keep all three as defence in depth, and report it rather than hide it.

### 13.5 What is not built yet (stated plainly)

- No UI.
- No real DSC / PKCS#7 parsing.
- No bank connectivity: bank messages are simulated with signed test keys.
- No RFC 3161 anchoring.
- No JFDR adapter.
- No PostgreSQL.

The kernel is the part the reviewer called decisive: the financial and regulatory controls. The finale build wraps it in FastAPI and a web UI, which are routine compared with the controls.

---

## 14. Demo: one app, one dataset, about 8 minutes

The scenario runner drives everything. Bank messages are labelled *simulated* once, at the start.

1. **(1.5 min) The decisive refund (S01).** Debit + UTR → *Sent, not complete*. The return arrives → liability reopened, both alerts shown, original attempt still visible. Re-issue → N10 → *Completed*.
2. **(1 min) The accounting test (S03).** One ₹50 lakh UTR splits 35 + 15. An extra ₹1 lakh is refused. The ₹3 lakh excess stays visible.
3. **(1.5 min) The old FDR (S06).** 2014 evidence → blocked. The bank reports auto-renewal → blocked on the *2019* rule (unverified) → the legal cell confirms → NOC names PNB-FD-2207. A discharge message for the old number is rejected.
4. **(1 min) The trust test (S04).** The pool matches; A's certifiable amount is ₹0. The bank's remitter data shows Beta → UNCERTAIN → ruling → Beta CORROBORATED.
5. **(1 min) Fairness (S05).** B's discrepancy does not touch A's ₹35 lakh. A partial release of the proven ₹15 lakh goes through. The 30-day hold review fires.
6. **(1 min) Judge's 13th, live.** Edit S13 or a policy value (for example, evidence age 90 → 30 days) in front of the judges and rerun. No code edits.
7. **(1 min) Close** on the test table: 161 checks, 43 tests, mutation score, and the two-design comparison.

**Fallback:** drop step 5. Never drop step 1. Keep a recorded run.

---

## 15. Answers to the round-4 questions

| # | Question | Answer |
| --- | --- | --- |
| Q1 | One ₹50 lakh UTR, ₹35 + 15 lakh obligations | Two allocations from one credit. The invariant is allocated ≤ received, not one credit per obligation. Demonstrated in S03, including a refused over-allocation |
| Q2 | Competitors can build the same: what measured result? | Agreed, they can. Our claim is not that others *cannot*. On the same inputs, a status-field design produced 67 false completions out of 2,000 refunds, marked 190 wrong-owner records as verified, and overstated the liability by ₹1,800 lakh through duplicates. The kernel produced 0, 0 and 0, and its controls are pinned by mutation tests. Extending JFDR with this kernel is our recommended route: it *is* the extension |
| Q3 | A 13th scenario without code changes? | Yes, if it combines existing actions, rules or policy (S13, with the code hash unchanged). A genuinely new action type needs code, and we say so |
| Q4 | Debited, UTR, rejected, money back | Liability register: outstanding again, in transit 0. Status: REISSUE_REQUIRED. Completion evidence: none (the return is recorded against the attempt). Audit: debit, return and re-issue all kept in the hash chain. Finance is alerted with a target date |
| Q5 | FDR matured 2019, auto-renewed; release 2026 | Renewal: the edition in force on the renewal date (APH 2018-19, 🟡 until the legal cell confirms it). Release: APH 2024-27 Cl. 6.46 → NOC. Extra evidence needed: the bank's remark on the auto-renewal, and a fresh (≤ 90-day, post-maturity) confirmation of the **current** number. The NOC names that number |
| Q6 | Conflicting history; one institution can prove its entitlement | Not both. A hold attaches only to the contested items. A's proven amount is releasable. The basis is a proposed policy for AICTE to approve, not a regulation we invented |
| Q7 | Bank confirms the pool; internal records incomplete | We certify the aggregate. For each institution we certify only its TRACEABLE + CORROBORATED amounts; the rest is reported as declared or uncertain |
| Q8 | Why another annual statement? | You won't receive one. v5 dropped them. You are contacted only if bank evidence contradicts AICTE's register, and silence is never treated as wrongdoing |
| Q9 | Portal says completed, account never credited | It cannot say *Completed* without your bank's credit confirmation. If a credit is reversed later, the status reverts, the liability reopens, and you see the owner and the re-issue date |
| Q10 | 180-day delay from an internal reconciliation issue | At 30 days the hold goes to the competent authority to continue or lift. It cannot silently extend. The undisputed part can be released. You see who placed the hold and why |
| Final | 10,000 legacy records | §10.7: bank-side first, never upgraded by import, nothing blocked, no resubmission, just-in-time verification at release. Synthetic proof on 10,200 records |

---

## 16. Competitiveness (estimates) and alternatives

Unchanged from v4. These are estimates, not facts.
- **Submissions ❓ (estimate):** 25–60 on 26265, based on 13/500 slots used on 22 Oct and the averages for SIH 2025 and 2026.
- **Alternatives, by ideas submitted:** 26265 (13), 26262 (15), 26261 (17), 26263 (17), 26264 (25). Stay on 26265.
- **Known competition:** `ayus0109/AICTE-FDR-portal`. It has one status per record and simulated verification, with no attribution, completion or rule model.
- **Past winners rewarded:** working builds, fit with existing government workflows, and security depth (SIH 2024 SIH1729, an AICTE approval portal; SIH 2025 SIH25159, AICTE phishing detection).

**Why v5 is harder to beat:** most teams will show screens. We can show a failing payment being handled correctly, with a test table behind it.

---

## 17. Build plan and PPT

1. **Before the idea deadline (confirm with your SPOC; a tracker shows 28 Oct ❓):** a 6-slide PPT. Slide 3 = the five questions plus the S01 output. Slide 6 = the test table (§13). Never write "fraud-proof".
2. **Weeks 1–2:** FastAPI over the kernel; PostgreSQL event table; officer and institution screens for S01, S03 and S06.
3. **Weeks 3–4:** real DSC verification with pyHanko; RFC 3161 anchoring; audit-packet PDF.
4. **Weeks 5–6:** the remaining screens, a hidden error set built by teammates who did not write the checks, and a recorded demo.

---

## 18. Open questions for the AICTE mentor

| Question | Why it matters |
| --- | --- |
| Exact idea deadline | Submission |
| Does AICTE's bank provide signed statements, remitter details and positive credit confirmations to AICTE? | Attribution and completion evidence |
| Current RTGS/NEFT return timelines per AICTE's bank | Policy windows |
| Official text of APH 2018-19 Cl. 5.34.2, and the editions from 2019-20 to 2023-24 | The renewal rule packs |
| Are the hold policy, the partial-release policy and the 90-day evidence age acceptable? | `policy.json` approval |
| Who maintains JFDR, and is there a data interface? | Integration |
| Portfolio size | Costs |

---

## 19. Self-check: claim status

| Claim | Status |
| --- | --- |
| APH 2024-27 Table 1.4, 10-year term, interest retained, NOC releases FDR, part payments, DSC, Affidavit-6 and Affidavit-9, Cl. 6.46(g)–(i) | ✅ |
| Cl. 6.46 NOC versus sanction order | 🟡 reviewer (consistent with our reading) |
| APH 2018-19 Cl. 5.34.2 renewal rule | 🟡 reviewer only; the PDF download was blocked from our environment |
| NEFT B+2 hours and N10 acknowledgement | ✅ RBI circular, 5 Feb 2010 (listed as withdrawn; current timelines ❓) |
| RTGS 30-minute credit / 1-hour return | ✅ SBI RTGS FAQ |
| All kernel results in §13 | 🧪 measured by running the code; synthetic data labelled |
| Baseline equals JFDR | ❌ Not claimed. The baseline is our own model |
| Cost figures | ❓ drivers only |

---

## Sources

**New in v5**
- RBI, NEFT refinement of process flow (DPSS CO EPPD No.168, 5 Feb 2010) — https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=5489
- SBI, RTGS FAQ on sbi.co.in (credit within 30 minutes, return within 1 hour). We read it during research but did not keep the exact page link; re-check before citing it in the PPT
- APH 2018-19 (reviewer-cited; not opened by us) — https://www.aicte.gov.in/sites/default/files/APH%202018-19%20Modified.pdf

**Carried from v4** (APH 2024-27, AICTE pages, CAG/Kerala AG circular, ICAI, RBI name look-up, CCA, NeSL, SFMS, competitor repo, SIH sources):

**AICTE**
- APH 2024-27 (full text) — https://cdnbbsr.s3waas.gov.in/s35938b4d054136e5d59ada6ec9c295d7a/uploads/2025/03/2025031399.pdf
- APH 2024-27 p.62, Cl. 6.46(g)–(i) — https://sairam.edu.in/wp-content/uploads/2025/04/AICTE-GREIVIENCE-AND-REDRESSAL-.pdf
- APH 2020-21 — https://epsiindia.org/wp-content/uploads/2019/01/APH-2020_21.pdf
- AICTE approval attachments (Affidavit-6, Affidavit-9) — https://www.aicte-india.org/bureaus/approval/approal-process-2024-25/approval-process-2024-25-attachments
- AICTE online security deposit steps — https://aicte.gov.in/sites/default/files/Security_Deposit.pdf
- AICTE FAQ (multi-programme deposit) — https://aicte.gov.in/sites/default/files/FAQ%20Updated.pdf
- Careers360 on the 2026-27 addendum — https://news.careers360.com/aicte-approval-process-handbook-2026-27-update-engineering-college-business-school-management-foreign-student-seats-minor-diploma/amp
- AICTE e-Gov RFP, March 2018 — https://aicte.gov.in/sites/default/files/RFPeGov.pdf
- AICTE help manual 2011-12 (JFDR Details) — https://www.dauniv.ac.in/frontassets/college_development_council/MBA%20Appr%20Proc%202011-2012.pdf

**Audit, banking, PKI**
- CAG / Kerala AG (Audit-II) circular — https://cag.gov.in/uploads/ae_circulars_office_orders/CircularsOfficeOrders-06a759096da1e76-62695435.pdf
- ICAI: external confirmations through third-party vendors (7 Sep 2022) — https://www.icai.org/post/external-confirmations-through-third-party-vendors
- ISA 505 — https://ktkt.uel.edu.vn/Resources/Docs/SubDomain/ktkt/VanBan/ISA/ISA%20505.pdf
- RBI name look-up circular — https://rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx?Id=12759
- CCA time-stamping guidelines — https://cca.gov.in/sites/files/pdf/services/TIMESTAMPINGGUIDELINES.pdf
- CCA PKI services — https://cca.gov.in/avail_service.html
- MCCIL lien letter — https://www.msei.in/SX-Content/static/mcxsxccl/Collateral/CS-Annexure-VI.pdf
- IREDA FDR letter — https://www.ireda.in/images/legaldoc/FDR---Letter.pdf
- GeM BG SFMS format — https://assets-bg.gem.gov.in/resources/upload/shared_doc/emdformat_1604313092.pdf
- NSE Clearing SFMS circular — https://nsearchives.nseindia.com/content/circulars/CD45365.pdf
- Mondaq on NeSL e-BG — https://www.mondaq.com/india/financial-services/1787030/digital-transformation-of-bank-guarantees-nesls-integration-of-electronic-bank-guarantees-with-entity-locker
- Sahamati AA glossary — https://sahamati.org.in/glossary-of-aa-terms/

**Fraud context**
- IANS — https://ianslive.in/idfc-first-bank-pays-rs-645-crore-in-chandigarh-branch-fraud--20260310110132
- FilingReader (KPMG) — https://filingreader.com/news-wire/mumbai/2026-06-05/kpmg-confirms-inr-646-crore-fraud-at-idfc-first-bank
- WION — https://embed.wionews.com/india-news/chandigarh-shock-how-an-ex-bank-official-allegedly-pulled-off-a-rs-590-crore-scam-1772033264602

**SIH**
- Competitor repo — https://github.com/ayus0109/AICTE-FDR-portal
- SIH 2026 tracker — https://zaidsayyed.in/tools/sih-problem-statements
- PIB SIH 2025 — https://www.education.gov.in/sites/upload_files/mhrd/files/PIB2201244.pdf
- KL University SIH 2024 — https://www.kluniversity.in/view.aspx?id=3518
- KJSCE SIH 2025 — https://kjsce.somaiya.edu/en/view-announcement/1043

