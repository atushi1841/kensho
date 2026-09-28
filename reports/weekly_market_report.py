"""週次マーケットレポート生成スクリプト — t_1b2ecfa1

7市場CSVから自動集計し、Gumroad商品説明を更新する。
実行: python3 reports/weekly_market_report.py
"""

from __future__ import annotations

import csv
import glob
import json
import os
import statistics
import subprocess
import sys
import urllib.parse
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kensho"))
from core.encoding import guard_stdio

guard_stdio()

# .env読み込み
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

DATA_DIR = Path("/mnt/d/Project2/gumroad-automation/datasets")
GUMROAD_TOKEN = os.environ.get("GUMROAD_TOKEN", "")
PRODUCT_ID = "VoJxWx8UC0KN7lDRsOts7A=="
GUMROAD_API = "https://api.gumroad.com/v2"

# Apify Store クロスプロモーション用
APIFY_STORE_BASE = "https://apify.com/fruitful_quintessence"
APIFY_ACTOR_URLS = {
    "japan-used-camera-market-scraper": "https://apify.com/fruitful_quintessence/japan-used-camera-market-scraper",
    "japan-watch-market-scraper": "https://apify.com/fruitful_quintessence/japan-watch-market-scraper",
    "japan-luxury-brand-market-scraper": "https://apify.com/fruitful_quintessence/japan-luxury-brand-market-scraper",
    "japan-used-instrument-market-scraper": "https://apify.com/fruitful_quintessence/japan-used-instrument-market-scraper",
    "japan-offmall-market-scraper": "https://apify.com/fruitful_quintessence/japan-offmall-market-scraper",
    "surugaya-japan-hobby-prices": "https://apify.com/fruitful_quintessence/surugaya-japan-hobby-prices",
    "mandarake-auction-scraper": "https://apify.com/fruitful_quintessence/mandarake-auction-scraper",
    "tackleberry-japan-fishing-tackle-scraper": "https://apify.com/fruitful_quintessence/tackleberry-japan-fishing-tackle-scraper",
    "yahoo-auctions-japan-scraper": "https://apify.com/fruitful_quintessence/yahoo-auctions-japan-scraper",
    "dlsite-scraper": "https://apify.com/fruitful_quintessence/dlsite-scraper",
    "dmm-scraper": "https://apify.com/fruitful_quintessence/dmm-scraper",
    "kitamura-japan-used-camera-scraper": "https://apify.com/fruitful_quintessence/kitamura-japan-used-camera-scraper",
    "jackroad-used-watch-scraper": "https://apify.com/fruitful_quintessence/jackroad-used-watch-scraper",
    "komehyo-japan-brand-scraper": "https://apify.com/fruitful_quintessence/komehyo-japan-brand-scraper",
    "eurostat-indicators": "https://apify.com/fruitful_quintessence/eurostat-indicators",
    "world-bank-indicators": "https://apify.com/fruitful_quintessence/world-bank-indicators",
    "goo-net-car-scraper": "https://apify.com/fruitful_quintessence/goo-net-car-scraper",
    "biglemon-machinery-scraper": "https://apify.com/fruitful_quintessence/biglemon-machinery-scraper",
    "digimart-japan-used-instrument-scraper": "https://apify.com/fruitful_quintessence/digimart-japan-used-instrument-scraper",
    "golfpartner-used-club-scraper": "https://apify.com/fruitful_quintessence/golfpartner-used-club-scraper",
}

# 市場名 → Apify actor 実名マッピング（クロスプロモーション用）
MARKET_TO_ACTOR = {
    "iosys-japan-used-smartphone-scraper": "iosys-japan-used-smartphone-scraper",
    "jackroad-used-watch-scraper": "jackroad-used-watch-scraper",
    "japan-used-instrument-market-scraper": "japan-used-instrument-market-scraper",
    "kitamura-japan-used-camera-scraper": "kitamura-japan-used-camera-scraper",
    "komehyo-japan-brand-scraper": "komehyo-japan-brand-scraper",
    "mandarake-auction-scraper": "mandarake-auction-scraper",
    "tackleberry-japan-fishing-tackle-scraper": "tackleberry-japan-fishing-tackle-scraper",
}

