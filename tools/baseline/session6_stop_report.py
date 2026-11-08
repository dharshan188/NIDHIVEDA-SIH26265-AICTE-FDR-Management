"""Document the observed Session 6 stop; do not turn intermediate passes into final acceptance."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = ROOT / "TEST_REPORT.md"
text = p.read_text()
marker = "## Session 6 — 2026-10-24\n"
assert marker in text
summary = """
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

"""
assert "### Final status: STOPPED — final PostgreSQL count did not reproduce" not in text
text = text.replace(marker, marker + summary, 1)
text = "> **Latest: Session 6 is stopped at the final PostgreSQL baseline failure (146 passed, 1 failed). Pillow is resolved.** See the [Session 6 report](#session-6--2026-10-24); older session claims below are historical.\n\n" + text
p.write_text(text)
print("Recorded Session 6 stop, completed evidence, simulations, production gaps, failed attempts and Pillow resolution.")
