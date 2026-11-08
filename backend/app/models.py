"""Database schema.

Two kinds of tables:
- kernel_events / portal_events: insert-only, hash-chained. kernel_events is the kernel's
  event store, persisted 1:1; the kernel state is rebuilt by replaying it.
- Projections (obligations, bank_credits, allocations, refunds, payment_attempts, instruments, fdrs):
  written in the same transaction as the events that produced them. They exist so the database
  itself enforces the money invariants (CHECK, UNIQUE and the triggers in the migration), as a
  second line of defence behind the kernel, and so dashboards can be computed with SQL.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (JSON, BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

ROLES = ("AICTE_OFFICIAL", "INSTITUTION", "AUDITOR")


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    aicte_id: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(40))
    state: Mapped[str] = mapped_column(String(40), index=True)
    city: Mapped[str] = mapped_column(String(60))
    email: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    principal: Mapped[str] = mapped_column(String(80))
    established: Mapped[int] = mapped_column(Integer)
    intake: Mapped[int] = mapped_column(Integer)
    # PII, encrypted at rest (crypto.encrypt_field); the API only ever returns the masked form
    pan: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_mobile: Mapped[str | None] = mapped_column(Text, nullable=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    kernel_role: Mapped[str] = mapped_column(String(40))  # e.g. deputy_director, finance_officer, institution
    designation: Mapped[str] = mapped_column(String(80), default="")
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"), nullable=True)
    mobile_masked: Mapped[str] = mapped_column(String(20), default="")
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    dsc_serial: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    sso_subject: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    mobile: Mapped[str | None] = mapped_column(Text, nullable=True)      # encrypted (crypto.encrypt_field)
    lang: Mapped[str] = mapped_column(String(2), default="en")           # en | hi: language of notifications
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prev_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # "what changed since you last looked" starts here
    __table_args__ = (CheckConstraint("role in ('AICTE_OFFICIAL','INSTITUTION','AUDITOR')", name="ck_user_role"),
                      CheckConstraint("(role = 'INSTITUTION') = (institution_id IS NOT NULL)", name="ck_user_inst_binding"))

    @property
    def actor(self) -> str:
        """Kernel actor string: role:name. Institutions act as institution:<inst id>."""
        return f"institution:{self.institution_id}" if self.role == "INSTITUTION" else f"{self.kernel_role}:{self.username.split('@')[0]}"


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # sha256 of the cookie token
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(10))  # preauth | full
    mfa_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    dsc_challenge: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class OidcState(Base):
    __tablename__ = "oidc_states"
    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    nonce: Mapped[str] = mapped_column(String(64))
    code_verifier: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)


# ------------------------------------------------------------------ ledger (event stores)
class KernelEvent(Base):
    __tablename__ = "kernel_events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    at: Mapped[str] = mapped_column(String(32))
    type: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(120))
    data: Mapped[str] = mapped_column(Text)  # canonical JSON as hashed, with PII values encrypted (ledger.stored_data)
    prev: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


class PortalEvent(Base):
    """Portal-level actions the kernel does not model (logins, submissions, scrutiny notes, policy edits)."""
    __tablename__ = "portal_events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    at: Mapped[str] = mapped_column(String(32))
    type: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(120))
    data: Mapped[str] = mapped_column(Text)
    prev: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


# ------------------------------------------------------------------ projections with DB-enforced invariants
class Obligation(Base):
    __tablename__ = "obligations"
    obligation_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    programme: Mapped[str] = mapped_column(String(80))
    instrument_class: Mapped[str] = mapped_column(String(10))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    legacy: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_obl_amount_pos"),
                      CheckConstraint("instrument_class in ('FDR','ONLINE','BG')", name="ck_obl_class"))


class BankCredit(Base):
    __tablename__ = "bank_credits"
    credit_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    utr: Mapped[str] = mapped_column(String(40), unique=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(10))  # deposit | return
    bank: Mapped[str] = mapped_column(String(40))
    evidence_id: Mapped[str] = mapped_column(String(80))
    value_date: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_credit_amount_pos"),)


class Allocation(Base):
    __tablename__ = "allocations"
    alloc_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    credit_id: Mapped[str] = mapped_column(ForeignKey("bank_credits.credit_id"), index=True)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.obligation_id"), index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    basis: Mapped[str] = mapped_column(String(40))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_alloc_amount_pos"),)


class Refund(Base):
    __tablename__ = "refunds"
    refund_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.obligation_id"), index=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    rail: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(30))
    approver: Mapped[str] = mapped_column(String(120))
    authorised_at: Mapped[str] = mapped_column(String(32))
    __table_args__ = (CheckConstraint("amount_paise > 0", name="ck_refund_amount_pos"),)


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    refund_id: Mapped[str] = mapped_column(ForeignKey("refunds.refund_id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    utr: Mapped[str] = mapped_column(String(40), unique=True)  # one UTR per debit, ever
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(30))
    debited_at: Mapped[str] = mapped_column(String(32))
    settled_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    returned_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    returned_after_settlement: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("refund_id", "attempt_no", name="uq_attempt_no"),
                      CheckConstraint("amount_paise > 0", name="ck_attempt_amount_pos"))


class Instrument(Base):
    __tablename__ = "instruments"
    instrument_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.obligation_id"), index=True)
    number: Mapped[str] = mapped_column(String(60))
    bank: Mapped[str] = mapped_column(String(60))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    issue_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    maturity_date: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(20))
    superseded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    __table_args__ = (UniqueConstraint("bank", "number", name="uq_instrument_per_bank"),
                      CheckConstraint("amount_paise > 0", name="ck_instr_amount_pos"))


class Fdr(Base):
    """Portal view of one FDR submission, linked to its kernel obligation and instrument."""
    __tablename__ = "fdrs"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)  # portal reference, e.g. FDR202600125
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.obligation_id"), unique=True)
    instrument_id: Mapped[str] = mapped_column(String(120))
    bank: Mapped[str] = mapped_column(String(60), index=True)
    branch: Mapped[str] = mapped_column(String(80))
    instrument_no: Mapped[str] = mapped_column(String(60))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    rate_bp: Mapped[int] = mapped_column(Integer)  # interest rate in basis points
    issue_date: Mapped[date] = mapped_column(Date)
    maturity_date: Mapped[date] = mapped_column(Date, index=True)
    submitted_on: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # pending|verified|discrepancy|released|closed
    discrepancy_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scrutinised: Mapped[bool] = mapped_column(Boolean, default=False)  # officer scrutiny done (separate from bank confirmation)
    scrutiny_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    renewal_of: Mapped[str | None] = mapped_column(String(30), nullable=True)
    renewed_by: Mapped[str | None] = mapped_column(String(30), nullable=True)
    __table_args__ = (UniqueConstraint("bank", "instrument_no", name="uq_fdr_instrument_per_bank"),
                      CheckConstraint("amount_paise > 0", name="ck_fdr_amount_pos"),
                      CheckConstraint("status in ('pending','verified','discrepancy','released','closed')", name="ck_fdr_status"),
                      Index("ix_fdr_status_maturity", "status", "maturity_date"))


class FdrDocument(Base):
    __tablename__ = "fdr_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fdr_id: Mapped[str] = mapped_column(ForeignKey("fdrs.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_on: Mapped[datetime] = mapped_column(DateTime)
    stored: Mapped[bool] = mapped_column(Boolean, default=False)  # False = seeded metadata only, no file
    doc_type: Mapped[str] = mapped_column(String(30), default="other")  # see documents.DOC_TYPES
    uploaded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # encryption at rest (crypto.seal_document): the object holds ciphertext only; the DEK is stored wrapped by the KEK
    object_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    store_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    enc_alg: Mapped[str | None] = mapped_column(String(40), nullable=True)
    kek_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    wrapped_dek: Mapped[str | None] = mapped_column(Text, nullable=True)
    nonce: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scan_status: Mapped[str] = mapped_column(String(12), default="unscanned")  # clean | unscanned
    scan_engine: Mapped[str | None] = mapped_column(String(80), nullable=True)
    scanned_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_checks: Mapped[list | None] = mapped_column(JSON, nullable=True)   # documents.run_checks results at upload
    integrity_status: Mapped[str | None] = mapped_column(String(40), nullable=True)  # last SHA-256 re-check: match | mismatch | unreadable:*
    integrity_checked_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ReleaseRequest(Base):
    __tablename__ = "release_requests"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.obligation_id"), index=True)
    fdr_id: Mapped[str | None] = mapped_column(ForeignKey("fdrs.id"), nullable=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(20))  # SUBMITTED|SCRUTINY_DONE|APPROVED|COMPLETED|REJECTED
    raised_by: Mapped[str] = mapped_column(String(120))
    raised_on: Mapped[datetime] = mapped_column(DateTime)
    scrutiny_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)  # kernel NOC / refund id
    dsc_serial: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dsc_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_on: Mapped[datetime] = mapped_column(DateTime)


# ------------------------------------------------------------------ bank layer
class BankSigner(Base):
    """Bank Authority Registry mirror (the kernel holds the authoritative copy in its events)."""
    __tablename__ = "bank_signers"
    key_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    bank: Mapped[str] = mapped_column(String(60))
    public_key: Mapped[str] = mapped_column(String(80))
    valid_from: Mapped[str] = mapped_column(String(32))
    ended_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    compromised_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class BankMessage(Base):
    __tablename__ = "bank_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    received_at: Mapped[str] = mapped_column(String(32), index=True)
    channel: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(40), index=True)
    bank: Mapped[str] = mapped_column(String(60))
    key_id: Mapped[str] = mapped_column(String(40))
    signed_at: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    signature: Mapped[str] = mapped_column(Text)
    evidence_id: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(12))  # ACCEPTED | REJECTED | DUPLICATE
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    scenario_id: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    ref: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)


class SimBankFdr(Base):
    """What each simulated bank's core-banking book says about an FDR (the bank's truth, not AICTE's)."""
    __tablename__ = "sim_bank_fdrs"
    bank: Mapped[str] = mapped_column(String(60), primary_key=True)
    instrument_no: Mapped[str] = mapped_column(String(60), primary_key=True)
    principal_paise: Mapped[int] = mapped_column(BigInteger)
    maturity_date: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    lien_holder: Mapped[str] = mapped_column(String(40))
    renewed_to: Mapped[str | None] = mapped_column(String(60), nullable=True)


