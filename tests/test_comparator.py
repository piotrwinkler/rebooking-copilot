from __future__ import annotations

import unittest

from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.models import Booking, ComparisonAssessment, FareOffer
from rebooking_copilot.services.comparator import FareComparator
from rebooking_copilot.services.economics import (
    EconomicsCalculator,
    StaticExchangeRateProvider,
)


class FareComparatorTest(unittest.TestCase):
    def setUp(self):
        self.bookings = load_pnrs("fixtures/pnrs.json").pnrs
        self.offers = load_fares_feed("fixtures/fares_feed.json").offers
        self.economics = EconomicsCalculator(StaticExchangeRateProvider())
        self.comparator = FareComparator()

    def test_marks_equivalent_offer_dimensions_as_same(self):
        booking = self._booking("QX7T2A")
        offer = self._offer("OF-1001")

        comparison = self.comparator.compare(
            booking,
            offer,
            self.economics.calculate(booking, offer),
        )

        by_name = self._by_name(comparison)
        self.assertEqual(ComparisonAssessment.SAME, by_name["cabin"].assessment)
        self.assertEqual(ComparisonAssessment.SAME, by_name["stops"].assessment)
        self.assertEqual(ComparisonAssessment.SAME, by_name["baggage"].assessment)
        self.assertEqual(ComparisonAssessment.SAME, by_name["refundability"].assessment)
        self.assertEqual(ComparisonAssessment.SAME, by_name["schedule"].assessment)
        self.assertEqual(ComparisonAssessment.SAME, by_name["carrier"].assessment)

    def test_marks_quality_degradations_and_preference_unknowns(self):
        booking = self._booking("HB6W9E")
        offer = self._offer("OF-5002")

        comparison = self.comparator.compare(
            booking,
            offer,
            self.economics.calculate(booking, offer),
        )

        by_name = self._by_name(comparison)
        self.assertEqual(ComparisonAssessment.WORSE, by_name["cabin"].assessment)
        self.assertEqual(ComparisonAssessment.WORSE, by_name["stops"].assessment)
        self.assertEqual(ComparisonAssessment.WORSE, by_name["baggage"].assessment)
        self.assertEqual(ComparisonAssessment.UNKNOWN, by_name["schedule"].assessment)
        self.assertEqual(ComparisonAssessment.UNKNOWN, by_name["carrier"].assessment)
        self.assertEqual(
            ComparisonAssessment.BETTER,
            by_name["future_change_fee"].assessment,
        )

    def test_marks_lost_refundability_as_worse(self):
        booking = self._booking("ZC3N1D")
        offer = self._offer("OF-4001")

        comparison = self.comparator.compare(
            booking,
            offer,
            self.economics.calculate(booking, offer),
        )

        by_name = self._by_name(comparison)
        self.assertEqual(ComparisonAssessment.WORSE, by_name["refundability"].assessment)

    def _booking(self, pnr: str) -> Booking:
        return next(booking for booking in self.bookings if booking.pnr == pnr)

    def _offer(self, offer_id: str) -> FareOffer:
        return next(offer for offer in self.offers if offer.offerId == offer_id)

    def _by_name(self, comparison):
        return {dimension.name: dimension for dimension in comparison.dimensions}


if __name__ == "__main__":
    unittest.main()
