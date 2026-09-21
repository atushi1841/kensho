#!/usr/bin/env python3
"""
tcg-price-collect: Japanese TCG / Pokemon used-price data collection + dataset accumulation.

Reuses the local Suruga-ya (駿河屋) scraper (Japan IP) to collect used/new prices for
Pokemon TCG (and general TCG) items, then accumulates time-series snapshots into a
saleable dataset (price history preserved with collected_at timestamps).

TOS-aware: low-frequency runs, crawl-delay respected by the scraper, public listing pages only.

Usage:
  python scripts/tcg_price_collect.py                 # collect + merge (no git commit)
  python scripts/tcg_price_collect.py --commit        # collect + merge + git commit
  python scripts/tcg_price_collect.py --pages 2       # more pages per keyword
  python scripts/tcg_price_collect.py --keywords "A,B"
  python scripts/tcg_price_collect.py --build-only    # rebuild dataset from accumulated data (no network)
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

# --- Suruga-ya scraper (reused, local / Japan IP) ---
SURUGA_DIR = PROJECT_DIR.parent / "suruga-scraper"
SURUGA_SRC = SURUGA_DIR / "src"
sys.path.insert(0, str(SURUGA_SRC))
from scraper import scrape  # noqa: E402

# --- Config ---
OUT_DIR = PROJECT_DIR / "data" / "tcg_dataset"
ACCUMULATED = OUT_DIR / "accumulated.jsonl"
LATEST_CSV = OUT_DIR / "tcg_dataset_latest.csv"       # current snapshot (one row per item)
HISTORY_CSV = OUT_DIR / "tcg_price_history.csv"        # time series (one row per observation)
SNAPSHOT_JSON = OUT_DIR / "tcg_dataset.json"           # dataset metadata + summary
README_MD = OUT_DIR / "README.md"

# Curated Pokemon TCG / general TCG search keywords (低頻度収集). Order matters: surugaya
# fills up to maxItems per keyword sequentially, so put the highest-value searches first.
DEFAULT_KEYWORDS = [
    "ポケモンカードゲーム リザードン",
    "ポケモンカードゲーム ピカチュウ",
    "ポケモンカードゲーム ミュウツー",
    "ポケモンカードゲーム ポケモンカード151",
    "ポケモンカードゲーム イーブイ",
]

SOURCE = "suruga-ya.jp"
LICENSE = "CC-BY-SA-4.0 (data), see README.md for terms"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(kw: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", kw).strip("_")[:40] or "kw"


def collect_keyword(keyword: str, max_pages: int) -> list[dict]:
    """Run the surugaya scraper for one keyword; return normalized observation records."""
    t0 = time.time()
    print(f"[collect] keyword='{keyword}' pages={max_pages}")
    out_fname = f"_tcg_{_slug(keyword)}.json"
    path = scrape(keyword, max_pages=max_pages, in_stock_only=False, output=out_fname)
    elapsed = time.time() - t0
    if path is None or not Path(path).exists():
        print(f"[collect] no results for '{keyword}'")
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items", [])
    collected_at = _ts()
    # remove the temporary probe file
    try:
        Path(path).unlink()
    except OSError:
        pass
    records = []
    for it in items:
        name = it.get("name", "")
        url = it.get("url", "")
        if not name and not url:
            continue
        records.append({
            "source": SOURCE,
            "keyword": keyword,
            "name": name,
            "url": url,
            "used_price_jpy": it.get("used_price_jpy"),
            "new_price_jpy": it.get("new_price_jpy"),
            "list_price_jpy": it.get("list_price_jpy"),
            "marketplace_price_jpy": it.get("marketplace_price_jpy"),
            "brand": it.get("brand", ""),
            "release_date": it.get("release_date", ""),
            "category": it.get("category", ""),
            "condition_badge": it.get("condition_badge", ""),
            "in_stock": bool(it.get("in_stock", True)),
            "image_url": it.get("image_url", ""),
            "collected_at": collected_at,
        })
    print(f"[collect] '{keyword}' -> {len(records)} records in {elapsed:.1f}s")
    return records


def _item_key(rec: dict) -> str:
    return rec.get("url") or ("n:" + rec.get("name", ""))


def merge_dataset() -> dict:
    """Re-read accumulated.jsonl, merge into latest + history. Returns summary dict."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    obs: list[dict] = []
    if ACCUMULATED.exists():
        with ACCUMULATED.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        obs.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    latest: dict[str, dict] = {}
    history: list[dict] = []
    for rec in obs:
        k = _item_key(rec)
        # history: one row per observation (time series)
        history.append(rec)
        # latest: rembember most recent per item key
        if k not in latest or rec["collected_at"] >= latest[k]["collected_at"]:
            latest[k] = rec

    # write latest CSV (current snapshot)
    def _num(x):
        return x if x is not None else ""
    with LATEST_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "url", "used_price_jpy", "new_price_jpy", "list_price_jpy",
                    "marketplace_price_jpy", "brand", "keyword", "in_stock",
                    "condition_badge", "release_date", "collected_at"])
        for it in sorted(latest.values(), key=lambda r: (r.get("used_price_jpy") is not None, r["collected_at"]), reverse=True):
            w.writerow([it["name"], it.get("url", ""), _num(it.get("used_price_jpy")),
                        _num(it.get("new_price_jpy")), _num(it.get("list_price_jpy")),
                        _num(it.get("marketplace_price_jpy")), it.get("brand", ""),
                        it.get("keyword", ""), int(it.get("in_stock", 1)),
                        it.get("condition_badge", ""), it.get("release_date", ""),
                        it.get("collected_at", "")])

    # write history CSV (time series)
    with HISTORY_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "url", "used_price_jpy", "new_price_jpy", "list_price_jpy",
                    "keyword", "in_stock", "collected_at"])
        for it in sorted(history, key=lambda r: r["collected_at"]):
            w.writerow([it["name"], it.get("url", ""), _num(it.get("used_price_jpy")),
                        _num(it.get("new_price_jpy")), _num(it.get("list_price_jpy")),
                        it.get("keyword", ""), int(it.get("in_stock", 1)),
                        it.get("collected_at", "")])

    # compute price-change stats (used-price movers)
    used_movers = {}
    for rec in history:
        u = rec.get("used_price_jpy")
        if not u:
            continue
        k = _item_key(rec)
        if k not in used_movers:
            used_movers[k] = {"name": rec["name"], "first": u, "last": u, "obs": 1}
        else:
            used_movers[k]["last"] = u
            used_movers[k]["obs"] += 1

    priced = [m for m in used_movers.values() if m["first"] != m["last"]]
    price_changed = sorted(
        [{"name": m["name"], "first_price_jpy": m["first"], "last_price_jpy": m["last"],
          "delta_jpy": m["last"] - m["first"], "observations": m["obs"]} for m in priced],
        key=lambda x: abs(x["delta_jpy"]), reverse=True)

    summary = {
        "source": SOURCE,
        "total_observations": len(obs),
        "unique_items": len(latest),
        "with_used_price": sum(1 for r in latest.values() if r.get("used_price_jpy") is not None),
        "in_stock": sum(1 for r in latest.values() if r.get("in_stock")),
        "keywords": sorted({r.get("keyword", "") for r in obs}),
        "first_collected_at": min((r["collected_at"] for r in obs), default=""),
        "last_collected_at": max((r["collected_at"] for r in obs), default=""),
        "price_changed_items": len(price_changed),
        "used_price_movers": price_changed[:15],
        "latest_csv": str(LATEST_CSV),
        "history_csv": str(HISTORY_CSV),
    }
    with SNAPSHOT_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def write_dataset_readme(summary: dict) -> None:
    """Write a sales-friendly dataset README (schema, license, use cases)."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    latest = LATEST_CSV.name
    hist = HISTORY_CSV.name
    md = f"""# Japan TCG / Pokemon Card Used-Price Dataset (駿河屋)

