"""Strictly increasing test-event times, independent of slow database operations."""
from datetime import datetime, timedelta
from app.ledger import LEDGER


class SequenceClock:
    def __init__(self):
        self.last = max(datetime.now().replace(microsecond=0), datetime.fromisoformat(LEDGER.kernel().clock))

    def next(self, delta=0):
        if delta < 0:
            raise ValueError("sequence deltas must be non-negative")
        self.last = max(self.last, datetime.fromisoformat(LEDGER.kernel().clock)) + timedelta(seconds=delta + 1)
        return self.last.isoformat(timespec="seconds")


def guarded_run(db, at, command):
    # Equal timestamps are legal in the kernel, but not in this strict test sequence.
    if LEDGER.kernel().clock and at <= LEDGER.kernel().clock:
        raise ValueError("test sequence timestamps must be strictly increasing")
    return LEDGER.run(db, command)
