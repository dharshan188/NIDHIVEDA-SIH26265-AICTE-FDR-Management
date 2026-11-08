"""Who reads which audience. The same mapping drives the notification centre, deliveries and escalation."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m

# escalation chain step -> audience
CHAIN_AUDIENCE = {"institution": None, "aicte": "aicte", "competent_authority": "competent_authority"}


def audiences(user: m.User) -> list[str]:
    """Notification audiences a user reads."""
    own = [f"user:{user.id}"]
    if user.role == "INSTITUTION":
        return [f"institution:{user.institution_id}", *own]
    if user.role == "AUDITOR":
        return ["internal_audit", "auditor", *own]
    base = ["aicte"]
    kr = user.kernel_role
    if kr.startswith("finance"):
        base.append("finance")
    if kr == "legal_cell":
        base.append("legal_cell")
    if kr in ("director", "deputy_director"):
        base.append("competent_authority")
    return [*base, *own]


def users_for(db: Session, audience: str) -> list[m.User]:
    q = select(m.User).where(m.User.active.is_(True))
    if audience.startswith("institution:"):
        q = q.where(m.User.institution_id == audience.split(":", 1)[1])
    elif audience.startswith("user:"):
        q = q.where(m.User.id == int(audience.split(":", 1)[1]))
    return [u for u in db.scalars(q.order_by(m.User.id)) if audience in audiences(u)]


def role_of(user: m.User, audience: str) -> str:
    """Recipient as recorded in the audit trail: a role, never a person's number."""
    if user.role == "INSTITUTION":
        return f"institution:{user.institution_id}"
    return f"{user.role.lower()}:{user.kernel_role}"


def open_path(audience: str, ref: str | None = None) -> str:
    """Where a notification's link lands."""
    if audience.startswith("institution:"):
        base = "/institution"
    elif audience in ("internal_audit", "auditor"):
        base = "/auditor"
    else:
        base = "/aicte"
    if ref and ref.startswith("FDR"):
        return f"{base}/fdr/{ref}"
    return f"{base}/notifications"
