from __future__ import annotations

from sqlalchemy.orm import Session

from .config import get_settings
from .models import Campaign, Lead, SavedFilter, User
from .security import hash_password
from .services.campaigns import default_categories, replace_searches
from .services.backfill import SMART_VIEWS, backfill_intelligence
from .services.directory import directory_needs_refresh, refresh_directory
from .services.import_export import import_existing_files
from .services.logging_service import log_event
from .services.settings_service import seed_settings


SYSTEM_VIEWS = SMART_VIEWS


def seed_admin(db: Session) -> User:
    settings = get_settings()
    user = db.query(User).filter(User.email == settings.admin_email.lower()).first()
    if user:
        return user
    user = User(
        email=settings.admin_email.lower(),
        password_hash=hash_password(settings.admin_password),
        name=settings.admin_name,
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_views(db: Session) -> None:
    for name, filters in SYSTEM_VIEWS:
        if db.query(SavedFilter).filter(SavedFilter.name == name, SavedFilter.is_system.is_(True)).first():
            continue
        db.add(SavedFilter(name=name, filters=filters, is_system=True))
    db.commit()


def seed_default_campaign(db: Session, user: User) -> None:
    if db.query(Campaign).first():
        return
    campaign = Campaign(
        name="UK – London Campaign",
        market="UK",
        country="United Kingdom",
        created_by=user.id,
        status="draft",
    )
    replace_searches(db, campaign, ["London"], default_categories())
    db.add(campaign)
    db.commit()


def bootstrap(db: Session) -> None:
    seed_settings(db)
    user = seed_admin(db)
    seed_views(db)
    if db.query(Lead).count() == 0:
        records = import_existing_files(db)
        imported = sum(item.imported + item.updated for item in records)
        log_event(
            db,
            type="import",
            action="auto_import",
            message=f"Imported bundled CSVs ({imported} rows processed)",
            status="success",
        )
    seed_default_campaign(db, user)
    if db.query(Lead).filter(Lead.overall_score.is_(None)).first():
        backfill_intelligence(db)
    if directory_needs_refresh(db):
        refresh_directory(db)
