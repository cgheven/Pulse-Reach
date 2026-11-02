from types import SimpleNamespace

from app.schemas import QualificationResult
from app.services.claude import QualificationError, validate_batch
from app.services.scoring import (
    apply_derived_fields,
    contactability_score,
    overall_from_parts,
    priority_from_score,
)
from app.services.taxonomy import PROPERTY_TYPES, normalize_property_type, property_bucket


def test_only_approved_property_types():
    assert PROPERTY_TYPES == [
        "Hostel",
        "Student Accommodation",
        "Guest House",
        "Hotel",
        "Co-living",
        "HMO / Shared Accommodation",
        "Boarding House",
        "Other",
    ]


def test_property_type_normalization():
    cases = {
        "Student Halls": "Student Accommodation",
        "Student Accommodation Centre": "Student Accommodation",
        "Guest House / Bed & Breakfast": "Guest House",
        "Serviced accommodation / Co-living": "Co-living",
        "HMO/Mixed": "HMO / Shared Accommodation",
        "HMO/Rental": "HMO / Shared Accommodation",
        "HMO/Vacation Rental": "HMO / Shared Accommodation",
        "Pub + Hostel": "Hostel",
        "Hotel/Group accommodation": "Hotel",
        "Estate Agent": "Other",
        "Property Management": "Other",
        "Construction Company": "Other",
        "Software Company": "Other",
        "Hostel": "Hostel",
    }
    for raw, expected in cases.items():
        assert normalize_property_type(raw) == expected, raw
    assert normalize_property_type("Hostel", "Student Halls") == "Hostel"


def test_contactability_bands():
    def lead(**kwargs):
        defaults = dict(
            decision_maker_name="",
            decision_maker_email="",
            decision_maker_phone="",
            decision_maker_linkedin="",
            email="",
            phone="",
            website="",
            linkedin="",
            facebook="",
            instagram="",
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    assert contactability_score(lead())[0] <= 20
    assert 30 <= contactability_score(lead(phone="+44 20 0000"))[0] <= 50
    assert 50 <= contactability_score(lead(phone="+44 20 0000", website="https://example.com"))[0] <= 70
    assert 60 <= contactability_score(lead(email="a@b.com", website="https://example.com"))[0] <= 80
    assert contactability_score(lead(decision_maker_name="Ada", email="a@b.com", phone="1", website="https://x.com"))[0] >= 90


def test_property_buckets():
    assert property_bucket(1, "") == "1"
    assert property_bucket(2, "") == "2–3"
    assert property_bucket(6, "") == "4–10"
    assert property_bucket(12, "") == "10+"
    assert property_bucket(None, "unknown") == "unknown"


def test_scores_are_not_clamped_to_79():
    high = overall_from_parts(90, 85, 70, 80)
    mid = overall_from_parts(55, 48, 54, 60)
    low = overall_from_parts(20, 16, 22, 30)
    assert high != 79 and high >= 80
    assert 40 <= mid <= 64
    assert low < 40
    assert {high, mid, low} == {high, mid, low}
    assert priority_from_score(high) == "A+"
    assert priority_from_score(mid) == "B"
    assert priority_from_score(low) == "C"


def test_chain_and_independent_differ():
    def lead(**kwargs):
        defaults = dict(
            name="Test House",
            source_category="Hostel",
            source_subtypes="",
            subtypes="",
            category="Hostel",
            property_type="Hostel",
            property_type_source="normalized",
            claude_reason="",
            fit_summary="",
            independent_operator="true",
            ideal_customer="true",
            website="https://example.com",
            phone="+44111",
            email="",
            address="1 Road",
            city="London",
            decision_maker_name="",
            decision_maker_email="",
            decision_maker_phone="",
            decision_maker_linkedin="",
            linkedin="",
            facebook="",
            instagram="",
            location_count=1,
            grouping_status="Unknown",
            estimated_property_count="unknown",
            estimated_property_count_min=None,
            estimated_property_count_max=None,
            estimated_property_count_source="",
            multi_property_signal=False,
            multi_property_confidence="",
            multi_property_evidence="",
            scale_confidence="",
            current_software="",
            website_research_json=None,
            website_research_status="",
            reviews=12,
            rating=4.2,
            priority="",
            priority_source="",
            qualification_source="",
            sales_priority="",
            recommended_next_action="",
            research_status="",
            score_breakdown=None,
            overall_score=None,
            icp_score=None,
            opportunity_score=None,
            contactability_score=None,
            data_quality_score=None,
            confidence="",
            normalized_domain="",
            normalized_phone="",
        )
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    independent = lead(name="Bloom Coliving", property_type="Co-living", multi_property_signal=True, location_count=3, grouping_status="Confirmed")
    chain = lead(name="Wombat's City Hostel London", independent_operator="false", ideal_customer="false")
    apply_derived_fields(independent, overwrite_scores=True)
    apply_derived_fields(chain, overwrite_scores=True)
    assert independent.overall_score != chain.overall_score
    assert independent.overall_score > chain.overall_score
    assert independent.overall_score != 79
    assert chain.sales_priority == "Reject"
    institutional = lead(name="iQ Student Accommodation London", property_type="Student Accommodation", independent_operator="false")
    apply_derived_fields(institutional, overwrite_scores=True)
    assert institutional.overall_score < independent.overall_score
    assert institutional.sales_priority == "Reject"


def _result(lead_id: str) -> QualificationResult:
    return QualificationResult(
        lead_id=lead_id,
        relevant=True,
        priority="A",
        overall_score=70,
        icp_score=68,
        opportunity_score=64,
        contactability_score=55,
        property_type="Hostel",
        estimated_property_count="1",
        independent_operator=True,
        ideal_customer=True,
        reason="Independent hostel with a website.",
        confidence="medium",
    )


def test_single_listing_scale_is_unknown():
    lead = SimpleNamespace(
        estimated_property_count="1",
        estimated_property_count_min=1,
        estimated_property_count_max=1,
        estimated_property_count_source="",
        location_count=1,
        grouping_status="Unknown",
        multi_property_signal=False,
        multi_property_confidence="",
        multi_property_evidence="",
        scale_confidence="",
    )
    from app.services.scoring import apply_scale

    assert apply_scale(lead) == "unknown"
    assert lead.estimated_property_count == "unknown"


def test_claude_batch_rejects_extra_and_missing():
    expected = ["1", "2"]
    try:
        validate_batch([_result("1")], expected)
        raise AssertionError("missing id should fail")
    except QualificationError:
        pass
    try:
        validate_batch([_result("1"), _result("2"), _result("3")], expected)
        raise AssertionError("extra id should fail")
    except QualificationError:
        pass
    validate_batch([_result("1"), _result("2")], expected)
