"""Nudge Ladder: outbox, ladder, reminders, scheduler, quiet hours, digests, escalation, action links, policy, insights."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app import models as m
from app.db import SessionLocal
from app.nudge import escalation, links, reminders, worker
from app.nudge import policy as pol
from app.nudge.clock import IST, ist_date
from app.nudge.ladder import rung_for
from app.nudge.outbox import notify
from app.nudge.templates import T, placeholders
from conftest import ABC, AUD, AUDITOR, INS, KIRAN, MEERA, OFF, SHARMA, XYZ

DAY = datetime(2026, 11, 2, 9, 0, tzinfo=IST)   # a Monday, 09:00 IST


def _fdr(db, inst="INST0001", status="verified") -> m.Fdr:
    return db.scalars(select(m.Fdr).where(m.Fdr.institution_id == inst, m.Fdr.status == status, m.Fdr.renewed_by.is_(None))
                      .order_by(m.Fdr.id)).first()


def _set_maturity(fid: str, d: date) -> None:
    with SessionLocal() as db:
        db.get(m.Fdr, fid).maturity_date = d
        db.commit()


def _count(db, model, *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where))


# ---------------------------------------------------------------- templates and ladder
def test_every_template_is_bilingual_with_the_same_placeholders():
    for tid, langs in T.items():
        assert set(langs) == {"en", "hi"}, tid
        for part in ("title", "body", "sms"):
            en, hi = langs["en"][part], langs["hi"][part]
            assert en and hi and en != hi, (tid, part)
            assert placeholders(en) == placeholders(hi), (tid, part)
            assert any("ऀ" <= ch <= "ॿ" for ch in hi), (tid, part)   # Devanagari present


@pytest.mark.parametrize("days,overdue,rung", [(90, False, "info"), (31, False, "info"), (30, False, "action"), (8, False, "action"),
                                               (7, False, "deadline"), (1, False, "deadline"), (0, False, "deadline"), (-1, False, "overdue"),
                                               (40, True, "overdue")])
def test_rung_at_each_threshold(days, overdue, rung):
    assert rung_for(days, overdue, pol.defaults()) == rung


def test_day_boundary_is_ist_not_utc():
    p = pol.defaults()
    maturity = date(2026, 12, 2)
    late_utc = datetime(2026, 11, 1, 18, 29, tzinfo=timezone.utc)    # 23:59 IST on 1 Nov
    next_utc = datetime(2026, 11, 1, 18, 31, tzinfo=timezone.utc)    # 00:01 IST on 2 Nov
    assert ist_date(late_utc) == date(2026, 11, 1) and ist_date(next_utc) == date(2026, 11, 2)
    assert (maturity - ist_date(late_utc)).days == 31 and rung_for(31, False, p) == "info"
    assert (maturity - ist_date(next_utc)).days == 30 and rung_for(30, False, p) == "action"
    assert reminders.window_for(31, p) == "T-60" and reminders.window_for(30, p) == "T-30"
    assert reminders.window_for(-2, p) is None and reminders.window_for(-3, p) == "M+3"


# ---------------------------------------------------------------- reminders and scheduler
def test_daily_sweep_one_reminder_per_instrument_and_window(db_path):
    with SessionLocal() as db:
        fid = _fdr(db).id
    _set_maturity(fid, ist_date(DAY) + timedelta(days=30))
    with SessionLocal() as db:
        out = reminders.sweep(db, DAY)
        assert out["ran"] and out["reminders"] > 0
        n = db.scalars(select(m.Notification).where(m.Notification.key == f"rem:{fid}:T-30")).one()
        assert n.rung == "action" and n.window == "T-30" and n.audience == "institution:INST0001" and n.text_hi
        assert reminders.sweep(db, DAY + timedelta(hours=3))["ran"] is False            # same IST day: refused
        before = _count(db, m.Notification)
        again = reminders.sweep(db, DAY + timedelta(hours=3), force=True)               # forced re-run: keys still hold
        assert again["reminders"] == again["overdue"] == again["gaps"] == 0 and _count(db, m.Notification) == before
        reminders.sweep(db, DAY + timedelta(days=1))                                    # next day, still the T-30 window
        assert _count(db, m.Notification, m.Notification.ref == fid, m.Notification.key.like("rem:%")) == 1
        # deliveries: one per channel per recipient, planned once even if planned twice
        worker.plan(db, DAY)
        worker.plan(db, DAY)
        chans = sorted(db.scalars(select(m.NotificationDelivery.channel).where(m.NotificationDelivery.notification_id == n.id)))
        assert chans == ["email", "in_app"]


def test_scheduler_survives_restart_without_resending(db_path):
    from app import scheduler
    with SessionLocal() as db:
        fid = _fdr(db).id
    _set_maturity(fid, date.today() + timedelta(days=7))
    first = scheduler.job_daily_reminders()
    assert first["ran"]
    with SessionLocal() as db:
        n_before = _count(db, m.Notification)
        d_before = _count(db, m.NotificationDelivery)
        sim_before = _count(db, m.ProviderSimMessage)
    s1 = scheduler.build(start_paused=True)          # "restart": a new scheduler over the same job store
    job = s1.get_job("daily_reminders")
    assert job.next_run_time.tzinfo is not None and job.next_run_time.astimezone(IST).hour == 8
    s1.shutdown(wait=False)
    s2 = scheduler.build(start_paused=True)
    assert [j.id for j in s2.get_jobs()].count("daily_reminders") == 1
    s2.shutdown(wait=False)
    again = scheduler.job_daily_reminders()           # the restarted process fires today's job again
    assert again["ran"] is False
    with SessionLocal() as db:
        assert _count(db, m.Notification) == n_before and _count(db, m.NotificationDelivery) == d_before
        assert _count(db, m.ProviderSimMessage) == sim_before
        assert db.get(m.SchedulerRun, ("daily_reminders", ist_date(datetime.now(IST)).isoformat())).finished_at


# ---------------------------------------------------------------- outbox guarantees
def test_notice_is_written_with_its_event_or_not_at_all(db_path):
    with SessionLocal() as db:
        f = _fdr(db)
        fid = f.id
        f.discrepancy_reason = "crash test"
        notify(db, "institution:INST0001", "clarification_required", {"fdr_id": fid, "reason": "crash test"}, ref=fid, key="crash-1")
        db.flush()
        db.rollback()                                   # the process dies before commit
    with SessionLocal() as db:
        assert db.scalars(select(m.Notification).where(m.Notification.key == "crash-1")).first() is None
        assert db.get(m.Fdr, fid).discrepancy_reason != "crash test"


def test_crash_while_planning_loses_nothing_and_duplicates_nothing(db_path, monkeypatch):
    with SessionLocal() as db:
        n = notify(db, "aicte", "fdr_submitted", {"fdr_id": "FDRX", "institution": "X", "bank": "SBI"}, rung="action", key="plan-crash")
        db.commit()
        nid = n.id
    import app.nudge.worker as w
    real, calls = w.role_of, {"n": 0}

    def flaky(u, aud):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("worker killed mid-plan")
        return real(u, aud)
    monkeypatch.setattr(w, "role_of", flaky)
    with SessionLocal() as db, pytest.raises(RuntimeError):
        worker.plan(db, DAY)
    monkeypatch.setattr(w, "role_of", real)
    with SessionLocal() as db:
        worker.plan(db, DAY)
        aicte_users = _count(db, m.User, m.User.role == "AICTE_OFFICIAL")
        rows = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == nid)).all()
        assert len(rows) == aicte_users * 2                       # in-app + e-mail, each recipient exactly once
        assert len({(r.channel, r.user_id) for r in rows}) == len(rows)


def test_retry_after_crash_does_not_send_twice(db_path):
    with SessionLocal() as db:
        n = notify(db, "institution:INST0001", "clarification_required", {"fdr_id": "FDRX", "reason": "r"}, rung="deadline", key="retry-1")
        db.commit()
        worker.plan(db, DAY)
        with pytest.raises(RuntimeError):
            worker.send_due(db, DAY, crash_after_provider="email")   # provider called, process dies before recording it
    with SessionLocal() as db:
        stuck = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == n.id,
                                                                m.NotificationDelivery.status == "sending")).all()
        assert len(stuck) == 1
        stuck_id = stuck[0].id
        worker.send_due(db, DAY + timedelta(seconds=30))                          # lease still held: nobody else takes it
        assert db.get(m.NotificationDelivery, stuck_id).status == "sending"
        worker.send_due(db, DAY + timedelta(minutes=5))                           # lease expired: retried with the same key
        sims = db.scalars(select(m.ProviderSimMessage).where(m.ProviderSimMessage.idempotency_key.like(f"n{n.id}-%"))).all()
        dels = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == n.id)).all()
        assert {d.status for d in dels} <= {"sent", "delivered"}
        assert len(sims) == len([d for d in dels if d.channel != "in_app"])       # one provider message per delivery
        assert max(s.calls for s in sims) == 2                                     # the retried one was called twice, sent once


# ---------------------------------------------------------------- quiet hours and digest
def test_quiet_hours_defer_sms_but_not_overdue(db_path):
    night = datetime(2026, 11, 2, 21, 30, tzinfo=IST)
    with SessionLocal() as db:
        a = notify(db, "institution:INST0001", "clarification_required", {"fdr_id": "F1", "reason": "x"}, rung="deadline", key="q-deadline")
        b = notify(db, "institution:INST0001", "reminder_missed_renewal", {"fdr_id": "F2", "days": 5}, rung="overdue", key="q-overdue")
        db.commit()
        worker.run_once(db, night)
        sms_a = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == a.id, m.NotificationDelivery.channel == "sms")).one()
        email_a = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == a.id, m.NotificationDelivery.channel == "email")).one()
        sms_b = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == b.id, m.NotificationDelivery.channel == "sms")).one()
        assert sms_a.status == "deferred" and sms_a.next_attempt_at == "2026-11-03T08:00:00"
        assert email_a.status == "sent" and sms_b.status == "sent"
        whats_b = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == b.id, m.NotificationDelivery.channel == "whatsapp")).one()
        assert whats_b.status == "sent"
        worker.send_due(db, datetime(2026, 11, 3, 7, 59, tzinfo=IST))
        db.refresh(sms_a)
        assert sms_a.status == "deferred"
        worker.send_due(db, datetime(2026, 11, 3, 8, 0, tzinfo=IST))
        db.refresh(sms_a)
        assert sms_a.status == "sent"


def test_informational_items_batch_into_one_digest_per_user_per_day(db_path):
    with SessionLocal() as db:
        for i in range(3):
            notify(db, "institution:INST0001", "fdr_verified", {"fdr_id": f"FDRD{i}"}, rung="info", key=f"dg-{i}")
        db.commit()
        worker.plan(db, DAY)
        batched = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.status == "batched")).all()
        assert len(batched) == 3
        assert worker.digest(db, DAY) == 1
        assert worker.digest(db, DAY + timedelta(hours=2)) == 0        # nothing left, and the day's key is taken
        dg = db.scalars(select(m.Notification).where(m.Notification.template == "digest")).one()
        assert dg.params["count"] == 3 and "FDRD0" in dg.text and dg.text_hi
        assert {d.status for d in db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.id.in_([b.id for b in batched])))} == {"digested"}
        worker.run_once(db, DAY)
        assert db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id == dg.id)).one().status == "delivered"


# ---------------------------------------------------------------- escalation and acknowledgement
def _overdue_notice(db, fid: str, at: datetime) -> m.Notification:
    _set_maturity(fid, ist_date(at) - timedelta(days=4))
    reminders.sweep(db, at)
    return db.scalars(select(m.Notification).where(m.Notification.key == f"rem:{fid}:M+3")).one()


def test_overdue_is_copied_up_the_chain_once_per_step(db_path):
    with SessionLocal() as db:
        fid = _fdr(db).id
        n = _overdue_notice(db, fid, DAY)
        assert n.rung == "overdue"
        copy1 = db.scalars(select(m.Notification).where(m.Notification.key == f"esc:{n.id}:1")).one()
        assert copy1.audience == "aicte" and copy1.escalation_step == 1 and copy1.parent_id == n.id
        escalation.sweep(db, DAY + timedelta(days=1))                                  # before step_after_days
        assert db.scalars(select(m.Notification).where(m.Notification.key == f"esc:{n.id}:2")).first() is None
        escalation.sweep(db, DAY + timedelta(days=3))
        copy2 = db.scalars(select(m.Notification).where(m.Notification.key == f"esc:{n.id}:2")).one()
        assert copy2.audience == "competent_authority" and copy2.parent_id == copy1.id
        for d in (4, 5, 9):
            escalation.sweep(db, DAY + timedelta(days=d))                              # end of the chain: fires once
        assert _count(db, m.Notification, m.Notification.key.like(f"esc:{n.id}:%")) == 2
        steps = [json.loads(e.data) for e in db.scalars(select(m.PortalEvent).where(m.PortalEvent.type == "notification_escalated"))]
        assert [s["step"] for s in steps if s.get("ref") == fid] == [1, 2]


def test_acknowledgement_stops_escalation(db_path):
    with SessionLocal() as db:
        fid = _fdr(db).id
        n = _overdue_notice(db, fid, DAY)
        inst_user = db.scalars(select(m.User).where(m.User.institution_id == "INST0001")).first()
        worker.acknowledge(db, n, inst_user, "open", DAY + timedelta(hours=5))
        out = escalation.sweep(db, DAY + timedelta(days=6))
        assert out["stopped_by_ack"] >= 1
        assert db.scalars(select(m.Notification).where(m.Notification.key == f"esc:{n.id}:2")).first() is None
        assert db.scalars(select(m.Notification).where(m.Notification.key == f"up:{n.id}")).first() is None


def test_unacknowledged_notice_climbs_one_rung_once(db_path):
    with SessionLocal() as db:
        n = notify(db, "institution:INST0001", "clarification_required", {"fdr_id": "FDRQ", "reason": "x"}, rung="action", key="climb", at="2026-11-02T09:00:00")
        db.commit()
        escalation.sweep(db, DAY + timedelta(days=6))
        assert db.scalars(select(m.Notification).where(m.Notification.key == f"up:{n.id}")).first() is None
        escalation.sweep(db, DAY + timedelta(days=7))
        up = db.scalars(select(m.Notification).where(m.Notification.key == f"up:{n.id}")).one()
        assert up.rung == "deadline" and up.parent_id == n.id and "FDRQ" in up.text and up.text_hi
        escalation.sweep(db, DAY + timedelta(days=8))
        assert _count(db, m.Notification, m.Notification.parent_id == n.id) == 1


# ---------------------------------------------------------------- action links
def test_action_links_refuse_expired_reused_forged_and_wrong_user(db_path):
    with SessionLocal() as db:
        u = db.scalars(select(m.User).where(m.User.username == ABC)).one()
        other = db.scalars(select(m.User).where(m.User.username == XYZ)).one()
        n = notify(db, "institution:INST0001", "fdr_verified", {"fdr_id": "FDRL"}, rung="info", key="link-n")
        db.flush()
        tok = links.issue(db, u.id, "/institution/fdr/FDRL", "open", n.id, DAY, ttl_hours=2)
        db.commit()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            links.resolve(db, tok, other, DAY)
        assert e.value.status_code == 403
        forged = tok[:-3] + ("AAA" if not tok.endswith("AAA") else "BBB")
        with pytest.raises(HTTPException) as e:
            links.resolve(db, forged, u, DAY)
        assert e.value.status_code == 400
        with pytest.raises(HTTPException) as e:
            links.resolve(db, tok, u, DAY + timedelta(hours=3))
        assert e.value.status_code == 410
        ok = links.resolve(db, tok, u, DAY + timedelta(minutes=5))
        assert ok["path"] == "/institution/fdr/FDRL" and ok["acknowledged"] and ok["step_up"] is None
        assert db.get(m.Notification, n.id).ack_via == "link"
        with pytest.raises(HTTPException) as e:
            links.resolve(db, tok, u, DAY + timedelta(minutes=6))
        assert e.value.status_code == 409
        assert _count(db, m.PortalEvent, m.PortalEvent.type == "action_link_refused") == 4
        assert db.scalars(select(m.ActionToken).where(m.ActionToken.token_hash == tok)).first() is None   # only the hash is stored


def test_approval_link_opens_but_never_approves(api):
    meera = api().login(MEERA, OFF, "totp")
    rr = next(r for r in meera.get("/api/release-requests").json()["items"] if r["stage"] == "SUBMITTED")
    with SessionLocal() as db:                       # as if the section officer had finished scrutiny
        db.get(m.ReleaseRequest, rr["id"]).stage = "SCRUTINY_DONE"
        db.commit()
    with SessionLocal() as db:
        uid = db.scalars(select(m.User.id).where(m.User.username == MEERA)).one()
        tok = links.issue(db, uid, f"/aicte/releases/{rr['id']}", "approve")
        db.commit()
    r = meera.post("/api/nudge/links/resolve", json={"token": tok}).json()
    assert r["step_up"] == "dsc" and r["action"] == "approve"
    assert meera.get(f"/api/release-requests/{rr['id']}").json()["stage"] == "SCRUTINY_DONE"
    bad = meera.post(f"/api/release-requests/{rr['id']}/approve", json={"certificate_pem": "x", "signature_b64": "y"})
    assert bad.status_code in (400, 401, 403, 422)
    assert meera.get(f"/api/release-requests/{rr['id']}").json()["stage"] == "SCRUTINY_DONE"


def test_link_resolve_needs_a_signed_in_session(api):
    a = api()
    assert a.post("/api/nudge/links/resolve", json={"token": "x" * 20}).status_code == 401


# ---------------------------------------------------------------- policy, centre, insights, audit
def test_policy_windows_editable_by_aicte_only(api, db_path):
    inst = api().login(ABC, INS)
    cur = inst.get("/api/nudge/policy").json()["policy"]
    new = json.loads(json.dumps(cur))
    new["reminders"]["before_maturity_days"] = [90, 45, 30, 7]
    assert inst.put("/api/nudge/policy", json={"policy": new, "reason": "try to change"}).status_code == 403
    aud = api().login(AUDITOR, AUD, "totp")
    assert aud.put("/api/nudge/policy", json={"policy": new, "reason": "try to change"}).status_code == 403
    off = api().login(KIRAN, OFF, "totp")
    broken = json.loads(json.dumps(new))
    broken["channels"]["overdue"] = ["in_app"]
    assert off.put("/api/nudge/policy", json={"policy": broken, "reason": "fewer channels"}).status_code == 422
    r = off.put("/api/nudge/policy", json={"policy": new, "reason": "add a 45-day window for this cycle"})
    assert r.status_code == 200 and r.json()["version"] == 1
    with SessionLocal() as db:
        fid = _fdr(db).id
    _set_maturity(fid, ist_date(DAY) + timedelta(days=44))
    with SessionLocal() as db:
        reminders.sweep(db, DAY)
        assert db.scalars(select(m.Notification).where(m.Notification.key == f"rem:{fid}:T-45")).first()
        assert db.scalars(select(m.PortalEvent).where(m.PortalEvent.type == "notify_policy_changed")).first()


def test_centre_open_acknowledges_and_health_measures(api):
    a = api().login(ABC, INS)
    with SessionLocal() as db:
        n = notify(db, "institution:INST0001", "clarification_required", {"fdr_id": "FDRC", "reason": "x"}, rung="action", key="centre-1")
        db.commit()
        worker.run_once(db)
    c = a.get("/api/nudge/centre").json()
    item = next(i for i in c["items"] if i["id"] == n.id)
    assert item["rung"] == "action" and {d["channel"] for d in item["deliveries"]} == {"in_app", "email"}
    assert any(d["simulated"] for d in item["deliveries"] if d["channel"] == "email")
    assert c["open_by_rung"]["action"] >= 1
    assert a.post(f"/api/nudge/notifications/{n.id}/open").json()["first"] is True
    assert a.post(f"/api/nudge/notifications/{n.id}/open").json()["first"] is False
    assert api().login(XYZ, INS).post(f"/api/nudge/notifications/{n.id}/open").status_code == 404
    assert a.get("/api/nudge/health").status_code == 403
    h = api().login(MEERA, OFF, "totp").get("/api/nudge/health").json()
    assert h["totals"]["acknowledged"] >= 1 and h["by_channel"]["email"]["simulated"] >= 1
    assert h["by_channel"]["email"].get("delivered_receipt", 0) == 0      # simulated sends are never counted as delivered
    # A delivery whose status is already "sent" must not also increment the same counter twice.
    with SessionLocal() as db:
        ids = select(m.Notification.id).where(m.Notification.at >= h["since"], m.Notification.template.is_not(None))
        deliveries = db.scalars(select(m.NotificationDelivery).where(m.NotificationDelivery.notification_id.in_(ids))).all()
        for channel, counts in h["by_channel"].items():
            expected = sum(1 for d in deliveries if d.channel == channel and d.status != "digested"
                           and (d.sent_at or d.status in ("sent", "delivered")))
            assert counts.get("sent", 0) == expected
            assert counts.get("sent", 0) <= counts["total"]
    row = next(r for r in h["per_institution"] if r["institution_id"] == "INST0001")
    assert row["acknowledged"] >= 1 and row["median_hours_to_action"] is not None


def test_what_changed_since_last_login(api):
    abc = api().login(ABC, INS)
    first = abc.get("/api/nudge/what-changed").json()
    assert first["first_visit"] is True
    with SessionLocal() as db:
        fid = _fdr(db, "INST0001", "pending").id
    meera = api().login(MEERA, OFF, "totp")
    assert meera.post(f"/api/fdrs/{fid}/discrepancy", json={"reason": "lien letter unsigned"}).status_code == 200
    again = api().login(ABC, INS).get("/api/nudge/what-changed").json()
    assert again["first_visit"] is False
    item = next(i for i in again["items"] if i["type"] == "fdr_discrepancy_flagged")
    assert item["count"] == 1 and fid in item["examples"]
    other = api().login(XYZ, INS).get("/api/nudge/what-changed").json()
    assert not any(fid in i["examples"] for i in other["items"])       # another institution does not see it


def test_deliveries_audited_with_role_not_number(db_path):
    with SessionLocal() as db:
        notify(db, "institution:INST0001", "reminder_missed_renewal", {"fdr_id": "FDRA", "days": 4}, rung="overdue", key="aud-1")
        db.commit()
        worker.run_once(db, DAY)
        evs = [json.loads(e.data) for e in db.scalars(select(m.PortalEvent).where(m.PortalEvent.type == "notification_delivery"))]
        assert {e["channel"] for e in evs} >= {"in_app", "email", "sms", "whatsapp", "push"}
        assert all(e["recipient_role"].startswith(("institution:", "aicte_official:", "auditor:")) for e in evs)
        raw = json.dumps(evs)
        assert "+91" not in raw and "@" not in raw
        assert any(e["status"].endswith("(SIMULATED)") for e in evs if e["channel"] == "sms")