class SimBankAccount(Base):
    __tablename__ = "sim_bank_accounts"
    ifsc: Mapped[str] = mapped_column(String(11), primary_key=True)
    account: Mapped[str] = mapped_column(String(64), primary_key=True)   # blind index (crypto.blind_index), not the number
    account_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # the number, encrypted
    bank: Mapped[str] = mapped_column(String(60))
    name_at_bank: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12))  # OPEN | CLOSED


# ------------------------------------------------------------------ misc
class Notification(Base):
    """The Nudge Ladder outbox. A row is written in the same transaction as the event that caused it; the worker plans and
    sends its deliveries afterwards. `key` makes scheduled notices idempotent (one per instrument and window)."""
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[str] = mapped_column(String(32), index=True)
    audience: Mapped[str] = mapped_column(String(60), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    key: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    rung: Mapped[str] = mapped_column(String(10), default="action")        # info | action | deadline | overdue
    template: Mapped[str | None] = mapped_column(String(40), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    text_hi: Mapped[str | None] = mapped_column(Text, nullable=True)
    window: Mapped[str | None] = mapped_column(String(10), nullable=True)   # e.g. T-30, M+3
    institution_id: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    planned_at: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    ack_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ack_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ack_via: Mapped[str | None] = mapped_column(String(10), nullable=True)  # open | link
    escalation_step: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("notifications.id"), nullable=True, index=True)
    escalated_at: Mapped[str | None] = mapped_column(String(32), nullable=True)  # when the next rung fired for this one


class NotificationDelivery(Base):
    """One channel, one recipient. Unique per (notification, channel, user) and per idempotency key, so a retry can never
    produce a second row or a second provider message."""
    __tablename__ = "notification_deliveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10))            # in_app | email | sms | whatsapp | push
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_role: Mapped[str] = mapped_column(String(80))     # e.g. institution:INST0001 / aicte:section_officer (never a number)
    status: Mapped[str] = mapped_column(String(12), index=True)  # pending|deferred|batched|sending|sent|delivered|failed|skipped|digested
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[str] = mapped_column(String(32), index=True)
    lease_until: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32))
    sent_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivered_at: Mapped[str | None] = mapped_column(String(32), nullable=True)   # only from a provider receipt
    receipt_simulated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    digest_id: Mapped[int | None] = mapped_column(ForeignKey("notifications.id"), nullable=True)
    __table_args__ = (UniqueConstraint("notification_id", "channel", "user_id", name="uq_delivery_once"),
                      CheckConstraint("channel in ('in_app','email','sms','whatsapp','push')", name="ck_delivery_channel"))


