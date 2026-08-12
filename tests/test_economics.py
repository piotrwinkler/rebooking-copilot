from __future__ import annotations

from decimal import Decimal
import unittest

from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.models import Booking, FareOffer
from rebooking_copilot.services.economics import (
    EconomicsCalculator,
    StaticExchangeRateProvider,
)


class EconomicsCalculatorTest(unittest.TestCase):
    def setUp(self):
        self.bookings = load_pnrs("fixtures/pnrs.json").pnrs
        self.offers = load_fares_feed("fixtures/fares_feed.json").offers
        self.calculator = EconomicsCalculator(StaticExchangeRateProvider())

    def test_calculates_positive_net_saving_in_usd(self):
        result = self.calculator.calculate(
            self._booking("QX7T2A"),
            self._offer("OF-1001"),
        )

        self.assertEqual(Decimal("480.00"), result.original_total.amount)
        self.assertEqual(Decimal("300.00"), result.candidate_total.amount)
        self.assertEqual(Decimal("100.00"), result.exchange_cost.amount)
        self.assertEqual(
            Decimal("100.00"),
            result.original_change_fee_per_passenger.amount,
        )
        self.assertEqual(
            Decimal("100.00"),
            result.candidate_change_fee_per_passenger.amount,
        )
        self.assertEqual(Decimal("80.00"), result.estimated_net_saving.amount)
        self.assertEqual("USD", result.estimated_net_saving.currency)
        self.assertFalse(result.fx_used)

    def test_multiplies_candidate_price_and_change_fee_by_passengers(self):
        result = self.calculator.calculate(
            self._booking("LM9P4C"),
            self._offer("OF-2001"),
        )

        self.assertEqual(Decimal("700.00"), result.original_total.amount)
        self.assertEqual(Decimal("640.00"), result.candidate_total.amount)
        self.assertEqual(Decimal("150.00"), result.exchange_cost.amount)
        self.assertEqual(Decimal("-90.00"), result.estimated_net_saving.amount)

    def test_normalizes_mixed_currency_values_to_usd(self):
        result = self.calculator.calculate(
            self._booking("RT5K8B"),
            self._offer("OF-3001"),
        )

        self.assertEqual(Decimal("2420.00"), result.original_total.amount)
        self.assertEqual(Decimal("2100.00"), result.candidate_total.amount)
        self.assertEqual(Decimal("0.00"), result.exchange_cost.amount)
        self.assertEqual(Decimal("320.00"), result.estimated_net_saving.amount)
        self.assertTrue(result.fx_used)
        self.assertEqual(1, len(result.fx_conversions))
        self.assertEqual("EUR", result.fx_conversions[0].source.currency)
        self.assertEqual("USD", result.fx_conversions[0].target.currency)

    def test_uses_original_change_fee_not_candidate_future_change_fee(self):
        booking = self._booking("QX7T2A").model_copy(deep=True)
        offer = self._offer("OF-1001").model_copy(deep=True)
        booking.ticket.changeFeePerPassenger.amount = Decimal("25.00")
        offer.changeFeePerPassenger.amount = Decimal("999.00")

        result = self.calculator.calculate(booking, offer)

        self.assertEqual(Decimal("25.00"), result.exchange_cost.amount)
        self.assertEqual(
            Decimal("25.00"),
            result.original_change_fee_per_passenger.amount,
        )
        self.assertEqual(
            Decimal("999.00"),
            result.candidate_change_fee_per_passenger.amount,
        )
        self.assertEqual(Decimal("155.00"), result.estimated_net_saving.amount)

    def _booking(self, pnr: str) -> Booking:
        return next(booking for booking in self.bookings if booking.pnr == pnr)

    def _offer(self, offer_id: str) -> FareOffer:
        return next(offer for offer in self.offers if offer.offerId == offer_id)


if __name__ == "__main__":
    unittest.main()
