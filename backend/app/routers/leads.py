from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import FollowUp, Lead, LeadEvidence, PropertyLocation, SavedFilter, SalesActivity, User
from ..schemas import BulkLeadUpdate, LeadPatch, ReviewAction, SavedFilterIn
from ..services.leads import apply_lead_filters, apply_status_change, lead_to_dict, record_activity, sort_leads
from ..services.scoring import apply_derived_fields
from ..services.taxonomy import PROPERTY_TYPES

router = APIRouter(prefix="/api/leads", tags=["leads"])


@router.get("")
def list_leads(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    search: str | None = None,
    priority: str | None = None,
    sales_status: str | None = None,
    property_type: str | None = None,
    city: str | None = None,
    country: str | None = None,
    campaign_id: UUID | None = None,
    qualification_status: str | None = None,
    view: str | None = None,
    sales_priority: str | None = None,
    research_status: str | None = None,
    min_contactability: int | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    has_email: str | None = None,
    has_phone: str | None = None,
    has_website: str | None = None,
    has_decision_maker: str | None = None,
    multi_property: str | None = None,
    estimated_properties: str | None = None,
    current_software: str | None = None,
    sort: str = "overall_score",
    direction: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    params = {
        "search": search,
        "priority": priority,
        "sales_status": sales_status,
        "property_type": property_type,
        "city": city,
        "country": country,
        "campaign_id": campaign_id,
        "qualification_status": qualification_status,
        "view": view,
        "sales_priority": sales_priority,
        "research_status": research_status,
        "min_contactability": min_contactability,
        "min_score": min_score,
        "max_score": max_score,
        "has_email": has_email,
        "has_phone": has_phone,
        "has_website": has_website,
        "has_decision_maker": has_decision_maker,
        "multi_property": multi_property,
        "estimated_properties": estimated_properties,
        "current_software": current_software,
    }
    query = apply_lead_filters(db.query(Lead), params)
    query = sort_leads(query, sort, direction)
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    cities = [r[0] for r in db.query(Lead.city).distinct().order_by(Lead.city.asc()).all() if r[0]]
    types = [r[0] for r in db.query(Lead.property_type).distinct().order_by(Lead.property_type.asc()).all() if r[0]]
    return {
        "items": [lead_to_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "facets": {"cities": cities, "property_types": PROPERTY_TYPES, "raw_property_types": types},
    }


@router.get("/filters")
def list_saved_filters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(SavedFilter).filter((SavedFilter.user_id == user.id) | (SavedFilter.is_system.is_(True))).all()
    return [{"id": str(row.id), "name": row.name, "filters": row.filters, "is_system": row.is_system} for row in rows]


@router.post("/filters")
def save_filter(payload: SavedFilterIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = SavedFilter(user_id=user.id, name=payload.name, filters=payload.filters)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "name": row.name, "filters": row.filters}


@router.get("/{lead_id}")
def get_lead(lead_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    activity = (
        db.query(SalesActivity)
        .filter(SalesActivity.lead_id == lead.id)
        .order_by(SalesActivity.created_at.desc())
        .limit(20)
        .all()
    )
    data = lead_to_dict(lead)
    evidence = db.query(LeadEvidence).filter(LeadEvidence.lead_id == lead.id).order_by(LeadEvidence.created_at.desc()).all()
    locations = db.query(PropertyLocation).filter(PropertyLocation.company_id == lead.company_id).all() if lead.company_id else []
    data["locations"] = [
        {"id": str(item.id), "name": item.name, "city": item.city, "address": item.address, "google_maps_url": item.google_maps_url}
        for item in locations
    ]
    data["sales_account"] = {
        "company_name": lead.company_name,
        "location_count": lead.location_count,
        "grouping_status": lead.grouping_status,
    } if lead.company_name else None
    data["evidence"] = [
        {
            "id": str(item.id),
            "evidence_type": item.evidence_type,
            "evidence_source": item.evidence_source,
            "evidence_text": item.evidence_text,
            "evidence_url": item.evidence_url,
        }
        for item in evidence
    ]
    data["activity"] = [
        {
            "id": str(item.id),
            "action": item.action,
            "from_status": item.from_status,
            "to_status": item.to_status,
            "note": item.note,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in activity
    ]
    return data


@router.patch("/{lead_id}")
def patch_lead(lead_id: UUID, payload: LeadPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    data = payload.model_dump(exclude_unset=True)
    if "sales_status" in data and data["sales_status"] and data["sales_status"] != lead.sales_status:
        apply_status_change(db, lead, data["sales_status"], user.id)
        data.pop("sales_status", None)
    if "next_followup_at" in data:
        follow = FollowUp(lead_id=lead.id, due_at=data["next_followup_at"], notes=lead.notes or "", created_by=user.id)
        db.add(follow)
    manual_fields = {"priority", "property_type", "estimated_property_count", "decision_maker_name", "decision_maker_role", "decision_maker_email", "decision_maker_phone", "decision_maker_linkedin"}
    for key, value in data.items():
        previous = getattr(lead, key, None)
        setattr(lead, key, value)
        if key in manual_fields:
            if key == "priority":
                lead.priority_source = "manual"
                lead.qualification_source = "manual"
            if key == "property_type":
                lead.property_type_source = "manual"
            if key == "estimated_property_count":
                lead.estimated_property_count_source = "manual"
            if previous != value:
                record_activity(db, lead, action=f"manual:{key}", user_id=user.id, from_status=str(previous or ""), to_status=str(value or ""))
    score_fields = {
        "priority",
        "property_type",
        "estimated_property_count",
        "email",
        "phone",
        "website",
        "decision_maker_name",
        "decision_maker_email",
        "decision_maker_phone",
    }
    apply_derived_fields(lead, overwrite_scores=bool(score_fields & set(data)), allow_priority_promote=False)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead_to_dict(lead)


@router.post("/{lead_id}/status/{status}")
def mark_status(lead_id: UUID, status: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    allowed = {"new", "qualified", "contacted", "replied", "trial", "customer", "lost"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid status")
    return lead_to_dict(apply_status_change(db, lead, status, user.id))


@router.post("/{lead_id}/review")
def review_lead(lead_id: UUID, payload: ReviewAction, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if payload.action == "reject":
        lead.priority = "C"
        lead.priority_source = "manual"
        lead.qualification_source = "manual"
        lead.needs_review = False
    elif payload.action == "approve":
        lead.needs_review = False
        if payload.priority:
            lead.priority = payload.priority
            lead.priority_source = "manual"
        if payload.property_type:
            lead.property_type = payload.property_type
            lead.property_type_source = "manual"
    elif payload.action == "edit":
        if payload.priority:
            lead.priority = payload.priority
            lead.priority_source = "manual"
        if payload.property_type:
            lead.property_type = payload.property_type
            lead.property_type_source = "manual"
        lead.needs_review = False
    if payload.notes:
        lead.notes = payload.notes if not lead.notes else f"{lead.notes}\n{payload.notes}"
    apply_derived_fields(lead, overwrite_scores=True, allow_priority_promote=False)
    record_activity(db, lead, action=f"review:{payload.action}", user_id=user.id, note=payload.notes or "")
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead_to_dict(lead)


@router.post("/bulk")
def bulk_update(payload: BulkLeadUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    leads = db.query(Lead).filter(Lead.id.in_(payload.lead_ids)).all()
    for lead in leads:
        if payload.sales_status:
            apply_status_change(db, lead, payload.sales_status, user.id)
        if payload.priority:
            lead.priority = payload.priority.upper()
        if payload.assigned_to:
            lead.assigned_to = payload.assigned_to
        db.add(lead)
    db.commit()
    return {"updated": len(leads)}


@router.post("/bulk-delete")
def bulk_delete(payload: BulkLeadUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete leads")
    count = db.query(Lead).filter(Lead.id.in_(payload.lead_ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": count}
