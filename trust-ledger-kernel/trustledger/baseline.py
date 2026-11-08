"""A conventional status-field workflow, written by us as the comparison point.

It is NOT JFDR (we have not seen JFDR's internals). It models the common design the
round-4 reviewer described: one credit per obligation, Completed on UTR + debit,
institution-level holds, migrated records marked Verified, NOC from the FDR number on file,
no edition-aware rules, signatures checked once at upload.
"""
from __future__ import annotations


class ConventionalWorkflow:
    def __init__(self) -> None:
        self.credit_owner: dict = {}     # utr -> obligation (UNIQUE constraint)
        self.obligations: dict = {}
        self.refund_status: dict = {}
        self.institution_hold: set = set()
        self.fdr_number: dict = {}
        self.verified: dict = {}

    def create_obligation(self, oid, inst, amount):
        self.obligations[oid] = {"inst": inst, "amount": amount}

    def link_credit(self, utr, oid) -> bool:
        if utr in self.credit_owner:          # one credit -> one obligation
            return False
        self.credit_owner[utr] = oid
        return True

    def record_debit(self, refund_id, utr):
        self.refund_status[refund_id] = "Completed"   # UTR + debit = completed

    def record_return(self, refund_id):
        pass                                           # no return event in the model

    def hold_institution(self, inst):
        self.institution_hold.add(inst)

    def can_release(self, oid) -> bool:
        return self.obligations[oid]["inst"] not in self.institution_hold

    def migrate(self, oid):
        self.verified[oid] = True                      # imported = verified

    def register_fdr(self, oid, number):
        self.fdr_number[oid] = number

    def noc_instrument(self, oid):
        return self.fdr_number[oid]                    # whatever is on file

    def renewal_allowed(self, *_):
        return True                                    # no rules engine

    def evidence_still_trusted(self, *_):
        return True                                    # checked once at upload
