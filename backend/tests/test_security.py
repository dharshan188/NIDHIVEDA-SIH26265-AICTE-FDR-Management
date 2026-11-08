"""Rate limits on login / OTP / links, security headers, and the OIDC client against a configured (non-mock) issuer."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import jwt

from app.config import get_settings
from conftest import ABC, INS, MEERA, OFF


def test_login_is_rate_limited_per_address(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_login_per_min", 5)
    a = api()
    codes = [a.post("/api/auth/login", json={"username": f"nobody{i}@x.in", "password": "wrong", "role": OFF}).status_code for i in range(7)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]
    r = a.post("/api/auth/login", json={"username": "nobody9@x.in", "password": "wrong", "role": OFF})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1


def test_otp_verification_is_rate_limited(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_otp_per_5min", 4)
    a = api()
    assert a.post("/api/auth/login", json={"username": ABC, "password": "Demo-Pass-2026!", "role": INS}).status_code == 200
    codes = [a.post("/api/auth/otp/verify", json={"code": "000000"}).status_code for _ in range(5)]
    assert 429 in codes and codes.index(429) == 4


def test_security_headers_on_api_responses(api):
    r = api().get("/api/health")
    h = r.headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["strict-transport-security"].startswith("max-age=31536000") and "camera=()" in h["permissions-policy"]
    assert h["cross-origin-opener-policy"] == "same-origin" and h["cache-control"] == "no-store"


def _route_to_testclient(monkeypatch, a, issuer_doc_override=None):
    """The real OIDC client code path, with its outbound HTTP served by the in-process issuer."""
    def get(url, **kw):
        path = urlparse(url).path
        r = a.c.get(path)
        if issuer_doc_override and path.endswith("openid-configuration"):
            return httpx.Response(200, json={**r.json(), **issuer_doc_override})
        return httpx.Response(r.status_code, content=r.content, headers=r.headers)

    def post(url, data=None, **kw):
        r = a.c.post(urlparse(url).path, data=data)
        return httpx.Response(r.status_code, content=r.content, headers=r.headers)

    class Jwks:
        def __init__(self, uri):
            self.keys = jwt.PyJWKSet.from_dict(a.c.get(urlparse(uri).path).json())

        def get_signing_key_from_jwt(self, token):
            kid = jwt.get_unverified_header(token)["kid"]
            return next(k for k in self.keys.keys if k.key_id == kid)
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(jwt, "PyJWKClient", Jwks)


def _sso_real(api, monkeypatch, override=None):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "oidc_issuer", f"{cfg.api_url}/mock-oidc")   # configured issuer: the client does discovery, token, JWKS
    a = api()
    _route_to_testclient(monkeypatch, a, override)
    r = a.get(f"/api/auth/sso/start?role={OFF}", follow_redirects=False)
    q = parse_qs(urlparse(r.headers["location"]).query)
    form = {"sub": "sso-meera", "redirect_uri": q["redirect_uri"][0], "state": q["state"][0], "nonce": q["nonce"][0],
            "code_challenge": q["code_challenge"][0]}
    cb = urlparse(a.post("/api/mock-oidc/authorize", data=form, follow_redirects=False).headers["location"])
    return a, a.get(f"{cb.path}?{cb.query}", follow_redirects=False)


def test_oidc_client_against_configured_issuer(api, monkeypatch):
    a, r = _sso_real(api, monkeypatch)
    assert r.status_code == 302, r.text
    me = a.get("/api/auth/me").json()
    assert me["mfa"] == "sso" and me["user"]["username"] == MEERA


def test_oidc_rejects_discovery_for_another_issuer(api, monkeypatch):
    _, r = _sso_real(api, monkeypatch, override={"issuer": "https://evil.example"})
    assert r.status_code == 401 and "issuer" in r.text


def test_link_resolution_is_rate_limited(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_link_per_min", 3)
    a = api().login(ABC, INS)
    codes = [a.post("/api/nudge/links/resolve", json={"token": f"bad.{i}.token-xxxxx"}).status_code for i in range(4)]
    assert codes[:3] == [400, 400, 400] and codes[3] == 429
