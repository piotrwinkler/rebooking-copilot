from __future__ import annotations

from rebooking_copilot.models import (
    Booking,
    BookingRecommendation,
    CandidateEvaluation,
    FareOffer,
)
from rebooking_copilot.services.comparator import FareComparator
from rebooking_copilot.services.economics import (
    EconomicsCalculator,
    StaticExchangeRateProvider,
)
from rebooking_copilot.services.fare_search import FareSearch
from rebooking_copilot.services.policy import PolicyEngine
from rebooking_copilot.services.ranker import CandidateRanker


class RebookingPipeline:
    def __init__(
        self,
        fare_search: FareSearch,
        economics_calculator: EconomicsCalculator,
        fare_comparator: FareComparator,
        policy_engine: PolicyEngine,
        candidate_ranker: CandidateRanker,
    ):
        self._fare_search = fare_search
        self._economics_calculator = economics_calculator
        self._fare_comparator = fare_comparator
        self._policy_engine = policy_engine
        self._candidate_ranker = candidate_ranker

    def run(
        self,
        bookings: list[Booking],
        offers: list[FareOffer],
    ) -> list[BookingRecommendation]:
        return [self.evaluate_booking(booking, offers) for booking in bookings]

    def evaluate_booking(
        self,
        booking: Booking,
        offers: list[FareOffer],
    ) -> BookingRecommendation:
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

        return self._candidate_ranker.rank(booking.pnr, candidate_evaluations)


def build_default_pipeline() -> RebookingPipeline:
    return RebookingPipeline(
        fare_search=FareSearch(),
        economics_calculator=EconomicsCalculator(StaticExchangeRateProvider()),
        fare_comparator=FareComparator(),
        policy_engine=PolicyEngine(),
        candidate_ranker=CandidateRanker(),
    )
