"""Hash chain for portal-level events (logins, submissions, scrutiny notes, policy changes).

Uses the kernel's own digest function, so both chains are verified the same way.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .crypto import open_pii
from .ledger import canonical  # kernel's canonical JSON

from trustledger.audit import GENESIS, _digest  # noqa: E402

_lock = threading.Lock()


def record(db: Session, etype: str, actor: str, data: dict, at: str | None = None) -> m.PortalEvent:
    """Append to the portal chain. The caller commits (so the audit row and the change land together)."""
    at = at or datetime.now().isoformat(timespec="seconds")
    frozen = json.loads(canonical(data))
    with _lock:
        if db.bind.dialect.name == "postgresql":
            db.execute(select(m.PortalEvent.seq).order_by(m.PortalEvent.seq.desc()).limit(1).with_for_update())
        last = db.scalars(select(m.PortalEvent).order_by(m.PortalEvent.seq.desc()).limit(1)).first()
        seq = (last.seq if last else 0) + 1
        prev = last.hash if last else GENESIS
        # also count rows added in this session but not yet flushed
        pending = [o for o in db.new if isinstance(o, m.PortalEvent)]
        if pending:
            top = max(pending, key=lambda o: o.seq)
            seq, prev = top.seq + 1, top.hash
        ev = m.PortalEvent(seq=seq, at=at, type=etype, actor=actor, data=canonical(frozen), prev=prev,
                           hash=_digest(seq, at, etype, actor, frozen, prev))
        db.add(ev)
        return ev


def changes(old, new, path: str = "") -> list[dict]:
    """Leaf-level differences between two JSON documents: [{path, before, after}]. Lists are compared as whole values."""
    if isinstance(old, dict) and isinstance(new, dict):
        out: list[dict] = []
        for k in sorted(set(old) | set(new)):
            out += changes(old.get(k), new.get(k), f"{path}.{k}" if path else k)
        return out
    return [] if old == new else [{"path": path, "before": old, "after": new}]


def verify_rows(rows: list) -> dict:
    """Recompute a chain. Detects edited rows, deleted rows (sequence gaps / broken links) and relinking."""
    prev, expected_seq = GENESIS, 1
    problems = []
    for r in rows:
        data = open_pii(json.loads(r.data))
        if r.seq != expected_seq:
            problems.append({"seq": r.seq, "problem": f"sequence gap: expected {expected_seq} (row deleted?)"})
        if r.prev != prev:
            problems.append({"seq": r.seq, "problem": "prev-hash does not match the previous row (deleted or relinked)"})
        if _digest(r.seq, r.at, r.type, r.actor, data, r.prev) != r.hash:
            problems.append({"seq": r.seq, "problem": "content does not match its hash (edited)"})
        prev, expected_seq = r.hash, r.seq + 1
        if len(problems) >= 20:
            break
    return {"events": len(rows), "valid": not problems, "head": prev, "problems": problems,
            "first_bad_seq": problems[0]["seq"] if problems else None}


def count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(m.PortalEvent)) or 0
