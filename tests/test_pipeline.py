from __future__ import annotations

from decimal import Decimal
import unittest

from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.pipeline import build_default_pipeline


class RebookingPipelineTest(unittest.TestCase):
    def setUp(self):
        self.bookings = load_pnrs("fixtures/pnrs.json").pnrs
        self.offers = load_fares_feed("fixtures/fares_feed.json").offers

    def test_runs_candidate_search_and_economics_for_each_booking(self):
        results = build_default_pipeline().run(self.bookings, self.offers)

        by_booking_id = {result.booking_id: result for result in results}

        self.assertEqual(len(self.bookings), len(results))
        self.assertEqual(1, by_booking_id["QX7T2A"].candidate_count)
        self.assertEqual(
            Decimal("80.00"),
            by_booking_id["QX7T2A"].candidates[0].economics.estimated_net_saving.amount,
        )
        self.assertEqual(2, by_booking_id["HB6W9E"].candidate_count)


if __name__ == "__main__":
    unittest.main()
