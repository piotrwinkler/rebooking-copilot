from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


class Money(BaseModel):
    amount: Decimal
    currency: str


class FxConversion(BaseModel):
    source: Money
    target: Money
    rate: Decimal


class EconomicsResult(BaseModel):
    original_total: Money
    candidate_total: Money
    exchange_cost: Money
    original_change_fee_per_passenger: Money
    candidate_change_fee_per_passenger: Money
    estimated_net_saving: Money
    fx_used: bool
    fx_conversions: list[FxConversion]


class ComparisonAssessment(str, Enum):
    BETTER = "BETTER"
    SAME = "SAME"
    WORSE = "WORSE"
    UNKNOWN = "UNKNOWN"


class ComparisonDimension(BaseModel):
    name: str
    assessment: ComparisonAssessment
    original: object
    candidate: object
    delta: object | None = None


class FareComparison(BaseModel):
    dimensions: list[ComparisonDimension]


class FlightSegment(BaseModel):
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    carrier: str
    flightNumber: str
    stops: int
    cabin: str
    fareBasis: str


class Ticket(BaseModel):
    pricePerPassenger: Money
    totalPaid: Money
    cabin: str
    refundable: bool
    changeFeePerPassenger: Money
    baggageIncludedPieces: int


class Booking(BaseModel):
    pnr: str
    passengers: int
    itinerary: list[FlightSegment]
    ticket: Ticket


class OfferRoute(BaseModel):
    origin: str
    destination: str
    departureDate: date


class FareOffer(BaseModel):
    offerId: str
    route: OfferRoute
    carrier: str
    flightNumber: str
    departure: datetime
    arrival: datetime
    stops: int
    cabin: str
    fareBasis: str
    price: Money
    refundable: bool
    changeFeePerPassenger: Money
    baggageIncludedPieces: int
    seatsAvailable: int


class PnrFixture(BaseModel):
    pnrs: list[Booking]


class FaresFeed(BaseModel):
    capturedAt: datetime
    offers: list[FareOffer]
