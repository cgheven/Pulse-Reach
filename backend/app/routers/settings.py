from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import ApiKeysUpdate, SettingsUpdate
from ..services.backfill import backfill_intelligence
from ..services.settings_service import public_settings, set_value

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings_payload(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return public_settings(db)


@router.patch("")
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        set_value(db, key, value)
    return public_settings(db)


@router.post("/keys")
def update_keys(payload: ApiKeysUpdate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if payload.outscraper_api_key:
        set_value(db, "outscraper_api_key", payload.outscraper_api_key.strip())
    if payload.anthropic_api_key:
        set_value(db, "anthropic_api_key", payload.anthropic_api_key.strip())
    return public_settings(db)


@router.post("/recompute")
def recompute_intelligence(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return backfill_intelligence(db)
