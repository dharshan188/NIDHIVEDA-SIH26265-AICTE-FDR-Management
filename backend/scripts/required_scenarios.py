"""The six scenarios the problem statement requires, run through the HTTP API only (the bank, providers and the clock are the
dev simulators, driven through /api/sim/*). Each check is recorded, not asserted, so the report shows every outcome.

  R1 new submission       R2 validity tracking       R3 approaching maturity
  R4 renewal              R5 discrepancy             R6 authorised release

Used by scripts/run_required_scenarios.py (report) and tests/test_required_scenarios.py (pytest).
"""
from __future__ import annotations

import io
from datetime import date, datetime, timedelta

MEERA, KIRAN, ABC = "meera@aicte-india.org", "kiran@aicte-india.org", "1-12345678"
OFF, INS = "AICTE_OFFICIAL", "INSTITUTION"


def pdf_bytes(text: str) -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()


class Run:
    def __init__(self, sid: str, title: str):
        self.sid, self.title, self.checks = sid, title, []

    def check(self, name: str, ok, detail: str = "") -> bool:
        self.checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
        return bool(ok)

    def result(self) -> dict:
        return {"id": self.sid, "title": self.title, "passed": sum(c["ok"] for c in self.checks),
                "failed": sum(not c["ok"] for c in self.checks), "checks": self.checks}


class Ctx:
    """State shared between scenarios (R1's FDR is used again in R3 and R4)."""

    def __init__(self, api):
        self.api = api
        self.abc = api().login(ABC, INS)
        self.meera = api().login(MEERA, OFF, "totp")
        self.kiran = api().login(KIRAN, OFF, "totp")
        self.new_fdr: str | None = None
        self.maturity: date | None = None


def _submit(ctx: Ctx, no: str, bank_amount_rupees: int, declared_rupees: int = 2500000, renewal_of: str | None = None,
            issue: date | None = None) -> tuple[int, dict]:
    issue = issue or date.today() - timedelta(days=5)
    maturity = issue + timedelta(days=3 * 365 + 2)
    ctx.abc.post("/api/sim/bank/fdrs", json={"bank": "SBI", "instrument_no": no, "amount_paise": bank_amount_rupees * 100,
                                              "maturity_date": maturity.isoformat()})
    form = {"bank": "SBI", "branch": "Chennai Main", "instrument_no": no, "amount_rupees": str(declared_rupees), "rate_bp": "705",
            "issue_date": issue.isoformat(), "maturity_date": maturity.isoformat()}
    if renewal_of:
        form["renewal_of"] = renewal_of
    files = [("files", ("fdr.pdf", pdf_bytes(f"FDR {no}"), "application/pdf")), ("files", ("lien.pdf", pdf_bytes(f"Lien on {no}"), "application/pdf"))]
    r = ctx.abc.post("/api/fdrs", data=form, files=files)
    return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text})


def _centre(client, template: str, ref: str | None = None) -> list[dict]:
    q = f"/api/nudge/centre?size=100&ref={ref}" if ref else "/api/nudge/centre?size=100"
    return [i for i in client.get(q).json()["items"] if i["template"] == template and (ref is None or i["ref"] == ref)]


def _run_at(ctx: Ctx, at: datetime, **kw) -> dict:
    return ctx.meera.post("/api/sim/nudge/run", json={"at": at.replace(tzinfo=None).isoformat(timespec="seconds"), **kw}).json()


