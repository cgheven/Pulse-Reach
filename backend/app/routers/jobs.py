from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Campaign, Job, User
from ..services.campaigns import enqueue_campaign_run

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(Job).order_by(Job.created_at.desc()).limit(50).all()
    return [
        {
            "id": str(job.id),
            "type": job.type,
            "status": job.status,
            "campaign_id": str(job.campaign_id) if job.campaign_id else None,
            "error": job.error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }
        for job in rows
    ]


@router.post("/{job_id}/retry")
def retry_job(job_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or not job.campaign_id:
        raise HTTPException(status_code=404, detail="Retryable job not found")
    campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    next_job = enqueue_campaign_run(db, campaign, user.id)
    return {"job_id": str(next_job.id), "status": next_job.status}


@router.get("/{job_id}")
def get_job(job_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": str(job.id),
        "type": job.type,
        "status": job.status,
        "campaign_id": str(job.campaign_id) if job.campaign_id else None,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
        "logs": job.logs,
        "cancel_requested": job.cancel_requested,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