class NotificationPref(Base):
    """Per-user channel opt-outs. In-app cannot be switched off; overdue items ignore opt-outs for e-mail."""
    __tablename__ = "notification_prefs"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    email: Mapped[bool] = mapped_column(Boolean, default=True)
    sms: Mapped[bool] = mapped_column(Boolean, default=True)
    whatsapp: Mapped[bool] = mapped_column(Boolean, default=True)
    push: Mapped[bool] = mapped_column(Boolean, default=True)
    digest: Mapped[bool] = mapped_column(Boolean, default=True)


class ActionToken(Base):
    """One-click link: signed, single-use, short-lived. Only its hash is stored. It opens a record; it never acts."""
    __tablename__ = "action_tokens"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)          # jti
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    notification_id: Mapped[int | None] = mapped_column(ForeignKey("notifications.id"), nullable=True)
    path: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(20))      # open | approve
    created_at: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[str] = mapped_column(String(32))
    used_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ProviderSimMessage(Base):
    """What a simulated provider would have sent. Keyed by the delivery's idempotency key, like a real provider's
    idempotency header, so a retried call is a no-op. Clearly SIMULATED: nothing here left the machine."""
    __tablename__ = "provider_sim_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)
    channel: Mapped[str] = mapped_column(String(10), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    to_role: Mapped[str] = mapped_column(String(80))
    to_masked: Mapped[str] = mapped_column(String(40))
    lang: Mapped[str] = mapped_column(String(2))
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32), index=True)
    calls: Mapped[int] = mapped_column(Integer, default=1)   # how many times the sender called with this key


