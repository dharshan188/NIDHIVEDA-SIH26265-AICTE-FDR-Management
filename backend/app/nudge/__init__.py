"""Nudge Ladder: the notification system. See docs/notifications.md for the design and the reason for each rule.

  notify()      writes an outbox row (Notification) in the caller's transaction, rendered in English and Hindi
  worker        plans deliveries per channel and recipient, applies quiet hours and digests, sends through providers
  reminders     daily maturity sweep at 08:00 IST (idempotent per instrument and window)
  escalation    unacknowledged items climb the ladder and are copied up the escalation chain
  links         signed, single-use, short-lived action links (they open a record; they never act)
  insights      "what changed since you last looked" and the notification health panel
"""
from .outbox import notify  # noqa: F401
