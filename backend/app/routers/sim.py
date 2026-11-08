"""/sim: SIMULATOR CONTROL (dev only). Not mounted when TL_ENV != dev.

Everything here plays the part of a bank, an SMS provider, a DSC token or a test operator.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .. import models as m
from .. import portal_audit
from ..bank.deliver import compromise_signer, deliver, end_signer, register_signer
from ..bank.simulator import BANKS, gateway, sign
from ..config import BACKEND_DIR, get_settings
from ..db import get_db
from ..deps import Principal, dev_only, require
from ..domain import release as rel
from ..domain.common import now_iso
from ..ledger import LEDGER
from ..security import dev_dsc_sign, totp_secret
from .auth import DEV_OTP_OUTBOX

router = APIRouter(prefix="/sim", tags=["simulator (dev only)"], dependencies=[Depends(dev_only)])
OPERATOR = require("AICTE_OFFICIAL", "AUDITOR")
S01_S09 = ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09"]


# ------------------------------------------------------------------ dev helpers for the login screen
@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """Dev only: lets the login screen fill in demo credentials."""
    cfg = get_settings()
    path = BACKEND_DIR / ".dev-credentials.json"
    if cfg.demo_password:
        return {"accounts": [{"username": u.username, "password": cfg.demo_password, "role": u.role, "kernel_role": u.kernel_role, "name": u.full_name}
                             for u in db.scalars(select(m.User).order_by(m.User.id))]}
    return {"accounts": json.loads(path.read_text()) if path.exists() else []}


@router.get("/otp-outbox/{username}")
def otp_outbox(username: str):
    """What the MOCK SMS provider sent (dev only)."""
    return DEV_OTP_OUTBOX.get(username) or {"code": None}


@router.get("/totp/{username}")
def totp_now(username: str, db: Session = Depends(get_db)):
    """Stands in for the user's authenticator app (dev only)."""
    u = db.scalars(select(m.User).where(m.User.username == username)).first()
    if not u or not u.totp_secret_enc:
        raise HTTPException(404, "not found")
    secret = totp_secret(u.totp_secret_enc)
    return {"code": pyotp.TOTP(secret).now(), "otpauth": pyotp.TOTP(secret).provisioning_uri(username, issuer_name="NIDHIVEDA (dev)")}


class DscSignIn(BaseModel):
    username: str
    message: str


@router.post("/dsc/sign")
def dsc_sign(body: DscSignIn):
    """Stands in for the user's DSC token and signer utility (SIMULATED DSC issuer)."""
    try:
        return dev_dsc_sign(body.username, body.message)
    except FileNotFoundError as e:
        raise HTTPException(404, "no dev DSC for this user") from e


# ------------------------------------------------------------------ bank events
class InjectIn(BaseModel):
    bank: str
    kind: str
    payload: dict
    key_id: str | None = None
    signed_at: str | None = None
    evidence_id: str | None = None
    tamper_payload: dict | None = None   # applied AFTER signing: the signature must then fail
    ref: str | None = None


