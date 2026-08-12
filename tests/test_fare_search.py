from __future__ import annotations

import unittest
from copy import deepcopy

from rebooking_copilot.fare_search import FareSearch, UnsupportedItineraryError
from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.models import Booking, FareOffer


class FareSearchTest(unittest.TestCase):
    def setUp(self):
        self.bookings = load_pnrs("fixtures/pnrs.json").pnrs
        self.offers = load_fares_feed("fixtures/fares_feed.json").offers
        self.search = FareSearch()

    def test_matches_by_route_and_departure_date(self):
        booking = self._booking("QX7T2A")

        candidates = self.search.find_candidates(booking, self.offers)

        self.assertEqual(["OF-1001"], [offer.offerId for offer in candidates])

    def test_rejects_offers_without_enough_seats_for_all_passengers(self):
        booking = self._booking("LM9P4C")
        offer = self._offer("OF-2001").model_copy(deep=True)
        offer.seatsAvailable = 1

        candidates = self.search.find_candidates(booking, [offer])

        self.assertEqual([], candidates)

    def test_search_does_not_filter_by_price(self):
        booking = self._booking("QX7T2A")
        expensive_offer = self._offer("OF-1001").model_copy(deep=True)
        expensive_offer.price.amount = booking.ticket.totalPaid.amount * 10

        candidates = self.search.find_candidates(booking, [expensive_offer])

        self.assertEqual(["OF-1001"], [offer.offerId for offer in candidates])

    def test_rejects_multi_segment_bookings_for_now(self):
        booking = self._booking("QX7T2A").model_copy(deep=True)
        booking.itinerary.append(deepcopy(booking.itinerary[0]))

        with self.assertRaises(UnsupportedItineraryError):
            self.search.find_candidates(booking, self.offers)

    def _booking(self, pnr: str) -> Booking:
        return next(booking for booking in self.bookings if booking.pnr == pnr)

    def _offer(self, offer_id: str) -> FareOffer:
        return next(offer for offer in self.offers if offer.offerId == offer_id)


if __name__ == "__main__":
    unittest.main()
