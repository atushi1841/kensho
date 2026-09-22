#!/usr/bin/env python3
"""tcg-price-query: price-trend query engine over the accumulated TCG dataset.

Reads data/tcg_dataset/ (JSONL accumulated observations) and exposes three
read-only query primitives used by the value-movement API / MCP:

  - current price for an item (by URL or name substring)
  - price history (time series) for an item
  - top movers ranking (biggest |delta| in used price across observations)
    with an optional "uptrend/downtrend" filter.

Pure-stdlib so it can run anywhere. No network. Data is data/tcg_dataset/accumulated.jsonl.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ACCUMULATED = PROJECT_DIR / "data" / "tcg_dataset" / "accumulated.jsonl"


@dataclass
class ItemSeries:
    key: str
    name: str
    url: str
    keyword: str
    observations: list[dict[str, Any]] = field(default_factory=list)

    def used_prices(self) -> list[tuple[str, Optional[int]]]:
        """Sorted (collected_at, used_price) pairs, oldest first."""
        out = []
        for obs in self.observations:
            ts = obs.get("collected_at", "")
            u = obs.get("used_price_jpy")
            if isinstance(u, int):
                out.append((ts, u))
        out.sort(key=lambda t: t[0])
        return out

    def current_used_price(self) -> Optional[int]:
        prices = self.used_prices()
        return prices[-1][1] if prices else None

    def first_used_price(self) -> Optional[int]:
        prices = self.used_prices()
        return prices[0][1] if prices else None

    def delta(self) -> Optional[int]:
        first, last = self.first_used_price(), self.current_used_price()
        if first is None or last is None:
            return None
        return last - first


def load_observations(path: Path = ACCUMULATED) -> list[dict[str, Any]]:
    """Read accumulated.jsonl into a list of observation dicts."""
    if not path.exists():
        return []
    obs: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return obs


def _item_key(rec: dict[str, Any]) -> str:
    return rec.get("url") or ("n:" + rec.get("name", ""))


def build_series(obs: list[dict[str, Any]]) -> dict[str, ItemSeries]:
    """Group observations into per-item time series."""
    series: dict[str, ItemSeries] = {}
    for rec in obs:
        key = _item_key(rec)
        s = series.get(key)
        if s is None:
            s = ItemSeries(
                key=key,
                name=rec.get("name", ""),
                url=rec.get("url", ""),
                keyword=rec.get("keyword", ""),
            )
            series[key] = s
        s.observations.append(rec)
    return series


def match_items(series: dict[str, ItemSeries], query: str) -> list[ItemSeries]:
    """Return series whose name or url contains the query (case-insensitive)."""
    q = query.strip().lower()
    if not q:
        return []
    hits = []
    for s in series.values():
        if q in s.name.lower() or q in s.url.lower():
            hits.append(s)
    return hits


def current_price(obs: list[dict[str, Any]], item: str) -> dict[str, Any]:
    """Current (latest) used/new/list price + snapshot metadata for an item."""
    series = build_series(obs)
    hits = match_items(series, item)
    if not hits:
        return {"found": False, "query": item, "matches": 0,
                "message": "no item matched that name/URL in the dataset"}
    latest: Optional[dict[str, Any]] = None
    for s in hits:
        for o in s.observations:
            if latest is None or o.get("collected_at", "") >= latest.get("collected_at", ""):
                latest = o
    assert latest is not None  # hits is non-empty so latest was set
    return {
        "found": True,
        "query": item,
        "matches": len(hits),
        "name": latest.get("name", ""),
        "url": latest.get("url", ""),
        "keyword": latest.get("keyword", ""),
        "in_stock": latest.get("in_stock", None),
        "used_price_jpy": latest.get("used_price_jpy"),
        "new_price_jpy": latest.get("new_price_jpy"),
        "list_price_jpy": latest.get("list_price_jpy"),
        "marketplace_price_jpy": latest.get("marketplace_price_jpy"),
        "collected_at": latest.get("collected_at", ""),
    }


def price_history(obs: list[dict[str, Any]], item: str,
                  limit: int = 50) -> dict[str, Any]:
    """Time series of prices for an item, oldest first."""
    series = build_series(obs)
    hits = match_items(series, item)
    if not hits:
        return {"found": False, "query": item,
                "message": "no item matched that name/URL in the dataset"}
    # point at the best (longest) matched series
    s = max(hits, key=lambda s: len(s.observations))
    rows = []
    for o in sorted(s.observations, key=lambda o: o.get("collected_at", "")):
        rows.append({
            "collected_at": o.get("collected_at", ""),
            "used_price_jpy": o.get("used_price_jpy"),
            "new_price_jpy": o.get("new_price_jpy"),
            "list_price_jpy": o.get("list_price_jpy"),
            "marketplace_price_jpy": o.get("marketplace_price_jpy"),
            "in_stock": o.get("in_stock", None),
        })
    return {
        "found": True,
        "query": item,
        "name": s.name,
        "url": s.url,
        "keyword": s.keyword,
        "observation_count": len(rows),
        "history": rows[-limit:],
    }


def top_movers(obs: list[dict[str, Any]], direction: Optional[str] = None,
               limit: int = 10) -> dict[str, Any]:
    """Rank items by |used-price change| across observations.

    direction: None (both), "up" (price rose / uptrend), "down" (price fell).
    """
    series = build_series(obs)
    movers = []
    for s in series.values():
        delta = s.delta()
        if delta is None or delta == 0:
            continue
        if direction == "up" and delta <= 0:
            continue
        if direction == "down" and delta >= 0:
            continue
        movers.append({
            "name": s.name,
            "url": s.url,
            "keyword": s.keyword,
            "first_price_jpy": s.first_used_price(),
            "last_price_jpy": s.current_used_price(),
            "delta_jpy": delta,
            "observations": len(s.observations),
        })
    movers.sort(key=lambda m: abs(m["delta_jpy"]), reverse=True)
    return {
        "direction": direction or "both",
        "mover_count": len(movers),
        "movers": movers[:limit],
        "updated_at": _ts(),
    }


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="TCG price-trend query engine")
    ap.add_argument("--current", type=str, default=None, help="item name/URL substring")
    ap.add_argument("--history", type=str, default=None, help="item name/URL substring")
    ap.add_argument("--movers", action="store_true")
    ap.add_argument("--direction", type=str, default=None, choices=["up", "down"])
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    obs = load_observations()
    if args.current:
        print(json.dumps(current_price(obs, args.current), ensure_ascii=False, indent=2))
    elif args.history:
        print(json.dumps(price_history(obs, args.history, limit=args.limit), ensure_ascii=False, indent=2))
    elif args.movers:
        print(json.dumps(top_movers(obs, direction=args.direction, limit=args.limit), ensure_ascii=False, indent=2))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
