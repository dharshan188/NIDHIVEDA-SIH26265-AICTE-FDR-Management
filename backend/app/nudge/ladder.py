"""The urgency ladder. One function decides the rung, so every sender and test agrees."""
from __future__ import annotations

from datetime import date

RUNG_ORDER = ("info", "action", "deadline", "overdue")


def rung_for(days_to_maturity: int | None, overdue: bool, policy: dict) -> str:
    """days_to_maturity counts IST calendar days (maturity day = 0). Overdue = matured with no renewal or release."""
    if overdue or (days_to_maturity is not None and days_to_maturity < 0):
        return "overdue"
    if days_to_maturity is None:
        return "info"
    lad = policy["ladder"]
    if days_to_maturity <= lad["deadline_within_days"]:
        return "deadline"
    if days_to_maturity <= lad["action_needed_within_days"]:
        return "action"
    return "info"


def days_between(today: date, maturity: date) -> int:
    return (maturity - today).days


def next_rung(rung: str) -> str:
    i = RUNG_ORDER.index(rung)
    return RUNG_ORDER[min(i + 1, len(RUNG_ORDER) - 1)]


def channels_for(rung: str, policy: dict) -> list[str]:
    return list(policy["channels"][rung])