Japanese-language secondary-market price data for trading card games (Pokemon TCG
中心), collected from Suruga-ya (駿河屋), Japan's largest second-hand hobby retailer.
Designed for overseas Pokemon/TCG investors and resellers who need a Japan-market
price reference.

## Files

| File | Contents |
|------|----------|
| {latest} | Current snapshot — latest observed price per item |
| {hist} | Time series — every price observation with `collected_at` |
| accumulated.jsonl | Append-only raw observations (JSONL) |

## Schema (CSV)

- `name` — item title (Japanese; brand/publisher in `brand`)
- `url` — canonical Suruga-ya product URL (dedupe key)
- `used_price_jpy` — current used price in JPY (primary reference price)
- `new_price_jpy` — new/sealed price in JPY when listed
- `list_price_jpy` — original list price (定価) when known
- `marketplace_price_jpy` — marketplace reseller price in JPY
- `brand` — publisher/brand when detected
- `keyword` — the search term that surfaced the item
- `in_stock` — 1/0 stock availability at collection time
- `condition_badge`, `release_date` — condition badge / release date when present
- `collected_at` — UTC timestamp of the observation (ISO 8601)

## Dataset stats (last build)

- Unique items:            {summary.get('unique_items', 0)}
- Total observations:      {summary.get('total_observations', 0)}
- Items with used price:   {summary.get('with_used_price', 0)}
- Items in stock:          {summary.get('in_stock', 0)}
- Keywords:                {', '.join(summary.get('keywords', []))}
- Collection window:       {summary.get('first_collected_at', '')} → {summary.get('last_collected_at', '')}
- Used-price movers seen:  {summary.get('price_changed_items', 0)}