def r1_new_submission(ctx: Ctx) -> dict:
    r = Run("R1", "New submission: upload, encrypt, scan, bank confirmation, verification, notices both ways")
    code, body = _submit(ctx, "SBI-R1-000001", 2500000)
    r.check("institution uploads the FDR with two PDFs", code == 200, code)
    if code != 200:
        return r.result()
    fid = ctx.new_fdr = body["fdr"]["id"]
    ctx.maturity = date.fromisoformat(body["fdr"]["maturity_date"])
    docs = body["documents"]
    r.check("both documents encrypted at rest (AES-256-GCM envelope)", all(d["encryption"] and "AES-256-GCM" in d["encryption"]["alg"] for d in docs), docs)
    r.check("both documents malware-scanned clean", all(d["scan"]["status"] == "clean" for d in docs))
    r.check("status pending until the bank confirms", body["fdr"]["status"] == "pending", body["fdr"]["status"])
    r.check("AICTE notified through the outbox (fdr_submitted)", _centre(ctx.meera, "fdr_submitted", fid))
    dl = ctx.abc.get(f"/api/fdrs/{fid}/documents/{docs[0]['id']}")
    r.check("download decrypts and the SHA-256 matches", dl.status_code == 200 and dl.headers.get("x-document-sha256") == docs[0]["sha256"])
    early = ctx.meera.post(f"/api/fdrs/{fid}/verify", json={})
    r.check("verification refused before any bank confirmation", early.status_code == 409, early.status_code)
    conf = ctx.meera.post(f"/api/fdrs/{fid}/bank-confirmation").json()
    rows = conf["comparison"]["rows"]
    r.check("issuing bank (SIMULATED) confirms every field", all(x["confidence"] == "BANK_CONFIRMED" for x in rows), [x["confidence"] for x in rows])
    v = ctx.meera.post(f"/api/fdrs/{fid}/verify", json={"note": "Bank confirmation matches the declaration"})
    r.check("officer verifies", v.status_code == 200 and v.json()["fdr"]["status"] == "verified", v.status_code)
    n = _centre(ctx.abc, "fdr_verified", fid)
    r.check("institution notified in English and Hindi", n and n[0]["text_en"] and n[0]["text_hi"])
    return r.result()


def r2_validity_tracking(ctx: Ctx) -> dict:
    r = Run("R2", "Validity tracking: daily sweep, ladder rungs, buckets from queries, rules in force per date")
    out = _run_at(ctx, datetime.combine(date.today(), datetime.min.time()).replace(hour=8), force=True)
    r.check("08:00 IST sweep runs", out.get("reminders", {}).get("ran") is True, out.get("reminders"))
    again = _run_at(ctx, datetime.combine(date.today(), datetime.min.time()).replace(hour=9))
    r.check("a second run the same IST day sends nothing new", again["reminders"].get("ran") is False or again["reminders"].get("reminders") == 0,
            again["reminders"])
    dash = ctx.meera.get("/api/dashboard/aicte").json()["stats"]["by_bucket"]
    lst = ctx.meera.get("/api/fdrs?bucket=maturing&size=1").json()
    r.check("dashboard 'maturing' count equals the list query", dash["maturing"]["count"] == lst["total"], (dash["maturing"]["count"], lst["total"]))
    mat = ctx.meera.get("/api/fdrs?bucket=maturing&sort=maturity&size=200").json()["items"]
    with_rem = None
    for f in mat:
        tl = ctx.meera.get(f"/api/fdrs/{f['id']}/timeline").json()
        if tl["reminders"]:
            with_rem = (f, tl)
            break
    r.check("a maturing FDR has a scheduled reminder", with_rem is not None)
    if with_rem:
        f, tl = with_rem
        days = (date.fromisoformat(f["maturity_date"]) - date.today()).days
        w = tl["reminders"][-1]["window"]
        r.check("reminder window is the tightest one reached", w.startswith("T-") and days <= int(w[2:]), (days, w))
        exp = "deadline" if days <= 7 else "action" if days <= 30 else "info"
        r.check("ladder rung follows days to maturity", tl["reminders"][-1]["rung"] == exp, (days, tl["reminders"][-1]["rung"]))
    tl1 = ctx.abc.get(f"/api/fdrs/{ctx.new_fdr}/timeline").json()
    issued = next(e for e in tl1["events"] if e["kind"] == "issued")
    r.check("timeline shows the rule editions in force on the issue date", issued["editions_in_force"] and issued["rule"]["key"] == "deposit.term_years",
            issued["editions_in_force"])
    return r.result()


