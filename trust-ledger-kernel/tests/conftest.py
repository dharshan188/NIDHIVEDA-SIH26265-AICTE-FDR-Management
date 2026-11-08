import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trustledger.crypto import TestBankSigner  # noqa: E402
from trustledger.kernel import Kernel, lakh, load_policy  # noqa: E402
from trustledger.rules import load_packs  # noqa: E402


class World:
    """Small helper so tests read like the business story."""

    def __init__(self, policy=None, packs=None):
        self.k = Kernel(policy or copy.deepcopy(load_policy()), packs if packs is not None else load_packs())
        self.bank = TestBankSigner("SBI", "SBI-K1")
        self.k.register_signer("SBI-K1", "SBI", self.bank.public_key_b64, "2000-01-01", "2000-01-01T00:00")
        self.k.register_institution("A", "Alpha Institute", "2000-01-02T00:00", known_accounts=["ACC-A"])
        self.k.register_institution("B", "Beta College", "2000-01-02T00:00", known_accounts=["ACC-B"])
        self._n = 0

    def ev(self, kind, payload, at, eid=None, signer=None):
        self._n += 1
        s = signer or self.bank
        self.k.record_bank_evidence(eid or f"E{self._n}", s.sign(kind, payload, at), at)

    def credit(self, utr, amount, at, narrative="", remitter_account=None):
        self.ev("credit_advice", {"utr": utr, "amount": amount, "value_date": at[:10], "narrative": narrative, "remitter_account": remitter_account}, at)
        return "CR-" + utr

    def ready_online(self, oid="O1", inst="A", amount=lakh(35), at="2026-01-01T10:00"):
        """Obligation funded by a traceable credit, entitled, affidavit and verified payee."""
        ref = f"REF-{oid}"
        self.k.create_obligation(oid, inst, "UG", amount, "ONLINE", at, reference=ref)
        cid = self.credit(f"UTR-{oid}", amount, at, narrative=ref)
        self.k.allocate(f"AL-{oid}", cid, oid, amount, "machine_reference", at, "system:auto")
        self.k.record_entitlement(oid, "closure", at, "section_officer:kiran")
        self.k.record_affidavit(oid, "AFFIDAVIT-6", True, at, "section_officer:kiran")
        if inst not in self.k.payees:
            name = self.k.institutions[inst]["name"]
            self.k.register_payee(inst, f"ACC-{inst}", "IFSC0001", name, at, f"institution:{inst}")
            self.ev("name_lookup", {"account": f"ACC-{inst}", "ifsc": "IFSC0001", "name_at_bank": name}, at)
        return oid


@pytest.fixture
def world():
    return World()
