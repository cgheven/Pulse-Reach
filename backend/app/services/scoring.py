from __future__ import annotations

from ..models import Lead
from .taxonomy import (
    REJECT_HINTS,
    normalize_domain,
    normalize_phone,
    normalize_property_type,
    parse_property_bounds,
    property_bucket,
)

FIT_TYPES = {
    "Hostel",
    "Student Accommodation",
    "Guest House",
    "Hotel",
    "Co-living",
    "HMO / Shared Accommodation",
    "Boarding House",
}

CHAIN_HINTS = (
    "wombat",
    "generator hostel",
    "generator london",
    "meininger",
    "premier inn",
    "travelodge",
    "holiday inn",
    "ibis",
    "hilton",
    "marriott",
    "accor",
    "a&o",
    "a and o",
    "st christopher",
    "safestay",
    "clink",
    "yha",
    "hostelling international",
    "easyhotel",
    "citizenm",
    "point a",
    "the hoxton",
    "iq student",
    "scape ",
    "unite students",
    "chapter ",
    "fresh student",
    "vita student",
    "student roost",
    "crm students",
    "urbanest",
    "publove",
)

INSTITUTION_HINTS = (
    "university",
    "college",
    "campus",
    "students' union",
    "student union",
    "ucl ",
    "lse ",
    "king's college",
    "kings college",
    "imperial college",
    "council housing",
    "local authority",
    "charity",
    "nhs ",
)


def _blob(lead: Lead) -> str:
    return " ".join(
        str(part or "").lower()
        for part in (
            lead.name,
            lead.source_category,
            lead.source_subtypes,
            lead.category,
            lead.property_type,
            lead.claude_reason,
            lead.fit_summary,
        )
    )


def is_chain(lead: Lead) -> bool:
    text = _blob(lead)
    if any(hint in text for hint in CHAIN_HINTS):
        return True
    if (lead.location_count or 1) >= 10 and lead.independent_operator != "true":
        return True
    bucket = current_scale(lead)
    return bucket == "10+" and lead.independent_operator != "true"


def is_rejected_org(lead: Lead) -> bool:
    text = _blob(lead)
    if any(hint in text for hint in INSTITUTION_HINTS):
        return True
    if any(hint in text for hint in REJECT_HINTS) and lead.property_type == "Other":
        return True
    return False


def current_scale(lead: Lead) -> str:
    if lead.estimated_property_count_source == "manual" and lead.estimated_property_count:
        return property_bucket(lead.estimated_property_count_min, lead.estimated_property_count)
    locations = lead.location_count or 1
    if locations >= 10:
        return "10+"
    if locations >= 4:
        return "4–10"
    if locations >= 2:
        return "2–3"
    return property_bucket(lead.estimated_property_count_min, lead.estimated_property_count)


def apply_scale(lead: Lead) -> str:
    if lead.estimated_property_count_source == "manual":
        bucket = property_bucket(lead.estimated_property_count_min, lead.estimated_property_count)
        return bucket
    locations = lead.location_count or 1
    grouped = lead.grouping_status in {"Confirmed", "Probable"} and locations >= 2
    raw_bucket = property_bucket(lead.estimated_property_count_min, lead.estimated_property_count)
    if grouped:
        if locations >= 10:
            bucket = "10+"
        elif locations >= 4:
            bucket = "4–10"
        else:
            bucket = "2–3"
        lead.estimated_property_count = bucket
        lead.estimated_property_count_min = locations
        lead.estimated_property_count_max = locations if locations < 10 else None
        lead.scale_confidence = "High" if lead.grouping_status == "Confirmed" else "Medium"
        lead.multi_property_signal = True
        lead.multi_property_confidence = "High" if lead.grouping_status == "Confirmed" else "Medium"
        if not lead.multi_property_evidence:
            lead.multi_property_evidence = f"{locations} Google listings grouped as {lead.grouping_status.lower()} same operator"
        return bucket
    if lead.multi_property_signal and raw_bucket in {"2–3", "4–10", "10+"}:
        lead.estimated_property_count = raw_bucket
        lead.scale_confidence = lead.scale_confidence or "Medium"
        lead.multi_property_confidence = lead.multi_property_confidence or "Medium"
        return raw_bucket
    if raw_bucket == "1" and not lead.multi_property_signal:
        # One Maps pin is not verified scale.
        lead.estimated_property_count = "unknown"
        lead.estimated_property_count_min = None
        lead.estimated_property_count_max = None
        lead.scale_confidence = "Low"
        return "unknown"
    if raw_bucket in {"2–3", "4–10", "10+"}:
        lead.estimated_property_count = raw_bucket
        lead.scale_confidence = lead.scale_confidence or "Medium"
        return raw_bucket
    lead.estimated_property_count = "unknown"
    lead.scale_confidence = lead.scale_confidence or "Low"
    return "unknown"


