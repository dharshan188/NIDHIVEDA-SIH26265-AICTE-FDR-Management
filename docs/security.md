# Security: FDR Trust Ledger prototype (SIH 2026, PS 26265)

What this prototype protects, how, what is only simulated, and what must change before production. The evidence for each
"implemented and tested" claim is in `TEST_REPORT.md` and `docs/verification/`.

## Pillow decision — option 1 implemented; reconfirmed in Session 7

The backend now uses a standalone **CPython 3.11.17** installed under `sih2/.python/`,
with a rebuilt `sih2/.venv/` and **Pillow 13.0.0**. `backend/requirements.txt` requires
`pillow>=13.0.0`; Python **3.11 or later is a production requirement** (the Dockerfile
already uses Python 3.12). The old Python 3.10 venv is retained, gitignored, only for rollback.

The complete backend environment was audited after rebuilding: **no known
vulnerabilities**, hence no high or critical advisories. Evidence:
[Session 7 versions](verification/session7/15-pillow-versions.txt),
[audit output](verification/session7/23-pip-audit.txt), [audit JSON](verification/session7/pip-audit.json)
and [56-distribution summary](verification/session7/61-audit-json-summary.txt). The historical Session 4 Pillow blocker
is resolved by upgrading, not by accepting its risk. Post-upgrade suite results
are recorded separately in TEST_REPORT.md.

Pillow remains a dependency reached through ReportLab PDF generation. Application
PDF exports draw text and shapes; no application path decodes user data as images.
Uploads remain PDF-only. These are defense-in-depth limits, not a substitute for
the dependency upgrade.

## 1. Threat model

**Assets.** Money owed to institutions (security deposits, FDR liens, refunds); the evidence that decides a release
(bank confirmations, Affidavit-6, DSC approvals); documents (scanned FDRs, lien letters); personal and financial data
(PAN, registered mobiles, payee bank accounts); and the audit trail itself.

**Actors.** Institution users (their own records only); AICTE officers in distinct roles (section officer, deputy
director, director, finance officer, finance reconciliation officer, legal cell); auditors (read and verify); banks
(simulated in this build); and outside attackers.

| Threat | Example | Main controls |
|---|---|---|
| Money released without entitlement | officer approves own scrutiny; release on stale or forged bank evidence | maker-checker roles in the kernel; DSC signature over the exact gate decision; release gate (current evidence, Affidavit-6, holds); database triggers re-check the money invariants |
| "Paid" claimed before the money arrives | refund marked complete on the bank debit | SETTLED only on a positive credit confirmation; RETURNED reopens the liability ("AICTE still owes you …") |
| Forged or replayed bank messages | fake credit advice; message signed with a compromised or expired key | Ed25519 signature per bank key; Bank Authority Registry with key validity windows and compromise dates; evidence invalidated retroactively |
| Tampering with history | DBA edits a credit from ₹35 lakh to ₹0.01 lakh; deletes an audit row | two SHA-256 hash chains (ledger, portal); `/audit-trail/verify` recomputes both, detects edits, gaps and relinking, checks an off-host checkpoint, and replays the ledger against live state; insert-only event tables |
| Account takeover | password stuffing; OTP brute force; session theft | Argon2id; lockout after 5 failures; rate limits; mandatory 2FA (OTP / TOTP / DSC); httpOnly, Secure, SameSite=Strict cookies; CSRF token plus custom header; 15-minute idle and 8-hour absolute expiry |
| Cross-institution access (IDOR) | institution A opens B's FDR, document or observation | institution scope on every record; out-of-scope returns 404, not 403 |
| Malicious uploads | PDF with JavaScript; EICAR / malware; renamed PNG | PDF-only content checks (extension, MIME, magic bytes, no active content, parses unencrypted); ClamAV before storage; infected files never stored and the refusal audited |
| Data theft at rest | stolen database dump or object-store bucket | envelope encryption of documents (AES-256-GCM, per-document key wrapped by the KEK); PII fields encrypted (HKDF-derived key); masked in every API response; tests show no plaintext in a PostgreSQL dump |
| Unauthorised policy change | lowering the evidence-age limit to release faster | only deputy director or director can change the release policy; every change shows before and after, needs a reason and is hash-chained; numbers must stay positive and keep their type |
| Phishing via notifications | forwarded SMS link performs an approval | action links are HMAC-signed, single-use, 72-hour, user-bound, and never act on their own; approvals need a fresh DSC signature |

## 2. Controls implemented (built and tested)