MARKET_NAMES = {
    "iosys-japan-used-smartphone-scraper": "中古スマホ・タブレット（アイオシス）",
    "jackroad-used-watch-scraper": "中古腕時計（ジャンクロード）",
    "japan-used-instrument-market-scraper": "中古楽器（全国楽器市場）",
    "kitamura-japan-used-camera-scraper": "中古カメラ・レンズ（キタムラ）",
    "komehyo-japan-brand-scraper": "ブランド品（コメ兵）",
    "mandarake-auction-scraper": "ホビーオークション（まんだらけ）",
    "tackleberry-japan-fishing-tackle-scraper": "中古タックルベリー",
}

PRICE_COL = {
    "iosys-japan-used-smartphone-scraper": "price",
    "jackroad-used-watch-scraper": "price",
    "japan-used-instrument-market-scraper": "price",
    "kitamura-japan-used-camera-scraper": "price",
    "komehyo-japan-brand-scraper": "price",
    "mandarake-auction-scraper": "current_price_jpy",
    "tackleberry-japan-fishing-tackle-scraper": "price",
}


def parse_csv_files(pattern: str) -> list[dict]:
    """CSVファイル群を読み込み、価格を数値に変換して返す。"""
    rows = []
    for fpath in sorted(glob.glob(pattern)):
        with open(fpath, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(row)
    return rows


def extract_date(filepath: str) -> str:
    """ファイル名からYYYY-MM-DDを抽出。"""
    basename = os.path.basename(filepath)
    parts = basename.split("_")
    for p in parts:
        if len(p) == 8 and p.isdigit():
            return f"{p[:4]}-{p[4:6]}-{p[6:8]}"
    return "unknown"


def compute_market_stats(rows: list[dict], price_col: str) -> dict:
    """1市場の統計を計算。"""
    prices = []
    for r in rows:
        try:
            val = r.get(price_col, "").strip().replace(",", "")
            if val:
                prices.append(float(val))
        except (ValueError, TypeError):
            continue

    if not prices:
        return {"count": 0, "median": 0, "min": 0, "max": 0, "mean": 0}

    prices_sorted = sorted(prices)
    return {
        "count": len(prices),
        "median": statistics.median(prices_sorted),
        "min": min(prices_sorted),
        "max": max(prices_sorted),
        "mean": statistics.mean(prices_sorted),
    }


def generate_report() -> tuple[str, dict]:
    """全市場の週次レポートを生成。returns (markdown_text, per_market_stats)."""
    # 各市場の全ファイルを日付順に読み込み
    market_data: dict[str, list[tuple[str, list[dict]]]] = defaultdict(list)

    for csv_path in sorted(DATA_DIR.glob("*.csv")):
        basename = os.path.basename(csv_path)
        # 市場名を抽出（ファイル名の最初の部分）
        for prefix in MARKET_NAMES:
            if basename.startswith(prefix):
                date_str = extract_date(str(csv_path))
                rows = parse_csv_files(str(csv_path))
                market_data[prefix].append((date_str, rows))
                break

    # 各市場の最新2日付のデータで統計
    report_date = datetime.now(UTC).strftime("%Y-%m-%d")
    lines = [
        "# 日本ホビー・中古市場 マーケットレポート",
        "",
        f"生成日: {report_date}",
        "データ源: 各市場公開商品ページの週次スクレイピング",
        "",
        "## サマリ",
        "",
        "| 市場 | サンプル数 | 中央値 | 最安 | 最高 | 前回比(中央値) |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    stats_all: dict[str, dict] = {}

    for market_key in sorted(MARKET_NAMES.keys()):
        entries = market_data.get(market_key, [])
        if not entries:
            continue

        # 日付順にソート
        entries.sort(key=lambda x: x[0])

        # 最新と前週のデータを分離
        latest_date = entries[-1][0]
        prev_entries = entries[:-1] if len(entries) > 1 else entries

        price_col = PRICE_COL.get(market_key, "price")

        # 最新週の統計
        latest_rows = entries[-1][1]
        curr_stats = compute_market_stats(latest_rows, price_col)

        # 前週の統計
        prev_rows = prev_entries[-1][1] if prev_entries else latest_rows
        prev_stats = compute_market_stats(prev_rows, price_col)

        # 前回比
        if prev_stats["median"] > 0:
            pct_change = ((curr_stats["median"] - prev_stats["median"]) / prev_stats["median"]) * 100
            change_str = f"{pct_change:+.1f}%"
        else:
            change_str = "—"

        market_name = MARKET_NAMES[market_key]
        lines.append(
            f"| {market_name} | {curr_stats['count']} | "
            f"¥{curr_stats['median']:,.0f} | ¥{curr_stats['min']:,.0f} | "
            f"¥{curr_stats['max']:,.0f} | {change_str} |"
        )

        stats_all[market_key] = {
            "name": market_name,
            "latest_date": latest_date,
            "count": curr_stats["count"],
            "median": curr_stats["median"],
            "min": curr_stats["min"],
            "max": curr_stats["max"],
            "mean": curr_stats["mean"],
            "prev_median": prev_stats["median"],
            "change_pct": pct_change if prev_stats["median"] > 0 else None,
        }

    # Apify Store クロスプロモーションリンクを追加
    lines += [
        "",
        "## 関連データソース (Apify Store)",
        "各市場の詳細データは Apify Store の PPE (Pay-per-event) アクターで取得可能です。従量課金で無料枠から開始できます。",
        "",
    ]
    
    for market_key in sorted(MARKET_NAMES.keys()):
        if market_key in MARKET_TO_ACTOR:
            actor_name = MARKET_TO_ACTOR[market_key]
            actor_url = APIFY_ACTOR_URLS.get(actor_name, APIFY_STORE_BASE)
            market_name = MARKET_NAMES[market_key]
            lines.append(f"- [{market_name}]({actor_url}) — Apify Store で詳細データを取得")

    lines += [
        "",
        "---",
        "全アクター一覧: " + APIFY_STORE_BASE,
        "",
        "## 注記",
        "- 中央値は価格の中央値（外れ値影響を回避）",
        "- 前回比は前週の中央値との変化率",
        "- データはスクレイピング自動収集による近似値",
        "",
    ]

    markdown = "\n".join(lines)
    return markdown, stats_all


def update_gumroad_product(description: str) -> dict:
    """Gumroad商品の説明を更新。"""
    if not GUMROAD_TOKEN:
        return {"success": False, "error": "GUMROAD_TOKEN not set"}

    url = f"{GUMROAD_API}/products/{PRODUCT_ID}"
    encoded_desc = urllib.parse.quote(description, safe="")
    cmd = [
        "curl",
        "-s",
        "-m",
        "15",
        "-w",
        "\nHTTP %{http_code}",
        "-X",
        "PUT",
        url,
        "-H",
        f"Authorization: Bearer {GUMROAD_TOKEN}",
        "-d",
        f"description={encoded_desc}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    output = result.stdout.strip()

    # HTTPコードを抽出
    http_code = "000"
    if "HTTP " in output:
        http_code = output.split("HTTP ")[-1].split("\n")[0].strip()

    # JSON部分を抽出して解析
    json_part = output.split("HTTP ")[0].strip() if "HTTP " in output else output
    try:
        parsed = json.loads(json_part)
        return {"success": parsed.get("success", False), "http_code": http_code, "data": parsed}
    except json.JSONDecodeError:
        return {"success": False, "http_code": http_code, "error": json_part[:200]}


def main() -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] weekly_market_report start")

    # 1. レポート生成
    markdown, stats = generate_report()
    print(f"  Report generated: {len(stats)} markets")

    # 2. Gumroad更新
    if GUMROAD_TOKEN:
        result = update_gumroad_product(markdown)
        print(f"  Gumroad update: HTTP {result.get('http_code', '?')} success={result.get('success')}")
    else:
        result = {"success": False, "error": "GUMROAD_TOKEN not set"}
        print("  GUMROAD_TOKEN not set — skipping Gumroad update")

    # 3. レポートファイル保存
    report_dir = Path(__file__).parent
    report_file = report_dir / f"weekly_market_report_{datetime.now().strftime('%Y%m%d')}.md"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"  Report saved: {report_file}")

    # 4. ログ
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"weekly_market_report_{datetime.now().strftime('%Y%m%d')}.log"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"run_at={datetime.now().isoformat()}\n")
        f.write(f"markets={len(stats)}\n")
        f.write(f"gumroad_success={result.get('success')}\n")
        f.write(f"gumroad_http={result.get('http_code', 'N/A')}\n")
        for k, v in stats.items():
            f.write(f"  {k}: median=¥{v['median']:,.0f} count={v['count']} change={v.get('change_pct')}\n")
    print(f"  Log saved: {log_file}")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] weekly_market_report done")


if __name__ == "__main__":
    main()
