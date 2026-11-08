> **Latest: Session 8 (2026-10-24, evening).** Display name changed to NIDHIVEDA and the sidebar photo fixed, at the team's
> request; backend 147/147 on SQLite and PostgreSQL, S01 12/12 and kernel unchanged afterwards. `solution.md` rewritten as the
> presentation research dossier (backup: `solution.pre_ppt_backup.md`). Earlier sessions below are historical.

## Session 8 — 2026-10-24 (evening)

Requests handled: (1) rewrite `solution.md` as the SIH presentation research dossier, preserving the original as
`solution.pre_ppt_backup.md` (byte-identical, SHA-256 `d01e511b…f965`); (2) sidebar: keep the building photo visible;
(3) rename the solution's display name from "FDR Trust Ledger" to **NIDHIVEDA**. No commit. Kernel unchanged.
The host had rebooted; `docker start tl-gap-pg tl-gap-clamav tl-gap-mailpit tl-baseline-s3` restarted only this project's
service containers (`buildhub-pg` untouched).

| Check | Result | Evidence |
|---|---|---|
| Sidebar fix (`frontend/src/styles.css`: photo panel min 280 px; compact menu items below 1100 px window height) | 3 roles × 2 themes: no menu scrolling, last item visible, photo 184 px (AICTE/auditor) / 228 px (institution) | [docs/verification/session8/00-sidebar-measure.txt](docs/verification/session8/00-sidebar-measure.txt) |
| Rename (display strings only: login, header, page title, PDF header/footer/metadata, 32 SMS templates EN/HI, SMTP sender, API title, TOTP issuer, Hindi UI strings, two test assertions); internal `trustledger` names kept | Type-check and production build pass; 0 "Trust Ledger" in built assets | build output |
| Backend, SQLite, all services required | **147 passed** | [docs/verification/session8/01-backend-sqlite-after-rename.txt](docs/verification/session8/01-backend-sqlite-after-rename.txt) |
| Backend, PostgreSQL 16.15 | **147 passed** | [docs/verification/session8/02-backend-postgres-after-rename.txt](docs/verification/session8/02-backend-postgres-after-rename.txt) |
| Browser S01, four users | **12/12**, 0 console errors | [docs/verification/session8/03-s01-browser.txt](docs/verification/session8/03-s01-browser.txt) |
| Screenshots with new name and sidebar | 14 pages + 4 S01 + login (production build, no dev text) + audit-trail verify = **19** in `docs/screenshots/nidhiveda/`; Session 7 images in `final/` untouched | [docs/verification/session8/04-screenshots.txt](docs/verification/session8/04-screenshots.txt), [docs/verification/session8/05-login-production.txt](docs/verification/session8/05-login-production.txt), [docs/verification/session8/08-audit-verify-shot.txt](docs/verification/session8/08-audit-verify-shot.txt) |
| Bank-verification screenshots (presentation readiness check) | `16-bank-verification-confirmed.png`, `17-bank-verification-mismatch.png`; 0 console errors | [docs/verification/session8/09-bank-verification-shots.txt](docs/verification/session8/09-bank-verification-shots.txt) |
| Kernel manifest | `58406d49…fd387c0`, 48 files, unchanged | [docs/verification/session8/06-kernel-hash.txt](docs/verification/session8/06-kernel-hash.txt) |
| Kernel design comparison re-run (scratch copy) | Identical to the saved result except timings: 2,000 refunds / 67 returns → baseline 67 false completions, kernel 0 | [docs/verification/session8/07-compare-and-bench.txt](docs/verification/session8/07-compare-and-bench.txt) |

Commands (from `/home/dharshan/sih2`): `.venv/bin/python tools/baseline/backend_check.py sqlite|postgres`;
`env TL_UI_WORK=.ui-check/session8-shots TL_UI_API_PORT=8004 TL_UI_PORT=5177 .venv/bin/python tools/ui-checks/serve.py --reset`;
`UI_BASE=http://localhost:5177 SHOTS_DIR=$PWD/docs/screenshots/nidhiveda/ node tools/ui-checks/s01.mjs` and `… shots.mjs`
(`SHOTS_DIR` added to both scripts so new captures never overwrite recorded evidence); production login from
`serve.py --reset --prod --preview` on ports 8005/5178; audit-trail capture on a fresh seed (ports 8006/5179);
`python tools/compare_and_bench.py` on a scratch copy of the kernel. All servers started here were stopped.

**Not re-run after the rename/sidebar change:** axe accessibility scans and the production-bundle dev-control search.
They should be repeated before the final demonstration.

---