- **Authentication:** Argon2id password hashes; generic login errors; lockout after 5 failures with a timed unlock;
  per-address and per-account rate limits on login, OTP and action links; mandatory second factor: OTP (6 digits,
  5 minutes, single use, 5 attempts, 5 sends per 15 minutes), TOTP (RFC 6238; secrets encrypted), or DSC (X.509 chain to a
  trust anchor, validity window, key usage, signature over a server challenge). OIDC client with state, nonce and PKCE.
- **Sessions:** server-side sessions; cookies httpOnly, Secure, SameSite=Strict; idle 15 minutes and absolute 8 hours;
  CSRF token plus the `X-TL-Client` header on every state change.
- **Authorisation:** role checks per endpoint; kernel roles for maker-checker (scrutiny officer cannot approve; approver
  cannot initiate payment); institution scoping on every record (IDOR returns 404); permitted-field rules per role and
  FDR state; ledger-held fields (bank, number, amount, dates, status) are never editable.
- **Integrity:** two hash chains; insert-only event tables; database triggers enforcing Σ allocations ≤ credit and
  ≤ required on SQLite and PostgreSQL; unique UTR per debit and unique FDR number per bank; ledger replay check.
- **Documents:** PDF-only content checks, recorded per file and shown on the upload page and the FDR page; ClamAV scan
  before storage; SHA-256 of the plaintext; AES-256-GCM with a per-document data key wrapped by the KEK; ciphertext
  only in the object store; SHA-256 re-checked on every download and on demand ("Check SHA-256 now"), with failures
  audited; an object-store outage is refused with a clear 503 and nothing is stored.
- **PII:** PAN, registered mobiles and payee accounts are encrypted at rest; masked in responses and in audit data;
  exact-match look-ups use a keyed blind index.
- **HTTP:** `Content-Security-Policy: default-src 'none'` on the API; `X-Frame-Options: DENY`;
  `X-Content-Type-Options: nosniff`; `Referrer-Policy: no-referrer`; HSTS; `Cache-Control: no-store`; a restrictive
  `Permissions-Policy`; COOP and CORP same-origin. API docs and OpenAPI are served only in dev.
- **Secrets:** all keys come from environment variables (`TL_*`). Outside dev, a missing secret stops start-up. In dev,
  generated secrets live in `backend/.dev-secrets.json` (mode 600, gitignored). gitleaks finds no secrets in the files
  a commit would contain ([Session 7 source scan](verification/session7/80-source-secret-final.txt)); the whole-directory scan still flags ignored local keys and dependencies.
- **Production build hygiene:** the simulator API (`/api/sim/*`), the mock OIDC issuer, demo-credential buttons, OTP/TOTP
  hints and sample-document buttons exist only when `TL_ENV=dev` or in the Vite dev build. The production bundle is
  searched for them. The final Session 7 [build](verification/session7/64-build-final.txt) and
  [literal search](verification/session7/73-final-bundle-search.txt) pass after the action-link and contrast fixes.

## 3. What is simulated (and labelled SIMULATED in the UI, the API and `CHANGELOG.md`)

| Simulated | Stand-in | Where it is labelled |
|---|---|---|
| Every bank channel: credit/debit advices, positive credit confirmation, returns, FDR confirmations, lien discharge, name look-up, key compromise | `app/bank/simulator.py`: 12 banks, Ed25519 keys from `TL_SIM_BANK_SEED` | SIMULATED badge on every bank value, table and PDF ("SIMULATED bank data"); `"simulated": true` in signed payloads; `/api/health` → `"bank_layer": "SIMULATED"` |
| SMS / e-mail OTP delivery | mock provider logs to the server console | dev-only OTP outbox |
| E-mail, SMS, WhatsApp, push notifications | provider simulators; Mailpit for real SMTP that delivers nothing outside the machine | `SIMULATED` delivery chips; health panel provider column; `"simulated": true` per delivery |
| Government SSO (e-Pramaan) | local mock OIDC issuer (dev only) | dev only; the client side is real |
| DSC issuer | locally generated test CA (`backend/devcerts/`, gitignored) | certificate and signature checks are real; the issuer is not |
| Authenticator app | dev endpoint returning the current TOTP | dev only |

## 4. Object storage: the SeaweedFS substitution for MinIO

The design names MinIO (with object lock) for documents. This build talks to any S3-compatible store through the `minio`
Python client (`app/storage.py`, `TL_OBJECT_STORE=s3`). Locally, and in every live-service test, that store is
**SeaweedFS 3.97** (`chrislusf/seaweedfs`, container `tl-baseline-s3`). The recorded project decision substitutes it because
the requested public MinIO distribution was unavailable for this setup (see the comments in `backend/docker-compose.yml`).
No new MinIO registry-availability check was performed in Session 6. The code uses only standard S3 calls (`bucket_exists`, `make_bucket`, `put_object`, `get_object`,
`stat_object`), so MinIO or a cloud S3 bucket can replace it by configuration alone.

