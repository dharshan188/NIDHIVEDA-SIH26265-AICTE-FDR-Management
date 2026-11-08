"""SIMULATED bank layer. Every bank here is simulated; nothing talks to a real bank.

- Each bank has its own Ed25519 key pair(s). Private keys are derived from TL_SIM_BANK_SEED (an env
  secret) and the key id, so no private key is stored in the repo or the database.
- Each bank keeps its own "core-banking book" (sim_bank_fdrs, sim_bank_accounts). Confirmations are
  answered from that book, so a bank can disagree with what an institution declared.
- Every envelope carries "simulated": true inside the signed payload and at the top level.
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crypto import blind_index
from ..config import get_settings
from .. import models as m
from . import interface as i

from trustledger.audit import canonical  # noqa: E402
from trustledger.crypto import b64  # noqa: E402

BANKS: dict[str, str] = {
    "SBI": "State Bank of India", "HDFC": "HDFC Bank", "ICICI": "ICICI Bank", "CANARA": "Canara Bank",
    "PNB": "Punjab National Bank", "BOB": "Bank of Baroda", "AXIS": "Axis Bank", "UNION": "Union Bank of India",
    "INDIAN": "Indian Bank", "BOI": "Bank of India", "KOTAK": "Kotak Mahindra Bank", "IDBI": "IDBI Bank",
}
IFSC_PREFIX = {"SBI": "SBIN", "HDFC": "HDFC", "ICICI": "ICIC", "CANARA": "CNRB", "PNB": "PUNB", "BOB": "BARB", "AXIS": "UTIB",
               "UNION": "UBIN", "INDIAN": "IDIB", "BOI": "BKID", "KOTAK": "KKBK", "IDBI": "IBKL"}
FINANCE_BANK = "SBI"
AICTE_POOL_ACCOUNT = "AICTE-POOL-0001"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def private_key(key_id: str) -> Ed25519PrivateKey:
    seed = get_settings().sim_bank_seed
    if not seed:
        raise RuntimeError("TL_SIM_BANK_SEED is not set; the bank simulator cannot sign")
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(f"{seed}|{key_id}".encode()).digest())


def public_key_b64(key_id: str) -> str:
    raw = private_key(key_id).public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return b64(raw)


def sign(bank: str, key_id: str, kind: str, payload: dict, signed_at: str | None = None) -> dict:
    payload = {**payload, "simulated": True}
    env = {"kind": kind, "bank": bank, "key_id": key_id, "signed_at": signed_at or now_iso(), "payload": payload}
    sig = private_key(key_id).sign(canonical(env).encode())
    return {**env, "signature": b64(sig), "simulated": True}


class _Base:
    def __init__(self, db: Session) -> None:
        self.db = db

    def key_for(self, bank: str) -> str:
        """The bank's current signing key: the newest one that is neither ended nor compromised."""
        rows = self.db.scalars(select(m.BankSigner).where(m.BankSigner.bank == bank).order_by(m.BankSigner.key_id.desc())).all()
        for r in rows:
            if not r.ended_at and not r.compromised_from:
                return r.key_id
        return rows[0].key_id if rows else f"{bank}-K1"


class SimAdvice(_Base, i.AdviceChannel):
    def credit_advice(self, bank, utr, amount, value_date, remitter_name, remitter_account, narrative, beneficiary_account=AICTE_POOL_ACCOUNT):
        return sign(bank, self.key_for(bank), "credit_advice", {
            "utr": utr, "amount": amount, "value_date": value_date, "remitter_name": remitter_name,
            "remitter_account": remitter_account, "narrative": narrative, "beneficiary_account": beneficiary_account})

    def debit_advice(self, refund_id, utr, amount, beneficiary_account, beneficiary_ifsc):
        return sign(FINANCE_BANK, self.key_for(FINANCE_BANK), "debit_advice", {
            "refund_id": refund_id, "utr": utr, "amount": amount, "remitter": "AICTE", "remitter_account": AICTE_POOL_ACCOUNT,
            "beneficiary_account": beneficiary_account, "beneficiary_ifsc": beneficiary_ifsc, "date": now_iso()[:10]})


class SimCreditConfirmation(_Base, i.CreditConfirmationChannel):
    def confirm(self, utr, amount, beneficiary_account, credited_at):
        return sign(FINANCE_BANK, self.key_for(FINANCE_BANK), "credit_confirmation", {
            "utr": utr, "amount": amount, "beneficiary_account": beneficiary_account, "credited_at": credited_at,
            "message_type": "N10/RTGS-ACK"})


class SimReturnAdvice(_Base, i.ReturnAdviceChannel):
    def return_payment(self, original_utr, return_utr, amount, reason_code):
        return sign(FINANCE_BANK, self.key_for(FINANCE_BANK), "return_advice", {
            "original_utr": original_utr, "return_utr": return_utr, "amount": amount, "reason_code": reason_code, "returned_at": now_iso()})


