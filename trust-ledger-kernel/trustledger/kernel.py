"""FDR Trust Ledger: control kernel.

Event-sourced: every command validates, then appends an event to the
hash-chained store. State is only changed by `_apply(event)`, so the whole
state can be rebuilt by replaying the store (tested).

Money is held as integer paise. Times are ISO-8601 strings ("2026-09-01T10:00").
Actors are "role:name" strings, e.g. "deputy_director:meera".

What this kernel covers: the financial and regulatory controls the round-4
review called decisive. What it does NOT cover: UI, DSC/PKCS#7 parsing,
bank connectivity, RFC 3161 anchoring, JFDR integration.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .audit import EventStore
from .crypto import verify_envelope
from .rules import RuleResolver, load_packs

POLICY_PATH = Path(__file__).resolve().parent.parent / "data" / "policy.json"
LAKH = 100_000 * 100  # paise in one lakh rupees

CONFIDENCE_ORDER = ["UNVERIFIED_SOURCE", "UNCERTAIN", "LEGACY_DECLARED", "DECLARED", "CORROBORATED", "TRACEABLE"]
BASES = {"machine_reference", "institution_declaration", "legacy_register", "reconciliation_officer"}


def lakh(x: float) -> int:
    return int(round(x * LAKH))


def fmt(paise: int) -> str:
    return f"Rs {paise / LAKH:,.2f} lakh"


def load_policy(path: Path = POLICY_PATH) -> dict:
    return json.loads(Path(path).read_text())


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _add_working_days(start: str, n: int) -> str:
    d = _dt(start).date()
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d.isoformat()


def role_of(actor: str) -> str:
    return actor.split(":", 1)[0]


# --------------------------------------------------------------------------- errors
class DomainError(Exception):
    code = "DomainError"


class OverAllocation(DomainError):
    code = "OverAllocation"


class InvalidEvidence(DomainError):
    code = "InvalidEvidence"


class MandatoryOverride(DomainError):
    code = "MandatoryOverride"


class GateBlocked(DomainError):
    code = "GateBlocked"

    def __init__(self, decision):
        self.decision = decision
        super().__init__("blocked by: " + ", ".join(decision.blocked_by))


class StateError(DomainError):
    code = "StateError"


class Unauthorised(DomainError):
    code = "Unauthorised"


class ConflictOfInterest(DomainError):
    code = "ConflictOfInterest"


# --------------------------------------------------------------------------- decisions
@dataclass
class Check:
    code: str
    mandatory: bool
    ok: bool
    detail: str
    overridden_by: str | None = None


@dataclass
class Decision:
    obligation_id: str
    at: str
    checks: list = field(default_factory=list)
    releasable: int = 0
    requested: int = 0
    instrument_no: str | None = None
    relied_evidence: list = field(default_factory=list)

    @property
    def blocked_by(self) -> list[str]:
        return [c.code for c in self.checks if not c.ok and not c.overridden_by]

    @property
    def allowed(self) -> bool:
        return not self.blocked_by

    def as_dict(self) -> dict:
        return {
            "obligation_id": self.obligation_id, "at": self.at, "allowed": self.allowed,
            "blocked_by": self.blocked_by, "releasable": self.releasable, "requested": self.requested,
            "instrument_no": self.instrument_no, "relied_evidence": self.relied_evidence,
            "checks": [c.__dict__ for c in self.checks],
        }


# --------------------------------------------------------------------------- kernel
class Kernel:
    def __init__(self, policy: dict | None = None, packs: list[dict] | None = None) -> None:
        self.policy = policy if policy is not None else load_policy()
        self._packs = packs if packs is not None else load_packs()
        self.store = EventStore()
        self._reset()

    def _reset(self) -> None:
        self.rules = RuleResolver(self._packs)
        self.institutions: dict = {}
        self.obligations: dict = {}
        self.signers: dict = {}
        self.evidence: dict = {}
        self.credits: dict = {}
        self.utr_index: dict = {}          # deposit UTR -> credit_id
        self.allocations: dict = {}
        self._by_credit: dict = {}         # derived indexes (rebuilt on replay, not part of snapshot)
        self._by_obl: dict = {}
        self._refunds_by_obl: dict = {}
        self._acct_owner: dict = {}
        self.claims: dict = {}             # competing claims that were NOT allocated
        self.disputes: dict = {}
        self.holds: dict = {}
        self.refunds: dict = {}
        self.attempt_by_utr: dict = {}     # payment UTR -> (refund_id, attempt index)
        self.instruments: dict = {}
        self.instr_by_no: dict = {}
        self.entitlements: dict = {}
        self.affidavits: dict = {}
        self.payees: dict = {}
        self.overrides: dict = {}
        self.handlers: dict = {}
        self.renewal_requests: dict = {}
        self.nocs: dict = {}
        self.pooled_balance: dict | None = None
        self.outbox: list = []
        self.clock = ""
        self._notified: set = set()

    # ---------------------------------------------------------------- plumbing
    def _emit(self, etype: str, actor: str, at: str, data: dict):
        if self.clock and at < self.clock:
            raise StateError(f"time went backwards: {at} < {self.clock}")
        ev = self.store.append(etype, actor, at, data)
        self._apply(ev)
        return ev

    def _apply(self, ev) -> None:
        self.clock = max(self.clock, ev.at)
        getattr(self, "_on_" + ev.type)(ev)
        obl = ev.data.get("obligation_id")
        if obl and role_of(ev.actor) not in ("institution", "system", "bank", "registry_admin", "migration"):
            self.handlers.setdefault(obl, set()).add(ev.actor)

    @classmethod
    def replay(cls, store: EventStore, policy: dict, packs: list[dict]) -> "Kernel":
        k = cls(policy, packs)
        for ev in store:
            k.store._events.append(ev)
            k._apply(ev)
        return k

    def _notify(self, at: str, to: str, kind: str, text: str, ref: str) -> None:
        self.outbox.append({"at": at, "to": to, "kind": kind, "text": text, "ref": ref})

    def _require_role(self, actor: str, allowed: list[str]) -> None:
        if role_of(actor) not in allowed:
            raise Unauthorised(f"{actor} is not one of {allowed}")

    # ---------------------------------------------------------------- registry
    def _unique(self, kind, key, table):
        if key in table:
            raise StateError(f"{kind} id {key} already exists; IDs are immutable (use a correction event)")

    def register_institution(self, inst_id, name, at, known_accounts=(), actor="system:onboarding"):
        self._unique("institution", inst_id, self.institutions)
        for acct in known_accounts:
            if acct in self._acct_owner:
                raise StateError(f"account {acct} already registered to {self._acct_owner[acct]}")
        self._emit("institution_registered", actor, at, {"inst_id": inst_id, "name": name, "known_accounts": list(known_accounts)})

    def _on_institution_registered(self, ev):
        d = ev.data
        self.institutions[d["inst_id"]] = {"name": d["name"], "known_accounts": set(d["known_accounts"])}
        for acct in d["known_accounts"]:
            self._acct_owner[acct] = d["inst_id"]

    def register_signer(self, key_id, bank, public_key_b64, valid_from, at, actor="registry_admin:aicte"):
        self._unique("signer", key_id, self.signers)
        self._emit("signer_registered", actor, at, {"key_id": key_id, "bank": bank, "pub": public_key_b64, "valid_from": valid_from})

    def _on_signer_registered(self, ev):
        d = ev.data
        self.signers[d["key_id"]] = {"bank": d["bank"], "pub": d["pub"], "valid_from": d["valid_from"], "ended_at": None, "compromised_from": None}

    def end_signer(self, key_id, ended_at, at, actor="registry_admin:aicte"):
        """Ordinary end of authority (officer transferred). Evidence received before ended_at stays valid."""
        self._emit("signer_ended", actor, at, {"key_id": key_id, "ended_at": ended_at})

    def _on_signer_ended(self, ev):
        self.signers[ev.data["key_id"]]["ended_at"] = ev.data["ended_at"]

    def compromise_signer(self, key_id, compromised_from, at, reason, actor="registry_admin:aicte"):
        """Key compromised from a date: every item received on/after that date is invalid, and dependants are flagged."""
        self._emit("signer_compromised", actor, at, {"key_id": key_id, "compromised_from": compromised_from, "reason": reason})

    def _on_signer_compromised(self, ev):
        d = ev.data
        self.signers[d["key_id"]]["compromised_from"] = d["compromised_from"]
        hit = [eid for eid, e in self.evidence.items() if e["key_id"] == d["key_id"] and e["received_at"] >= d["compromised_from"]]
        for eid in hit:
            self._notify(ev.at, "internal_audit", "evidence_invalidated",
                         f"Evidence {eid} relied on key {d['key_id']} after its compromise date {d['compromised_from']}; dependent decisions re-checked.", eid)
        for noc_id, n in self.nocs.items():
            if set(n["relied_evidence"]) & set(hit):
                self._notify(ev.at, "internal_audit", "issued_noc_needs_review",
                             f"NOC {noc_id} was issued relying on now-invalid evidence; review required (not auto-reversed).", noc_id)
        for rid, r in self.refunds.items():
            if set(r["relied_evidence"]) & set(hit):
                self._notify(ev.at, "internal_audit", "refund_needs_review",
                             f"Refund {rid} relied on now-invalid evidence; review required.", rid)

    def _signer_valid_at(self, key_id: str, when: str) -> tuple[bool, str]:
        s = self.signers.get(key_id)
        if not s:
            return False, "unknown signer"
        if when < s["valid_from"]:
            return False, "before signer authority began"
        if s["compromised_from"] and when >= s["compromised_from"]:
            return False, f"signer compromised from {s['compromised_from']}"
        if s["ended_at"] and when > s["ended_at"]:
            return False, f"signer authority ended {s['ended_at']}"
        return True, "ok"

    def evidence_valid(self, eid: str) -> bool:
        e = self.evidence.get(eid)
        return bool(e) and self._signer_valid_at(e["key_id"], e["received_at"])[0]

    # ---------------------------------------------------------------- bank evidence
    def record_bank_evidence(self, evidence_id, envelope, at, actor="bank:channel"):
        """Verify and record a signed bank message. Validity is judged at RECEIPT time (our clock),
        so a compromised key cannot back-date its way past the compromise date."""
        if evidence_id in self.evidence:
            if self.evidence[evidence_id].get("signature") == envelope.get("signature"):
                return None            # exact re-delivery of the same signed message: no-op
            self._emit("evidence_rejected", actor, at, {"evidence_id": evidence_id, "kind": envelope.get("kind"), "reason": "evidence id reused with different content"})
            raise InvalidEvidence("evidence id reused with different content")
        s = self.signers.get(envelope.get("key_id"))
        reason = None
        if not s:
            reason = "unknown signer"
        elif not verify_envelope(envelope, s["pub"]):
            reason = "signature does not verify"
        elif envelope["bank"] != s["bank"]:
            reason = "signer belongs to a different bank"
        else:
            ok, why = self._signer_valid_at(envelope["key_id"], at)
            if not ok:
                reason = why
        if reason is None:
            reason = self._validate_evidence_semantics(envelope)
        if reason:
            self._emit("evidence_rejected", actor, at, {"evidence_id": evidence_id, "kind": envelope.get("kind"), "reason": reason})
            raise InvalidEvidence(reason)
        self._emit("evidence_recorded", actor, at, {"evidence_id": evidence_id, "envelope": envelope})

    def _on_evidence_rejected(self, ev):
        self._notify(ev.at, "internal_audit", "evidence_rejected", f"Rejected {ev.data['kind']} {ev.data['evidence_id']}: {ev.data['reason']}", ev.data["evidence_id"])

    def _validate_evidence_semantics(self, env) -> str | None:
        p, kind = env["payload"], env["kind"]
        if kind == "credit_advice" and p["utr"] in self.utr_index:
            return "duplicate credit UTR"
        if kind in ("debit_advice",):
            r = self.refunds.get(p["refund_id"])
            if not r or r["state"] != "INITIATED":
                return "debit for a refund that is not initiated"
            if p["amount"] != r["amount"]:
                return "debit amount differs from authorised refund amount"
        if kind in ("credit_confirmation", "return_advice"):
            utr = p["utr"] if kind == "credit_confirmation" else p["original_utr"]
            if utr not in self.attempt_by_utr:
                return "unknown payment UTR"
            rid, i = self.attempt_by_utr[utr]
            att = self.refunds[rid]["attempts"][i]
            if env["bank"] != self.evidence[att["debit_evidence"]]["bank"]:
                return "confirmation/return must come from the bank that debited the payment"
            if kind == "credit_confirmation" and att["status"] != "DEBITED":
                return f"credit confirmation for attempt in state {att['status']}"
            if kind == "credit_confirmation":
                if p.get("amount") != att["amount"]:
                    return "credit confirmation amount differs from the amount paid"
                if p.get("beneficiary_account") != att["beneficiary_account"]:
                    return "credit confirmation names a different beneficiary account"
            if kind == "return_advice":
                if att["status"] not in ("DEBITED", "SETTLED"):
                    return f"return for attempt in state {att['status']}"
                if p["amount"] != att["amount"]:
                    return "return amount differs from payment amount"
        fin_bank = self.policy["payments"].get("finance_bank")
        if kind in ("debit_advice", "name_lookup") and fin_bank and env["bank"] != fin_bank:
            return f"{kind} accepted only from AICTE Finance's bank ({fin_bank})"
        if kind == "debit_advice" and p["utr"] in self.attempt_by_utr:
            return "payment UTR already used by another payment attempt"
        if kind == "instrument_confirmation":
            no = p["instrument_no"] if p["instrument_no"] in self.instr_by_no else p.get("supersedes")
            if no in self.instr_by_no and env["bank"] != self.instruments[self.instr_by_no[no]]["bank"]:
                return "instrument confirmation must come from the instrument's issuing bank"
            if not isinstance(p.get("amount"), int) or p["amount"] <= 0:
                return "instrument confirmation without a valid principal amount"
        if kind == "lien_discharge" and p["instrument_no"] in self.instr_by_no \
                and env["bank"] != self.instruments[self.instr_by_no[p["instrument_no"]]]["bank"]:
            return "lien discharge must come from the instrument's issuing bank"
        if kind == "lien_discharge":
            n = next((n for n in self.nocs.values() if n["instrument_no"] == p["instrument_no"]), None)
            if not n:
                return "lien discharge for an instrument with no NOC"
        if kind == "remitter_details":
            if p["utr"] not in self.utr_index:
                return "remitter details for unknown UTR"
            if env["bank"] != self.evidence[self.credits[self.utr_index[p["utr"]]]["evidence_id"]]["bank"]:
                return "remitter details must come from the bank that holds the credit"
        return None

    def _on_evidence_recorded(self, ev):
        d = ev.data
        env, eid = d["envelope"], d["evidence_id"]
        p, kind = env["payload"], env["kind"]
        self.evidence[eid] = {"kind": kind, "key_id": env["key_id"], "bank": env["bank"], "signed_at": env["signed_at"], "received_at": ev.at, "payload": p,
                              "signature": env["signature"]}
        if kind == "credit_advice":
            cid = "CR-" + p["utr"]
            self.credits[cid] = {"utr": p["utr"], "amount": p["amount"], "value_date": p["value_date"], "remitter_name": p.get("remitter_name"),
                                 "remitter_account": p.get("remitter_account"), "narrative": p.get("narrative", ""), "kind": "deposit", "evidence_id": eid}
            self.utr_index[p["utr"]] = cid
        elif kind == "remitter_details":
            c = self.credits[self.utr_index[p["utr"]]]
            c["remitter_name"], c["remitter_account"] = p["remitter_name"], p["remitter_account"]
            c["remitter_evidence_id"] = eid
        elif kind == "debit_advice":
            r = self.refunds[p["refund_id"]]
            att = {"utr": p["utr"], "rail": r["rail"], "amount": p["amount"], "debited_at": ev.at, "status": "DEBITED", "debit_evidence": eid,
                   "beneficiary_account": r["paying_to"]}
            r["attempts"].append(att)
            self.attempt_by_utr[p["utr"]] = (p["refund_id"], len(r["attempts"]) - 1)
            r["state"] = "DEBITED"
            r["history"].append((ev.at, "DEBITED", p["utr"]))
        elif kind == "credit_confirmation":
            rid, i = self.attempt_by_utr[p["utr"]]
            r = self.refunds[rid]
            r["attempts"][i].update(status="SETTLED", settled_at=ev.at, confirm_evidence=eid)
            r["state"] = "SETTLED"
            r["history"].append((ev.at, "SETTLED", p["utr"]))
            self._notify(ev.at, f"institution:{r['inst_id']}", "refund_settled", f"Completed: your bank confirmed credit of {fmt(r['amount'])} (UTR {p['utr']}).", rid)
        elif kind == "return_advice":
            rid, i = self.attempt_by_utr[p["original_utr"]]
            r = self.refunds[rid]
            att = r["attempts"][i]
            after_settlement = att["status"] == "SETTLED"
            att.update(status="RETURNED", returned_at=ev.at, return_reason=p["reason_code"], return_evidence=eid, returned_after_settlement=after_settlement)
            rcid = "RET-" + p["return_utr"]
            self.credits[rcid] = {"utr": p["return_utr"], "amount": p["amount"], "value_date": ev.at[:10], "kind": "return",
                                  "returns_utr": p["original_utr"], "evidence_id": eid, "remitter_name": None, "remitter_account": None, "narrative": ""}
            needs_payee = p["reason_code"] in self.policy["payments"]["return_reasons_requiring_payee_reverification"]
            if needs_payee:
                self.payees[r["inst_id"]]["verified"] = False
                self.payees[r["inst_id"]]["invalidated_by"] = eid
            r["state"] = "REISSUE_REQUIRED"
            r["history"].append((ev.at, "RETURNED" + ("_AFTER_SETTLEMENT" if after_settlement else ""), p["original_utr"]))
            target = _add_working_days(ev.at, self.policy["payments"]["reissue_target_working_days"])
            r["reissue_target"] = target
            step = "update and re-verify your bank account (Affidavit-9 process), then AICTE Finance re-issues" if needs_payee else "AICTE Finance re-issues to the same verified account"
            self._notify(ev.at, "finance", "payment_returned",
                         f"{r['rail']} UTR {p['original_utr']} for refund {rid} RETURNED ({p['reason_code']}){' AFTER it was marked settled - investigate' if after_settlement else ''}. Liability of {fmt(r['amount'])} reopened. Re-issue target {target}.", rid)
            self._notify(ev.at, f"institution:{r['inst_id']}", "refund_returned",
                         f"Your bank returned AICTE's payment of {fmt(r['amount'])} on {ev.at[:10]} (reason: {p['reason_code']}). The refund is NOT complete and AICTE still owes you this amount. Owner: AICTE Finance. Next step: {step}. Target: {target}.", rid)
        elif kind == "instrument_confirmation":
            self._apply_instrument_confirmation(ev, eid, p)
        elif kind == "lien_discharge":
            noc = next(n for n in self.nocs.values() if n["instrument_no"] == p["instrument_no"])
            noc["state"] = "LIEN_DISCHARGED"
            noc["discharged_at"] = ev.at
            ins = self.instruments[self.instr_by_no[p["instrument_no"]]]
            ins["status"] = "DISCHARGED"
            self._notify(ev.at, f"institution:{noc['inst_id']}", "lien_discharged", f"Completed: bank confirmed lien on FDR {p['instrument_no']} discharged.", noc["noc_id"])
        elif kind == "name_lookup":
            for inst, pay in self.payees.items():
                if pay["account"] == p["account"] and pay["ifsc"] == p["ifsc"]:
                    match = p["name_at_bank"].strip().casefold() == pay["name"].strip().casefold()
                    pay["verified"] = match
                    pay["lookup_evidence"] = eid
                    if not match:
                        self._notify(ev.at, f"institution:{inst}", "payee_name_mismatch", f"Bank name look-up returned '{p['name_at_bank']}', which does not match '{pay['name']}'.", inst)
        elif kind == "pooled_balance":
            self.pooled_balance = {"balance": p["balance"], "as_of": p["as_of"], "evidence_id": eid}

    # ---------------------------------------------------------------- obligations & allocation
    def create_obligation(self, obligation_id, inst_id, programme, amount, instrument_class, at, reference=None, actor="system:portal", legacy=False):
        self._unique("obligation", obligation_id, self.obligations)
        if inst_id not in self.institutions:
            raise StateError("unknown institution")
        if instrument_class not in ("ONLINE", "FDR"):
            raise StateError("instrument_class must be ONLINE or FDR")
        if amount <= 0:
            raise StateError("amount must be positive")
        self._emit("obligation_created", actor, at, {"obligation_id": obligation_id, "inst_id": inst_id, "programme": programme,
                                                     "amount": amount, "instrument_class": instrument_class, "reference": reference, "legacy": legacy})

    def _on_obligation_created(self, ev):
        d = dict(ev.data)
        d["legacy_declared"] = 0
        self.obligations[d["obligation_id"]] = d

    def remaining_on_credit(self, credit_id: str) -> int:
        c = self.credits[credit_id]
        used = sum(a["amount"] for a in self._allocs_on_credit(credit_id) if a["active"])
        return c["amount"] - used

    def allocated_to(self, obligation_id: str) -> int:
        return sum(a["amount"] for a in self._allocs_for_obl(obligation_id) if a["active"])

    def _allocs_on_credit(self, credit_id):
        return [self.allocations[x] for x in self._by_credit.get(credit_id, [])]

    def _allocs_for_obl(self, obligation_id):
        return [self.allocations[x] for x in self._by_obl.get(obligation_id, [])]

    def _index_alloc(self, alloc_id):
        a = self.allocations[alloc_id]
        for idx, key in ((self._by_credit, a["credit_id"]), (self._by_obl, a["obligation_id"])):
            lst = idx.setdefault(key, [])
            if alloc_id not in lst:
                lst.append(alloc_id)

    def allocate(self, alloc_id, credit_id, obligation_id, amount, basis, at, actor):
        """Many-to-many: one credit may fund several obligations; one obligation may be funded by several credits.
        Invariants: allocated <= received per credit; allocated <= required per obligation; amount > 0."""
        if basis not in BASES:
            raise StateError(f"unknown basis {basis}")
        if alloc_id in self.allocations or alloc_id in self.claims:
            raise StateError(f"allocation id {alloc_id} already used")
        c = self.credits.get(credit_id)
        o = self.obligations.get(obligation_id)
        if not c or not o:
            raise StateError("unknown credit or obligation")
        if c["kind"] != "deposit":
            raise StateError("a returned-payment credit cannot be allocated as a new deposit")
        if o["instrument_class"] != "ONLINE":
            raise StateError("FDR obligations are funded by instruments, not credits")
        if amount <= 0:
            raise OverAllocation("allocation must be positive")
        if basis == "machine_reference" and (not o["reference"] or o["reference"] not in re.split(r"[^A-Za-z0-9-]+", c["narrative"])):
            raise StateError("machine_reference basis claimed but the credit narrative does not carry the obligation reference")
        if self.allocated_to(obligation_id) + amount > o["amount"]:
            raise OverAllocation(f"obligation {obligation_id} would exceed its required {fmt(o['amount'])}")
        if amount > self.remaining_on_credit(credit_id):
            others = {self.obligations[a["obligation_id"]]["inst_id"] for a in self._allocs_on_credit(credit_id)
                      if a["active"]} - {o["inst_id"]}
            if others:
                # A competing claim from another institution: record it, open a dispute, move no money.
                dispute_id = f"DSP-{credit_id}"
                self._emit("competing_claim", actor, at, {"claim_id": alloc_id, "credit_id": credit_id, "obligation_id": obligation_id,
                                                          "amount": amount, "basis": basis, "dispute_id": dispute_id,
                                                          "claimants": sorted(others | {o["inst_id"]})})
                return {"status": "DISPUTED", "dispute_id": dispute_id}
            raise OverAllocation(f"credit {credit_id} has only {fmt(self.remaining_on_credit(credit_id))} unallocated")
        self._emit("allocated", actor, at, {"alloc_id": alloc_id, "credit_id": credit_id, "obligation_id": obligation_id, "amount": amount, "basis": basis})
        return {"status": "ALLOCATED"}

    def _on_allocated(self, ev):
        d = ev.data
        self.allocations[d["alloc_id"]] = {**d, "active": True, "at": ev.at}
        self._index_alloc(d["alloc_id"])

    def _on_competing_claim(self, ev):
        d = ev.data
        self.claims[d["claim_id"]] = dict(d)
        ds = self.disputes.setdefault(d["dispute_id"], {"credit_id": d["credit_id"], "claimants": [], "status": "OPEN", "opened_at": ev.at, "basis": "competing claims exceed credit"})
        ds["claimants"] = sorted(set(ds["claimants"]) | set(d["claimants"]))
        self._notify(ev.at, "finance", "attribution_dispute", f"Competing claims on credit {d['credit_id']} by {', '.join(d['claimants'])}. Only allocations on this credit are affected.", d["dispute_id"])

    def reverse_allocation(self, alloc_id, at, actor, reason):
        if not self.allocations.get(alloc_id, {}).get("active"):
            raise StateError("no active allocation")
        o = self.allocations[alloc_id]["obligation_id"]
        if self.committed_refunds(o) > self.allocated_to(o) - self.allocations[alloc_id]["amount"]:
            raise StateError("cannot reverse: refunds already committed against this allocation")
        self._emit("allocation_reversed", actor, at, {"alloc_id": alloc_id, "reason": reason, "obligation_id": o})

    def _on_allocation_reversed(self, ev):
        self.allocations[ev.data["alloc_id"]]["active"] = False

    def open_dispute(self, dispute_id, credit_id, claimants, basis, at, actor):
        self._require_role(actor, self.policy["holds"]["who_may_place"])
        if not basis:
            raise StateError("a dispute needs a recorded basis")
        self._unique("dispute", dispute_id, self.disputes)
        self._emit("dispute_opened", actor, at, {"dispute_id": dispute_id, "credit_id": credit_id, "claimants": sorted(claimants), "basis": basis})

    def _on_dispute_opened(self, ev):
        d = ev.data
        self.disputes[d["dispute_id"]] = {"credit_id": d["credit_id"], "claimants": d["claimants"], "status": "OPEN", "opened_at": ev.at, "basis": d["basis"]}

    def resolve_dispute(self, dispute_id, at, actor, reference, award: dict):
        """award: {claim_or_alloc_id: amount_to_keep}. Competent authority decides; the kernel enforces the invariants."""
        self._require_role(actor, self.policy["roles"]["approve_release"])
        ds = self.disputes[dispute_id]
        credit = self.credits[ds["credit_id"]]
        if sum(award.values()) > credit["amount"]:
            raise OverAllocation("award exceeds the credit")
        for item_id, amt in award.items():
            src = self.allocations.get(item_id) or self.claims.get(item_id)
            if not src or src["credit_id"] != ds["credit_id"] or amt < 0:
                raise StateError(f"{item_id} is not a claim or allocation on the disputed credit")
            oid = src["obligation_id"]
            others = sum(a["amount"] for a in self._allocs_for_obl(oid) if a["active"] and a["alloc_id"] not in award)
            if others + sum(v for k2, v in award.items() if (self.allocations.get(k2) or self.claims.get(k2))["obligation_id"] == oid) > self.obligations[oid]["amount"]:
                raise OverAllocation(f"award would over-fund obligation {oid}")
        kept_elsewhere = sum(a["amount"] for a in self._allocs_on_credit(ds["credit_id"]) if a["active"] and a["alloc_id"] not in award)
        if kept_elsewhere + sum(award.values()) > credit["amount"]:
            raise OverAllocation("award plus remaining allocations exceed the credit")
        self._emit("dispute_resolved", actor, at, {"dispute_id": dispute_id, "reference": reference, "award": award})

    def _on_dispute_resolved(self, ev):
        d = ev.data
        ds = self.disputes[d["dispute_id"]]
        ds["status"] = "RESOLVED"
        for item_id, amt in d["award"].items():
            if item_id in self.allocations:
                a = self.allocations[item_id]
                a["active"] = amt > 0
                a["amount"] = amt if amt > 0 else a["amount"]
                a["basis"] = "reconciliation_officer" if amt > 0 else a["basis"]
                a["ruling"] = d["reference"]
            elif item_id in self.claims and amt > 0:
                c = self.claims[item_id]
                self.allocations[item_id] = {"alloc_id": item_id, "credit_id": c["credit_id"], "obligation_id": c["obligation_id"], "amount": amt,
                                             "basis": "reconciliation_officer", "active": True, "at": ev.at, "ruling": d["reference"]}
                self._index_alloc(item_id)

    # ---------------------------------------------------------------- confidence
    def allocation_confidence(self, alloc_id: str) -> str:
        a = self.allocations[alloc_id]
        c = self.credits[a["credit_id"]]
        inst = self.institutions[self.obligations[a["obligation_id"]]["inst_id"]]
        if not self.evidence_valid(c["evidence_id"]):
            return "UNVERIFIED_SOURCE"
        if any(ds["credit_id"] == a["credit_id"] and ds["status"] == "OPEN" for ds in self.disputes.values()):
            return "UNCERTAIN"
        if a.get("ruling"):
            return "CORROBORATED"
        if a["basis"] == "machine_reference":
            return "TRACEABLE"
        rem_ev = c.get("remitter_evidence_id", c["evidence_id"])
        owner = self._acct_owner.get(c.get("remitter_account"))
        if owner and owner != self.obligations[a["obligation_id"]]["inst_id"] and self.evidence_valid(rem_ev):
            return "UNCERTAIN"   # bank says the money came from ANOTHER registered institution
        remitter_ok = self.evidence_valid(rem_ev) and (
            (c.get("remitter_account") and c["remitter_account"] in inst["known_accounts"])
            or (c.get("remitter_name") and c["remitter_name"].strip().casefold() == inst["name"].strip().casefold()))
        if remitter_ok:
            return "CORROBORATED"
        return "LEGACY_DECLARED" if a["basis"] == "legacy_register" else "DECLARED"

    def _held(self, *, alloc_id=None, credit_id=None, instrument_id=None) -> list[str]:
        out = []
        for hid, h in self.holds.items():
            if h["status"] != "ACTIVE":
                continue
            s = h["scope"]
            if (alloc_id and alloc_id in s.get("allocations", [])) or (credit_id and credit_id in s.get("credits", [])) \
                    or (instrument_id and instrument_id in s.get("instruments", [])):
                out.append(hid)
        return out

    def funding_breakdown(self, obligation_id: str) -> dict:
        out = {k: 0 for k in CONFIDENCE_ORDER}
        out["HELD"] = 0
        for a in self._allocs_for_obl(obligation_id):
            aid = a["alloc_id"]
            if a["active"]:
                if self._held(alloc_id=aid, credit_id=a["credit_id"]):
                    out["HELD"] += a["amount"]
                else:
                    out[self.allocation_confidence(aid)] += a["amount"]
        out["LEGACY_DECLARED"] += self.obligations[obligation_id]["legacy_declared"]
        return out

    # ---------------------------------------------------------------- holds
    def place_hold(self, hold_id, scope, basis, at, actor):
        hp = self.policy["holds"]
        self._require_role(actor, hp["who_may_place"])
        if hp["basis_required"] and not basis:
            raise StateError("hold needs a recorded basis")
        if hp["scope"] == "affected_items_only" and (set(scope) - {"allocations", "credits", "instruments"}):
            raise StateError("policy allows holds on specific allocations, credits or instruments only, not whole institutions")
        self._unique("hold", hold_id, self.holds)
        review_due = (_dt(at) + timedelta(days=hp["review_after_days"])).isoformat(timespec="minutes")
        self._emit("hold_placed", actor, at, {"hold_id": hold_id, "scope": scope, "basis": basis, "review_due": review_due,
                                              "policy": self.policy["policy_id"]})

    def _on_hold_placed(self, ev):
        self.holds[ev.data["hold_id"]] = {**ev.data, "status": "ACTIVE", "placed_at": ev.at, "placed_by": ev.actor}

    def release_hold(self, hold_id, at, actor, reason):
        self._require_role(actor, self.policy["holds"]["who_may_place"] + self.policy["roles"]["approve_release"])
        self._emit("hold_released", actor, at, {"hold_id": hold_id, "reason": reason})

    def _on_hold_released(self, ev):
        self.holds[ev.data["hold_id"]]["status"] = "RELEASED"

    # ---------------------------------------------------------------- case facts
    def record_entitlement(self, obligation_id, basis, at, actor):
        self._emit("entitlement_recorded", actor, at, {"obligation_id": obligation_id, "basis": basis})

    def _on_entitlement_recorded(self, ev):
        self.entitlements[ev.data["obligation_id"]] = {"basis": ev.data["basis"], "at": ev.at, "by": ev.actor}

    def record_affidavit(self, obligation_id, kind, format_ok, at, actor):
        self._emit("affidavit_recorded", actor, at, {"obligation_id": obligation_id, "kind": kind, "format_ok": format_ok})

    def _on_affidavit_recorded(self, ev):
        self.affidavits[ev.data["obligation_id"]] = {"kind": ev.data["kind"], "format_ok": ev.data["format_ok"]}

    def register_payee(self, inst_id, account, ifsc, name, at, actor, change_basis=None):
        existing = self.payees.get(inst_id)
        if existing and not (change_basis and change_basis.get("affidavit") == "AFFIDAVIT-9" and change_basis.get("ter_fee_paid")):
            raise StateError("changing a registered payee account needs Affidavit-9 and the TER fee (APH 2024-27)")
        self._emit("payee_registered", actor, at, {"inst_id": inst_id, "account": account, "ifsc": ifsc, "name": name, "change_basis": change_basis})

    def _on_payee_registered(self, ev):
        d = ev.data
        self.payees[d["inst_id"]] = {"account": d["account"], "ifsc": d["ifsc"], "name": d["name"], "verified": False}

    def payee_verified(self, inst_id: str) -> bool:
        pay = self.payees.get(inst_id)
        return bool(pay and pay["verified"] and pay.get("lookup_evidence") and self.evidence_valid(pay["lookup_evidence"]))

    def override_admin(self, obligation_id, code, at, actor, reason):
        if code not in self.policy["admin_checks"]:
            self._emit("override_refused", actor, at, {"obligation_id": obligation_id, "code": code, "reason": reason})
            raise MandatoryOverride(f"{code} is a mandatory clearance and cannot be overridden")
        self._require_role(actor, self.policy["admin_checks"][code]["override_roles"])
        if not reason:
            raise StateError("override needs a reason")
        self._emit("admin_override", actor, at, {"obligation_id": obligation_id, "code": code, "reason": reason})

    def _on_override_refused(self, ev):
        self._notify(ev.at, "internal_audit", "override_refused", f"{ev.actor} tried to override mandatory {ev.data['code']} on {ev.data['obligation_id']}.", ev.data["obligation_id"])

    def _on_admin_override(self, ev):
        self.overrides[(ev.data["obligation_id"], ev.data["code"])] = ev.actor

    # ---------------------------------------------------------------- rules
    def confirm_rule_pack(self, edition_id, at, actor, reference):
        self._require_role(actor, self.policy["roles"]["legal_ruling"])
        self._emit("rule_pack_confirmed", actor, at, {"edition_id": edition_id, "reference": reference})

    def _on_rule_pack_confirmed(self, ev):
        self.rules.confirm_pack(ev.data["edition_id"])

    def legal_ruling(self, case_id, key, on_date, value, reference, at, actor):
        self._require_role(actor, self.policy["roles"]["legal_ruling"])
        self._emit("legal_ruling", actor, at, {"case_id": case_id, "key": key, "on_date": on_date, "value": value, "reference": reference})

    def _on_legal_ruling(self, ev):
        d = ev.data
        self.rules.add_ruling(d["case_id"], d["key"], d["on_date"], d["value"], d["reference"])

    # ---------------------------------------------------------------- FDR instruments
    def register_instrument(self, instrument_id, obligation_id, number, bank, amount, issue_date, maturity_date, at, actor, source="institution"):
        self._unique("instrument", instrument_id, self.instruments)
        if number in self.instr_by_no:
            raise StateError("instrument number already registered")
        if self.obligations[obligation_id]["instrument_class"] != "FDR":
            raise StateError("not an FDR obligation")
        self._emit("instrument_registered", actor, at, {"instrument_id": instrument_id, "obligation_id": obligation_id, "number": number, "bank": bank,
                                                        "amount": amount, "issue_date": issue_date, "maturity_date": maturity_date, "source": source})

    def _on_instrument_registered(self, ev):
        d = ev.data
        self.instruments[d["instrument_id"]] = {**d, "status": "ACTIVE", "confirmations": [], "renewed_from": None, "superseded_by": None, "renewal": None}
        self.instr_by_no[d["number"]] = d["instrument_id"]

    def _apply_instrument_confirmation(self, ev, eid, p):
        """Bank's statement of an instrument's current position. Handles: plain re-confirmation, auto-renewal
        to a new number (change_kind=auto_renewal), a renumbering without renewal (change_kind=renumbered),
        and an unexpected discharge or lien change reported by the bank."""
        no = p["instrument_no"]
        if no not in self.instr_by_no and p.get("supersedes") in self.instr_by_no:
            old = self.instruments[self.instr_by_no[p["supersedes"]]]
            kind = p.get("change_kind", "auto_renewal")
            new_id = f"{old['instrument_id']}>{no}"
            self.instruments[new_id] = {"instrument_id": new_id, "obligation_id": old["obligation_id"], "number": no, "bank": old["bank"],
                                        "amount": p["amount"], "issue_date": p.get("changed_on"), "maturity_date": p["maturity_date"], "source": "bank",
                                        "status": "ACTIVE", "confirmations": [], "renewed_from": old["instrument_id"], "superseded_by": None,
                                        "renewal": {"kind": kind, "renewed_on": p["changed_on"], "remark": p.get("remark")} if kind == "auto_renewal" else None}
            self.instr_by_no[no] = new_id
            old["superseded_by"] = new_id
            old["status"] = "RENEWED" if kind == "auto_renewal" else "RENUMBERED"
        iid = self.instr_by_no.get(no)
        if not iid:
            self._notify(ev.at, "finance", "unmatched_instrument", f"Bank confirmation for unknown instrument {no}; not linked to any obligation.", eid)
            return
        ins = self.instruments[iid]
        ins["confirmations"].append({"evidence_id": eid, "as_of": p["as_of"], "status": p["status"], "lien_holder": p["lien_holder"],
                                     "amount": p["amount"], "maturity_date": p["maturity_date"]})
        has_noc = any(n["instrument_no"] == no for n in self.nocs.values())
        if (p["status"] != "ACTIVE" or p["lien_holder"] != "AICTE") and not has_noc:
            self._notify(ev.at, "internal_audit", "lien_anomaly",
                         f"Bank reports {no} status={p['status']} lien={p['lien_holder']} but AICTE issued no NOC. Investigate.", iid)

    def current_instrument(self, obligation_id: str) -> dict | None:
        cands = [i for i in self.instruments.values() if i["obligation_id"] == obligation_id and not i["superseded_by"]]
        return cands[-1] if cands else None

    def request_renewal(self, instrument_id, renewal_date, new_number, new_maturity, at, actor):
        """A manual renewal/replacement request. Rules are resolved for the renewal DATE."""
        ins = self.instruments[instrument_id]
        after = renewal_date > ins["maturity_date"]
        key = "fdr.manual_renewal_after_maturity"
        if not after:
            outcome, cites, status = "ACCEPTED_PENDING_BANK_CONFIRMATION", ["pre-maturity renewal/replacement"], "n/a"
        else:
            res = self.rules.resolve(key, renewal_date, case_id=instrument_id)
            status, cites = res.status, res.cites
            if res.usable and res.value == "prohibited":
                outcome = "REJECTED"
            elif res.usable and res.value in ("permitted", "permitted_with_bank_remark"):
                outcome = "ACCEPTED_PENDING_BANK_CONFIRMATION"
            else:
                outcome = "ESCALATED_TO_LEGAL_CELL"
        self._emit("renewal_decided", actor, at, {"instrument_id": instrument_id, "obligation_id": ins["obligation_id"], "renewal_date": renewal_date,
                                                  "new_number": new_number, "new_maturity": new_maturity, "outcome": outcome,
                                                  "rule_status": status, "cites": cites})
        return outcome

    def _on_renewal_decided(self, ev):
        d = ev.data
        self.renewal_requests[(d["instrument_id"], d["renewal_date"])] = d
        if d["outcome"] == "REJECTED":
            ins = self.instruments[d["instrument_id"]]
            self._notify(ev.at, f"institution:{self.obligations[ins['obligation_id']]['inst_id']}", "renewal_rejected",
                         f"Renewal of FDR {ins['number']} after maturity is not permitted ({'; '.join(d['cites'])}). Options: release on entitlement, or replacement as the rules allow.", d["instrument_id"])
        if d["outcome"] == "ESCALATED_TO_LEGAL_CELL":
            self._notify(ev.at, "legal_cell", "rule_question", f"Which rule governs renewal of {d['instrument_id']} on {d['renewal_date']}? Resolver status: {d['rule_status']}.", d["instrument_id"])

    # ---------------------------------------------------------------- release gate
    def committed_refunds(self, obligation_id: str) -> int:
        return sum(self.refunds[x]["amount"] for x in self._refunds_by_obl.get(obligation_id, []) if self.refunds[x]["state"] != "CANCELLED")

    def evaluate_release(self, obligation_id, at, approver, amount=None) -> Decision:
        o = self.obligations[obligation_id]
        dec = Decision(obligation_id, at)
        add = lambda code, mand, ok, detail: dec.checks.append(Check(code, mand, ok, detail, self.overrides.get((obligation_id, code)) if not mand else None))
        day = at[:10]

        ent = self.entitlements.get(obligation_id)
        add("M_ENTITLEMENT", True, bool(ent), ent["basis"] if ent else "no entitlement basis recorded")
        key = "release.fdr_instrument" if o["instrument_class"] == "FDR" else "release.online_instrument"
        res = self.rules.resolve(key, day, case_id=obligation_id)
        add("M_RULES", True, res.usable, f"{res.status}: {res.value} ({'; '.join(res.cites)})")
        aff = self.affidavits.get(obligation_id)
        add("M_AFFIDAVIT_6", True, bool(aff and aff["kind"] == "AFFIDAVIT-6"), "Affidavit-6 on record" if aff else "missing Affidavit-6")
        if aff and not aff["format_ok"]:
            add("AFFIDAVIT_FORMAT", False, False, "format deviates from template")
        role_ok = role_of(approver) in self.policy["roles"]["approve_release"]
        add("M_APPROVER_ROLE", True, role_ok, f"{approver} {'may' if role_ok else 'may not'} approve")
        coi = approver in self.handlers.get(obligation_id, set())
        add("M_CONFLICT_OF_INTEREST", True, not coi, f"{approver} handled this case earlier" if coi else "approver has not handled this case")

        if o["instrument_class"] == "ONLINE":
            fb = self.funding_breakdown(obligation_id)
            sufficient = sum(fb[k] for k in self.policy["release"]["online_sufficient_confidence"])
            dec.releasable = max(0, sufficient - self.committed_refunds(obligation_id))
            dec.requested = amount if amount is not None else max(0, self.allocated_to(obligation_id) + o["legacy_declared"] - self.committed_refunds(obligation_id))
            partial_ok = self.policy["release"]["allow_partial_release_of_undisputed_amount"]
            ok = dec.requested > 0 and dec.requested <= dec.releasable
            detail = (f"requested {fmt(dec.requested)}, releasable now {fmt(dec.releasable)}; breakdown "
                      + ", ".join(f"{k}={fmt(v)}" for k, v in fb.items() if v))
            if not ok and partial_ok and dec.releasable > 0:
                detail += f" -> a partial release of {fmt(dec.releasable)} is allowed by policy"
            add("M_ATTRIBUTION", True, ok, detail)
            pay = self.payees.get(o["inst_id"])
            pay_ok = self.payee_verified(o["inst_id"])
            add("M_PAYEE_VERIFIED", True, pay_ok,
                "registered account verified by bank name look-up" if pay_ok else "payee not verified (name look-up evidence missing, mismatched or invalidated by a return)")
            for a in self._allocs_for_obl(obligation_id):
                if a["active"]:
                    dec.relied_evidence.append(self.credits[a["credit_id"]]["evidence_id"])
            if pay and pay.get("lookup_evidence"):
                dec.relied_evidence.append(pay["lookup_evidence"])
        else:
            ins = self.current_instrument(obligation_id)
            if not ins:
                add("M_CURRENT_INSTRUMENT", True, False, "no instrument on record")
            else:
                dec.instrument_no = ins["number"]
                valid = [c for c in ins["confirmations"] if self.evidence_valid(c["evidence_id"])]
                last = max(valid, key=lambda c: c["as_of"]) if valid else None
                max_age = self.policy["release"]["fdr_current_instrument_max_evidence_age_days"]
                problems = []
                if not last:
                    problems.append("no valid bank confirmation of this instrument")
                else:
                    age = (_dt(day) - _dt(last["as_of"][:10])).days
                    if age > max_age:
                        problems.append(f"latest bank confirmation is {age} days old (policy max {max_age})")
                    if self.policy["release"]["fdr_evidence_must_postdate_last_maturity"] and ins["maturity_date"] <= day and last["as_of"][:10] < ins["maturity_date"]:
                        problems.append("instrument matured after the latest confirmation; bank may have renewed or paid it")
                    if last["amount"] != ins["amount"]:
                        problems.append(f"bank-confirmed principal {fmt(last['amount'])} differs from recorded {fmt(ins['amount'])}: discrepancy review")
                    if last["status"] != "ACTIVE" or last["lien_holder"] != "AICTE":
                        problems.append(f"bank reports status={last['status']} lien={last['lien_holder']}")
                    dec.relied_evidence.append(last["evidence_id"])
                add("M_CURRENT_INSTRUMENT", True, not problems, "; ".join(problems) or f"bank confirmed {ins['number']} active under AICTE lien as of {last['as_of'][:10]}")
                if ins["renewal"]:
                    rr = self.rules.resolve("fdr.auto_renewal", ins["renewal"]["renewed_on"], case_id=obligation_id)
                    ok = rr.usable and rr.value in ("accepted_with_bank_remark", "accepted")
                    if ok and rr.value == "accepted_with_bank_remark" and not ins["renewal"]["remark"]:
                        ok, extra = False, "; bank remark on auto-renewal missing"
                    else:
                        extra = ""
                    add("M_RENEWAL_RULES", True, ok, f"auto-renewal on {ins['renewal']['renewed_on']}: {rr.status} {rr.value} ({'; '.join(rr.cites) or 'no clause'}){extra}")
                held = self._held(instrument_id=ins["instrument_id"])
                add("M_NO_HOLD", True, not held, f"holds: {held}" if held else "no hold on this instrument")
        return dec

    # ---------------------------------------------------------------- release, NOC, payment
    def authorise_release(self, case_id, obligation_id, at, approver, amount=None, rail="RTGS"):
        if case_id in self.refunds or case_id in self.nocs:
            raise StateError(f"case id {case_id} already used")
        live = [n["noc_id"] for n in self.nocs.values() if n["obligation_id"] == obligation_id]
        if live:
            raise StateError(f"NOC {live[0]} already issued for this obligation; supersede or cancel it formally")
        dec = self.evaluate_release(obligation_id, at, approver, amount)
        o = self.obligations[obligation_id]
        if o["instrument_class"] == "ONLINE" and not dec.allowed and dec.blocked_by == ["M_ATTRIBUTION"] and amount is None \
                and dec.releasable > 0 and self.policy["release"]["allow_partial_release_of_undisputed_amount"]:
            dec = self.evaluate_release(obligation_id, at, approver, dec.releasable)
        if not dec.allowed:
            self._emit("release_refused", approver, at, {"obligation_id": obligation_id, "decision": dec.as_dict()})
            raise GateBlocked(dec)
        if o["instrument_class"] == "ONLINE":
            self._emit("refund_authorised", approver, at, {"refund_id": case_id, "obligation_id": obligation_id, "inst_id": o["inst_id"],
                                                           "amount": dec.requested, "rail": rail, "decision": dec.as_dict()})
        else:
            self._emit("noc_issued", approver, at, {"noc_id": case_id, "obligation_id": obligation_id, "inst_id": o["inst_id"],
                                                    "instrument_no": dec.instrument_no, "decision": dec.as_dict()})
        return dec

    def _on_release_refused(self, ev):
        pass

    def _on_refund_authorised(self, ev):
        d = ev.data
        self.refunds[d["refund_id"]] = {"refund_id": d["refund_id"], "obligation_id": d["obligation_id"], "inst_id": d["inst_id"], "amount": d["amount"],
                                        "rail": d["rail"], "state": "AUTHORISED", "approver": ev.actor, "attempts": [], "history": [(ev.at, "AUTHORISED", None)],
                                        "relied_evidence": d["decision"]["relied_evidence"]}
        self._refunds_by_obl.setdefault(d["obligation_id"], []).append(d["refund_id"])

    def _on_noc_issued(self, ev):
        d = ev.data
        self.nocs[d["noc_id"]] = {"noc_id": d["noc_id"], "obligation_id": d["obligation_id"], "inst_id": d["inst_id"], "instrument_no": d["instrument_no"],
                                  "state": "NOC_ISSUED", "approver": ev.actor, "relied_evidence": d["decision"]["relied_evidence"]}

    def initiate_payment(self, refund_id, at, actor):
        r = self.refunds[refund_id]
        self._require_role(actor, self.policy["roles"]["initiate_payment"])
        if actor == r["approver"]:
            raise ConflictOfInterest("the approver cannot also initiate the payment")
        if r["state"] not in ("AUTHORISED", "REISSUE_REQUIRED"):
            raise StateError(f"cannot initiate from {r['state']}")
        # time-of-use re-check of the controls that can change after authorisation
        pay = self.payees.get(r["inst_id"])
        if not self.payee_verified(r["inst_id"]):
            raise GateBlocked(Decision(r["obligation_id"], at, [Check("M_PAYEE_VERIFIED", True, False, "payee must be (re)verified before (re)issue")]))
        bad = [e for e in r["relied_evidence"] if not self.evidence_valid(e)]
        if bad:
            raise GateBlocked(Decision(r["obligation_id"], at, [Check("M_EVIDENCE_VALID", True, False, f"evidence now invalid: {bad}")]))
        held = [a["alloc_id"] for a in self._allocs_for_obl(r["obligation_id"]) if a["active"] and self._held(alloc_id=a["alloc_id"], credit_id=a["credit_id"])]
        fb = self.funding_breakdown(r["obligation_id"])
        sufficient = sum(fb[k] for k in self.policy["release"]["online_sufficient_confidence"])
        if sufficient < self.committed_refunds(r["obligation_id"]):
            raise GateBlocked(Decision(r["obligation_id"], at, [Check("M_ATTRIBUTION", True, False, f"funding no longer sufficient (held: {held})")]))
        self._emit("payment_initiated", actor, at, {"refund_id": refund_id, "obligation_id": r["obligation_id"], "payee": dict(pay)})

    def _on_payment_initiated(self, ev):
        r = self.refunds[ev.data["refund_id"]]
        r["state"] = "INITIATED"
        r["paying_to"] = ev.data["payee"]["account"]
        r["history"].append((ev.at, "INITIATED", None))

    def tick(self, at, actor="system:scheduler"):
        """Time-driven controls: overdue credit confirmations and hold reviews. Emits events (auditable)."""
        due = []
        for rid, r in self.refunds.items():
            for i, att in enumerate(r["attempts"]):
                win = self.policy["payments"]["confirmation_window_minutes"][att["rail"]]
                key = ("overdue", rid, i)
                if att["status"] == "DEBITED" and _dt(at) > _dt(att["debited_at"]) + timedelta(minutes=win) and key not in self._notified:
                    due.append(("confirmation_overdue", {"refund_id": rid, "attempt": i, "utr": att["utr"], "window_min": win}))
        for hid, h in self.holds.items():
            key = ("hold", hid)
            if h["status"] == "ACTIVE" and at >= h["review_due"] and key not in self._notified:
                due.append(("hold_review_due", {"hold_id": hid}))
        for etype, data in due:
            self._emit(etype, actor, at, data)

    def _on_confirmation_overdue(self, ev):
        d = ev.data
        self._notified.add(("overdue", d["refund_id"], d["attempt"]))
        self._notify(ev.at, "finance", "confirmation_overdue",
                     f"No credit confirmation for UTR {d['utr']} within {d['window_min']} min. Status stays 'awaiting confirmation'; chase AICTE's bank.", d["refund_id"])

    def _on_hold_review_due(self, ev):
        h = self.holds[ev.data["hold_id"]]
        self._notified.add(("hold", ev.data["hold_id"]))
        self._notify(ev.at, "competent_authority", "hold_review_due",
                     f"Hold {ev.data['hold_id']} ({h['basis']}) placed by {h['placed_by']} reached its review date; decide: continue with recorded reason, or release.", ev.data["hold_id"])

    # ---------------------------------------------------------------- legacy migration
    def import_legacy(self, batch_id, records, at, actor="migration:batch"):
        """Imports legacy records WITHOUT marking anything verified.
        ONLINE: if a legacy UTR matches exactly one bank-statement credit of the same amount, a legacy_register allocation is made
        (confidence comes from bank evidence only; never TRACEABLE). Otherwise the amount stays LEGACY_DECLARED.
        FDR: the instrument is registered with source=legacy and NO confirmation, so release later needs a just-in-time bank confirmation.
        Nothing is blocked and no institution is asked to resubmit at import time."""
        report = {"records": 0, "linked_to_bank_credit": 0, "declared_only": 0, "disputed": 0, "flagged_duplicate": 0, "fdr_registered": 0}
        for rec in records:
            report["records"] += 1
            oid = f"LEG-{rec['legacy_id']}"
            if rec["inst_id"] not in self.institutions:
                self.register_institution(rec["inst_id"], rec.get("inst_name", rec["inst_id"]), at, actor=actor)
            self.create_obligation(oid, rec["inst_id"], rec.get("programme", "legacy"), rec["amount"], rec["instrument_class"], at, actor=actor, legacy=True)
            if rec["instrument_class"] == "FDR":
                self.register_instrument(f"I-{oid}", oid, rec["fdr_number"], rec.get("bank", "unknown"), rec["amount"], rec.get("issue_date", "1900-01-01"),
                                         rec.get("maturity_date", "2099-12-31"), at, actor, source="legacy")
                report["fdr_registered"] += 1
                continue
            cid = self.utr_index.get(rec.get("utr") or "")
            if cid and self.credits[cid]["amount"] >= rec["amount"]:
                try:
                    out = self.allocate(f"A-{oid}", cid, oid, rec["amount"], "legacy_register", at, actor)
                except OverAllocation as e:
                    # Same institution claiming more of one credit than it holds: a likely duplicate record.
                    # Flag it; do NOT add it to the liability register.
                    self._emit("legacy_flagged", actor, at, {"obligation_id": oid, "batch_id": batch_id, "reason": f"possible duplicate: {e}"})
                    report["flagged_duplicate"] += 1
                    continue
                report["disputed" if out["status"] == "DISPUTED" else "linked_to_bank_credit"] += 1
                continue
            self._emit("legacy_declared", actor, at, {"obligation_id": oid, "amount": rec["amount"], "batch_id": batch_id,
                                                      "why": "no matching bank credit" if rec.get("utr") else "no payment reference"})
            report["declared_only"] += 1
        return report

    def _on_legacy_flagged(self, ev):
        self.obligations[ev.data["obligation_id"]]["flag"] = ev.data["reason"]
        self._notify(ev.at, "finance", "legacy_flagged", f"{ev.data['obligation_id']}: {ev.data['reason']}", ev.data["obligation_id"])

    def _on_legacy_declared(self, ev):
        self.obligations[ev.data["obligation_id"]]["legacy_declared"] += ev.data["amount"]

    # ---------------------------------------------------------------- reports
    def liability_register(self, obligation_id: str) -> dict:
        held = self.allocated_to(obligation_id) + self.obligations[obligation_id]["legacy_declared"]
        settled = in_transit = 0
        for r in (self.refunds[x] for x in self._refunds_by_obl.get(obligation_id, [])):
            for att in r["attempts"]:
                if att["status"] == "SETTLED":
                    settled += att["amount"]
                elif att["status"] == "DEBITED":
                    in_transit += att["amount"]
        return {"held_for_institution": held, "settled_refunds": settled, "in_transit": in_transit,
                "outstanding_liability": held - settled, "cash_with_aicte_for_this": held - settled - in_transit}

    def book_balance(self) -> int:
        credits = sum(c["amount"] for c in self.credits.values())
        debits = sum(att["amount"] for r in self.refunds.values() for att in r["attempts"])
        return credits - debits

    def refund_status_text(self, refund_id: str) -> str:
        r = self.refunds[refund_id]
        att = r["attempts"][-1] if r["attempts"] else None
        s = r["state"]
        if s == "AUTHORISED":
            return f"Refund of {fmt(r['amount'])} approved. Payment not yet sent."
        if s == "INITIATED":
            return "Payment instruction submitted to AICTE's bank. Not yet sent."
        if s == "DEBITED":
            return f"Sent from AICTE's bank on {att['debited_at']} via {att['rail']}, UTR {att['utr']}. Waiting for your bank's credit confirmation. NOT yet complete."
        if s == "SETTLED":
            return f"Completed: your bank confirmed credit on {att['settled_at']} (UTR {att['utr']})."
        if s == "REISSUE_REQUIRED":
            return (f"Payment UTR {att['utr']} was returned by your bank on {att['returned_at'][:10]} ({att['return_reason']}). "
                    f"NOT complete: AICTE still owes you {fmt(r['amount'])}. Owner: AICTE Finance. Target re-issue: {r['reissue_target']}.")
        return s

    def certification_report(self) -> dict:
        """What can honestly be certified: the pool in aggregate, and each institution only to the extent of its evidence."""
        per_inst: dict = {}
        unallocated = sum(self.remaining_on_credit(cid) for cid, c in self.credits.items() if c["kind"] == "deposit")
        total_outstanding = in_transit = 0
        for oid, o in self.obligations.items():
            lr = self.liability_register(oid)
            total_outstanding += lr["outstanding_liability"]
            in_transit += lr["in_transit"]
            if o["instrument_class"] != "ONLINE":
                continue
            fb = self.funding_breakdown(oid)
            row = per_inst.setdefault(o["inst_id"], {"certifiable": 0, "declared_not_certifiable": 0, "uncertain": 0, "held": 0, "unverified_source": 0})
            row["certifiable"] += fb["TRACEABLE"] + fb["CORROBORATED"]
            row["declared_not_certifiable"] += fb["DECLARED"] + fb["LEGACY_DECLARED"]
            row["uncertain"] += fb["UNCERTAIN"]
            row["held"] += fb["HELD"]
            row["unverified_source"] += fb["UNVERIFIED_SOURCE"]
        disputed_unallocated = sum(c["amount"] for c in self.claims.values()
                                   if c["claim_id"] not in self.allocations and self.disputes[c["dispute_id"]]["status"] == "OPEN")
        expected_pool = total_outstanding - in_transit + unallocated
        bank = self.pooled_balance
        legacy_total = sum(o["legacy_declared"] for o in self.obligations.values())
        return {
            "bank_confirmed_pool": bank["balance"] if bank and self.evidence_valid(bank["evidence_id"]) else None,
            "expected_pool_from_ledger": expected_pool,
            "aggregate_matches": bool(bank) and self.evidence_valid(bank["evidence_id"]) and bank["balance"] == expected_pool,
            "unallocated_credits": unallocated,
            "competing_claims_not_allocated": disputed_unallocated,
            "legacy_declared_total": legacy_total,
            "per_institution": per_inst,
            "statement": ("Aggregate pool can be certified against the bank. Individual balances are certified only to the 'certifiable' amounts; "
                          "declared, uncertain and held amounts are reported as such and are NOT certified."),
        }

    def confirmation_requests(self) -> list[dict]:
        """Risk-based: only allocations that are not already proven by bank evidence. Non-response has no effect."""
        wanted = set(self.policy["confirmations"]["request_only_for"])
        out = []
        for aid, a in self.allocations.items():
            if a["active"] and self.allocation_confidence(aid) in wanted:
                out.append({"inst_id": self.obligations[a["obligation_id"]]["inst_id"], "obligation_id": a["obligation_id"], "alloc_id": aid, "amount": a["amount"]})
        for oid, o in self.obligations.items():
            if o["legacy_declared"] and "LEGACY_DECLARED" in wanted:
                out.append({"inst_id": o["inst_id"], "obligation_id": oid, "alloc_id": None, "amount": o["legacy_declared"]})
        return out

    def snapshot(self) -> dict:
        def ser(x):
            if isinstance(x, set):
                return sorted(x)
            if isinstance(x, tuple):
                return list(x)
            return x
        state = {k: getattr(self, k) for k in ("institutions", "obligations", "signers", "evidence", "credits", "allocations", "claims", "disputes",
                                                "holds", "refunds", "instruments", "entitlements", "affidavits", "payees", "nocs", "outbox")}
        state["handlers"] = self.handlers
        state["overrides"] = {f"{k[0]}|{k[1]}": v for k, v in self.overrides.items()}
        return json.loads(json.dumps(state, default=ser, sort_keys=True))
