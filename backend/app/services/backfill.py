from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Lead, LeadEvidence, SavedFilter
from .grouping import group_companies
from .scoring import apply_derived_fields

SMART_VIEWS = [
    ("Hot Prospects", {"view": "hot"}),
    ("A+ Prospects", {"priority": "A+"}),
    ("Multi-property Operators", {"view": "multi_property"}),
    ("Contactable", {"view": "contactable"}),
    ("2–10 Property Operators", {"view": "scale_2_10"}),
    ("Student Accommodation", {"property_type": "Student Accommodation"}),
    ("Hostels", {"property_type": "Hostel"}),
    ("HMO / Shared Accommodation", {"property_type": "HMO / Shared Accommodation"}),
    ("Missing Decision Maker", {"view": "missing_dm"}),
    ("Needs Research", {"view": "needs_research"}),
    ("Needs Review", {"view": "needs_review"}),
    ("Rejected", {"priority": "C"}),
]


def backfill_intelligence(db: Session) -> dict[str, int]:
    leads = db.query(Lead).all()
    for lead in leads:
        apply_derived_fields(lead, overwrite_scores=False, allow_priority_promote=False)
        if lead.priority and lead.claude_reason and not _has_evidence(db, lead.id, "qualification"):
            db.add(
                LeadEvidence(
                    lead_id=lead.id,
                    evidence_type="qualification",
                    evidence_source="claude",
                    evidence_text=lead.claude_reason,
                    evidence_url="",
                )
            )
        db.add(lead)
    db.commit()
    grouped = group_companies(db)
    scored = db.query(Lead).all()
    for lead in scored:
        apply_derived_fields(lead, overwrite_scores=True, allow_priority_promote=False)
        db.add(lead)
    db.commit()
    _seed_views(db)
    return {"leads": len(scored), "groups": grouped}


def _has_evidence(db: Session, lead_id, evidence_type: str) -> bool:
    return (
        db.query(LeadEvidence)
        .filter(LeadEvidence.lead_id == lead_id, LeadEvidence.evidence_type == evidence_type)
        .first()
        is not None
    )


def _seed_views(db: Session) -> None:
    for name, filters in SMART_VIEWS:
        row = db.query(SavedFilter).filter(SavedFilter.name == name, SavedFilter.is_system.is_(True)).first()
        if row:
            row.filters = filters
            continue
        db.add(SavedFilter(name=name, filters=filters, is_system=True))
    db.commit()
