from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Lead, User

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

COLUMNS = ["new", "qualified", "contacted", "replied", "trial", "customer", "lost"]


@router.get("")
def get_pipeline(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    leads = (
        db.query(Lead.id, Lead.name, Lead.property_type, Lead.category, Lead.city, Lead.priority, Lead.next_followup_at, Lead.sales_status)
        .order_by(Lead.updated_at.desc())
        .all()
    )
    columns = {status: [] for status in COLUMNS}
    for lead in leads:
        status = lead.sales_status if lead.sales_status in columns else "new"
        columns[status].append(
            {
                "id": str(lead.id),
                "name": lead.name,
                "property_type": lead.property_type or lead.category,
                "city": lead.city,
                "priority": lead.priority,
                "next_followup_at": lead.next_followup_at.isoformat() if lead.next_followup_at else None,
                "sales_status": lead.sales_status,
            }
        )
    return {"columns": columns}
