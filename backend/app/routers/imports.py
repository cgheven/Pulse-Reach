from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ImportRecord, User
from ..services.directory import refresh_directory
from ..services.import_export import import_csv_text, import_existing_files

router = APIRouter(prefix="/api/leads", tags=["imports"])


def _record(row: ImportRecord) -> dict:
    return {
        "id": str(row.id),
        "filename": row.filename,
        "imported": row.imported,
        "updated": row.updated,
        "skipped": row.skipped,
        "duplicates": row.duplicates,
        "errors": row.errors,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/import")
async def import_leads(file: UploadFile = File(...), db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    text = (await file.read()).decode("utf-8-sig", errors="replace")
    record = import_csv_text(db, text, file.filename or "upload.csv")
    refresh_directory(db)
    return _record(record)


@router.post("/import/existing")
def import_bundled(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    records = import_existing_files(db)
    refresh_directory(db)
    return [_record(row) for row in records]


@router.get("/imports")
def list_imports(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.query(ImportRecord).order_by(ImportRecord.created_at.desc()).limit(50).all()
    return [_record(row) for row in rows]
