"""Start the backend (uvicorn :8000) and the frontend (vite :5173) for the browser checks, on a disposable SQLite database.

Usage: .venv/bin/python tools/ui-checks/serve.py [--reset] [--prod] [--no-vite]

  --reset    delete the UI-check database first and run `scripts/seed.py --reset` (migrate to head + seed)
  --prod     TL_ENV=prod: no /api/sim/*, no mock OIDC, no dev secrets file (keys come from this process's environment)
  --no-vite  backend only

Real local services: ClamAV (:3310) scans every upload; SeaweedFS (tl-baseline-s3, :8334) holds the encrypted documents.
Credentials for SeaweedFS are read from the container's environment into the child process only; nothing is written to disk.
The database and audit checkpoint live under sih2/.ui-check (gitignored), never in the developer's database.
Demo password for every seeded user: TL_DEMO_PASSWORD (default UiCheck-Demo-2026, the value tools/ui-checks/lib.mjs uses).
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(os.environ.get("TL_UI_WORK", ROOT / ".ui-check"))
PY = str(ROOT / ".venv/bin/python")


def container_env(name: str) -> dict[str, str]:
    obj = json.loads(subprocess.check_output(["docker", "inspect", name]))[0]
    return dict(item.split("=", 1) for item in obj["Config"]["Env"] if "=" in item)


def main() -> None:
    reset, prod, no_vite = "--reset" in sys.argv, "--prod" in sys.argv, "--no-vite" in sys.argv
    api_port = os.environ.get("TL_UI_API_PORT", "8000")
    ui_port = os.environ.get("TL_UI_PORT", "5173")
    WORK.mkdir(parents=True, exist_ok=True)
    s3 = container_env("tl-baseline-s3")
    env = {**os.environ,
           "TL_DATABASE_URL": f"sqlite:///{WORK / 'ui.db'}",
           "TL_CHECKPOINT_PATH": str(WORK / "checkpoints.jsonl"),
           "TL_DEMO_PASSWORD": os.environ.get("TL_DEMO_PASSWORD", "UiCheck-Demo-2026"),
           "TL_SCANNER": "clamd", "TL_CLAMD_HOST": "127.0.0.1", "TL_CLAMD_PORT": "3310",
           "TL_OBJECT_STORE": "s3", "TL_S3_ENDPOINT": "127.0.0.1:8334", "TL_S3_BUCKET": "tl-integration-tests",   # SeaweedFS here is capped at 8 volumes; reuse the bucket the tests use
           "TL_S3_ACCESS_KEY": s3["S3_ACCESS_KEY"], "TL_S3_SECRET_KEY": s3["S3_SECRET_KEY"],
           "TL_COOKIE_SECURE": "false",
           "TL_PUBLIC_URL": f"http://localhost:{ui_port}", "TL_API_URL": f"http://localhost:{ui_port}/api",
           "TL_API_PROXY": f"http://127.0.0.1:{api_port}"}
    # All application keys stay in the process environment. Do not write a keys JSON file.
    # A reset uses a disposable test DB; reuse requires the caller to supply the same keys.
    key_names = ("TL_SECRET_KEY", "TL_SIM_BANK_SEED", "TL_MASTER_KEY", "TL_DATA_KEY", "TL_PROVIDER_WEBHOOK_SECRET", "TL_OIDC_CLIENT_SECRET")
    if (WORK / "ui.db").exists() and not reset and any(not env.get(k) for k in key_names):
        raise SystemExit("Existing UI-check DB: supply the original keys through environment variables, or use --reset for a disposable test DB")
    for key in key_names:
        if not env.get(key):
            env[key] = (base64.b64encode(secrets.token_bytes(32)).decode() if key == "TL_MASTER_KEY" else
                        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode() if key == "TL_DATA_KEY" else secrets.token_urlsafe(48))
    env["TL_ENV"] = "prod" if prod else "dev"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TL_DEVCERTS_DIR"] = str(WORK / "devcerts")
    if reset:
        (WORK / "ui.db").unlink(missing_ok=True)
        (WORK / "checkpoints.jsonl").unlink(missing_ok=True)
        # Seed the simulated DSC issuer for browser tests even when the subsequent server is production-mode.
        subprocess.run([PY, "scripts/seed.py", "--reset"], cwd=ROOT / "backend", env={**env, "TL_ENV": "dev"}, check=True)
    reload_args = ["--reload", "--reload-dir", str(ROOT / "backend/app")] if "--reload" in sys.argv else []
    procs = [subprocess.Popen([PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", api_port, *reload_args], cwd=ROOT / "backend", env=env)]
    if not no_vite:
        procs.append(subprocess.Popen(["npx", "vite", *(["preview"] if "--preview" in sys.argv else []), "--host", "127.0.0.1", "--port", ui_port, "--strictPort"], cwd=ROOT / "frontend", env=env))

    def stop(*_):
        for p in procs:
            p.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    for p in procs:
        p.wait()


if __name__ == "__main__":
    main()
