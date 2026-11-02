from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..models import Campaign, Job, User
from ..schemas import CampaignCreate, CampaignUpdate
from ..services.campaigns import campaign_to_dict, default_categories, enqueue_campaign_run, replace_searches
from ..services.dashboard import campaign_quality, campaign_quality_map

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("")
def list_campaigns(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(Campaign).options(selectinload(Campaign.searches)).order_by(Campaign.created_at.desc()).all()
    quality = campaign_quality_map(db, [row.id for row in rows])
    return [campaign_to_dict(row) | {"quality": quality[row.id]} for row in rows]


@router.post("")
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = Campaign(
        name=payload.name.strip(),
        market=payload.market,
        country=payload.country,
        created_by=user.id,
        status="draft",
    )
    categories = payload.categories or default_categories()
    cities = payload.cities or ["London"]
    replace_searches(db, campaign, cities, categories)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@router.get("/{campaign_id}")
def get_campaign(campaign_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    jobs = db.query(Job).filter(Job.campaign_id == campaign.id).order_by(Job.created_at.desc()).limit(10).all()
    data = campaign_to_dict(campaign)
    data["quality"] = campaign_quality(db, campaign.id)
    data["jobs"] = [
        {
            "id": str(job.id),
            "status": job.status,
            "type": job.type,
            "progress": job.progress,
            "error": job.error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
        for job in jobs
    ]
    return data


@router.patch("/{campaign_id}")
def update_campaign(campaign_id: UUID, payload: CampaignUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if payload.name:
        campaign.name = payload.name
    if payload.market:
        campaign.market = payload.market
    if payload.country:
        campaign.country = payload.country
    if payload.cities is not None or payload.categories is not None:
        cities = payload.cities or sorted({item.city for item in campaign.searches})
        categories = payload.categories or [{"category": item.category, "result_limit": item.result_limit} for item in campaign.searches]
        replace_searches(db, campaign, cities, categories)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign_to_dict(campaign)


@router.post("/{campaign_id}/run")
def run_campaign(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    active = (
        db.query(Job)
        .filter(Job.campaign_id == campaign.id, Job.status.in_(["queued", "running"]))
        .first()
    )
    if active:
        return {"job_id": str(active.id), "status": active.status}
    job = enqueue_campaign_run(db, campaign, user.id)
    return {"job_id": str(job.id), "status": job.status}


@router.post("/{campaign_id}/cancel")
def cancel_campaign(campaign_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    job = (
        db.query(Job)
        .filter(Job.campaign_id == campaign_id, Job.status.in_(["queued", "running"]))
        .order_by(Job.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No running campaign job")
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
    db.add(job)
    db.commit()
    return {"ok": True, "job_id": str(job.id)}


@router.post("/{campaign_id}/retry")
def retry_campaign(campaign_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    job = enqueue_campaign_run(db, campaign, user.id)
    return {"job_id": str(job.id), "status": job.status}