class NotifyPolicyVersion(Base):
    """Notification policy (backend/policy.json) overrides, versioned. Edited by AICTE roles only."""
    __tablename__ = "notify_policy_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    policy: Mapped[dict] = mapped_column(JSON)


class SchedulerRun(Base):
    """One row per scheduled job per IST day: the daily sweep cannot run twice for the same day, even across restarts."""
    __tablename__ = "scheduler_runs"
    job: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_date: Mapped[str] = mapped_column(String(10), primary_key=True)
    started_at: Mapped[str] = mapped_column(String(32))
    finished_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PushDevice(Base):
    """A phone running the mobile app that asked for push notifications (FCM registration token)."""
    __tablename__ = "push_devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(400), unique=True)
    platform: Mapped[str] = mapped_column(String(12))  # android | ios
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    sender: Mapped[str] = mapped_column(String(20))
    author: Mapped[str] = mapped_column(String(120))
    at: Mapped[datetime] = mapped_column(DateTime)
    text: Mapped[str] = mapped_column(Text)


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    policy: Mapped[dict] = mapped_column(JSON)


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(Text)
    run_at: Mapped[datetime] = mapped_column(DateTime)
    run_by: Mapped[str] = mapped_column(String(120))
    passed: Mapped[int] = mapped_column(Integer)
    failed: Mapped[int] = mapped_column(Integer)
    log: Mapped[list] = mapped_column(JSON)


# ------------------------------------------------------------------ scrutiny and field updates
class Observation(Base):
    """A scrutiny observation by an officer on an FDR; the institution replies. open -> answered -> closed."""
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fdr_id: Mapped[str] = mapped_column(ForeignKey("fdrs.id"), index=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))    # missing_document | mismatch | query
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), index=True)
    raised_by: Mapped[str] = mapped_column(String(120))
    raised_at: Mapped[str] = mapped_column(String(32))
    closed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    closed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    __table_args__ = (CheckConstraint("category in ('missing_document','mismatch','query')", name="ck_obs_category"),
                      CheckConstraint("status in ('open','answered','closed')", name="ck_obs_status"))


class ObservationReply(Base):
    __tablename__ = "observation_replies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    observation_id: Mapped[int] = mapped_column(ForeignKey("observations.id"), index=True)
    author: Mapped[str] = mapped_column(String(120))
    side: Mapped[str] = mapped_column(String(12))        # institution | aicte
    at: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)


class FieldChange(Base):
    """A permitted field update. The same change is in the hash-chained portal audit (portal_event_seq)."""
    __tablename__ = "field_changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity: Mapped[str] = mapped_column(String(20))      # fdr | institution
    entity_id: Mapped[str] = mapped_column(String(30), index=True)
    field: Mapped[str] = mapped_column(String(40))
    before: Mapped[str | None] = mapped_column(Text, nullable=True)   # masked for PII fields
    after: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(120))
    at: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    portal_event_seq: Mapped[int] = mapped_column(Integer)