def contactability_score(lead: Lead) -> tuple[int, list[str]]:
    named = bool(lead.decision_maker_name)
    email = bool(lead.decision_maker_email or lead.email)
    phone = bool(lead.decision_maker_phone or lead.phone)
    website = bool(lead.website)
    linkedin = bool(lead.decision_maker_linkedin or lead.linkedin)
    social = bool(lead.facebook or lead.instagram)
    reasons = []
    if named and email and phone and website:
        score = 94 if linkedin else 90
        reasons.append("Named decision maker plus email, phone, and website")
    elif email and website and phone:
        score = 74
        reasons.append("Email, phone, and website")
    elif email and website:
        score = 66
        reasons.append("Email and website")
    elif phone and website:
        score = 58 if linkedin or social else 54
        reasons.append("Phone and website")
    elif phone and email:
        score = 50
        reasons.append("Phone and email")
    elif phone:
        score = 38 if named else 32
        reasons.append("Phone only")
    elif email:
        score = 34
        reasons.append("Email only")
    elif website:
        score = 22
        reasons.append("Website only")
    else:
        score = 6
        reasons.append("No usable contact details")
    if linkedin:
        score = min(100, score + 4)
        reasons.append("LinkedIn present")
    if social and score < 90:
        score = min(100, score + 3)
    return score, reasons


def data_quality_score(lead: Lead) -> tuple[int, list[str]]:
    score = 0
    if lead.name:
        score += 15
    if lead.website:
        score += 15
    if lead.phone:
        score += 15
    if lead.email or lead.decision_maker_email:
        score += 12
    if lead.address:
        score += 10
    if lead.city:
        score += 8
    if lead.property_type in FIT_TYPES:
        score += 10
    if current_scale(lead) not in {"", "unknown"}:
        score += 8
    if lead.decision_maker_name:
        score += 7
    return min(100, score), []


def icp_score(lead: Lead) -> tuple[int, list[str]]:
    reasons = []
    if is_rejected_org(lead):
        return 8, ["Institutional, university, or non-operator signal"]
    if is_chain(lead):
        return 18, ["Large chain / national brand"]
    score = 12
    if lead.property_type in FIT_TYPES:
        score += 22
        reasons.append(f"{lead.property_type} is a PulseHub type")
    else:
        score -= 12
        reasons.append("Property type is not a PulseHub operator class")
    if lead.independent_operator == "true":
        score += 18
        reasons.append("Independent operator")
    elif lead.independent_operator == "false":
        score -= 10
    if lead.ideal_customer == "true":
        score += 8
    bucket = current_scale(lead)
    if bucket in {"2–3", "4–10"}:
        score += 16
        reasons.append(f"Scale {bucket} matches ICP")
    elif bucket == "1":
        score += 4
    elif bucket == "10+":
        score += 6
    elif bucket == "unknown":
        score += 0
    if lead.website:
        score += 8
    if lead.multi_property_signal and lead.independent_operator != "false":
        score += 12
        reasons.append("Independent multi-property signal")
    if (lead.reviews or 0) >= 20:
        score += 4
    return max(0, min(100, score)), reasons


