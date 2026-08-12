from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from rebooking_copilot.models import (
    Booking,
    EconomicsResult,
    FareOffer,
    FxConversion,
    Money,
)


MONEY_QUANTUM = Decimal("0.01")


class MissingExchangeRateError(ValueError):
    """Raised when the POC static FX table cannot convert a currency pair."""


class ExchangeRateProvider(Protocol):
    def convert(self, money: Money, target_currency: str) -> tuple[Money, FxConversion | None]:
        ...


class StaticExchangeRateProvider:
    def __init__(self, rates: dict[tuple[str, str], Decimal] | None = None):
        self._rates = rates or {
            ("EUR", "USD"): Decimal("1.10"),
            ("USD", "EUR"): Decimal("0.91"),
        }

    def convert(self, money: Money, target_currency: str) -> tuple[Money, FxConversion | None]:
        source_currency = money.currency.upper()
        target_currency = target_currency.upper()
        source = Money(amount=_quantize_money(money.amount), currency=source_currency)

        if source_currency == target_currency:
            return source, None

        if source.amount == Decimal("0"):
            return Money(amount=source.amount, currency=target_currency), None

        rate = self._rates.get((source_currency, target_currency))
        if rate is None:
            raise MissingExchangeRateError(
                f"No static FX rate configured for {source_currency}->{target_currency}."
            )

        target = Money(
            amount=_quantize_money(source.amount * rate),
            currency=target_currency,
        )
        return target, FxConversion(source=source, target=target, rate=rate)


class EconomicsCalculator:
    def __init__(
        self,
        exchange_rate_provider: ExchangeRateProvider,
        comparison_currency: str = "USD",
    ):
        self._exchange_rate_provider = exchange_rate_provider
        self._comparison_currency = comparison_currency.upper()

    def calculate(self, booking: Booking, offer: FareOffer) -> EconomicsResult:
        original_total, original_fx = self._convert(booking.ticket.totalPaid)
        candidate_total = Money(
            amount=_quantize_money(offer.price.amount * booking.passengers),
            currency=offer.price.currency,
        )
        candidate_total, candidate_fx = self._convert(candidate_total)

        exchange_cost = Money(
            amount=_quantize_money(
                booking.ticket.changeFeePerPassenger.amount * booking.passengers
            ),
            currency=booking.ticket.changeFeePerPassenger.currency,
        )
        exchange_cost, exchange_fx = self._convert(exchange_cost)

        estimated_net_saving = Money(
            amount=_quantize_money(
                original_total.amount - candidate_total.amount - exchange_cost.amount
            ),
            currency=self._comparison_currency,
        )
        fx_conversions = [
            conversion
            for conversion in (original_fx, candidate_fx, exchange_fx)
            if conversion is not None
        ]

        return EconomicsResult(
            original_total=original_total,
            candidate_total=candidate_total,
            exchange_cost=exchange_cost,
            estimated_net_saving=estimated_net_saving,
            fx_used=bool(fx_conversions),
            fx_conversions=fx_conversions,
        )

    def _convert(self, money: Money) -> tuple[Money, FxConversion | None]:
        return self._exchange_rate_provider.convert(money, self._comparison_currency)


def _quantize_money(amount: Decimal) -> Decimal:
    return amount.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
