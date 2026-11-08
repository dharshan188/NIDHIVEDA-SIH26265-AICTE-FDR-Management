"""Publish measured baseline evidence only after both complete backend runs pass."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/verification/baseline-resume"
for name in ("sqlite-verified.txt", "postgres-verified.txt"):
    contents = (OUT / name).read_text()
    assert "137 passed" in contents and " failed" not in contents and " skipped" not in contents, name
assert "32/33 mutants killed" in (OUT / "kernel-check.txt").read_text()
assert "unchanged: True; ZIP match: True" in (OUT / "kernel-check.txt").read_text()
assert "21 service-gating checks passed" in (OUT / "service-gates.txt").read_text()
archive = OUT / "previous-TEST_REPORT.md"
if not archive.exists():
    shutil.copyfile(ROOT / "TEST_REPORT.md", archive)

text = """# FDR Trust Ledger — measured baseline, 2026-10-24

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

"""

commands = [
    ("Initial seven live-service tests", ".venv/bin/python tools/baseline/backend_check.py sqlite tests/test_postgres.py tests/test_integration_services.py", "services-first.txt"),
    ("First PostgreSQL full attempt (lost full log, summary only)", ".venv/bin/python tools/baseline/backend_check.py postgres", "postgres-full-first.txt"),
    ("Second PostgreSQL full attempt", ".venv/bin/python tools/baseline/backend_check.py postgres", "postgres-full-second.txt"),
    ("Second SQLite full attempt", ".venv/bin/python tools/baseline/backend_check.py sqlite", "sqlite-full-second.txt"),
    ("ENOSPC PostgreSQL attempt (partial log)", ".venv/bin/python tools/baseline/backend_check.py postgres", "postgres-final.txt"),
    ("ENOSPC SQLite attempt (partial log)", ".venv/bin/python tools/baseline/backend_check.py sqlite", "sqlite-final.txt"),
    ("SQLite retry before S3 replacement", ".venv/bin/python tools/baseline/backend_check.py sqlite", "sqlite-final-retry.txt"),
    ("Bounded services", ".venv/bin/python tools/baseline/backend_check.py sqlite tests/test_integration_services.py", "services-bounded.txt"),
    ("Final SQLite", ".venv/bin/python tools/baseline/backend_check.py sqlite", "sqlite-verified.txt"),
    ("Final PostgreSQL", ".venv/bin/python tools/baseline/backend_check.py postgres", "postgres-verified.txt"),
    ("Service gates", ".venv/bin/python tools/baseline/check_service_gates.py", "service-gates.txt"),
    ("Missing required service (pytest failure expected)", ".venv/bin/python tools/baseline/backend_check.py missing", "required-missing.txt"),
    ("Kernel control, mutation and ZIP integrity", ".venv/bin/python tools/baseline/kernel_check.py", "kernel-check.txt"),
    ("Final integrity and environment inspection", ".venv/bin/python tools/baseline/final_inspection.py", "final-inspection.txt"),
]
for label, command, log in commands:
    text += f"### {label}\n\n```bash\nset -o pipefail; {command} 2>&1 | tee docs/verification/baseline-resume/{log}\n```\n\n[Captured output](docs/verification/baseline-resume/{log}).\n\n"

text += """Additional inspections/validation:

```bash
git rev-parse --show-toplevel
git -C /home/dharshan status --short -- sih2
git -C /home/dharshan diff --check -- sih2
rg -n 'pytest\\.skip|skipif|pytestmark' backend/tests > docs/verification/baseline-resume/skip-gates-source.txt
.venv/bin/python -m py_compile tools/baseline/*.py backend/tests/conftest.py backend/tests/service_config.py backend/tests/test_integration_services.py backend/tests/test_postgres.py backend/tests/test_ledger_db.py backend/tests/test_documents_security.py
```

Git status reports `?? sih2/`: the project is untracked within the home-rooted repository. Therefore `git diff --check` alone does not validate these new files; Python compilation and the executed suites provide validation. No commit was attempted. Earlier baseline outputs are retained under `docs/verification/final-baseline/`; the previous report is [archived](docs/verification/baseline-resume/previous-TEST_REPORT.md) and is not current evidence.

## Scope boundary

Stopped after the requested baseline-resume steps. Feature work A–H remains paused pending user confirmation. Frontend axe, browser S01, backend mutation, scenario-report regeneration, security scans and the other remaining original acceptance checks were not rerun in this scoped resume. This report does **not** claim the entire original acceptance list is complete.
"""
(ROOT / "TEST_REPORT.md").write_text(text)
print("TEST_REPORT.md updated from complete passing logs; previous report archived.")