def opportunity_score(lead: Lead) -> tuple[int, list[str]]:
    if is_rejected_org(lead):
        return 6, ["Not a commercial PulseHub opportunity"]
    if is_chain(lead):
        return 16, ["Chain operations are low PulseHub opportunity"]
    score = 14
    reasons = []
    bucket = current_scale(lead)
    if lead.multi_property_signal or (lead.location_count or 1) >= 2:
        score += 18
        reasons.append("Multi-property operation")
    if bucket == "4–10":
        score += 16
    elif bucket == "2–3":
        score += 12
    elif bucket == "10+":
        score += 8
    elif bucket == "1":
        score += 2
    if lead.property_type in FIT_TYPES:
        score += 10
    if lead.independent_operator == "true":
        score += 10
    if (lead.reviews or 0) >= 80:
        score += 8
    elif (lead.reviews or 0) >= 20:
        score += 4
    if lead.current_software:
        score += 6
        reasons.append("Existing operations software visible")
    if lead.website_research_json and lead.website_research_json.get("booking_system"):
        score += 4
    return max(0, min(100, score)), reasons


def overall_from_parts(icp: int, opportunity: int, contact: int, quality: int) -> int:
    return max(0, min(100, round(icp * 0.4 + opportunity * 0.3 + contact * 0.2 + quality * 0.1)))


def priority_from_score(score: int) -> str:
    if score >= 80:
        return "A+"
    if score >= 65:
        return "A"
    if score >= 40:
        return "B"
    return "C"


def sales_priority_for(lead: Lead, overall: int, contact: int, opportunity: int) -> str:
    grade = lead.priority or priority_from_score(overall)
    if grade == "C" or is_rejected_org(lead) or is_chain(lead) and overall < 50:
        return "Reject"
    if grade == "A+" and contact >= 50 and (lead.multi_property_signal or opportunity >= 70):
        return "Hot"
    if grade in {"A+", "A"}:
        return "High"
    if grade == "B":
        return "Medium"
    return "Low"


def recommended_next_action(lead: Lead) -> str:
    grade = lead.priority
    if grade == "C" or is_rejected_org(lead) or is_chain(lead):
        return "Skip — not a PulseHub prospect"
    if not lead.website:
        return "Find company website"
    if not lead.decision_maker_name:
        return "Find owner/director"
    if not (lead.email or lead.decision_maker_email):
        return "Find business email"
    if lead.multi_property_signal is False and current_scale(lead) == "unknown":
        return "Check number of locations"
    if not lead.current_software:
        return "Review current software"
    if (lead.contactability_score or 0) >= 50 and grade in {"A+", "A"}:
        return "Contact owner"
    if grade == "B":
        return "Review pricing / locations page"
    return "Review public listing"


def research_status_for(lead: Lead) -> str:
    if lead.sales_priority == "Hot" and (lead.contactability_score or 0) >= 50:
        return "sales_ready"
    if lead.decision_maker_name or lead.decision_maker_email:
        return "contact_researched"
    if lead.website_research_status == "completed":
        return "website_researched"
    if lead.priority:
        return "ai_researched"
    return "not_researched"


