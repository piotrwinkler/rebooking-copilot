# Rebooking Copilot

POC for a flight reshopping / rebooking recommendation agent. The project is being built iteratively; the current implementation covers fixture loading, Candidate Search, Economics Calculator, Comparator, and a thin pipeline that connects them.

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

This prints the current intermediate output: candidate offers per booking with normalized economics and fare comparison details. Final recommendations will be added once Policy Engine and Ranker are implemented.

The current test suite covers Candidate Search behavior:

- route/date matching
- rejecting offers without enough seats
- keeping price filtering out of search
- rejecting multi-segment bookings for this POC slice
- calculating net savings with passenger count and change fees
- normalizing mixed-currency calculations to USD with static FX
- comparing candidate fare quality dimensions

## Project Shape

- `fixtures/` contains the assignment input JSON.
- `rebooking_copilot/models.py` defines Pydantic domain models.
- `rebooking_copilot/loaders.py` loads fixture JSON into typed models.
- `rebooking_copilot/services/fare_search.py` implements Candidate Search.
- `rebooking_copilot/services/economics.py` implements static FX and net-saving calculations.
- `rebooking_copilot/services/comparator.py` implements factual fare comparison.
- `rebooking_copilot/pipeline.py` wires implemented services together.
- `rebooking_copilot/__main__.py` provides the CLI entrypoint.
- `DESIGN.md` is the living design document and should be updated as each subsystem is implemented.
