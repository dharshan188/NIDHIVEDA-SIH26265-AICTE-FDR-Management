"""Delivering bank messages into the ledger, and the Bank Authority Registry.

Validity is judged by the kernel at RECEIPT time (our clock), against the registry and AICTE's
own records. Every message, accepted or not, is logged in bank_messages with its outcome.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..crypto import seal_pii
from .. import models as m
from ..db import SessionLocal
from ..ledger import LEDGER
from .simulator import now_iso, public_key_b64

from trustledger.kernel import InvalidEvidence  # noqa: E402

CHANNEL_OF = {
    "credit_advice": "advice", "debit_advice": "advice", "credit_confirmation": "credit_confirmation",
    "return_advice": "return_advice", "instrument_confirmation": "fdr_confirmation", "lien_discharge": "lien_discharge",
    "name_lookup": "name_lookup", "remitter_details": "remitter_details", "pooled_balance": "pooled_balance",
}


def _log(env: dict, eid: str, at: str, status: str, reason: str | None, ref: str | None, scenario_id: str | None) -> m.BankMessage:
    with SessionLocal() as s:
        row = m.BankMessage(received_at=at, channel=CHANNEL_OF.get(env.get("kind"), "other"), kind=env.get("kind", "?"), bank=env.get("bank", "?"),
                            key_id=env.get("key_id", "?"), signed_at=env.get("signed_at", "?"), payload=seal_pii(env.get("payload", {})),
                            signature=env.get("signature", ""), evidence_id=eid, status=status, reason=reason,
                            simulated=bool(env.get("simulated", env.get("payload", {}).get("simulated"))), scenario_id=scenario_id, ref=ref)
        s.add(row)
        s.commit()
        return row


def deliver(db: Session, env: dict, *, evidence_id: str | None = None, ref: str | None = None, scenario_id: str | None = None,
            at: str | None = None) -> dict:
    """Hand a signed envelope to the kernel. Returns the logged outcome; never raises for a rejected message."""
    eid = evidence_id or f"E-{env.get('kind', 'msg')}-{uuid.uuid4().hex[:12]}"
    at = at or now_iso()
    already = eid in LEDGER.kernel().evidence
    try:
        LEDGER.run(db, lambda k: k.record_bank_evidence(eid, env, at))
        status, reason = ("DUPLICATE", "identical re-delivery; no change") if already else ("ACCEPTED", None)
    except InvalidEvidence as e:
        status, reason = "REJECTED", str(e)
    row = _log(env, eid, at, status, reason, ref, scenario_id)
    return {"id": row.id, "evidence_id": eid, "status": status, "reason": reason, "kind": env.get("kind"), "bank": env.get("bank"),
            "key_id": env.get("key_id"), "received_at": at, "simulated": row.simulated}


# ------------------------------------------------------------------ Bank Authority Registry
def register_signer(db: Session, bank: str, key_id: str, valid_from: str, at: str | None = None, note: str | None = None) -> None:
    pub = public_key_b64(key_id)
    at = at or now_iso()

    def after(s: Session, k, new) -> None:
        s.add(m.BankSigner(key_id=key_id, bank=bank, public_key=pub, valid_from=valid_from, note=note))

    LEDGER.run(db, lambda k: k.register_signer(key_id, bank, pub, valid_from, at), after)


def end_signer(db: Session, key_id: str, ended_at: str, actor: str, at: str | None = None) -> None:
    def after(s: Session, k, new) -> None:
        s.get(m.BankSigner, key_id).ended_at = ended_at

    LEDGER.run(db, lambda k: k.end_signer(key_id, ended_at, at or now_iso(), actor=actor), after)


def compromise_signer(db: Session, key_id: str, compromised_from: str, reason: str, actor: str, at: str | None = None) -> None:
    def after(s: Session, k, new) -> None:
        row = s.get(m.BankSigner, key_id)
        row.compromised_from, row.note = compromised_from, reason

    LEDGER.run(db, lambda k: k.compromise_signer(key_id, compromised_from, at or now_iso(), reason, actor=actor), after)
