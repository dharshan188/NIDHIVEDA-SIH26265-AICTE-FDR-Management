from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from conftest import ABC, AUD, AUDITOR, INS, MEERA, OFF, PW, XYZ


def _login(c, user, pw=PW, role=OFF):
    return c.post("/api/auth/login", json={"username": user, "password": pw, "role": role})


def test_password_is_argon2id(app):
    with SessionLocal() as db:
        u = db.scalars(select(m.User).where(m.User.username == MEERA)).one()
        assert u.password_hash.startswith("$argon2id$")


def test_generic_error_does_not_reveal_account(api):
    a = api()
    r1 = _login(a, MEERA, "wrong-password")
    r2 = _login(a, "nobody@aicte-india.org", "wrong-password")
    r3 = _login(a, MEERA, PW, role=INS)          # right password, wrong role tab
    assert r1.status_code == r2.status_code == r3.status_code == 401
    assert r1.json() == r2.json() == r3.json()


def test_lockout_after_five_failures_then_timed_unlock(api):
    a = api()
    for _ in range(5):
        assert _login(a, MEERA, "bad").status_code == 401
    assert _login(a, MEERA, PW).status_code == 401          # locked: even the right password fails, same message
    with SessionLocal() as db:
        u = db.scalars(select(m.User).where(m.User.username == MEERA)).one()
        assert u.locked_until and u.locked_until > datetime.now()
        u.locked_until = datetime.now() - timedelta(seconds=1)   # lock time elapsed
        db.commit()
    assert _login(a, MEERA, PW).status_code == 200


def test_mfa_is_mandatory(api):
    a = api()
    assert _login(a, MEERA).status_code == 200
    assert a.get("/api/auth/me").status_code == 401           # password alone gives no session
    assert a.get("/api/dashboard/aicte").status_code == 401


def test_otp_single_use(api):
    a = api()
    _login(a, MEERA)
    a.post("/api/auth/otp/send")
    code = a.get(f"/api/sim/otp-outbox/{MEERA}").json()["code"]
    assert a.post("/api/auth/otp/verify", json={"code": code}).status_code == 200
    b = api()
    _login(b, MEERA)
    assert b.post("/api/auth/otp/verify", json={"code": code}).status_code == 401   # reuse refused


def test_otp_expiry(api):
    a = api()
    _login(a, MEERA)
    a.post("/api/auth/otp/send")
    code = a.get(f"/api/sim/otp-outbox/{MEERA}").json()["code"]
    with SessionLocal() as db:
        row = db.scalars(select(m.OtpCode).order_by(m.OtpCode.id.desc())).first()
        row.expires_at = datetime.now() - timedelta(seconds=1)
        db.commit()
    assert a.post("/api/auth/otp/verify", json={"code": code}).status_code == 401


def test_otp_wrong_code_attempts_burn_the_code(api):
    a = api()
    _login(a, MEERA)
    a.post("/api/auth/otp/send")
    code = a.get(f"/api/sim/otp-outbox/{MEERA}").json()["code"]
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        assert a.post("/api/auth/otp/verify", json={"code": wrong}).status_code == 401
    assert a.post("/api/auth/otp/verify", json={"code": code}).status_code == 401   # burned after 5 wrong tries


