# Session 7 final report

## Complete, with evidence

- Backend **147 passed on SQLite and 147 on PostgreSQL 16.15**, no failures/skips. [SQLite](verification/session7/60-final-sqlite-metrics.txt), [PostgreSQL](verification/session7/59-final-postgres-metrics.txt).
- Kernel **67 tests, 13 scenarios / 161 checks, mutation 32/33**; unchanged, 48 files match ZIP. [Evidence](verification/session7/20-final-kernel.txt).
- Build/dev-control search pass; axe **42 routes + 18 panel/editor views per theme, zero violations/errors**; S01 **12/12**;
  PDF checks **8/8**, Nudge/SQL **7/7**, three migration paths pass. [Full evidence index](../TEST_REPORT.md#session-7--2026-10-24).
- Final [screenshots](screenshots/final/README.md), [scenario report](scenario-report.md), [security](security.md), [notification design](notifications.md), and [three-list changelog](../CHANGELOG.md).

## Simulated, with labels

Bank gateway, test DSC issuer, mock government SSO, OTP/TOTP helpers and external notification providers remain simulated.
UI badges/chips, API flags/health and bank-data PDFs identify SIMULATED behavior. The required API scenario runner also
uses a labelled scanner stub and simulated clock; full integration suites use real ClamAV, SeaweedFS and Mailpit.
[Inventory and label locations](security.md#3-what-is-simulated-and-labelled-simulated-in-the-ui-the-api-and-changelogmd).

## Planned replacements

Authorised bank channels/JFDR; CCA DSC and registered government OIDC; DLT SMS, production SMTP, WhatsApp Business and FCM;
HSM/KMS, Object Lock and independent CERT-In penetration testing. [Production gaps](security.md#6-production-gaps-that-need-outside-parties).

## Failed, skipped or retained

- **ZAP unverified**: image download timed out on initial and resumed retry; no scan report or clean result.
  [Attempts](verification/session7/48-zap-status.txt).
- **No renewal-gap proof screenshot**: live data has zero gaps. No gap was created; the timeline image is explicitly named
  `08-fdr-detail-timeline-no-gap.png`. [SQL](verification/session7/49-gap-sql.txt), [API](verification/session7/41-final-screenshots.txt).
- npm: **2 moderate package findings**, 0 high/critical; Router major upgrade remains planned. Whole-directory gitleaks:
  **430 ignored local/dependency findings**; source-set scan clean. [npm](verification/session7/33-npm-audit.txt), [secret breakdown](verification/session7/50-secret-summary.txt).
- Earlier fixture, contrast, OTP-quota and interrupted-run failures are retained in TEST_REPORT.md. They are superseded
  only by the linked completed reruns. Build chunk-size and Starlette deprecation warnings remain.

## Pillow decision

Option 1 implemented: standalone **Python 3.11.17**, rebuilt venv, **Pillow 13.0.0**; **56 audited distributions, zero known
advisories**. Python 3.11+ remains a production requirement. [Versions](verification/session7/15-pillow-versions.txt), [audit](verification/session7/61-audit-json-summary.txt).

No commit made. No kernel changes. No project service containers stopped/deleted; buildhub-pg untouched.
