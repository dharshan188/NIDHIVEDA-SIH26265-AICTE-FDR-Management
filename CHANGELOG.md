# FDR Trust Ledger — Session 7 final verification

Historical failures and interrupted commands are retained in [TEST_REPORT.md](TEST_REPORT.md), Session 7.

## Built and tested

- Fixed strictly increasing Hypothesis fixture times and added regression assertions in the former assertion-free probe.
  Kernel unchanged; **147 passed on SQLite and 147 on PostgreSQL 16.15**, no skips.
  [SQLite](docs/verification/session7/60-final-sqlite-metrics.txt), [PostgreSQL](docs/verification/session7/59-final-postgres-metrics.txt), [fixture](docs/verification/session7/55-fixture-source.txt).
- Corrected double-counted sent deliveries; an existing health test now compares counts directly to delivery rows.
  [Before](docs/verification/session7/57-health-regression-before.txt), [after](docs/verification/session7/58-health-regression-after.txt), [live SQL](docs/verification/session7/71-nudge-sql-final.txt).
- Kernel scratch verification: **67 tests, 13 scenarios / 161 checks, 32/33 mutants killed; 48 files match ZIP**.
  [Evidence](docs/verification/session7/20-final-kernel.txt). The expected re-issue evidence-check mutant survives; kernel behavior was not changed.
- Dashboards' audit-based What changed cards, AICTE policy previews/reasons, FDR timeline/rules, document scan/encryption/SHA-256,
  observation controls and permitted-field editors: **18 targeted views per theme, zero axe violations**.
  [Light](docs/verification/session7/66-axe-panels-light-final.txt), [dark](docs/verification/session7/76-axe-panels-dark-complete.txt).
- Fixed badge and future-timeline contrast; final **42-route scans in each theme have zero violations and zero console errors**.
  [Light](docs/verification/session7/68-axe-light-complete.txt), [dark](docs/verification/session7/69-axe-dark-complete.txt).
- PDF-only upload exercised against real ClamAV and encrypted SeaweedFS/S3 storage; current screenshots show content checks,
  encryption and integrity results. [Capture](docs/verification/session7/41-final-screenshots.txt), [final refresh](docs/verification/session7/72-refreshed-screenshots.txt).
- Migration 0006: fresh SQLite, fresh PostgreSQL and dev-DB copy pass; clean seed/reset passes on the isolated UI DB.
  [Migration](docs/verification/session7/22-final-migrations.txt), [seed](docs/verification/session7/29-ui-server.txt).
- Production build passes; all 12 searched dev-only patterns absent. **18 screenshots, 1536×1024**.
  [Build](docs/verification/session7/64-build-final.txt), [search](docs/verification/session7/73-final-bundle-search.txt), [screenshots](docs/screenshots/final/README.md).
- Standalone Python **3.11.17**, Pillow **13.0.0**: **56 audited distributions, zero known advisories**.
  [Versions](docs/verification/session7/15-pillow-versions.txt), [audit](docs/verification/session7/61-audit-json-summary.txt).
- Source-set gitleaks passes. Whole-directory scan is **not clean: 430 ignored local/dependency findings**.
  npm audit has **0 high/critical and 2 moderate package findings**.
  [Source scan](docs/verification/session7/80-source-secret-final.txt), [whole-directory breakdown](docs/verification/session7/50-secret-summary.txt), [npm](docs/verification/session7/33-npm-audit.txt).

## Built with a simulator (named)

- **SIMULATED bank gateway** and **SIMULATED DSC test issuer**: four-user S01 **12/12**, zero console errors; debit remains
  incomplete, a return leaves ₹35 lakh owed, positive credit alone completes payment. Bank values have SIMULATED UI badges,
  API `simulated` flags / health `bank_layer`, and PDF labels. **8/8 PDF export checks** pass (seven labelled bank-data exports
  and one audit-only control). [S01](docs/verification/session7/31-s01-browser.txt), [PDFs](docs/verification/session7/70-pdf-labels-final.txt), [API labels](docs/verification/session7/52-prod-readiness.txt).
- **SIMULATED OTP/TOTP helpers**, local mock OIDC issuer, test DSC CA and email/SMS/WhatsApp/push providers; Mailpit is a
  real SMTP sink with no external delivery. Provider simulation is labelled in delivery chips, health and API responses.
  Nudge centre, escalation, health, preferences and one-use action links match **7 direct SQL comparisons**.
  Helpers are absent from production routes. [Live data](docs/verification/session7/71-nudge-sql-final.txt), [production](docs/verification/session7/52-prod-readiness.txt), [label inventory](docs/security.md#3-what-is-simulated-and-labelled-simulated-in-the-ui-the-api-and-changelogmd).
- Required API scenarios use a **SIMULATED malware-scanner stub**, simulated bank/providers/clock and filesystem storage:
  **R1–R6 / 52 checks**. Separate full suites require real ClamAV/S3/Mailpit/PostgreSQL. Kernel-wrapper S01–S09 has **115 checks**.
  [Required report](docs/scenario-report.md), [wrapper output](docs/verification/session7/34-scenario-output.txt).

## Planned (real service needed / remaining acceptance)

- Replace bank simulation with authorised signed bank/SFMS or host-to-host channels and **JFDR registry access**;
  replace test DSC issuance with **CCA-trusted certificates and CRL/OCSP**; use registered **e-Pramaan/DigiLocker OIDC**.
  [Production gaps](docs/security.md#6-production-gaps-that-need-outside-parties).
- Replace notification simulation with **DLT-registered SMS, authenticated production SMTP, WhatsApp Business and FCM**;
  replace LocalKms with a **government HSM or managed KMS**; configure **S3 Object Lock/WORM**, off-host trusted checkpoints,
  shared Redis rate limiting and operational backup/HA controls. [Security plan](docs/security.md#5-planned-not-built).
- Complete **OWASP ZAP baseline** where the container image is downloadable, then arrange an **independent CERT-In empanelled
  penetration test**. ZAP produced no report here after download timeouts; no clean scan claimed.
  [Attempts/status](docs/verification/session7/48-zap-status.txt).
- Review **React Router 7 migration** for the remaining moderate advisories. [Audit](docs/verification/session7/33-npm-audit.txt).
- A real renewal-gap screenshot requires an **existing live-data gap**: current API/SQL show none. No gap was created.
  [SQL](docs/verification/session7/49-gap-sql.txt), [timeline](docs/verification/session7/72-refreshed-screenshots.txt).
