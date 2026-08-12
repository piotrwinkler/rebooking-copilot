from __future__ import annotations

import argparse
import json
from pathlib import Path

from rebooking_copilot.loaders import load_fares_feed, load_pnrs
from rebooking_copilot.output import StructuredOutputBuilder
from rebooking_copilot.pipeline import build_default_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Rebooking Copilot POC pipeline."
    )
    parser.add_argument("--pnrs", default="fixtures/pnrs.json", type=Path)
    parser.add_argument("--fares", default="fixtures/fares_feed.json", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--indent", default=2, type=int)
    args = parser.parse_args()

    bookings = load_pnrs(args.pnrs).pnrs
    fare_feed = load_fares_feed(args.fares)
    recommendations = build_default_pipeline().run(bookings, fare_feed.offers)
    output = StructuredOutputBuilder().build(
        recommendations=recommendations,
        fare_snapshot_captured_at=fare_feed.capturedAt,
    )

    payload = json.dumps(output.model_dump(mode="json"), indent=args.indent)
    if args.output:
        args.output.write_text(f"{payload}\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
