from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import get_settings
from .ledger import LEDGER
from .routers import auth, data, exports, ledger_api, nudge, oidc_mock, push as push_api, records, sim

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def create_app(start_scheduler: bool = True) -> FastAPI:
    cfg = get_settings()
    app = FastAPI(title="NIDHIVEDA API", version="0.1.0", docs_url="/api/docs" if cfg.is_dev else None,
                  openapi_url="/api/openapi.json" if cfg.is_dev else None)
    for r in (auth.router, data.router, ledger_api.router, nudge.router, push_api.router, records.router, exports.router):
        app.include_router(r, prefix="/api")
    if cfg.is_dev:
        app.include_router(sim.router, prefix="/api")
        app.include_router(oidc_mock.router, prefix="/api")

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Cache-Control", "no-store")
        # the API serves JSON and files only: nothing it returns may run script or be framed
        resp.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
                                if not request.url.path.startswith("/api/docs") else "frame-ancestors 'none'")
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return resp

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logging.getLogger("trustledger").exception("unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "internal error"}, status_code=500)

    @app.get("/api/health")
    def health():
        return {"ok": True, "env": cfg.env, "kernel_events": len(LEDGER.kernel().store), "bank_layer": "SIMULATED"}

    if start_scheduler:
        @app.on_event("startup")
        def _start():
            from .scheduler import start
            LEDGER.kernel()
            start()

        @app.on_event("shutdown")
        def _stop():
            from .scheduler import stop
            stop()
    return app


app = create_app()
