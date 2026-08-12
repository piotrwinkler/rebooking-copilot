# Rebooking Copilot Design

This document is a living design note for the Rebooking Copilot take-home prototype.
It starts intentionally small and will grow alongside the implementation.

## Approach & Architecture

The prototype reviews existing ticketed bookings against a static fare snapshot and emits one structured recommendation per booking. The core product objective is financial saving: travel-quality changes are treated as constraints that determine whether a cheaper option can be recommended directly or should be sent to a human.

The planned flow is:

```text
                  Fare Snapshot
                       |
Booking -----> Candidate Search
                       |
                       v
              Economics Calculator
                       |
                       v
                   Comparator
                       |
                       v
                  Policy Engine <------------+
                       |                      |
                       |              Customer Policy
                       |               Configuration
                       |               FUTURE WORK
                       |                      |
                       v
     Candidate Evaluations (unified data format)
                       |
                       v
               Candidate Ranker
                       |
                       v
                 Recommendation
             /          |           \
         REBOOK   HUMAN_REVIEW   DO_NOT_REBOOK
                       |
                       v
              Structured Output
                       |
                       v
        Explanation Generator (future)
                /              \
              LLM        deterministic
                              fallback
```

Deterministic code owns candidate search, economics, fare comparison, policy decisions, ranking, and structured output. This keeps financial and policy behavior auditable and reproducible.

The codebase keeps domain services in `rebooking_copilot/services/` and wires them through a thin pipeline. The current runnable pipeline loads fixture bookings and fares, runs Candidate Search, calculates normalized economics for each candidate, compares fare quality dimensions, applies per-candidate policy, then ranks candidate evaluations into one booking-level recommendation. Candidate evaluations remain embedded in the structured output for auditability.

### Candidate Search

Candidate Search is the first implemented subsystem. For this POC, an offer is considered a candidate for a booking when:

- the offer origin matches the booking origin
- the offer destination matches the booking destination
- the offer departure date matches the booking departure date
- the offer has enough available seats for all passengers on the booking

Search does not filter by price. Every route/date/seat-valid offer is passed to the economics layer, where change fees and FX conversion are included before deciding whether the offer produces a real net saving.

ASSUMPTIONS: 
- The POC will consider only direct origin/destination matches as valid. Production search could support multi-segment journeys, including cases where the searchable journey origin/destination differs from individual flight legs.
- Only flights with enough seats for all passengers will be chosen. Production search could allow splitting passengers into different flights.

### Economics Calculator

The Economics Calculator determines whether a candidate produces a real financial saving after normalizing currencies and applying the current exchange/rebooking cost. It is separate from the Comparator because money calculations need explicit arithmetic, FX handling, and audit metadata; travel-quality comparison should consume the calculated economics rather than recompute them.

For each booking/candidate pair it should calculate:

- original booking value in the normalized comparison currency
- candidate total fare in the normalized comparison currency
- current exchange/rebooking cost in the normalized comparison currency
- estimated net saving
- whether FX conversion was used

The estimated net saving formula for the POC is:

```text
original_total_paid
- candidate_price_per_passenger * passenger_count
- original_change_fee_per_passenger * passenger_count
= estimated_net_saving
```

All monetary arithmetic should use `Decimal`, not floating-point numbers. The structured output should preserve money amounts as strings or Decimal-safe values to avoid accidental precision loss.

FX conversion is deterministic in the POC. A `StaticExchangeRateProvider` will use hardcoded rates and never call a network API. **Production would replace this with a timestamped FX provider and include the rate source/time in audit metadata.**

CONFIRMED WITH PMs:
- Positive net saving is required before a candidate can be considered a reshopping opportunity. It is a hard requirement for the whole system.

WHAT I WOULD LIKE TO CONFIRM WITH PMs OR OTHERWISE VERIFY IN THE LITERATURE:
- USD can be used as a comparison currency.

ASSUMPTIONS:
- The original booking's `changeFeePerPassenger` is the current exchange/rebooking cost.
- The candidate offer's `changeFeePerPassenger` describes the future fare's change policy and is not the immediate cost to perform this exchange.
- If FX conversion is used, recommendation metadata should expose it and confidence may be reduced later because the POC rate is stubbed.

### Comparator

The Comparator describes factual differences between the existing booking and a candidate after economics have been calculated. It does not decide whether to rebook and does not attach dollar values to traveler inconvenience.

Each comparison dimension is assessed as `BETTER`, `SAME`, `WORSE`, or `UNKNOWN`, with raw original/candidate values and deltas preserved where useful.

Implemented POC dimensions:
- cabin, using an explicit hierarchy
- stops
- baggage included pieces
- refundability
- departure/arrival schedule with a 15 minute equivalence tolerance
- carrier
- future change fee, using normalized per-passenger values calculated by the economics layer

