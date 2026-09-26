#!/usr/bin/env python3
"""nongsan-mcp: FastMCP server for Japanese agricultural market price data.

Data sources:
- 農業物価統計調査 (e-Stat): monthly national average prices, ~1951-present
  - rice (うるち玄米, もち玄米), wheat, barley, beans, vegetables, fruits, etc.
- WAGRI 青果物市況API: daily fresh market prices (requires free registration)

Tools:
- nongsan_current_price(item) -> latest price + trend
- nongsan_price_history(item, limit=12) -> time series
- nongsan_top_movers(months=12, direction="both", limit=10) -> biggest changes
- nongsan_search_items(keyword) -> find item keys
- wagri_fresh_market(date, market_code=None, item_code=None) -> daily fresh prices (if auth available)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from fastmcp import FastMCP

# --- Configuration ---
DATA_FILE = Path(__file__).parent / "data" / "noubukka_data.json"
WAGRI_API_BASE = "https://api.wagri2.net/MaffOpenData/market/FreshMarketInformation"
WAGRI_AUTH_HEADER = os.environ.get("WAGRI_AUTH_KEY")  # Optional: set if registered
LOG_LEVEL = logging.INFO

# --- Logging ---
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nongsan_mcp")

# --- MCP Server ---
mcp = FastMCP("nongsan-mcp")

# --- Data Structures ---

@dataclass
class PriceSeries:
    """Time series for one agricultural item."""
    item_key: str
    category: str
    name: str
    detail: str
    grade: str
    unit: str
    observations: list[dict[str, Any]] = field(default_factory=list)  # [{"date": "YYYY-MM", "price": int}]

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_key": self.item_key,
            "category": self.category,
            "name": self.name,
            "detail": self.detail,
            "grade": self.grade,
            "unit": self.unit,
            "observations": self.observations,
            "latest_price": self.observations[-1]["price"] if self.observations else None,
            "latest_date": self.observations[-1]["date"] if self.observations else None,
        }

    def current_price(self) -> Optional[int]:
        return self.observations[-1]["price"] if self.observations else None

    def price_history(self, limit: int = 12) -> list[dict[str, Any]]:
        return self.observations[-limit:]

    def delta(self, months_back: int = 12) -> Optional[int]:
        if len(self.observations) < 2:
            return None
        if len(self.observations) <= months_back:
            first = self.observations[0]["price"]
        else:
            first = self.observations[-months_back - 1]["price"]
        last = self.observations[-1]["price"]
        return last - first

    def pct_change(self, months_back: int = 12) -> Optional[float]:
        if len(self.observations) < 2:
            return None
        if len(self.observations) <= months_back:
            first = self.observations[0]["price"]
        else:
            first = self.observations[-months_back - 1]["price"]
        last = self.observations[-1]["price"]
        if first == 0:
            return None
        return round((last - first) / first * 100, 1)


# --- Data Loading ---

_SERIES_CACHE: dict[str, PriceSeries] | None = None

def load_all_series() -> dict[str, PriceSeries]:
    """Load all price series from cached JSON. Build cache on first call."""
    global _SERIES_CACHE
    if _SERIES_CACHE is not None:
        return _SERIES_CACHE

    if not DATA_FILE.exists():
        logger.warning(f"Data file not found: {DATA_FILE}. Run build_data.py first.")
        _SERIES_CACHE = {}
        return _SERIES_CACHE

    with DATA_FILE.open(encoding="utf-8") as f:
        raw = json.load(f)

    series: dict[str, PriceSeries] = {}
    for item in raw:
        ps = PriceSeries(
            item_key=item["item_key"],
            category=item["category"],
            name=item["name"],
            detail=item.get("detail", ""),
            grade=item.get("grade", ""),
            unit=item.get("unit", ""),
            observations=item["observations"],
        )
        series[ps.item_key] = ps

    _SERIES_CACHE = series
    logger.info(f"Loaded {len(series)} price series from {DATA_FILE}")
    return series


def parse_date_label(label: str) -> Optional[str]:
    """Parse Japanese date labels like '令和７年１月' or '令和２年平均' into ISO format 'YYYY-MM' or 'YYYY'."""
    label = label.strip()
    if not label:
        return None

    # 年度平均
    if "平均" in label and "月" not in label:
        # e.g., '令和７年平均'
        import re
        m = re.search(r"(令和|平成|昭和)(\d+)年平均", label)
        if m:
            era, year = m.groups()
            y = _wareki_to_seireki(era, int(year))
            return f"{y}"
        return None

    # 月次: '令和７年１月', '        ２月', '令和８年１月（概数）'
    import re
    # Try to extract year and month
    year_match = re.search(r"(令和|平成|昭和)(\d+)年", label)
    month_match = re.search(r"(\d{1,2})月", label)

    if year_match:
        era, year = year_match.groups()
        y = _wareki_to_seireki(era, int(year))
    else:
        # Month-only row (continues previous year)
        return None

    if month_match:
        m = int(month_match.group(1))
        return f"{y}-{m:02d}"

    return None


def _wareki_to_seireki(era: str, year: int) -> int:
    """Convert Japanese era year to Gregorian year."""
    if era == "令和":
        return 2018 + year  # 令和1年 = 2019
    elif era == "平成":
        return 1988 + year  # 平成1年 = 1989
    elif era == "昭和":
        return 1925 + year  # 昭和1年 = 1926
    else:
        return 2000 + year


def build_data_from_excel(excel_path: str = "/tmp/noubukka.xlsx") -> list[dict[str, Any]]:
    """Parse the e-Stat Excel file and build structured JSON. Run once to create cache."""
    import openpyxl

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb['1(3)農産物_価格']

    # Build column headers
    headers = []
    last_p, last_n = None, None
    for c in range(3, ws.max_column + 1):
        p = ws.cell(row=5, column=c).value
        n = ws.cell(row=6, column=c).value
        d = ws.cell(row=7, column=c).value
        g = ws.cell(row=9, column=c).value
        u = ws.cell(row=10, column=c).value

        if p:
            last_p = p.replace('\n', '').strip()
        if n:
            last_n = n.replace('\n', '').strip()

        label = last_n
        if d:
            clean_d = d.replace('\n', '').strip()
            label += f'（{clean_d}）'

        headers.append({
            'col': c,
            'category': last_p,
            'name': last_n,
            'detail': d.replace('\n', '').strip() if d else '',
            'grade': g.replace('\n', '').strip() if g else '',
            'unit': u.replace('\n', '').strip() if u else '',
            'item_key': label.replace(' ', '').replace('（', '_').replace('）', '').replace('(', '_').replace(')', '_').replace('/', '_')
        })

    # Parse data rows
    series_dict: dict[str, PriceSeries] = {}
    for h in headers:
        key = h['item_key']
        series_dict[key] = PriceSeries(
            item_key=key,
            category=h['category'] or '',
            name=h['name'] or '',
            detail=h['detail'],
            grade=h['grade'],
            unit=h['unit'],
            observations=[],
        )

    for r in range(12, ws.max_row + 1):
        row_label = ws.cell(row=r, column=1).value
        if not row_label:
            continue

        date_iso = parse_date_label(str(row_label))
        if not date_iso:
            continue

        for h in headers:
            c = h['col']
            val = ws.cell(row=r, column=c).value
            if isinstance(val, (int, float)) and val != '…' and val is not None:
                series_dict[h['item_key']].observations.append({
                    "date": date_iso,
                    "price": int(val) if isinstance(val, float) and val == int(val) else int(val)
                })

    # Sort observations by date
    for s in series_dict.values():
        s.observations.sort(key=lambda x: x["date"])

    # Filter out series with no data
    result = [s.to_dict() for s in series_dict.values() if s.observations]

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open('w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"Built data: {len(result)} series saved to {DATA_FILE}")
    return result


# --- Tools ---

@mcp.tool()
async def nongsan_current_price(item: str) -> dict[str, Any]:
    """Current national average price for an agricultural item (MAFF e-Stat).

    Args:
        item: Item keyword (e.g., "うるち玄米", "トマト", "キャベツ", "米", "小麦", "大豆")
              Supports partial match on name/detail.

    Returns latest price (JPY per unit), unit, date, and 12-month trend.
    """
    series_dict = load_all_series()
    if not series_dict:
        # Try to build from excel if cache missing
        build_data_from_excel()
        series_dict = load_all_series()

    if not series_dict:
        return {"error": "No data available. Run build_data_from_excel() first."}

    item_lower = item.lower()
    matches = []
    for key, ps in series_dict.items():
        searchable = f"{ps.category} {ps.name} {ps.detail}".lower()
        if item_lower in searchable or item_lower in key.lower():
            matches.append(ps)

    if not matches:
        # Show available items for reference
        available = sorted(set(f"{ps.category}/{ps.name}" for ps in series_dict.values()))
        return {"error": f"Item '{item}' not found. Available categories: {available[:30]}..."}

    # Return best match (most observations)
    best = max(matches, key=lambda x: len(x.observations))
    data = best.to_dict()
    data["trend_12m"] = {
        "delta_jpy": best.delta(12),
        "pct_change": best.pct_change(12),
    }
    return data


@mcp.tool()
async def nongsan_price_history(item: str, limit: int = 24) -> dict[str, Any]:
    """Monthly price history (time series) for an agricultural item.

    Args:
        item: Item keyword (e.g., "うるち玄米", "トマト", "キャベツ")
        limit: Max number of monthly observations to return (default 24, max 120)

    Returns chronological observations with date and price.
    """
    series_dict = load_all_series()
    if not series_dict:
        build_data_from_excel()
        series_dict = load_all_series()

    if not series_dict:
        return {"error": "No data available."}

    item_lower = item.lower()
    matches = []
    for key, ps in series_dict.items():
        searchable = f"{ps.category} {ps.name} {ps.detail}".lower()
        if item_lower in searchable or item_lower in key.lower():
            matches.append(ps)

    if not matches:
        return {"error": f"Item '{item}' not found."}

    best = max(matches, key=lambda x: len(x.observations))
    history = best.price_history(min(limit, 120))
    return {
        "item_key": best.item_key,
        "category": best.category,
        "name": best.name,
        "detail": best.detail,
        "grade": best.grade,
        "unit": best.unit,
        "observations": history,
        "count": len(history),
    }


@mcp.tool()
async def nongsan_top_movers(months: int = 12, direction: str = "both", limit: int = 10) -> dict[str, Any]:
    """Biggest price movers over the specified period.

    Args:
        months: Lookback period in months (default 12, max 60)
        direction: "up" (price rose), "down" (price fell), "both" (default)
        limit: Max items to return (default 10)

    Returns ranked list with price change (JPY and %).
    """
    series_dict = load_all_series()
    if not series_dict:
        build_data_from_excel()
        series_dict = load_all_series()

    if not series_dict:
        return {"error": "No data available."}

    movers = []
    for ps in series_dict.values():
        if len(ps.observations) < 2:
            continue
        d = ps.delta(months)
        if d is None:
            continue
        pct = ps.pct_change(months)
        if pct is None:
            continue

        if direction == "up" and d <= 0:
            continue
        if direction == "down" and d >= 0:
            continue

        movers.append({
            "item_key": ps.item_key,
            "category": ps.category,
            "name": ps.name,
            "detail": ps.detail,
            "grade": ps.grade,
            "unit": ps.unit,
            "latest_price": ps.current_price(),
            "latest_date": ps.observations[-1]["date"] if ps.observations else None,
            "delta_jpy": d,
            "pct_change": pct,
            "direction": "up" if d > 0 else "down",
        })

    # Sort by absolute change
    movers.sort(key=lambda x: abs(x["delta_jpy"]), reverse=True)
    return {
        "period_months": months,
        "direction": direction,
        "movers": movers[:limit],
    }


@mcp.tool()
async def nongsan_search_items(keyword: str) -> dict[str, Any]:
    """Search available agricultural items by keyword.

    Args:
        keyword: Search term (e.g., "米", "野菜", "トマト", "玄米")

    Returns matching items with their keys for use in other tools.
    """
    series_dict = load_all_series()
    if not series_dict:
        build_data_from_excel()
        series_dict = load_all_series()

    if not series_dict:
        return {"error": "No data available."}

    keyword_lower = keyword.lower()
    results = []
    for ps in series_dict.values():
        searchable = f"{ps.category} {ps.name} {ps.detail}".lower()
        if keyword_lower in searchable:
            results.append({
                "item_key": ps.item_key,
                "category": ps.category,
                "name": ps.name,
                "detail": ps.detail,
                "grade": ps.grade,
                "unit": ps.unit,
                "latest_price": ps.current_price(),
                "latest_date": ps.observations[-1]["date"] if ps.observations else None,
                "obs_count": len(ps.observations),
            })

    results.sort(key=lambda x: (x["category"], x["name"]))
    return {"keyword": keyword, "matches": results, "count": len(results)}


@mcp.tool()
async def wagri_fresh_market(date: str, market_code: Optional[str] = None, item_code: Optional[str] = None) -> dict[str, Any]:
    """Fresh market daily prices from WAGRI API (青果物市況情報).

    Args:
        date: Target date in YYYY-MM-DD format (e.g., "2026-09-25")
        market_code: Optional market code filter (e.g., "13300" for 豊洲)
        item_code: Optional item code filter

    Requires WAGRI_API_KEY environment variable (free registration at wagri.naro.go.jp).
    Returns daily prices per market/item with volume, high/medium/low prices.
    """
    if not WAGRI_AUTH_HEADER:
        return {
            "error": "WAGRI_AUTH_KEY environment variable not set.",
            "help": "Register at https://wagri-subscription.db.naro.go.jp/ords/r/prd/subscription/pre-registration (free) and set WAGRI_AUTH_KEY=your_key"
        }

    url = f"{WAGRI_API_BASE}/GetByDays/{date}"
    headers = {"X-Authorization": WAGRI_AUTH_HEADER}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 401:
                return {"error": "WAGRI authentication failed. Check WAGRI_AUTH_KEY."}
            resp.raise_for_status()
            data = resp.json()

            # Filter by market/item if specified
            markets = data.get("Markets", [])
            if market_code:
                markets = [m for m in markets if m.get("MarketCode") == market_code]

            if item_code:
                for m in markets:
                    m["Items"] = [i for i in m.get("Items", []) if i.get("ItemCode") == item_code]

            return {
                "date": date,
                "market_count": len(markets),
                "markets": markets,
                "source": "WAGRI 青果物市況情報API (農水省オープンデータ)",
                "attribution": "データ出典：農林水産省 青果物市況情報 (政府標準利用規約2.0)"
            }
        except httpx.HTTPError as e:
            return {"error": f"WAGRI API error: {e}"}
        except Exception as e:
            return {"error": f"Request failed: {e}"}


# --- Build script entry point ---
if __name__ == "__main__":
    import sys
    if "--build" in sys.argv:
        build_data_from_excel()
    elif "--serve" in sys.argv:
        mcp.run(transport="stdio")
    elif "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        print("Usage:")
        print("  python nongsan_mcp.py --build     # Build data cache from Excel")
        print("  python nongsan_mcp.py --serve     # Run MCP stdio server")
        print("  python nongsan_mcp.py --http      # Run MCP HTTP server")