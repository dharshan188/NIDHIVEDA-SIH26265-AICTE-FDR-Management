"""/push: phones running the mobile app register here; the Nudge Ladder push channel sends to these devices."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..nudge.channels import provider
from ..db import get_db
from ..deps import Principal, current

router = APIRouter(prefix="/push", tags=["push notifications"])


class DeviceIn(BaseModel):
    token: str = Field(min_length=10, max_length=400)
    platform: str = Field(pattern="^(android|ios)$")


@router.post("/devices")
def register(body: DeviceIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    """Registers (or moves to this user) the phone's FCM token. A token belongs to one signed-in user at a time."""
    now = datetime.now()
    dev = db.scalars(select(m.PushDevice).where(m.PushDevice.token == body.token)).first()
    if dev:
        dev.user_id, dev.platform, dev.last_seen = p.user.id, body.platform, now
    else:
        db.add(m.PushDevice(user_id=p.user.id, token=body.token, platform=body.platform, created_at=now, last_seen=now))
    db.commit()
    return {"ok": True, "provider": provider("push").name, "simulated": provider("push").simulated}


@router.post("/devices/remove")
def unregister(body: DeviceIn, p: Principal = Depends(current), db: Session = Depends(get_db)):
    """Called on sign-out so the phone stops receiving this user's notifications."""
    db.execute(delete(m.PushDevice).where(m.PushDevice.token == body.token, m.PushDevice.user_id == p.user.id))
    db.commit()
    return {"ok": True}


@router.get("/status")
def status(p: Principal = Depends(current), db: Session = Depends(get_db)):
    n = db.scalar(select(func.count()).select_from(m.PushDevice).where(m.PushDevice.user_id == p.user.id))
    return {"provider": provider("push").name, "simulated": provider("push").simulated, "devices": n}
