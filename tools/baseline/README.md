# Baseline checks

Run from `/home/dharshan/sih2`:

```bash
.venv/bin/python tools/baseline/backend_check.py sqlite
.venv/bin/python tools/baseline/backend_check.py postgres
.venv/bin/python tools/baseline/check_service_gates.py
.venv/bin/python tools/baseline/backend_check.py missing
.venv/bin/python tools/baseline/kernel_check.py
```

The backend runner requires PostgreSQL 16 in `tl-gap-pg` on loopback port 55433,
ClamAV on 3310, Mailpit SMTP on 1025 and HTTP on 8025, and SeaweedFS in
`tl-baseline-s3` on 8334. Credentials are read from the named containers into
environment variables, redacted from output and never saved to a host credentials
file. Each run creates and removes its own disposable database. PostgreSQL
application fixtures use isolated clones of a seeded template; the four dedicated
PostgreSQL tests additionally exercise Alembic and concurrency. The SQLite run
uses SQLite application fixtures and PostgreSQL for those four dedicated tests.

Start existing services with `docker start tl-gap-pg tl-gap-clamav tl-gap-mailpit`.
The old `tl-gap-s3` container cannot restart because its configuration mount is
missing; leave it intact. `start_s3.py` uses an individual `docker run` to create
a separate SeaweedFS container with generated credentials in its environment:

```bash
.venv/bin/python tools/baseline/start_s3.py
```

`backend_check.py missing` configures a closed local ClamAV endpoint and accepts
only pytest exit 1. It is a negative check, not a passing service test.
`check_service_gates.py` verifies all four services' optional/required/configured
and auto-detected behavior without changing any service.

Direct pytest accepts `TL_TEST_CLAMD=host:port`,
`TL_TEST_S3=endpoint,access,secret`, `TL_TEST_SMTP=host:smtp_port:http_port`, and
`TL_TEST_PG_URL` (a **disposable** PostgreSQL database URL). Add `--require-services`
or `TL_REQUIRE_SERVICES=1` for the baseline. Configured but unavailable services
fail even without that option. Local ClamAV and Mailpit are auto-detected at
default ports. A reachable S3/PostgreSQL service without credentials fails
clearly. Optional absent services produce explicit `ENVIRONMENT` skips.
Set `TL_TEST_BACKEND=postgres` for PostgreSQL application fixtures too; the dump
test needs `TL_TEST_PG_CONTAINER` for `docker exec pg_dump`.

The kernel check reads the original files and ZIP and runs the unmodified
mutation harness on a scratch copy only. Its canonical hash is SHA-256 over
compact sorted JSON mapping relative filenames to their SHA-256. All non-cache
files are included. It accepts the expected 32/33 score while retaining the
harness's actual exit code and output.

No commands here commit changes or stop/delete containers. Mailpit is a
**SIMULATED** delivery destination; bank, OTP and DSC tests use **SIMULATED**
providers. ClamAV, SeaweedFS and PostgreSQL are real local services.
