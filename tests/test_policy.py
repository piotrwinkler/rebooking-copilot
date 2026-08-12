from __future__ import annotations

import unittest

from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.models import Booking, FareOffer, PolicyDecision
from rebooking_copilot.services.comparator import FareComparator
from rebooking_copilot.services.economics import (
    EconomicsCalculator,
    StaticExchangeRateProvider,
)
from rebooking_copilot.services.policy import PolicyEngine


class PolicyEngineTest(unittest.TestCase):
    def setUp(self):
        self.bookings = load_pnrs("fixtures/pnrs.json").pnrs
        self.offers = load_fares_feed("fixtures/fares_feed.json").offers
        self.economics = EconomicsCalculator(StaticExchangeRateProvider())
        self.comparator = FareComparator()
        self.policy = PolicyEngine()

    def test_rebooks_positive_saving_with_no_quality_degradation(self):
        evaluation = self._evaluate("QX7T2A", "OF-1001")

        self.assertEqual(PolicyDecision.REBOOK, evaluation.decision)
        self.assertEqual(
            ["POSITIVE_NET_SAVING", "ALL_QUALITY_DIMENSIONS_ACCEPTABLE"],
            evaluation.reason_codes,
        )
        self.assertEqual("1.00", str(evaluation.confidence))
        self.assertEqual([], evaluation.confidence_reason_codes)

    def test_sends_positive_saving_with_degradation_for_human_review(self):
        evaluation = self._evaluate("ZC3N1D", "OF-4001")

        self.assertEqual(PolicyDecision.SEND_FOR_HUMAN_REVIEW, evaluation.decision)
        self.assertIn("POSITIVE_NET_SAVING", evaluation.reason_codes)
        self.assertIn("WORSE_REFUNDABILITY", evaluation.reason_codes)
        self.assertEqual("0.80", str(evaluation.confidence))
        self.assertEqual(
            ["CONFIDENCE_PENALTY_REFUNDABILITY"],
            evaluation.confidence_reason_codes,
        )

    def test_rejects_non_positive_saving_before_quality_policy(self):
        evaluation = self._evaluate("LM9P4C", "OF-2001")

        self.assertEqual(PolicyDecision.DO_NOT_REBOOK, evaluation.decision)
        self.assertEqual(["NON_POSITIVE_NET_SAVING"], evaluation.reason_codes)
        self.assertEqual("0.00", str(evaluation.confidence))
        self.assertEqual(
            ["NON_POSITIVE_NET_SAVING"],
            evaluation.confidence_reason_codes,
        )

    def test_human_review_reasons_include_unknown_dimensions(self):
        booking = self._booking("QX7T2A")
        offer = self._offer("OF-1001").model_copy(deep=True)
        offer.departure = offer.departure.replace(hour=12)

        economics = self.economics.calculate(booking, offer)
        comparison = self.comparator.compare(booking, offer, economics)
        evaluation = self.policy.evaluate(economics, comparison)

        self.assertEqual(PolicyDecision.SEND_FOR_HUMAN_REVIEW, evaluation.decision)
        self.assertIn("UNKNOWN_SCHEDULE", evaluation.reason_codes)
        self.assertEqual("0.85", str(evaluation.confidence))
        self.assertIn(
            "CONFIDENCE_PENALTY_SCHEDULE",
            evaluation.confidence_reason_codes,
        )

    def test_stubbed_fx_reduces_confidence(self):
        evaluation = self._evaluate("RT5K8B", "OF-3001")

        self.assertEqual(PolicyDecision.REBOOK, evaluation.decision)
        self.assertEqual("0.90", str(evaluation.confidence))
        self.assertEqual(
            ["CONFIDENCE_PENALTY_STUBBED_FX"],
            evaluation.confidence_reason_codes,
        )

    def _evaluate(self, pnr: str, offer_id: str):
        booking = self._booking(pnr)
        offer = self._offer(offer_id)
        economics = self.economics.calculate(booking, offer)
        comparison = self.comparator.compare(booking, offer, economics)
        return self.policy.evaluate(economics, comparison)

    def _booking(self, pnr: str) -> Booking:
        return next(booking for booking in self.bookings if booking.pnr == pnr)

    def _offer(self, offer_id: str) -> FareOffer:
        return next(offer for offer in self.offers if offer.offerId == offer_id)


if __name__ == "__main__":
    unittest.main()
