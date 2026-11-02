from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: str

    model_config = {"from_attributes": True}


class CampaignSearchIn(BaseModel):
    city: str
    category: str
    result_limit: int = Field(default=20, ge=1, le=500)


class CampaignCreate(BaseModel):
    name: str
    market: str = "UK"
    country: str = "United Kingdom"
    cities: list[str] = Field(default_factory=list)
    categories: list[dict[str, Any]] = Field(default_factory=list)


class CampaignUpdate(BaseModel):
    name: str | None = None
    market: str | None = None
    country: str | None = None
    cities: list[str] | None = None
    categories: list[dict[str, Any]] | None = None


class CampaignSearchOut(BaseModel):
    id: UUID
    city: str
    category: str
    result_limit: int
    status: str
    results_count: int

    model_config = {"from_attributes": True}


class CampaignOut(BaseModel):
    id: UUID
    name: str
    market: str
    country: str
    status: str
    last_run_at: datetime | None
    created_at: datetime
    searches: list[CampaignSearchOut] = []

    model_config = {"from_attributes": True}


class LeadPatch(BaseModel):
    sales_status: str | None = None
    assigned_to: UUID | None = None
    last_contacted_at: datetime | None = None
    next_followup_at: datetime | None = None
    notes: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    linkedin: str | None = None
    facebook: str | None = None
    instagram: str | None = None
    priority: str | None = None
    property_type: str | None = None
    estimated_property_count: str | None = None
    decision_maker_name: str | None = None
    decision_maker_role: str | None = None
    decision_maker_email: str | None = None
    decision_maker_phone: str | None = None
    decision_maker_linkedin: str | None = None
    needs_review: bool | None = None
    review_reason: str | None = None


class BulkLeadUpdate(BaseModel):
    lead_ids: list[UUID]
    sales_status: str | None = None
    priority: str | None = None
    assigned_to: UUID | None = None


class FollowUpCreate(BaseModel):
    lead_id: UUID
    due_at: datetime
    notes: str = ""


class FollowUpReschedule(BaseModel):
    due_at: datetime
    notes: str | None = None


class ExportRequest(BaseModel):
    preset: str | None = None
    priority: str | None = None
    sales_status: str | None = None
    property_type: str | None = None
    city: str | None = None
    country: str | None = None
    campaign_id: UUID | None = None
    search: str | None = None
    lead_ids: list[UUID] | None = None


class SavedFilterIn(BaseModel):
    name: str
    filters: dict[str, Any]


class SettingsUpdate(BaseModel):
    claude_model: str | None = None
    default_market: str | None = None
    default_country: str | None = None
    qualification: dict[str, Any] | None = None
    sales_statuses: list[str] | None = None
    property_types: list[str] | None = None
    search_categories: list[str] | None = None


class ApiKeysUpdate(BaseModel):
    outscraper_api_key: str | None = None
    anthropic_api_key: str | None = None


class UserCreate(BaseModel):
    email: str
    password: str
    name: str = ""
    role: str = "member"


class ReviewAction(BaseModel):
    action: str
    priority: str | None = None
    property_type: str | None = None
    notes: str | None = None


class QualificationResult(BaseModel):
    lead_id: str
    relevant: bool
    priority: str
    overall_score: int
    icp_score: int
    opportunity_score: int
    contactability_score: int
    data_quality_score: int = 0
    property_type: str
    estimated_property_count: str
    estimated_property_count_min: int | None = None
    estimated_property_count_max: int | None = None
    estimated_bed_count: str = "unknown"
    scale_confidence: str = "unknown"
    independent_operator: bool
    ideal_customer: bool
    multi_property_signal: bool = False
    multi_property_confidence: str = ""
    multi_property_evidence: str = ""
    current_software: str = ""
    current_software_confidence: str = ""
    fit_summary: str = ""
    reason: str
    confidence: str


class QualificationBatch(BaseModel):
    results: list[QualificationResult]
