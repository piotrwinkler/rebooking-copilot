# Rebooking Copilot Design

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
- The POC will consider only direct origin/destination matches as valid.
- Only offers with enough seats for all passengers will be considered candidates.

FUTURE IMPROVEMENTS:
- Support multi-segment journeys, including cases where the searchable journey origin/destination differs from individual flight legs.
- Consider whether passenger splitting is acceptable for customers that allow travelers in one booking to move to different flights.

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

FX conversion is deterministic in the POC. A `StaticExchangeRateProvider` will use hardcoded rates and never call a network API.

CONFIRMED WITH PMs:
- Positive net saving is required before a candidate can be considered a reshopping opportunity. It is a hard requirement for the whole system.

WHAT I WOULD CONFIRM WITH PMs:
- USD can be used as a comparison currency.

ASSUMPTIONS:
- The original booking's `changeFeePerPassenger` is the current exchange/rebooking cost.
- The candidate offer's `changeFeePerPassenger` describes the future fare's change policy and is not the immediate cost to perform this exchange.
- If FX conversion is used, recommendation metadata should expose it and confidence may be reduced later because the POC rate is stubbed.

FUTURE IMPROVEMENTS:
- Replace static FX rates with a timestamped FX provider and include the rate source/time in audit metadata.

### Comparator

The Comparator describes factual differences between the existing booking and a candidate after economics have been calculated. It does not decide whether to rebook and does not attach dollar values to traveler inconvenience.

Each comparison dimension is assessed as `BETTER`, `SAME`, `WORSE`, or `UNKNOWN`, with raw original/candidate values and deltas preserved where useful.

Implemented POC dimensions:
- cabin, using an explicit hierarchy
- stops
- baggage included pieces
- refundability
- departure/arrival schedule with a 15-minute equivalence tolerance
- carrier
- future change fee, using normalized per-passenger values calculated by the economics layer

ASSUMPTIONS:
- Things like fewer stops and more baggage pieces can be treated as obvious positives.
- Earlier or later schedule changes are not inherently better, so material schedule changes are `UNKNOWN`.
- Different carriers are `UNKNOWN`, not better or worse.
- Fare basis is kept as metadata elsewhere and not interpreted.
- Future change fee is compared as a future fare attribute and is separate from the immediate exchange cost.

FUTURE IMPROVEMENTS:
- Add customer-specific preferences for dimensions that are not universally better or worse.
- Compare richer fare-rule attributes when the data source provides them.

### Policy Engine

The Policy Engine is the first component that turns computed facts into a decision. Candidate Search, Economics Calculator, and Comparator do not reject candidates for business reasons; they only produce facts for policy.

`confidence` is calculated inside Policy Engine. In this POC it means how confident the system is that a given candidate is a good and safe option to rebook under the current static policy. It is a deterministic heuristic.

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

WHAT I WOULD CONFIRM WITH PMs:
- The exact penalties used for confidence computation.

ASSUMPTIONS:
- The default rule set is intentionally defensive: the system skips human review only when it is highly confident that the candidate is a good rebooking recommendation. This creates a safer path toward future automatic actions without requiring user input for every case.
- The default policy is meant to be broadly usable across customers: it optimizes for savings while avoiding quality degradations that could violate unknown customer policies. Customer-specific tuning can increase captured savings later, but the POC starts from a conservative baseline.
- Quality degradation does not become a dollar penalty in this POC; it moves the candidate to human review.

FUTURE IMPROVEMENTS:
- Allow the Ranker or customer policy to use confidence as a tie-breaker, threshold, or customer-specific rule input.
- Replace the static POC policy with versioned customer-specific policy configuration.
- Use an LLM to help parse existing human-readable policies into a structured format, or to support review of policies that cannot be represented exactly as deterministic rules.

### Candidate Evaluations

A Candidate Evaluation is the complete deterministic record for one booking/candidate pair. It is the unit passed from Policy Engine to Ranker and should contain enough information to explain, audit, and later reproduce the decision.

For this POC each evaluation should include:
- candidate `offer_id`
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

