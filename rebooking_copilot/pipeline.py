from __future__ import annotations

from pydantic import BaseModel

from rebooking_copilot.models import (
    Booking,
    EconomicsResult,
    FareComparison,
    FareOffer,
    PolicyEvaluation,
)
from rebooking_copilot.services.comparator import FareComparator
from rebooking_copilot.services.economics import (
    EconomicsCalculator,
    StaticExchangeRateProvider,
)
from rebooking_copilot.services.fare_search import FareSearch
from rebooking_copilot.services.policy import PolicyEngine


class CandidateEvaluation(BaseModel):
    offer_id: str
    economics: EconomicsResult
    comparison: FareComparison
    policy: PolicyEvaluation


class BookingPipelineResult(BaseModel):
    booking_id: str
    candidate_count: int
    candidates: list[CandidateEvaluation]


class RebookingPipeline:
    def __init__(
        self,
        fare_search: FareSearch,
        economics_calculator: EconomicsCalculator,
        fare_comparator: FareComparator,
        policy_engine: PolicyEngine,
    ):
        self._fare_search = fare_search
        self._economics_calculator = economics_calculator
        self._fare_comparator = fare_comparator
        self._policy_engine = policy_engine

    def run(
        self,
        bookings: list[Booking],
        offers: list[FareOffer],
    ) -> list[BookingPipelineResult]:
        return [self.evaluate_booking(booking, offers) for booking in bookings]

    def evaluate_booking(
        self,
        booking: Booking,
        offers: list[FareOffer],
    ) -> BookingPipelineResult:
        candidates = self._fare_search.find_candidates(booking, offers)
        candidate_evaluations = []
        for candidate in candidates:
            economics = self._economics_calculator.calculate(booking, candidate)
            comparison = self._fare_comparator.compare(booking, candidate, economics)
            policy = self._policy_engine.evaluate(economics, comparison)
            candidate_evaluations.append(
                CandidateEvaluation(
                    offer_id=candidate.offerId,
                    economics=economics,
                    comparison=comparison,
                    policy=policy,
                )
            )

        return BookingPipelineResult(
            booking_id=booking.pnr,
            candidate_count=len(candidate_evaluations),
            candidates=candidate_evaluations,
        )


def build_default_pipeline() -> RebookingPipeline:
    return RebookingPipeline(
        fare_search=FareSearch(),
        economics_calculator=EconomicsCalculator(StaticExchangeRateProvider()),
        fare_comparator=FareComparator(),
        policy_engine=PolicyEngine(),
    )
