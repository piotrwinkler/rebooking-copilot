from __future__ import annotations

import json
from pathlib import Path

from rebooking_copilot.models import FaresFeed, PnrFixture


def load_pnrs(path: str | Path) -> PnrFixture:
    with Path(path).open(encoding="utf-8") as file:
        return PnrFixture(**json.load(file))


def load_fares_feed(path: str | Path) -> FaresFeed:
    with Path(path).open(encoding="utf-8") as file:
        return FaresFeed(**json.load(file))