def test_otp_send_rate_limited(api):
    a = api()
    _login(a, MEERA)
    codes = [a.post("/api/auth/otp/send").status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_totp_login(api):
    a = api().login(MEERA, OFF, method="totp")
    assert a.get("/api/auth/me").json()["mfa"] == "totp"


def test_dsc_login_and_wrong_certificate(api):
    a = api()
    _login(a, MEERA)
    ch = a.post("/api/auth/dsc/challenge").json()["challenge"]
    other = a.dsc(AUDITOR, ch)                       # auditor's valid certificate, wrong person
    assert a.post("/api/auth/dsc/verify", json={"certificate_pem": other["certificate_pem"], "signature_b64": other["signature_b64"]}).status_code == 401
    ch = a.post("/api/auth/dsc/challenge").json()["challenge"]
    mine = a.dsc(MEERA, ch)
    r = a.post("/api/auth/dsc/verify", json={"certificate_pem": mine["certificate_pem"], "signature_b64": mine["signature_b64"]})
    assert r.status_code == 200
    # a challenge is single use
    assert a.post("/api/auth/dsc/verify", json=mine).status_code == 401


def test_dsc_signature_over_different_message_rejected(api):
    a = api()
    _login(a, MEERA)
    a.post("/api/auth/dsc/challenge")
    forged = a.dsc(MEERA, "TL-LOGIN:something-else")
    assert a.post("/api/auth/dsc/verify", json=forged).status_code == 401


def test_role_enforcement(api):
    inst = api().login(ABC, INS)
    assert inst.get("/api/dashboard/aicte").status_code == 403
    assert inst.get("/api/institutions").status_code == 403
    assert inst.get("/api/audit-trail").status_code == 403
    aud = api().login(AUDITOR, AUD)
    assert aud.get("/api/dashboard/auditor").status_code == 200
    assert aud.post("/api/fdrs/FDR202600126/verify", json={}).status_code == 403
    off = api().login(MEERA, OFF)
    assert off.get("/api/dashboard/auditor").status_code == 403


def test_session_idle_timeout(api):
    a = api().login(MEERA, OFF)
    assert a.get("/api/auth/me").status_code == 200
    with SessionLocal() as db:
        for s in db.scalars(select(m.SessionRow).where(m.SessionRow.kind == "full")):
            s.last_seen = datetime.now() - timedelta(minutes=16)
        db.commit()
    r = a.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["detail"] == "session expired"


def test_session_cookie_flags(api):
    a = api()
    _login(a, MEERA)
    a.post("/api/auth/otp/send")
    code = a.get(f"/api/sim/otp-outbox/{MEERA}").json()["code"]
    r = a.post("/api/auth/otp/verify", json={"code": code})
    cookies = r.headers.get_list("set-cookie")
    sess = next(c for c in cookies if c.startswith("tl_session="))
    assert "HttpOnly" in sess and "Secure" in sess and "SameSite=strict" in sess


def test_csrf_required_on_state_change(api):
    a = api().login(MEERA, OFF)
    good = a.c.headers.pop("X-CSRF-Token")
    assert a.post("/api/notifications/read").status_code == 403
    a.c.headers["X-CSRF-Token"] = "forged"
    assert a.post("/api/notifications/read").status_code == 403
    a.c.headers["X-CSRF-Token"] = good
    assert a.post("/api/notifications/read").status_code == 200


def test_logout_revokes_session(api):
    a = api().login(MEERA, OFF)
    assert a.post("/api/auth/logout").status_code == 200
    assert a.get("/api/auth/me").status_code == 401


# ------------------------------------------------------------------ IDOR
def test_idor_institution_cannot_read_other_institution(api):
    abc = api().login(ABC, INS)
    assert abc.get("/api/fdrs/FDR202600124").status_code == 404            # XYZ's FDR
    assert abc.get("/api/fdrs/FDR202600125").status_code == 200            # own FDR
    assert abc.get("/api/dashboard/institution/INST0002").status_code == 404
    assert abc.get("/api/institutions/INST0002").status_code == 404
    assert abc.get("/api/messages/INST0002").status_code == 404
    assert abc.get("/api/payees/INST0002").status_code == 404
    assert abc.post("/api/release-requests", json={"fdr_id": "FDR202600124", "reason": "not mine at all"}).status_code == 404
    ids = {f["institution_id"] for f in abc.get("/api/fdrs?size=200").json()["items"]}
    assert ids == {"INST0001"}
    pays = abc.get("/api/payments").json()["items"]
    assert pays and {p["institution_id"] for p in pays} == {"INST0001"}
    xyz = api().login(XYZ, INS)
    assert xyz.get("/api/fdrs/FDR202600125").status_code == 404


# ------------------------------------------------------------------ SSO
def _sso(api, sub="sso-meera", role=OFF, tamper_nonce=False):
    a = api()
    r = a.get(f"/api/auth/sso/start?role={role}", follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    form = {"sub": sub, "redirect_uri": q["redirect_uri"][0], "state": q["state"][0], "nonce": "evil" if tamper_nonce else q["nonce"][0],
            "code_challenge": q["code_challenge"][0]}
    r = a.post("/api/mock-oidc/authorize", data=form, follow_redirects=False)
    cb = urlparse(r.headers["location"])
    return a, a.get(f"{cb.path}?{cb.query}", follow_redirects=False)


def test_sso_login(api):
    a, r = _sso(api)
    assert r.status_code == 302
    assert a.get("/api/auth/me").json()["mfa"] == "sso"


def test_sso_nonce_mismatch_rejected(api):
    _, r = _sso(api, tamper_nonce=True)
    assert r.status_code == 401


def test_sso_role_mismatch_rejected(api):
    _, r = _sso(api, role=INS)
    assert r.status_code == 401
