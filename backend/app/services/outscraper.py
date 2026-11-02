from __future__ import annotations

from typing import Any, Callable

from outscraper import ApiClient

from .geo import region_for  # noqa: F401  (re-exported for callers)
from .leads import row_from_raw


ProgressCb = Callable[[dict[str, Any]], None]

def search_places(
    api_key: str,
    *,
    query: str,
    limit: int,
    language: str = "en",
    region: str | None = None,
    enrich_contacts: bool = False,
) -> list[dict[str, Any]]:
    """Google Maps search. `enrich_contacts` adds Outscraper's Emails & Contacts enrichment (extra cost per result)."""
    client = ApiClient(api_key=api_key)
    result = client.google_maps_search(
        [query],
        limit=limit,
        language=language,
        region=region,
        enrichment=["domains_service"] if enrich_contacts else None,
    )
    if isinstance(result, list) and result and isinstance(result[0], list):
        places = result[0]
    elif isinstance(result, list):
        places = result
    else:
        places = []
    leads: list[dict[str, Any]] = []
    for raw in places:
        if not isinstance(raw, dict):
            continue
        payload = row_from_raw(raw, query)
        if not payload["place_id"] or not payload["name"]:
            continue
        leads.append(payload)
    return leads