What the substitution does **not** provide: object lock / WORM retention is not configured, so a storage administrator
could delete or overwrite ciphertext. Overwriting is detected (the SHA-256 re-check fails and is audited) but not prevented.
Operational note: the local SeaweedFS is capped at 8 volumes to avoid the disk exhaustion recorded in `TEST_REPORT.md`, so
new buckets cannot be created there; the UI checks reuse the integration-test bucket.

## 5. Planned (not built)

- Object lock / WORM retention for documents (MinIO object lock, S3 Object Lock or equivalent).
- RFC 3161 time-stamping of the hash-chain heads. The off-host checkpoint is a local file today.
- Shared rate-limit store (Redis) for more than one API process; the per-account lockout is already in the database.
- PostgreSQL production setup: row-level security, managed backups, HA, monitoring, key-rotation runbooks.
- DSC-signed PDF validation (pyHanko) for uploaded bank letters.
- CRL/OCSP revocation checks for DSC certificates against the CCA India trust chain.

## 6. Production gaps that need outside parties

| Gap | Why it blocks production | What is needed |
|---|---|---|
| **Real bank authorisation** | Every bank message here is simulated. AICTE must authorise each bank to send signed confirmations, credit advices and return advices, and must agree the channel (SFMS, host-to-host, PKCS#7). | Agreements with AICTE's banker and the issuing banks; real signing certificates; revocation lists |
| **JFDR access** | Confirming FDRs at scale needs the banks' joint FDR registry (or each bank's FDR enquiry interface). No interface exists in this build. | Access and API specification from the operator; a JFDR adapter behind the existing bank interface |
| **KMS for keys** | The master key (KEK) is an environment variable held in process memory (`LocalKms`). A host compromise exposes it. | Government HSM or cloud KMS implementing the existing `Kms` wrap/unwrap interface; key-rotation runbook |
| **Independent penetration test** | Dependency scans, secret scans and the project's tests are automated checks, not a penetration test. ZAP has not produced a report in Session 7 (image download timeouts). | CERT-In empanelled auditor; fix and retest before go-live |
| Real SMS / e-mail / WhatsApp gateways | Notifications are simulated | DLT-registered SMS sender and templates; e-mail domain with SPF, DKIM and DMARC; WhatsApp Business templates |
| e-Pramaan / DigiLocker SSO | Only a mock issuer exists | Client registration with the identity provider |

## 7. Final Session 7 scan results and limitations

- Python 3.11.17 / Pillow 13.0.0: **56 distributions, zero known advisories** ([audit](verification/session7/23-pip-audit.txt), [summary](verification/session7/61-audit-json-summary.txt)).
- npm audit: **0 high, 0 critical, 2 moderate package findings** for React Router. Automatic remediation requires a major
  migration to React Router 7. This client-rendered BrowserRouter SPA does not use SSR error hydration; the navigation
  advisory still requires an upgrade review. The findings are retained, not called fixed. [Audit](verification/session7/33-npm-audit.txt).
- gitleaks whole-directory scan: **430 findings**, all in ignored local verification environments, installed dependencies,
  standalone Python or development credentials/DSC keys. Source-set scan has no leaks; no commit was made. Whole directory
  is not called clean. [Breakdown](verification/session7/50-secret-summary.txt), [source scan](verification/session7/80-source-secret-final.txt).
  The saved whole-directory JSON redacts every Secret value; ephemeral simulated OTP values in logs are redacted.
- ZAP: initial image pull and resumed retry both timed out (180 seconds each). The earlier retry was interrupted by the
  host reboot. **No ZAP scan report exists, no risk score or clean scan is claimed.**
  [Recorded attempts](verification/session7/48-zap-status.txt). Complete before production acceptance.
- Production build/search passes: no literal `demo`, OTP hints, reset controls or other tested dev controls in assets.
  Production OTP/TOTP helper endpoints return 404. [Search](verification/session7/73-final-bundle-search.txt), [HTTP checks](verification/session7/52-prod-readiness.txt).
- Final backend: 147 tests on each database; axe: 42 routes and 18 additional panel/editor views in each theme, zero
  violations and console errors. Automated checks cover the recorded views and conditions, not an independent penetration test.
  [Session 7 evidence](../TEST_REPORT.md#session-7--2026-10-24).

After the host reboot, project PostgreSQL/ClamAV/Mailpit were started. The existing SeaweedFS container `tl-baseline-s3`
was restarted only after explicit user approval. No pre-existing container was stopped, removed or recreated;
`buildhub-pg` was untouched. Individual Docker commands were used, not compose.
