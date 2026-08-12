from __future__ import annotations

from datetime import datetime

from rebooking_copilot.models import BookingRecommendation, StructuredOutput


class StructuredOutputBuilder:
    def __init__(self, schema_version: str = "poc.v1"):
        self._schema_version = schema_version

    def build(
        self,
        recommendations: list[BookingRecommendation],
        fare_snapshot_captured_at: datetime,
    ) -> StructuredOutput:
        return StructuredOutput(
            schema_version=self._schema_version,
            fare_snapshot_captured_at=fare_snapshot_captured_at,
            recommendation_count=len(recommendations),
            recommendations=recommendations,
        )
