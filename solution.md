# NIDHIVEDA — SIH 2026 Final Presentation Research Dossier

> **Purpose.** This file is the single, evidence-backed source for building the six-slide SIH 2026 presentation. It is not
> the presentation. Every material claim names a repository file, test, log or screenshot. Simulated parts are labelled
> **SIMULATED**. Facts the team must supply are marked **REQUIRES TEAM INPUT**.
>
> **Name.** The solution's display name is **NIDHIVEDA** (changed from "FDR Trust Ledger" on 2026-10-24 at the team's
> request). The code still uses the internal name `trust-ledger` (`trust-ledger-kernel/`, Python package `trustledger`),
> because the control kernel is hash-locked and must not change. Evidence recorded before the rename shows the old name.
>
> **Previous version** of this file, preserved byte-for-byte: [solution.pre_ppt_backup.md](solution.pre_ppt_backup.md)
> (SHA-256 `d01e511b2f9dc3709f464a7454219115b5763bf157332dce96a7fed6eca1f965`). Its content is carried forward below.
>
> **Evidence dates.** All runs are on 2026-10-24 (IST). "Session 7" is the last full verification. "Session 8" is the
> verification after the rename and sidebar change ([docs/verification/session8/](docs/verification/session8/)).

---

## 1. Project Identity and Presentation Metadata

| Item | Value | Source / status |
|---|---|---|
| Solution name | **NIDHIVEDA** | Team instruction, 2026-10-24; shown in UI ([docs/screenshots/nidhiveda/01-login.png](docs/screenshots/nidhiveda/01-login.png)) |
| Tagline used in the UI | "Security Deposit & FDR Management Portal" | [frontend/src/pages/Login.tsx](frontend/src/pages/Login.tsx) |
| Problem statement ID | SIH26265 | Previous `solution.md`; kernel docs |
| Problem statement title | Streamline of Security Deposit / FDR Portal | Previous `solution.md` (from a public reproduction; see §17) |
| Organisation | All India Council for Technical Education (AICTE) | Same |
| Category / theme | Software / Smart Automation | Same |
| Official SIH wording verified? | **No.** sih.gov.in returned HTTP 403 when the previous document was written; wording came from a third-party tracker | Previous `solution.md` "Requirement source" |
| Registered team name | **REQUIRES TEAM INPUT** | Not in repository |
| Team ID | **REQUIRES TEAM INPUT** | Not in repository |
| College / institute | **REQUIRES TEAM INPUT** | Not in repository |
| Team members, mentor | **REQUIRES TEAM INPUT** (only if the SIH template asks) | Not in repository |
| GitHub repository URL | **REQUIRES TEAM INPUT.** `sih2/` is untracked inside a home-folder git repository whose remote is `github.com/dharshan188/teachnova26`; that is not confirmed as the project repository and nothing has been committed | `git status` shows `?? sih2/` |
| Demonstration URL | **REQUIRES TEAM INPUT** (none; the app runs locally) | — |
| Recorded demo video | **REQUIRES TEAM INPUT** (none found) | Search of repository |
| Screenshot directory | [docs/screenshots/nidhiveda/](docs/screenshots/nidhiveda/README.md) (current name and sidebar); [docs/screenshots/final/](docs/screenshots/final/README.md) (Session 7 evidence) | — |
| Technical documentation | [docs/security.md](docs/security.md), [docs/notifications.md](docs/notifications.md), [docs/scenario-report.md](docs/scenario-report.md), [TEST_REPORT.md](TEST_REPORT.md), [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md) | — |

No credentials, keys or personal data are reproduced in this document. Seeded user names (e.g. "Meera Iyer",
`1-12345678`, `1-xyz-demo`) are synthetic demo accounts.

---

## 2. Executive Summary and One-Sentence Innovation

**One sentence:** NIDHIVEDA treats an FDR or security deposit as a case with independent evidence for each stage, so a
document, a UTR or an approval is never mistaken for proof that the money is actually available, released or received.

**Summary.** NIDHIVEDA is a working prototype portal for AICTE's Regulation Bureau, institutions, finance officers and
auditors. It keeps institution declarations separate from bank-confirmed facts, checks and encrypts every uploaded PDF,
tracks maturity and renewal with the rule edition in force on each date, routes release through scrutiny, maker-checker
DSC approval and finance, and marks a refund "Completed" only on the beneficiary bank's positive credit confirmation.
Every financial event is in a SHA-256 hash chain that can be re-verified and replayed.

**What exists today (verified):** a React + FastAPI application on SQLite and PostgreSQL 16, an unchanged control kernel,
147 backend tests passing on both databases, a four-user browser run of the ₹35 lakh refund scenario, and real local
ClamAV and S3-compatible encrypted storage.

**What is SIMULATED:** every bank channel, the DSC certificate issuer, government SSO, OTP delivery and external
notification providers. Production use needs AICTE and bank authorisation (§12).

---

## 3. Exact Problem Understanding

**The brief (paraphrased; verify against the official SIH page, §19).** AICTE needs one system for security deposits
and FDRs covering submission, document management, bank verification, validity and maturity tracking, renewal history,
release and refund, notifications, dashboards, audit trails with role-based access, and secure, authorised integration.

