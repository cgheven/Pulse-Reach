from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from anthropic import Anthropic
from sqlalchemy.orm import Session

from ..models import Lead, LeadEvidence, QualificationRun
from ..schemas import QualificationBatch, QualificationResult
from .scoring import apply_derived_fields
from .taxonomy import normalize_property_type


class QualificationError(RuntimeError):
    pass


def system_prompt(market: str) -> str:
    return f"""
You qualify accommodation-operator leads for PulseHub, an accommodation management SaaS in the {market} market.

ALLOWED property_type values exactly:
Hostel, Student Accommodation, Guest House, Hotel, Co-living, HMO / Shared Accommodation, Boarding House, Other

ICP:
- Independent operator or small/mid operating company
- Actually operates accommodation
- Usually 1-10 properties
- Hostel, Student Accommodation, Guest House, Hotel, Co-living, HMO / Shared Accommodation, Boarding House
- Own website and public contact details increase score
- Multiple locations under one independent company increase score. Do not reject only because they have several sites.

REJECT / C:
- Universities, colleges, institutional PBSA
- Large national/international chains
- Charities and public bodies
- Estate agents, consultants, construction, software companies
- Accommodation that is incidental
- Irrelevant businesses

Return qualitative classification fields. Scores may be estimated; the server recalculates them.
estimated_property_count must be one of: 1, 2-3, 4-10, 10+, unknown
Do not invent people, exact property counts, or software.
Use unknown / empty when evidence is missing.
Return exactly one object per supplied lead_id and no extras.
""".strip()


def lead_prompt(lead: Lead) -> str:
    return f"""
lead_id: {lead.id}
Name: {lead.name}
Source category: {lead.source_category or lead.category}
Source subtypes: {lead.source_subtypes or lead.subtypes}
Website: {lead.website or "none"}
Phone: {lead.phone or "none"}
Email: {lead.email or "none"}
Address: {lead.address}
City: {lead.city}
Postcode: {lead.postal_code}
Rating: {lead.rating if lead.rating is not None else "unknown"}
Reviews: {lead.reviews if lead.reviews is not None else "unknown"}
Google Maps URL: {lead.google_maps_url}
Search query: {lead.query}
""".strip()


REQUIRED = (
    "lead_id",
    "relevant",
    "priority",
    "overall_score",
    "icp_score",
    "opportunity_score",
    "contactability_score",
    "property_type",
    "estimated_property_count",
    "independent_operator",
    "ideal_customer",
    "reason",
    "confidence",
)


def validate_batch(results: list[QualificationResult], expected_ids: list[str]) -> None:
    if not results:
        raise QualificationError("Claude returned no results")
    ids = [str(item.lead_id).strip() for item in results]
    if len(ids) != len(expected_ids):
        raise QualificationError(f"Claude returned {len(ids)} results for {len(expected_ids)} leads")
    if len(set(ids)) != len(ids):
        raise QualificationError("Claude returned duplicate lead_id values")
    missing = set(expected_ids) - set(ids)
    extra = set(ids) - set(expected_ids)
    if missing or extra:
        raise QualificationError(f"Claude lead_id mismatch. missing={sorted(missing)} extra={sorted(extra)}")
    for item in results:
        data = item.model_dump()
        for field in REQUIRED:
            if data.get(field) in (None, ""):
                raise QualificationError(f"Claude result missing required field: {field}")
        if str(item.priority).upper().replace(" ", "") not in {"A+", "A", "B", "C"}:
            raise QualificationError(f"Invalid priority {item.priority}")


def _call_claude(client: Anthropic, model: str, system: str, user: str, batch_size: int) -> list[QualificationResult]:
    response = client.messages.parse(
        model=model,
        max_tokens=max(1200, 450 * batch_size),
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=QualificationBatch,
    )
    parsed = response.parsed_output
    if not parsed:
        raise QualificationError("Claude returned invalid structured output")
    return parsed.results


