"""Daily maturity sweep (08:00 IST). For every live, unrenewed FDR:

- before maturity: the tightest window in reminders.before_maturity_days that the FDR has reached (one notice per window);
- after maturity with no renewal: reminders.after_missed_renewal_days (overdue, copied to the escalation role);
- renewal gaps (timeline.gaps): a notice to AICTE.

Idempotent twice over: scheduler_runs allows one run per IST day, and every notice has a unique key
(rem:<fdr>:<window>), so even a forced re-run cannot send a window twice.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models as m
from .. import portal_audit
from ..bank.simulator import BANKS
from ..domain.common import fmt_inr
from ..ledger import LEDGER
from ..timeline import gaps
from . import policy as pol
from .clock import iso, ist_date, now_ist
from .escalation import copy_up
from .ladder import days_between, rung_for
from .outbox import notify

JOB = "daily_reminders"


def window_for(days: int, policy: dict) -> str | None:
    if days >= 0:
        hit = [w for w in sorted(policy["reminders"]["before_maturity_days"]) if days <= w]
        return f"T-{hit[0]}" if hit else None
    late = [a for a in sorted(policy["reminders"]["after_missed_renewal_days"]) if -days >= a]
    return f"M+{late[-1]}" if late else None


def claim_run(db: Session, job: str, day: str, now: datetime) -> bool:
    try:
        with db.begin_nested():
            db.add(m.SchedulerRun(job=job, run_date=day, started_at=iso(now)))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def sweep(db: Session, now: datetime | None = None, force: bool = False, only: list[str] | None = None) -> dict:
    """`only` limits the sweep to some FDRs (simulator runs at a far-off date); the daily job sweeps everything."""
    now = now or now_ist()
    day = ist_date(now)
    if not claim_run(db, JOB, day.isoformat(), now) and not force:
        return {"ran": False, "reason": f"already ran for {day} (IST)"}
    p = pol.active(db)
    k = LEDGER.kernel()
    created = {"reminders": 0, "overdue": 0, "gaps": 0, "escalation_copies": 0}
    q = select(m.Fdr, m.Institution).join(m.Institution).where(m.Fdr.status.in_(("verified", "pending", "discrepancy")),
                                                                m.Fdr.renewed_by.is_(None))
    if only:
        q = q.where(m.Fdr.id.in_(only))
    for f, inst in db.execute(q.order_by(m.Fdr.id)):
        d = days_between(day, f.maturity_date)
        ins = k.instruments.get(f.instrument_id) or {}
        if ins.get("status") in ("RENEWED", "RENUMBERED"):
            continue   # the bank renewed it; the renewal is tracked on the new number
        w = window_for(d, p)
        params = {"fdr_id": f.id, "bank": BANKS.get(f.bank, f.bank), "amount": fmt_inr(f.amount_paise), "maturity": f.maturity_date.strftime("%d %b %Y"),
                  "days": abs(d)}
        if w:
            key = f"rem:{f.id}:{w}"
            before = db.scalars(select(m.Notification.id).where(m.Notification.key == key)).first()
            n = notify(db, f"institution:{f.institution_id}", "reminder_before" if d >= 0 else "reminder_missed_renewal", params, ref=f.id,
                       rung=rung_for(d, d < 0, p), key=key, window=w, at=iso(now), kind="maturity_reminder")
            if before is None:
                created["overdue" if d < 0 else "reminders"] += 1
                db.flush()
                if n.rung == "overdue":
                    created["escalation_copies"] += copy_up(db, n, now, reason="overdue on creation")
        for g in gaps(db, k, f, day):
            key = f"gap:{f.id}:{g['kind']}"
            if db.scalars(select(m.Notification.id).where(m.Notification.key == key)).first() is None:
                notify(db, "aicte", "renewal_gap", {**params, "days": g["days"]}, ref=f.id, rung="action", key=key, at=iso(now),
                       institution_id=f.institution_id, kind="renewal_gap")
                created["gaps"] += 1
    run = db.get(m.SchedulerRun, (JOB, day.isoformat()))
    if run:
        run.finished_at, run.result = iso(now), created
    portal_audit.record(db, "reminder_sweep", "system:scheduler", {"run_date": day.isoformat(), **created})
    db.commit()
    return {"ran": True, "run_date": day.isoformat(), **created}
