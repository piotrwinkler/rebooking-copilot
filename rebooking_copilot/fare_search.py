from __future__ import annotations

from rebooking_copilot.models import Booking, FareOffer


class UnsupportedItineraryError(ValueError):
    """Raised when the POC receives an itinerary shape it does not model yet."""


class FareSearch:
    def find_candidates(
        self,
        booking: Booking,
        offers: list[FareOffer],
    ) -> list[FareOffer]:
        segment = self._single_segment_for(booking)

        return [
            offer
            for offer in offers
            if offer.route.origin == segment.origin
            and offer.route.destination == segment.destination
            and offer.route.departureDate == segment.departure.date()
            and offer.seatsAvailable >= booking.passengers
        ]

    def _single_segment_for(self, booking: Booking):
        if len(booking.itinerary) != 1:
            raise UnsupportedItineraryError(
                "Candidate Search POC supports exactly one itinerary segment."
            )

        return booking.itinerary[0]
