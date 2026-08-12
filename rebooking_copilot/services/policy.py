from __future__ import annotations

from decimal import Decimal

from rebooking_copilot.models import (
    ComparisonAssessment,
    ComparisonDimension,
    EconomicsResult,
    FareComparison,
    PolicyDecision,
    PolicyEvaluation,
)


_CONFIDENCE_PENALTIES = {
    ("cabin", ComparisonAssessment.WORSE): Decimal("0.30"),
    ("stops", ComparisonAssessment.WORSE): Decimal("0.25"),
    ("refundability", ComparisonAssessment.WORSE): Decimal("0.20"),
    ("baggage", ComparisonAssessment.WORSE): Decimal("0.15"),
    ("schedule", ComparisonAssessment.UNKNOWN): Decimal("0.15"),
    ("carrier", ComparisonAssessment.UNKNOWN): Decimal("0.10"),
    ("future_change_fee", ComparisonAssessment.WORSE): Decimal("0.10"),
}
_DEFAULT_UNKNOWN_PENALTY = Decimal("0.20")
_FX_STUB_PENALTY = Decimal("0.10")


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
                confidence=Decimal("0.00"),
                confidence_reason_codes=["NON_POSITIVE_NET_SAVING"],
            )

        confidence, confidence_reasons = self._confidence(economics, comparison)
        review_reasons = self._review_reasons(comparison)
        if review_reasons:
            return PolicyEvaluation(
                decision=PolicyDecision.SEND_FOR_HUMAN_REVIEW,
                reason_codes=["POSITIVE_NET_SAVING", *review_reasons],
                confidence=confidence,
                confidence_reason_codes=confidence_reasons,
            )

        return PolicyEvaluation(
            decision=PolicyDecision.REBOOK,
            reason_codes=[
                "POSITIVE_NET_SAVING",
                "ALL_QUALITY_DIMENSIONS_ACCEPTABLE",
            ],
            confidence=confidence,
            confidence_reason_codes=confidence_reasons,
        )

    def _review_reasons(self, comparison: FareComparison) -> list[str]:
        reason_codes = []
        for dimension in comparison.dimensions:
            if dimension.assessment == ComparisonAssessment.WORSE:
                reason_codes.append(f"WORSE_{dimension.name.upper()}")
            elif dimension.assessment == ComparisonAssessment.UNKNOWN:
                reason_codes.append(f"UNKNOWN_{dimension.name.upper()}")

        return reason_codes

    def _confidence(
        self,
        economics: EconomicsResult,
        comparison: FareComparison,
    ) -> tuple[Decimal, list[str]]:
        confidence = Decimal("1.00")
        reason_codes = []

        for dimension in comparison.dimensions:
            penalty = self._confidence_penalty_for(dimension)
            if penalty == Decimal("0.00"):
                continue

            confidence -= penalty
            reason_codes.append(f"CONFIDENCE_PENALTY_{dimension.name.upper()}")

        if economics.fx_used:
            confidence -= _FX_STUB_PENALTY
            reason_codes.append("CONFIDENCE_PENALTY_STUBBED_FX")

        return max(Decimal("0.00"), confidence), reason_codes

    def _confidence_penalty_for(self, dimension: ComparisonDimension) -> Decimal:
        configured_penalty = _CONFIDENCE_PENALTIES.get(
            (dimension.name, dimension.assessment)
        )
        if configured_penalty is not None:
            return configured_penalty

        if dimension.assessment == ComparisonAssessment.UNKNOWN:
            return _DEFAULT_UNKNOWN_PENALTY

        return Decimal("0.00")