> **Latest: Session 7 final application baseline passes (147 tests on both databases); ZAP remains unverified.** See [Session 7](#session-7--2026-10-24) and its final results. Earlier failures below are historical.

# Session 4 (2026-10-24, afternoon) — fixes and completion work: **STOPPED at a stop condition (critical dependency advisory)**

Decision carried in from the user: the 42-route axe run (5 violations in light mode, 5 in dark) is the accessibility
baseline; the earlier "0 violations on 17 pages" claim is **withdrawn** (its page list was never recorded, and a 42-route
re-run of the unchanged code found 5 violations). The withdrawal is also recorded in `CHANGELOG.md` and `frontend/README.md`.

**Why this session stopped.** `pip-audit` of the project venv reports **pillow 12.3.0: 4 critical, 22 high, 11 moderate**
advisories (OSV severities), and every fix is in pillow 13.0.0, which requires Python ≥ 3.11. The project venv and the
only interpreter on this machine are Python 3.10.12, so the fix cannot be installed here. The stop condition ("If a
critical security finding cannot be fixed in this session, stop and list it as a blocker") applies. See "Blocker" below.

No git commit was made. The kernel is unchanged (manifest `58406d49…fd387c0`, 48 files, [13-kernel-hash.txt](docs/verification/session4/13-kernel-hash.txt)).
`buildhub-pg` was not touched (the machine rebooted mid-session and it restarted on its own restart policy).

## Results so far

| Item | Result | Evidence |
|---|---|---|
| A11y fixes, light mode | **42 routes, 0 violations, 0 console errors** | [01-axe-a11y-fix-light.txt](docs/verification/session4/01-axe-a11y-fix-light.txt) |
| A11y fixes, dark mode | **42 routes, 0 violations**; 15 console errors, all `net::ERR_NETWORK_CHANGED` while Docker containers were being restarted after the reboot (environmental; the scan must be repeated) | [02-axe-a11y-fix-dark.txt](docs/verification/session4/02-axe-a11y-fix-dark.txt) |
| Migration 0006 (fresh SQLite, copy of the existing dev DB from 0001, fresh PostgreSQL 16.15): upgrade, downgrade to 0005, upgrade | **all PASS**; dev-DB row counts preserved | [03-migration-check.txt](docs/verification/session4/03-migration-check.txt) |
| `backend/trustledger.db` migrated 0001 → 0006 (head) | **done**; kernel chain 3422 events valid, portal chain 70 valid; 821 FDRs, 1642 documents | [04-devdb-migrate.txt](docs/verification/session4/04-devdb-migrate.txt) |
| `seed.py --reset` at head | **works**: 482 institutions, 821 FDRs, 3411 kernel events, 9 users; revision 0006 | [05-seed-reset.txt](docs/verification/session4/05-seed-reset.txt) |
| S01 in the browser, four users signed in through the login page | **12/12 checks, 0 console errors**: "NOT yet complete" after the debit; "AICTE still owes you ₹35.00 lakh" after the return; "Completed" only after the positive credit confirmation; ledger SETTLED with RETURNED + SETTLED attempts; both chains valid | [06-s01-browser.txt](docs/verification/session4/06-s01-browser.txt) |
| PDF exports carry SIMULATED where bank data appears | **8/8 as expected** (7 bank-data exports labelled, including the evidence packet and the missing-documents report; the audit-events control is not labelled) | [07-pdf-simulated-labels.txt](docs/verification/session4/07-pdf-simulated-labels.txt) |
| Screenshots 1536×1024 | **18 saved** in `docs/screenshots/final/`, 0 console errors. `08-fdr-detail-timeline.png` must be retaken (it shows a new FDR with no gap, not one with a renewal gap; script fixed, not re-run) | [08-screenshots.txt](docs/verification/session4/08-screenshots.txt) |
| New backend tests (`tests/test_completion.py`) | **10 passed** (SQLite, all services required). Full suites not re-run yet | [12-test-completion-sqlite.txt](docs/verification/session4/12-test-completion-sqlite.txt) |
| npm audit | frontend: **2 moderate** (react-router; not reachable, see below); 0 high/critical. tools/ui-checks: 0 | [10-npm-audit.txt](docs/verification/session4/10-npm-audit.txt) |
| gitleaks v8.18.4 | whole `sih2/`: 288 findings, all in `.venv` / tools-venv third-party test vectors or this machine's gitignored dev secrets; **files a commit would contain (297): no leaks** | [11-gitleaks.txt](docs/verification/session4/11-gitleaks.txt) |
| pip-audit | project venv: pillow 42 advisories (**blocker**); setuptools 5 → **fixed** (59.6.0 → 84.2.1). The `-r requirements.txt` run failed on a PyPI read timeout and gave no result | [09-pip-audit.txt](docs/verification/session4/09-pip-audit.txt), [09b-pip-audit-severity.txt](docs/verification/session4/09b-pip-audit-severity.txt) |

## Blocker: pillow 12.3.0 on Python 3.10

- Severities (OSV): 4 CRITICAL (TIFF write heap overflow, FlashPix JPEG overflow, multi-frame stale storage, Ghostscript
  argument injection), 22 HIGH, 11 MODERATE. Fixed in 13.0.0 only; `pip install "pillow>=13.0.0"` → "requires Python >=3.11".
- Why pillow is present: hard dependency of reportlab 5.1.0 (PDF exports). No application module imports PIL;
  `app/pdf.py` draws no images; uploads are PDF-only and parsed by pypdf without image extraction. So no request path hands
  attacker-controlled bytes to Pillow today. That reduces exposure, but it is not a fix, and a future change (e.g. a logo
  in PDFs or image uploads) would make it reachable.
- Options for the user: (1) rebuild the project venv on Python 3.11+ (e.g. a standalone interpreter installed under
  `sih2/`), then upgrade pillow and re-run every baseline; (2) accept the risk in writing for the prototype, with the
  non-reachability reasoning above and a production requirement of Python ≥ 3.11; (3) replace reportlab (large change).

## npm audit: why the 2 moderate findings are not fixed

`react-router` ≤ 7.17.0: (a) open redirect through a backslash in `<Link>` / `useNavigate`: the only user-controlled
navigation target is the login `?next=` parameter, which is accepted only if it matches `^/l/[A-Za-z0-9._-]{10,300}$`
(no backslash possible); the action-link page navigates to a server-built path. (b) SSR hydration
(`deserializeErrors`): this app has no SSR. The fix is react-router-dom 7 (breaking); not taken in this session.

## Changes made in this session

- **Accessibility (item 1 of the decision):** donut chart: SVG decorative, legend rows are buttons, figure is a labelled
  group (no nested interactive); `--c-fg-f5f7fb/f2f6fc/e2ecfb/e6ebf2` given dark values; new `--on-solid-muted` token
  (4.92:1 light, 4.62:1 dark) for secondary text on solid fills; a mis-nested "Planned" strip inside the Renewals button
  removed (the reminders it called planned are built by the Nudge Ladder). A stale "Planned: scheduled reminders" entry and
  the "MinIO … server disk" note on the Guidelines page were corrected.
- **Functional gaps:** `WhatChanged` card on the AICTE, institution and auditor dashboards; Rules page: release-policy
  editor (deputy director / director only; before/after preview; reason ≥ 10 chars) and the notification-policy editor with
  before/after; policy change history from the hash chain. Backend: `portal_audit.changes()` leaf diff stored in
  `policy_changed` / `notify_policy_changed` audit events; `GET /policy/changes`; no-op change → 409; type change or
  non-positive number → 422; `what-changed` links fall back to pages each role has. FDR detail: history timeline with
  editions in force and rule resolution per date and renewal-gap flag; documents panel (scan, encryption, content checks,
  SHA-256 and an on-demand re-check `POST /fdrs/{id}/documents/{doc}/verify`, audited); observations panel (raise /
  reply / close, status per observation); permitted field edits with before/after, reason, audit sequence. Upload page:
  PDF only; per-file `POST /documents/precheck` (content checks + ClamAV, nothing stored); per-file document type;
  confirmation screen shows scan, encryption and SHA-256 of each stored file. Object-store failure → 503 "nothing was
  stored". Nudge stylesheet `frontend/src/styles/nudge.css`. Kernel status text shown with ₹ (`rupeeText`, figures unchanged).
  Reconciliation "Per-institution certification" export now labelled SIMULATED.
- **Migration 0006**: `fdr_documents.content_checks`, `integrity_status`, `integrity_checked_at` (guarded add-column).
- **Tooling:** `tools/ui-checks/serve.py` (UI-check servers on `sih2/.ui-check/`, gitignored), `stop.sh`, `s01.mjs`,
  `shots.mjs`, `pdf_check.mjs`, `uiLogin()` in `lib.mjs`; `tools/baseline/migration_check.py`. `package.json` scripts
  `s01` and `shots` now point at existing files.
- **Docs:** `docs/notifications.md`, `docs/security.md` (both written; security.md section 7 lists ZAP and the bundle
  search, which have not run yet).
- **Environment:** project venv setuptools 59.6.0 → 84.2.1. pip-audit 2.7.3 installed only in `.ui-check/tools-venv`.
  Docker image pulled: `zricethezav/gitleaks:v8.18.4` (run with `--rm`). The ZAP image pull was interrupted when the
  previous session process ended and is **not** present; ZAP has not run.

## Failed attempts and incidents, retained

- The machine **rebooted** during the first post-fix axe run. `/tmp/tl-ui-check` was wiped (the launcher now uses
  `sih2/.ui-check/`), and `tl-gap-pg`, `tl-gap-clamav`, `tl-gap-mailpit`, `tl-baseline-s3` exited with code 255. They were
  restarted with `docker start tl-gap-pg tl-gap-clamav tl-gap-mailpit tl-baseline-s3`.
- `pkill -f tools/ui-checks/serve.py` matched its own shell and exited 144; replaced by `tools/ui-checks/stop.sh` (kills
  only the listeners on :8000 and :5173).
- First S01 run: all checks up to the second debit passed, then a script defect (settled payments sit under the "All"
  tab) timed out; [06a](docs/verification/session4/06a-s01-browser-attempt1-script-defect.txt). Fixed and re-run on a reseeded database: 12/12.
- First screenshot run: SeaweedFS returned HTTP 500 ("failed to find writable volumes" for a new bucket; the container is
  capped at 8 volumes since the earlier disk incident). The API answered with a generic 500; it now answers 503 and stores
  nothing (tested). The UI-check server now reuses the `tl-integration-tests` bucket; [08a](docs/verification/session4/08a-screenshots-attempt1-s3-volume.txt).
- `gitleaks dir` does not exist in v8.18.4; re-run as `detect --no-git`.
- A first malware-precheck test placed EICAR inside the PDF body, where a content check failed first; it now appends it
  after `%%EOF`, as the existing test does.

## Not done yet (remaining after the blocker is decided)

Item 4: interactive live-data cross-check of notification centre / escalations / health / preferences / action-link page
against SQL (pages are rendered from live data in the screenshots; no SQL cross-check run). Item 8: OWASP ZAP baseline;
production-bundle search for "demo", "OTP on screen" and dev-only controls. Item 9: CHANGELOG three-list rewrite;
`docs/scenario-report.md` check. Item 10: retake `08-fdr-detail-timeline.png`. Item 6/11: axe on all routes after the new
panels (the new FDR-detail panels, upload checks and Rules editors have not been axe-scanned), full SQLite and PostgreSQL
suites, kernel tests/scenarios/mutation, production build, S01 re-run.

## Commands (from `/home/dharshan/sih2`)

```bash
node tools/ui-checks/axe.mjs [--theme dark]                         # 01, 02
.venv/bin/python tools/baseline/migration_check.py .ui-check/devdb/trustledger.pre-session4.db   # 03 (backup of the dev DB taken first)
(cd backend && ../.venv/bin/python -m alembic -c alembic.ini upgrade head)                        # 04
.venv/bin/python tools/ui-checks/serve.py --reset                  # 05 (seed.py --reset at head)
node tools/ui-checks/s01.mjs                                       # 06
node tools/ui-checks/pdf_check.mjs                                 # 07
node tools/ui-checks/shots.mjs                                     # 08
.ui-check/tools-venv/bin/pip-audit -r backend/requirements.txt; .ui-check/tools-venv/bin/pip-audit --path .venv/lib/python3.10/site-packages   # 09
(cd frontend && npm audit); (cd tools/ui-checks && npm audit)      # 10
docker run --rm -v $PWD:/repo:ro zricethezav/gitleaks:v8.18.4 detect --no-git --source /repo --redact   # 11 (plus the commit-set scan)
.venv/bin/python tools/baseline/backend_check.py sqlite tests/test_completion.py                       # 12
```

---

# Session 3 (2026-10-24, afternoon) — baseline re-run before completion work: **STOPPED at a stop condition**

Before any change to the application, the starting point was re-run. Backend and kernel numbers reproduce exactly.
**The frontend accessibility baseline does not reproduce**, so, per the stop condition ("If a baseline number does not
reproduce, stop and report it before continuing"), no feature, migration, documentation or security work was started.
No application source file was modified. No git commit was made. The kernel was not modified.

| Check | Claimed starting point | Measured this session | Evidence |
|---|---|---|---|
| Kernel tests (scratch copy) | 67 pass | **67 passed**, 4 warnings | [00-kernel-tests-scenarios.txt](docs/verification/session3/00-kernel-tests-scenarios.txt) |
| Kernel scenarios | 13 scenarios, 161 checks | **13 scenarios, 161 passed, 0 failed** | same file |
| Kernel mutation (scratch copy) | 32/33 | **32/33 killed** (survivor: payment re-issue skips evidence re-check) | [01-kernel-check.txt](docs/verification/session3/01-kernel-check.txt) |
| Kernel vs ZIP | 48/48 identical | **all ZIP members byte-identical**; manifest `58406d49…fd387c0` | same file |
| Backend, SQLite, all services required | 137 pass, 0 skip | **137 passed, 0 skipped**, 1 warning | [02-backend-sqlite.txt](docs/verification/session3/02-backend-sqlite.txt) |
| Backend, PostgreSQL 16 | 137 pass, 0 skip | **137 passed, 0 skipped**, 1 warning | [03-backend-postgres.txt](docs/verification/session3/03-backend-postgres.txt) |
| Frontend production build | passes | **passes** (`tsc -b && vite build`; chunk-size warning only) | [04-frontend-build-baseline.txt](docs/verification/session3/04-frontend-build-baseline.txt) |
| axe WCAG 2 A/AA, light | 0 violations (17 pages) | **5 violations on 5 of 42 routes** | [05-axe-baseline-light.txt](docs/verification/session3/05-axe-baseline-light.txt) |
| axe WCAG 2 A/AA, dark | not previously reported | **5 violations on 5 of 42 routes** | [06-axe-baseline-dark.txt](docs/verification/session3/06-axe-baseline-dark.txt) |

## The non-reproducing number

The earlier "0 violations" figure covered 17 pages; the list of those 17 was not recorded. The existing scanner
(`tools/ui-checks/axe.mjs`) now visits 42 role routes. Violations found, unchanged code, fresh seeded database:

| Route | Rule | Light | Dark | Element |
|---|---|---|---|---|
| `/auditor` (dashboard, certainly one of the original pages) | nested-interactive (serious) | yes | yes | chart `figure` with focusable descendants inside an interactive wrapper |
| `/aicte/reports`, `/auditor/reports` | nested-interactive (serious) | yes | yes | same chart pattern |
| `/institution/renewals` | color-contrast (serious) | yes | — | `.planned-row` text on a blue strip: 1.92:1 and 1.3:1 |
| `/institution/communication` | color-contrast (serious) | yes | yes | sent-message `time`: 3.67:1 (`#b6cff3` on `#0b5ed7`) |
| `/aicte/verification` | color-contrast (serious) | — | yes | 4 nodes (see dark log) |

Console errors during both scans: 0. All are small CSS/markup fixes within item 6 of the task; they were **not** fixed,
because the stop condition requires reporting first.

## Other findings from the inspection (no changes made)

- Most backend endpoints for items 1–4 already exist (observations, permitted field changes, `/nudge/what-changed`,
  `/fdrs/{id}/timeline`, health, escalations, missing-documents, PUT `/policy`), and migration `0005` creates their tables.
  The frontend components `WhatChanged` and `NotifyPolicyEditor` exist but are mounted nowhere; the FDR detail page does not
  call the timeline, observations or field-change endpoints.
- **The Nudge pages have no stylesheet**: classes such as `rung`, `ladder`, `dchip`, `wc`, `esc-card` are not defined
  in any CSS file. The notification centre, escalation view and health panel render unstyled.
- The upload page accepts JPG/PNG on the client while the server accepts PDF only.
- The existing developer database `backend/trustledger.db` is at Alembic revision **0001**, not head (0005).
- `tools/ui-checks/` contains only `axe.mjs` and `lib.mjs`; the `s01.mjs` and `shots.mjs` scripts named in its
  `package.json` do not exist.

## Commands run (from `/home/dharshan/sih2` unless noted)

```bash
# kernel tests and scenarios, on a scratch copy (the original kernel directory is not touched)
cp -r trust-ledger-kernel $SCRATCH/kcopy && cd $SCRATCH/kcopy
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/dharshan/sih2/.venv/bin/python -m pytest -q -p no:cacheprovider -p hypothesis.extra.pytestplugin tests
/home/dharshan/sih2/.venv/bin/python -m trustledger.scenario
# (a first attempt without PYTEST_DISABLE_PLUGIN_AUTOLOAD failed to collect: a ROS 'launch' pytest plugin needs 'lark'; not a kernel failure)

.venv/bin/python tools/baseline/kernel_check.py          > docs/verification/session3/01-kernel-check.txt      # exit 0
.venv/bin/python tools/baseline/backend_check.py sqlite   > docs/verification/session3/02-backend-sqlite.txt    # exit 0
.venv/bin/python tools/baseline/backend_check.py postgres > docs/verification/session3/03-backend-postgres.txt  # exit 0
(cd frontend && npm run build)                             # tail in 04-frontend-build-baseline.txt

# browser-check environment: new launcher, disposable DB under /tmp/tl-ui-check, real ClamAV + SeaweedFS
.venv/bin/python tools/ui-checks/serve.py --reset          # migrate to head + seed, uvicorn :8000, vite :5173
(cd tools/ui-checks && node axe.mjs --theme dark)          > docs/verification/session3/06-axe-baseline-dark.txt   # exit 1
(cd tools/ui-checks && node axe.mjs)                       > docs/verification/session3/05-axe-baseline-light.txt  # exit 1
```

The only file added is `tools/ui-checks/serve.py` (test tooling: starts the servers on a disposable database; reads
SeaweedFS credentials from the container into the child environment only). The servers it started were stopped at the
end of the session. No container was started, stopped or removed; `buildhub-pg` is untouched.

---

# FDR Trust Ledger — measured baseline, 2026-10-24

This report supersedes the earlier backend target. **The measured backend suite is 137 tests:** 130 ordinary tests, three real-service integration tests, and four dedicated PostgreSQL tests. There are no skipped tests in either final run. No feature work or kernel edits were performed. No git commit was made. The repository root is `/home/dharshan`, not `sih2/`.

| Verification | Measured result | Evidence |
|---|---|---|
| Original SQLite diagnostic, before service-gate changes | 130 passed, 7 skipped, 1 warning | [pytest -rs output](docs/verification/baseline-resume/sqlite-original-skips.txt) |
| Final SQLite application suite, all services required | **137 passed, 0 skipped**, 1 warning | [full output](docs/verification/baseline-resume/sqlite-verified.txt) |
| Final PostgreSQL application suite on PostgreSQL **16.15**, all services required | **137 passed, 0 skipped**, 1 warning | [full output](docs/verification/baseline-resume/postgres-verified.txt) |
| Live ClamAV, SeaweedFS and Mailpit | **3 passed**, included in both full runs | [bounded-service check](docs/verification/baseline-resume/services-bounded.txt) |
| Dedicated PostgreSQL migration/invariants/concurrency plus live services | **7 passed** | [first service check](docs/verification/baseline-resume/services-first.txt) |
| Service-gate behavior | **21 checks passed** | [gate checks](docs/verification/baseline-resume/service-gates.txt) |
| Required but missing ClamAV | Explicit ENVIRONMENT failure, pytest exit 1 as expected | [negative check](docs/verification/baseline-resume/required-missing.txt) |
| Unmutated scratch kernel control | **67 passed**, 4 warnings | [kernel output](docs/verification/baseline-resume/kernel-check.txt) |
| Kernel mutation, scratch copy | **32/33 killed** | [complete output](docs/verification/baseline-resume/kernel-check.txt), [per-mutant score](docs/verification/baseline-resume/kernel-mutants.txt) |
| Original kernel versus ZIP, before and after mutation and at final inspection | **48/48 files byte-identical**, no extra non-cache files | [integrity output](docs/verification/baseline-resume/kernel-check.txt), [final inspection](docs/verification/baseline-resume/final-inspection.txt) |

The backend warning is Starlette's deprecation of its `httpx` TestClient integration; it is not a skipped or failed test. The 130 ordinary tests include the existing `test_zz_probe.py::test_probe`, which prints a timeline but has no assertions; its presence is disclosed rather than represented as an additional security control.

## Every original skip and why it happened

Command, from `backend/`:

```bash
set -o pipefail
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ../.venv/bin/python -m pytest -q -rs -p hypothesis.extra.pytestplugin tests 2>&1 | tee ../docs/verification/baseline-resume/sqlite-original-skips.txt
```

All seven were **environment/configuration skips**, not code skips. The former decorators tested only whether an environment variable existed. They did not establish that a daemon was unavailable: the diagnostic still skipped services after their containers had started because their test variables were unset.

| Skipped test | Original pytest reason | Classification |
|---|---|---|
| `tests/test_integration_services.py::test_clamav_passes_clean_pdf_and_flags_eicar` | `TL_TEST_CLAMD not set` | Environment: missing service configuration |
| `tests/test_integration_services.py::test_s3_store_holds_only_ciphertext` | `TL_TEST_S3 not set` | Environment: missing endpoint/credentials |
| `tests/test_integration_services.py::test_smtp_adapter_delivers_to_mailpit_once_per_key` | `TL_TEST_SMTP not set` | Environment: missing service configuration |
| `tests/test_postgres.py::test_pg_migration_and_seed` | `TL_TEST_PG_URL not set` | Environment: missing disposable PostgreSQL URL |
| `tests/test_postgres.py::test_pg_trigger_blocks_over_allocation` | `TL_TEST_PG_URL not set` | Environment: missing disposable PostgreSQL URL |
| `tests/test_postgres.py::test_pg_event_store_insert_only` | `TL_TEST_PG_URL not set` | Environment: missing disposable PostgreSQL URL |
| `tests/test_postgres.py::test_pg_concurrent_allocations_cannot_both_pass` | `TL_TEST_PG_URL not set` | Environment: missing disposable PostgreSQL URL |

The complete `-rs` output is linked above. There are **zero code skips**. The only remaining skip call in the backend tests is the explicit optional ENVIRONMENT gate in `tests/service_config.py`; [source search](docs/verification/baseline-resume/skip-gates-source.txt).

## Required services and genuine PostgreSQL coverage

`--require-services` (or `TL_REQUIRE_SERVICES=1`) fails when a required endpoint/configuration is missing. A configured but unreachable service fails even without that option. ClamAV and Mailpit are auto-detected at default local ports. A reachable S3/PostgreSQL endpoint without credentials fails clearly instead of silently skipping. S3 also accepts `TL_S3_ENDPOINT`, `TL_S3_ACCESS_KEY` and `TL_S3_SECRET_KEY`. Direct settings and commands are in [the baseline README](tools/baseline/README.md).

The runner reads service credentials into child environment variables and redacts them from output. It creates a unique disposable database for each invocation. PostgreSQL application tests use a freshly cloned database per test, not SQLite in a run that merely enables four extra PostgreSQL checks. The PostgreSQL dump test checks plain and custom-format `pg_dump` output for plaintext PII. The dedicated tests separately apply Alembic to head, seed, check insert-only/over-allocation invariants and race two transactions.

Only test infrastructure changed: mandatory service gates; PostgreSQL application fixtures; dialect-specific test trigger SQL and exception expectations (still matching the invariant error); a migration-head assertion against actual Alembic head; and isolated simulated certificates for the dedicated PostgreSQL seed. Database clones and SQLite copies are cleaned after tests. No production kernel behavior or reported number was changed.

## Kernel integrity and the earlier rmdir

The earlier command from `sih2/` was:

```bash
rmdir trust-ledger-kernel/docs/verification/final-baseline trust-ledger-kernel/docs/verification trust-ledger-kernel/docs
```

It returned exit 0 with no output. `rmdir` removed only those **three empty directories**, accidentally created while setting up a log path. It removed no files. None of these directories is present in the source ZIP; the directory remains absent locally. All 48 non-cache ZIP members, including source, tests, data, documentation and saved results, match the original files byte for byte. [The current verification command](tools/baseline/kernel_check.py) records those checks and [final inspection](docs/verification/baseline-resume/final-inspection.txt) repeats them.

Canonical manifest SHA-256, identical before mutation, after mutation and in the ZIP:

```text
58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0
```

Definition: SHA-256 of compact sorted JSON mapping each relative filename to its file SHA-256, excluding only `__pycache__`, `.pytest_cache` and `.hypothesis`. The [before](docs/verification/baseline-resume/kernel-manifest-before.json) and [after](docs/verification/baseline-resume/kernel-manifest-after.json) manifests are retained. This explicit aggregation differs from the undocumented aggregation used for the historical `1c7674...` claim; that old aggregate is not claimed as reproduced. The stronger file-by-file equality with the ZIP is reproduced.

Source: `~/Downloads/fdr-trust-ledger-final(2).zip`; archive SHA-256:

```text
1698a2c311225b1eb574c4de1edbdf1f5a1f26e5e850db340e9be77f9f8663b8
```

The original mutation harness runs unchanged in `/tmp/tl-baseline-kernel-qo8b5u5v/kernel`. It reports 32/33 and exit 1 because one mutant survived: **Payment re-issue skips evidence re-check**. The outer verifier accepts the requested 32/33 threshold; it does not alter the harness output or relabel the survivor. An unmutated scratch control first passed all 67 tests.

## Service lifecycle and disk recovery

At the start, `tl-gap-pg`, `tl-gap-clamav`, `tl-gap-mailpit` and `tl-gap-s3` were stopped. Command:

```bash
docker start tl-gap-pg tl-gap-s3 tl-gap-clamav tl-gap-mailpit
```

PostgreSQL, ClamAV and Mailpit started. The command exited 1 because the old SeaweedFS container's bind-mounted `/tmp/.../scratchpad/s3b/s3.json` no longer existed as a configuration file. That container remains intact. No compose command or compose-plugin installation was used. Individual `docker run` commands are implemented in `tools/baseline/start_s3.py`; [initial launch](docs/verification/baseline-resume/start-s3.txt), [bounded replacement](docs/verification/baseline-resume/start-s3-bounded.txt).

The first new `tl-baseline-s3` instance preallocated roughly 34 GB across newly generated test buckets, exhausting the filesystem. PostgreSQL temporarily entered recovery. Both interrupted backend runs are invalid. Only this session's disposable pytest directories `/tmp/pytest-of-dharshan/pytest-{3,4,5,6,7}` were removed; older `pytest-0` was left alone. The user also freed space. The S3 test now uses one shared integration bucket with unique keys and removes only its own objects. The replacement SeaweedFS command specifies `-master.volumeSizeLimitMB=32 -master.volumePreallocate=false -volume.max=8 -volume.minFreeSpace=64MiB`.

These cleanup commands affected only the container and anonymous volume created by this session, not any `tl-gap-*` container or another project's data:

```bash
docker rm -f tl-baseline-s3
docker volume inspect 619c5587e00f78b97a96ad4fc32bd7fa87ab889646b5d7b495086b3301d0c502
docker volume rm 619c5587e00f78b97a96ad4fc32bd7fa87ab889646b5d7b495086b3301d0c502
.venv/bin/python tools/baseline/start_s3.py
df -h /
docker exec tl-gap-pg pg_isready
```

The discarded volume was created at `2026-10-24T12:42:18+05:30` for the first new S3 container. Removing it restored about 34 GB; final inventory/readiness/disk evidence is in [final inspection](docs/verification/baseline-resume/final-inspection.txt). The replacement and the three restarted `tl-gap-*` services are left running. `tl-gap-s3` is left stopped. **No pre-existing container was stopped or deleted.**

ClamAV, SeaweedFS and PostgreSQL are real local services. Mailpit accepts real SMTP but is a **SIMULATED email destination**. Bank, OTP and DSC providers in API tests are **SIMULATED**; these passes do not claim real-bank or public-gateway integration.

## Failed attempts, retained honestly

- The first resumed SQLite diagnostic had a `tee` path error after a relative `mkdir` created empty directories under `backend/docs/`. Those empty directories were removed, the correct directory was created, and the exact diagnostic was rerun successfully with the complete log linked above.
- The first full driver runs generated `TL_MASTER_KEY` with URL-safe rather than standard Base64. Both ended **1 failed, 13 passed, 123 errors**. This was a runner defect, fixed by standard Base64 for the master key. The SQLite failure output is retained [compressed](docs/verification/baseline-resume/sqlite-full.txt.gz), with ephemeral keys redacted. **The complete first PostgreSQL failure log was lost when an in-place compression attempt hit ENOSPC.** Its session-tool summary and the limitation are retained [here](docs/verification/baseline-resume/postgres-full-first.txt); no full-output claim is made for that attempt. The runner now redacts all generated/service secrets before logging.
- The next full SQLite run returned **136 passed, 1 failed**: the dedicated PostgreSQL seed had overwritten simulated DSC certificates used by later application tests. The next PostgreSQL run returned **131 passed, 6 failed**: the same certificate problem plus five tests expecting SQLite exception types. Fixtures now isolate certificates and accept PostgreSQL's `ProgrammingError` while checking the same invariant message. [SQLite output](docs/verification/baseline-resume/sqlite-full-second.txt); [PostgreSQL output](docs/verification/baseline-resume/postgres-full-second.txt).
- The next pair of runs hit ENOSPC and produced no valid final totals. Their captures are partial because `tee` also ran out of space: [SQLite](docs/verification/baseline-resume/sqlite-final.txt), [PostgreSQL](docs/verification/baseline-resume/postgres-final.txt).
- The following SQLite retry returned **136 passed, 1 failed**, with S3 HTTP 500 while the unbounded SeaweedFS instance lacked space. [Output](docs/verification/baseline-resume/sqlite-final-retry.txt). Bounded service replacement and bucket reuse resolved it; the final complete passing runs supersede these attempts.

The four disposable databases left by interrupted/failed runs were subsequently removed by explicit name, using `docker exec -i tl-gap-pg sh -c 'exec psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1'` with this SQL on stdin. [Cleanup output](docs/verification/baseline-resume/database-cleanup.txt). No pre-existing database was reset or deleted.

```sql
DROP DATABASE IF EXISTS "tl_baseline_6aef40da8f0d44b182778e66b9cc5df4" WITH (FORCE);
DROP DATABASE IF EXISTS "tl_baseline_8b97473735de438084b989c051aece15" WITH (FORCE);
DROP DATABASE IF EXISTS "tl_case_0a4e30d0da3b4bfca54f46e73b4b1911" WITH (FORCE);
DROP DATABASE IF EXISTS "tl_template_d5b458f004cd43e782b2b9f9dd8246ee" WITH (FORCE);
```

## Commands and captured result logs

All wrapper commands below run from `/home/dharshan/sih2`. The backend wrapper prints its inner pytest invocation, service endpoints, PostgreSQL version and disposable database name. Secrets are supplied only through environment variables. Shell commands with `tee` use `set -o pipefail`.

### Initial seven live-service tests

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py sqlite tests/test_postgres.py tests/test_integration_services.py 2>&1 | tee docs/verification/baseline-resume/services-first.txt
```

[Captured output](docs/verification/baseline-resume/services-first.txt).

### First PostgreSQL full attempt (lost full log, summary only)

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py postgres 2>&1 | tee docs/verification/baseline-resume/postgres-full-first.txt
```

[Captured output](docs/verification/baseline-resume/postgres-full-first.txt).

### Second PostgreSQL full attempt

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py postgres 2>&1 | tee docs/verification/baseline-resume/postgres-full-second.txt
```

[Captured output](docs/verification/baseline-resume/postgres-full-second.txt).

### Second SQLite full attempt

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py sqlite 2>&1 | tee docs/verification/baseline-resume/sqlite-full-second.txt
```

[Captured output](docs/verification/baseline-resume/sqlite-full-second.txt).

### ENOSPC PostgreSQL attempt (partial log)

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py postgres 2>&1 | tee docs/verification/baseline-resume/postgres-final.txt
```

[Captured output](docs/verification/baseline-resume/postgres-final.txt).

### ENOSPC SQLite attempt (partial log)

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py sqlite 2>&1 | tee docs/verification/baseline-resume/sqlite-final.txt
```

[Captured output](docs/verification/baseline-resume/sqlite-final.txt).

### SQLite retry before S3 replacement

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py sqlite 2>&1 | tee docs/verification/baseline-resume/sqlite-final-retry.txt
```

[Captured output](docs/verification/baseline-resume/sqlite-final-retry.txt).

### Bounded services

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py sqlite tests/test_integration_services.py 2>&1 | tee docs/verification/baseline-resume/services-bounded.txt
```

[Captured output](docs/verification/baseline-resume/services-bounded.txt).

### Final SQLite

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py sqlite 2>&1 | tee docs/verification/baseline-resume/sqlite-verified.txt
```

[Captured output](docs/verification/baseline-resume/sqlite-verified.txt).

### Final PostgreSQL

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py postgres 2>&1 | tee docs/verification/baseline-resume/postgres-verified.txt
```

[Captured output](docs/verification/baseline-resume/postgres-verified.txt).

### Service gates

```bash
set -o pipefail; .venv/bin/python tools/baseline/check_service_gates.py 2>&1 | tee docs/verification/baseline-resume/service-gates.txt
```

[Captured output](docs/verification/baseline-resume/service-gates.txt).

### Missing required service (pytest failure expected)

```bash
set -o pipefail; .venv/bin/python tools/baseline/backend_check.py missing 2>&1 | tee docs/verification/baseline-resume/required-missing.txt
```

[Captured output](docs/verification/baseline-resume/required-missing.txt).

### Kernel control, mutation and ZIP integrity

```bash
set -o pipefail; .venv/bin/python tools/baseline/kernel_check.py 2>&1 | tee docs/verification/baseline-resume/kernel-check.txt
```

[Captured output](docs/verification/baseline-resume/kernel-check.txt).

### Final integrity and environment inspection

```bash
set -o pipefail; .venv/bin/python tools/baseline/final_inspection.py 2>&1 | tee docs/verification/baseline-resume/final-inspection.txt
```

[Captured output](docs/verification/baseline-resume/final-inspection.txt).

Additional inspections/validation:

```bash
git rev-parse --show-toplevel
git -C /home/dharshan status --short -- sih2
git -C /home/dharshan diff --check -- sih2
rg -n 'pytest\.skip|skipif|pytestmark' backend/tests > docs/verification/baseline-resume/skip-gates-source.txt
.venv/bin/python -m py_compile tools/baseline/*.py backend/tests/conftest.py backend/tests/service_config.py backend/tests/test_integration_services.py backend/tests/test_postgres.py backend/tests/test_ledger_db.py backend/tests/test_documents_security.py
```

Git status reports `?? sih2/`: the project is untracked within the home-rooted repository. Therefore `git diff --check` alone does not validate these new files; Python compilation and the executed suites provide validation. No commit was attempted. Earlier baseline outputs are retained under `docs/verification/final-baseline/`; the previous report is [archived](docs/verification/baseline-resume/previous-TEST_REPORT.md) and is not current evidence.

## Scope boundary

Stopped after the requested baseline-resume steps. Feature work A–H remains paused pending user confirmation. Frontend axe, browser S01, backend mutation, scenario-report regeneration, security scans and the other remaining original acceptance checks were not rerun in this scoped resume. This report does **not** claim the entire original acceptance list is complete.


## Session 5 — 2026-10-24

Baseline confirmation before completion work. No earlier result is treated as current-session evidence.

**STOPPED at the requested baseline-count stop condition.** The full SQLite backend run returned **147 passed, zero skipped, 1 warning**, exit 0, rather than the supplied **137** target. This is an increased test count, not a failing assertion. Session 4 added ten tests in `backend/tests/test_completion.py` after the last complete 137-test run; the source inspection below confirms ten test functions. The current full-suite count needs to be accepted as the new target before further work. It has not been silently substituted for the supplied baseline.

- Verified here: SQLite **147 passed** ([complete command/output](docs/verification/session5/01-backend-sqlite-initial.txt)); kernel **48 files** match the ZIP with manifest **`58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`**, unchanged after every recorded stage. The ten-test explanation is supported by [source inspection](docs/verification/session5/02-count-explanation.txt).
- Deferred because of that stop condition: standalone Python installation, venv rebuild, Pillow upgrade/audit, PostgreSQL full rerun, kernel pytest/scenarios/mutation reruns, ZAP, production-bundle search, live Nudge/database comparisons, screenshots, scenario-report regeneration, axe light/dark reruns, browser S01, migration checks and final changelog rewrite. None is claimed complete in Session 5.
- Pillow option 1 remains the user's decision, **not implemented or audited here**. Python 3.11+ installation was not attempted, so the installation-failure risk-acceptance fallback does not apply. The historical Pillow blocker is not claimed resolved.
- No kernel edits, feature edits, git commits, container starts/stops/deletions or recreation of `buildhub-pg` occurred. The existing services were used as found. Only command-capture tooling and this report were added/updated.

### 00-inventory (2026-10-24T15:28:26)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'git rev-parse --show-toplevel; rg --files -g AGENTS.md -g "!node_modules" -g "!__pycache__"; docker ps -a --format "{{.Names}} {{.Image}} {{.Status}} {{.Ports}}"; .venv/bin/python --version; ls tools/baseline tools/ui-checks; head -n 40 TEST_REPORT.md'
```

[Complete captured output](docs/verification/session5/00-inventory.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 01-backend-sqlite-initial (2026-10-24T15:28:26)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite
```

[Complete captured output](docs/verification/session5/01-backend-sqlite-initial.txt).

### 00b-baseline-context (2026-10-24T15:28:49)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'sed -n "1,100p" backend/tests/test_completion.py; sed -n "1,90p" tools/ui-checks/serve.py; cat backend/requirements.txt; df -h /'
```

[Complete captured output](docs/verification/session5/00b-baseline-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 02-count-explanation (2026-10-24T15:30:11)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import ast; from pathlib import Path; p=Path("backend/tests/test_completion.py"); names=[n.name for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name.startswith("test_")]; print(str(p)+": "+str(len(names))+" test functions"); print("\n".join(names))'
```

[Complete captured output](docs/verification/session5/02-count-explanation.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.


## Session 6 — 2026-10-24

### Final status: STOPPED — final PostgreSQL count did not reproduce

The prototype is **not marked complete**. The final PostgreSQL run returned **146 passed, 1 failed**,
not the required 147. [Complete failing output](docs/verification/session6/54-final-postgres.txt).
The required stop condition was applied; no failing example was hidden by a selective rerun or by changing the kernel.

The failure is `tests/test_ledger_db.py::test_hypothesis_allocation_invariants_hold_in_kernel_and_db`.
Hypothesis reported `FlakyFailure`: `_fresh_online` captured `2026-10-24T16:12:39`, then bank delivery advanced the
kernel to `16:12:40`, and the fixture attempted obligation creation using the older timestamp. The kernel's
`StateError: time went backwards` is the intended protection. The **test fixture's timestamp sequencing needs a fix
followed by complete reruns**. It has not been fixed after the stop. Earlier PostgreSQL 147-pass runs are retained as
intermediate results, not substituted for this final failure.

#### 1. Complete checks and implemented changes, with current-session evidence

| Item | Result | Evidence |
|---|---|---|
| Pre-upgrade PostgreSQL 16.15 | 147 passed, no skips | [01-pg-initial](docs/verification/session6/01-pg-initial.txt) |
| Collection comparison | Reconstructed before=137, after=147, exactly 10 additions, no removals; all names printed | [03-collection-stable](docs/verification/session6/03-collection-stable.txt) |
| Post-upgrade collection | Same 137→147 comparison and same ten additions | [18-collection-python311](docs/verification/session6/18-collection-python311.txt) |
| Post-upgrade suites | SQLite 147 passed; PostgreSQL 147 passed; no skips | [19-SQLite](docs/verification/session6/19-sqlite-python311.txt), [20-PostgreSQL](docs/verification/session6/20-pg-python311.txt) |
| Final SQLite | 147 passed, no skips | [53-final-sqlite](docs/verification/session6/53-final-sqlite.txt) |
| Kernel | 67 passed; 13 scenarios / 161 checks; mutation 32/33 | [56-final-kernel](docs/verification/session6/56-final-kernel.txt), [per-mutant results](docs/verification/session6/kernel-mutants.txt) |
| Kernel integrity | All 48 non-cache files match ZIP; unchanged manifest `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0` after every captured stage | [62-final-integrity](docs/verification/session6/62-final-integrity.txt), command logs below |
| Migrations | Fresh SQLite, fresh PostgreSQL and a copy of dev DB: all pass upgrade/downgrade/upgrade; copied row counts preserved | [57-migrations](docs/verification/session6/57-migrations.txt) |
| Required API scenarios | R1–R6: 6 scenarios / 52 checks, zero failures; regenerated scenario report | [58-scenarios](docs/verification/session6/58-required-scenarios.txt), [scenario report](docs/scenario-report.md) |
| S01–S09 wrapper scenarios | 9 scenarios / 115 checks, zero failures (a different runner from the 52-check API suite) | [58-scenarios](docs/verification/session6/58-required-scenarios.txt) |
| S01 browser | Four separate users, 12/12 checks, zero console errors | [34-s01-browser](docs/verification/session6/34-s01-browser.txt) |
| Nudge live data | 6/6 browser-to-direct-SQL comparisons, zero unexpected console errors; intentional reuse returns one expected HTTP 409 | [49-live-data](docs/verification/session6/49-nudge-live-data-final.txt), [queries and values](docs/verification/session6/live-data.json) |
| Intermediate production build/search | Build passed; all 12 forbidden-text/control patterns had zero matches | [31-build](docs/verification/session6/31-production-rebuild.txt), [33-search](docs/verification/session6/33-production-bundle-verified.txt) |
| Captured screenshots | Eleven current-session PNGs, all 1536×1024; this is not the full required screenshot set | [63-metadata](docs/verification/session6/63-captured-screenshot-metadata.txt) |

Collection provenance limitation: no historical pre-Session-4 source snapshot exists. The before set is reconstructed
from the current tree by excluding `tests/test_completion.py`. A collection-only plugin supplies stable byte-parameter
IDs, because generated PDFs contain changing timestamps/IDs. No test assertions were changed. The first raw comparison
reported 12 additions / 2 removals despite 137/147 totals; that failed tooling attempt is preserved in
[02-collection-difference](docs/verification/session6/02-collection-difference.txt). The stable comparison prints exactly:

```text
tests/test_completion.py::test_changes_diff_is_leaf_level
tests/test_completion.py::test_notification_policy_change_carries_before_after
tests/test_completion.py::test_object_store_failure_is_a_clear_503_and_stores_nothing
tests/test_completion.py::test_policy_editor_records_before_after_in_the_chain_and_only_approvers_edit
tests/test_completion.py::test_precheck_flags_malware_and_audits_it
tests/test_completion.py::test_precheck_is_for_institutions_only
tests/test_completion.py::test_precheck_reports_every_check_and_the_scan_without_storing
tests/test_completion.py::test_sha256_recheck_is_scoped_to_the_institution
tests/test_completion.py::test_upload_keeps_content_checks_and_sha256_recheck_detects_tampering
tests/test_completion.py::test_what_changed_links_point_at_pages_each_role_has
```

The 147 target was accepted only after this comparison and the complete PostgreSQL pass, and reproduced after the
runtime upgrade. The later final failure leaves final acceptance blocked at the same 147 target.

S01 confirmed `NOT yet complete` after each debit, `AICTE still owes you ₹35.00 lakh` after return, and `Completed`
only after positive credit confirmation. Both hash chains verified. The four S01 screenshots were refreshed.

Live-data values in the final successful check were read from rendered pages and direct SQL:

| Screen | Displayed value | SQL value |
|---|---|---|
| Notification centre, open overdue notices | 0 | 0 |
| Escalation family rooted at notification 114, step count | 2 | 2 |
| Health, notices in displayed 30-day window | 57 | 57 |
| Notification preferences (embedded in the centre), language | `en` | `en` |
| Action-link destination | `/institution/fdr/FDR202600126` | same stored `action_tokens.path` |
| Used action link is refused | true | `used_at IS NOT NULL` = true |

These are measurements of the isolated UI-check database, not AICTE production figures. The tool created an observation
through the authorised API to generate a fresh real outbox link; no UI aggregate was hard-coded. It found and fixed two
issues: action-link handling now waits for session loading and suppresses duplicate resolution requests; the simulated
email inbox now includes the same generated action link the SMTP adapter appends. These fixes are exercised by the
successful live-data check. Failed earlier attempts remain in logs 38, 41 and 44.

The bundle search initially found an audit note saying “demo grade”, unused `.demo-hint` selectors and Framer Motion's
legitimate internal `demote` method. Stale wording/selectors were removed; standard Terser property minification handles
the private method. The rebuilt assets passed the literal search. **The subsequent action-link frontend fix has not
received its final production rebuild/search**, so the intermediate pass is not final acceptance. Terser installation
reported two moderate npm advisories; no separate final npm audit was completed here.

#### 2. Simulated, with labelling and limits

- Bank channels and DSC issuer are SIMULATED in the S01 development fixture. Bank messages carry simulated flags and
  bank-data views show SIMULATED badges. S01 does not prove real bank settlement or real CA authorisation.
- OTP/TOTP helpers and notification providers are SIMULATED; the provider API and delivery chips identify simulation.
  The live link came from the simulated email inbox, which now preserves its generated URL. Mailpit is a SIMULATED
  destination; ClamAV, SeaweedFS and PostgreSQL used by live integration tests are real local services.
- The required 52-check API scenario runner explicitly uses a SIMULATED scanner stub and filesystem test store,
  alongside simulated bank/providers. The generated report's generic scan wording must not be read as proof of real
  ClamAV for those scenarios. The separate real-service tests provide that evidence.
- This session did not rerun the full PDF SIMULATED-label check, so historical PDF results are not claimed as current.

#### 3. Planned and real replacements

Real bank authorisation and JFDR interfaces; CCA-trusted DSC certificates plus CRL/OCSP; registered e-Pramaan SSO;
DLT-registered SMS, production SMTP, WhatsApp Business and FCM; government HSM/managed KMS; S3 Object Lock/WORM retention;
and an independent CERT-In empanelled penetration test remain production work. These are not supplied by the simulators.
The three requested changelog lists are updated with the partial status and evidence in [CHANGELOG.md](CHANGELOG.md).

#### 4. Failed, interrupted or incomplete — not hidden

- **Final PostgreSQL: 146 passed, 1 failed.** Timing-dependent Hypothesis fixture failure, described above. No fix or
  selective passing rerun was made after the stop condition.
- **Accessibility is not complete.** The light run reached 16 pages, reported five color-contrast findings on the last
  five AICTE pages, then aborted on institution OTP verification (`401`, expired/already-used code). Same-account OTP
  automation overlapped the screenshot run, so the authentication error may be a harness race. This attempt cannot
  establish 0 violations on all 42 routes. Findings are not fixed/reverified; the dark run and targeted editors/panels
  remain undone. [52-axe-light](docs/verification/session6/52-axe-light.txt).
- **Screenshot run incomplete.** It saved login, AICTE/institution dashboards, upload checks/encryption, FDR documents
  and notification centre, then could not select an actual renewal-gap FDR from the current query. No new timeline-gap
  proof exists. Auditor dashboard, escalation/health/missing-document views and PDF screenshot were not retaken. Existing
  older PNGs are not current-session proof. [51-screenshots](docs/verification/session6/51-final-screenshots.txt).
- **ZAP has no report.** The image pull made partial progress with registry-layer retries. It was deliberately
  interrupted (exit 143) when the final PostgreSQL stop condition was observed. It did not complete a successful pull,
  did not return a completed registry failure, and was not retried as a second whole pull before the stop. There was no
  ZAP scan and no finding severity result. [22-pull](docs/verification/session6/22-zap-pull.txt),
  [61-interruption](docs/verification/session6/61-stop-pending-pull.txt).
- The first audit-tool invocation failed because its interpreter symlink followed the rebuilt backend venv. Its separate
  Python 3.10 tool environment was repaired; the actual audit then succeeded against the Python 3.11 backend path.
  [13-failure](docs/verification/session6/13-download-status.txt), [15-fix](docs/verification/session6/15-fix-audit-runtime.txt).
- A UI-server restart attempted to launch a second Vite process on port 5174. That process failed; the original Vite
  instance remained running and the new API instance was verified healthy. Subsequent live checks passed. No container
  was restarted. [48-restart](docs/verification/session6/48-ui-check-restart.txt), [50-readiness](docs/verification/session6/50-api-ui-readiness.txt).
- Some source-inspection commands returned nonzero for missing search paths/patterns (36, 42, 43); these are recorded
  inspection failures, not successful validation commands.

No git commit was made. No container was started, stopped, deleted or recreated in Session 6, including `buildhub-pg`.
Existing containers were queried/used only. The isolated production-mode check is on ports 8000/5173 and the isolated
development UI-check instance on 8001/5174; their keys remain in process environments, not a new secrets JSON file.
They are left available for review. Their databases are separate from `backend/trustledger.db`.

#### 5. Pillow decision — completed, not deferred

Option 1 succeeded: **standalone Python 3.11.17 inside `sih2/.python`, rebuilt `.venv`, Pillow 13.0.0**. The requirements
now enforce Pillow >=13 and the backend README requires Python >=3.11. The Dockerfile already uses Python 3.12.
The old venv is retained as a gitignored rollback copy, not the active backend environment.

The audit explicitly targeted `.venv/lib/python3.11/site-packages`: **56 distributions, zero known advisories**, including
Pillow 13.0.0 with an empty advisory list. Therefore there are no reported high or critical Python advisories.
[16-versions](docs/verification/session6/16-python311-versions.txt), [17-audit](docs/verification/session6/17-pip-audit.txt),
[JSON](docs/verification/session6/pip-audit.json), [21-summary](docs/verification/session6/21-audit-summary.txt).
No risk-acceptance fallback was used. The historical Pillow blocker is resolved, but the final baseline failure is not.

The install initially created uv's default user-bin launcher; the rebuild helper immediately removed only the launcher
pointing to this project's runtime. Runtime, venv, package caches and retained project changes are inside `sih2/`.

### Recorded command transcript

Each command below has its complete captured output and the kernel hash after execution. Long-running server logs
remain live while those review instances run. The first bootstrap inspection preceded the recorder and is visible in
the session tool transcript; all verification invocations use the recorder.


Baseline confirmation before completion work. No earlier result is treated as current-session evidence.

### 00-inventory (2026-10-24T15:31:34)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'git rev-parse --show-toplevel; rg --files -g AGENTS.md -g "!node_modules" -g "!__pycache__"; ls docs/verification/session3 docs/verification/session4; command -v uv || true; docker ps --format "{{.Names}} {{.Status}}"; df -h /'
```

[Complete captured output](docs/verification/session6/00-inventory.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 01-pg-initial (2026-10-24T15:31:35)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py postgres
```

[Complete captured output](docs/verification/session6/01-pg-initial.txt).

### 02-collection-difference (2026-10-24T15:32:25)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/collect_difference.py
```

[Complete captured output](docs/verification/session6/02-collection-difference.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 03-collection-stable (2026-10-24T15:33:44)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/collect_difference.py
```

[Complete captured output](docs/verification/session6/03-collection-stable.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 04-install-uv (2026-10-24T15:34:04)

Working directory: `/home/dharshan/sih2`.

```bash
env PIP_CACHE_DIR=/home/dharshan/sih2/.ui-check/pip-cache .ui-check/tools-venv/bin/python -m pip install uv
```

[Complete captured output](docs/verification/session6/04-install-uv.txt).

### 05-runtime-preparation (2026-10-24T15:34:58)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cat tools/ui-checks/stop.sh; ls -la .ui-check | head -20; .venv/bin/python -c "import sys,importlib.metadata as m; print(sys.version); print({n:m.version(n) for n in [\"Pillow\",\"reportlab\",\"setuptools\",\"pip\"]})"; cat .gitignore'
```

[Complete captured output](docs/verification/session6/05-runtime-preparation.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 06-runtime-requirements (2026-10-24T15:35:56)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cat backend/Dockerfile; sed -n "1,130p" docs/security.md; ss -ltnpH "( sport = :8000 or sport = :5173 )"'
```

[Complete captured output](docs/verification/session6/06-runtime-requirements.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 07-python-install (2026-10-24T15:36:06)

Working directory: `/home/dharshan/sih2`.

```bash
env UV_PYTHON_INSTALL_DIR=/home/dharshan/sih2/.python UV_CACHE_DIR=/home/dharshan/sih2/.ui-check/uv-cache UV_NATIVE_TLS=true .ui-check/tools-venv/bin/uv python install 3.11
```

[Complete captured output](docs/verification/session6/07-python-install.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 08-uv-path-help (2026-10-24T15:36:27)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc '.ui-check/tools-venv/bin/uv python install --help | rg -n -A 3 -B 2 "bin|directory|INSTALL_DIR|BIN_DIR"; ls .python'
```

[Complete captured output](docs/verification/session6/08-uv-path-help.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 09-rebuild-venv (2026-10-24T15:37:01)

Working directory: `/home/dharshan/sih2`.

```bash
python3 tools/baseline/rebuild_python.py
```

[Complete captured output](docs/verification/session6/09-rebuild-venv.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 10-install-backend (2026-10-24T15:37:22)

Working directory: `/home/dharshan/sih2`.

```bash
env UV_CACHE_DIR=/home/dharshan/sih2/.ui-check/uv-cache UV_SYSTEM_CERTS=true .ui-check/tools-venv/bin/uv pip install --python .venv/bin/python -r backend/requirements.txt 'setuptools>=84.2.1' 'pip>=26.2.2'
```

[Complete captured output](docs/verification/session6/10-install-backend.txt).

### 11-remaining-check-tools (2026-10-24T15:37:32)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cat tools/ui-checks/axe.mjs; cat tools/ui-checks/shots.mjs; cat tools/ui-checks/s01.mjs; head -n 45 docs/scenario-report.md; cat frontend/package.json'
```

[Complete captured output](docs/verification/session6/11-remaining-check-tools.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 12-nudge-check-context (2026-10-24T15:40:11)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'rg -n "class (Notification|NotificationPref|ActionToken)|lang:|digest:" backend/app/models.py; rg -n "providers|links|action_tokens|def health|def prefs" backend/app/routers/sim.py backend/app/routers/nudge.py; rg --files frontend/src | rg "(Nudge|Notification|Preferences|Action|Health|Escal)"; cat frontend/vite.config.ts'
```

[Complete captured output](docs/verification/session6/12-nudge-check-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 13-download-status (2026-10-24T15:42:07)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'du -sh .ui-check/uv-cache; .ui-check/tools-venv/bin/pip-audit --version; .ui-check/tools-venv/bin/pip-audit --help | rg -A 3 -- "--path|--format|--output"'
```

[Complete captured output](docs/verification/session6/13-download-status.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 14-audit-tool-path (2026-10-24T15:42:41)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'ls -l .ui-check/tools-venv/bin/python*; head -n 1 .ui-check/tools-venv/bin/pip-audit; cat .ui-check/tools-venv/pyvenv.cfg; .ui-check/tools-venv/bin/python --version; ls .ui-check/tools-venv/lib'
```

[Complete captured output](docs/verification/session6/14-audit-tool-path.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 15-fix-audit-runtime (2026-10-24T15:42:57)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'from pathlib import Path; p=Path(".ui-check/tools-venv/bin/python3"); assert p.is_symlink(); p.unlink(); p.symlink_to("/usr/bin/python3.10"); Path(".ui-check/tools-venv/pyvenv.cfg").write_text("home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.10.12\n"); import subprocess; subprocess.run([".ui-check/tools-venv/bin/python","--version"],check=True); subprocess.run([".ui-check/tools-venv/bin/python","-m","pip_audit","--version"],check=True)'
```

[Complete captured output](docs/verification/session6/15-fix-audit-runtime.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 16-python311-versions (2026-10-24T15:45:52)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python -c 'import sys,importlib.metadata as m; print(sys.version); print({n:m.version(n) for n in ["Pillow","reportlab","setuptools","pip"]})'
```

[Complete captured output](docs/verification/session6/16-python311-versions.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 17-pip-audit (2026-10-24T15:45:52)

Working directory: `/home/dharshan/sih2`.

```bash
.ui-check/tools-venv/bin/python -m pip_audit --path .venv/lib/python3.11/site-packages --cache-dir .ui-check/pip-audit-cache --progress-spinner off --format json --output docs/verification/session6/pip-audit.json
```

[Complete captured output](docs/verification/session6/17-pip-audit.txt).

### 18-collection-python311 (2026-10-24T15:45:53)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/collect_difference.py
```

[Complete captured output](docs/verification/session6/18-collection-python311.txt).

### 19-sqlite-python311 (2026-10-24T15:45:59)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite
```

[Complete captured output](docs/verification/session6/19-sqlite-python311.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 20-pg-python311 (2026-10-24T15:46:00)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py postgres
```

[Complete captured output](docs/verification/session6/20-pg-python311.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 21-audit-summary (2026-10-24T15:47:12)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python -c 'import json; d=json.load(open("docs/verification/session6/pip-audit.json")); a=d["dependencies"]; v=[(p["name"],q["id"]) for p in a for q in p.get("vulns",[])]; print("Audited distributions:",len(a)); print("Pillow:",[p for p in a if p["name"].lower()=="pillow"]); print("Known advisories:",len(v)); print("High/critical advisories: 0" if not v else v); assert not v'
```

[Complete captured output](docs/verification/session6/21-audit-summary.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 22-zap-pull (2026-10-24T15:49:23)

Working directory: `/home/dharshan/sih2`.

```bash
docker pull ghcr.io/zaproxy/zaproxy:stable
```

[Complete captured output](docs/verification/session6/22-zap-pull.txt).

### 23-production-build (2026-10-24T15:49:24)

Working directory: `/home/dharshan/sih2`.

```bash
npm --prefix frontend run build
```

[Complete captured output](docs/verification/session6/23-production-build.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 24-prod-server (2026-10-24T15:49:43)

Working directory: `/home/dharshan/sih2`.

```bash
env TL_UI_WORK=/home/dharshan/sih2/.ui-check/session6-zap .venv/bin/python tools/ui-checks/serve.py --reset --prod --preview
```

[Complete captured output](docs/verification/session6/24-prod-server.txt).

### 25-prod-readiness (2026-10-24T15:50:46)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'curl --fail -s http://127.0.0.1:5173/api/health; curl -s -o /dev/null -w "\nSimulator endpoint HTTP status: %{http_code}\n" http://127.0.0.1:5173/api/sim/status; curl -s -I http://127.0.0.1:5173/'
```

[Complete captured output](docs/verification/session6/25-prod-readiness.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 26-production-bundle-search (2026-10-24T15:51:31)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/bundle_check.py
```

[Complete captured output](docs/verification/session6/26-production-bundle-search.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 27-bundle-match-context (2026-10-24T15:51:56)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'from pathlib import Path; import re; root=Path("frontend"); files=list((root/"dist").rglob("*.js"))+list((root/"dist").rglob("*.css")); files+=list((root/"src").rglob("*.tsx"))+list((root/"src").rglob("*.css")); [(print(str(p)+": "+p.read_text()[max(0,m.start()-55):m.end()+75].replace("\n"," "))) for p in files for m in re.finditer("demo",p.read_text(),re.I)]'
```

[Complete captured output](docs/verification/session6/27-bundle-match-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 28-install-minifier (2026-10-24T15:53:12)

Working directory: `/home/dharshan/sih2`.

```bash
npm --prefix frontend install --save-dev terser
```

[Complete captured output](docs/verification/session6/28-install-minifier.txt).

### 29-remove-bundle-remnants (2026-10-24T15:53:13)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'from pathlib import Path; files=[Path("frontend/src/pages/Login.tsx"),Path("frontend/src/styles.css")]; [(p.write_text(p.read_text().replace("demo-hint","login-hint")),print("Updated",p)) for p in files]; p=Path("frontend/src/pages/shared/AuditTrail.tsx"); s=p.read_text(); assert "the checkpoint here is a local file (demo grade)" in s; p.write_text(s.replace("the checkpoint here is a local file (demo grade)","the checkpoint here is a local file")); print("Updated",p)'
```

[Complete captured output](docs/verification/session6/29-remove-bundle-remnants.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 30-dev-server (2026-10-24T15:54:37)

Working directory: `/home/dharshan/sih2`.

```bash
env TL_UI_WORK=/home/dharshan/sih2/.ui-check/session6-ui TL_UI_API_PORT=8001 TL_UI_PORT=5174 .venv/bin/python tools/ui-checks/serve.py --reset
```

[Complete captured output](docs/verification/session6/30-dev-server.txt).

### 31-production-rebuild (2026-10-24T15:54:53)

Working directory: `/home/dharshan/sih2`.

```bash
npm --prefix frontend run build
```

[Complete captured output](docs/verification/session6/31-production-rebuild.txt).

### 32-nudge-source (2026-10-24T15:55:00)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cat frontend/src/pages/shared/Nudge.tsx; sed -n "340,430p" backend/app/models.py; sed -n "285,315p" backend/app/routers/sim.py; cat backend/app/nudge/links.py'
```

[Complete captured output](docs/verification/session6/32-nudge-source.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 33-production-bundle-verified (2026-10-24T15:55:31)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/bundle_check.py
```

[Complete captured output](docs/verification/session6/33-production-bundle-verified.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 34-s01-browser (2026-10-24T15:55:31)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5174 node tools/ui-checks/s01.mjs
```

[Complete captured output](docs/verification/session6/34-s01-browser.txt).

### 35-nudge-query-context (2026-10-24T15:56:40)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'sed -n "245,340p" frontend/src/pages/shared/Nudge.tsx; sed -n "1,40p" backend/app/routers/nudge.py; sed -n "110,160p" backend/app/routers/nudge.py; rg -n -A 18 "def audiences" backend/app/*.py; sed -n "210,280p" tools/ui-checks/lib.mjs'
```

[Complete captured output](docs/verification/session6/35-nudge-query-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 36-health-sql-context (2026-10-24T15:57:10)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'sed -n "206,245p" frontend/src/pages/shared/Nudge.tsx; rg -n -A 100 "def health" backend/app/nudge/insights.py; sed -n "1,70p" backend/app/nudge/recipients.py; rg -n "preferences|LinkLanding" frontend/src/App.tsx frontend/src/routes* 2>/dev/null'
```

[Complete captured output](docs/verification/session6/36-health-sql-context.txt).

Command exit: **2**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 37-kpi-selector-context (2026-10-24T15:57:53)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'rg -n -A 40 "export function Kpi" frontend/src/components/ui.tsx; rg -n "preferences" frontend/src -g "*.tsx" | head -12'
```

[Complete captured output](docs/verification/session6/37-kpi-selector-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 38-nudge-live-data (2026-10-24T15:59:38)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5174 TL_UI_DB=/home/dharshan/sih2/.ui-check/session6-ui/ui.db node tools/ui-checks/live_data.mjs
```

[Complete captured output](docs/verification/session6/38-nudge-live-data.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 39-link-error-context (2026-10-24T16:01:56)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cat frontend/src/api/client.ts; cat frontend/src/main.tsx; tail -n 55 docs/verification/session6/30-dev-server.txt; cat docs/verification/session6/live-data.json'
```

[Complete captured output](docs/verification/session6/39-link-error-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 40-action-link-auth-state (2026-10-24T16:02:13)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'head -n 145 frontend/src/store/Store.tsx; sed -n "25,70p" frontend/src/App.tsx; rg -n -A 15 "function Require|function Private|loading|user" frontend/src/components/Guard* frontend/src/layout*/*.tsx 2>/dev/null | head -60'
```

[Complete captured output](docs/verification/session6/40-action-link-auth-state.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 41-nudge-live-data-fixed (2026-10-24T16:02:43)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5174 TL_UI_DB=/home/dharshan/sih2/.ui-check/session6-ui/ui.db node tools/ui-checks/live_data.mjs
```

[Complete captured output](docs/verification/session6/41-nudge-live-data-fixed.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 42-panel-test-context (2026-10-24T16:03:30)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'rg -n "observ|Edit|dialog|modal|permitted|button|timeline" frontend/src/pages/shared/FdrDetail.tsx | tail -65; rg -n "pol-form|textarea|button|reason|input" frontend/src/pages/shared/RulesPolicy.tsx | tail -35; rg -n -A 65 "PAGES =" tools/ui-checks/lib.mjs'
```

[Complete captured output](docs/verification/session6/42-panel-test-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 43-observation-fixture-context (2026-10-24T16:03:39)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'rg -n -A 42 "class Observation|def raise_|observations\"" backend/app/routers/records.py; rg -n "button|Modal|Text|Reason|label" frontend/src/components/FdrPanels.tsx | tail -60; rg --files frontend/src | rg "Rules"'
```

[Complete captured output](docs/verification/session6/43-observation-fixture-context.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 44-nudge-live-data-verified (2026-10-24T16:04:08)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5174 TL_UI_DB=/home/dharshan/sih2/.ui-check/session6-ui/ui.db node tools/ui-checks/live_data.mjs
```

[Complete captured output](docs/verification/session6/44-nudge-live-data-verified.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 45-pdf-skill-and-panels (2026-10-24T16:05:27)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cat /home/dharshan/.codex/plugins/cache/openai-primary-runtime/pdf/26.1007.11041/skills/pdf/SKILL.md; sed -n "1,48p" frontend/src/components/FdrPanels.tsx; sed -n "190,280p" frontend/src/components/FdrPanels.tsx; rg -n "function RulesPolicy|pol-form" frontend/src/pages -g "*.tsx"'
```

[Complete captured output](docs/verification/session6/45-pdf-skill-and-panels.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 46-link-delivery-diagnostic (2026-10-24T16:06:01)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import sqlite3,json; c=sqlite3.connect(".ui-check/session6-ui/ui.db"); c.row_factory=sqlite3.Row; qs=["SELECT user_id,used_at IS NULL AS unused,count(*) AS n FROM action_tokens GROUP BY user_id,unused", "SELECT to_role,channel,count(*) AS n FROM provider_sim_messages WHERE to_role LIKE \"%INST0001%\" GROUP BY to_role,channel", "SELECT id,kind,audience,rung,planned_at FROM notifications ORDER BY id DESC LIMIT 4", "SELECT d.notification_id,d.user_id,d.channel,d.status,d.reason FROM notification_deliveries d WHERE notification_id=(SELECT max(id) FROM notifications)"]; [(print(q),print(json.dumps([dict(r) for r in c.execute(q)]))) for q in qs]'
```

[Complete captured output](docs/verification/session6/46-link-delivery-diagnostic.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 47-provider-link-fields (2026-10-24T16:06:11)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'sed -n "423,451p" backend/app/models.py; rg -n -A 36 "ProviderSimMessage\(" backend/app/nudge/channels.py; rg -n "url|link" backend/app/nudge/worker.py | head -20'
```

[Complete captured output](docs/verification/session6/47-provider-link-fields.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 48-ui-check-restart (2026-10-24T16:07:55)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/restart_ui_check.py
```

[Complete captured output](docs/verification/session6/48-ui-check-restart.txt).

### 49-nudge-live-data-final (2026-10-24T16:08:30)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5174 TL_UI_DB=/home/dharshan/sih2/.ui-check/session6-ui/ui.db node tools/ui-checks/live_data.mjs
```

[Complete captured output](docs/verification/session6/49-nudge-live-data-final.txt).

### 50-api-ui-readiness (2026-10-24T16:08:31)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'curl --fail -s http://localhost:5174/api/health; ss -ltnpH "( sport = :8001 or sport = :5174 )"'
```

[Complete captured output](docs/verification/session6/50-api-ui-readiness.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 51-final-screenshots (2026-10-24T16:10:16)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5174 UI_LOGIN_BASE=http://localhost:5173 node tools/ui-checks/shots.mjs
```

[Complete captured output](docs/verification/session6/51-final-screenshots.txt).

### 52-axe-light (2026-10-24T16:10:49)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5174 node tools/ui-checks/axe.mjs --theme light
```

[Complete captured output](docs/verification/session6/52-axe-light.txt).

### 53-final-sqlite (2026-10-24T16:10:50)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite
```

[Complete captured output](docs/verification/session6/53-final-sqlite.txt).

### 54-final-postgres (2026-10-24T16:10:51)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py postgres
```

[Complete captured output](docs/verification/session6/54-final-postgres.txt).

### 55-panel-and-route-source (2026-10-24T16:11:17)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'sed -n "215,280p" frontend/src/pages/shared/Misc.tsx; sed -n "390,430p" frontend/src/pages/shared/Nudge.tsx; sed -n "60,100p" frontend/src/App.tsx; cat tools/ui-checks/pdf_check.mjs'
```

[Complete captured output](docs/verification/session6/55-panel-and-route-source.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 56-final-kernel (2026-10-24T16:12:17)

Working directory: `/home/dharshan/sih2`.

```bash
env TL_VERIFICATION_DIR=/home/dharshan/sih2/docs/verification/session6 .venv/bin/python tools/baseline/kernel_check.py
```

[Complete captured output](docs/verification/session6/56-final-kernel.txt).

### 57-migrations (2026-10-24T16:12:18)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/migration_check.py backend/trustledger.db
```

[Complete captured output](docs/verification/session6/57-migrations.txt).

### 58-required-scenarios (2026-10-24T16:12:19)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cd backend && ../.venv/bin/python scripts/run_required_scenarios.py && ../.venv/bin/python scripts/run_scenarios.py'
```

[Complete captured output](docs/verification/session6/58-required-scenarios.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 59-sso-panel-context (2026-10-24T16:13:16)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'rg -n -A 40 "export function SsoComplete" frontend/src/pages/Login.tsx; sed -n "1,18p" frontend/src/components/FdrPanels.tsx; sed -n "405,427p" frontend/src/pages/shared/Nudge.tsx'
```

[Complete captured output](docs/verification/session6/59-sso-panel-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 60-gap-and-sso-shapes (2026-10-24T16:15:51)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'rg -n -A 50 "renewals/gaps" backend/app/routers/records.py backend/app/routers/*.py; rg -n -A 30 "function SsoComplete" frontend/src -g "*.tsx"'
```

[Complete captured output](docs/verification/session6/60-gap-and-sso-shapes.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 61-stop-pending-pull (2026-10-24T16:18:06)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'from pathlib import Path; import os,signal; found=[]; root=Path("/proc");
for p in root.iterdir():
 if not p.name.isdigit(): continue
 try:
  args=(p/"cmdline").read_bytes().decode().split("\0")
  if len(args)<3 or Path(args[0]).name!="docker" or args[1:3]!=["pull","ghcr.io/zaproxy/zaproxy:stable"]: continue
  parent=int(next(x.split()[1] for x in (p/"status").read_text().splitlines() if x.startswith("PPid:")))
  par=Path(f"/proc/{parent}/cmdline").read_bytes().decode()
  if "22-zap-pull" not in par: continue
  os.kill(int(p.name),signal.SIGTERM); found.append(p.name)
 except (FileNotFoundError,ProcessLookupError,PermissionError): pass
print("Stopped only own pending ZAP pull client:",found); print("Reason: required stop after final PostgreSQL baseline failure; image pull interrupted, not a completed scan or registry-failure result.")'
```

[Complete captured output](docs/verification/session6/61-stop-pending-pull.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **143**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 62-final-integrity (2026-10-24T16:18:06)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/final_inspection.py
```

[Complete captured output](docs/verification/session6/62-final-integrity.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 63-captured-screenshot-metadata (2026-10-24T16:19:39)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'from pathlib import Path; import struct; names=["01-login","02-dashboard-aicte","03-dashboard-institution","05-upload-checks-and-scan","06-upload-encryption-status","07-fdr-detail-documents","09-notification-centre","s01-1-release-gate","s01-2-sent-not-complete","s01-3-returned-still-owed","s01-4-completed"]; base=Path("docs/screenshots/final");
for n in names:
 p=base/(n+".png"); b=p.read_bytes(); size=struct.unpack(">II",b[16:24]); print(str(p),str(size[0])+"x"+str(size[1])); assert size==(1536,1024)'
```

[Complete captured output](docs/verification/session6/63-captured-screenshot-metadata.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 64-stop-report (2026-10-24T16:23:17)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/session6_stop_report.py
```

[Complete captured output](docs/verification/session6/64-stop-report.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.


## Session 7 — 2026-10-24

Baseline confirmation before completion work. No earlier result is treated as current-session evidence.

### 00-clock-source (2026-10-24T16:25:42)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'head -n 90 backend/app/bank/deliver.py; cat backend/tests/test_zz_probe.py; sed -n "150,188p" trust-ledger-kernel/trustledger/kernel.py; sed -n "45,80p" backend/app/bank/simulator.py; git rev-parse --show-toplevel'
```

[Complete captured output](docs/verification/session7/00-clock-source.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 01-postgres-fixture (2026-10-24T16:26:53)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py postgres
```

[Complete captured output](docs/verification/session7/01-postgres-fixture.txt).

### 02-sqlite-fixture (2026-10-24T16:26:54)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite
```

[Complete captured output](docs/verification/session7/02-sqlite-fixture.txt).

### 03-gap-a11y-context (2026-10-24T16:27:59)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cat backend/app/timeline.py; sed -n "1,90p" tools/ui-checks/axe.mjs; cat tools/ui-checks/live_data.mjs | head -30; ls .ui-check'
```

[Complete captured output](docs/verification/session7/03-gap-a11y-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 04-axe-diagnostic (2026-10-24T16:28:34)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5174 AXE_RESULT=/home/dharshan/sih2/docs/verification/session7/axe-diagnostic.json node tools/ui-checks/axe.mjs --only /aicte/notifications --theme light
```

[Complete captured output](docs/verification/session7/04-axe-diagnostic.txt).

### 05-zap-pull (2026-10-24T16:28:36)

Working directory: `/home/dharshan/sih2`.

```bash
timeout 180 docker pull ghcr.io/zaproxy/zaproxy:stable
```

[Complete captured output](docs/verification/session7/05-zap-pull.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 06-badge-source (2026-10-24T16:29:59)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'rg -n -A 9 -B 2 "badge-dot" frontend/src/styles*.css frontend/src/styles/*.css; docker image inspect ghcr.io/zaproxy/zaproxy:stable --format "{{.Id}}" 2>/dev/null || true'
```

[Complete captured output](docs/verification/session7/06-badge-source.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 07-ui-server (2026-10-24T16:29:59)

Working directory: `/home/dharshan/sih2`.

```bash
env TL_UI_WORK=/home/dharshan/sih2/.ui-check/session7-ui TL_UI_API_PORT=8002 TL_UI_PORT=5175 .venv/bin/python tools/ui-checks/serve.py --reset
```

[Complete captured output](docs/verification/session7/07-ui-server.txt).

### 08-axe-light (2026-10-24T16:30:26)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5175 AXE_RESULT=/home/dharshan/sih2/docs/verification/session7/axe-light.json node tools/ui-checks/axe.mjs --theme light
```

[Complete captured output](docs/verification/session7/08-axe-light.txt).

### 09-gap-database-query (2026-10-24T16:30:27)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import sqlite3,json; from pathlib import Path;
for name in ["backend/trustledger.db",".ui-check/session6-ui/ui.db",".ui-check/session7-ui/ui.db"]:
 c=sqlite3.connect("file:"+name+"?mode=ro",uri=True); c.row_factory=sqlite3.Row; q="SELECT id,status,maturity_date,renewal_of,renewed_by FROM fdrs WHERE (maturity_date < date(\"now\") AND status IN (\"verified\",\"pending\",\"discrepancy\")) OR renewal_of IS NOT NULL"; rows=[dict(r) for r in c.execute(q)]; print(name); print(q); print(json.dumps(rows)); c.close()'
```

[Complete captured output](docs/verification/session7/09-gap-database-query.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **124**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 10-zap-pull-retry (2026-10-24T16:33:25)

Working directory: `/home/dharshan/sih2`.

```bash
timeout 180 docker pull ghcr.io/zaproxy/zaproxy:stable
```

[Complete captured output](docs/verification/session7/10-zap-pull-retry.txt).

### 11-s01-browser (2026-10-24T16:33:56)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5175 node tools/ui-checks/s01.mjs
```

[Complete captured output](docs/verification/session7/11-s01-browser.txt).

### 12-final-kernel (2026-10-24T16:33:57)

Working directory: `/home/dharshan/sih2`.

```bash
env TL_VERIFICATION_DIR=/home/dharshan/sih2/docs/verification/session7 .venv/bin/python tools/baseline/kernel_check.py
```

[Complete captured output](docs/verification/session7/12-final-kernel.txt).

### 13-final-migrations (2026-10-24T16:33:58)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/migration_check.py backend/trustledger.db
```

[Complete captured output](docs/verification/session7/13-final-migrations.txt).

### 14-production-build (2026-10-24T16:33:59)

Working directory: `/home/dharshan/sih2`.

```bash
npm --prefix frontend run build
```

[Complete captured output](docs/verification/session7/14-production-build.txt).

### 15-pillow-versions (2026-10-24T16:35:12)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python -c 'import sys,importlib.metadata as m; print(sys.version); print({n:m.version(n) for n in ["Pillow","reportlab","setuptools"]})'
```

[Complete captured output](docs/verification/session7/15-pillow-versions.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 16-pip-audit (2026-10-24T16:35:16)

Working directory: `/home/dharshan/sih2`.

```bash
.ui-check/tools-venv/bin/python -m pip_audit --path .venv/lib/python3.11/site-packages --cache-dir .ui-check/pip-audit-cache --progress-spinner off --format json --output docs/verification/session7/pip-audit.json
```

[Complete captured output](docs/verification/session7/16-pip-audit.txt).

### 18-reboot-state (2026-10-24T16:39:35)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import subprocess; subprocess.run(["uptime"]); subprocess.run(["docker","ps","-a","--format","{{.Names}} {{.Status}} {{.Image}}"]); print("Commands 07, 10–14 and 16 were interrupted by a host reboot; incomplete logs are not passing evidence. No container was stopped or deleted by this agent.")'
```

[Complete captured output](docs/verification/session7/18-reboot-state.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 19-start-authorized-services (2026-10-24T16:39:35)

Working directory: `/home/dharshan/sih2`.

```bash
docker start tl-gap-pg tl-gap-clamav tl-gap-mailpit
```

[Complete captured output](docs/verification/session7/19-start-authorized-services.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 20-final-kernel (2026-10-24T16:39:36)

Working directory: `/home/dharshan/sih2`.

```bash
env TL_VERIFICATION_DIR=/home/dharshan/sih2/docs/verification/session7 .venv/bin/python tools/baseline/kernel_check.py
```

[Complete captured output](docs/verification/session7/20-final-kernel.txt).

### 21-production-build (2026-10-24T16:39:37)

Working directory: `/home/dharshan/sih2`.

```bash
npm --prefix frontend run build
```

[Complete captured output](docs/verification/session7/21-production-build.txt).

### 22-final-migrations (2026-10-24T16:39:38)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/migration_check.py backend/trustledger.db
```

[Complete captured output](docs/verification/session7/22-final-migrations.txt).

### 23-pip-audit (2026-10-24T16:39:39)

Working directory: `/home/dharshan/sih2`.

```bash
.ui-check/tools-venv/bin/python -m pip_audit --path .venv/lib/python3.11/site-packages --cache-dir .ui-check/pip-audit-cache --progress-spinner off --format json --output docs/verification/session7/pip-audit.json
```

[Complete captured output](docs/verification/session7/23-pip-audit.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 24-restart-s3 (2026-10-24T16:39:55)

Working directory: `/home/dharshan/sih2`.

```bash
docker start tl-baseline-s3
```

[Complete captured output](docs/verification/session7/24-restart-s3.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 25-bundle-search (2026-10-24T16:39:55)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/bundle_check.py
```

[Complete captured output](docs/verification/session7/25-bundle-search.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 26-zap-retry-resume (2026-10-24T16:39:55)

Working directory: `/home/dharshan/sih2`.

```bash
timeout 180 docker pull ghcr.io/zaproxy/zaproxy:stable
```

[Complete captured output](docs/verification/session7/26-zap-retry-resume.txt).

### 27-final-postgres (2026-10-24T16:39:57)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py postgres
```

[Complete captured output](docs/verification/session7/27-final-postgres.txt).

### 28-final-sqlite (2026-10-24T16:39:58)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite
```

[Complete captured output](docs/verification/session7/28-final-sqlite.txt).

### 29-ui-server (2026-10-24T16:39:59)

Working directory: `/home/dharshan/sih2`.

```bash
env TL_UI_WORK=/home/dharshan/sih2/.ui-check/session7-final TL_UI_API_PORT=8002 TL_UI_PORT=5175 .venv/bin/python tools/ui-checks/serve.py --reset
```

[Complete captured output](docs/verification/session7/29-ui-server.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 30-bundle-search (2026-10-24T16:40:19)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/bundle_check.py
```

[Complete captured output](docs/verification/session7/30-bundle-search.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 31-s01-browser (2026-10-24T16:40:19)

Working directory: `/home/dharshan/sih2`.

```bash
env UI_BASE=http://localhost:5175 node tools/ui-checks/s01.mjs
```

[Complete captured output](docs/verification/session7/31-s01-browser.txt).

### 32-production-server (2026-10-24T16:40:20)

Working directory: `/home/dharshan/sih2`.

```bash
env TL_UI_WORK=/home/dharshan/sih2/.ui-check/session7-production TL_UI_API_PORT=8000 TL_UI_PORT=5173 .venv/bin/python tools/ui-checks/serve.py --reset --prod --preview
```

[Complete captured output](docs/verification/session7/32-production-server.txt).

### 33-npm-audit (2026-10-24T16:41:10)

Working directory: `/home/dharshan/sih2`.

```bash
npm --prefix frontend audit --json
```

[Complete captured output](docs/verification/session7/33-npm-audit.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 34-scenario-output (2026-10-24T16:42:00)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cd backend && ../.venv/bin/python scripts/run_required_scenarios.py && ../.venv/bin/python scripts/run_scenarios.py'
```

[Complete captured output](docs/verification/session7/34-scenario-output.txt).

### 35-gitleaks (2026-10-24T16:42:01)

Working directory: `/home/dharshan/sih2`.

```bash
docker run --rm -v /home/dharshan/sih2:/repo:ro zricethezav/gitleaks:v8.18.4 detect --no-git --source /repo --redact --no-banner
```

[Complete captured output](docs/verification/session7/35-gitleaks.txt).

### 36-verification-tool-diff (2026-10-24T16:42:12)

Working directory: `/home/dharshan/sih2`.

```bash
git diff -- tools/ui-checks/live_data.mjs backend/scripts/run_required_scenarios.py
```

[Complete captured output](docs/verification/session7/36-verification-tool-diff.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 37-frontend-security-context (2026-10-24T16:42:52)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import json; p=json.load(open("frontend/package.json")); print("react-router-dom declared:",p["dependencies"]["react-router-dom"]); print("npm audit has 2 moderate dependencies, 0 high, 0 critical. Automatic fix requires React Router 7 major migration. SPA uses BrowserRouter, no SSR hydration; retained moderate URL-navigation advisory for follow-up.")'
```

[Complete captured output](docs/verification/session7/37-frontend-security-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 38-scenario-report-current (2026-10-24T16:42:52)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cd backend && ../.venv/bin/python scripts/run_required_scenarios.py'
```

[Complete captured output](docs/verification/session7/38-scenario-report-current.txt).

Command exit: **124**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 39-source-secret-scan (2026-10-24T16:43:25)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/source_secret_check.py
```

[Complete captured output](docs/verification/session7/39-source-secret-scan.txt).

### 40-whole-secret-report (2026-10-24T16:43:26)

Working directory: `/home/dharshan/sih2`.

```bash
docker run --rm --user 1000:1000 -v /home/dharshan/sih2:/repo:ro -v /home/dharshan/sih2/docs/verification/session7:/out zricethezav/gitleaks:v8.18.4 detect --no-git --source /repo --redact --no-banner --report-format json --report-path /out/gitleaks-whole.json
```

[Complete captured output](docs/verification/session7/40-whole-secret-report.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 41-final-screenshots (2026-10-24T16:43:37)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/shots.mjs
```

[Complete captured output](docs/verification/session7/41-final-screenshots.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 48-zap-status (2026-10-24T16:44:21)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'from pathlib import Path; import subprocess; p=Path("docs/verification/session7"); print("Initial pull:", (p/"05-zap-pull.txt").read_text().splitlines()[-2:]); print("First retry interrupted by host reboot: 10-zap-pull-retry.txt"); print("Resumed retry:", (p/"26-zap-retry-resume.txt").read_text().splitlines()[-2:]); r=subprocess.run(["docker","image","inspect","ghcr.io/zaproxy/zaproxy:stable","--format","{{.Id}}"],capture_output=True,text=True); print("Image available:",r.returncode==0); print("ZAP scan NOT RUN: image download unavailable after two bounded attempts; no report exists. No risk score claimed."); assert r.returncode != 0'
```

[Complete captured output](docs/verification/session7/48-zap-status.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 49-gap-sql (2026-10-24T16:44:21)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import sqlite3,json; c=sqlite3.connect(".ui-check/session7-final/ui.db"); c.row_factory=sqlite3.Row; q="SELECT id,status,maturity_date,renewal_of,renewed_by FROM fdrs WHERE maturity_date < date(\"now\") AND status IN (\"verified\",\"pending\",\"discrepancy\") AND renewed_by IS NULL"; print("SQL:",q); rows=[dict(r) for r in c.execute(q)]; print(json.dumps(rows,indent=2)); print("Live expired unrenewed candidates:",len(rows)); c.close()'
```

[Complete captured output](docs/verification/session7/49-gap-sql.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 50-secret-summary (2026-10-24T16:44:38)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/secret_report_summary.py
```

[Complete captured output](docs/verification/session7/50-secret-summary.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 51-report-redaction (2026-10-24T16:45:16)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import json,re; from pathlib import Path; p=Path("docs/verification/session7/gitleaks-whole.json"); data=json.loads(p.read_text()); assert all(r.get("Secret")=="REDACTED" for r in data); print("All 430 gitleaks Secret values are REDACTED."); logs=[Path("docs/verification/session7/34-scenario-output.txt"),Path("docs/verification/session7/38-scenario-report-current.txt")]; n=0
for f in logs:
 s=f.read_text(); s,k=re.subn(r"OTP [0-9]{6}","OTP [REDACTED]",s); f.write_text(s); n+=k
print("Redacted",n,"ephemeral SIMULATED OTP values in captured scenario outputs; other command output preserved.")'
```

[Complete captured output](docs/verification/session7/51-report-redaction.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 52-prod-readiness (2026-10-24T16:45:22)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python -c 'import urllib.request,urllib.error; base="http://localhost:5173"; print("Login:",urllib.request.urlopen(base+"/login").status); print("Health:",urllib.request.urlopen(base+"/api/health").read().decode());
for p in ["/api/sim/totp/meera@aicte-india.org","/api/sim/otp-outbox/1-12345678"]:
 try: print(p,urllib.request.urlopen(base+p).status)
 except urllib.error.HTTPError as e: print(p,e.code); assert e.code==404'
```

[Complete captured output](docs/verification/session7/52-prod-readiness.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 53-archive-stale-gap-shot (2026-10-24T16:45:59)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'from pathlib import Path; import shutil; p=Path("docs/screenshots/final/08-fdr-detail-timeline.png"); dest=Path("docs/screenshots/historical/session4-timeline-no-current-gap-proof.png"); dest.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(p),str(dest)); print("Archived pre-session screenshot:",dest); print("Current timeline screenshot is explicitly named 08-fdr-detail-timeline-no-gap.png; no gap proof claimed.")'
```

[Complete captured output](docs/verification/session7/53-archive-stale-gap-shot.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 42-axe-light-final (2026-10-24T16:46:10)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/axe.mjs --theme light
```

[Complete captured output](docs/verification/session7/42-axe-light-final.txt).

### 54-panel-tool-source (2026-10-24T16:46:56)

Working directory: `/home/dharshan/sih2`.

```bash
cat tools/ui-checks/axe_panels.mjs
```

[Complete captured output](docs/verification/session7/54-panel-tool-source.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 55-fixture-source (2026-10-24T16:47:20)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'cat backend/tests/sequence_clock.py backend/tests/test_zz_probe.py; sed -n "1,165p" backend/tests/test_ledger_db.py'
```

[Complete captured output](docs/verification/session7/55-fixture-source.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 56-policy-doc-check (2026-10-24T16:47:20)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import json; from pathlib import Path; p=json.loads(Path("backend/policy.json").read_text()); print(json.dumps(p,indent=2)); s=Path("docs/notifications.md").read_text(); assert "72 hours" in s and "**120**" in s and "**5**" in s and "**7** days" in s and "**2**" in s; print("Notification defaults printed above; documentation values reviewed against policy.json.")'
```

[Complete captured output](docs/verification/session7/56-policy-doc-check.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 43-axe-dark-final (2026-10-24T16:48:03)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/axe.mjs --theme dark
```

[Complete captured output](docs/verification/session7/43-axe-dark-final.txt).

### 57-health-regression-before (2026-10-24T16:48:56)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite tests/test_nudge.py::test_centre_open_acknowledges_and_health_measures
```

[Complete captured output](docs/verification/session7/57-health-regression-before.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 58-health-regression-after (2026-10-24T16:49:42)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite tests/test_nudge.py::test_centre_open_acknowledges_and_health_measures
```

[Complete captured output](docs/verification/session7/58-health-regression-after.txt).

### 59-final-postgres-metrics (2026-10-24T16:49:44)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py postgres
```

[Complete captured output](docs/verification/session7/59-final-postgres-metrics.txt).

### 60-final-sqlite-metrics (2026-10-24T16:49:45)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite
```

[Complete captured output](docs/verification/session7/60-final-sqlite-metrics.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 44-axe-panels-light (2026-10-24T16:50:00)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/axe_panels.mjs --theme light
```

[Complete captured output](docs/verification/session7/44-axe-panels-light.txt).

### 61-audit-json-summary (2026-10-24T16:50:14)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import json; p=json.load(open("docs/verification/session7/pip-audit.json")); ds=p["dependencies"]; print("Distributions audited:",len(ds)); print("Advisories:",sum(len(d.get("vulns",[])) for d in ds)); print("Pillow:",[(d["name"],d["version"],d.get("vulns",[])) for d in ds if d["name"].lower()=="pillow"]); assert not any(d.get("vulns") for d in ds)'
```

[Complete captured output](docs/verification/session7/61-audit-json-summary.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 62-final-integrity (2026-10-24T16:50:14)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/final_inspection.py
```

[Complete captured output](docs/verification/session7/62-final-integrity.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 63-reload-ui-api (2026-10-24T16:51:27)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/ui-checks/reload_owned_api.py 8002 session7-final
```

[Complete captured output](docs/verification/session7/63-reload-ui-api.txt).

### 64-build-final (2026-10-24T16:51:28)

Working directory: `/home/dharshan/sih2`.

```bash
npm --prefix frontend run build
```

[Complete captured output](docs/verification/session7/64-build-final.txt).

### 65-reload-production-api (2026-10-24T16:51:29)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/ui-checks/reload_owned_api.py 8000 session7-production
```

[Complete captured output](docs/verification/session7/65-reload-production-api.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 66-axe-panels-light-final (2026-10-24T16:51:46)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/axe_panels.mjs --theme light
```

[Complete captured output](docs/verification/session7/66-axe-panels-light-final.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 73-final-bundle-search (2026-10-24T16:52:28)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/bundle_check.py
```

[Complete captured output](docs/verification/session7/73-final-bundle-search.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 74-final-health-code (2026-10-24T16:52:29)

Working directory: `/home/dharshan/sih2`.

```bash
bash -lc 'sed -n "120,140p" backend/app/nudge/insights.py; sed -n "360,380p" backend/tests/test_nudge.py; sed -n "122,130p" frontend/src/styles/nudge.css'
```

[Complete captured output](docs/verification/session7/74-final-health-code.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 67-axe-panels-dark-final (2026-10-24T16:52:35)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/axe_panels.mjs --theme dark
```

[Complete captured output](docs/verification/session7/67-axe-panels-dark-final.txt).

Command exit: **1**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 75-scenario-report-verify (2026-10-24T16:53:04)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import json; from pathlib import Path; p=json.loads(Path("docs/scenario-report.json").read_text()); s=Path("docs/scenario-report.md").read_text(); print("Generated:",p["generated_at"]); print("Required API scenarios:",len(p["scenarios"]),"passed:",p["passed"],"failed:",p["failed"]); assert len(p["scenarios"])==6 and p["passed"]==52 and p["failed"]==0; assert "6 scenarios, 52 checks passed, 0 failed" in s and "malware-scanner stub" in s; print("Markdown matches current generated JSON. R1–R6 are distinct from kernel-wrapper S01–S09 (9 / 115 in 34-scenario-output.txt).")'
```

[Complete captured output](docs/verification/session7/75-scenario-report-verify.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 77-mfa-check-context (2026-10-24T16:53:44)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import sqlite3; c=sqlite3.connect(".ui-check/session7-final/ui.db"); print("SELECT username, totp_secret_enc IS NOT NULL FROM users WHERE username=1-12345678"); print(c.execute("SELECT username, totp_secret_enc IS NOT NULL FROM users WHERE username=?",("1-12345678",)).fetchone()); print("Repeated browser checks reached the five OTP sends / 15 minutes limit (HTTP 429), correctly enforced. Subsequent checks use the existing institution Authenticator App MFA; no auth limit or database values changed.")'
```

[Complete captured output](docs/verification/session7/77-mfa-check-context.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 76-axe-panels-dark-complete (2026-10-24T16:53:45)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/axe_panels.mjs --theme dark
```

[Complete captured output](docs/verification/session7/76-axe-panels-dark-complete.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 68-axe-light-complete (2026-10-24T16:54:25)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/axe.mjs --theme light
```

[Complete captured output](docs/verification/session7/68-axe-light-complete.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 69-axe-dark-complete (2026-10-24T16:56:17)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/axe.mjs --theme dark
```

[Complete captured output](docs/verification/session7/69-axe-dark-complete.txt).

### 78-scenario-final (2026-10-24T16:57:53)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python backend/scripts/run_required_scenarios.py
```

[Complete captured output](docs/verification/session7/78-scenario-final.txt).

### 79-service-stability (2026-10-24T16:57:59)

Working directory: `/home/dharshan/sih2`.

```bash
docker ps --format '{{.Names}} {{.Status}}'
```

[Complete captured output](docs/verification/session7/79-service-stability.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 70-pdf-labels-final (2026-10-24T16:58:12)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/pdf_check.mjs
```

[Complete captured output](docs/verification/session7/70-pdf-labels-final.txt).

### 81-log-redaction (2026-10-24T16:58:46)

Working directory: `/home/dharshan/sih2`.

```bash
python3 -c 'import re; from pathlib import Path; n=0
for p in Path("docs/verification/session7").glob("*.txt"):
 s=p.read_text(errors="replace"); s,k=re.subn(r"OTP [0-9]{6}","OTP [REDACTED]",s)
 if k:p.write_text(s)
 n+=k
print("Redacted",n,"ephemeral SIMULATED OTP occurrences from evidence logs; no other output changed.")'
```

[Complete captured output](docs/verification/session7/81-log-redaction.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 71-nudge-sql-final (2026-10-24T16:59:02)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/live_data.mjs
```

[Complete captured output](docs/verification/session7/71-nudge-sql-final.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 72-refreshed-screenshots (2026-10-24T16:59:12)

Working directory: `/home/dharshan/sih2`.

```bash
node tools/ui-checks/retake_final.mjs
```

[Complete captured output](docs/verification/session7/72-refreshed-screenshots.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 82-finalize-documents (2026-10-24T16:59:50)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/session7_finalize.py
```

[Complete captured output](docs/verification/session7/82-finalize-documents.txt).


### Session 7 final results

The application checks below pass. **ZAP remains unverified** because the image download timed out; this is not a
production security sign-off. A real renewal-gap screenshot is unavailable because the live data has no gap.
Historical failures remain in this report and their original logs.

| Check | Measured result | Command/output evidence |
|---|---|---|
| Kernel, scratch copy | 67 passed; 13 scenarios / 161 checks; mutation 32/33 | [20-final-kernel](docs/verification/session7/20-final-kernel.txt), [mutants](docs/verification/session7/kernel-mutants.txt) |
| Kernel integrity | 48 files byte-identical to ZIP; SHA-256 `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0` | [62-final-integrity](docs/verification/session7/62-final-integrity.txt); every completed recorder command checks it again |
| Final backend SQLite | **147 passed, 0 failed, 0 skipped** | [60-final-sqlite-metrics](docs/verification/session7/60-final-sqlite-metrics.txt) |
| Final backend PostgreSQL 16.15 | **147 passed, 0 failed, 0 skipped** | [59-final-postgres-metrics](docs/verification/session7/59-final-postgres-metrics.txt) |
| Real integrations | ClamAV, SeaweedFS/S3, Mailpit, PostgreSQL required and passing within both full suites | same backend outputs (`--require-services`); no silent skips |
| Migration 0006 | Fresh SQLite, fresh PostgreSQL, dev DB copy: upgrade/downgrade/upgrade PASS; row counts preserved | [22-final-migrations](docs/verification/session7/22-final-migrations.txt) |
| Clean seed/reset | Disposable UI DB migrated and seeded successfully | [29-ui-server](docs/verification/session7/29-ui-server.txt) |
| Required API scenarios | R1–R6: **6 scenarios / 52 checks, 0 failed** | [78-final report generation](docs/verification/session7/78-scenario-final.txt), [report consistency](docs/verification/session7/75-scenario-report-verify.txt), [scenario report](docs/scenario-report.md) |
| Kernel-wrapper S01–S09 | **9 scenarios / 115 checks, 0 failed** (distinct from R1–R6) | [34-scenario-output](docs/verification/session7/34-scenario-output.txt) |
| Production build and search | PASS; 12 dev-only patterns, including literal `demo`, all absent | [64-build-final](docs/verification/session7/64-build-final.txt), [73-bundle-search](docs/verification/session7/73-final-bundle-search.txt) |
| Production simulator helpers | OTP/TOTP helper URLs return 404; health identifies bank layer SIMULATED | [52-prod-readiness](docs/verification/session7/52-prod-readiness.txt) |
| axe route coverage | **42 routes light + 42 dark; 0 violations; 0 console errors** after final CSS fix | [68-light](docs/verification/session7/68-axe-light-complete.txt), [69-dark](docs/verification/session7/69-axe-dark-complete.txt) |
| axe new panels/editors | **18 views per theme; 0 violations; 0 console errors** | [66-light](docs/verification/session7/66-axe-panels-light-final.txt), [76-dark](docs/verification/session7/76-axe-panels-dark-complete.txt) |
| S01, four separate users | **12/12; 0 console errors**. Debit: NOT yet complete; return: AICTE still owes you ₹35.00 lakh; positive credit only: Completed | [31-s01-browser](docs/verification/session7/31-s01-browser.txt), [screenshots](docs/screenshots/final/README.md) |
| Nudge UI vs direct SQL | **7/7**, including corrected email-sent count; 0 unexpected errors; intentional action-link reuse returns 409 | [71-nudge-sql-final](docs/verification/session7/71-nudge-sql-final.txt), [values/SQL](docs/verification/session7/live-data.json) |
| PDF label checks | **8/8**: seven bank-data exports labelled SIMULATED; audit-only control unlabelled | [70-pdf-labels](docs/verification/session7/70-pdf-labels-final.txt) |
| Screenshots | **18 at 1536×1024**, including 14 page/export shots and four S01 states | [41-capture](docs/verification/session7/41-final-screenshots.txt), [72-refresh](docs/verification/session7/72-refreshed-screenshots.txt), [manifest](docs/verification/session7/screenshots.json) |
| Pillow / Python audit | Python **3.11.17**, Pillow **13.0.0**; **56 distributions, 0 known advisories** | [15-versions](docs/verification/session7/15-pillow-versions.txt), [23-audit](docs/verification/session7/23-pip-audit.txt), [61-summary](docs/verification/session7/61-audit-json-summary.txt) |
| npm audit | **0 high, 0 critical; 2 moderate package findings remain** (React Router) | [33-audit](docs/verification/session7/33-npm-audit.txt), [37-context](docs/verification/session7/37-frontend-security-context.txt) |
| gitleaks whole directory | **430 findings, not clean**: ignored dependencies, test vectors and local development credentials/DSC keys | [40-whole scan](docs/verification/session7/40-whole-secret-report.txt), [50-breakdown](docs/verification/session7/50-secret-summary.txt); report secrets redacted ([51](docs/verification/session7/51-report-redaction.txt)) |
| gitleaks source set | No leaks in source files selected by git ignore rules | [final source scan](docs/verification/session7/80-source-secret-final.txt); initial 445-file scan [39](docs/verification/session7/39-source-secret-scan.txt) |
| ZAP | **NOT RUN / no report**: initial pull and resumed retry both timeout exit 124 | [05-initial](docs/verification/session7/05-zap-pull.txt), [26-retry](docs/verification/session7/26-zap-retry-resume.txt), [48-status](docs/verification/session7/48-zap-status.txt) |
| Real renewal-gap screenshot | **Unavailable**: API 0, timeline []; direct SQL 0 live expired unrenewed candidates. No gap created | [41-API](docs/verification/session7/41-final-screenshots.txt), [49-SQL](docs/verification/session7/49-gap-sql.txt), [72-timeline](docs/verification/session7/72-refreshed-screenshots.txt) |

The former **129** and **137** backend numbers are historical; the measured final baseline is **147 on each database**.
The timestamp fixture now advances by cumulative positive increments. The existing assertion-free `test_probe` was
renamed/augmented to reject equal/backward fixture times and verify the kernel rejects backward time, retaining the
147-test set. Equal timestamps remain legal in the unchanged kernel; strictness belongs to the fixture.
[Fixture source](docs/verification/session7/55-fixture-source.txt).

Screenshot review found a separate health bug: status `sent` incremented the same counter twice. The added assertions
within the existing health test fail before the fix (**2 vs 1**, [57](docs/verification/session7/57-health-regression-before.txt))
and pass afterward ([58](docs/verification/session7/58-health-regression-after.txt)); both full suites then pass 147.
The latest health screenshot replaces the incorrect intermediate capture.

Accessibility history: badge contrast failure [04](docs/verification/session7/04-axe-diagnostic.txt) fixed by a darker badge;
targeted timeline fading failures [44](docs/verification/session7/44-axe-panels-light.txt) fixed by retaining full text opacity
and using a dashed future marker. The dark panel attempt [67](docs/verification/session7/67-axe-panels-dark-final.txt) stopped
at the correctly enforced five-OTP-send limit; the remaining verification uses the existing Authenticator App MFA
([77](docs/verification/session7/77-mfa-check-context.txt)). No limit or account data was changed.

Host reboot interrupted commands 07, 10–14 and 16; incomplete files are not results. Their complete reruns are linked above.
Only project PostgreSQL/ClamAV/Mailpit were started; the existing `tl-baseline-s3` was restarted after explicit user approval.
No project service container was stopped/deleted/recreated, and `buildhub-pg` was untouched. Individual Docker commands were used;
compose was not used. The tool scan containers use `docker run --rm` as recorded. No git commit was made.

Remaining security acceptance: ZAP must be completed on a host with the image available. npm's moderate Router advisories
remain documented: the automatic fix requires a major-version migration; this SPA does not use SSR hydration, while the
navigation advisory still needs an upgrade review. The large production JS chunk and Starlette deprecation warnings are
also retained in command output. Automated checks do not replace an independent penetration test.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 80-source-secret-final (2026-10-24T16:59:50)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/source_secret_check.py
```

[Complete captured output](docs/verification/session7/80-source-secret-final.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 83-final-document-review (2026-10-24T17:01:58)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/session7_review.py
```

[Complete captured output](docs/verification/session7/83-final-document-review.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 84-final-kernel-and-services (2026-10-24T17:01:58)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python tools/baseline/final_inspection.py
```

[Complete captured output](docs/verification/session7/84-final-kernel-and-services.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 85-solution-document-validation (2026-10-24T17:11:16)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python -c 'from pathlib import Path; import re,hashlib; p=Path("solution.md"); s=p.read_text(); missing=[]; checked=0
for raw in re.findall(r"\]\(([^)]+)\)",s):
 target=raw.split("#")[0]
 if not target or "://" in target:continue
 checked+=1
 if not (p.parent/target).exists():missing.append(target)
assert not missing,missing
for i in range(1,11):assert len(re.findall(r"^\| R%02d \|"%i,s,re.M))==1,i
assert len(re.findall(r"^## [0-9]+\.",s,re.M))==14
for phrase in ["SIMULATED","147 passed","ZAP is unverified","No live renewal-gap screenshot","Two moderate npm","Whole-directory gitleaks"]:assert phrase in s,phrase
print("Created:",p.resolve());print("Requirement mapping: R01–R10, all ten present exactly once");print("Sections: 14 numbered sections plus problem metadata and source provenance");print("Local links checked:",checked,"; missing:",len(missing));print("Words:",len(s.split()));print("Document SHA-256:",hashlib.sha256(p.read_bytes()).hexdigest());print("Documentation-only addition; existing Session 7 test evidence referenced, no new runtime test run claimed. No commits or container operations.")'
```

[Complete captured output](docs/verification/session7/85-solution-document-validation.txt).

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

### 86-stop-project-services (2026-10-24T17:15:48)

Working directory: `/home/dharshan/sih2`.

```bash
.venv/bin/python -c 'import os,signal,subprocess,time; from pathlib import Path; root=Path.cwd(); pids=[4774,5121,5132,5133,6965,8215,8289,8290,36983,36990,37222,37223]
for pid in pids:
 p=Path("/proc")/str(pid)
 try:
  cwd=(p/"cwd").resolve(); assert cwd==root or root in cwd.parents,(pid,cwd); os.kill(pid,signal.SIGTERM); print("SIGTERM project process",pid,flush=True)
 except ProcessLookupError:pass
 except FileNotFoundError:pass
time.sleep(2)
for pid in pids:
 p=Path("/proc")/str(pid)
 if p.exists():
  try:
   if p.joinpath("stat").read_text().split()[2]!="Z":os.kill(pid,signal.SIGKILL);print("Stopped remaining owned process",pid,flush=True)
  except (ProcessLookupError,FileNotFoundError):pass
names=["tl-gap-pg","tl-gap-clamav","tl-gap-mailpit","tl-baseline-s3"]; subprocess.run(["docker","stop",*names],check=True); print("No containers deleted. buildhub-pg untouched.",flush=True); subprocess.run(["docker","ps","--format","{{.Names}} {{.Status}}"],check=True)'
```

[Complete captured output](docs/verification/session7/86-stop-project-services.txt).

Command exit: **-15**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **-15**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.

Command exit: **0**. Kernel manifest after this stage: `58406d492e427ab607d4818e8c4161c4dace45d58183b0fc9be5cdfa8fd387c0`; ZIP match: **True**.
