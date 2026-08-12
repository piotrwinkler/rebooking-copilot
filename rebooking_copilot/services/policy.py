from __future__ import annotations

from decimal import Decimal

from rebooking_copilot.models import (
    ComparisonAssessment,
    EconomicsResult,
    FareComparison,
    PolicyDecision,
    PolicyEvaluation,
)


class PolicyEngine:
    def evaluate(
        self,
        economics: EconomicsResult,
        comparison: FareComparison,
    ) -> PolicyEvaluation:
        if economics.estimated_net_saving.amount <= Decimal("0"):
            return PolicyEvaluation(
                decision=PolicyDecision.DO_NOT_REBOOK,
                reason_codes=["NON_POSITIVE_NET_SAVING"],
            )

        review_reasons = self._review_reasons(comparison)
        if review_reasons:
            return PolicyEvaluation(
                decision=PolicyDecision.SEND_FOR_HUMAN_REVIEW,
                reason_codes=["POSITIVE_NET_SAVING", *review_reasons],
            )

        return PolicyEvaluation(
            decision=PolicyDecision.REBOOK,
            reason_codes=[
                "POSITIVE_NET_SAVING",
                "ALL_QUALITY_DIMENSIONS_ACCEPTABLE",
            ],
        )

    def _review_reasons(self, comparison: FareComparison) -> list[str]:
        reason_codes = []
        for dimension in comparison.dimensions:
            if dimension.assessment == ComparisonAssessment.WORSE:
                reason_codes.append(f"WORSE_{dimension.name.upper()}")
            elif dimension.assessment == ComparisonAssessment.UNKNOWN:
                reason_codes.append(f"UNKNOWN_{dimension.name.upper()}")

        return reason_codes
