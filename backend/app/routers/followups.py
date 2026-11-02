from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import FollowUp, Lead, User
from ..schemas import FollowUpCreate, FollowUpReschedule
from ..services.leads import lead_to_dict

router = APIRouter(prefix="/api/followups", tags=["followups"])


def _item(lead: Lead) -> dict:
    return {
        **lead_to_dict(lead),
        "business": lead.name,
        "status": lead.sales_status,
        "due_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
    }


@router.get("")
def list_followups(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = start_today + timedelta(days=1)
    leads = db.query(Lead).filter(Lead.next_followup_at.isnot(None)).order_by(Lead.next_followup_at.asc()).all()
    today, overdue, upcoming = [], [], []
    for lead in leads:
        due = lead.next_followup_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        item = _item(lead)
        if due < start_today:
            overdue.append(item)
        elif due < end_today:
            today.append(item)
        else:
            upcoming.append(item)
    return {"today": today, "overdue": overdue, "upcoming": upcoming}


@router.post("")
def create_followup(payload: FollowUpCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.next_followup_at = payload.due_at
    if payload.notes:
        lead.notes = payload.notes if not lead.notes else f"{lead.notes}\n{payload.notes}"
    db.add(FollowUp(lead_id=lead.id, due_at=payload.due_at, notes=payload.notes, created_by=user.id))
    db.add(lead)
    db.commit()
    return _item(lead)


@router.post("/{lead_id}/complete")
def complete_followup(lead_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    open_items = db.query(FollowUp).filter(FollowUp.lead_id == lead.id, FollowUp.completed_at.is_(None)).all()
    for item in open_items:
        item.completed_at = datetime.now(timezone.utc)
        db.add(item)
    lead.next_followup_at = None
    db.add(lead)
    db.commit()
    return {"ok": True}


@router.post("/{lead_id}/reschedule")
def reschedule(lead_id: UUID, payload: FollowUpReschedule, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.next_followup_at = payload.due_at
    if payload.notes is not None:
        lead.notes = payload.notes
    db.add(FollowUp(lead_id=lead.id, due_at=payload.due_at, notes=payload.notes or "", created_by=user.id))
    db.add(lead)
    db.commit()
    return _item(lead)