ASSUMPTIONS:
- Earlier or later schedule changes are not inherently better, so material schedule changes are `UNKNOWN`.
- Different carriers are `UNKNOWN`, not better or worse.
- Fare basis is kept as metadata elsewhere and not interpreted.
- Future change fee is compared as a future fare attribute and is separate from the immediate exchange cost.

### Policy Engine

The Policy Engine is the first component that turns computed facts into a decision. Candidate Search, Economics Calculator, and Comparator do not reject candidates for business reasons; they only produce facts for policy.

`confidence` is calculated inside Policy Engine. In this POC it means how confident the system is that a given candidate is a good/safe option to rebook under the current static policy. It is a deterministic heuristic, not a calibrated probability. Ranker could later use this value as a tie-breaker, threshold, or customer-specific rule input.

The POC policy is intentionally static:
- `DO_NOT_REBOOK` when estimated net saving is zero or negative.
- `REBOOK` when estimated net saving is positive and every comparison dimension is `BETTER` or `SAME`.
- `SEND_FOR_HUMAN_REVIEW` when estimated net saving is positive and at least one comparison dimension is `WORSE` or `UNKNOWN`.

| Condition | Decision | Reason codes | Rationale |
| --- | --- | --- | --- |
| `estimated_net_saving <= 0` | `DO_NOT_REBOOK` | `NON_POSITIVE_NET_SAVING` | Rebooking must produce a real financial saving after change fees and FX. |
| `estimated_net_saving > 0` and all comparison dimensions are `BETTER` or `SAME` | `REBOOK` | `POSITIVE_NET_SAVING`, `ALL_QUALITY_DIMENSIONS_ACCEPTABLE` | The candidate saves money and does not degrade any evaluated travel-quality attribute. |
| `estimated_net_saving > 0` and at least one dimension is `WORSE` | `SEND_FOR_HUMAN_REVIEW` | `POSITIVE_NET_SAVING`, `WORSE_<DIMENSION>` | The candidate saves money, but the traveler/client may not accept the degradation. |
| `estimated_net_saving > 0` and at least one dimension is `UNKNOWN` | `SEND_FOR_HUMAN_REVIEW` | `POSITIVE_NET_SAVING`, `UNKNOWN_<DIMENSION>` | The candidate saves money, but the system cannot safely decide whether the change is acceptable. |

The policy also emits stable reason codes such as `NON_POSITIVE_NET_SAVING`, `ALL_QUALITY_DIMENSIONS_ACCEPTABLE`, `WORSE_REFUNDABILITY`, and `UNKNOWN_SCHEDULE`.

Confidence starts at `1.00` only for candidates with positive net saving. Candidates with zero or negative net saving receive `0.00` because they are not good rebooking options under the core business requirement.

Initial POC confidence penalties:

| Signal | Penalty |
| --- | --- |
| Cabin downgrade | `-0.30` |
| Additional stop | `-0.25` |
| Loss of refundability | `-0.20` |
| Lost baggage piece | `-0.15` |
| Material schedule change / unknown schedule impact | `-0.15` |
| Different carrier / unknown carrier impact | `-0.10` |
| Worse future change fee | `-0.10` |
| Other unknown comparison | `-0.20` |
| Stubbed FX conversion | `-0.10` |

The result is clamped to `[0.00, 1.00]` and emitted with confidence reason codes such as `CONFIDENCE_PENALTY_REFUNDABILITY` or `CONFIDENCE_PENALTY_STUBBED_FX`.

CONFIRMED WITH PMs:
- Customers should be able to define their own rules in production but for the purpose of this POC the rules should be static.
- Positive net saving is a hard gate before any reshopping opportunity exists.

WHAT I WOULD CONFIRM:
- The penalties for confidence computation
- The default set of rules for the whole system is extremly defensive - we skip human review only when we are 100% sure that something is a good rebooking recomendation. It can help with enabling automatic actions without the need of any user input. 

ASSUMPTIONS:
- Quality degradation does not become a dollar penalty in this POC; it moves the candidate to human review.
- Customer-specific policy configuration is future work, but the service boundary should allow replacing this static policy later. An LLM could be used to parse already existing human readable policies into the structured format or could be add as an element of the reasoning system for policies that could not be parsed to the structured format.

### Candidate Evaluations

A Candidate Evaluation is the complete deterministic record for one booking/candidate pair. It is the unit passed from Policy Engine to Ranker and should contain enough information to explain, audit, and later reproduce the decision.

For this POC each evaluation should include:
- selected `offer_id`
- normalized economics, including estimated net saving and FX metadata
- comparison dimensions and raw deltas
- policy decision, reason codes, confidence, and confidence reason codes

Candidate Evaluations are intentionally preserved even when policy returns `DO_NOT_REBOOK`. This keeps the output auditable: the system can show that an offer was found, priced, compared, and then rejected by policy because it did not produce positive net saving or failed another rule.

### Candidate Ranker

The Ranker converts multiple candidate-level policy evaluations into one booking-level recommendation. It does not invent a utility function and does not price traveler inconvenience. Ranking follows the product objective: capture the best acceptable saving.