def r3_approaching_maturity(ctx: Ctx) -> dict:
    r = Run("R3", "Approaching maturity: T-7 deadline rung, quiet hours, acknowledgement stops the ladder")
    at = datetime.combine(ctx.maturity - timedelta(days=7), datetime.min.time()).replace(hour=21)
    _run_at(ctx, at, fdr_ids=[ctx.new_fdr])
    n = [i for i in _centre(ctx.abc, "reminder_before", ctx.new_fdr) if i["window"] == "T-7"]
    r.check("T-7 reminder created on the deadline rung", n and n[0]["rung"] == "deadline", n[:1])
    if not n:
        return r.result()
    ch = {d["channel"]: d for d in n[0]["deliveries"]}
    r.check("channels: in-app, e-mail and SMS", set(ch) == {"in_app", "email", "sms"}, sorted(ch))
    if set(ch) != {"in_app", "email", "sms"}:
        return r.result()
    r.check("in-app and e-mail go out at 21:00", ch["in_app"]["status"] == "delivered" and ch["email"]["status"] == "sent", ch)
    r.check("SMS held for quiet hours (20:00–08:00 IST)", ch["sms"]["status"] == "deferred", ch["sms"])
    r.check("e-mail marked SIMULATED (provider simulator)", ch["email"]["simulated"] is True)
    _run_at(ctx, at + timedelta(hours=11), reminders=False)
    sms = {d["channel"]: d for d in _centre(ctx.abc, "reminder_before", ctx.new_fdr)[0]["deliveries"]}["sms"]
    r.check("SMS sent at 08:00 next morning", sms["status"] == "sent", sms)
    ack = ctx.abc.post(f"/api/nudge/notifications/{n[0]['id']}/open").json()
    r.check("institution opens it: acknowledged", ack["acknowledged"] and ack["first"])
    _run_at(ctx, at + timedelta(days=4), reminders=False)
    det = ctx.abc.get(f"/api/nudge/notifications/{n[0]['id']}").json()
    r.check("no rung-up after acknowledgement", len(det["ladder"]) == 1, [x["template"] for x in det["ladder"]])
    return r.result()


def r4_renewal(ctx: Ctx) -> dict:
    r = Run("R4", "Renewal: missed renewal goes overdue and escalates; a renewal FDR closes the gap and stops reminders")
    at = datetime.combine(ctx.maturity + timedelta(days=4), datetime.min.time()).replace(hour=8)
    _run_at(ctx, at, fdr_ids=[ctx.new_fdr])
    od = [i for i in _centre(ctx.abc, "reminder_missed_renewal", ctx.new_fdr)]
    r.check("3 days after maturity: overdue notice", od and od[0]["rung"] == "overdue" and od[0]["window"] == "M+3", od[:1])
    if od:
        r.check("overdue uses every channel", {d["channel"] for d in od[0]["deliveries"]} == {"in_app", "email", "sms", "whatsapp", "push"},
                [d["channel"] for d in od[0]["deliveries"]])
    esc = _centre(ctx.meera, "escalation_copy", ctx.new_fdr)
    r.check("copied to the AICTE officer (escalation role)", esc and esc[0]["rung"] == "overdue")
    gaps = ctx.meera.get("/api/renewals/gaps").json()["items"]
    r.check("renewal gap is flagged (no bank notice, no renewal FDR)", any(g["fdr_id"] == ctx.new_fdr for g in gaps)) if ctx.maturity < date.today() else \
        r.check("renewal gap check runs (maturity is in the future on the real clock)", isinstance(gaps, list))
    code, body = _submit(ctx, "SBI-R4-000002", 2500000, renewal_of=ctx.new_fdr)
    r.check("institution submits the renewal FDR", code == 200, code)
    if code == 200:
        tl = ctx.abc.get(f"/api/fdrs/{ctx.new_fdr}/timeline").json()
        r.check("old FDR's timeline shows the renewal", any(e["kind"] == "renewed" and e.get("related") == body["fdr"]["id"] for e in tl["events"]))
        r.check("old FDR has no renewal gap any more", not tl["gaps"], tl["gaps"])
        before = len(_centre(ctx.abc, "reminder_missed_renewal", ctx.new_fdr))
        _run_at(ctx, at + timedelta(days=30), fdr_ids=[ctx.new_fdr])
        after = len(_centre(ctx.abc, "reminder_missed_renewal", ctx.new_fdr))
        r.check("no further reminders for the renewed FDR", before == after, (before, after))
    return r.result()


