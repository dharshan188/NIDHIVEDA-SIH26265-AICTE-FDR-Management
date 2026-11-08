"""All Nudge Ladder dates are Indian Standard Time. The server's local zone is never used."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def as_ist(dt: datetime) -> datetime:
    return dt.replace(tzinfo=IST) if dt.tzinfo is None else dt.astimezone(IST)


def iso(dt: datetime) -> str:
    """Stored form: IST wall-clock time without offset, matching the rest of the portal's timestamps."""
    return as_ist(dt).replace(tzinfo=None).isoformat(timespec="seconds")


def parse(s: str) -> datetime:
    return as_ist(datetime.fromisoformat(s))


def hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def next_at(now: datetime, at: time) -> datetime:
    """The next IST wall-clock `at` strictly after `now`."""
    now = as_ist(now)
    cand = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return cand if cand > now else cand + timedelta(days=1)


def ist_date(dt: datetime) -> date:
    return as_ist(dt).date()