The POC ranking rules are:

| Available candidate evaluations | Booking-level decision | Selected offer | Ranking rule |
| --- | --- | --- | --- |
| At least one `REBOOK` candidate | `REBOOK` | `REBOOK` candidate with highest estimated net saving | Directly acceptable savings win over human-review candidates. |
| No `REBOOK`, at least one `SEND_FOR_HUMAN_REVIEW` candidate | `SEND_FOR_HUMAN_REVIEW` | review candidate with highest estimated net saving | The best saving is surfaced for human judgment. |
| No `REBOOK` and no `SEND_FOR_HUMAN_REVIEW` candidates | `DO_NOT_REBOOK` | `null` | No policy-acceptable reshopping opportunity exists. |

CONFIRMED WITH PMs:
- Highest estimated net saving is the most important criterion.

WHAT I WOULD LIKE TO CONFIRM:
- `REBOOK` outranks `SEND_FOR_HUMAN_REVIEW` even if a review candidate saves more.
- If there is many options we could potentially increase the number of the options presented to customers to selected few or many. Won't be implemented here but could be as a future improvement.

ASSUMPTIONS:
- Rejected candidates should remain available in metadata where practical, especially for explaining `DO_NOT_REBOOK`.

### Structured Output

The structured JSON output is the primary product of the POC. It is designed to be machine-readable and audit-friendly rather than optimized for human prose. It was confirmed with PMs that the goal is to integrate this into existing customer services and systems so additional/dedicated layers of data parsing may be needed in production.

The top-level payload includes:
- `schema_version`
- `fare_snapshot_captured_at`
- `recommendation_count`
- `recommendations`

Each recommendation includes the booking-level decision, selected offer, estimated net saving, confidence, reason codes, and candidate evaluations. Candidate evaluations preserve economics, comparison facts, policy decisions, confidence reasons, and rejected alternatives where practical.

The CLI supports both printing JSON to stdout and writing it to a file:

```bash
poetry run rebooking-copilot
poetry run rebooking-copilot --output results.json
```

The Explanation Generator is deliberately not implemented in this POC. Production could add a deterministic explanation formatter or an LLM-backed explanation layer later, but it must consume the structured output and must not change decisions, savings, confidence, selected offers, or comparison facts.

## Where the LLM Is and Is Not

The LLM is not on the financial or policy decision path. It must not decide whether to rebook, choose an offer, calculate savings, alter confidence, or change comparison facts.

If an LLM is added later, it will only generate concise human-readable explanations from an already-computed structured recommendation. Explanation generation is future work and is not required for the POC to run.

It was also confirmed with PMs that customers alrady have their own policies defined but in unstructured way like human readable PDF documents for example. LLM could be a useful tool in parsing such input to the structured format or can be added as a judge in case some rules could not be parsed exactly as they are. But it should never act as the only decision step because it introduces uncertainty to the system, increases costs and makes it harder to test and produce repitable results which is especially important in the money related systems. And in this systems many decisions can be made deterministically.

## Correctness & Money Safety

The first safety rule is that candidate search is intentionally broad and non-financial: it only finds potentially relevant offers. The economics layer will decide whether an offer is actually beneficial after considering price, passenger count, the current exchange/rebooking cost, and currency normalization.

Current assumptions to encode:

- USD is the normalized comparison currency.
- The original booking's `changeFeePerPassenger` is the current exchange/rebooking cost.
- The candidate offer's `changeFeePerPassenger` is treated as a future fare attribute for comparison, not as the immediate exchange cost.
- `DO_NOT_REBOOK` results should still include useful metadata explaining why no candidate was selected.

## Scale, Cost & Observability

Several layers of observability should be introduced for the application:

### 

## Assumptions & Open Questions

The POC assumes the fixture shape: one itinerary segment per booking and one fare snapshot loaded from static JSON. Customer-specific policies are future work; this prototype will use a static policy and document its rationale as it is implemented.

Open questions to revisit as the design grows:

- What customer-specific travel-quality degradations are acceptable for direct rebooking?
- What minimum saving threshold, if any, should be required beyond positive net saving?
- How fresh must a fare snapshot be before a recommendation is considered actionable?

## Deliberately Not Done / Next Steps

Not implemented in this first design slice:

- multi-segment journey matching
- customer-policy ingestion or configuration
- live fare search
- automatic ticket exchange
- UI or workflow integration
- live LLM calls
- Explanation Generator

The next implementation step is to create domain models and fixture loading, then implement Candidate Search with tests for route/date matching, insufficient seats, no price filtering during search, and the single-segment fixture assumption.

## AI Usage Note

This project is being developed with Codex as an AI coding assistant. I am using it to review the assignment, draft design slices, and implement the prototype iteratively while keeping deterministic financial and policy logic explicit. One AI suggestion I rejected was using a generic agent framework for the decision path; that would add unnecessary complexity and make money-impacting behavior harder to audit for this POC.