## Use cases

- **Export / reseller arbitrage**: find Japanese retail prices below your overseas exit price
- **Price monitoring**: track a card's used-price trend over time (see history CSV)
- **Market research**: reference Japan-market demand for a set/card before buying
- **AI training data**: labelled {summary.get('unique_items', 0)}-row snapshot of JP secondary-market prices

## Data notes & license

- Source: public listing pages of suruga-ya.jp (Japan IP). Collected at low frequency with
  crawl-delay to stay within polite-use bounds. No official API exists.
- Prices are point-in-time observations captured at `collected_at`; they are indicative,
  not a live feed, and may differ from the current listing.
- **License: CC BY-SA 4.0.** Attribution required; share-alike applies. Commercial use allowed.
  This is independent data; not affiliated with or endorsed by Suruga-ya or the Pokemon Company.
- For the price-history timeline, data must be accumulated over successive runs — a single
  snapshot shows current prices only.
"""
    README_MD.write_text(md, encoding="utf-8")


def git_commit() -> None:
    import subprocess
    os.chdir(PROJECT_DIR)
    subprocess.run(["git", "add", str(OUT_DIR)], check=True)
    msg = f"tcg-price-collect: append dataset snapshot ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')})"
    subprocess.run(["git", "commit", "-m", msg], check=True)
    print(f"[commit] {msg}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--keywords", type=str, default=None)
    ap.add_argument("--build-only", action="store_true")
    args = ap.parse_args()

    if not args.build_only:
        kws = [k.strip() for k in args.keywords.split(",")] if args.keywords else DEFAULT_KEYWORDS
        kws = [k for k in kws if k]
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        for kw in kws:
            try:
                recs = collect_keyword(kw, max_pages=args.pages)
            except Exception as e:  # keep going on per-keyword failures
                print(f"[collect] ERROR keyword='{kw}': {e}")
                recs = []
            with ACCUMULATED.open("a", encoding="utf-8") as f:
                for r in recs:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = merge_dataset()
    write_dataset_readme(summary)
    print("\n=== Dataset summary ===")
    for k, v in summary.items():
        if not k.endswith("_csv") and k != "used_price_movers":
            print(f"  {k}: {v}")
    if summary.get("used_price_movers"):
        print("  Used-price movers:")
        for m in summary["used_price_movers"]:
            print(f"    ¥{m['first_price_jpy']:,} → ¥{m['last_price_jpy']:,} (Δ{m['delta_jpy']:+,}) | {m['name'][:50]}")

    if args.commit:
        git_commit()
    else:
        print("\n(commit skipped — rerun with --commit to persist to git)")


if __name__ == "__main__":
    main()
