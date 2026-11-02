from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import SystemLog, User

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def list_logs(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    type: str | None = None,
    status: str | None = None,
    campaign_id: UUID | None = None,
    date: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    query = db.query(SystemLog)
    if type:
        query = query.filter(SystemLog.type == type)
    if status:
        query = query.filter(SystemLog.status == status)
    if campaign_id:
        query = query.filter(SystemLog.campaign_id == campaign_id)
    if date:
        start = datetime.fromisoformat(date)
        query = query.filter(SystemLog.created_at >= start)
    query = query.order_by(SystemLog.created_at.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "items": [
            {
                "id": str(row.id),
                "timestamp": row.created_at.isoformat() if row.created_at else None,
                "type": row.type,
                "action": row.action,
                "campaign_id": str(row.campaign_id) if row.campaign_id else None,
                "status": row.status,
                "message": row.message,
            }
            for row in rows
        ],
    }
