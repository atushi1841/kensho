#!/usr/bin/env python3
"""tcg-price-japan MCP server (MCPB bundle entry point).

Exposes the Japan TCG (Trading Card Game) used-price trend dataset collected
from suruga-ya.jp as read-only MCP tools for AI agents.

Tools:
  - tcg_current_price(item) -> latest used/new/list price snapshot (JPY)
  - tcg_price_history(item, limit=50) -> price time series
  - tcg_top_movers(direction=None, limit=10) -> biggest |delta| movers

Data source: bundled data/accumulated.jsonl (960 observations, read-only).
No network, no API key required.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastmcp import FastMCP

DATA = Path(__file__).resolve().parent.parent / "data" / "accumulated.jsonl"

server = FastMCP("tcg-price-japan")


def _load() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not DATA.exists():
        return rows
    with DATA.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _match(rows: list[dict[str, Any]], item: str) -> list[dict[str, Any]]:
    q = item.strip().lower()
    out = []
    for r in rows:
        blob = " ".join([
            str(r.get("name", "")),
            str(r.get("keyword", "")),
            str(r.get("url", "")),
        ]).lower()
        if q and q in blob:
            out.append(r)
    return out


@server.tool()
async def tcg_current_price(item: str) -> dict[str, Any]:
    """Current used/new/list price for a Pokemon/TCG item in the Japan (Suruga-ya) dataset.

    Args:
        item: item name or URL substring (e.g. "リザードン", "pokemon card").
    Returns the latest observed price snapshot (JPY) plus match count.
    """
    rows = sorted(_match(_load(), item), key=lambda r: r.get("collected_at", ""))
    if not rows:
        return {"item": item, "matches": 0, "error": "no matching item in dataset"}
    latest = rows[-1]
    return {
        "item": item,
        "matches": len(rows),
        "name": latest.get("name"),
        "url": latest.get("url"),
        "used_price_jpy": latest.get("used_price_jpy"),
        "new_price_jpy": latest.get("new_price_jpy"),
        "list_price_jpy": latest.get("list_price_jpy"),
        "collected_at": latest.get("collected_at"),
        "source": latest.get("source"),
    }


@server.tool()
async def tcg_price_history(item: str, limit: int = 50) -> dict[str, Any]:
    """Price time series (trend) for an item in the Japan TCG used-price dataset.

    Args:
        item: item name or URL substring.
        limit: max number of history rows to return (default 50).
    Returns oldest-first observations of used/new/list prices (JPY).
    """
    rows = sorted(_match(_load(), item), key=lambda r: r.get("collected_at", ""))
    if not rows:
        return {"item": item, "matches": 0, "error": "no matching item in dataset"}
    hist = [
        {
            "collected_at": r.get("collected_at"),
            "used_price_jpy": r.get("used_price_jpy"),
            "new_price_jpy": r.get("new_price_jpy"),
            "list_price_jpy": r.get("list_price_jpy"),
        }
        for r in rows[-limit:]
    ]
    return {"item": item, "matches": len(rows), "history": hist}


@server.tool()
async def tcg_top_movers(direction: Optional[str] = None, limit: int = 10) -> dict[str, Any]:
    """Biggest used-price movers in the Japan TCG dataset (ranked by |delta JPY|).

    Args:
        direction: None/"both" = up+down, "up" = price rose, "down" = price fell.
        limit: max movers to return (default 10).
    """
    rows = _load()
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = r.get("url") or r.get("name") or str(r)
        by_key.setdefault(key, []).append(r)

    movers = []
    for key, series in by_key.items():
        series = sorted(series, key=lambda r: r.get("collected_at", ""))
        if len(series) < 2:
            continue
        first = series[0].get("used_price_jpy")
        last = series[-1].get("used_price_jpy")
        if first is None or last is None:
            continue
        delta = last - first
        if direction == "up" and delta <= 0:
            continue
        if direction == "down" and delta >= 0:
            continue
        movers.append({
            "name": series[-1].get("name"),
            "url": key,
            "first_used_price_jpy": first,
            "last_used_price_jpy": last,
            "delta_jpy": delta,
            "pct": round(delta * 100.0 / first, 2) if first else None,
            "observations": len(series),
        })
    movers.sort(key=lambda m: abs(m["delta_jpy"]), reverse=True)
    return {"direction": direction, "count": len(movers), "movers": movers[:limit]}


if __name__ == "__main__":
    server.run(transport="stdio")
