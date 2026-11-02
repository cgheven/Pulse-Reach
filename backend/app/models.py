from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import get_settings
from .database import Base

SCHEMA = get_settings().db_schema


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(50), default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    market: Mapped[str] = mapped_column(String(100), default="UK")
    country: Mapped[str] = mapped_column(String(100), default="United Kingdom")
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    searches: Mapped[list[CampaignSearch]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    jobs: Mapped[list[Job]] = relationship(back_populates="campaign")


class CampaignSearch(Base):
    __tablename__ = "campaign_searches"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    campaign_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.campaigns.id", ondelete="CASCADE"), index=True)
    city: Mapped[str] = mapped_column(String(150), index=True)
    category: Mapped[str] = mapped_column(String(150))
    result_limit: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    query_text: Mapped[str] = mapped_column(Text, default="")
    a_plus_count: Mapped[int] = mapped_column(Integer, default=0)
    a_count: Mapped[int] = mapped_column(Integer, default=0)
    b_count: Mapped[int] = mapped_column(Integer, default=0)
    c_count: Mapped[int] = mapped_column(Integer, default=0)
    contactable_count: Mapped[int] = mapped_column(Integer, default=0)
    quality_score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign: Mapped[Campaign] = relationship(back_populates="searches")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("idx_leads_priority", "priority"),
        Index("idx_leads_sales_status", "sales_status"),
        Index("idx_leads_city", "city"),
        Index("idx_leads_country", "country"),
        Index("idx_leads_property_type", "property_type"),
        Index("idx_leads_place_id", "place_id"),
        Index("idx_leads_google_id", "google_id"),
        Index("idx_leads_norm_website", "normalized_website"),
        Index("idx_leads_norm_name_city", "normalized_name_city"),
        Index("idx_leads_followup", "next_followup_at"),
        Index("idx_leads_campaign", "campaign_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    place_id: Mapped[str] = mapped_column(String(255), default="")
    google_id: Mapped[str] = mapped_column(String(255), default="")
    name: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(255), default="")
    subtypes: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    phone: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(150), default="")
    postal_code: Mapped[str] = mapped_column(String(50), default="")
    country: Mapped[str] = mapped_column(String(150), default="")
    rating: Mapped[float | None] = mapped_column(Float)
    reviews: Mapped[int | None] = mapped_column(Integer)
    business_status: Mapped[str] = mapped_column(String(100), default="")
    google_maps_url: Mapped[str] = mapped_column(Text, default="")
    query: Mapped[str] = mapped_column(Text, default="")
    linkedin: Mapped[str] = mapped_column(String(500), default="")
    facebook: Mapped[str] = mapped_column(String(500), default="")
    instagram: Mapped[str] = mapped_column(String(500), default="")
    relevant: Mapped[str] = mapped_column(String(20), default="")
    priority: Mapped[str] = mapped_column(String(10), default="")
    property_type: Mapped[str] = mapped_column(String(150), default="")
    estimated_property_count: Mapped[str] = mapped_column(String(100), default="")
    independent_operator: Mapped[str] = mapped_column(String(20), default="")
    ideal_customer: Mapped[str] = mapped_column(String(20), default="")
    claude_reason: Mapped[str] = mapped_column(Text, default="")
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sales_status: Mapped[str] = mapped_column(String(50), default="new")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"))
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, default="")
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.campaigns.id"))
    normalized_website: Mapped[str] = mapped_column(String(500), default="")
    normalized_name_city: Mapped[str] = mapped_column(String(500), default="")
    source_category: Mapped[str] = mapped_column(String(255), default="")
    source_subtypes: Mapped[str] = mapped_column(Text, default="")
    normalized_domain: Mapped[str] = mapped_column(String(255), default="")
    normalized_phone: Mapped[str] = mapped_column(String(50), default="")
    overall_score: Mapped[int | None] = mapped_column(Integer)
    icp_score: Mapped[int | None] = mapped_column(Integer)
    opportunity_score: Mapped[int | None] = mapped_column(Integer)
    contactability_score: Mapped[int | None] = mapped_column(Integer)
    estimated_property_count_min: Mapped[int | None] = mapped_column(Integer)
    estimated_property_count_max: Mapped[int | None] = mapped_column(Integer)
    estimated_bed_count: Mapped[str] = mapped_column(String(50), default="")
    scale_confidence: Mapped[str] = mapped_column(String(50), default="")
    multi_property_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    multi_property_evidence: Mapped[str] = mapped_column(Text, default="")
    current_software: Mapped[str] = mapped_column(String(255), default="")
    current_software_confidence: Mapped[str] = mapped_column(String(50), default="")
    software_evidence: Mapped[str] = mapped_column(Text, default="")
    fit_summary: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[str] = mapped_column(String(50), default="")
    decision_maker_name: Mapped[str] = mapped_column(String(255), default="")
    decision_maker_role: Mapped[str] = mapped_column(String(100), default="")
    decision_maker_email: Mapped[str] = mapped_column(String(255), default="")
    decision_maker_phone: Mapped[str] = mapped_column(String(100), default="")
    decision_maker_linkedin: Mapped[str] = mapped_column(String(500), default="")
    decision_maker_confidence: Mapped[str] = mapped_column(String(50), default="")
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.companies.id"))
    company_name: Mapped[str] = mapped_column(String(255), default="")
    company_domain: Mapped[str] = mapped_column(String(255), default="")
    location_count: Mapped[int] = mapped_column(Integer, default=1)
    grouping_status: Mapped[str] = mapped_column(String(50), default="Unknown")
    qualification_source: Mapped[str] = mapped_column(String(20), default="")
    priority_source: Mapped[str] = mapped_column(String(20), default="")
    property_type_source: Mapped[str] = mapped_column(String(20), default="")
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str] = mapped_column(Text, default="")
    website_research_status: Mapped[str] = mapped_column(String(50), default="")
    website_research_json: Mapped[dict | None] = mapped_column(JSONB)
    data_quality_score: Mapped[int | None] = mapped_column(Integer)
    sales_priority: Mapped[str] = mapped_column(String(20), default="")
    recommended_next_action: Mapped[str] = mapped_column(Text, default="")
    research_status: Mapped[str] = mapped_column(String(50), default="not_researched")
    multi_property_confidence: Mapped[str] = mapped_column(String(50), default="")
    estimated_property_count_source: Mapped[str] = mapped_column(String(20), default="")
    score_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    raw_json: Mapped[dict | None] = mapped_column(JSONB)
    # Directory view: simple, rule-based classification (see services/directory.py)
    accommodation_type: Mapped[str | None] = mapped_column(String(50))
    gender: Mapped[str | None] = mapped_column(String(20))
    mobile: Mapped[str] = mapped_column(String(100), default="")
    operator_key: Mapped[str] = mapped_column(String(255), default="")
    operator_name: Mapped[str] = mapped_column(String(255), default="")
    property_count: Mapped[int] = mapped_column(Integer, default=1)
    size_tier: Mapped[str] = mapped_column(String(20), default="Low")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class QualificationRun(Base):
    __tablename__ = "qualification_runs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.campaigns.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.jobs.id"))
    lead_count: Mapped[int] = mapped_column(Integer, default=0)
    a_plus_count: Mapped[int] = mapped_column(Integer, default=0)
    a_count: Mapped[int] = mapped_column(Integer, default=0)
    b_count: Mapped[int] = mapped_column(Integer, default=0)
    c_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SalesActivity(Base):
    __tablename__ = "sales_activity"
    __table_args__ = (
        Index("idx_activity_lead", "lead_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.leads.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"))
    action: Mapped[str] = mapped_column(String(100))
    from_status: Mapped[str] = mapped_column(String(50), default="")
    to_status: Mapped[str] = mapped_column(String(50), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FollowUp(Base):
    __tablename__ = "follow_ups"
    __table_args__ = (
        Index("idx_followups_due", "due_at"),
        Index("idx_followups_lead", "lead_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.leads.id", ondelete="CASCADE"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_type", "type"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="queued")
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.campaigns.id"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"))
    progress: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    logs: Mapped[list] = mapped_column(JSONB, default=list)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    campaign: Mapped[Campaign | None] = relationship(back_populates="jobs")


class ImportRecord(Base):
    __tablename__ = "imports"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(255))
    imported: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="completed")
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportRecord(Base):
    __tablename__ = "exports"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(255), default="")
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    file_path: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(50), default="queued")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemLog(Base):
    __tablename__ = "system_logs"
    __table_args__ = (
        Index("idx_logs_created", "created_at"),
        Index("idx_logs_type", "type"),
        Index("idx_logs_status", "status"),
        Index("idx_logs_campaign", "campaign_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(150))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.campaigns.id"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.jobs.id"))
    status: Mapped[str] = mapped_column(String(50), default="info")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("key", name="uq_app_settings_key"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(150), unique=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index("idx_companies_domain", "domain"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), default="")
    domain: Mapped[str] = mapped_column(String(255), default="")
    grouping_status: Mapped[str] = mapped_column(String(50), default="Unknown")
    location_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PropertyLocation(Base):
    __tablename__ = "properties_locations"
    __table_args__ = (
        Index("idx_properties_company", "company_id"),
        Index("idx_properties_lead", "lead_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.companies.id"))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.leads.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(500), default="")
    city: Mapped[str] = mapped_column(String(150), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    google_maps_url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeadEvidence(Base):
    __tablename__ = "lead_evidence"
    __table_args__ = (
        Index("idx_evidence_lead", "lead_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.leads.id", ondelete="CASCADE"))
    evidence_type: Mapped[str] = mapped_column(String(100), default="")
    evidence_source: Mapped[str] = mapped_column(String(100), default="")
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    evidence_url: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedFilter(Base):
    __tablename__ = "saved_filters"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey(f"{SCHEMA}.users.id"))
    name: Mapped[str] = mapped_column(String(150))
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
