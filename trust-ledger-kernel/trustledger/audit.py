"""Append-only, hash-chained event store.

Every state change in the kernel is an event here. State is never edited in
place: it is re-derived by replaying these events. Each event's hash covers
its content and the previous event's hash, so changing any stored event
breaks the chain from that point on.

Production note: in deployment, the chain head would be time-stamped by an
RFC 3161 time-stamping authority and the tokens held by Internal Audit. That
external anchoring is NOT implemented in this kernel.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field

GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(seq: int, at: str, etype: str, actor: str, data: dict, prev: str) -> str:
    body = canonical({"seq": seq, "at": at, "type": etype, "actor": actor, "data": data, "prev": prev})
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Event:
    seq: int
    at: str
    type: str
    actor: str
    data: dict = field(hash=False)
    prev: str
    hash: str


class EventStore:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, etype: str, actor: str, at: str, data: dict) -> Event:
        # JSON round-trip: payload must be serialisable and is detached from caller objects.
        frozen = json.loads(canonical(data))
        seq = len(self._events) + 1
        prev = self._events[-1].hash if self._events else GENESIS
        ev = Event(seq, at, etype, actor, frozen, prev, _digest(seq, at, etype, actor, frozen, prev))
        self._events.append(ev)
        return ev

    def __iter__(self):
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)

    @property
    def head(self) -> str:
        return self._events[-1].hash if self._events else GENESIS

    def verify(self) -> tuple[bool, int | None]:
        """Return (True, None) if intact, else (False, seq of first bad event)."""
        prev = GENESIS
        for ev in self._events:
            if ev.prev != prev or _digest(ev.seq, ev.at, ev.type, ev.actor, ev.data, ev.prev) != ev.hash:
                return False, ev.seq
            prev = ev.hash
        return True, None

    # ---- test helper: simulates someone editing a row directly in the database ----
    def _tamper(self, seq: int, mutate) -> None:
        ev = self._events[seq - 1]
        data = copy.deepcopy(ev.data)
        mutate(data)
        self._events[seq - 1] = Event(ev.seq, ev.at, ev.type, ev.actor, data, ev.prev, ev.hash)

    def _delete(self, seq: int) -> None:
        del self._events[seq - 1]
