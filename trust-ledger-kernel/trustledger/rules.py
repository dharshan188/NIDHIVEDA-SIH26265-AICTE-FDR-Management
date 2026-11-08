"""Edition-aware rule resolution.

Rules are data (JSON packs). The resolver picks the edition(s) in force on the
date of the act being judged (e.g. the renewal date), not today's date.

Outcomes:
  RESOLVED        one value, from a pack that is verified (or confirmed by the legal cell)
  UNVERIFIED      one value, but its pack is not verified -> legal cell must confirm first
  NOT_SPECIFIED   no pack in force says anything -> legal cell ruling needed
  CONFLICT        two packs in force disagree -> legal cell ruling needed
A case-scoped legal-cell ruling, once recorded, overrides all of the above for that case.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent.parent / "data" / "rules"


@dataclass
class Resolution:
    key: str
    on_date: str
    status: str
    value: object = None
    cites: list = field(default_factory=list)
    editions: list = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.status in ("RESOLVED", "RULED")


def load_packs(rules_dir: Path = RULES_DIR, include_disabled: bool = False) -> list[dict]:
    packs = []
    for p in sorted(rules_dir.glob("*.json")):
        pack = json.loads(p.read_text())
        if pack.get("enabled", True) or include_disabled:
            packs.append(pack)
    return packs


class RuleResolver:
    def __init__(self, packs: list[dict]) -> None:
        self.packs = {p["edition_id"]: dict(p) for p in packs}
        self.confirmed: set[str] = set()      # packs confirmed by legal cell
        self.rulings: dict[tuple, dict] = {}  # (case_id, key, on_date) -> ruling

    def confirm_pack(self, edition_id: str) -> None:
        if edition_id not in self.packs:
            raise KeyError(edition_id)
        self.confirmed.add(edition_id)

    def add_ruling(self, case_id: str, key: str, on_date: str, value, reference: str) -> None:
        self.rulings[(case_id, key, on_date)] = {"value": value, "reference": reference}

    def in_force(self, on_date: str) -> list[dict]:
        return [p for p in self.packs.values() if p["effective_from"] <= on_date <= p["effective_to"]]

    def resolve(self, key: str, on_date: str, case_id: str | None = None) -> Resolution:
        if case_id and (case_id, key, on_date) in self.rulings:
            r = self.rulings[(case_id, key, on_date)]
            return Resolution(key, on_date, "RULED", r["value"], [r["reference"]], ["legal_cell_ruling"])
        found = []
        for p in self.in_force(on_date):
            rule = p["rules"].get(key)
            if rule is not None and rule["value"] != "not_specified":
                found.append((p, rule))
        if not found:
            eds = [p["edition_id"] for p in self.in_force(on_date)]
            return Resolution(key, on_date, "NOT_SPECIFIED", None, [], eds)
        values = {json.dumps(r["value"]) for _, r in found}
        cites = [f'{p["edition_id"]}: {r["cite"]}' for p, r in found]
        eds = [p["edition_id"] for p, _ in found]
        if len(values) > 1:
            return Resolution(key, on_date, "CONFLICT", None, cites, eds)
        value = found[0][1]["value"]
        verified = all(p["source_status"] == "verified" or p["edition_id"] in self.confirmed for p, _ in found)
        return Resolution(key, on_date, "RESOLVED" if verified else "UNVERIFIED", value, cites, eds)