def apply_derived_fields(lead: Lead, *, overwrite_scores: bool = False, allow_priority_promote: bool = False) -> None:
    if not lead.source_category:
        lead.source_category = lead.category or ""
    if not lead.source_subtypes:
        lead.source_subtypes = lead.subtypes or ""
    if lead.property_type_source != "manual":
        lead.property_type = normalize_property_type(lead.property_type, lead.source_category, lead.source_subtypes, lead.name)
        if not lead.property_type_source:
            lead.property_type_source = "normalized"
    lead.normalized_domain = normalize_domain(lead.website)
    lead.normalized_phone = normalize_phone(lead.phone)
    if lead.estimated_property_count_source != "manual":
        low, high = parse_property_bounds(lead.estimated_property_count)
        if lead.estimated_property_count_min is None:
            lead.estimated_property_count_min = low
        if lead.estimated_property_count_max is None:
            lead.estimated_property_count_max = high
    bucket = apply_scale(lead)
    if bucket in {"2–3", "4–10", "10+"}:
        lead.multi_property_signal = True
        lead.multi_property_confidence = lead.multi_property_confidence or "Medium"
        if not lead.multi_property_evidence:
            lead.multi_property_evidence = f"Estimated property range: {bucket}"
    elif not lead.multi_property_signal:
        lead.multi_property_confidence = lead.multi_property_confidence or "Low"

    contact, contact_why = contactability_score(lead)
    icp, icp_why = icp_score(lead)
    opportunity, opp_why = opportunity_score(lead)
    quality, _ = data_quality_score(lead)
    overall = overall_from_parts(icp, opportunity, contact, quality)

    if overwrite_scores or lead.contactability_score is None:
        lead.contactability_score = contact
    if overwrite_scores or lead.icp_score is None:
        lead.icp_score = icp
    if overwrite_scores or lead.opportunity_score is None:
        lead.opportunity_score = opportunity
    if overwrite_scores or lead.data_quality_score is None:
        lead.data_quality_score = quality
    if overwrite_scores or lead.overall_score is None:
        lead.overall_score = overall

    if lead.priority_source != "manual" and allow_priority_promote:
        lead.priority = priority_from_score(lead.overall_score or overall)
        if not lead.priority_source:
            lead.priority_source = "scored"
    if not lead.qualification_source and lead.priority:
        lead.qualification_source = "ai"

    lead.sales_priority = sales_priority_for(lead, lead.overall_score or overall, lead.contactability_score or contact, lead.opportunity_score or opportunity)
    lead.recommended_next_action = recommended_next_action(lead)
    lead.research_status = research_status_for(lead)
    lead.score_breakdown = {
        "icp": icp_why,
        "opportunity": opp_why,
        "contactability": contact_why,
        "weights": {"icp": 0.4, "opportunity": 0.3, "contactability": 0.2, "data_quality": 0.1},
    }
    if not lead.fit_summary and lead.claude_reason:
        lead.fit_summary = lead.claude_reason
    if not lead.fit_summary:
        lead.fit_summary = _fallback_summary(lead, bucket)
    reasons = []
    if lead.property_type == "Other" and lead.priority in {"A", "A+", "B"}:
        reasons.append("Property type is uncertain")
    if lead.grouping_status == "Unknown" and lead.multi_property_signal:
        reasons.append("Company grouping is uncertain")
    if (lead.confidence or "").lower() in {"low", "unknown"}:
        reasons.append("Low AI confidence")
    if lead.independent_operator in {"", "unknown"} and lead.priority:
        reasons.append("Operator status is uncertain")
    lead.needs_review = bool(reasons)
    lead.review_reason = "; ".join(reasons)


def _fallback_summary(lead: Lead, bucket: str) -> str:
    if is_rejected_org(lead) or is_chain(lead):
        return "Likely not a PulseHub ICP: chain, institution, or non-operator."
    kind = lead.property_type or "accommodation business"
    scale = "unknown scale" if bucket == "unknown" else f"{bucket} properties"
    independence = "Independent " if lead.independent_operator == "true" else ""
    multi = " Multi-property signal present." if lead.multi_property_signal else ""
    return f"{independence}{kind} in {lead.city or 'unknown city'} with {scale}.{multi}".strip()


def is_hot(lead: Lead) -> bool:
    return lead.sales_priority == "Hot" or (lead.priority in {"A+", "A"} and (lead.overall_score or 0) >= 70)
