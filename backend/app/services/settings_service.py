from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AppSetting

DEFAULTS: dict[str, Any] = {
    "claude_model": "claude-haiku-4-5-20251001",
    "default_market": "UK",
    "default_country": "United Kingdom",
    "qualification": {
        "batch_size": 10,
        "batch_delay_seconds": 0.2,
        "only_send_if_has_website": False,
    },
    "sales_statuses": ["new", "qualified", "contacted", "replied", "trial", "customer", "lost"],
    "property_types": [
        "Hostel",
        "Student Accommodation",
        "Guest House",
        "Hotel",
        "Co-living",
        "HMO / Shared Accommodation",
        "Boarding House",
        "Other",
    ],
    "search_categories": [
        "Hostel",
        "Student Accommodation",
        "HMO",
        "Co-living",
        "Guest House",
        "Boarding House",
        "Hotel",
        "Other",
    ],
}

SECRET_KEYS = {"outscraper_api_key", "anthropic_api_key"}


def _ensure_setting(db: Session, key: str, value: Any) -> None:
    existing = db.query(AppSetting).filter(AppSetting.key == key).first()
    if existing:
        return
    db.add(AppSetting(key=key, value={"value": value}))
    db.flush()


def seed_settings(db: Session) -> None:
    env = get_settings()
    values = dict(DEFAULTS)
    values["claude_model"] = env.claude_model or values["claude_model"]
    for key, value in values.items():
        _ensure_setting(db, key, value)
    existing_types = get_value(db, "property_types")
    if existing_types != DEFAULTS["property_types"]:
        set_value(db, "property_types", DEFAULTS["property_types"])
    if env.outscraper_api_key:
        _ensure_setting(db, "outscraper_api_key", env.outscraper_api_key)
    if env.anthropic_api_key:
        _ensure_setting(db, "anthropic_api_key", env.anthropic_api_key)
    db.commit()


def get_value(db: Session, key: str, default: Any = None) -> Any:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row:
        return DEFAULTS.get(key, default)
    return row.value.get("value", default)


def set_value(db: Session, key: str, value: Any) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = {"value": value}
    else:
        db.add(AppSetting(key=key, value={"value": value}))
    db.commit()


def public_settings(db: Session) -> dict[str, Any]:
    payload = {key: get_value(db, key) for key in DEFAULTS}
    out_key = get_value(db, "outscraper_api_key", "") or get_settings().outscraper_api_key
    claude_key = get_value(db, "anthropic_api_key", "") or get_settings().anthropic_api_key
    payload["api_keys"] = {
        "outscraper": _mask(out_key),
        "claude": _mask(claude_key),
    }
    return payload


def get_outscraper_key(db: Session) -> str:
    return (get_value(db, "outscraper_api_key", "") or get_settings().outscraper_api_key or "").strip()


def get_anthropic_key(db: Session) -> str:
    return (get_value(db, "anthropic_api_key", "") or get_settings().anthropic_api_key or "").strip()


def get_claude_model(db: Session) -> str:
    return (get_value(db, "claude_model") or get_settings().claude_model or "claude-haiku-4-5-20251001").strip()


def _mask(value: str) -> dict[str, Any]:
    value = (value or "").strip()
    if not value:
        return {"configured": False, "hint": ""}
    hint = f"••••{value[-4:]}" if len(value) >= 4 else "••••"
    return {"configured": True, "hint": hint}
