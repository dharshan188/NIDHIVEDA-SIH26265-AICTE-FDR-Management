"""Scenario runner: executes JSON scenario files against the kernel with no code changes.

A step is either an action ({"do": ...}) or an expectation ({"expect": ...}).
Any key ending in "_lakh" is converted to integer paise and the suffix dropped,
so scenario authors can write amounts the way AICTE staff do.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .crypto import TestBankSigner
from .kernel import DomainError, Kernel, fmt, lakh

ACTIONS = {
    "institution": "register_institution", "obligation": "create_obligation", "allocate": "allocate",
    "reverse_allocation": "reverse_allocation", "dispute": "open_dispute", "resolve_dispute": "resolve_dispute",
    "hold": "place_hold", "release_hold": "release_hold", "entitlement": "record_entitlement",
    "affidavit": "record_affidavit", "payee": "register_payee", "override": "override_admin",
    "confirm_pack": "confirm_rule_pack", "ruling": "legal_ruling", "instrument": "register_instrument",
    "renewal_request": "request_renewal", "authorise": "authorise_release", "initiate": "initiate_payment",
    "tick": "tick", "end_signer": "end_signer", "compromise_signer": "compromise_signer", "legacy_import": "import_legacy",
}


def convert(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k.endswith("_lakh"):
                out[k[:-5]] = lakh(v) if not isinstance(v, dict) else convert(v)
            else:
                out[k] = convert(v)
        return out
    if isinstance(obj, list):
        return [convert(x) for x in obj]
    return obj


def dig(obj, path: str):
    for part in path.split(".") if path else []:
        if isinstance(obj, (list, tuple)):
            obj = obj[int(part)]
        else:
            obj = obj[part]
    return obj


class Runner:
    def __init__(self, policy=None, packs=None) -> None:
        self.k = Kernel(policy, packs)
        self.banks: dict = {}
        self.last = None
        self.log: list = []

    # ------------------------------------------------------------ actions
    def do(self, step: dict):
        step = convert(step)
        kind = step.pop("do")
        if kind == "bank":
            signer = TestBankSigner(step["bank"], step["key"])
            self.banks[step["key"]] = signer
            self.k.register_signer(step["key"], step["bank"], signer.public_key_b64, step["valid_from"], step["at"])
            return None
        if kind == "evidence":
            signer = self.banks[step["key"]]
            env = signer.sign(step["kind"], step["payload"], step.get("signed_at", step["at"]))
            if step.get("forge_amount") is not None:   # tamper after signing: signature must fail
                env["payload"] = {**env["payload"], "amount": step["forge_amount"]}
            return self.k.record_bank_evidence(step["id"], env, step["at"])
        if kind == "tamper":
            def mut(d, path=step["path"], value=step["value"]):
                tgt = d
                for p in path[:-1]:
                    tgt = tgt[p]
                tgt[path[-1]] = value
            self.k.store._tamper(step["seq"], mut)
            return None
        method = getattr(self.k, ACTIONS[kind])
        return method(**step)

    # ------------------------------------------------------------ expectations
    def check(self, step: dict) -> tuple[bool, str]:
        e = step["expect"]
        k = self.k
        if e == "error":
            try:
                self.do(dict(step["step"]))
            except DomainError as err:
                return err.code == step["code"], f"raised {err.code}: {err}"
            return False, "no error raised"
        step = convert({x: y for x, y in step.items() if x != "step"})
        if e == "refund_state":
            got = k.refunds[step["refund"]]["state"]
            return got == step["equals"], f"refund {step['refund']} state={got}"
        if e == "liability":
            lr = k.liability_register(step["obligation"])
            bad = {f: (lr[f], v) for f, v in step.items() if f in lr and lr[f] != v}
            return not bad, f"{step['obligation']}: " + ", ".join(f"{f}={fmt(v)}" for f, v in lr.items()) + (f" MISMATCH {bad}" if bad else "")
        if e == "release":
            dec = k.evaluate_release(step["obligation"], step["at"], step["approver"], step.get("amount"))
            ok = dec.allowed == step["allowed"]
            for code in step.get("blocked_by_includes", []):
                ok &= code in dec.blocked_by
            for code in step.get("not_blocked_by", []):
                ok &= code not in dec.blocked_by
            if "releasable" in step:
                ok &= dec.releasable == step["releasable"]
            if "instrument_no" in step:
                ok &= dec.instrument_no == step["instrument_no"]
            detail = "; ".join(f"{c.code}:{'ok' if c.ok else 'BLOCK'}({c.detail})" for c in dec.checks if not c.ok) or "all checks pass"
            return ok, f"allowed={dec.allowed} releasable={fmt(dec.releasable)} | {detail}"
        if e == "notification":
            hits = [n for n in k.outbox if n["to"] == step["to"] and n["kind"] == step["kind"] and step.get("contains", "") in n["text"]]
            return bool(hits) == step.get("present", True), (hits[-1]["text"] if hits else "no matching notification")
        if e == "no_notification":
            hits = [n for n in k.outbox if n["kind"] == step["kind"]]
            return not hits, f"{len(hits)} '{step['kind']}' notifications"
        if e == "portal_text":
            txt = k.refund_status_text(step["refund"])
            ok = all(s in txt for s in step.get("contains", [])) and not any(s in txt for s in step.get("not_contains", []))
            return ok, txt
        if e == "confidence":
            got = k.allocation_confidence(step["alloc"])
            return got == step["equals"], f"{step['alloc']} confidence={got}"
        if e == "chain":
            ok, bad = k.store.verify()
            good = ok == step["valid"] and (step.get("first_bad_seq") in (None, bad))
            return good, f"chain valid={ok} first_bad={bad} events={len(k.store)}"
        if e == "replay_matches":
            r = Kernel.replay(k.store, k.policy, k._packs)
            return r.snapshot() == k.snapshot(), f"replayed {len(k.store)} events"
        if e == "result":
            got = dig(self.last, step.get("path", "")) if step.get("path") else self.last
            return got == step["equals"], f"result={got}"
        if e == "value":
            src = {"certification_report": lambda: k.certification_report(),
                   "funding": lambda: k.funding_breakdown(step["obligation"]),
                   "confirmation_requests": lambda: k.confirmation_requests(),
                   "nocs": lambda: k.nocs, "instruments": lambda: k.instruments, "refund": lambda: k.refunds[step["refund"]],
                   "outbox": lambda: k.outbox, "holds": lambda: k.holds, "allocations": lambda: k.allocations,
                   "book_balance": lambda: k.book_balance(),
                   "current_instrument": lambda: k.current_instrument(step["obligation"])}[step["of"]]()
            got = dig(src, step.get("path", ""))
            if "len" in step:
                return len(got) == step["len"], f"{step['of']}{'.' + step['path'] if step.get('path') else ''} len={len(got)}"
            label = step["of"] + (f".{step['path']}" if step.get("path") else "")
            return got == step["equals"], f"{label} = {got}"
        raise ValueError(f"unknown expectation {e}")

    def run(self, scenario: dict, verbose: bool = False) -> dict:
        passed = failed = 0
        for i, step in enumerate(scenario["steps"], 1):
            if "note" in step and len(step) == 1:
                self.log.append(f"      # {step['note']}")
                continue
            if "expect" in step:
                try:
                    ok, detail = self.check(step)
                except Exception as err:  # noqa: BLE001 - report, don't crash the runner
                    ok, detail = False, f"expectation crashed: {type(err).__name__}: {err}"
                passed += ok
                failed += not ok
                self.log.append(f"{i:>3} {'PASS' if ok else 'FAIL'} expect {step['expect']}: {detail}")
            else:
                try:
                    self.last = self.do(dict(step))
                    self.log.append(f"{i:>3}  ..  do {step['do']}" + (f" -> {self.last}" if isinstance(self.last, (str, dict)) and step['do'] != 'legacy_import' else ""))
                    if step["do"] == "legacy_import":
                        self.log.append(f"         import report: {self.last}")
                except Exception as err:  # noqa: BLE001
                    failed += 1
                    code = getattr(err, "code", type(err).__name__)
                    self.log.append(f"{i:>3} FAIL do {step['do']} raised {code}: {err}")
        return {"id": scenario["id"], "title": scenario["title"], "passed": passed, "failed": failed, "log": self.log}


SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def load_scenario(path: Path) -> dict:
    """Expands "include" (shared setup step lists) and applies "policy_overrides" (dotted keys)."""
    sc = json.loads(Path(path).read_text())
    steps = []
    for name in sc.get("include", []):
        steps += json.loads((SCENARIO_DIR / "includes" / f"{name}.json").read_text())["steps"]
    sc["steps"] = steps + sc["steps"]
    return sc


def make_policy(overrides: dict | None) -> dict:
    import copy
    from .kernel import load_policy
    pol = copy.deepcopy(load_policy())
    for dotted, value in (overrides or {}).items():
        *path, last = dotted.split(".")
        tgt = pol
        for p in path:
            tgt = tgt[p]
        tgt[last] = value
    return pol


def run_file(path: Path, verbose=True) -> dict:
    sc = load_scenario(path)
    res = Runner(policy=make_policy(sc.get("policy_overrides"))).run(sc)
    if verbose:
        print(f"\n=== {sc['id']}: {sc['title']}")
        if sc.get("policy_overrides"):
            print(f"    policy overrides (data only): {sc['policy_overrides']}")
        if sc.get("reviewer_ref"):
            print(f"    answers: {sc['reviewer_ref']}")
        print("\n".join(res["log"]))
        print(f"--> {res['passed']} passed, {res['failed']} failed")
    return res


if __name__ == "__main__":
    files = [Path(a) for a in sys.argv[1:]] or sorted(SCENARIO_DIR.glob("*.json"))
    total_f = 0
    results = [run_file(f) for f in files]
    print("\nSUMMARY")
    for r in results:
        print(f"  {r['id']:<5} {'OK  ' if not r['failed'] else 'FAIL'} {r['passed']:>3} checks  {r['title']}")
        total_f += r["failed"]
    print(f"  scenarios={len(results)} checks_passed={sum(r['passed'] for r in results)} checks_failed={total_f}")
    sys.exit(1 if total_f else 0)
