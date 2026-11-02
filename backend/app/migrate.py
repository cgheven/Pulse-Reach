from __future__ import annotations

from sqlalchemy import text

from .config import get_settings
from .database import engine

LEAD_COLUMNS = {
    "source_category": "VARCHAR(255) DEFAULT ''",
    "source_subtypes": "TEXT DEFAULT ''",
    "normalized_domain": "VARCHAR(255) DEFAULT ''",
    "normalized_phone": "VARCHAR(50) DEFAULT ''",
    "overall_score": "INTEGER",
    "icp_score": "INTEGER",
    "opportunity_score": "INTEGER",
    "contactability_score": "INTEGER",
    "estimated_property_count_min": "INTEGER",
    "estimated_property_count_max": "INTEGER",
    "estimated_bed_count": "VARCHAR(50) DEFAULT ''",
    "scale_confidence": "VARCHAR(50) DEFAULT ''",
    "multi_property_signal": "BOOLEAN DEFAULT FALSE",
    "multi_property_evidence": "TEXT DEFAULT ''",
    "current_software": "VARCHAR(255) DEFAULT ''",
    "current_software_confidence": "VARCHAR(50) DEFAULT ''",
    "software_evidence": "TEXT DEFAULT ''",
    "fit_summary": "TEXT DEFAULT ''",
    "confidence": "VARCHAR(50) DEFAULT ''",
    "decision_maker_name": "VARCHAR(255) DEFAULT ''",
    "decision_maker_role": "VARCHAR(100) DEFAULT ''",
    "decision_maker_email": "VARCHAR(255) DEFAULT ''",
    "decision_maker_phone": "VARCHAR(100) DEFAULT ''",
    "decision_maker_linkedin": "VARCHAR(500) DEFAULT ''",
    "decision_maker_confidence": "VARCHAR(50) DEFAULT ''",
    "company_id": "UUID",
    "company_name": "VARCHAR(255) DEFAULT ''",
    "company_domain": "VARCHAR(255) DEFAULT ''",
    "location_count": "INTEGER DEFAULT 1",
    "grouping_status": "VARCHAR(50) DEFAULT 'Unknown'",
    "qualification_source": "VARCHAR(20) DEFAULT ''",
    "priority_source": "VARCHAR(20) DEFAULT ''",
    "property_type_source": "VARCHAR(20) DEFAULT ''",
    "needs_review": "BOOLEAN DEFAULT FALSE",
    "review_reason": "TEXT DEFAULT ''",
    "website_research_status": "VARCHAR(50) DEFAULT ''",
    "website_research_json": "JSONB",
    "data_quality_score": "INTEGER",
    "sales_priority": "VARCHAR(20) DEFAULT ''",
    "recommended_next_action": "TEXT DEFAULT ''",
    "research_status": "VARCHAR(50) DEFAULT 'not_researched'",
    "multi_property_confidence": "VARCHAR(50) DEFAULT ''",
    "estimated_property_count_source": "VARCHAR(20) DEFAULT ''",
    "score_breakdown": "JSONB",
    "accommodation_type": "VARCHAR(50)",
    "gender": "VARCHAR(20)",
    "mobile": "VARCHAR(100) DEFAULT ''",
    "operator_key": "VARCHAR(255) DEFAULT ''",
    "operator_name": "VARCHAR(255) DEFAULT ''",
    "property_count": "INTEGER DEFAULT 1",
    "size_tier": "VARCHAR(20) DEFAULT 'Low'",
}

SEARCH_COLUMNS = {
    "query_text": "TEXT DEFAULT ''",
    "a_plus_count": "INTEGER DEFAULT 0",
    "a_count": "INTEGER DEFAULT 0",
    "b_count": "INTEGER DEFAULT 0",
    "c_count": "INTEGER DEFAULT 0",
    "contactable_count": "INTEGER DEFAULT 0",
    "quality_score": "INTEGER DEFAULT 0",
}

RUN_COLUMNS = {
    "a_plus_count": "INTEGER DEFAULT 0",
}


def migrate_schema() -> None:
    schema = get_settings().db_schema
    with engine.begin() as conn:
        conn.execute(text(f"SET search_path TO {schema}, public"))
        _add_columns(conn, schema, "leads", LEAD_COLUMNS)
        _add_columns(conn, schema, "campaign_searches", SEARCH_COLUMNS)
        _add_columns(conn, schema, "qualification_runs", RUN_COLUMNS)
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_leads_score ON {schema}.leads (overall_score)"))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_leads_review ON {schema}.leads (needs_review)"))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_leads_domain ON {schema}.leads (normalized_domain)"))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_leads_company ON {schema}.leads (company_id)"))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_leads_acc_type ON {schema}.leads (accommodation_type)"))
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_leads_operator ON {schema}.leads (operator_key)"))


def _add_columns(conn, schema: str, table: str, columns: dict[str, str]) -> None:
    existing = {
        row[0]
        for row in conn.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = :schema AND table_name = :table
                """
            ),
            {"schema": schema, "table": table},
        )
    }
    for name, definition in columns.items():
        if name in existing:
            continue
        conn.execute(text(f"ALTER TABLE {schema}.{table} ADD COLUMN {name} {definition}"))