@router.post("/bank/inject")
def inject(body: InjectIn, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    if body.bank not in BANKS:
        raise HTTPException(422, "unknown bank")
    env = sign(body.bank, body.key_id or f"{body.bank}-K1", body.kind, body.payload, body.signed_at)
    if body.tamper_payload:
        env["payload"] = {**env["payload"], **body.tamper_payload}
    return deliver(db, env, evidence_id=body.evidence_id, ref=body.ref)


@router.post("/payments/{rid}/debit")
def sim_debit(rid: str, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    return rel.bank_debit(db, rid)


class ConfirmIn(BaseModel):
    amount_paise: int | None = None
    beneficiary_account: str | None = None


@router.post("/payments/{rid}/confirm")
def sim_confirm(rid: str, body: ConfirmIn | None = None, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    body = body or ConfirmIn()
    return rel.bank_confirm(db, rid, amount=body.amount_paise, account=body.beneficiary_account)


class ReturnIn(BaseModel):
    reason_code: str = "BENEFICIARY_BANK_REJECT"


@router.post("/payments/{rid}/return")
def sim_return(rid: str, body: ReturnIn, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    return rel.bank_return(db, rid, body.reason_code)


class ChangeIn(BaseModel):
    change_kind: str = "auto_renewal"   # or "renumbered"
    years: int = 3
    remark: str | None = "Auto-renewed on maturity under standing instruction"


@router.post("/fdrs/{fid}/bank-change")
def sim_fdr_change(fid: str, body: ChangeIn, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    f = db.get(m.Fdr, fid)
    if not f:
        raise HTTPException(404, "not found")
    new_no = f"{f.instrument_no[:6]}R{datetime.now():%y%m%d%H%M%S}"
    new_mat = (f.maturity_date + timedelta(days=365 * body.years)).isoformat()
    env = gateway(db).fdr_confirmation.notify_change(f.bank, f.instrument_no, new_no, body.change_kind, new_mat, body.remark)
    db.commit()
    return deliver(db, env, ref=fid)


# ------------------------------------------------------------------ keys
class KeyIn(BaseModel):
    at: str | None = None
    reason: str = "Bank reported key compromise (SIMULATED)"


@router.post("/keys/{key_id}/expire")
def expire_key(key_id: str, body: KeyIn, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    s = db.get(m.BankSigner, key_id)
    if not s:
        raise HTTPException(404, "not found")
    when = body.at or now_iso()
    notice = gateway(db).key_events.revocation_notice(key_id, when)
    end_signer(db, key_id, when, actor="registry_admin:aicte")
    _rotate(db, s.bank)
    return {"notice": notice, "signer": key_id, "ended_at": when}


@router.post("/keys/{key_id}/compromise")
def compromise_key(key_id: str, body: KeyIn, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    s = db.get(m.BankSigner, key_id)
    if not s:
        raise HTTPException(404, "not found")
    when = body.at or now_iso()
    notice = gateway(db).key_events.compromise_notice(key_id, when, body.reason)
    compromise_signer(db, key_id, when, body.reason, actor="registry_admin:aicte")
    _rotate(db, s.bank)
    return {"notice": notice, "signer": key_id, "compromised_from": when}


def _rotate(db: Session, bank: str) -> None:
    n = len(db.scalars(select(m.BankSigner).where(m.BankSigner.bank == bank)).all()) + 1
    register_signer(db, bank, f"{bank}-K{n}", now_iso()[:10], note="rotated in after previous key ended/compromised (SIMULATED)")


# ------------------------------------------------------------------ scenarios S01-S09 (kernel fixtures, replayed in a sandbox)
@router.get("/scenarios")
def scenarios(db: Session = Depends(get_db)):
    from trustledger.scenario import SCENARIO_DIR, load_scenario
    out = []
    for sid in S01_S09:
        f = next(SCENARIO_DIR.glob(f"{sid}_*.json"))
        sc = load_scenario(f)
        last = db.scalars(select(m.ScenarioRun).where(m.ScenarioRun.scenario_id == sid).order_by(m.ScenarioRun.id.desc())).first()
        out.append({"id": sid, "title": sc["title"], "answers": sc.get("reviewer_ref"), "steps": len(sc["steps"]),
                    "last_run": {"at": last.run_at.isoformat(timespec="seconds"), "passed": last.passed, "failed": last.failed} if last else None})
    return {"items": out}


@router.post("/scenarios/{sid}/replay")
def replay(sid: str, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    """Runs the scenario JSON with the kernel's own runner in a sandbox kernel (the live ledger is not touched),
    logging every bank message it generates as SIMULATED with scenario_id."""
    if sid not in S01_S09:
        raise HTTPException(404, "not found")
    from trustledger.scenario import SCENARIO_DIR, Runner, load_scenario, make_policy
    f = next(SCENARIO_DIR.glob(f"{sid}_*.json"))
    sc = load_scenario(f)
    runner = Runner(policy=make_policy(sc.get("policy_overrides")))
    msgs: list[m.BankMessage] = []
    orig = runner.k.record_bank_evidence

    def recording(evidence_id, envelope, at, actor="bank:channel"):
        status, reason = "ACCEPTED", None
        try:
            return orig(evidence_id, envelope, at, actor)
        except Exception as e:  # noqa: BLE001
            status, reason = "REJECTED", str(e)
            raise
        finally:
            msgs.append(m.BankMessage(received_at=at, channel="scenario", kind=envelope.get("kind", "?"), bank=envelope.get("bank", "?"),
                                      key_id=envelope.get("key_id", "?"), signed_at=envelope.get("signed_at", "?"),
                                      payload={**envelope.get("payload", {}), "simulated": True}, signature=envelope.get("signature", ""),
                                      evidence_id=evidence_id, status=status, reason=reason, simulated=True, scenario_id=sid, ref=sid))
    runner.k.record_bank_evidence = recording
    res = runner.run(sc)
    db.add_all(msgs)
    db.add(m.ScenarioRun(scenario_id=sid, title=sc["title"], run_at=datetime.now(), run_by=p.actor, passed=res["passed"], failed=res["failed"], log=res["log"]))
    portal_audit.record(db, "scenario_replayed", p.actor, {"scenario": sid, "passed": res["passed"], "failed": res["failed"]})
    db.commit()
    return {**res, "bank_messages": len(msgs), "sandbox": True, "simulated": True}


# ------------------------------------------------------------------ audit tamper (to demonstrate detection)
class TamperIn(BaseModel):
    seq: int
    mode: str = "edit"   # edit | delete_last


@router.post("/audit/tamper")
def tamper(body: TamperIn, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    """Simulates a privileged direct database edit, bypassing the insert-only triggers. Dev only."""
    pg = db.bind.dialect.name == "postgresql"
    if pg:
        db.execute(text("ALTER TABLE kernel_events DISABLE TRIGGER trg_kernel_events_io"))
    else:
        db.execute(text("DROP TRIGGER IF EXISTS trg_kernel_events_no_delete"))
    if body.mode == "edit":
        row = db.get(m.KernelEvent, body.seq)
        if not row:
            raise HTTPException(404, "not found")
        data = json.loads(row.data)
        data["tampered"] = True
        db.execute(text("UPDATE kernel_events SET data = :d WHERE seq = :s"), {"d": json.dumps(data, sort_keys=True, separators=(",", ":")), "s": body.seq})
    else:
        db.execute(text("DELETE FROM kernel_events WHERE seq = (SELECT MAX(seq) FROM kernel_events)"))
    if pg:
        db.execute(text("ALTER TABLE kernel_events ENABLE TRIGGER trg_kernel_events_io"))
    else:
        from ..invariants import SQLITE
        db.execute(text(SQLITE[2]))
    db.commit()
    return {"ok": True, "note": "the live in-memory kernel is unchanged; run /audit-trail/verify to see detection"}


@router.get("/status")
def status():
    return {"env": get_settings().env, "simulated_bank": True, "banks": BANKS, "kernel_events": len(LEDGER.kernel().store), "today": date.today().isoformat()}


# ------------------------------------------------------------------ Nudge Ladder (simulated time and providers)
class NudgeRunIn(BaseModel):
    at: str | None = None          # IST wall-clock time to act as "now", e.g. 2026-11-01T08:00:00
    reminders: bool = True
    escalate: bool = True
    digest: bool = False
    deliver: bool = True
    force: bool = False            # run the daily sweep even if it already ran today (still idempotent per window)
    fdr_ids: list[str] | None = None  # limit the sweep to these FDRs (useful at a simulated far-off date)


@router.post("/nudge/run")
def nudge_run(body: NudgeRunIn, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    """Dev only: runs the scheduled jobs now (or at a simulated IST time) instead of waiting for 08:00."""
    from ..nudge import escalation, reminders, worker
    from ..nudge.clock import IST, now_ist
    now = datetime.fromisoformat(body.at).replace(tzinfo=IST) if body.at else now_ist()
    out: dict = {"now": now.isoformat(timespec="seconds")}
    if body.reminders:
        out["reminders"] = reminders.sweep(db, now, force=body.force or bool(body.fdr_ids), only=body.fdr_ids)
    if body.escalate:
        out["escalation"] = escalation.sweep(db, now)
    if body.digest:
        out["digest"] = worker.digest(db, now)
    if body.deliver:   # drain the backlog (the 30 s worker would do this over several passes)
        total: dict = {}
        for _ in range(50):
            step = worker.run_once(db, now)
            for k, v in step.items():
                total[k] = total.get(k, 0) + v
            if step["planned"] == 0 and sum(v for k, v in step.items() if k != "planned") == 0:
                break
        out["delivery"] = total
    return out


@router.get("/providers/messages")
def provider_messages(channel: str = "", limit: int = 50, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    """What the provider simulators would have sent. SIMULATED: nothing left this machine."""
    q = select(m.ProviderSimMessage).order_by(m.ProviderSimMessage.id.desc()).limit(limit)
    if channel:
        q = q.where(m.ProviderSimMessage.channel == channel)
    return {"simulated": True, "items": [{"id": r.id, "channel": r.channel, "provider": r.provider, "to_role": r.to_role, "to": r.to_masked,
                                          "lang": r.lang, "subject": r.subject, "body": r.body, "at": r.created_at, "calls": r.calls}
                                         for r in db.scalars(q)]}


class SimReceiptIn(BaseModel):
    channel: str | None = None


@router.post("/providers/receipts")
def provider_receipts(body: SimReceiptIn, p: Principal = Depends(OPERATOR), db: Session = Depends(get_db)):
    """The simulators' delivery receipts. Marked receipt_simulated: the health panel counts them apart from real receipts."""
    from ..nudge.clock import iso, now_ist
    q = select(m.NotificationDelivery).where(m.NotificationDelivery.status == "sent", m.NotificationDelivery.simulated.is_(True))
    if body.channel:
        q = q.where(m.NotificationDelivery.channel == body.channel)
    n = 0
    for d in db.scalars(q):
        d.status, d.delivered_at, d.receipt_simulated = "delivered", iso(now_ist()), True
        portal_audit.record(db, "notification_receipt", f"provider:{d.provider}", {"delivery_id": d.id, "channel": d.channel, "status": "delivered",
                                                                                  "simulated": True, "recipient_role": d.recipient_role})
        n += 1
    db.commit()
    return {"receipts": n, "simulated": True}


class BookFdrIn(BaseModel):
    bank: str
    instrument_no: str
    amount_paise: int
    maturity_date: str
    lien_holder: str = "AICTE"


@router.post("/bank/fdrs")
def book_fdr(body: BookFdrIn, p: Principal = Depends(require("INSTITUTION", "AICTE_OFFICIAL", "AUDITOR")), db: Session = Depends(get_db)):
    """Dev only: the (simulated) bank issues an FDR in its own core-banking book, as a real bank would before the
    institution uploads it. Later confirmations are answered from this book."""
    if body.bank not in BANKS:
        raise HTTPException(422, "unknown bank")
    db.merge(m.SimBankFdr(bank=body.bank, instrument_no=body.instrument_no, principal_paise=body.amount_paise, maturity_date=body.maturity_date,
                          status="ACTIVE", lien_holder=body.lien_holder))
    db.commit()
    return {"booked": True, "simulated": True}
