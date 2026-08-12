from __future__ import annotations

from decimal import Decimal

from rebooking_copilot.models import (
    BookingRecommendation,
    CandidateEvaluation,
    Money,
    PolicyDecision,
)


class CandidateRanker:
    def __init__(self, comparison_currency: str = "USD"):
        self._comparison_currency = comparison_currency

    def rank(
        self,
        booking_id: str,
        candidates: list[CandidateEvaluation],
    ) -> BookingRecommendation:
        rebook_candidates = self._candidates_with_decision(
            candidates,
            PolicyDecision.REBOOK,
        )
        if rebook_candidates:
            selected = self._highest_saving(rebook_candidates)
            return self._recommendation(booking_id, PolicyDecision.REBOOK, selected, candidates)

        review_candidates = self._candidates_with_decision(
            candidates,
            PolicyDecision.SEND_FOR_HUMAN_REVIEW,
        )
        if review_candidates:
            selected = self._highest_saving(review_candidates)
            return self._recommendation(
                booking_id,
                PolicyDecision.SEND_FOR_HUMAN_REVIEW,
                selected,
                candidates,
            )

        return BookingRecommendation(
            booking_id=booking_id,
            decision=PolicyDecision.DO_NOT_REBOOK,
            selected_offer_id=None,
            estimated_net_saving=Money(
                amount=Decimal("0.00"),
                currency=self._comparison_currency,
            ),
            reason_codes=[self._do_not_rebook_reason(candidates)],
            candidate_count=len(candidates),
            candidates=candidates,
        )

    def _candidates_with_decision(
        self,
        candidates: list[CandidateEvaluation],
        decision: PolicyDecision,
    ) -> list[CandidateEvaluation]:
        return [candidate for candidate in candidates if candidate.policy.decision == decision]

    def _highest_saving(
        self,
        candidates: list[CandidateEvaluation],
    ) -> CandidateEvaluation:
        return max(
            candidates,
            key=lambda candidate: candidate.economics.estimated_net_saving.amount,
        )

    def _recommendation(
        self,
        booking_id: str,
        decision: PolicyDecision,
        selected: CandidateEvaluation,
        candidates: list[CandidateEvaluation],
    ) -> BookingRecommendation:
        return BookingRecommendation(
            booking_id=booking_id,
            decision=decision,
            selected_offer_id=selected.offer_id,
            estimated_net_saving=selected.economics.estimated_net_saving,
            reason_codes=selected.policy.reason_codes,
            candidate_count=len(candidates),
            candidates=candidates,
        )

    def _do_not_rebook_reason(self, candidates: list[CandidateEvaluation]) -> str:
        if not candidates:
            return "NO_CANDIDATES_FOUND"

        return "NO_REBOOKABLE_CANDIDATES"
