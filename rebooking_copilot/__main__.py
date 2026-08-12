from __future__ import annotations

import argparse
import json
from pathlib import Path

from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.pipeline import build_default_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Rebooking Copilot POC pipeline."
    )
    parser.add_argument("--pnrs", default="fixtures/pnrs.json", type=Path)
    parser.add_argument("--fares", default="fixtures/fares_feed.json", type=Path)
    parser.add_argument("--indent", default=2, type=int)
    args = parser.parse_args()

    bookings = load_pnrs(args.pnrs).pnrs
    offers = load_fares_feed(args.fares).offers
    results = build_default_pipeline().run(bookings, offers)

    payload = [result.model_dump(mode="json") for result in results]
    print(json.dumps(payload, indent=args.indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
