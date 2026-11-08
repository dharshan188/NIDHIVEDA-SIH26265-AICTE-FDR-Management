"""Two read models, both computed from stored rows (nothing estimated):

what_changed(): the audit trail (portal + kernel chains) since the user's previous sign-in, filtered to what the user is
                allowed to see, grouped into plain sentences, plus the open items that need this user now.
health():       notification counts by channel and status, acknowledgement rate, escalations and time-to-action, overall,
                by rung and per institution.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from .clock import iso, now_ist, parse
from .recipients import audiences

# portal / kernel event type -> (sentence for one, sentence for many, link suffix by role prefix)
PHRASES = {
    "fdr_submitted": ("{n} new FDR submitted", "{n} new FDRs submitted", "fdrs"),
    "fdr_verified": ("{n} FDR verified", "{n} FDRs verified", "fdrs"),
    "fdr_discrepancy_flagged": ("{n} discrepancy flagged", "{n} discrepancies flagged", "verification"),
    "document_added": ("{n} document added", "{n} documents added", "fdrs"),
    "document_rejected_malware": ("{n} upload blocked by the malware scan", "{n} uploads blocked by the malware scan", "audit-trail"),
    "document_downloaded": ("{n} document opened", "{n} documents opened", "audit-trail"),
    "observation_raised": ("{n} scrutiny observation raised", "{n} scrutiny observations raised", "fdrs"),
    "observation_replied": ("{n} reply to an observation", "{n} replies to observations", "fdrs"),
    "observation_closed": ("{n} observation closed", "{n} observations closed", "fdrs"),
    "field_changed": ("{n} record field updated", "{n} record fields updated", "audit-trail"),
    "notification_escalated": ("{n} notice escalated", "{n} notices escalated", "notifications"),
    "reminder_sweep": ("maturity reminders ran {n} time", "maturity reminders ran {n} times", "notifications"),
    "release_requested": ("{n} release request raised", "{n} release requests raised", "releases"),
    "payee_registered": ("{n} payee account registered", "{n} payee accounts registered", "payments"),
    "notify_policy_changed": ("notification policy changed", "notification policy changed {n} times", "notifications"),
    "policy_changed": ("release policy changed", "release policy changed {n} times", "rules"),
    "evidence_recorded": ("{n} bank message accepted (SIMULATED bank)", "{n} bank messages accepted (SIMULATED bank)", "reconciliation"),
    "evidence_rejected": ("{n} bank message rejected", "{n} bank messages rejected", "reconciliation"),
    "noc_issued": ("{n} NOC issued", "{n} NOCs issued", "releases"),
    "payment_initiated": ("{n} payment initiated", "{n} payments initiated", "payments"),
    "hold_placed": ("{n} hold placed", "{n} holds placed", "reconciliation"),
    "hold_released": ("{n} hold released", "{n} holds released", "reconciliation"),
    "renewal_decided": ("{n} renewal rule decision", "{n} renewal rule decisions", "renewals"),
}
BASE = {"INSTITUTION": "/institution", "AICTE_OFFICIAL": "/aicte", "AUDITOR": "/auditor"}
# pages that exist only for some roles: where the others go instead
FALLBACK = {("/auditor", "rules"): "audit-trail", ("/auditor", "verification"): "discrepancies", ("/auditor", "reconciliation"): "audit-trail",
            ("/institution", "rules"): "guidelines", ("/institution", "verification"): "fdrs", ("/institution", "reconciliation"): "payments",
            ("/institution", "audit-trail"): "notifications", ("/institution", "releases"): "release"}


def _page(base: str, page: str) -> str:
    return FALLBACK.get((base, page), page)


def _visible(user: m.User, ev, fdr_ids: set[str], obl_ids: set[str]) -> bool:
    if user.role != "INSTITUTION":
        return True
    inst = user.institution_id
    if ev.actor == f"institution:{inst}":
        return True
    d = ev.data
    return inst in d or any(f in d for f in fdr_ids) or any(o in d for o in obl_ids)


def what_changed(db: Session, user: m.User, since: str | None = None, now: datetime | None = None) -> dict:
    now = now or now_ist()
    since = since or (user.prev_login_at.isoformat(timespec="seconds") if user.prev_login_at else iso(now - timedelta(days=7)))
    fdr_ids: set[str] = set()
    obl_ids: set[str] = set()
    if user.role == "INSTITUTION":
        rows = db.execute(select(m.Fdr.id, m.Fdr.obligation_id).where(m.Fdr.institution_id == user.institution_id)).all()
        fdr_ids, obl_ids = {r[0] for r in rows}, {r[1] for r in rows}
        obl_ids |= set(db.scalars(select(m.Obligation.obligation_id).where(m.Obligation.institution_id == user.institution_id)))
    counts: Counter = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for model in (m.PortalEvent, m.KernelEvent):
        for ev in db.scalars(select(model).where(model.at >= since).order_by(model.seq)):
            if ev.type not in PHRASES or (ev.type == "document_downloaded" and user.role == "INSTITUTION"):
                continue
            if ev.actor == f"user:{user.id}" or not _visible(user, ev, fdr_ids, obl_ids):
                continue
            counts[ev.type] += 1
            try:
                d = json.loads(ev.data)
            except ValueError:
                d = {}
            ref = d.get("fdr_id") or d.get("obligation_id") or d.get("ref")
            if ref and len(examples[ev.type]) < 3 and ref not in examples[ev.type]:
                examples[ev.type].append(str(ref))
    base = BASE.get(user.role, "/aicte")
    items = [{"type": t, "count": c, "text": (PHRASES[t][0] if c == 1 else PHRASES[t][1]).format(n=c), "examples": examples[t],
              "link": f"{base}/{_page(base, PHRASES[t][2])}"} for t, c in counts.most_common()]
    aud = audiences(user)
    needs = db.scalars(select(m.Notification).where(m.Notification.audience.in_(aud), m.Notification.ack_at.is_(None),
                                                    m.Notification.rung.in_(("deadline", "overdue"))).order_by(m.Notification.at.desc()).limit(6)).all()
    from .outbox import title
    lang = user.lang or "en"
    attention = [{"id": n.id, "rung": n.rung, "title": title(n, lang), "at": n.at, "ref": n.ref} for n in needs]
    if user.role == "INSTITUTION":
        open_obs = db.scalar(select(func.count()).select_from(m.Observation).where(m.Observation.institution_id == user.institution_id,
                                                                                    m.Observation.status == "open"))
    else:
        open_obs = db.scalar(select(func.count()).select_from(m.Observation).where(m.Observation.status == "answered"))
    return {"since": since, "until": iso(now), "first_visit": user.prev_login_at is None, "items": items, "attention": attention,
            "open_observations": open_obs, "source": "portal and ledger audit trails"}


def _median_hours(pairs: list[tuple[str, str]]) -> float | None:
    hrs = [(parse(b) - parse(a)).total_seconds() / 3600 for a, b in pairs if a and b]
    return round(statistics.median(hrs), 1) if hrs else None


def health(db: Session, days: int = 30, now: datetime | None = None) -> dict:
    now = now or now_ist()
    since = iso(now - timedelta(days=days))
    notes = db.scalars(select(m.Notification).where(m.Notification.at >= since, m.Notification.template.is_not(None))).all()
    ids = [n.id for n in notes]
    dels = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id.in_(ids))).all() if ids else []
    by_channel: dict[str, Counter] = defaultdict(Counter)
    for d in dels:
        c = by_channel[d.channel]
        c["total"] += 1
        # "sent" below is a semantic count, including delivered rows; count each once.
        if d.status != "sent":
            c[d.status] += 1
        if d.sent_at or d.status in ("sent", "delivered", "digested"):
            c["sent"] += 1 if d.status != "digested" else 0
        if d.delivered_at:
            c["delivered_simulated" if d.receipt_simulated else "delivered_receipt"] += 1
        if d.simulated:
            c["simulated"] += 1
    roots = [n for n in notes if n.template not in ("digest",)]
    acked = [n for n in roots if n.ack_at]
    by_rung = {}
    for r in ("info", "action", "deadline", "overdue"):
        rs = [n for n in roots if n.rung == r]
        by_rung[r] = {"notices": len(rs), "acknowledged": sum(1 for n in rs if n.ack_at),
                      "median_hours_to_action": _median_hours([(n.at, n.ack_at) for n in rs if n.ack_at])}
    per_inst: dict[str, list[m.Notification]] = defaultdict(list)
    for n in roots:
        if n.institution_id:
            per_inst[n.institution_id].append(n)
    names = dict(db.execute(select(m.Institution.id, m.Institution.name).where(m.Institution.id.in_(list(per_inst)))).all()) if per_inst else {}
    inst_rows = sorted(({"institution_id": i, "institution": names.get(i, i), "notices": len(ns), "acknowledged": sum(1 for n in ns if n.ack_at),
                         "ack_rate": round(sum(1 for n in ns if n.ack_at) / len(ns), 3),
                         "median_hours_to_action": _median_hours([(n.at, n.ack_at) for n in ns if n.ack_at]),
                         "escalated": sum(1 for n in ns if n.escalated_at)} for i, ns in per_inst.items()),
                       key=lambda r: (r["ack_rate"], -r["notices"]))
    from .channels import summary
    return {"window_days": days, "since": since, "generated_at": iso(now), "providers": summary(),
            "totals": {"notices": len(roots), "deliveries": len(dels), "acknowledged": len(acked),
                       "ack_rate": round(len(acked) / len(roots), 3) if roots else None,
                       "escalated": sum(1 for n in roots if n.escalated_at), "escalation_notices": sum(1 for n in roots if n.template in ("rung_up", "escalation_copy")),
                       "median_hours_to_action": _median_hours([(n.at, n.ack_at) for n in acked])},
            "by_channel": {k: dict(v) for k, v in by_channel.items()}, "by_rung": by_rung, "per_institution": inst_rows[:50],
            "note": "Measured from notification and delivery rows. 'delivered_receipt' counts real provider receipts only; "
                    "simulated providers' receipts are counted separately as delivered_simulated."}
