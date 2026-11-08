from pathlib import Path

import pytest

from trustledger.scenario import Runner, load_scenario, make_policy

FILES = sorted((Path(__file__).resolve().parent.parent / "scenarios").glob("*.json"))


@pytest.mark.parametrize("path", FILES, ids=[f.stem for f in FILES])
def test_scenario(path):
    sc = load_scenario(path)
    res = Runner(policy=make_policy(sc.get("policy_overrides"))).run(sc)
    assert res["failed"] == 0, "\n".join(res["log"])
    assert res["passed"] > 0
