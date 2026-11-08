from trustledger.rules import RuleResolver, load_packs


def r(include_disabled=False):
    return RuleResolver(load_packs(include_disabled=include_disabled))


def test_resolves_by_date_of_act_not_today():
    res = r().resolve("fdr.manual_renewal_after_maturity", "2018-12-20")
    assert res.status == "UNVERIFIED" and res.value == "prohibited" and res.editions == ["APH-2018-19"]


def test_window_boundaries_are_inclusive():
    assert r().resolve("fdr.auto_renewal", "2019-03-31").value == "accepted_with_bank_remark"
    assert r().resolve("fdr.auto_renewal", "2019-04-01").status == "NOT_SPECIFIED"


def test_gap_between_editions_is_not_guessed():
    res = r().resolve("release.fdr_instrument", "2021-06-01")
    assert res.status == "NOT_SPECIFIED" and not res.usable


def test_verified_pack_resolves():
    res = r().resolve("release.fdr_instrument", "2026-09-01")
    assert res.status == "RESOLVED" and res.value == "noc" and "Cl. 6.46" in res.cites[0]


def test_not_specified_value_counts_as_silence():
    assert r().resolve("fdr.manual_renewal_after_maturity", "2025-06-10").status == "NOT_SPECIFIED"


def test_conflicting_editions_escalate():
    res = r(include_disabled=True).resolve("deposit.term_years", "2026-08-01")
    assert res.status == "CONFLICT" and not res.usable and len(res.cites) == 2


def test_legal_confirmation_and_case_ruling():
    rr = r()
    rr.confirm_pack("APH-2018-19")
    assert rr.resolve("fdr.manual_renewal_after_maturity", "2018-12-20").status == "RESOLVED"
    rr.add_ruling("CASE-1", "fdr.manual_renewal_after_maturity", "2025-06-10", "permitted", "LC/1")
    assert rr.resolve("fdr.manual_renewal_after_maturity", "2025-06-10", case_id="CASE-1").status == "RULED"
    assert rr.resolve("fdr.manual_renewal_after_maturity", "2025-06-10", case_id="OTHER").status == "NOT_SPECIFIED"