WHAT I WOULD CONFIRM WITH PMs:
- `REBOOK` outranks `SEND_FOR_HUMAN_REVIEW` even if a review candidate saves more.

ASSUMPTIONS:
- In the POC, rejected candidates remain available in the structured output for auditability and for explaining `DO_NOT_REBOOK`.

FUTURE IMPROVEMENTS:
- Return a selected subset of viable options rather than only the top recommendation when there are many strong alternatives.
- Use confidence as a tie-breaker or threshold if future policy requires it.

### Structured Output

The structured JSON output is the primary product of the POC. It is designed to be machine-readable and audit-friendly rather than optimized for human prose. It was confirmed with PMs that the end state should integrate into existing customer workflows and systems, so production may need additional API adapters or event-specific payload shapes.

The top-level payload includes:
- `schema_version`
- `fare_snapshot_captured_at`
- `recommendation_count`
- `recommendations`

Each recommendation includes the booking-level decision, selected offer, estimated net saving, confidence, reason codes, and candidate evaluations. Candidate evaluations preserve economics, comparison facts, policy decisions, confidence reasons, and rejected alternatives.

The CLI supports both printing JSON to stdout and writing it to a file:

```bash
poetry run rebooking-copilot
poetry run rebooking-copilot --output results.json
```

The Explanation Generator is deliberately not implemented in this POC as it is not a critical part of the system. If added later, it must consume the structured output and must not change decisions, savings, confidence, selected offers, or comparison facts.

FUTURE IMPROVEMENTS:
- Add API adapters or event-specific payload shapes for target customer workflows.
- Return only a subset of candidates in API responses while storing the full audit trail separately.
- Add a deterministic explanation formatter or LLM-backed explanation layer that consumes structured output without changing it.

## Where the LLM Is and Is Not

The LLM is not on the financial or policy decision path. It must not decide whether to rebook, choose an offer, calculate savings, alter confidence, or change comparison facts.

An LLM could be added as the final layer to generate a human-readable summary of the recommendation, but it is not a critical system component.

It was also confirmed with PMs that customers already have their own policies, often in unstructured formats such as human-readable PDF documents. An LLM could be useful for parsing that input into a structured policy format, or as an assistive review step for rules that cannot be represented exactly. It should not be the only decision step because it introduces uncertainty, increases cost, and makes the system harder to test and reproduce. That is especially important in money-related workflows. In this POC, all decisions can be made deterministically assuming the policies are known and correct.

## Correctness & Money Safety

All calculations and comparisons are deterministic. The system does not rely on an LLM for money, policy, ranking, confidence, or structured output. Candidate Search is intentionally broad and non-financial: it only finds potentially relevant offers. Economics then determines whether each offer is actually beneficial after considering price, passenger count, the current exchange/rebooking cost, and currency normalization.

The core safety rule is that rebooking must produce positive estimated net saving. Travel-quality changes are handled as policy constraints: if a candidate saves money but may violate customer policy or traveler expectations, the system recommends human review instead of direct rebooking.

Every recommendation includes machine-readable reason codes and candidate-level metadata so the decision path can be audited and reproduced. This is especially important for money-impacting workflows: the system should be able to show which fare snapshot, FX assumptions, candidate comparisons, and policy rules produced each recommendation.

Before any future automatic ticket exchange, production must revalidate the selected option because prices, availability, and fare attributes can change after the recommendation is generated. This is especially important after human review, which may introduce a delay between recommendation and action.

## Scale, Cost & Observability

If the system processes a much larger booking volume, latency and throughput will become product concerns. The current POC evaluates a static fare feed in memory; production fare search is likely to be the main bottleneck and cost driver. Searches should be grouped, cached, or batched where possible, and large workloads should be processed asynchronously with queues and workers.

If an LLM is later used for human-readable explanations or policy parsing, token usage and latency must be tracked separately. LLM calls should remain outside the critical decision path and should use cost controls such as prompt caching, deterministic templates, and clear fallbacks.