def qualify_leads(
    db: Session,
    leads: list[Lead],
    *,
    api_key: str,
    model: str,
    market: str,
    batch_size: int = 10,
    delay_seconds: float = 0.2,
    campaign_id: UUID | None = None,
    job_id: UUID | None = None,
    should_cancel: Any | None = None,
    on_progress: Any | None = None,
) -> dict[str, int]:
    if not leads:
        return {"a_plus": 0, "a": 0, "b": 0, "c": 0, "total": 0}

    client = Anthropic(api_key=api_key)
    system = system_prompt(market)
    counts = {"a_plus": 0, "a": 0, "b": 0, "c": 0, "total": 0}
    run = QualificationRun(campaign_id=campaign_id, job_id=job_id, lead_count=len(leads), status="running")
    db.add(run)
    db.commit()

    try:
        for start in range(0, len(leads), batch_size):
            if should_cancel and should_cancel():
                run.status = "cancelled"
                db.commit()
                raise QualificationError("Qualification cancelled")
            batch = leads[start : start + batch_size]
            expected_ids = [str(lead.id) for lead in batch]
            numbered = "\n\n".join(lead_prompt(lead) for lead in batch)
            user = (
                f"Classify each lead independently.\n"
                f"Return exactly {len(batch)} results in the requested schema.\n"
                f"Each result must include the exact lead_id supplied below.\n\n{numbered}"
            )
            results: list[QualificationResult] | None = None
            last_error = ""
            for attempt in (1, 2):
                try:
                    prompt = user
                    if attempt == 2:
                        prompt = (
                            "Return exactly one result for every supplied lead_id, in the requested schema, with no additional records.\n\n"
                            + user
                        )
                    results = _call_claude(client, model, system, prompt, len(batch))
                    validate_batch(results, expected_ids)
                    break
                except Exception as exc:
                    last_error = str(exc)
                    results = None
                    if attempt == 2:
                        run.status = "failed"
                        run.error = last_error
                        db.commit()
                        raise QualificationError(last_error) from exc
            assert results is not None
            by_id = {str(item.lead_id): item for item in results}
            for lead in batch:
                if lead.priority_source == "manual" or lead.qualification_source == "manual":
                    counts["total"] += 1
                    continue
                _apply_result(db, lead, by_id[str(lead.id)])
                key = {"A+": "a_plus", "A": "a", "B": "b", "C": "c"}.get(lead.priority, "c")
                counts[key] += 1
                counts["total"] += 1
            db.commit()
            if on_progress:
                on_progress(counts)
            time.sleep(delay_seconds)
        run.a_plus_count = counts["a_plus"]
        run.a_count = counts["a"]
        run.b_count = counts["b"]
        run.c_count = counts["c"]
        run.status = "completed"
        db.commit()
        return counts
    except QualificationError:
        raise
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        db.commit()
        raise


def _apply_result(db: Session, lead: Lead, item: QualificationResult) -> None:
    priority = item.priority.upper().replace(" ", "")
    if priority not in {"A+", "A", "B", "C"}:
        priority = "C"
    lead.relevant = str(item.relevant).lower()
    if lead.priority_source != "manual":
        lead.priority = priority
    if lead.property_type_source != "manual":
        lead.property_type = normalize_property_type(item.property_type)
        lead.property_type_source = "ai"
    if lead.estimated_property_count_source != "manual":
        lead.estimated_property_count = item.estimated_property_count.strip()
        lead.estimated_property_count_min = item.estimated_property_count_min
        lead.estimated_property_count_max = item.estimated_property_count_max
        lead.estimated_bed_count = item.estimated_bed_count or ""
        lead.scale_confidence = item.scale_confidence or ""
    lead.independent_operator = str(item.independent_operator).lower()
    lead.ideal_customer = str(item.ideal_customer).lower()
    if item.multi_property_signal:
        lead.multi_property_signal = True
    lead.multi_property_confidence = item.multi_property_confidence or lead.multi_property_confidence
    if item.multi_property_evidence:
        lead.multi_property_evidence = item.multi_property_evidence
    if item.current_software and not lead.current_software:
        lead.current_software = item.current_software
        lead.current_software_confidence = item.current_software_confidence or ""
    lead.fit_summary = item.fit_summary or item.reason
    lead.claude_reason = item.reason.strip()
    lead.confidence = item.confidence
    lead.qualified_at = datetime.now(timezone.utc)
    if lead.qualification_source != "manual":
        lead.qualification_source = "ai"
    apply_derived_fields(lead, overwrite_scores=True, allow_priority_promote=False)
    if lead.sales_status == "new" and lead.priority in {"A+", "A", "B"}:
        lead.sales_status = "qualified"
    db.add(lead)
    db.add(
        LeadEvidence(
            lead_id=lead.id,
            evidence_type="qualification",
            evidence_source="claude",
            evidence_text=item.reason.strip(),
            evidence_url="",
        )
    )
