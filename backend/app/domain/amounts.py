"""Table 1.4 base-deposit calculator and Cl. 2.21(h)/(i) penalty proposals.

Both produce PROPOSALS for an officer to sign off. Nothing here changes a deposit, a refund or a
penalty by itself, and anything outside the table (exemptions, addenda) is escalated, not guessed.
"""
from __future__ import annotations

import json
from pathlib import Path

LAKH_PAISE = 100_000 * 100
DATA = json.loads((Path(__file__).resolve().parents[2] / "data" / "aph_2024_27_amounts.json").read_text())


def required_deposit(lines: list[dict], institution_type: str, leased: bool) -> dict:
    """lines: [{"discipline": ..., "level": "Diploma"|"UG"|"PG"}]. Multi-programme institutions pay the sum."""
    if institution_type in ("Government", "Government Aided"):
        return {"status": "ESCALATED", "reason": f"{institution_type} institutions may be exempt (Cl. 1.12(i)); eligibility needs officer review",
                "proposal_only": True}
    out, total = [], 0
    for ln in lines:
        base = DATA["table_1_4_lakh"].get(ln["discipline"], {}).get(ln["level"])
        if base is None:
            return {"status": "ESCALATED", "reason": f"no Table 1.4 amount for {ln['discipline']} / {ln['level']}", "proposal_only": True}
        amt = base * (2 if leased else 1) * LAKH_PAISE
        out.append({**ln, "base_lakh": base, "doubled": leased, "amount_paise": amt})
        total += amt
    return {"status": "PROPOSED", "lines": out, "total_paise": total, "cite": "APH 2024-27 Table 1.4" + (" (doubled: leased)" if leased else ""),
            "proposal_only": True, "requires": "officer sign-off; legal cell to confirm addenda"}


def penalty_proposal(principal_paise: int, clause: str) -> dict:
    p = DATA["closure_penalties"].get(clause)
    if p is None:
        return {"status": "ESCALATED", "reason": f"unknown clause {clause}", "proposal_only": True}
    deduction = principal_paise * p["percent"] // 100
    return {"status": "PROPOSED", "clause": f"APH 2024-27 Cl. {clause}", "percent": p["percent"], "condition": p["condition"],
            "principal_paise": principal_paise, "deduction_paise": deduction, "net_release_paise": principal_paise - deduction,
            "proposal_only": True, "requires": "competent-authority review of applicability; not applied automatically"}
