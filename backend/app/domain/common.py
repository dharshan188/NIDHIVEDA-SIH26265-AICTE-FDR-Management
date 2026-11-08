from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from trustledger.kernel import (ConflictOfInterest, DomainError, GateBlocked, InvalidEvidence, MandatoryOverride,  # noqa: F401
                                OverAllocation, StateError, Unauthorised)

from ..ledger import LedgerError


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def domain_http(e: Exception) -> HTTPException:
    """Map kernel errors to HTTP. The kernel's reason is passed through: it is the explanation users need."""
    if isinstance(e, GateBlocked):
        return HTTPException(409, {"error": "GateBlocked", "message": str(e), "decision": e.decision.as_dict()})
    if isinstance(e, Unauthorised):
        return HTTPException(403, {"error": "Unauthorised", "message": str(e)})
    if isinstance(e, ConflictOfInterest):
        return HTTPException(409, {"error": "ConflictOfInterest", "message": str(e)})
    if isinstance(e, MandatoryOverride):
        return HTTPException(409, {"error": "MandatoryOverride", "message": str(e)})
    if isinstance(e, LedgerError):
        return HTTPException(409, {"error": "DatabaseInvariant", "message": str(e)})
    if isinstance(e, DomainError):
        return HTTPException(409, {"error": type(e).__name__, "message": str(e)})
    if isinstance(e, KeyError):
        return HTTPException(404, {"error": "NotFound", "message": f"unknown id {e}"})
    raise e


def rupees(paise: int) -> float:
    return paise / 100


def fmt_inr(paise: int) -> str:
    """Rs with Indian digit grouping: 3500000000 paise -> 'Rs 3,50,00,000'."""
    r = str(abs(paise) // 100)
    head, tail = r[:-3], r[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    return ("-" if paise < 0 else "") + "Rs " + (f"{head},{tail}" if head else tail)
