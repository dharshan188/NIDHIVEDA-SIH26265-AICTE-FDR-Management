"""Publish the final report only after every claimed command has completed successfully."""
from pathlib import Path
import json,re,struct,hashlib
R=Path(__file__).resolve().parents[1]; V=R/'docs/verification/session7'
def evidence(label,required):
    s=(V/f'{label}.txt').read_text()
    assert 'Command exit code: 0' in s,(label,'incomplete or failed')
    for text in required:assert text in s,(label,text)
evidence('20-final-kernel',['67 passed','scenarios=13 checks_passed=161 checks_failed=0','32/33 mutants killed','ZIP match: True'])
for label in ['59-final-postgres-metrics','60-final-sqlite-metrics']: evidence(label,['147 passed'])
for label in ['68-axe-light-complete','69-axe-dark-complete']:evidence(label,['42 pages, 0 with violations, 0 violations','console errors: 0'])
for label in ['66-axe-panels-light-final','76-axe-panels-dark-complete']:evidence(label,['18 views; 0 violations; console errors: 0'])
evidence('70-pdf-labels-final',['8/8 as expected','console errors: 0'])
evidence('71-nudge-sql-final',['7/7 passed','unexpected console errors: 0'])
evidence('72-refreshed-screenshots',['console errors: 0','Actual renewal gaps: []'])
evidence('22-final-migrations',['SUMMARY: all PASS [True, True, True]'])
evidence('31-s01-browser',['12/12 checks passed; console errors: 0'])
evidence('64-build-final',['built in'])
evidence('73-final-bundle-search',['matched assets (with repeats): 0'])
evidence('23-pip-audit',['No known vulnerabilities found'])
evidence('78-scenario-final',['scenarios=6 checks_passed=52 checks_failed=0'])
shots=R/'docs/screenshots/final'; manifest=[]
for p in sorted(shots.glob('*.png')):
    b=p.read_bytes(); dims=struct.unpack('>II',b[16:24]); assert dims==(1536,1024),(p,dims)
    manifest.append({'file':p.name,'width':dims[0],'height':dims[1],'sha256':hashlib.sha256(b).hexdigest()})
assert len(manifest)==18,len(manifest)
(V/'screenshots.json').write_text(json.dumps(manifest,indent=2)+'\n')
(shots/'README.md').write_text('''# Final screenshots — Session 7

All 18 PNGs are 1536×1024. Creation: [14 page screenshots](../../verification/session7/41-final-screenshots.txt),
[four-user S01](../../verification/session7/31-s01-browser.txt), and
[refreshed FDR/health screenshots after fixes](../../verification/session7/72-refreshed-screenshots.txt).
[Dimensions and SHA-256 manifest](../../verification/session7/screenshots.json).

**No real renewal gap exists in the live data:** API total 0, timeline gaps [], and SQL found no live expired unrenewed
candidates. See [API output](../../verification/session7/41-final-screenshots.txt) and
[SQL query](../../verification/session7/49-gap-sql.txt). `08-fdr-detail-timeline-no-gap.png` is a timeline screenshot,
not evidence of a gap. No gap was created. The pre-session screenshot is archived in `../historical/`.

The PDF export screenshot was rendered with Poppler and visually reviewed: the SIMULATED bank-data label is visible.
The login screenshot uses the production build; authenticated verification uses the isolated local test database.
'''+ '\n'.join(f'- [{i["file"]}]({i["file"]})' for i in manifest)+'\n')
summary='''

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
No container was stopped/deleted/recreated, and `buildhub-pg` was untouched. Individual Docker commands were used;
compose was not used. The tool scan containers use `docker run --rm` as recorded. No git commit was made.

Remaining security acceptance: ZAP must be completed on a host with the image available. npm's moderate Router advisories
remain documented: the automatic fix requires a major-version migration; this SPA does not use SSR hydration, while the
navigation advisory still needs an upgrade review. The large production JS chunk and Starlette deprecation warnings are
also retained in command output. Automated checks do not replace an independent penetration test.
'''
p=R/'TEST_REPORT.md';s=p.read_text();s=s.replace(s.splitlines()[0],'> **Latest: Session 7 final application baseline passes (147 tests on both databases); ZAP remains unverified.** See [Session 7](#session-7--2026-10-24) and its final results. Earlier failures below are historical.',1);p.write_text(s+summary)
(R/'CHANGELOG.md').write_text('''# FDR Trust Ledger — Session 7 final verification

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
''')
p=R/'docs/security.md';s=p.read_text().replace('## Session 6: Pillow decision — option 1 implemented','## Pillow decision — option 1 implemented; reconfirmed in Session 7')
s=s.replace('`docs/verification/session6/16-python311-versions.txt`, `17-pip-audit.txt`,\n`pip-audit.json` and `21-audit-summary.txt`.', '[Session 7 versions](verification/session7/15-pillow-versions.txt),\n[audit output](verification/session7/23-pip-audit.txt), [audit JSON](verification/session7/pip-audit.json)\nand [56-distribution summary](verification/session7/61-audit-json-summary.txt).')
s=s.replace('ZAP has not produced a report in Session 6.', 'ZAP has not produced a report in Session 7 (image download timeouts).')
i=s.index('## 7. Session 4 scan results (summary)');s=s[:i]+'''## 7. Final Session 7 scan results and limitations

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
''';p.write_text(s)
p=R/'docs/notifications.md';s=p.read_text().replace('Every provider is\n  shown with its SIMULATED badge.', 'Every simulated external provider is\n  shown with its SIMULATED badge; the real in-app centre is not labelled as simulated.')
s+='''

## 9. Session 7 verification

Defaults above were reviewed against the printed [current policy.json](verification/session7/56-policy-doc-check.txt).
The centre, escalation family, health totals and email-sent counter, embedded preferences and successful/reused action
links match **7 direct SQL comparisons** ([commands, UI and SQL values](verification/session7/71-nudge-sql-final.txt),
[structured results](verification/session7/live-data.json)). Reusing a consumed action link intentionally returns HTTP 409.
The health counter no longer counts a `sent` delivery twice; the existing regression test checks each channel against
its actual delivery rows ([before](verification/session7/57-health-regression-before.txt), [after](verification/session7/58-health-regression-after.txt)).
Sent continues to mean provider acceptance, not proof of bank credit or external message delivery.
''';p.write_text(s)
(R/'docs/FINAL_REPORT.md').write_text('''# Session 7 final report

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
''')
print('Final documents written only after all required passing evidence was found. Screenshots:',len(manifest))
