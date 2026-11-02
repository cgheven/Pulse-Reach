from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from .database import SessionLocal
from .models import Campaign, Job
from .services.campaigns import JobCancelled, run_campaign_job
from .services.import_export import build_export
from .services.logging_service import append_job_log, log_event

_stop = threading.Event()
_thread: threading.Thread | None = None


def start_worker() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="lead-engine-worker", daemon=True)
    _thread.start()


def stop_worker() -> None:
    _stop.set()


def _loop() -> None:
    while not _stop.is_set():
        try:
            _process_next()
        except Exception:
            time.sleep(1)
        time.sleep(0.5)


def _process_next() -> None:
    db = SessionLocal()
    try:
        job = (
            db.query(Job)
            .filter(Job.status == "queued")
            .order_by(Job.created_at.asc())
            .first()
        )
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        db.refresh(job)
        try:
            if job.type == "campaign_run":
                run_campaign_job(db, job)
            elif job.type == "export_csv":
                record = build_export(db, job.progress.get("filters") or {}, job.created_by)
                job.result = {"export_id": str(record.id), "row_count": record.row_count, "filename": record.filename}
                job.status = "completed"
                job.finished_at = datetime.now(timezone.utc)
                db.add(job)
                db.commit()
            else:
                raise RuntimeError(f"Unknown job type: {job.type}")
        except JobCancelled:
            job.status = "cancelled"
            job.finished_at = datetime.now(timezone.utc)
            if job.campaign_id:
                campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first()
                if campaign:
                    campaign.status = "cancelled"
                    db.add(campaign)
            db.add(job)
            db.commit()
            append_job_log(db, job, "Job cancelled")
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            if job.campaign_id:
                campaign = db.query(Campaign).filter(Campaign.id == job.campaign_id).first()
                if campaign:
                    campaign.status = "failed"
                    db.add(campaign)
            db.add(job)
            db.commit()
            append_job_log(db, job, f"Job failed: {exc}", "error")
            log_event(db, type="job", action="failed", message=str(exc), status="error", campaign_id=job.campaign_id, job_id=job.id)
    finally:
        db.close()