**Why a status field is not enough.** A conventional portal stores one status per record ("Submitted → Verified →
Released"). Five different questions get collapsed into that one field:

| Question | What can wrongly stand in for the answer | NIDHIVEDA's evidence |
|---|---|---|
| Entitlement: is a deposit required, and is release allowed? | A request form | Obligation from the rule edition; scrutiny of entitlement and Affidavit-6 |
| Attribution: whose money is it? | A matching pool total | Explicit allocation records with confidence levels |
| Availability: does the instrument exist now? | An uploaded scan | A valid, current, signed bank confirmation that matches the declaration |
| Authorisation: who approved? | An officer clicking "approve" | Maker-checker, conflict-of-interest check, DSC signature over the exact gate decision |
| Completion: did the money arrive? | A debit and UTR | Beneficiary bank's positive credit confirmation (refund) or lien-discharge confirmation (FDR) |

**Regulatory background** (from the repository's research, not re-verified this session; see §17): APH 2024-27 Cl. 1.12
requires a security deposit for new non-government institutions; Table 1.4 sets amounts (e.g. ₹35 lakh for UG
Engineering & Technology), doubled for leased premises; the deposit is held for 10 years; Cl. 6.46 sets release
conditions; Affidavit-6 is needed for release and Affidavit-9 for bank-detail changes. AICTE already has a "JFDR Details"
module (portal manual 2011-12; 2018 e-Gov RFP §7.2.2). **NIDHIVEDA does not claim AICTE lacks an FDR system.**

---

## 4. Verified Implementation Status

Status key: **IMPLEMENTED_AND_TESTED**, **IMPLEMENTED_NOT_FULLY_TESTED**, **SIMULATED_EXTERNAL_DEPENDENCY**, **PLANNED**,
**UNKNOWN**. One requirement can have parts with different statuses.

### R01 — Centralised institution and FDR repository

| Aspect | Detail |
|---|---|
| Functionality | Institutions, obligations, instruments, FDRs (reference, bank, branch, amount, rate, issue/maturity, status, renewal links), documents, release requests, payments; search, filters, role-scoped lists |
| Frontend | `/aicte/institutions`, `/aicte/institutions/:id`, `/aicte/submissions`, `/institution/fdrs`, `/auditor/fdrs`, `/{role}/fdr/:id` ([frontend/src/App.tsx](frontend/src/App.tsx)) |
| Backend | `GET /api/fdrs`, `/api/fdrs/{id}`, `/api/institutions`, `/api/obligations` ([backend/app/routers/data.py](backend/app/routers/data.py)) |
| Entities | `institutions`, `fdrs`, `obligations`, `instruments`, `fdr_documents`, `release_requests` ([backend/app/models.py](backend/app/models.py)) |
| Controls | Institution scoping on every record; an out-of-scope request returns 404 (`institution_scope`, [backend/app/deps.py](backend/app/deps.py)); unique FDR number per bank (DB constraint) |
| Tests | `test_idor_institution_cannot_read_other_institution`, `test_dashboard_figures_from_db`, `test_db_unique_utr_per_debit_and_fdr_per_bank` |
| UI evidence | [02-dashboard-aicte.png](docs/screenshots/nidhiveda/02-dashboard-aicte.png), [04-dashboard-auditor.png](docs/screenshots/nidhiveda/04-dashboard-auditor.png) |
| Simulated | Data is synthetic (seed) |
| Limits | No import from the live JFDR system; legacy import exists for register/statement files only (`POST /api/legacy/import`) |
| **Status** | **IMPLEMENTED_AND_TESTED** (synthetic data) |

### R02 — Secure document uploads and management

| Aspect | Detail |
|---|---|
| Functionality | PDF-only upload; six content checks (size 64 B–10 MB, `.pdf` name, declared MIME, `%PDF-` signature, no scripts/attachments/forms, opens unencrypted with ≥1 page); malware scan before storage; SHA-256; AES-256-GCM envelope encryption with a per-document key wrapped by the master key; ciphertext-only object storage; SHA-256 re-check on every download and on demand; per-file pre-check on the upload page before anything is stored |
| Frontend | `/institution/upload`; documents panel on `/{role}/fdr/:id` ([frontend/src/components/FdrPanels.tsx](frontend/src/components/FdrPanels.tsx)) |
| Backend | `POST /api/fdrs`, `POST /api/documents/precheck`, `GET /api/fdrs/{id}/documents/{doc}`, `POST /api/fdrs/{id}/documents/{doc}/verify`; [backend/app/documents.py](backend/app/documents.py) `run_checks` (l. 42), `ingest` (l. 116), `read` (l. 151), `verify_integrity` (l. 174); [backend/app/crypto.py](backend/app/crypto.py) |
| Entities | `fdr_documents` (incl. `content_checks`, `integrity_status`, migration [0006](backend/migrations/versions/0006_document_checks.py)) |
| Controls | Infected files never stored and refusal audited; an object-store failure returns 503 and stores nothing; documents scoped per institution |
| Tests | `test_upload_encrypts_stores_and_verifies_on_download`, `test_document_bytes_unreadable_without_the_key`, `test_tampered_ciphertext_is_refused_and_audited`, `test_upload_rejects_non_pdf_and_unsafe_pdf`, `test_malware_is_rejected_not_stored_and_audited`, `test_document_access_is_scoped_per_institution`, `test_precheck_*` (3), `test_upload_keeps_content_checks_and_sha256_recheck_detects_tampering`, `test_object_store_failure_is_a_clear_503_and_stores_nothing`; real-service `test_clamav_passes_clean_pdf_and_flags_eicar`, `test_s3_store_holds_only_ciphertext` |
| UI evidence | [05-upload-checks-and-scan.png](docs/screenshots/nidhiveda/05-upload-checks-and-scan.png), [06-upload-encryption-status.png](docs/screenshots/nidhiveda/06-upload-encryption-status.png), [07-fdr-detail-documents.png](docs/screenshots/nidhiveda/07-fdr-detail-documents.png) |
| Real vs simulated | ClamAV 1.4.6 and SeaweedFS (S3 API) are **real local services**. The R1–R6 scenario runner uses a labelled scanner stub and filesystem storage |
| Limits | Master key held in the process environment (`LocalKms`), not an HSM/KMS; no object lock/WORM; seeded documents are metadata only (1,615 of 1,617 rows have no stored file, so they appear as "unverified" in reports); DSC-signed PDF validation (pyHanko) not built |
| **Status** | **IMPLEMENTED_AND_TESTED**; KMS and WORM **PLANNED** |

### R03 — Bank verification and discrepancy identification

| Aspect | Detail |
|---|---|
| Functionality | Field-by-field declared vs bank-confirmed comparison with confidence per field; verification refused without a valid confirmation from the issuing bank, or on mismatch; discrepancy flagging; observations (officer raises, institution replies, officer closes); bank messages Ed25519-signed per bank key, with a Bank Authority Registry (key validity and compromise dates) |
| Frontend | `/aicte/verification`, `/auditor/discrepancies`, comparison and observations panels on `/{role}/fdr/:id`, `/aicte/reconciliation` |
| Backend | `POST /api/fdrs/{id}/bank-confirmation`, `/verify`, `/discrepancy`, `/observations`; [backend/app/domain/fdr.py](backend/app/domain/fdr.py) `verify` (l. 109); [backend/app/bank/deliver.py](backend/app/bank/deliver.py); [backend/app/routers/records.py](backend/app/routers/records.py) |
| Entities | `bank_messages`, `bank_signers`, `observations`, `observation_replies` |
| Controls | Verification by any AICTE official, but only if a valid matching confirmation exists; only the issuing bank's key counts; compromised keys invalidate later evidence, including back-dated messages |
| Tests | `test_valid_confirmation_then_verify`, `test_tampered_message_rejected`, `test_wrong_bank_cannot_confirm_another_banks_fdr`, `test_compromised_from_invalidates_evidence_received_after`, `test_backdating_does_not_escape_compromise`, `test_bank_mismatch_creates_discrepancy`, `test_observation_lifecycle_open_answered_closed`; scenario R5 (9 checks); kernel S09 (12 checks) |
| UI evidence | [07-fdr-detail-documents.png](docs/screenshots/nidhiveda/07-fdr-detail-documents.png) (observations panel); comparison table: no dedicated final screenshot (**recapture recommended**, §15) |
| Simulated | **All bank messages are SIMULATED** (`backend/app/bank/simulator.py`, 12 test banks); labelled in UI, API (`"simulated": true`) and PDFs |
| Limits | No real bank, SFMS or JFDR channel |
| **Status** | Controls **IMPLEMENTED_AND_TESTED**; bank source **SIMULATED_EXTERNAL_DEPENDENCY** |

### R04 — Validity and maturity tracking

| Aspect | Detail |
|---|---|
| Functionality | Dashboard buckets computed by SQL from stored dates; "maturing in 90 days"; daily 08:00 IST sweep with reminders at 90/60/30/7 days; urgency ladder (info → action ≤30 d → deadline ≤7 d → overdue); quiet hours; overdue after missed renewal (+3 days) |
| Frontend | `/{role}/renewals`, dashboards, `/{role}/notifications` |
| Backend | `_bucket_sql` ([backend/app/routers/data.py](backend/app/routers/data.py) l. 26); [backend/app/nudge/reminders.py](backend/app/nudge/reminders.py); [backend/app/nudge/ladder.py](backend/app/nudge/ladder.py) `rung_for` (l. 9); [backend/policy.json](backend/policy.json) |
| Entities | `fdrs.maturity_date`, `notifications`, `scheduler_runs`, `notify_policy_versions` |
| Tests | `test_maturing_counted_from_server_date`, `test_rung_at_each_threshold` (parametrised), `test_day_boundary_is_ist_not_utc`, `test_daily_sweep_one_reminder_per_instrument_and_window`, `test_scheduler_survives_restart_without_resending`; scenarios R2 (7), R3 (8) |
| UI evidence | Dashboards (56 maturing), [09-notification-centre.png](docs/screenshots/nidhiveda/09-notification-centre.png) |
| Limits | Thresholds are configurable prototype defaults, not statutory AICTE deadlines |
| **Status** | **IMPLEMENTED_AND_TESTED** |

### R05 — Renewal and replacement history

| Aspect | Detail |
|---|---|
| Functionality | Renewal FDR links to its predecessor (`renewal_of` / `renewed_by`); per-FDR timeline shows each event with the APH editions in force on that date and how the relevant rule resolves; renewal-gap detection (matured, no renewal FDR and no bank renewal notice; or renewal unconfirmed for > 7 days); bank renumbering traced; unverified, unspecified or conflicting rules escalate instead of being guessed |
| Frontend | History timeline panel on `/{role}/fdr/:id`; `/aicte/rules` |
| Backend | [backend/app/timeline.py](backend/app/timeline.py) `fdr_timeline` (l. 29), `gaps` (l. 73); `GET /api/fdrs/{id}/timeline`, `/api/renewals/gaps`; rule packs [trust-ledger-kernel/data/rules/](trust-ledger-kernel/data/rules/) |
| Tests | `test_rules_escalate_never_guess`, `test_manual_renewal_after_maturity_escalates`, `test_renewal_before_maturity_is_replacement`; scenario R4 (8); kernel S06 (12), S07 (9), S08 (6) |
| UI evidence | [08-fdr-detail-timeline-no-gap.png](docs/screenshots/nidhiveda/08-fdr-detail-timeline-no-gap.png): shows the rules in force but **no gap**, because the seeded data has none (API returned 0 gaps; [session 7 SQL](docs/verification/session7/49-gap-sql.txt)) |
| Limits | No live screenshot of a renewal gap; gap behaviour is proven by tests and scenarios only. Rule packs include an unverified 2026-27 test addendum |
| **Status** | **IMPLEMENTED_AND_TESTED**; gap UI **IMPLEMENTED_NOT_FULLY_TESTED** in the browser |

### R06 — Release, discharge and refund processing

| Aspect | Detail |
|---|---|
| Functionality | Institution request → section-officer scrutiny (entitlement, Affidavit-6) → release gate showing each check (`M_ENTITLEMENT`, `M_AFFIDAVIT_6`, `M_RULES`, `M_APPROVER_ROLE`, `M_CONFLICT_OF_INTEREST`, `M_ATTRIBUTION`, `M_PAYEE_VERIFIED`) → deputy director/director approval with DSC signature over the gate decision → **FDR path:** NOC, completed only on the bank's lien-discharge confirmation; **online-deposit path:** finance initiates → debit + UTR ("NOT yet complete") → positive credit confirmation ("Completed") or return ("AICTE still owes you…") → re-issue. Returns after settlement are flagged |
| Frontend | `/{role}/releases` (`/institution/release`), `/{role}/payments` |
| Backend | [backend/app/routers/ledger_api.py](backend/app/routers/ledger_api.py) (release, payment, payee routes); [backend/app/domain/release.py](backend/app/domain/release.py) `approve` (l. 88: maker-checker l. 91–92, DSC l. 95–99); kernel `refund_status_text` ([trust-ledger-kernel/trustledger/kernel.py](trust-ledger-kernel/trustledger/kernel.py) l. 1019), gate checks (l. 803–806) |
| Entities | `release_requests`, `refunds`, `payment_attempts`, `allocations`, `bank_credits`, `kernel_events` |
| Controls | Scrutiny only by `section_officer`; approval only by `deputy_director`/`director`; the scrutiny officer cannot approve; the approver cannot initiate payment; DSC must be registered to the approver; mandatory checks cannot be overridden; initiation and re-issue only by `finance_officer` |
| Tests | `test_s01_live_returned_rtgs_refund`, `test_settlement_needs_matching_confirmation`, `test_return_after_settlement_flagged`, `test_maker_checker_scrutiny_officer_cannot_approve`, `test_approver_cannot_initiate_payment`, `test_mandatory_override_refused_logged_and_conflicts_officer`, `test_dsc_approval_bound_to_gate`, `test_fdr_release_noc_then_lien_discharge`; scenario R6 (10); kernel S01–S03, S10; browser S01 12/12 |
| UI evidence | [s01-1-release-gate.png](docs/screenshots/nidhiveda/s01-1-release-gate.png) … [s01-4-completed.png](docs/screenshots/nidhiveda/s01-4-completed.png) |
| Simulated | **Bank debit, return, credit confirmation and lien discharge are SIMULATED**; **DSC certificates come from a SIMULATED test CA** (signature checks are real) |
| Limits | No real payment; production DSC needs a CCA trust chain and revocation checks |
| **Status** | Controls **IMPLEMENTED_AND_TESTED**; bank and DSC issuer **SIMULATED_EXTERNAL_DEPENDENCY** |

### R07 — Notifications, reminders and escalations

| Aspect | Detail |
|---|---|
| Functionality | Transactional outbox (notice written in the same transaction as its event); English and Hindi templates; channels chosen by urgency rung; quiet hours 20:00–08:00 IST for SMS/WhatsApp, except overdue; daily digest; acknowledgement stops escalation; unacknowledged notices climb a rung and are copied institution → AICTE officer → competent authority; signed, single-use, user-bound 72-hour action links that never act on their own; preferences; health panel |
| Frontend | `/{role}/notifications`, `/aicte/escalations`, `/aicte/notification-health`, `/l/:token`, notification policy editor on `/aicte/rules` |
| Backend | [backend/app/nudge/](backend/app/nudge/) (`outbox.py`, `worker.py`, `escalation.py`, `links.py`, `insights.py`); [backend/app/routers/nudge.py](backend/app/routers/nudge.py) |
| Entities | `notifications`, `notification_deliveries`, `notification_prefs`, `action_tokens`, `provider_sim_messages`, `notify_policy_versions` |
| Tests | All 20 in `backend/tests/test_nudge.py` (e.g. `test_notice_is_written_with_its_event_or_not_at_all`, `test_retry_after_crash_does_not_send_twice`, `test_quiet_hours_defer_sms_but_not_overdue`, `test_acknowledgement_stops_escalation`, `test_action_links_refuse_expired_reused_forged_and_wrong_user`, `test_approval_link_opens_but_never_approves`); `test_smtp_adapter_delivers_to_mailpit_once_per_key`; scenarios R3, R4; UI vs direct SQL 7/7 ([session 7](docs/verification/session7/71-nudge-sql-final.txt)) |
| UI evidence | [09-notification-centre.png](docs/screenshots/nidhiveda/09-notification-centre.png), [10-escalations.png](docs/screenshots/nidhiveda/10-escalations.png), [11-notification-health.png](docs/screenshots/nidhiveda/11-notification-health.png) |
| Simulated | **E-mail, SMS, WhatsApp and push providers are SIMULATED** (labelled per delivery). Mailpit accepts real SMTP but delivers nothing externally |
| Limits | No DLT-registered SMS, production SMTP, WhatsApp Business or FCM; push shows 0 sent of 50 in the health panel (cause not investigated) |
| **Status** | Logic **IMPLEMENTED_AND_TESTED**; delivery **SIMULATED_EXTERNAL_DEPENDENCY** |

### R08 — Dashboards, reports and management visibility

| Aspect | Detail |
|---|---|
| Functionality | Three role dashboards (KPIs, status and value charts with table alternatives, alerts, maturity list); "What changed since you last looked", built from the audit chains since the previous sign-in; reports; missing-documents report (absent / expired / unverified) with CSV and PDF; any table to CSV/PDF; evidence packet PDF per FDR; every bank-data PDF labelled SIMULATED |
| Frontend | `/aicte`, `/institution`, `/auditor`, `/{role}/reports`, `/{role}/missing-documents` |
| Backend | `GET /api/dashboard/*` ([backend/app/routers/data.py](backend/app/routers/data.py) `_stats` l. 32); [backend/app/routers/exports.py](backend/app/routers/exports.py); [backend/app/pdf.py](backend/app/pdf.py); [backend/app/nudge/insights.py](backend/app/nudge/insights.py) |
| Tests | `test_dashboard_figures_from_db`, `test_missing_documents_*` (3), `test_any_table_exports_to_pdf_with_simulated_label`, `test_fdr_evidence_packet_pdf`, `test_what_changed_since_last_login`, `test_what_changed_links_point_at_pages_each_role_has`; PDF label check 8/8 ([session 7](docs/verification/session7/70-pdf-labels-final.txt)) |
| UI evidence | Dashboards 02–04, [12-missing-documents.png](docs/screenshots/nidhiveda/12-missing-documents.png), [14-pdf-export-missing-documents.png](docs/screenshots/nidhiveda/14-pdf-export-missing-documents.png) |
| Limits | Label inconsistencies across dashboards (§8, §19) |
| **Status** | **IMPLEMENTED_AND_TESTED** |

### R09 — Audit trails and role-based access controls

| Aspect | Detail |
|---|---|
| Functionality | Two SHA-256 hash chains (ledger: every kernel event; portal: sign-ins, submissions, scrutiny, policy and field changes); `/audit-trail/verify` recomputes both, detects edits, deletions and relinking, checks an off-host checkpoint and replays the ledger against live state; insert-only event tables; roles enforced at the API and in the kernel; permitted-field edits with before/after, reason and audit sequence number; policy editors with before/after preview and mandatory reason |
| Frontend | `/aicte/audit-trail`, `/auditor/audit-trail`, record-fields panel on FDR pages, `/aicte/rules` |
| Backend | [backend/app/portal_audit.py](backend/app/portal_audit.py) `record` (l. 23), `changes` (l. 44), `verify_rows` (l. 54); [backend/app/ledger.py](backend/app/ledger.py); [backend/app/routers/records.py](backend/app/routers/records.py); `require` / `require_kernel_role` in [backend/app/deps.py](backend/app/deps.py) |
| Tests | `test_audit_verify_clean`, `test_audit_detects_edit`, `test_audit_detects_middle_deletion_and_relink`, `test_audit_detects_deletion_of_last_event_via_checkpoint`, `test_audit_checkpoint_catches_consistent_rewrite_of_head`, `test_event_store_is_insert_only`, `test_role_enforcement`, `test_permitted_change_keeps_before_after_reason_and_is_chained`, `test_ledger_fields_roles_and_states_are_enforced`, `test_policy_editor_records_before_after_in_the_chain_and_only_approvers_edit`; kernel S11 (tamper) |
| UI evidence | [15-audit-trail-verify.png](docs/screenshots/nidhiveda/15-audit-trail-verify.png), [13-rules-policy-editor.png](docs/screenshots/nidhiveda/13-rules-policy-editor.png) |
| Limits | The checkpoint is a local file, not an independent trusted timestamp (RFC 3161 **PLANNED**); hash chains detect tampering but do not prevent collusion by authorised staff |
| **Status** | **IMPLEMENTED_AND_TESTED** |

### R10 — Security and authorised system integration

| Aspect | Detail |
|---|---|
| Functionality | Argon2id passwords; mandatory second factor (OTP, TOTP or DSC); lockout after 5 failures; rate limits; server-side sessions (15 min idle, 8 h absolute); httpOnly, Secure, SameSite=Strict cookies; CSRF token plus custom header; security headers (CSP, HSTS, X-Frame-Options and others); PII (PAN, mobiles, bank accounts) encrypted and masked; OIDC client with state, nonce and PKCE; adapters behind interfaces for banks, notifications, storage, scanner and KMS; dev-only controls absent from the production build |
| Backend | [backend/app/security.py](backend/app/security.py), [backend/app/routers/auth.py](backend/app/routers/auth.py), [backend/app/ratelimit.py](backend/app/ratelimit.py), [backend/app/main.py](backend/app/main.py) (headers), [backend/app/bank/interface.py](backend/app/bank/interface.py) |
| Tests | 20 in `test_auth.py`, 6 in `test_security.py`, `test_stolen_database_file_has_no_plaintext_pii`, `test_bank_accounts_masked_in_audit_trail_and_bank_log`; production-bundle search 12/12 patterns absent ([session 7](docs/verification/session7/73-final-bundle-search.txt)); `/api/sim/*` returns 404 in production mode ([session 7](docs/verification/session7/52-prod-readiness.txt)) |
| Simulated | **SIMULATED** government SSO (mock OIDC), OTP outbox, TOTP helper, DSC issuer, bank gateway |
| Limits | OWASP ZAP **not run** (image download failed); no independent penetration test; key management local; JFDR and bank interfaces are not connected |
| **Status** | Local controls **IMPLEMENTED_AND_TESTED**; external integrations **SIMULATED_EXTERNAL_DEPENDENCY** / **PLANNED** |

---

## 5. Complete Stakeholder and User Workflow

### 5.1 Roles as implemented (seeded accounts are synthetic)

| Portal role | Kernel role | Seed account | May do (enforced at API and/or kernel) | May not do |
|---|---|---|---|---|
| INSTITUTION | `institution` | `1-12345678` (ABC), `1-xyz-demo` (XYZ) | Own records only; submit FDR and PDFs; reply to observations; request release; register payee; edit permitted fields (branch, rate while pending/discrepancy; contacts) | See other institutions (404); verify; approve |
| AICTE_OFFICIAL | `section_officer` | kiran@ | Record release scrutiny; verify FDRs; raise/close observations; flag discrepancies | Approve the same request (maker-checker) |
| AICTE_OFFICIAL | `deputy_director`, `director` | meera@, sharma@ | Approve release with DSC; edit release policy | Approve a case they handled; initiate payment |
| AICTE_OFFICIAL | `finance_officer` | ravi@ | Initiate and re-issue payments; payee name look-up | Approve releases |
| AICTE_OFFICIAL | `finance_reconciliation_officer` | anil@ | Place/release scoped holds; legacy import; name look-up | — |
| AICTE_OFFICIAL | `legal_cell` | legal@ | Confirm rule packs; record rulings | — |
| AUDITOR | `internal_audit` | auditor@ | Read all records, dashboards, audit trail, reconciliation, bank messages; verify hash chains; export reports and packets; **place, review and release scoped holds** (`POST /api/holds`; kernel `place_hold`, kernel.py l. 626/642) | Approve releases, initiate payments, verify FDRs, edit records or policy (endpoints require AICTE roles) |

Any AICTE official (not only a section officer) can call FDR **verification**, but the server refuses it without a valid,
matching bank confirmation ([backend/app/domain/fdr.py](backend/app/domain/fdr.py) l. 109–118).

### 5.2 Institution journey

Sign in (password + OTP; [01-login.png](docs/screenshots/nidhiveda/01-login.png)) → dashboard with KPIs and "What changed"
([03](docs/screenshots/nidhiveda/03-dashboard-institution.png)) → upload FDR in three steps, each file pre-checked and scanned
([05](docs/screenshots/nidhiveda/05-upload-checks-and-scan.png)) → confirmation with encryption and SHA-256
([06](docs/screenshots/nidhiveda/06-upload-encryption-status.png)) → status "institution declared / pending" until the bank
confirms → reply to observations → renewal upload (`/institution/upload?renewal=…`) → release or refund request
(`/institution/release`) → payment status in plain language (`/institution/payments`) → notifications and preferences.

### 5.3 AICTE officer journey

Sign in (TOTP or DSC) → AICTE dashboard → submissions and verification queue → request bank confirmation (SIMULATED) →
compare declared vs confirmed → verify, or flag a discrepancy and raise an observation → renewals and maturity →
release: scrutiny (section officer), gate review and DSC approval (deputy director) → payments (finance officer) →
reconciliation (bank messages, signing keys, certification) → audit trail, reports, rules and policy.

### 5.4 Auditor journey

Sign in → auditor dashboard ([04](docs/screenshots/nidhiveda/04-dashboard-auditor.png)) → FDR records, compliance
review, discrepancies → audit trail with "Verify ledger integrity" ([15](docs/screenshots/nidhiveda/15-audit-trail-verify.png))
→ evidence packet PDF per FDR → reports and exports → scoped holds where audit requires them.

### 5.5 End-to-end workflow (online-deposit refund, S01)

| # | Actor | Event / decision | Evidence recorded | Resulting status |
|---|---|---|---|---|
| 1 | Institution XYZ | Requests refund of `ONL-XYZ-UG` (₹35 lakh) | Portal event `release_requested`; outbox notice to AICTE | Release request SUBMITTED |
| 2 | Section officer | Records entitlement and Affidavit-6 | Kernel events `entitlement_recorded`, `affidavit_recorded` | SCRUTINY_DONE |
| 3 | Deputy director | Reviews gate (7 mandatory checks pass); signs with DSC | DSC signature over the gate decision; `refund_authorised` | APPROVED; refund AUTHORISED |
| 4 | Finance officer | Initiates RTGS payment | `payment_initiated` | INITIATED |
| 5 | Bank (SIMULATED) | Debit advice with UTR | Signed debit advice | DEBITED, institution sees "NOT yet complete" |
| 6 | Bank (SIMULATED) | Return advice (BENEFICIARY_BANK_REJECT) | Signed return advice | REISSUE_REQUIRED, "AICTE still owes you ₹35.00 lakh"; liability reopened |
| 7 | Finance officer | Re-issues | Second attempt | INITIATED → DEBITED |
| 8 | Bank (SIMULATED) | Positive credit confirmation (N10/RTGS ack) | Signed credit confirmation | SETTLED, "Completed: your bank confirmed credit…" |
| 9 | Auditor | Verifies both chains | `/audit-trail/verify` | Both chains valid |

---

## 6. Five Most Important Differentiators

Ranked by A (relevance to SIH26265), B (technical depth shown), C (ease of explanation), D (quality of evidence).
Scores 1–5 are this dossier's judgement.

| Rank | Innovation | A | B | C | D | Total |
|---|---|---|---|---|---|---|
| 1 | Completion only on positive bank confirmation; returned refunds reopen the liability | 5 | 4 | 5 | 5 | **19** |
| 2 | Five separate answers (entitlement, attribution, availability, authorisation, completion) | 5 | 5 | 3 | 5 | 18 |
| 3 | Independent bank evidence with provenance (declared vs confirmed; signer authority; compromise) | 5 | 4 | 4 | 4 | 17 |
| 4 | Tamper-evident history + controlled release permissions (maker-checker, DSC, CoI) | 4 | 4 | 4 | 5 | 17 |
| 5 | Edition-aware rules and renewal lineage | 4 | 4 | 3 | 3 | 14 |

**Recommended opening message (primary innovation):** *"In NIDHIVEDA, a refund is complete only when the institution's
bank confirms the money arrived; if the bank returns it, the system says AICTE still owes the money."* It is the most
relevant to the brief, the simplest to explain, demonstrable live (S01), and backed by unit, scenario and browser evidence.

### 6.1 Completion only on positive confirmation (returned-refund recovery)
- **Problem:** a refund can be debited with a UTR and then returned by the beneficiary bank.
- **Conventional limitation:** a status field moves to "Paid/Completed" at debit, so a return is invisible.
- **Mechanism:** payment states AUTHORISED → INITIATED → DEBITED → SETTLED only on a signed positive credit confirmation; a return advice moves it to REISSUE_REQUIRED and reopens the liability; a return after settlement is flagged.
- **Proof:** kernel `refund_status_text` (kernel.py l. 1019–1034); `test_s01_live_returned_rtgs_refund`, `test_settlement_needs_matching_confirmation`, `test_return_after_settlement_flagged`; kernel S01 (20 checks), S02 (13); browser S01 12/12 ([session 8](docs/verification/session8/03-s01-browser.txt)); synthetic comparison: 2,000 refunds with 67 returns → self-written status-field baseline shows **67 false completions**, NIDHIVEDA's kernel **0** ([session 8 re-run](docs/verification/session8/07-compare-and-bench.txt)).
- **For a judge:** "A UTR proves the money left AICTE, not that it reached the college."
- **Visual:** [s01-3-returned-still-owed.png](docs/screenshots/nidhiveda/s01-3-returned-still-owed.png) next to [s01-4-completed.png](docs/screenshots/nidhiveda/s01-4-completed.png).
- **Limitation:** bank messages are SIMULATED; real confirmation depends on AICTE's bank providing them. The comparison baseline is written by the team, not JFDR.

### 6.2 Five separate answers
- **Problem:** one "Verified/Released" flag mixes five questions (§3).
- **Mechanism:** separate obligation, allocation, evidence, approval and completion records; the release gate lists each check with its reason ([s01-1-release-gate.png](docs/screenshots/nidhiveda/s01-1-release-gate.png)); the FDR page shows "Five answers" separately.
- **Proof:** kernel S03 (one UTR funds two obligations; 13 checks), S04 (unprovable attribution not certified; 18), S05 (scoped holds; 12); `test_hypothesis_allocation_invariants_hold_in_kernel_and_db`; DB triggers (`test_db_refuses_over_allocation_of_a_credit`, `test_pg_concurrent_allocations_cannot_both_pass`).
- **For a judge:** "Being approved is not the same as being paid, and a matching total is not proof of whose money it is."
- **Limitation:** harder to explain in 30 seconds; use the table in §3.

### 6.3 Independent bank evidence and provenance
- **Problem:** institutions often supply their own "proof" (a scan, a letter).
- **Mechanism:** each field shows its source (institution declared / bank confirmed / mismatch); only the issuing bank's registered key counts; signer validity windows and compromise dates invalidate evidence retroactively; evidence must be fresh at release (policy: 90 days, post-dating last maturity).
- **Proof:** `test_wrong_bank_cannot_confirm_another_banks_fdr`, `test_key_of_other_bank_rejected`, `test_compromised_from_invalidates_evidence_received_after`, `test_backdating_does_not_escape_compromise`; kernel S08, S09; scenario R5.
- **For a judge:** "We trust what the bank signs, not what the applicant uploads."
- **Visual:** comparison table on the FDR page (**recapture needed**); R5 scenario report.
- **Limitation:** all bank channels are SIMULATED; real coverage depends on bank participation ("wherever supported").

### 6.4 Tamper-evident history and controlled release permissions
- **Mechanism:** two SHA-256 chains, checkpoint and replay; insert-only tables; maker-checker; DSC bound to the gate decision and registered to the approver; conflict-of-interest blocking; mandatory checks not overridable; scoped holds with 30-day escalation.
- **Proof:** audit tests (§4 R09); `test_maker_checker_scrutiny_officer_cannot_approve`, `test_dsc_approval_bound_to_gate`, `test_mandatory_override_refused_logged_and_conflicts_officer`, `test_hold_escalates_after_30_days`; kernel S10, S11.
- **For a judge:** "If anyone edits ₹35 lakh to ₹0.01 lakh in the database, one click shows exactly which record was changed."
- **Visual:** [15-audit-trail-verify.png](docs/screenshots/nidhiveda/15-audit-trail-verify.png).
- **Limitation:** local checkpoint, not an RFC 3161 timestamp; does not stop collusion by authorised people.

### 6.5 Edition-aware rules and renewal lineage
- **Mechanism:** JSON rule packs per APH edition, resolved by the date of the act; UNVERIFIED / NOT_SPECIFIED / CONFLICT escalate to the legal cell; renewal lineage and gap detection; per-date "rules in force" on the timeline.
- **Proof:** `test_rules_escalate_never_guess`, `test_manual_renewal_after_maturity_escalates`; kernel S06, S07; scenario R4.
- **For a judge:** "An FDR from 2019 is judged by 2019's rules, not today's."
- **Visual:** [08-fdr-detail-timeline-no-gap.png](docs/screenshots/nidhiveda/08-fdr-detail-timeline-no-gap.png) (no live gap).
- **Limitation:** only APH 2018-19, 2024-27 and a test addendum are encoded; some clauses are marked unverified; the legal cell must confirm before enforcement.

---

## 7. Best Live Demonstration

### 7.1 S01 — returned ₹35 lakh refund (recommended)

**Sequence supported (verified):** institution request → section-officer scrutiny → deputy-director DSC approval →
finance initiation → SIMULATED debit + UTR → SIMULATED return → liability reopened → re-issue → second debit →
SIMULATED positive confirmation → Completed. Exactly the ten steps in the brief.

| Item | Detail |
|---|---|
| Users (4 browser sessions) | `1-xyz-demo` (institution, OTP), `kiran@aicte-india.org` (section officer, TOTP), `meera@aicte-india.org` (deputy director, TOTP + simulated DSC), `ravi@aicte-india.org` (finance, TOTP) |
| Routes | `/institution/release` → `/aicte/releases` (Kiran: "Record scrutiny"; Meera: "Approve with DSC") → `/aicte/payments` (Ravi: "Initiate payment", then dev-only SIMULATED bank buttons "Bank debits (issues UTR)", "Bank returns payment", "Re-issue", "Beneficiary bank confirms credit (N10)") → `/institution/payments` ("All" tab) |
| API | `POST /api/release-requests`, `/release-requests/{id}/scrutiny`, `/approve`; `/payments/{id}/initiate`, `/reissue`; dev-only `/api/sim/payments/{id}/debit`, `/return`, `/confirm`; `GET /api/payments` |
| Dataset | Fresh seed; obligation `ONL-XYZ-UG`; request `REL202600121`; refund `RF-REL202600121`; UTRs `SBINR520261024000004` (returned), `…005` (settled) |
| Messages seen by the institution | "…NOT yet complete." / "NOT complete: AICTE still owes you ₹35.00 lakh. Owner: AICTE Finance. Target re-issue: 2026-10-30." / "Completed: your bank confirmed credit on … (UTR …005)." |
| Screenshots | [s01-1](docs/screenshots/nidhiveda/s01-1-release-gate.png), [s01-2](docs/screenshots/nidhiveda/s01-2-sent-not-complete.png), [s01-3](docs/screenshots/nidhiveda/s01-3-returned-still-owed.png), [s01-4](docs/screenshots/nidhiveda/s01-4-completed.png) |
| Recorded results | Session 7: 12/12, 0 console errors ([31-s01-browser.txt](docs/verification/session7/31-s01-browser.txt)); Session 8 after the rename: 12/12, 0 console errors ([03-s01-browser.txt](docs/verification/session8/03-s01-browser.txt)) |
| Automation | `node tools/ui-checks/s01.mjs` against servers from `tools/ui-checks/serve.py --reset` |

**Suggested 60–90 s live sequence (not timed; rehearse and measure):** pre-sign-in the four users in four browser
windows; (1) institution submits the request; (2) Kiran records scrutiny; (3) Meera shows the gate's seven green checks
and approves with DSC; (4) Ravi initiates, presses "Bank debits"; (5) switch to the institution: "NOT yet complete";
(6) Ravi presses "Bank returns payment"; institution: "AICTE still owes you ₹35.00 lakh"; (7) Ravi re-issues, debit,
"Beneficiary bank confirms credit"; institution: "Completed". Close on the payment history showing both attempts.

**Dependencies and failure conditions:**
- Requires the **dev build** (`TL_ENV=dev`), because the SIMULATED bank buttons and the simulated DSC signer exist only there. Say so on screen.
- Requires a **fresh seed** (`seed.py --reset` on an isolated database): after one run, `ONL-XYZ-UG` already has a refund and cannot be requested again. `--reset` deletes its target database; never point it at real data.
- Python 3.11 venv; ClamAV/SeaweedFS are not needed for S01 itself, but `serve.py` reads the SeaweedFS container's configuration (the container must exist).
- TOTP codes expire every 30 s; OTP sends are rate-limited (5 per 15 minutes).
- Settled payments appear under the "All" tab, not "Needs attention" (a past script failure; [06a](docs/verification/session4/06a-s01-browser-attempt1-script-defect.txt)).
- The host rebooted twice during verification sessions; restart the `tl-gap-*` / `tl-baseline-s3` containers before a demo.

### 7.2 Backup demonstrations (if S01 cannot run live)
1. **Play the recorded screenshots** s01-1 → s01-4 (no dependencies).
2. **Tamper detection (kernel S11):** edit a stored credit in the database, then click "Verify ledger integrity" → the edited record is named. Dev-only `/api/sim/audit/tamper` exists. **No screenshot of the failing state exists** (only the intact state, [15](docs/screenshots/nidhiveda/15-audit-trail-verify.png)).
3. **Upload security:** upload a clean PDF (all checks pass, ClamAV clean, encrypted) and an EICAR test file (rejected, audited). Needs ClamAV running.

---

## 8. Current Canonical Demo Dataset

**All data is synthetic**, produced by [backend/app/seed.py](backend/app/seed.py) through the kernel
(`random.Random(26265)`; dates relative to the server date, "deterministic for a given date"). **Dashboard buckets are
mutually exclusive** (SQL `CASE` in `_bucket_sql`): `maturing` = status verified and maturity ≤ today + 90 days;
`active` = verified otherwise; every other bucket = the stored status. **"Active" ≠ "Verified": verified = active +
maturing.** All values below are on 2026-10-24; the bucket counts change as days pass.

Two datasets exist:
- **Seed baseline** (`backend/trustledger.db`, also any fresh `seed.py --reset`): 821 FDRs.
- **Screenshot dataset** (fresh seed + S01 + one ₹35 lakh FDR uploaded by the screenshot script): 822 FDRs. Queried read-only in `.ui-check/session8-shots/ui.db`; identical figures in the Session 7 screenshot DB.

| METRIC | CURRENT VERIFIED VALUE | DATA SOURCE | CALCULATION | SCREENSHOT | NOTES |
|---|---|---|---|---|---|
| Total institutions | 482 | `institutions` table (both DBs) | `count(*)` | 02, 04 ("Total Institutions 482") | All 482 have ≥ 1 FDR |
| Total FDRs | 821 seed / **822** screenshots | `fdrs` | `count(*)` | 04 ("Total FDRs 822") | +1 = `FDR202600372` uploaded by the screenshot run |
| Active (bucket) | 612 | `_bucket_sql` | verified ∧ maturity > today+90 | 02, 04 | ₹215.80 crore |
| Maturing in 90 days (bucket) | 56 | `_bucket_sql` | verified ∧ maturity ≤ today+90 | 02, 04 | ₹20.10 crore; 0 verified FDRs are already past maturity |
| Verified (status) | 668 | `fdrs.status='verified'` | active + maturing | not shown as one number | ₹235.90 crore |
| Pending verification | 27 seed / **28** | status | — | 02, 04 | ₹8.80 / ₹9.15 crore |
| Discrepancy | 18 | status | — | 02 alerts, 04 | ₹6.20 crore; 18 institutions |
| Released | 64 | status | — | 04 chart | ₹21.80 crore |
| Closed | 44 | status | — | 04 chart | ₹15.80 crore |
| Bucket check | 612+56+28+18+64+44 = 822 ✔ | — | sum | 04 | Percentages in 04 recompute correctly (612/822 = 74.5%, 28/822 = 3.4%, 56/822 = 6.8%) |
| Total recorded FDR value | ₹288.50 crore seed / **₹288.85 crore** | `sum(amount_paise)` | all buckets | 04 donut | **Includes released and closed instruments.** Currently held (active+maturing+pending+discrepancy) = **₹251.25 crore** (screenshot DB) |
| Open release requests | 12 (screenshot DB) / 13 (dev DB: 12 submitted + 1 approved) | stages SUBMITTED, SCRUTINY_DONE, APPROVED | count | 02, 04 ("12") | Amount ₹3.75 crore counts **FDR-linked requests only** (online-deposit requests have no FDR amount) |
| Completed release requests | 109 (108 seed + S01) | `release_requests` | count | s01-1 ("Completed: 108" before S01) | — |
| Online-deposit refunds | 4 (DEBITED 1, REISSUE_REQUIRED 1, SETTLED 2) | `refunds` | group by state | 09 (ABC's returned ₹15 lakh refund `RF-SEED-ABC`) | Seed shows payment states; S01 adds `RF-REL202600121` |
| Submission dates | 2019-05-22 → 2026-10-24 | `fdrs.submitted_on` | min/max | — | Relative to seed date |
| Issue dates | 2019-05-16 → 2026-10-19 | `fdrs.issue_date` | — | — | — |
| Maturity dates | 2024-05-11 → 2031-10-07 | `fdrs.maturity_date` | — | — | — |
| Countdown | `days_left` = maturity − server date | `serialize.fdr` | — | 08 ("Matures in 1100 days") | Server date, IST |
| Bank messages | 920, all `simulated=1` | `bank_messages` | — | "Last bank message … SIMULATED" | Range 2015-06-01 → run time |
| "Last bank message" timestamp | Time of the latest **SIMULATED** message (e.g. 24 Oct 2026, 04:43 PM in Session 7) | `max(bank_messages.received_at)` | — | 02, 04 hero | **Not a live bank synchronisation.** Institution pages use only messages that reference an FDR, so they show older times (e.g. 13 Oct) even after an S01 payment message |
| Documents | 1,617 rows, 2 with stored files | `fdr_documents` | — | 12 | Seed documents are metadata only, hence 1,402 "unverified" in the missing-documents report |
| Missing-documents report | 1,463 items: absent 61, expired 0, unverified 1,402; 468 institutions | report query | — | 12, 14 | — |
| Notifications (health, 30 days) | 61 notices, 304 deliveries, 1 acknowledged (1.6%), 6 escalated / 15 escalation notices | outbox and delivery rows | — | 11 (Session 7 values) | Synthetic activity; not a performance claim |
| Kernel events | 3,412 after a fresh seed | `kernel_events` | — | 15 | Grows with each action |

**Labelling conflicts on screen — CONFLICT — REQUIRES RESOLUTION (do not change data; fix labels or explain):**
1. **Auditor KPI "Active / Verified FDRs 612"** shows only the active bucket; 668 FDRs are verified. Same in the auditor value chart ("Active / Verified FDRs 215.80").
2. **"Active FDRs" has two meanings:** AICTE/auditor = the active bucket (612); institution dashboard = active + maturing ("live"). Not a numeric error for ABC (0 maturing), but the definition differs.
3. **"Total FDRs ₹288.85 crore"** includes released and closed instruments; do not present it as money currently held.
4. **"Release Requests 12 · ₹3.75 crore"**: the amount excludes online-deposit requests.
5. **Within the same screenshot run**, the institution dashboard (captured first) shows 2 FDRs for ABC, while AICTE/auditor dashboards (captured after the upload) include the third (`FDR202600372`).
6. **Institution "Last bank message"** does not reflect payment messages (stale relative to S01).

---

## 9. Verified System Architecture

| Layer | Implemented technology | Evidence |
|---|---|---|
| Frontend | React 19.3.1, TypeScript 6.0.3, Vite 8.3.5, React Router 6.30.6, Recharts, Framer Motion, lucide icons; custom CSS tokens (light/dark); English/Hindi | `frontend/package.json`, installed versions |
| API | FastAPI 0.162.0, Pydantic 2.14.1; Python **3.11.17** (standalone, rebuilt in Session 6/7) | `.venv`; [session 7 versions](docs/verification/session7/15-pillow-versions.txt) |
| Authentication | Argon2id passwords; server-side sessions; second factor: OTP (6 digits, 5 min), TOTP (RFC 6238), DSC (X.509 chain, key usage, signature over a server challenge); OIDC client (state, nonce, PKCE) | [backend/app/security.py](backend/app/security.py), [backend/app/routers/auth.py](backend/app/routers/auth.py) |
| DSC signing | Real certificate and signature verification; certificates issued by a **SIMULATED** local test CA | `backend/devcerts/` (gitignored), `issue_dev_dsc` |
| Persistence | SQLAlchemy 2.1.6, Alembic 1.20.1 (migrations 0001–0006); SQLite (dev) and PostgreSQL 16.15 (tested) | [backend/migrations/versions/](backend/migrations/versions/) |
| Event sourcing and audit | Kernel events persisted 1:1 and replayed on start-up; two SHA-256 chains; local checkpoint file | [backend/app/ledger.py](backend/app/ledger.py), [backend/app/portal_audit.py](backend/app/portal_audit.py) |
| Financial constraints | Integer paise; DB triggers: Σ allocations ≤ credit and ≤ required; returned payments not allocatable; unique UTR per debit and FDR number per bank; insert-only event tables; atomic event and projection writes | [backend/app/invariants.py](backend/app/invariants.py) |
| Control kernel | `trust-ledger-kernel/trustledger` (unchanged; 48 files, manifest `58406d49…fd387c0`) | [session 8 hash](docs/verification/session8/06-kernel-hash.txt) |
| PDF validation | pypdf 6.21.2 plus byte checks | `documents.run_checks` |
| Malware scanning | ClamAV 1.4.6 over clamd INSTREAM (real, local container); dev stub only for dev/scenario runs | [backend/app/scanner.py](backend/app/scanner.py) |
| Encryption | AES-256-GCM envelope (per-document DEK wrapped by KEK); HKDF field key for PII; blind index | [backend/app/crypto.py](backend/app/crypto.py) |
| Object storage | SeaweedFS 3.97 via the S3 API (`minio` client); MinIO named in the design; no object lock | [backend/app/storage.py](backend/app/storage.py); [docs/security.md](docs/security.md) §4 |
| Scheduling | APScheduler: nudge worker, kernel tick, escalation, daily reminders, digest | [backend/app/scheduler.py](backend/app/scheduler.py) |
| Notification outbox | Transactional outbox, leases, idempotency keys, retries | [backend/app/nudge/worker.py](backend/app/nudge/worker.py) |
| Rules engine | Kernel resolver over JSON rule packs by date | `trust-ledger-kernel/data/rules/*.json` |
| Bank gateway | Abstract interface; **SIMULATED** implementation (12 banks, Ed25519) | [backend/app/bank/interface.py](backend/app/bank/interface.py), `simulator.py` |
| PDF generation | reportlab 5.1.0 (Pillow 13.0.0) | [backend/app/pdf.py](backend/app/pdf.py) |
| Testing | pytest + Hypothesis; kernel mutation harness; Playwright-core browser scripts; axe-core | `backend/tests/`, `tools/ui-checks/` |
| Deployment | Local only: `backend/Dockerfile`, `backend/docker-compose.yml` (PostgreSQL 16, SeaweedFS, ClamAV, Mailpit); no hosted deployment | — |

**Planned in the kernel design but not built:** Next.js, Tailwind, ECharts, Keycloak, row-level security, MinIO object
lock ([trust-ledger-kernel/solution_final.md](trust-ledger-kernel/solution_final.md) §11). The built frontend is React +
Vite with its own authentication.

```mermaid
flowchart TD
    subgraph Users
      I[Institution]:::u
      O[AICTE officers<br/>scrutiny / approver / finance / reconciliation / legal]:::u
      A[Auditor]:::u
    end
    I & O & A --> UI[React + Vite UI<br/>role dashboards, EN/HI]
    UI -->|HTTPS, session cookie,<br/>CSRF + X-TL-Client| API[FastAPI API<br/>auth + 2FA, role & kernel-role checks,<br/>institution scoping]
    API --> K[Control kernel (unchanged)<br/>evidence, allocation, release gate,<br/>payments, rules, holds]
    K --> DB[(SQLite / PostgreSQL 16<br/>events + projections,<br/>triggers, 2 hash chains)]
    API --> DB
    API --> DOC[PDF checks → ClamAV → SHA-256 →<br/>AES-256-GCM envelope]
    DOC --> S3[(SeaweedFS S3<br/>ciphertext only)]
    DB --> OUT[Notification outbox + worker<br/>ladder, escalation, digests]
    OUT --> PROV[SIMULATED e-mail / SMS /<br/>WhatsApp / push; Mailpit sink]
    BANK[SIMULATED bank gateway<br/>Ed25519-signed messages] -->|signed evidence| API
    IDP[SIMULATED mock OIDC + test DSC CA] -.-> API
    classDef u fill:#eef,stroke:#88a
```

**Trust boundaries:** (1) browser ↔ API (authentication, CSRF, rate limits); (2) API ↔ kernel (every money command passes
role, maker-checker and evidence checks); (3) bank → API (only signed messages from a registered, unrevoked key);
(4) API ↔ storage (ciphertext only; key outside the store); (5) API → providers (simulated; idempotent);
(6) database ↔ audit verifier (chains and checkpoint detect changes made outside the API).

---

## 10. Security and Financial Controls

| Control | Where | Test evidence |
|---|---|---|
| Argon2id; generic login errors; lockout after 5 failures | `security.py`, `auth.py` | `test_password_is_argon2id`, `test_generic_error_does_not_reveal_account`, `test_lockout_after_five_failures_then_timed_unlock` |
| Mandatory 2FA (OTP single use, expiry, attempts, rate limit; TOTP; DSC) | same | `test_mfa_is_mandatory`, `test_otp_*` (4), `test_totp_login`, `test_dsc_login_and_wrong_certificate`, `test_dsc_signature_over_different_message_rejected` |
| Sessions, cookies, CSRF | `deps.py` | `test_session_idle_timeout`, `test_session_cookie_flags`, `test_csrf_required_on_state_change`, `test_logout_revokes_session` |
| Rate limits, security headers | `ratelimit.py`, `main.py` | `test_login_is_rate_limited_per_address`, `test_otp_verification_is_rate_limited`, `test_security_headers_on_api_responses`, `test_link_resolution_is_rate_limited` |
| IDOR protection (404) | `institution_scope` | `test_idor_institution_cannot_read_other_institution`, `test_document_access_is_scoped_per_institution` |
| PII encryption and masking | `crypto.py` | `test_stolen_database_file_has_no_plaintext_pii`, `test_pii_change_is_masked_in_history_and_encrypted_at_rest` |
| Money invariants in kernel and DB | `invariants.py` | `test_db_refuses_*` (3), Hypothesis tests (2), `test_pg_trigger_blocks_over_allocation`, `test_pg_concurrent_allocations_cannot_both_pass` |
| Rollback on storage refusal | `ledger.py` | `test_ledger_rolls_back_memory_when_db_refuses` |
| Maker-checker, DSC, CoI, override refusal | `release.py`, kernel | §6.4 tests |
| Scoped holds with 30-day escalation | kernel, `ledger_api.py` | `test_holds_scoped_and_role_limited`, `test_hold_escalates_after_30_days` |
| Dev-only controls absent in production | `main.py` (`/api/sim` dev only), Vite dev guards | [bundle search 12/12 absent](docs/verification/session7/73-final-bundle-search.txt); `/api/sim/*` 404 in prod ([52](docs/verification/session7/52-prod-readiness.txt)); production login shows no dev text ([session 8](docs/verification/session8/05-login-production.txt)) |

**Not established:** OWASP ZAP (never ran: image download timed out twice, [48-zap-status.txt](docs/verification/session7/48-zap-status.txt));
independent penetration test; production key management; WORM retention; trusted timestamping; resistance to collusion
by authorised users. Full threat model: [docs/security.md](docs/security.md).

---

## 11. Testing and Validation Evidence

Counts are kept separate: **test cases** (pytest-collected), **scenarios**, and **checks** (assertions inside scenarios).
Do not add them together.

| TEST NAME | RESULT | DATE | COMMAND | EVIDENCE FILE | LIMITATION |
|---|---|---|---|---|---|
| Backend suite, SQLite, all real services required | **147 passed**, 0 skipped | 2026-10-24 (S7; re-run S8 after rename) | `.venv/bin/python tools/baseline/backend_check.py sqlite` | [S7 60](docs/verification/session7/60-final-sqlite-metrics.txt), [S8 01](docs/verification/session8/01-backend-sqlite-after-rename.txt) | 147 collected cases from 126 functions (parametrised); 1 Starlette deprecation warning |
| Backend suite, PostgreSQL 16.15 | **147 passed**, 0 skipped | same | `… backend_check.py postgres` | [S7 59](docs/verification/session7/59-final-postgres-metrics.txt), [S8 02](docs/verification/session8/02-backend-postgres-after-rename.txt) | Disposable DB per run |
| Kernel unit/property tests | 67 passed | S7 | `tools/baseline/kernel_check.py` (scratch copy) | [20-final-kernel.txt](docs/verification/session7/20-final-kernel.txt) | 4 warnings |
| Kernel scenarios | 13 scenarios, **161 checks**, 0 failed | S7 | `python -m trustledger.scenario` | same | Synthetic |
| Kernel mutation | **32/33 killed** | S7 | `trust-ledger-kernel/tools/mutants.py` (scratch) | [kernel-mutants.txt](docs/verification/session7/kernel-mutants.txt) | Survivor: "payment re-issue skips evidence re-check" (blocked independently by two other controls) |
| Kernel integrity | 48 files match ZIP; manifest `58406d49…fd387c0` | S7, S8 | hash script | [84](docs/verification/session7/84-final-kernel-and-services.txt), [S8 06](docs/verification/session8/06-kernel-hash.txt) | — |
| Required SIH scenarios R1–R6 | 6 scenarios, **52 checks**, 0 failed | 2026-10-24 16:58 | `backend/scripts/run_required_scenarios.py` | [docs/scenario-report.md](docs/scenario-report.md) | Scanner stub, simulated bank/clock, filesystem storage |
| Kernel-wrapper business scenarios S01–S09 | 9 scenarios, **115 checks** | S7 | `backend/scripts/run_scenarios.py` | [34-scenario-output.txt](docs/verification/session7/34-scenario-output.txt) | Simulated bank |
| Browser S01, four users | **12/12 checks**, 0 console errors | S7 16:43; S8 after rename | `node tools/ui-checks/s01.mjs` | [S7 31](docs/verification/session7/31-s01-browser.txt), [S8 03](docs/verification/session8/03-s01-browser.txt) | Dev build; simulated bank and DSC issuer |
| Nudge pages vs direct SQL | 7/7 | S7 | `live_data.mjs` | [71](docs/verification/session7/71-nudge-sql-final.txt) | — |
| PDF SIMULATED labels | 8/8 (7 labelled + 1 control) | S7 | `pdf_check.mjs` | [70](docs/verification/session7/70-pdf-labels-final.txt) | — |
| Document security tests | 8 + 3 precheck + 2 integrity + 1 outage, plus 2 real-service | S7/S8 suites | in the backend suite | — | — |
| Authorization tests | 20 auth + 6 security + role tests | same | same | — | — |
| Accessibility (axe-core, WCAG 2 A/AA tags) | 42 routes × 2 themes, **0 violations**, 0 console errors; 18 panel/editor views × 2 themes, 0 violations | S7 16:56–16:58 | `node tools/ui-checks/axe.mjs [--theme dark]` | [68](docs/verification/session7/68-axe-light-complete.txt), [69](docs/verification/session7/69-axe-dark-complete.txt), [66](docs/verification/session7/66-axe-panels-light-final.txt), [76](docs/verification/session7/76-axe-panels-dark-complete.txt) | Automated only; **not re-run after the S8 sidebar/rename change** |
| Integrity: audit chains + replay | Valid | S7, S8 | `/api/audit-trail/verify` | S01 logs; [S8 08](docs/verification/session8/08-audit-verify-shot.txt) | Local checkpoint |
| Migrations 0006 | Fresh SQLite, fresh PostgreSQL, dev-DB copy: pass | S7 | `tools/baseline/migration_check.py` | [22](docs/verification/session7/22-final-migrations.txt) | — |
| Python dependency audit | 56 distributions, **0 advisories** (Pillow 13.0.0) | S7 | pip-audit | [61](docs/verification/session7/61-audit-json-summary.txt) | Python 3.11+ required |
| npm audit | 0 high/critical, **2 moderate** (react-router) | S7 | `npm audit` | [33](docs/verification/session7/33-npm-audit.txt) | Router 7 migration planned |
| gitleaks | Source set (506 files): **no leaks**; whole directory: 430 findings in ignored local secrets/dependencies | S7 | gitleaks 8.18.4 | [80](docs/verification/session7/80-source-secret-final.txt), [50](docs/verification/session7/50-secret-summary.txt) | Whole-directory scan not clean |
| Production build + dev-control search | Build passes; 12/12 patterns absent | S7 (build re-run S8) | `npm run build`; `bundle_check.py` | [64](docs/verification/session7/64-build-final.txt), [73](docs/verification/session7/73-final-bundle-search.txt) | Bundle search not re-run after the rename |
| Synthetic design comparison | 2,000 refunds / 67 returns: baseline 67 false completions, kernel 0; 10,200 legacy records: baseline marks 190 wrong-owner and 3,024 unevidenced as Verified, kernel certifies 0 wrong-owner | S8 re-run, identical to saved result | `python tools/compare_and_bench.py` (scratch copy) | [S8 07](docs/verification/session8/07-compare-and-bench.txt) | The baseline was written by the team; it is **not JFDR** |
| OWASP ZAP baseline | **NOT RUN** | S6, S7 | `docker pull ghcr.io/zaproxy/zaproxy:stable` timed out | [48](docs/verification/session7/48-zap-status.txt) | Outstanding |

**Four strongest statistics for the PPT:**
1. **147 automated backend tests pass on both SQLite and PostgreSQL 16, with zero skips**, using real ClamAV, S3 storage and SMTP sink.
2. **Four-user browser run of the ₹35 lakh returned-refund scenario: 12/12 checks**; "Completed" appears only after the bank's positive credit confirmation.
3. **Kernel: 13 business scenarios / 161 checks; 32 of 33 seeded control faults caught by the tests** (mutation testing).
4. **Synthetic comparison: 0 false refund completions versus 67 for a status-field design** (2,000 refunds, 67 returns), with the caveat that the baseline is the team's own model.

---

## 12. Feasibility and Deployment Boundaries

**COMPLETE WORKING PROTOTYPE** (now): the full application runs locally with real authentication, 2FA, encryption,
malware scanning, object storage, hash-chained audit, notification logic and all workflows in §5, on synthetic data.

**AUTHORIZED PRODUCTION DEPLOYMENT** (not yet): needs the external parties and approvals below.

| Dimension | Assessment | Evidence / dependency |
|---|---|---|
| Technical | Implemented and tested end to end (§4, §11) | Test logs |
| Operational | Roles map to existing AICTE functions (scrutiny, competent authority, finance, legal cell, audit). Institutions keep their current steps (upload, Affidavit-6), with clearer status. Officers work from queues and a release gate instead of files | §5; needs AICTE process owners to confirm role mapping |
| Integration | Interfaces exist for banks, KMS, notifications, storage and scanner. Phases: **(1)** shadow mode reading exported JFDR/legacy registers (legacy import exists) with no live effect; **(2)** AICTE's own banker for credit/debit/return advices and name look-up; **(3)** issuing banks for FDR confirmations and lien discharge "wherever supported"; **(4)** JFDR read/write adapter once access and specifications are granted | `POST /api/legacy/import`; [bank/interface.py](backend/app/bank/interface.py); JFDR existence per §3 |
| Economic | Resources: one API service, PostgreSQL with backups/HA, S3-compatible store with object lock, ClamAV, SMS/e-mail gateways, KMS/HSM, monitoring, support staff. **No cost or saving figures are claimed**; quotations and portfolio size are needed | Kernel design §12 lists cost drivers only |
| Regulatory | Legal-cell confirmation of rule packs and policy defaults; AICTE authorisation of bank channels; CCA-trusted DSC; e-Pramaan/DigiLocker registration; DLT SMS registration; CERT-In-empanelled security audit; data-protection review for PII | [docs/security.md](docs/security.md) §5–6 |

| Unresolved dependency | Mitigation / phase |
|---|---|
| Real bank confirmations, credits, returns | Start with AICTE's own bank; signed file exchange (SFTP/H2H) before APIs; keep SIMULATED labels until then |
| JFDR access | Shadow mode on exported data; adapter after specifications |
| CCA DSC, CRL/OCSP | Use existing officer DSC tokens; add revocation checks |
| Government SSO | Register an e-Pramaan/DigiLocker OIDC client (client code exists) |
| KMS/HSM | Implement the existing `Kms` interface with NIC/cloud HSM |
| WORM, trusted timestamps | Enable S3 Object Lock; RFC 3161 anchoring of chain heads (CCA timestamping guidelines) |
| Security acceptance | Complete ZAP; independent penetration test |
| Scale | PostgreSQL HA; shared rate-limit store (Redis) for multiple API processes |

---

## 13. Measurable Impact and Benefits

| Benefit | Status | Evidence |
|---|---|---|
| No false "Completed" refund after a bank return | **DEMONSTRATED_ON_SYNTHETIC_DATA** | 0 vs 67 (comparison); S01 browser 12/12 |
| Wrong-owner legacy credits not certified | DEMONSTRATED_ON_SYNTHETIC_DATA | 0 vs 190 (10,200-record synthetic migration) |
| Safer verification (no verify without matching bank evidence) | DEMONSTRATED_ON_SYNTHETIC_DATA | R1, R5; `test_valid_confirmation_then_verify` |
| Better discrepancy identification | DEMONSTRATED_ON_SYNTHETIC_DATA | R5; field-level comparison |
| Earlier maturity visibility | DEMONSTRATED_ON_SYNTHETIC_DATA | 90/60/30/7-day reminders; R2, R3 |
| Traceable financial approvals | DEMONSTRATED_ON_SYNTHETIC_DATA | Gate + DSC + chains |
| Faster audit evidence retrieval | EXPECTED_BENEFIT | One-click evidence packet exists; retrieval time not measured |
| Reduction in manual follow-up | EXPECTED_BENEFIT | Automated ladder; no baseline |
| Improved record consistency | EXPECTED_BENEFIT | Single repository; DB invariants |
| Verification or turnaround time | **UNVERIFIED** | Never measured against a baseline |

**How an AICTE pilot could measure it:** agree a baseline period on the current process; then run shadow mode on the same
cases. Measure: submission-to-first-review and evidence-complete-to-verification times (median and 90th percentile,
excluding bank waiting time); staff touches and follow-up letters per case; renewals confirmed before maturity; refunds
shown complete before beneficiary credit; time to assemble an audit packet. AICTE sets go/no-go thresholds in advance.

**Strongest quantitative impact statement for the PPT:** *"On 2,000 synthetic refunds with 67 bank returns, a status-field
design shows 67 refunds as completed that were never received; NIDHIVEDA shows none."* (Caveat on the slide: synthetic
data; baseline modelled by the team.)

---

## 14. Competitive Positioning

| EXISTING APPROACH | OUR CONTROL | PRACTICAL BENEFIT | EVIDENCE |
|---|---|---|---|
| One status field per record (generic portal design; **JFDR internals not seen**) | Five separate answers with their own evidence | An approval is never read as payment | §3; kernel S03–S05 |
| Institution uploads its own proof | Bank-signed confirmation, field-level comparison, signer registry | Forged or stale letters do not verify | R5; S08, S09 |
| Refund "Paid" at debit/UTR | Completion only on positive credit confirmation; returns reopen liability | No false completions | S01; comparison 0 vs 67 |
| Rules applied as of today | Edition-aware rule packs; escalate when unverified | Old FDRs judged by their own rules | S06, S07 |
| Editable logs | Two hash chains, checkpoint, replay | Tampering is detected and located | S11; audit tests |
| Manual reminders | Outbox ladder with escalation and acknowledgement | Unanswered notices reach a responsible officer | R3, R4; test_nudge |
| Document management systems (generic) | Content checks, malware scan, envelope encryption, SHA-256 re-check | Unsafe or altered files are refused | R02 tests |

**Adjacent infrastructure (do not overclaim):** NeSL e-BG and SFMS IFN 760COV serve **bank guarantees**; the repository's
research found no standard SFMS message for FDRs. **Do not claim these support FDRs.** Account Aggregator: AICTE is
not an eligible FIU (repository research). A public GitHub prototype for the same PS exists (`ayus0109/AICTE-FDR-portal`);
its claims were not tested by the team, so **do not cite weaknesses of it as fact**. All of these points come from
[trust-ledger-kernel/solution_final.md](trust-ledger-kernel/solution_final.md) §6–7 and were not re-verified in this
session (**requires research** before quoting).

---

## 15. Recommended Prototype Screenshots

### 15.1 Inventory

Current set: `docs/screenshots/nidhiveda/` (session 8; NIDHIVEDA name, fixed sidebar; 1536×1024). Session 7 originals
with the same file names are in `docs/screenshots/final/` (old name). Older images: `docs/screenshots/*.png`
(pre-session-3 UI, old name) and `docs/screenshots/historical/`. Mockups (`design/*.png`) are **not** running-app evidence.

| File (nidhiveda/) | Screen | Role | Feature | Matches current UI | SIMULATED labelled | Sensitive data | Projector | Suggested slide |
|---|---|---|---|---|---|---|---|---|
| 01-login.png | Login (production build) | — | 2FA choice, SSO button | Yes | n/a | None | Good | 1 or 2 |
| 02-dashboard-aicte.png | AICTE dashboard | Deputy director | KPIs, What changed, alerts | Yes | Yes (hero) | Synthetic names | Good (dense) | 2 |
| 03-dashboard-institution.png | Institution dashboard | ABC | Own deposits, status | Yes | Yes | Synthetic | Good | 2 |
| 04-dashboard-auditor.png | Auditor dashboard | Auditor | Distribution charts | Yes; **label issue** (§8 #1) | Yes | Synthetic | Good | 5 |
| 05-upload-checks-and-scan.png | Upload, step 2 | Institution | 6 checks, ClamAV, encryption pending | Yes; **dev-only link visible** | n/a | Hashes only | Good | 3 |
| 06-upload-encryption-status.png | Upload done | Institution | Scan, AES-256-GCM, SHA-256 | Yes | Yes (footer) | Hashes | Good | 3 |
| 07-fdr-detail-documents.png | FDR detail | Deputy director | Documents, SHA-256 match, timeline | Yes | — | Hashes | Good | 3 |
| 08-fdr-detail-timeline-no-gap.png | FDR detail | Deputy director | Timeline, rules in force | Yes; **no gap shown** | — | — | Fair | 3 (caveat) |
| 09-notification-centre.png | Notification centre | Institution | Ladder, returned-refund notice | Yes; notice text uses "Rs 15.00 lakh" | Yes | Synthetic | Good | 2 |
| 10-escalations.png | Escalations | Deputy director | Escalation chain | Yes | — | Synthetic | Good | 2 |
| 11-notification-health.png | Health | Deputy director | Delivery evidence | Yes; **right table cut off** | Yes (per provider) | — | Fair | 5 (optional) |
| 12-missing-documents.png | Missing documents | Deputy director | Exceptions report | Yes | Yes | Synthetic | Good | 5 |
| 13-rules-policy-editor.png | Rules & policy | Deputy director | Before/after policy editors | Yes | — | — | Good | 3 |
| 14-pdf-export-missing-documents.png | PDF page 1 | — | Export with "SIMULATED bank data" | Yes | **Yes** | Synthetic | Good | 5/6 |
| 15-audit-trail-verify.png | Audit trail | Auditor | Chains intact, checkpoint, replay | Yes | — | Hash prefixes | Good | 3 or 5 |
| s01-1-release-gate.png | Release gate | Deputy director | 7 mandatory checks, DSC approve | Yes | — | Synthetic | Good | 2/3 |
| s01-2-sent-not-complete.png | Payments | Institution XYZ | "NOT yet complete" | Yes | Yes | ID shows `1-xyz-demo` | Good | 2 |
| s01-3-returned-still-owed.png | Payments | Institution XYZ | "AICTE still owes you ₹35.00 lakh" | Yes; footer bank time stale (§8 #6) | Yes | `1-xyz-demo` | Good | **2 (hero)** |
| s01-4-completed.png | Payments | Institution XYZ | Completed on credit confirmation | Yes | Yes | `1-xyz-demo` | Good | **2 (hero)** |

### 15.2 Best picks
1. Institution: [03-dashboard-institution.png](docs/screenshots/nidhiveda/03-dashboard-institution.png) or [06-upload-encryption-status.png](docs/screenshots/nidhiveda/06-upload-encryption-status.png)
2. AICTE officer verification: [s01-1-release-gate.png](docs/screenshots/nidhiveda/s01-1-release-gate.png) (a declared-vs-bank comparison screenshot does **not** exist; recapture recommended)
3. Auditor evidence: [15-audit-trail-verify.png](docs/screenshots/nidhiveda/15-audit-trail-verify.png)
4. Returned refund: [s01-3-returned-still-owed.png](docs/screenshots/nidhiveda/s01-3-returned-still-owed.png) + [s01-4-completed.png](docs/screenshots/nidhiveda/s01-4-completed.png)
5. Document security: [07-fdr-detail-documents.png](docs/screenshots/nidhiveda/07-fdr-detail-documents.png)
6. Test results: no screenshot exists; use a table built from §11 or capture a terminal showing `147 passed` from [docs/verification/session8/01-backend-sqlite-after-rename.txt](docs/verification/session8/01-backend-sqlite-after-rename.txt)

### 15.3 Recapture recommended
- 05 on the production build (removes the dev-only link; needs a production upload flow with a real sign-in).
- A declared-vs-bank comparison view with a MISMATCH row (R5 data).
- 11 at a wider viewport or cropped to the channel table.
- A tamper-detected state of the audit trail (only on an isolated database).
- Optionally rename the XYZ seed ID `1-xyz-demo` if "demo" on a slide is unwanted (seed change; not done).

---

## 16. Six-Slide SIH Content Bank

### Slide 1 — Title
- **Takeaway:** NIDHIVEDA: a trustworthy security-deposit and FDR portal for AICTE.
- **Facts:** PS SIH26265, AICTE, Software / Smart Automation; working prototype; three roles (institution, AICTE officers, auditor).
- **Visual:** [01-login.png](docs/screenshots/nidhiveda/01-login.png).
- **Numbers:** none needed.
- **Sources:** §1.
- **Do not claim:** an official AICTE product or endorsement; a team name, ID or college not supplied.
- **Open questions:** team name, team ID, college, member list (**REQUIRES TEAM INPUT**); exact official PS title.

### Slide 2 — Proposed Solution
- **Takeaway:** each stage has its own evidence; completion means the money arrived.
- **Facts:** (1) declared vs bank-confirmed fields, verification refused without valid bank evidence; (2) release gate + maker-checker DSC approval; (3) refund "Completed" only on positive credit confirmation, returns reopen the liability.
- **Visual:** s01-3 + s01-4 side by side; optionally s01-1.
- **Numbers:** ₹35 lakh S01; 7 mandatory gate checks.
- **Sources:** §5.5, §6.1, [S8 S01 log](docs/verification/session8/03-s01-browser.txt).
- **Do not claim:** live bank integration; "fraud-proof"; "first in the world".
- **Open:** how JFDR would host or link the module (mentor input).

### Slide 3 — Technical Approach
- **Takeaway:** a control kernel with hash-chained events behind a secured API.
- **Facts:** (1) React + FastAPI + PostgreSQL 16; unchanged kernel with event sourcing; (2) PDF checks → ClamAV → SHA-256 → AES-256-GCM → S3; (3) two SHA-256 chains with replay; DB-level money invariants.
- **Visual:** Mermaid diagram (§9); 07 or 15.
- **Numbers:** 2FA mandatory; 6 content checks per file.
- **Sources:** §9, §10.
- **Do not claim:** Next.js, Keycloak or MinIO object lock (planned, not built); production KMS.
- **Open:** hosting target (NIC / empanelled cloud).

### Slide 4 — Feasibility and Viability
- **Takeaway:** complete working prototype; production needs authorised integrations, not new invention.
- **Facts:** (1) everything in §4 runs and is tested locally; (2) bank, SSO, DSC issuer and notification providers are SIMULATED behind interfaces; (3) a phased path: shadow mode → AICTE's bank → issuing banks → JFDR.
- **Visual:** a "real vs SIMULATED" table (§9, §12).
- **Numbers:** 147/147 on two databases.
- **Sources:** §12; [docs/security.md](docs/security.md).
- **Do not claim:** costs, savings, timelines or bank agreements.
- **Open:** AICTE portfolio size; bank channel options; JFDR operator.

### Slide 5 — Impact and Benefits
- **Takeaway:** fewer false completions, earlier warnings, faster audit answers.
- **Facts:** (1) 0 vs 67 false refund completions (synthetic); (2) 90/60/30/7-day reminders with escalation; (3) one-click evidence packet and integrity verification.
- **Visual:** 04 (with the label caveat) or 12; 14 (SIMULATED-labelled PDF).
- **Numbers:** 0 vs 67; 0 vs 190 wrong-owner certifications (synthetic).
- **Sources:** §13; [S8 07](docs/verification/session8/07-compare-and-bench.txt).
- **Do not claim:** measured time savings or percentage effort reductions.
- **Open:** pilot metrics agreed with AICTE.

### Slide 6 — Research and References
- **Takeaway:** grounded in AICTE rules and audit guidance; validated by tests.
- **Facts:** (1) APH 2024-27 Cl. 1.12, Table 1.4, Cl. 6.46; (2) JFDR exists (AICTE portal manual, 2018 RFP); (3) audit guidance on direct bank confirmation (CAG/Kerala AG circular, ICAI 2022).
- **Visual:** the four statistics from §11.
- **Numbers:** 147, 12/12, 161 checks, 32/33.
- **Sources:** §17.
- **Do not claim:** that sources were re-verified unless the team re-opens them; the 2026 IDFC FIRST case is context only, not linked to this PS.
- **Open:** official SIH PS page check.

---

## 17. Research and Primary References

These are the references collected by the team in
[trust-ledger-kernel/solution_final.md](trust-ledger-kernel/solution_final.md) ("Sources"; ✅ = marked verified there,
🟡 = partly). **None was re-opened in this session**; confirm each link before citing it on a slide.

| Topic | Reference | Status in repo |
|---|---|---|
| Security deposit rules (Cl. 1.12, Table 1.4, 1.10(b), 2.3.2, 6.46) | APH 2024-27 — https://cdnbbsr.s3waas.gov.in/s35938b4d054136e5d59ada6ec9c295d7a/uploads/2025/03/2025031399.pdf | ✅ (Cl. 6.46 earlier sub-clauses 🟡) |
| Older editions | APH 2020-21 — https://epsiindia.org/wp-content/uploads/2019/01/APH-2020_21.pdf; APH 2018-19 — https://www.aicte.gov.in/sites/default/files/APH%202018-19%20Modified.pdf | 2018-19 not opened |
| Affidavit-6 / Affidavit-9 | https://www.aicte-india.org/bureaus/approval/approal-process-2024-25/approval-process-2024-25-attachments | ✅ |
| Online security-deposit steps | https://aicte.gov.in/sites/default/files/Security_Deposit.pdf | ✅ |
| Multi-programme deposits | AICTE FAQ — https://aicte.gov.in/sites/default/files/FAQ%20Updated.pdf | ✅ |
| JFDR existence | AICTE help manual 2011-12; AICTE e-Gov RFP 2018 §7.2.2 — https://aicte.gov.in/sites/default/files/RFPeGov.pdf | ✅ (current operator ❓) |
| 2026-27 addendum | Careers360 report | 🟡 official PDF not opened |
| Audit guidance | CAG / Kerala AG (Audit-II) circular; ICAI external confirmations (7 Sep 2022); ISA 505 | ✅ |
| Payments | RBI NEFT process (DPSS CO EPPD No.168, 2010); RBI name look-up circular; SBI RTGS FAQ (link not kept) | Partly |
| PKI / time-stamping | CCA PKI services; CCA time-stamping guidelines | ✅ |
| Bank guarantees (adjacent) | NeSL e-BG (Mondaq); GeM / NSE SFMS formats | ✅ |
| Fraud context only | IDFC FIRST Bank Chandigarh 2026 (IANS, FilingReader, WION) | Context; not linked to the PS |
| SIH problem statement | Tracker https://zaidsayyed.in/tools/sih-problem-statements/sih26265; official https://sih.gov.in/sih2026PS returned 403 | **Requires verification** |

Internal evidence references: [TEST_REPORT.md](TEST_REPORT.md), [docs/FINAL_REPORT.md](docs/FINAL_REPORT.md),
[CHANGELOG.md](CHANGELOG.md), [docs/scenario-report.md](docs/scenario-report.md), [docs/security.md](docs/security.md),
[docs/notifications.md](docs/notifications.md), [docs/verification/](docs/verification/).

---

## 18. Expected Judge Questions and Evidence-Based Answers

| Question | Answer | Evidence |
|---|---|---|
| Is this connected to real banks? | No. All bank messages are SIMULATED, signed with test keys, and labelled. The interface is ready for AICTE-authorised channels. | §4 R03; `bank/interface.py` |
| AICTE already has JFDR. Why this? | We do not replace JFDR; we add evidence controls that a status field cannot hold, and propose integration with or hosting inside JFDR. | §3, §12 |
| How do you know a refund reached the college? | Only the beneficiary bank's positive credit confirmation completes it; a debit/UTR is "NOT yet complete". | S01 |
| What if an officer colludes? | Maker-checker, conflict-of-interest blocking, DSC binding and hash chains make it visible and attributable; they do not prevent collusion by authorised people. | §6.4, §10 |
| Can someone edit the database directly? | The change is detected and located by chain verification and replay. | S11; audit tests |
| How secure are documents? | PDF-only checks, ClamAV, AES-256-GCM per-document keys, ciphertext-only storage, SHA-256 re-check. Keys are local today; KMS planned. | R02 |
| Has it been security-tested? | Automated tests, dependency and secret scans; ZAP not completed; no independent penetration test yet. | §11 |
| What are your numbers based on? | Synthetic seed data; real AICTE portfolio size is unknown. | §8 |
| How much time does it save? | Not measured; we propose a pilot with a baseline. | §13 |
| Does it scale? | In a synthetic run the kernel imported 10,200 legacy records (29,377 events) in 1.5 s (2.7 s in the saved run), single process; this is not a load test. Production needs PostgreSQL HA and load testing. | [S8 07](docs/verification/session8/07-compare-and-bench.txt) |
| Is it accessible? | 0 axe violations on 42 routes in both themes (automated); manual assistive-technology testing pending. | §11 |
| Hindi support? | Yes: UI and notification templates. | `frontend/src/lib/hi.ts`, `nudge/templates.py` |

---

## 19. Missing Information and Contradictions

**Requires team input:** team name, team ID, college, members/mentor (if the template needs them), repository URL,
demo URL or video, confirmation of the official PS wording.

**Contradictions and issues found (unresolved):**
1. Dashboard label conflicts (§8, items 1–6). **CONFLICT — REQUIRES RESOLUTION** (labels, not data).
2. Notification health panel (Session 7 screenshot): in-app "Sent 74" but "Delivered (receipt) 82" (8 batched); push "Total 50, Sent 0" — the semantics of "sent" for in-app need explanation before showing.
3. Notification text says "Rs 15.00 lakh" while payment pages show "₹" (formatting applied only on payment pages).
4. Source-set gitleaks counts differ between runs: 445 files ([39](docs/verification/session7/39-source-secret-scan.txt)) vs 506 ([80](docs/verification/session7/80-source-secret-final.txt), later). Both clean.
5. The kernel design (`solution_final.md` §11) lists a Next.js/Keycloak/MinIO stack as planned; the build uses React/Vite, built-in auth and SeaweedFS.
6. CHANGELOG.md was rewritten in Session 7 and no longer carries the Session 4 note withdrawing the earlier "0 violations on 17 pages" axe claim (the withdrawal remains in TEST_REPORT.md Session 4 and the frontend README).
7. Dev-DB `backend/trustledger.db` was seeded on an earlier date: 1,642 document rows vs 1,617 in a fresh seed; 13 vs 12 open release requests.
8. Accessibility and the production-bundle search were **not re-run after the Session 8 rename and sidebar change** (build and backend suites were).
9. No renewal-gap screenshot; no comparison-mismatch screenshot; no tamper-detected screenshot.
10. Official SIH PS wording unverified (403).

---

## 20. Final Presentation Readiness Assessment

| Area | Ready? | Note |
|---|---|---|
| Problem framing and innovation message | **Yes** | §2, §3, §6 |
| Demo (S01) | **Yes**, on a fresh dev-build database | §7; backup screenshots exist |
| Architecture and security | **Yes** | §9, §10; state ZAP/pen-test gaps |
| Test evidence | **Yes** | §11 four statistics |
| Numbers | **Mostly**; fix or explain the label conflicts before showing dashboards | §8 |
| Screenshots | **Mostly**; recapture comparison view and production upload if time allows | §15.3 |
| Metadata | **No**: team details missing | §1 |
| References | **Partly**; re-open links before citing | §17 |

**Enough evidence exists to begin designing Slide 1**, provided the team supplies the team name, team ID and college,
and confirms the official problem-statement title.

---

*Verification notes for this rewrite (2026-10-24, session 8):* all repository paths cited above were checked to exist;
dataset figures were queried read-only from `.ui-check/session8-shots/ui.db`, `.ui-check/session7-final/ui.db` and
`backend/trustledger.db`; no seed data, migrations or historical evidence were modified by this rewrite. Application
changes made in the same session at the team's request (NIDHIVEDA display name; sidebar photo visibility) are recorded
in [TEST_REPORT.md](TEST_REPORT.md), Session 8.

---

## FINAL PPT READINESS CHECK

*2026-10-24, after Session 8. Adds to the dossier above; nothing above was changed.*

### 1. Confirmed project identity
- **SIH26265 — "Streamline of security deposit/ FDR portal."** AICTE (Ministry of Education); Software; Smart Automation. Source: public SIH tracker (zaidsayyed.in, fetched 2026-10-24). The official page `sih.gov.in/sih2026PS` returned **404**, so the wording is unverified against SIH itself.
- **Solution name: NIDHIVEDA** (UI, PDFs, notifications; [01-login.png](docs/screenshots/nidhiveda/01-login.png)).
- **Missing (REQUIRES TEAM INPUT):** team name, team ID, college, GitHub URL (`sih2/` is uncommitted; the home repo remote `teachnova26` is not confirmed as the project), demo link or video.

### 2. Three strongest innovations
| Innovation | Problem → mechanism | Evidence | Screenshot | One sentence for a judge |
|---|---|---|---|---|
| **Completion = money received** | A UTR or debit is not proof of payment. NIDHIVEDA completes a refund only on the bank's positive credit confirmation; a return reopens the liability | `kernel.py` `refund_status_text` (l. 1019); `test_s01_live_returned_rtgs_refund`; browser S01 12/12 | [s01-3](docs/screenshots/nidhiveda/s01-3-returned-still-owed.png), [s01-4](docs/screenshots/nidhiveda/s01-4-completed.png) | "If the college's bank sends the money back, NIDHIVEDA says AICTE still owes it, instead of 'Paid'." |
| **Bank-signed evidence, field by field** | Institutions upload their own proof. Each field shows declared vs bank-confirmed; verification is refused without a valid, matching signature from the issuing bank's registered key | `domain/fdr.py` `verify` (l. 109); `test_wrong_bank_cannot_confirm_another_banks_fdr`, `test_bank_mismatch_creates_discrepancy`; R5 (9 checks) | [17-bank-verification-mismatch.png](docs/screenshots/nidhiveda/17-bank-verification-mismatch.png) | "We trust what the bank signs, not what the applicant uploads." |
| **Controlled, tamper-evident release** | A single approver or edited records. Seven-check release gate, maker-checker, conflict-of-interest block, DSC signature over the exact decision; two SHA-256 chains that locate any database edit | `domain/release.py` `approve` (l. 88–99); `test_maker_checker_scrutiny_officer_cannot_approve`, `test_dsc_approval_bound_to_gate`, `test_audit_detects_edit` | [s01-1](docs/screenshots/nidhiveda/s01-1-release-gate.png), [15](docs/screenshots/nidhiveda/15-audit-trail-verify.png) | "No officer can approve their own scrutiny, and any record changed behind the system's back is caught." |

### 3. Verified competitor comparison
| System | Confirmed (source) | Unknown | NIDHIVEDA demonstrably adds |
|---|---|---|---|
| **AICTE JFDR** | Exists: "JFDR Details" in the 2011-12 portal manual; listed for revamp in the 2018 e-Gov RFP (repository research) | Current features, operator and interfaces | Not comparable feature-by-feature; position NIDHIVEDA as a control layer for, or a module within, JFDR |
| **ayus0109/AICTE-FDR-portal** (same PS; code inspected at commit `68bff01`, 2026-10-22) | React/FastAPI; 11 tests; reminders at 30/15/7/0 days; renewal links; release workflow; plain audit log table; S3 server-side AES256; verification is an officer-recorded outcome (`MANUAL_SCRUTINY` / `DEMO_BANK_SIMULATION`); release `status` set directly, including `COMPLETED` | Runtime behaviour (not executed) | Payment states with return handling; bank-signed field comparison; DSC maker-checker; hash-chained audit; ClamAV scan and envelope encryption; edition-aware rules. None of these was found in its source |
| **Arpit-Chaurasia26/Digital-Fixed-Deposit-System** | General **bank FD booking** app (Spring Boot/Vue); not AICTE; withdrawals and penalties; README lists no audit trail or renewal | Code not inspected | Different problem; not a direct competitor |
| **milindweb/FD_ATS** | **Offline desktop** FD manager (Wails/Go/React/SQLite); renewals, closures, Excel reports; single login | Code not inspected | Different problem; not a direct competitor |

Do not claim that NeSL e-BG or SFMS support FDRs (they serve bank guarantees).

### 4. Eight best screenshots (`docs/screenshots/nidhiveda/`)
| Need | File |
|---|---|
| Login | `01-login.png` (production build) |
| Institution dashboard | `03-dashboard-institution.png` |
| AICTE dashboard | `02-dashboard-aicte.png` |
| Auditor dashboard | `04-dashboard-auditor.png` |
| Bank verification | `17-bank-verification-mismatch.png` (alt. `16-bank-verification-confirmed.png`) |
| Release approval | `s01-1-release-gate.png` |
| Returned-refund detection | `s01-3-returned-still-owed.png` (+ `s01-4-completed.png`) |
| Audit integrity | `15-audit-trail-verify.png` |

**Consistent dataset to quote:** the screenshot dataset (synthetic; 2026-10-24): **482 institutions, 822 FDRs, ₹288.85 crore recorded**; buckets 612 active / 56 maturing / 28 pending / 18 discrepancy / 64 released / 44 closed; 12 open release requests. **Flags:**
- Auditor "Active / Verified 612" excludes 56 verified maturing FDRs (668 verified).
- ₹288.85 crore includes released and closed instruments; **₹251.25 crore is currently held**.
- "₹3.75 crore" of release requests excludes online-deposit requests.
- "Active FDRs" means different things on institution vs AICTE dashboards.
- `03` shows 2 FDRs for ABC because it was captured before the third was uploaded.
- `15`, `16` and `17` come from a fresh seed (sidebar badge 27, not 28; 3,412 ledger events). They show no portfolio totals, so they do not conflict with the quoted figures.
- Use "SIMULATED bank message", never "live bank sync".

### 5. Four strongest test results
| Result | Command | Evidence | Proves | Does not prove |
|---|---|---|---|---|
| **147/147 on SQLite and PostgreSQL 16** | `.venv/bin/python tools/baseline/backend_check.py sqlite\|postgres` | [S8 01](docs/verification/session8/01-backend-sqlite-after-rename.txt), [S8 02](docs/verification/session8/02-backend-postgres-after-rename.txt) | Controls work on both databases with real ClamAV, S3 storage and SMTP sink | Production load, security certification |
| **S01 browser 12/12**, four users | `node tools/ui-checks/s01.mjs` | [S8 03](docs/verification/session8/03-s01-browser.txt) | End-to-end refund with return and re-issue as users see it | Real bank behaviour (**SIMULATED** bank and DSC issuer) |
| **Kernel 161 scenario checks; 32/33 mutants killed** | `tools/baseline/kernel_check.py` | [S7 20](docs/verification/session7/20-final-kernel.txt) | Tests catch planted control faults | That all faults are found (one survivor disclosed) |
| **0 vs 67 false completions** (2,000 refunds, 67 returns) | `python tools/compare_and_bench.py` (scratch copy) | [S8 07](docs/verification/session8/07-compare-and-bench.txt) | The design difference on identical synthetic inputs | Real AICTE outcomes; the baseline is the team's model, not JFDR |

### 6. Best demonstration
**S01 (₹35 lakh refund), dev build, fresh seed, four users:** request → scrutiny → DSC approval → initiate → debit ("NOT yet complete") → return ("AICTE still owes you ₹35.00 lakh") → re-issue → credit confirmation ("Completed"). Backup: the s01-1…4 screenshots.

### 7. Feasibility and impact
- **Component-ready (prototype grade):** authentication with 2FA, role and kernel checks, document pipeline (checks, ClamAV, encryption, S3), hash-chained audit, notification logic, PostgreSQL support.
- **Needs AICTE/bank authorisation:** bank confirmations, payment advices and lien discharge; JFDR access; CCA DSC; e-Pramaan SSO; DLT SMS and production e-mail; KMS/HSM.
- **Biggest risk:** banks may not provide signed confirmations at scale. **Mitigation:** start with AICTE's own banker (credits, debits, returns), use signed file exchange before APIs, and add issuing banks "wherever supported"; unconfirmed items stay "institution declared".
- **Strongest measured result:** 0 vs 67 false completions (synthetic).
- **Strongest expected benefit:** no refund or FDR release is reported complete before the bank confirms it, with an audit packet ready on demand. Time savings are not measured; a pilot would measure them.

### 8. Four-perspective evaluation
| Perspective | Strongest benefit | Hardest question → answer |
|---|---|---|
| AICTE problem owner | One record from submission to bank-confirmed release | "Does it replace JFDR?" → No; it adds evidence controls and integrates via adapters (§12) |
| Operational officer | Queues, a release gate showing every check, automatic reminders and escalation | "More work for officers?" → Checks run automatically; officers decide on flagged items. Effort is unmeasured; pilot proposed |
| Auditor | One-click chain verification, evidence packet, read access to everything, scoped holds | "Can authorised staff collude?" → Actions are attributable and tamper-evident, not prevented (§10) |
| SIH judge | Live S01 showing a returned refund caught | "Is the bank real?" → No, it is SIMULATED and labelled; the interfaces are ready for authorised channels |

### 9. Remaining blockers
1. Team name, team ID and college (needed for Slide 1).
2. Official problem-statement wording (sih.gov.in 404; tracker only).
3. Not blockers, but fix or caption before showing: the dashboard label issues in §4, and the outstanding re-runs (axe and production-bundle search after the rename; ZAP never run).

### 10. Content emphasis, Slides 1–6
1. **Title:** NIDHIVEDA, SIH26265, AICTE, team details, `01-login.png`.
2. **Solution:** "complete only when the bank confirms"; S01 images; the five-answers table.
3. **Technical:** architecture diagram (§9); bank comparison (`17`); release gate; hash chains (`15`).
4. **Feasibility:** working prototype vs authorised deployment; "real vs SIMULATED" table; phased bank/JFDR path.
5. **Impact:** 0 vs 67 (synthetic, captioned); reminders and escalation; audit packet; pilot metrics, no invented savings.
6. **References and evidence:** APH 2024-27 clauses, JFDR sources, CAG/ICAI guidance; the four test results above.
