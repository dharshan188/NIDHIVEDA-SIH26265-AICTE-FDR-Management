"""Persistent scheduler (APScheduler, job store in the application database).

  daily_reminders  08:00 IST (policy reminders.run_at)   maturity sweep, then a delivery pass
  daily_digest     08:00 IST (policy digest.send_at)     one digest per user for informational items
  nudge_worker     every 30 s                            plan and send due deliveries
  escalation       every 15 min                          acknowledgement loop and escalation chain
  kernel_tick      every 60 s                            the kernel's own timed controls (credit confirmations, 30-day holds)

A restart never re-sends: the job store keeps next-run times, misfired runs are coalesced into one, and the daily jobs
are additionally guarded by scheduler_runs (one row per job per IST day) and by unique notification keys.
"""
from __future__ import annotations

import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .db import SessionLocal, engine
from .nudge.clock import IST, hhmm, ist_date, now_ist

log = logging.getLogger("trustledger.scheduler")
_sched: BackgroundScheduler | None = None


def job_daily_reminders() -> dict:
    from .nudge import reminders, worker
    with SessionLocal() as db:
        out = reminders.sweep(db)
        out["delivery"] = worker.run_once(db)
        return out


def job_daily_digest() -> int:
    from .nudge import worker
    from .nudge.reminders import claim_run
    with SessionLocal() as db:
        now = now_ist()
        if not claim_run(db, "daily_digest", ist_date(now).isoformat(), now):
            return 0
        n = worker.digest(db, now)
        worker.run_once(db, now)
        return n


def job_worker() -> dict:
    from .nudge import worker
    with SessionLocal() as db:
        return worker.run_once(db)


def job_escalation() -> dict:
    from .nudge import escalation
    with SessionLocal() as db:
        return escalation.sweep(db)


def job_kernel_tick() -> None:
    from .domain.common import now_iso
    from .ledger import LEDGER
    with SessionLocal() as db:
        LEDGER.run(db, lambda k: k.tick(now_iso()))


def build(start_paused: bool = False) -> BackgroundScheduler:
    from .nudge import policy as pol
    with SessionLocal() as db:
        p = pol.active(db)
    s = BackgroundScheduler(timezone=IST, jobstores={"default": SQLAlchemyJobStore(engine=engine(), tablename="apscheduler_jobs")},
                            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 6 * 3600})
    r, d = hhmm(p["reminders"]["run_at"]), hhmm(p["digest"]["send_at"])
    s.add_job(job_daily_reminders, CronTrigger(hour=r.hour, minute=r.minute, timezone=IST), id="daily_reminders", replace_existing=True)
    s.add_job(job_daily_digest, CronTrigger(hour=d.hour, minute=d.minute, timezone=IST), id="daily_digest", replace_existing=True)
    s.add_job(job_worker, "interval", seconds=30, id="nudge_worker", replace_existing=True)
    s.add_job(job_escalation, "interval", minutes=15, id="escalation", replace_existing=True)
    s.add_job(job_kernel_tick, "interval", seconds=60, id="kernel_tick", replace_existing=True)
    s.start(paused=start_paused)
    return s


def start() -> BackgroundScheduler:
    global _sched
    if _sched is None:
        _sched = build()
        now = now_ist()
        if now.time() >= hhmm("08:00"):   # catch up a missed 08:00 run today (no-op if it already ran)
            _sched.add_job(job_daily_reminders, id="catch_up_reminders", replace_existing=True)
        log.info("scheduler started: %s", [j.id for j in _sched.get_jobs()])
    return _sched


def stop() -> None:
    global _sched
    if _sched is not None:
        _sched.shutdown(wait=False)
        _sched = None
