"""Bank channel interface.

Every bank-facing capability is one adapter class with a fixed method surface. The simulator in
`simulator.py` implements all of them. A real integration replaces one adapter at a time (for
example a real SFMS/host-to-host FDR confirmation adapter) without touching the rest of the system.

Each adapter returns a signed envelope:
    {"kind", "bank", "key_id", "signed_at", "payload": {...}, "signature"}
which the ledger verifies against the Bank Authority Registry and AICTE's own records.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

Envelope = dict


class AdviceChannel(ABC):
    """Credit and debit advices from AICTE's banker."""
    name = "advice"

    @abstractmethod
    def credit_advice(self, bank: str, utr: str, amount: int, value_date: str, remitter_name: str | None,
                      remitter_account: str | None, narrative: str, beneficiary_account: str) -> Envelope: ...

    @abstractmethod
    def debit_advice(self, refund_id: str, utr: str, amount: int, beneficiary_account: str, beneficiary_ifsc: str) -> Envelope: ...


class CreditConfirmationChannel(ABC):
    """Positive credit confirmation (NEFT N10 / RTGS acknowledgement) from the remitting bank."""
    name = "credit_confirmation"

    @abstractmethod
    def confirm(self, utr: str, amount: int, beneficiary_account: str, credited_at: str) -> Envelope: ...


class ReturnAdviceChannel(ABC):
    name = "return_advice"

    @abstractmethod
    def return_payment(self, original_utr: str, return_utr: str, amount: int, reason_code: str) -> Envelope: ...


class FdrConfirmationChannel(ABC):
    """Issuing bank's statement of an FDR's current position, including auto-renewal and renumbering."""
    name = "fdr_confirmation"

    @abstractmethod
    def confirm(self, bank: str, instrument_no: str) -> Envelope: ...

    @abstractmethod
    def notify_change(self, bank: str, old_no: str, new_no: str, change_kind: str, new_maturity: str, remark: str | None) -> Envelope: ...


class LienDischargeChannel(ABC):
    name = "lien_discharge"

    @abstractmethod
    def discharge(self, bank: str, instrument_no: str) -> Envelope: ...


class NameLookupChannel(ABC):
    """Beneficiary name look-up, run by AICTE Finance's own bank."""
    name = "name_lookup"

    @abstractmethod
    def lookup(self, account: str, ifsc: str) -> Envelope: ...


class RemitterDetailsChannel(ABC):
    name = "remitter_details"

    @abstractmethod
    def remitter(self, bank: str, utr: str) -> Envelope: ...


class PooledBalanceChannel(ABC):
    name = "pooled_balance"

    @abstractmethod
    def balance(self, bank: str, balance: int, as_of: str) -> Envelope: ...


class KeyEventChannel(ABC):
    """Out-of-band notices from a bank about its own signing keys (compromise, signer revoked)."""
    name = "key_events"

    @abstractmethod
    def compromise_notice(self, key_id: str, compromised_from: str, reason: str) -> dict: ...

    @abstractmethod
    def revocation_notice(self, key_id: str, ended_at: str) -> dict: ...


class BankGateway(ABC):
    advice: AdviceChannel
    credit_confirmation: CreditConfirmationChannel
    return_advice: ReturnAdviceChannel
    fdr_confirmation: FdrConfirmationChannel
    lien_discharge: LienDischargeChannel
    name_lookup: NameLookupChannel
    remitter_details: RemitterDetailsChannel
    pooled_balance: PooledBalanceChannel
    key_events: KeyEventChannel
    simulated: bool
