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


class PolicyDecision(str, Enum):
    REBOOK = "REBOOK"
    SEND_FOR_HUMAN_REVIEW = "SEND_FOR_HUMAN_REVIEW"
    DO_NOT_REBOOK = "DO_NOT_REBOOK"


class PolicyEvaluation(BaseModel):
    decision: PolicyDecision
    reason_codes: list[str]
    confidence: Decimal
    confidence_reason_codes: list[str]


class CandidateEvaluation(BaseModel):
    offer_id: str
    economics: EconomicsResult
    comparison: FareComparison
    policy: PolicyEvaluation


class BookingRecommendation(BaseModel):
    booking_id: str
    decision: PolicyDecision
    selected_offer_id: str | None
    estimated_net_saving: Money
    confidence: Decimal
    reason_codes: list[str]
    candidate_count: int
    candidates: list[CandidateEvaluation]


class StructuredOutput(BaseModel):
    schema_version: str
    fare_snapshot_captured_at: datetime
    recommendation_count: int
    recommendations: list[BookingRecommendation]


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
