"""Delivery channels behind one interface.

Each channel has a real adapter and a simulator; settings pick one (TL_EMAIL_PROVIDER, TL_SMS_PROVIDER,
TL_WHATSAPP_PROVIDER, TL_PUSH_PROVIDER). Simulators write what would have been sent to provider_sim_messages and are
labelled SIMULATED everywhere. Every call carries the delivery's idempotency key, so a retried call cannot send twice:
the simulator and the HTTP adapters pass it to the provider; SMTP uses it as the Message-ID.

Status meanings (never stronger than the evidence):
  sent       the provider accepted the message (HTTP 2xx / SMTP 250) — not proof of delivery
  delivered  a delivery receipt arrived from the provider (webhook), or the channel is our own in-app centre
"""
from __future__ import annotations

import json
import logging
import smtplib
import threading
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import get_settings
from .clock import iso, now_ist

log = logging.getLogger("trustledger.nudge")


@dataclass
class OutMsg:
    channel: str
    idempotency_key: str
    to: str | list[str]        # address, number or device tokens (plaintext, in memory only)
    to_masked: str
    to_role: str
    lang: str
    subject: str
    body: str
    short: str
    link: str
    data: dict = field(default_factory=dict)


@dataclass
class SendResult:
    provider: str
    provider_ref: str
    status: str            # sent | delivered | skipped
    simulated: bool
    detail: str = ""


class Provider(Protocol):
    name: str
    simulated: bool

    def send(self, db: Session, msg: OutMsg) -> SendResult: ...


class ProviderError(Exception):
    """Temporary failure: the worker retries with back-off."""


# ------------------------------------------------------------------ in-app (our own notification centre)
class InApp:
    name, simulated = "portal-in-app", False

    def send(self, db: Session, msg: OutMsg) -> SendResult:
        return SendResult(self.name, msg.idempotency_key, "delivered", False, "shown in the user's notification centre")


# ------------------------------------------------------------------ simulator (all external channels)
class Simulator:
    simulated = True

    def __init__(self, channel: str):
        self.channel = channel
        self.name = f"simulator-{channel}"

    def send(self, db: Session, msg: OutMsg) -> SendResult:
        # The provider is a separate system: its record is committed in its own session and survives a crash of the worker.
        from ..db import SessionLocal
        with SessionLocal() as ps:
            row = ps.scalars(select(m.ProviderSimMessage).where(m.ProviderSimMessage.idempotency_key == msg.idempotency_key)).first()
            if row:   # retried call: a real provider would return the original message id
                row.calls += 1
            else:
                row = m.ProviderSimMessage(idempotency_key=msg.idempotency_key, channel=self.channel, provider=self.name, to_role=msg.to_role,
                                           to_masked=msg.to_masked, lang=msg.lang, subject=msg.subject if self.channel == "email" else None,
                                           body=(msg.body if msg.link in msg.body else f"{msg.body}\n\n{msg.link}") if self.channel == "email" else msg.short,
                                           created_at=iso(now_ist()))
                ps.add(row)
            ps.commit()
            ref = f"SIM-{row.id}"
        return SendResult(self.name, ref, "sent", True, "SIMULATED: stored by the provider simulator, nothing left this machine")


# ------------------------------------------------------------------ real adapters
class SmtpEmail:
    """Any SMTP relay (NIC mail relay, SES, SendGrid SMTP). With TL_SMTP_SINK=true (Mailpit in docker-compose) messages
    land in a local inbox and are labelled SIMULATED."""

    def __init__(self, host: str, port: int, user: str, password: str, sender: str, starttls: bool, sink: bool):
        self.host, self.port, self.user, self.password, self.sender, self.starttls = host, port, user, password, sender, starttls
        self.simulated = sink
        self.name = "smtp-mailpit-sink" if sink else f"smtp:{host}"

    def send(self, db: Session, msg: OutMsg) -> SendResult:
        em = EmailMessage()
        em["From"], em["To"], em["Subject"] = self.sender, msg.to, msg.subject
        em["Message-ID"] = f"<{msg.idempotency_key}@fdr-trust-ledger>"   # the relay / mailbox can de-duplicate on it
        em["Content-Language"] = msg.lang
        em.set_content(f"{msg.body}\n\n{msg.link}\n")
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as s:
                if self.starttls:
                    s.starttls()
                if self.user:
                    s.login(self.user, self.password)
                s.send_message(em)
        except (OSError, smtplib.SMTPException) as e:
            raise ProviderError(f"SMTP: {e}") from e
        return SendResult(self.name, em["Message-ID"], "sent", self.simulated, "accepted by the SMTP server (not a delivery receipt)")


class HttpSms:
    """Generic SMS gateway over HTTPS (NIC SMS / a DLT-registered aggregator). Delivery receipts arrive on
    POST /api/providers/receipts/sms, signed with TL_PROVIDER_WEBHOOK_SECRET."""
    simulated = False

    def __init__(self, url: str, api_key: str, sender: str, dlt_entity: str):
        self.url, self.api_key, self.sender, self.dlt_entity = url, api_key, sender, dlt_entity
        self.name = "http-sms"

    def send(self, db: Session, msg: OutMsg) -> SendResult:
        try:
            r = httpx.post(self.url, timeout=15, headers={"Authorization": f"Bearer {self.api_key}", "Idempotency-Key": msg.idempotency_key},
                           json={"to": msg.to, "from": self.sender, "text": msg.short, "unicode": msg.lang == "hi",
                                 "dlt_entity_id": self.dlt_entity, "reference": msg.idempotency_key})
        except httpx.HTTPError as e:
            raise ProviderError(f"SMS gateway: {e}") from e
        if r.status_code >= 500 or r.status_code == 429:
            raise ProviderError(f"SMS gateway HTTP {r.status_code}")
        r.raise_for_status()
        return SendResult(self.name, str(r.json().get("message_id", msg.idempotency_key)), "sent", False, "accepted by the SMS gateway")


