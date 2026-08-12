from __future__ import annotations

from pydantic import BaseModel

from rebooking_copilot.models import Booking, EconomicsResult, FareOffer
from rebooking_copilot.services.economics import (
    EconomicsCalculator,
    StaticExchangeRateProvider,
)
from rebooking_copilot.services.fare_search import FareSearch


class CandidateEconomics(BaseModel):
    offer_id: str
    economics: EconomicsResult


class BookingPipelineResult(BaseModel):
    booking_id: str
    candidate_count: int
    candidates: list[CandidateEconomics]


class RebookingPipeline:
    def __init__(
        self,
        fare_search: FareSearch,
        economics_calculator: EconomicsCalculator,
    ):
        self._fare_search = fare_search
        self._economics_calculator = economics_calculator

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
        candidate_economics = [
            CandidateEconomics(
                offer_id=candidate.offerId,
                economics=self._economics_calculator.calculate(booking, candidate),
            )
            for candidate in candidates
        ]

        return BookingPipelineResult(
            booking_id=booking.pnr,
            candidate_count=len(candidate_economics),
            candidates=candidate_economics,
        )


def build_default_pipeline() -> RebookingPipeline:
    return RebookingPipeline(
        fare_search=FareSearch(),
        economics_calculator=EconomicsCalculator(StaticExchangeRateProvider()),
    )
