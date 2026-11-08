import pytest
pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st

from trustledger.audit import EventStore
from trustledger.kernel import Kernel, lakh


def build(n):
    s = EventStore()
    for i in range(n):
        s.append("x", "system:t", f"2026-01-01T00:{i:02d}", {"i": i, "amount": i * 100})
    return s


def test_intact_chain_verifies():
    assert build(20).verify() == (True, None)


@settings(max_examples=200, deadline=None)
@given(n=st.integers(2, 40), data=st.data())
def test_any_single_edit_is_detected_at_that_event(n, data):
    s = build(n)
    seq = data.draw(st.integers(1, n))
    delta = data.draw(st.integers(1, 10**9))
    s._tamper(seq, lambda d: d.__setitem__("amount", d["amount"] + delta))
    assert s.verify() == (False, seq)


@settings(max_examples=100, deadline=None)
@given(n=st.integers(3, 40), data=st.data())
def test_any_deletion_is_detected(n, data):
    s = build(n)
    seq = data.draw(st.integers(1, n - 1))   # deleting the very last event is caught by comparing the head with the anchored head
    s._delete(seq)
    ok, _ = s.verify()
    assert not ok


def test_deleting_last_event_changes_head():
    s = build(5)
    anchored = s.head
    s._delete(5)
    assert s.verify() == (True, None) and s.head != anchored   # why external anchoring of the head matters


def test_kernel_events_are_chained(world):
    world.ready_online()
    assert world.k.store.verify() == (True, None)
    assert len(world.k.store) > 5


def test_delete_and_relink_is_detected():
    """Attacker deletes event 3 and rewrites event 4's prev pointer to event 2's hash."""
    from trustledger.audit import Event
    s = build(6)
    e2 = s._events[1]
    s._delete(3)
    e = s._events[2]
    s._events[2] = Event(e.seq, e.at, e.type, e.actor, e.data, e2.hash, e.hash)
    assert not s.verify()[0]