class WhatsAppCloud:
    """WhatsApp Business Cloud API (template messages). Receipts arrive on POST /api/providers/receipts/whatsapp."""
    simulated = False

    def __init__(self, token: str, phone_id: str, template: str):
        self.token, self.phone_id, self.template = token, phone_id, template
        self.name = "whatsapp-cloud"

    def send(self, db: Session, msg: OutMsg) -> SendResult:
        try:
            r = httpx.post(f"https://graph.facebook.com/v20.0/{self.phone_id}/messages", timeout=15,
                           headers={"Authorization": f"Bearer {self.token}"},
                           json={"messaging_product": "whatsapp", "to": msg.to, "type": "template", "biz_opaque_callback_data": msg.idempotency_key,
                                 "template": {"name": self.template, "language": {"code": "hi" if msg.lang == "hi" else "en"},
                                              "components": [{"type": "body", "parameters": [{"type": "text", "text": msg.short[:900]}]}]}})
        except httpx.HTTPError as e:
            raise ProviderError(f"WhatsApp: {e}") from e
        if r.status_code >= 500 or r.status_code == 429:
            raise ProviderError(f"WhatsApp HTTP {r.status_code}")
        r.raise_for_status()
        return SendResult(self.name, r.json()["messages"][0]["id"], "sent", False, "accepted by WhatsApp Cloud API")


class FcmPush:
    """Firebase Cloud Messaging HTTP v1 to the phones registered by the mobile app (push_devices)."""
    simulated = False
    name = "fcm"
    SCOPE = "https://www.googleapis.com/auth/firebase.messaging"

    def __init__(self, credentials_path: str):
        with open(credentials_path) as f:
            self.sa = json.load(f)
        self.url = f"https://fcm.googleapis.com/v1/projects/{self.sa['project_id']}/messages:send"
        self._token, self._exp, self._lock = "", 0.0, threading.Lock()

    def _access_token(self, client: httpx.Client) -> str:
        with self._lock:
            if time.time() < self._exp - 60:
                return self._token
            now = int(time.time())
            uri = self.sa.get("token_uri", "https://oauth2.googleapis.com/token")
            assertion = jwt.encode({"iss": self.sa["client_email"], "scope": self.SCOPE, "aud": uri, "iat": now, "exp": now + 3600},
                                   self.sa["private_key"], algorithm="RS256")
            r = client.post(uri, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion})
            r.raise_for_status()
            body = r.json()
            self._token, self._exp = body["access_token"], now + body.get("expires_in", 3600)
            return self._token

    def send(self, db: Session, msg: OutMsg) -> SendResult:
        refs, dead = [], []
        try:
            with httpx.Client(timeout=10) as client:
                for tok in msg.to:
                    r = client.post(self.url, headers={"Authorization": f"Bearer {self._access_token(client)}"}, json={"message": {
                        "token": tok, "notification": {"title": msg.subject, "body": msg.short},
                        "data": {"path": msg.data.get("path", ""), "notification_id": str(msg.data.get("notification_id", ""))},
                        "android": {"priority": "high", "notification": {"channel_id": "tl-alerts", "tag": msg.idempotency_key}}}})
                    if r.status_code in (400, 404) and ("UNREGISTERED" in r.text or "INVALID_ARGUMENT" in r.text):
                        dead.append(tok)
                    elif r.status_code >= 300:
                        raise ProviderError(f"FCM HTTP {r.status_code}")
                    else:
                        refs.append(r.json().get("name", ""))
        except httpx.HTTPError as e:
            raise ProviderError(f"FCM: {e}") from e
        if dead:
            db.query(m.PushDevice).filter(m.PushDevice.token.in_(dead)).delete(synchronize_session=False)
        return SendResult(self.name, ",".join(refs)[:120] or msg.idempotency_key, "sent", False, f"accepted by FCM for {len(refs)} device(s)")


# ------------------------------------------------------------------ registry
@lru_cache
def provider(channel: str) -> Provider:
    s = get_settings()
    if channel == "in_app":
        return InApp()
    if channel == "email" and s.email_provider == "smtp":
        return SmtpEmail(s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password, s.smtp_from, s.smtp_starttls, s.smtp_sink)
    if channel == "sms" and s.sms_provider == "http":
        return HttpSms(s.sms_url, s.sms_api_key, s.sms_sender, s.sms_dlt_entity)
    if channel == "whatsapp" and s.whatsapp_provider == "cloud":
        return WhatsAppCloud(s.whatsapp_token, s.whatsapp_phone_id, s.whatsapp_template)
    if channel == "push" and s.push_provider == "fcm":
        return FcmPush(s.fcm_credentials)
    return Simulator(channel)


def summary() -> dict:
    """For the health panel and /api/push/status: which adapter each channel uses right now."""
    out = {}
    for ch in ("in_app", "email", "sms", "whatsapp", "push"):
        p = provider(ch)
        out[ch] = {"provider": p.name, "simulated": p.simulated}
    return out
