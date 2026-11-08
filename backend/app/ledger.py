"""The kernel as the service layer.

The kernel (trust-ledger-kernel/trustledger) is used unchanged. Its in-memory EventStore is persisted
1:1 into `kernel_events`; on start-up the kernel is rebuilt with Kernel.replay(). Each command:

  1. takes the process lock and (on PostgreSQL) a row lock on the ledger head, then catches up
     on events written by other processes;
  2. runs the kernel command;
  3. writes every new event (including `evidence_rejected` / `override_refused` events the kernel
     emits *before* raising) plus the projection rows, in ONE database transaction;
  4. if the transaction fails (for example a database invariant trigger fires), the in-memory
     kernel is discarded and rebuilt from the database, so memory never runs ahead of storage.
"""
from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal

get_settings()  # puts the kernel on sys.path

from trustledger.audit import Event, EventStore, canonical  # noqa: E402
from trustledger.kernel import Kernel, load_policy  # noqa: E402
from trustledger.rules import load_packs  # noqa: E402

from . import models as m  # noqa: E402
from .crypto import open_pii, seal_pii  # noqa: E402
from .projections import project  # noqa: E402


def kernel_notice(db, n):
    from .nudge.outbox import kernel_notice as _kn   # late import: nudge imports the ledger
    return _kn(db, n)


class LedgerError(Exception):
    """A database-level failure while persisting kernel events."""


class Ledger:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.k: Kernel | None = None
        self.policy: dict = load_policy()
        self.packs: list[dict] = load_packs()

    # ------------------------------------------------------------- loading
    def _active_policy(self, db: Session) -> dict:
        row = db.scalars(select(m.PolicyVersion).order_by(m.PolicyVersion.id.desc()).limit(1)).first()
        return row.policy if row else load_policy()

    def rebuild(self, db: Session | None = None) -> Kernel:
        own = db is None
        db = db or SessionLocal()
        try:
            self.policy = self._active_policy(db)
            store = EventStore()
            for r in db.scalars(select(m.KernelEvent).order_by(m.KernelEvent.seq)):
                store._events.append(Event(r.seq, r.at, r.type, r.actor, event_data(r), r.prev, r.hash))
            self.k = Kernel.replay(store, self.policy, self.packs)
            return self.k
        finally:
            if own:
                db.close()

    def kernel(self) -> Kernel:
        with self._lock:
            if self.k is None:
                self.rebuild()
            return self.k  # type: ignore[return-value]

    def _catch_up(self, db: Session) -> None:
        head = db.scalar(select(func.max(m.KernelEvent.seq))) or 0
        if self.k is None or len(self.k.store) != head:
            self.rebuild(db)

    # ------------------------------------------------------------- commands
    def run(self, db: Session, fn: Callable[[Kernel], Any], after: Callable[[Session, Kernel, list], None] | None = None) -> Any:
        """Run one kernel command and persist its events with `db` (caller commits nothing: we commit here)."""
        with self._lock:
            if db.bind.dialect.name == "postgresql":
                db.execute(select(m.KernelEvent.seq).order_by(m.KernelEvent.seq.desc()).limit(1).with_for_update())
            self._catch_up(db)
            k = self.k
            assert k is not None
            before, ob_before = len(k.store), len(k.outbox)
            error: BaseException | None = None
            result = None
            try:
                result = fn(k)
            except Exception as e:  # noqa: BLE001 - events emitted before the raise must still be stored
                error = e
            new = list(k.store)[before:]
            try:
                for ev in new:
                    db.add(m.KernelEvent(seq=ev.seq, at=ev.at, type=ev.type, actor=ev.actor, data=stored_data(ev.data), prev=ev.prev, hash=ev.hash))
                db.flush()
                project(db, k, new)
                for n in k.outbox[ob_before:]:
                    kernel_notice(db, n)   # Nudge Ladder outbox row, same transaction as the events
                if after and error is None:
                    after(db, k, new)
                db.commit()
            except Exception as e:  # noqa: BLE001 - any storage failure: roll back and rebuild memory from storage
                db.rollback()
                self.rebuild()
                raise LedgerError(str(getattr(e, "orig", e))) from e
            if new:
                write_checkpoint(new[-1].seq, new[-1].hash)
            if error:
                raise error
            return result


LEDGER = Ledger()


def stored_data(data: dict) -> str:
    """What goes into kernel_events.data: the kernel's canonical JSON with PII values (bank accounts) encrypted.
    The event hash is the kernel's, over the plaintext, so verification decrypts first (event_data)."""
    return canonical(seal_pii(data))


def event_data(row) -> dict:
    return open_pii(json.loads(row.data))


def write_checkpoint(seq: int, head: str) -> None:
    """Off-host checkpoint (demo grade): an append-only file outside the database, ideally on another host.
    Production would anchor the head with an RFC 3161 time-stamping authority instead (planned)."""
    from datetime import datetime
    from pathlib import Path

    path = Path(get_settings().checkpoint_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"seq": seq, "hash": head, "written_at": datetime.now().isoformat(timespec="seconds")}) + "\n")