class SimFdrConfirmation(_Base, i.FdrConfirmationChannel):
    def confirm(self, bank, instrument_no):
        row = self.db.get(m.SimBankFdr, (bank, instrument_no))
        if row is None:
            # The bank has no such instrument: it says so, signed. The ledger records it as an unmatched confirmation.
            return sign(bank, self.key_for(bank), "instrument_confirmation", {
                "instrument_no": instrument_no, "as_of": now_iso()[:10], "status": "NOT_FOUND", "lien_holder": "NONE", "amount": 1,
                "maturity_date": "1900-01-01"})
        return sign(bank, self.key_for(bank), "instrument_confirmation", {
            "instrument_no": instrument_no, "as_of": now_iso()[:10], "status": row.status, "lien_holder": row.lien_holder,
            "amount": row.principal_paise, "maturity_date": row.maturity_date})

    def notify_change(self, bank, old_no, new_no, change_kind, new_maturity, remark=None):
        old = self.db.get(m.SimBankFdr, (bank, old_no))
        principal = old.principal_paise if old else 1
        if old:
            old.status, old.renewed_to = ("RENEWED" if change_kind == "auto_renewal" else "RENUMBERED"), new_no
            self.db.merge(m.SimBankFdr(bank=bank, instrument_no=new_no, principal_paise=principal, maturity_date=new_maturity,
                                       status="ACTIVE", lien_holder=old.lien_holder))
        return sign(bank, self.key_for(bank), "instrument_confirmation", {
            "instrument_no": new_no, "supersedes": old_no, "change_kind": change_kind, "changed_on": now_iso()[:10], "remark": remark,
            "as_of": now_iso()[:10], "status": "ACTIVE", "lien_holder": old.lien_holder if old else "AICTE", "amount": principal,
            "maturity_date": new_maturity})


class SimLienDischarge(_Base, i.LienDischargeChannel):
    def discharge(self, bank, instrument_no):
        row = self.db.get(m.SimBankFdr, (bank, instrument_no))
        if row:
            row.lien_holder, row.status = "NONE", "LIEN_DISCHARGED"
        return sign(bank, self.key_for(bank), "lien_discharge", {"instrument_no": instrument_no, "discharged_on": now_iso()[:10]})


class SimNameLookup(_Base, i.NameLookupChannel):
    def lookup(self, account, ifsc):
        row = self.db.get(m.SimBankAccount, (ifsc, blind_index(account)))
        name = row.name_at_bank if row and row.status == "OPEN" else ("ACCOUNT CLOSED" if row else "NO SUCH ACCOUNT")
        return sign(FINANCE_BANK, self.key_for(FINANCE_BANK), "name_lookup", {"account": account, "ifsc": ifsc, "name_at_bank": name})


class SimRemitterDetails(_Base, i.RemitterDetailsChannel):
    def remitter(self, bank, utr):
        c = self.db.get(m.BankCredit, "CR-" + utr)
        return sign(bank, self.key_for(bank), "remitter_details", {"utr": utr, "remitter_name": "UNKNOWN", "remitter_account": "UNKNOWN",
                                                                   "known_to_bank": c is not None})


class SimPooledBalance(_Base, i.PooledBalanceChannel):
    def balance(self, bank, balance, as_of):
        return sign(bank, self.key_for(bank), "pooled_balance", {"account": AICTE_POOL_ACCOUNT, "balance": balance, "as_of": as_of})


class SimKeyEvents(_Base, i.KeyEventChannel):
    def compromise_notice(self, key_id, compromised_from, reason):
        return {"kind": "key_compromise_notice", "key_id": key_id, "compromised_from": compromised_from, "reason": reason, "simulated": True}

    def revocation_notice(self, key_id, ended_at):
        return {"kind": "signer_revocation_notice", "key_id": key_id, "ended_at": ended_at, "simulated": True}


class SimulatedBankGateway(i.BankGateway):
    simulated = True

    def __init__(self, db: Session) -> None:
        self.advice = SimAdvice(db)
        self.credit_confirmation = SimCreditConfirmation(db)
        self.return_advice = SimReturnAdvice(db)
        self.fdr_confirmation = SimFdrConfirmation(db)
        self.lien_discharge = SimLienDischarge(db)
        self.name_lookup = SimNameLookup(db)
        self.remitter_details = SimRemitterDetails(db)
        self.pooled_balance = SimPooledBalance(db)
        self.key_events = SimKeyEvents(db)


def gateway(db: Session) -> i.BankGateway:
    """Single switch point: replace with a real gateway (per channel) once AICTE authorises bank links."""
    return SimulatedBankGateway(db)
