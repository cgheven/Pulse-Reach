from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ExportRecord, User
from ..schemas import ExportRequest
from ..services.import_export import build_export

router = APIRouter(prefix="/api/leads", tags=["exports"])


@router.post("/export")
def export_leads(payload: ExportRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = build_export(db, payload.model_dump(exclude_none=True), user.id)
    return {
        "id": str(record.id),
        "filename": record.filename,
        "row_count": record.row_count,
        "status": record.status,
        "download_url": f"/api/leads/export/{record.id}/download",
    }


@router.get("/export/{export_id}")
def get_export(export_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    record = db.query(ExportRecord).filter(ExportRecord.id == export_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Export not found")
    return {
        "id": str(record.id),
        "filename": record.filename,
        "row_count": record.row_count,
        "status": record.status,
        "download_url": f"/api/leads/export/{record.id}/download",
    }


@router.get("/export/{export_id}/download")
def download_export(export_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    record = db.query(ExportRecord).filter(ExportRecord.id == export_id).first()
    if not record or not record.file_path:
        raise HTTPException(status_code=404, detail="Export not found")
    path = Path(record.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing")
    return FileResponse(path, filename=record.filename or path.name, media_type="text/csv")
