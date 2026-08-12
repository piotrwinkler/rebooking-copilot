from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from rebooking_copilot.models import (
    Booking,
    ComparisonAssessment,
    ComparisonDimension,
    EconomicsResult,
    FareComparison,
    FareOffer,
)


_CABIN_ORDER = {
    "BASIC_ECONOMY": 0,
    "ECONOMY": 1,
    "PREMIUM_ECONOMY": 2,
    "BUSINESS": 3,
    "FIRST": 4,
}


class FareComparator:
    def __init__(self, schedule_tolerance: timedelta = timedelta(minutes=15)):
        self._schedule_tolerance = schedule_tolerance

    def compare(
        self,
        booking: Booking,
        offer: FareOffer,
        economics: EconomicsResult,
    ) -> FareComparison:
        segment = booking.itinerary[0]

        return FareComparison(
            dimensions=[
                self._compare_cabin(booking.ticket.cabin, offer.cabin),
                self._compare_numeric("stops", segment.stops, offer.stops, lower_is_better=True),
                self._compare_numeric(
                    "baggage",
                    booking.ticket.baggageIncludedPieces,
                    offer.baggageIncludedPieces,
                    lower_is_better=False,
                ),
                self._compare_refundability(booking.ticket.refundable, offer.refundable),
                self._compare_schedule(segment.departure, segment.arrival, offer),
                self._compare_carrier(segment.carrier, offer.carrier),
                self._compare_future_change_fee(economics),
            ]
        )

    def _compare_cabin(
        self,
        original: str,
        candidate: str,
    ) -> ComparisonDimension:
        original_rank = _CABIN_ORDER.get(original)
        candidate_rank = _CABIN_ORDER.get(candidate)

        if original_rank is None or candidate_rank is None:
            assessment = ComparisonAssessment.UNKNOWN
            delta = None
        elif candidate_rank > original_rank:
            assessment = ComparisonAssessment.BETTER
            delta = candidate_rank - original_rank
        elif candidate_rank < original_rank:
            assessment = ComparisonAssessment.WORSE
            delta = candidate_rank - original_rank
        else:
            assessment = ComparisonAssessment.SAME
            delta = 0

        return ComparisonDimension(
            name="cabin",
            assessment=assessment,
            original=original,
            candidate=candidate,
            delta=delta,
        )

    def _compare_numeric(
        self,
        name: str,
        original: int,
        candidate: int,
        lower_is_better: bool,
    ) -> ComparisonDimension:
        delta = candidate - original
        if delta == 0:
            assessment = ComparisonAssessment.SAME
        elif (delta < 0 and lower_is_better) or (delta > 0 and not lower_is_better):
            assessment = ComparisonAssessment.BETTER
        else:
            assessment = ComparisonAssessment.WORSE

        return ComparisonDimension(
            name=name,
            assessment=assessment,
            original=original,
            candidate=candidate,
            delta=delta,
        )

    def _compare_refundability(
        self,
        original: bool,
        candidate: bool,
    ) -> ComparisonDimension:
        if original == candidate:
            assessment = ComparisonAssessment.SAME
        elif candidate and not original:
            assessment = ComparisonAssessment.BETTER
        else:
            assessment = ComparisonAssessment.WORSE

        return ComparisonDimension(
            name="refundability",
            assessment=assessment,
            original=original,
            candidate=candidate,
        )

    def _compare_schedule(self, original_departure, original_arrival, offer: FareOffer):
        departure_delta_minutes = int(
            (offer.departure - original_departure).total_seconds() / 60
        )
        arrival_delta_minutes = int((offer.arrival - original_arrival).total_seconds() / 60)
        within_tolerance = (
            abs(departure_delta_minutes) <= self._schedule_tolerance.total_seconds() / 60
            and abs(arrival_delta_minutes) <= self._schedule_tolerance.total_seconds() / 60
        )

        return ComparisonDimension(
            name="schedule",
            assessment=(
                ComparisonAssessment.SAME
                if within_tolerance
                else ComparisonAssessment.UNKNOWN
            ),
            original={
                "departure": original_departure,
                "arrival": original_arrival,
            },
            candidate={
                "departure": offer.departure,
                "arrival": offer.arrival,
            },
            delta={
                "departure_minutes": departure_delta_minutes,
                "arrival_minutes": arrival_delta_minutes,
            },
        )

    def _compare_carrier(
        self,
        original: str,
        candidate: str,
    ) -> ComparisonDimension:
        return ComparisonDimension(
            name="carrier",
            assessment=(
                ComparisonAssessment.SAME
                if original == candidate
                else ComparisonAssessment.UNKNOWN
            ),
            original=original,
            candidate=candidate,
        )

    def _compare_future_change_fee(self, economics: EconomicsResult) -> ComparisonDimension:
        original = economics.original_change_fee_per_passenger.amount
        candidate = economics.candidate_change_fee_per_passenger.amount
        delta = candidate - original

        if delta == Decimal("0"):
            assessment = ComparisonAssessment.SAME
        elif delta < Decimal("0"):
            assessment = ComparisonAssessment.BETTER
        else:
            assessment = ComparisonAssessment.WORSE

        return ComparisonDimension(
            name="future_change_fee",
            assessment=assessment,
            original={
                "amount": str(original),
                "currency": economics.original_change_fee_per_passenger.currency,
            },
            candidate={
                "amount": str(candidate),
                "currency": economics.candidate_change_fee_per_passenger.currency,
            },
            delta=str(delta),
        )
