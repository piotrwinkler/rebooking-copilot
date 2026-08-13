# Rebooking Copilot

POC for a flight reshopping / rebooking recommendation agent. The project is being built iteratively; the current implementation covers fixture loading, Candidate Search, Economics Calculator, Comparator, Policy Engine, Candidate Ranker, and a thin pipeline that connects them.

## Setup

This project uses Poetry for dependency management and virtualenv creation. The
repository config tells Poetry to create the virtualenv locally as `.venv/`.

```bash
poetry install
```

If Poetry cannot find `python` because pyenv is set to `system`, either keep the
checked-in `.python-version` file or point Poetry at any local Python
interpreter explicitly:

```bash
poetry env use python3
poetry install
```

## Run Tests

```bash
poetry run python -m unittest discover -s tests
```

## Run Pipeline

```bash
poetry run rebooking-copilot
```

This prints a structured JSON payload with one booking-level recommendation per booking, plus candidate-level economics, comparison details, policy decisions, and confidence for auditability. Runtime uses only the checked-in fixture JSON and static FX rates; no external APIs, paid services, network calls, or API keys are required.

Abridged example output shape:

```json
{
  "schema_version": "poc.v1",
  "fare_snapshot_captured_at": "2026-07-08T09:00:00Z",
  "recommendation_count": 5,
  "recommendations": [
    {
      "booking_id": "QX7T2A",
      "decision": "REBOOK",
      "selected_offer_id": "OF-1001",
      "estimated_net_saving": {
        "amount": "80.00",
        "currency": "USD"
      },
      "confidence": "1.00",
      "reason_codes": [
        "POSITIVE_NET_SAVING",
        "ALL_QUALITY_DIMENSIONS_ACCEPTABLE"
      ],
      "candidate_count": 1,
      "candidates": [
        {
          "offer_id": "OF-1001",
          "policy": {
            "decision": "REBOOK",
            "reason_codes": [
              "POSITIVE_NET_SAVING",
              "ALL_QUALITY_DIMENSIONS_ACCEPTABLE"
            ],
            "confidence": "1.00",
            "confidence_reason_codes": []
          }
        }
      ]
    }
  ]
}
```

To write the full output to a file:

```bash
poetry run rebooking-copilot --output results.json
```

The POC intentionally does not implement the Explanation Generator; human-readable explanations are future work.

The current test suite covers Candidate Search behavior:

- route/date matching
- rejecting offers without enough seats
- keeping price filtering out of search
- rejecting multi-segment bookings for this POC slice
- calculating net savings with passenger count and change fees
- normalizing mixed-currency calculations to USD with static FX
- comparing candidate fare quality dimensions
- applying the POC policy to each candidate
- ranking candidate evaluations into one booking-level recommendation
- building structured output for the CLI

## Project Shape

- `fixtures/` contains the assignment input JSON.
- `rebooking_copilot/models.py` defines Pydantic domain models.
- `rebooking_copilot/loaders.py` loads fixture JSON into typed models.
- `rebooking_copilot/services/fare_search.py` implements Candidate Search.
- `rebooking_copilot/services/economics.py` implements static FX and net-saving calculations.
- `rebooking_copilot/services/comparator.py` implements factual fare comparison.
- `rebooking_copilot/services/policy.py` implements per-candidate policy decisions.
- `rebooking_copilot/services/ranker.py` implements booking-level candidate ranking.
- `rebooking_copilot/pipeline.py` wires implemented services together.
- `rebooking_copilot/output.py` wraps recommendations in the final structured output payload.
- `rebooking_copilot/__main__.py` provides the CLI entrypoint.
- `DESIGN.md` is the living design document and should be updated as each subsystem is implemented.
