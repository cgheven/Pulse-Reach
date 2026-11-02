from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ..models import Job, SystemLog


def log_event(
    db: Session,
    *,
    type: str,
    action: str,
    message: str,
    status: str = "info",
    campaign_id: UUID | None = None,
    job_id: UUID | None = None,
) -> None:
    db.add(
        SystemLog(
            type=type,
            action=action,
            message=message,
            status=status,
            campaign_id=campaign_id,
            job_id=job_id,
        )
    )
    db.commit()


def append_job_log(db: Session, job: Job, message: str, status: str = "info") -> None:
    logs = list(job.logs or [])
    logs.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "message": message,
        }
    )
    job.logs = logs
    db.add(job)
    db.commit()
    db.refresh(job)
