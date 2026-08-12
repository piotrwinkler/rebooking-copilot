from __future__ import annotations

from decimal import Decimal
import unittest

from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.models import Booking, CandidateEvaluation, FareOffer, PolicyDecision
from rebooking_copilot.services.comparator import FareComparator
from rebooking_copilot.services.economics import (
    EconomicsCalculator,
    StaticExchangeRateProvider,
)
from rebooking_copilot.services.policy import PolicyEngine
from rebooking_copilot.services.ranker import CandidateRanker


class CandidateRankerTest(unittest.TestCase):
    def setUp(self):
        self.bookings = load_pnrs("fixtures/pnrs.json").pnrs
        self.offers = load_fares_feed("fixtures/fares_feed.json").offers
        self.economics = EconomicsCalculator(StaticExchangeRateProvider())
        self.comparator = FareComparator()
        self.policy = PolicyEngine()
        self.ranker = CandidateRanker()

    def test_selects_highest_saving_rebook_candidate(self):
        recommendation = self.ranker.rank(
            "booking-1",
            [
                self._evaluation("QX7T2A", "OF-1001"),
                self._evaluation("RT5K8B", "OF-3001"),
            ],
        )

        self.assertEqual(PolicyDecision.REBOOK, recommendation.decision)
        self.assertEqual("OF-3001", recommendation.selected_offer_id)
        self.assertEqual(Decimal("320.00"), recommendation.estimated_net_saving.amount)

    def test_rebook_candidates_outrank_higher_saving_review_candidates(self):
        recommendation = self.ranker.rank(
            "booking-2",
            [
                self._evaluation("QX7T2A", "OF-1001"),
                self._evaluation("ZC3N1D", "OF-4001"),
            ],
        )

        self.assertEqual(PolicyDecision.REBOOK, recommendation.decision)
        self.assertEqual("OF-1001", recommendation.selected_offer_id)
        self.assertEqual(Decimal("80.00"), recommendation.estimated_net_saving.amount)

    def test_selects_highest_saving_human_review_when_no_rebook_candidate_exists(self):
        recommendation = self.ranker.rank(
            "booking-3",
            [self._evaluation("ZC3N1D", "OF-4001")],
        )

        self.assertEqual(PolicyDecision.SEND_FOR_HUMAN_REVIEW, recommendation.decision)
        self.assertEqual("OF-4001", recommendation.selected_offer_id)
        self.assertEqual(Decimal("140.00"), recommendation.estimated_net_saving.amount)

    def test_returns_do_not_rebook_when_all_candidates_are_rejected(self):
        recommendation = self.ranker.rank(
            "booking-4",
            [
                self._evaluation("LM9P4C", "OF-2001"),
                self._evaluation("HB6W9E", "OF-5001"),
            ],
        )

        self.assertEqual(PolicyDecision.DO_NOT_REBOOK, recommendation.decision)
        self.assertIsNone(recommendation.selected_offer_id)
        self.assertEqual(Decimal("0.00"), recommendation.estimated_net_saving.amount)
        self.assertEqual(["NO_REBOOKABLE_CANDIDATES"], recommendation.reason_codes)
        self.assertEqual(2, recommendation.candidate_count)

    def test_returns_do_not_rebook_when_no_candidates_exist(self):
        recommendation = self.ranker.rank("booking-5", [])

        self.assertEqual(PolicyDecision.DO_NOT_REBOOK, recommendation.decision)
        self.assertIsNone(recommendation.selected_offer_id)
        self.assertEqual(["NO_CANDIDATES_FOUND"], recommendation.reason_codes)
        self.assertEqual([], recommendation.candidates)

    def _evaluation(self, pnr: str, offer_id: str) -> CandidateEvaluation:
        booking = self._booking(pnr)
        offer = self._offer(offer_id)
        economics = self.economics.calculate(booking, offer)
        comparison = self.comparator.compare(booking, offer, economics)
        policy = self.policy.evaluate(economics, comparison)
        return CandidateEvaluation(
            offer_id=offer.offerId,
            economics=economics,
            comparison=comparison,
            policy=policy,
        )

    def _booking(self, pnr: str) -> Booking:
        return next(booking for booking in self.bookings if booking.pnr == pnr)

    def _offer(self, offer_id: str) -> FareOffer:
        return next(offer for offer in self.offers if offer.offerId == offer_id)


if __name__ == "__main__":
    unittest.main()
