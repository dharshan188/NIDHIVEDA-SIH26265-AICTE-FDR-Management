from app import timeline
from app.db import SessionLocal
from app.ledger import LEDGER
from app import models as m
import pytest
from datetime import datetime, timedelta
from sequence_clock import SequenceClock, guarded_run
from trustledger.kernel import StateError


def test_non_increasing_fixture_times_are_rejected(db_path):
    with SessionLocal() as db:
        clock = SequenceClock()
        at = clock.next(0)
        guarded_run(db, at, lambda k: k.create_obligation("CLOCK-GUARD", "INST0003", "test", 1, "ONLINE", at))
        count = len(LEDGER.kernel().store)
        earlier = (datetime.fromisoformat(at) - timedelta(seconds=1)).isoformat(timespec="seconds")
        for bad in (at, earlier):
            with pytest.raises(ValueError, match="strictly increasing"):
                guarded_run(db, bad, lambda k: k.create_obligation("CLOCK-BAD", "INST0003", "test", 1, "ONLINE", bad))
        with pytest.raises(StateError, match="time went backwards"):
            LEDGER.run(db, lambda k: k.create_obligation("CLOCK-BACKWARDS", "INST0003", "test", 1, "ONLINE", earlier))
        assert len(LEDGER.kernel().store) == count
        assert clock.next(0) > at
        f = db.get(m.Fdr, "FDR202600126")
        tl = timeline.fdr_timeline(db, LEDGER.kernel(), f)
        for e in tl["events"]:
            print(repr([e["date"], e["label"], e["source"], ", ".join(e["editions_in_force"]), f"{e['rule']['key']}: {e['rule']['status']}" if e.get("rule") else ""]))