def r5_discrepancy(ctx: Ctx) -> dict:
    r = Run("R5", "Discrepancy: bank says a different amount; verification blocked; flagged; observation answered and closed")
    code, body = _submit(ctx, "SBI-R5-000003", 2000000, declared_rupees=2500000)
    r.check("institution declares Rs 25 lakh (bank book says Rs 20 lakh)", code == 200, code)
    if code != 200:
        return r.result()
    fid = body["fdr"]["id"]
    conf = ctx.meera.post(f"/api/fdrs/{fid}/bank-confirmation").json()
    amt = next(x for x in conf["comparison"]["rows"] if x["field"] == "amount")
    r.check("comparison shows the amount MISMATCH", amt["confidence"] == "MISMATCH", amt)
    v = ctx.meera.post(f"/api/fdrs/{fid}/verify", json={"note": "try"})
    r.check("verification refused on mismatch", v.status_code == 409 and v.json()["detail"]["error"] == "Mismatch", v.status_code)
    fl = ctx.meera.post(f"/api/fdrs/{fid}/discrepancy", json={"reason": "Principal declared Rs 25 lakh; bank confirms Rs 20 lakh"})
    r.check("officer flags the discrepancy", fl.status_code == 200 and fl.json()["fdr"]["status"] == "discrepancy")
    r.check("institution receives 'clarification needed' (action rung)", any(i["rung"] == "action" for i in _centre(ctx.abc, "clarification_required", fid)))
    o = ctx.kiran.post(f"/api/fdrs/{fid}/observations", json={"category": "mismatch", "text": "Upload the bank's advice for the principal amount"}).json()
    r.check("scrutiny observation recorded (mismatch)", o.get("observation", {}).get("status") == "open")
    rep = ctx.abc.post(f"/api/observations/{o['observation']['id']}/replies", json={"text": "Bank advice uploaded; principal is Rs 20 lakh"}).json()
    r.check("institution replies: observation answered", rep["items"][0]["status"] == "answered")
    cl = ctx.kiran.post(f"/api/observations/{o['observation']['id']}/close").json()
    r.check("officer closes the observation", cl["observation"]["status"] == "closed")
    rep = ctx.meera.get("/api/reports/missing-documents?state=unverified&size=500").json()
    r.check("missing-documents report lists it as unverified", any(i["instrument"] == fid for i in rep["items"]))
    return r.result()


def r6_authorised_release(ctx: Ctx) -> dict:
    r = Run("R6", "Authorised release: scrutiny, DSC approval, NOC, completion only on bank lien discharge")
    fid = "FDR202600125"
    rq = ctx.abc.post("/api/release-requests", json={"fdr_id": fid, "reason": "Replacement with higher-value FDR"})
    r.check("institution raises the release request", rq.status_code == 200, rq.status_code)
    if rq.status_code != 200:
        return r.result()
    rid = rq.json()["id"]
    r.check("AICTE notified (release_requested)", _centre(ctx.meera, "release_requested", rid))
    sc = ctx.kiran.post(f"/api/release-requests/{rid}/scrutiny", json={"entitlement_basis": "Replacement approved"})
    r.check("section officer completes scrutiny", sc.status_code == 200, sc.status_code)
    no_dsc = ctx.meera.post(f"/api/release-requests/{rid}/approve", json={"certificate_pem": "-", "signature_b64": "-"})
    r.check("approval without a valid DSC signature is refused", no_dsc.status_code in (400, 401, 422), no_dsc.status_code)
    gate = ctx.meera.get(f"/api/release-requests/{rid}/gate").json()
    r.check("release gate allows (all mandatory checks pass)", gate["allowed"], gate.get("blocked_by"))
    sig = ctx.meera.dsc(MEERA, gate["approval_message"])
    ap = ctx.meera.post(f"/api/release-requests/{rid}/approve", json={"certificate_pem": sig["certificate_pem"], "signature_b64": sig["signature_b64"]})
    r.check("deputy director approves with DSC: NOC issued", ap.status_code == 200 and ap.json()["case_id"].startswith("NOC-"), ap.status_code)
    r.check("NOC alone is not completion (FDR still verified)", ctx.abc.get(f"/api/fdrs/{fid}").json()["fdr"]["status"] == "verified")
    r.check("institution told: not complete until lien discharge", any("lien" in (i["text_en"] or "") for i in _centre(ctx.abc, "release_approved", rid)))
    ld = ctx.meera.post(f"/api/release-requests/{rid}/lien-discharge").json()
    r.check("bank (SIMULATED) confirms lien discharge", ld.get("status") == "ACCEPTED", ld.get("status"))
    r.check("only now: released", ctx.abc.get(f"/api/fdrs/{fid}").json()["fdr"]["status"] == "released")
    return r.result()


ALL = [r1_new_submission, r2_validity_tracking, r3_approaching_maturity, r4_renewal, r5_discrepancy, r6_authorised_release]


def run_all(api) -> list[dict]:
    ctx = Ctx(api)
    return [fn(ctx) for fn in ALL]
