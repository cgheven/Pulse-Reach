from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class OutreachProvider(ABC):
    """Extension point for Apollo, email, and LinkedIn outreach."""

    name: str

    @abstractmethod
    def export_audience(self, leads: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError


class ApolloProvider(OutreachProvider):
    name = "apollo"

    def export_audience(self, leads: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError("Apollo integration is reserved for a later release.")


class EmailOutreachProvider(OutreachProvider):
    name = "email"

    def export_audience(self, leads: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError("Email outreach is reserved for a later release.")


class LinkedInOutreachProvider(OutreachProvider):
    name = "linkedin"

    def export_audience(self, leads: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError("LinkedIn outreach is reserved for a later release.")