With many data sources, production would also need source-specific parsers and validation monitoring. At high booking volumes, sending too many recommendations to human review can become operationally expensive for customers, so configurable automation may eventually be needed for high-confidence cases.

Several observability layers should be introduced to track whether the system is healthy, reproducible, and actually creating trusted savings:

### System Observability

- CPU, memory, disk, and container/process restarts
- job queue depth and worker throughput if processing becomes asynchronous
- dependency health for fare providers, FX providers, policy stores, and output sinks
- error rates by component, especially fare search, FX conversion, policy evaluation, and output delivery

### Application Observability

Every recommendation should be reproducible from logged or persisted inputs and component outputs. At minimum, store or trace:

- booking snapshot and fare snapshot identifiers
- fare snapshot capture time
- applied policy name/version
- FX rates and conversion metadata
- candidate search inputs and candidate counts
- candidate evaluations, including economics, comparison dimensions, policy decisions, confidence, and reason codes
- final booking-level recommendation

The application should also emit operational metrics:

- bookings processed per run
- candidates evaluated per booking
- latency per pipeline stage
- recommendation counts by decision
- validation or parsing failures by input source

### Business Observability

- estimated savings by customer, route, carrier, currency, and policy version
- accepted, rejected, and overridden recommendations
- realized savings after actual rebooking
- false positives where a recommendation looked good but could not be executed safely
- false negatives found by human agents or later fare snapshots
- stale fare snapshots and cases where prices changed before action

### LLM/Agent Observability

If LLM usage is added later, track it separately from deterministic decision logic:

- token usage
- token cost
- latency per LLM call
- prompt/template version
- fallback rate
- evaluation scores for generated explanations or policy extraction

## Assumptions & Open Questions

Most assumptions and questions are attached to the relevant architecture sections. The POC uses a deliberately conservative static policy that should be broadly applicable across customers: it captures clear savings, avoids direct rebooking when quality degradation is detected, and sends ambiguous cases to human review.

Important assumptions:

- Fixtures represent single-segment itineraries.
- Offer matching by origin, destination, departure date, and seat availability is sufficient for the POC.
- Positive net saving is the hard financial gate.
- USD is acceptable as the normalized comparison currency for the POC.
- The original booking's change fee is the immediate exchange/rebooking cost.
- Customer-specific policy ingestion is out of scope.
- Automatic ticket exchange is out of scope.

Open questions:

- Are the confidence penalties directionally acceptable to the business?
- Should `REBOOK` always outrank `SEND_FOR_HUMAN_REVIEW`, even when the review candidate saves more?
- Is there a minimum absolute or percentage saving threshold beyond positive net saving?
- How fresh must a fare snapshot be before a recommendation becomes stale?
- Which quality degradations should different customer segments allow for direct rebooking?

## Deliberately Not Done / Next Steps

Not implemented in this first design slice:

- Explanation Generator (not enough time)
- multi-segment journey matching
- passenger splitting across different flights
- customer-policy ingestion or configuration, potentially assisted by an LLM
- timestamped production FX provider
- real ticket-exchange pricing model
- live fare search
- automatic ticket exchange, which could later be controlled by a feature flag and a configurable confidence threshold
- UI or workflow integration
- live LLM calls
- a component that revalidates the chosen candidate before rebooking if a human reviews it later, because prices and fare attributes can change dynamically
- API adapters or event-specific output payloads
- partial API responses backed by full audit storage
- CI/CD pipeline, Docker, linters
- integration, E2E tests

## AI Usage Note

I used ChatGPT to discuss the assignment, fixtures, possible system boundaries, and questions worth clarifying with PMs. After receiving PM feedback, I used Codex iteratively to draft `DESIGN.md` sections and implement the prototype component by component. I reviewed and adjusted the design after each iteration while Codex generated or updated the corresponding code.

One AI suggestion I rejected was using an LLM as a judge for this POC. For the current scope, the decision can be represented as deterministic rules over known fixture attributes. An LLM judge would increase cost and uncertainty without adding meaningful decision quality, and would make money-impacting behavior harder to test and reproduce.
