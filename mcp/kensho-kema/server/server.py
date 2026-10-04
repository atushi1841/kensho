#!/usr/bin/env python3
"""kensho-kema MCP server (MCPB bundle entry point).

Exposes the kensho Japan X/Twitter sweepstakes dataset from ke-ma.net (懸賞マニア) as
read-only MCP tools for AI agents.

Tools:
  - current_sweep(keyword) -> latest sweep matching keyword
  - sweep_history(keyword, limit=50) -> time series of matching sweeps
  - top_prize_movers(direction=None, limit=10) -> biggest prize value changes

Data source: bundled data/accumulated.jsonl (ke-ma.net observations, read-only).
No network, no API key required.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastmcp import FastMCP

DATA = Path(__file__).resolve().parent.parent / "data" / "accumulated.jsonl"

server = FastMCP("kensho-kema")


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


def _match(rows: list[dict[str, Any]], keyword: str) -> list[dict[str, Any]]:
    q = keyword.strip().lower()
    if not q:
        return rows
    out = []
    for r in rows:
        blob = " ".join([
            str(r.get("tweet_text", "")),
            str(r.get("prize_items", [])),
            str(r.get("x_url", "")),
            str(r.get("tweet_id", "")),
            str(r.get("source", "")),
            str(r.get("detail_url", "")),
            str(r.get("導線", "")),
        ]).lower()
        if q in blob:
            out.append(r)
    return out


@server.tool()
async def current_sweep(keyword: str) -> dict[str, Any]:
    """Latest sweep matching keyword in the kensho Japan sweepstakes dataset from ke-ma.net (懸賞マニア).

    Args:
        keyword: tweet text, prize, or URL substring (e.g. "PDRN", "MEDIHEal", "礼物").
    Returns the latest observed sweep snapshot plus match count.
    """
    rows = sorted(_match(_load(), keyword), key=lambda r: r.get("collected_at", r.get("deadline", "")))
    if not rows:
        return {"keyword": keyword, "matches": 0, "error": "no matching sweep in dataset"}
    latest = rows[-1]
    return {
        "keyword": keyword,
        "matches": len(rows),
        "tweet_id": latest.get("tweet_id"),
        "x_url": latest.get("x_url"),
        "tweet_text": latest.get("tweet_text"),
        "deadline": latest.get("deadline"),
        "winner_count": latest.get("winner_count"),
        "days_remaining": latest.get("days_remaining"),
        "prize_items": latest.get("prize_items"),
        "estimated_value_jpy": latest.get("estimated_value_jpy"),
        "priority": latest.get("priority"),
        "keyword_flag": latest.get("keyword_flag"),
        "source": latest.get("source"),
        "collected_at": latest.get("collected_at"),
        "detail_url": latest.get("detail_url"),
        "rd_url": latest.get("rd_url"),
        "applied": latest.get("applied"),
    }


@server.tool()
async def sweep_history(keyword: str, limit: int = 50) -> dict[str, Any]:
    """Time series of sweeps matching keyword in the kensho dataset from ke-ma.net (懸賞マニア).

    Args:
        keyword: tweet text, prize, or URL substring.
        limit: max number of history rows to return (default 50).
    Returns oldest-first observations of matching sweeps.
    """
    rows = sorted(_match(_load(), keyword), key=lambda r: r.get("collected_at", r.get("deadline", "")))
    if not rows:
        return {"keyword": keyword, "matches": 0, "error": "no matching sweep in dataset"}
    hist = [
        {
            "tweet_id": r.get("tweet_id"),
            "x_url": r.get("x_url"),
            "deadline": r.get("deadline"),
            "winner_count": r.get("winner_count"),
            "prize_items": r.get("prize_items"),
            "estimated_value_jpy": r.get("estimated_value_jpy"),
            "priority": r.get("priority"),
            "collected_at": r.get("collected_at"),
            "source": r.get("source"),
        }
        for r in rows[-limit:]
    ]
    return {"keyword": keyword, "matches": len(rows), "history": hist}


@server.tool()
async def top_prize_movers(direction: Optional[str] = None, limit: int = 10) -> dict[str, Any]:
    """Biggest prize value movers in the kensho sweepstakes dataset from ke-ma.net (懸賞マニア), ranked by |delta JPY|.

    Args:
        direction: None/"both" = up+down, "up" = value rose, "down" = value fell.
        limit: max movers to return (default 10).
    Note: ke-ma.net snapshots do not carry estimated_value_jpy, so this returns an empty
    list for the kema source (use sweep_history for tweet-level detail instead).
    """
    rows = _load()
    by_key: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = r.get("tweet_id") or r.get("x_url") or str(r)
        by_key.setdefault(key, []).append(r)

    movers = []
    for key, series in by_key.items():
        series = sorted(series, key=lambda r: r.get("collected_at", r.get("deadline", "")))
        if len(series) < 2:
            continue
        first = series[0].get("estimated_value_jpy")
        last = series[-1].get("estimated_value_jpy")
        if first is None or last is None:
            continue
        delta = last - first
        if direction == "up" and delta <= 0:
            continue
        if direction == "down" and delta >= 0:
            continue
        movers.append({
            "tweet_id": series[-1].get("tweet_id"),
            "x_url": series[-1].get("x_url"),
            "first_value_jpy": first,
            "last_value_jpy": last,
            "delta_jpy": delta,
            "pct": round(delta * 100.0 / first, 2) if first else None,
            "observations": len(series),
            "source": series[0].get("source"),
        })
    movers.sort(key=lambda m: abs(m["delta_jpy"]), reverse=True)
    return {"direction": direction, "count": len(movers), "movers": movers[:limit]}


if __name__ == "__main__":
    server.run(transport="stdio")