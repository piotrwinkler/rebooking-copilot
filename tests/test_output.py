from __future__ import annotations

import unittest

from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.output import StructuredOutputBuilder
from rebooking_copilot.pipeline import build_default_pipeline


class StructuredOutputBuilderTest(unittest.TestCase):
    def test_wraps_recommendations_with_run_metadata(self):
        bookings = load_pnrs("fixtures/pnrs.json").pnrs
        fare_feed = load_fares_feed("fixtures/fares_feed.json")
        recommendations = build_default_pipeline().run(bookings, fare_feed.offers)

        output = StructuredOutputBuilder().build(
            recommendations=recommendations,
            fare_snapshot_captured_at=fare_feed.capturedAt,
        )

        self.assertEqual("poc.v1", output.schema_version)
        self.assertEqual(fare_feed.capturedAt, output.fare_snapshot_captured_at)
        self.assertEqual(len(bookings), output.recommendation_count)
        self.assertEqual("QX7T2A", output.recommendations[0].booking_id)


if __name__ == "__main__":
    unittest.main()
