#!/usr/bin/env python3
"""scripts/apify_store_promo.py — Apify Store PPEアクターのプロモーション自動投稿.

Apify Store の PPE 課金アクター 73 本が external_runs=0 / external_users=0
で実績収益 $0.0000 のまま。外部需要を喚起するため、X(atushi16) へ
CDP + SOCKS5 プロキシ分離でプロモ投稿を自動生成・投稿する。

設計:
  - 週次 dedup: data/apify_store_promo_state.json に ISO 週キー + スロットで
    投稿済み記録。cron 再実行でも冪等（同週同スロット2回目は安全スキップ）。
  - 対象抽出: data/apify_ppe_external_runs_state.json の last_trigger から
    24h 以上経過かつ external_runs=0 のアクターを優先選出。
  - 文言ローテーション: WEEKLY_TWEETS を週番号×スロットで選択（同一文言連投回避）。
  # 投稿経路: scripts/x_post_driver.js（Windows Chrome + CDP + node）を既定とする。
  #            KENSHO_PROMO_BROWSER 環境変数で切り替え（auto=win優先、firefox/cdpにフォールバック）。
  #            2026-10-03 実測で WSL から動くのは win 経路のみ（詳細は下部の経路切り替え節）。
  - 効果測定連携: 投稿 tweet_id を data/apify_store_promo_state.json に記録し、
    翌週の external_runs 変化で効果を追跡可能にする。

使い方:
  python scripts/apify_store_promo.py            # 週次投稿（同週同スロット済みならスキップ）
  python scripts/apify_store_promo.py --dry-run  # 投稿せず実行内容を表示
  python scripts/apify_store_promo.py --force    # 週次dedupを無視（検証用）
  python scripts/apify_store_promo.py --slot a   # スロット指定（a=月曜/b=金曜）

退出コード: 0=投稿/スキップ(正常)  2=dry-run  1=依存/投稿失敗
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import date, datetime, UTC, timedelta
from pathlib import Path
from typing import Any, Callable

REPO = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO / "scripts"
DATA_DIR = REPO / "data"
STATE_FILE = DATA_DIR / "apify_store_promo_state.json"
EXTERNAL_RUNS_STATE_FILE = DATA_DIR / "apify_ppe_external_runs_state.json"
PPE_PRICE_FILE = DATA_DIR / "tmp" / "pay_per_event.json"

# ──────────────────────────────────────────────────────────────
# 投稿経路切り替え（環境変数で制御）
#   KENSHO_PROMO_BROWSER=win     → Windows Chrome + CDP + node（既定・唯一WSLで動く経路）
#   KENSHO_PROMO_BROWSER=firefox → Playwright Firefox
#   KENSHO_PROMO_BROWSER=cdp     → SeleniumBase CDP Mode
#   未設定/auto                  → win → firefox → cdp の順に試す
#
# 2026-10-03 実測: WSL の Linux Chrome/chromedriver は SIGTRAP で起動できず
#   (uc_driver exited -5)、Playwright Firefox は X の入力欄を出せない。
#   Windows Chrome を CDP で操作する scripts/x_post_driver.js のみが投稿に成功した。
# ──────────────────────────────────────────────────────────────
PROMO_BROWSER: str = os.environ.get("KENSHO_PROMO_BROWSER", "auto").lower()

# アカウント設定
ACCOUNT_KEY = "atushi16"

# 週2投稿用スロット（月曜↔金曜で4日間隔・BOT検知回避）
SLOTS: tuple[str, ...] = ("a", "b")

# Apify Store ベース URL（プロフィールページ）
APIFY_STORE_BASE = "https://apify.com/fruitful_quintessence"

# Gumroad 商品（外部流入ルート — t_28467ede: X 投稿文言に埋め込む）
GUMROAD_PROMO_URL = "https://atushi5.gumroad.com/l/kutuxe"  # 無料サンプル 30行（導線入口）

# Apify Store アクター URL（PPE 課金アクターへの直接リンク）
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


def week_key(d: date) -> str:
    """ISO 週キー（例: 2026-W39）。週次 dedup の単位。"""
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _slot_index(week: int, slot: str) -> int:
    """週×スロットごとに独立した文言を割り当てる。"""
    return (week * len(SLOTS) + SLOTS.index(slot)) % len(WEEKLY_TWEETS)


def _load_json(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_ppe_prices() -> dict[str, float]:
    """pay_per_event.json の actors_ppe（実API名 → 単価）を読み込む。"""
    if not PPE_PRICE_FILE.exists():
        return {}
    try:
        with open(PPE_PRICE_FILE, encoding="utf-8") as f:
            return dict(json.load(f).get("actors_ppe") or {})
    except Exception:
        return {}


def load_external_runs_state() -> dict[str, Any]:
    """apify_ppe_external_runs_state.json を読み込む。"""
    return _load_json(EXTERNAL_RUNS_STATE_FILE)


def get_actor_display_info(actual_name: str) -> dict[str, str]:
    """アクター実名から表示用情報を返す。"""
    # アクター名 → 表示名/カテゴリ/ハッシュタグのマッピング
    mapping = {
        "japan-used-camera-market-scraper": {
            "display": "Japan Used Camera Prices",
            "category": "中古カメラ",
            "hashtags": "#中古カメラ #カメラ転売 #Kitamura #Fujiya #MapCamera",
        },
        "japan-watch-market-scraper": {
            "display": "Japan Used Watch Prices",
            "category": "中古時計",
            "hashtags": "#中古時計 #ロレックス #オメガ #Jackroad #Komehyo",
        },
        "japan-luxury-brand-market-scraper": {
            "display": "Japan Luxury Resale Prices",
            "category": "中古ブランド",
            "hashtags": "#中古ブランド #エルメス #シャネル #ルイヴィトン #Komehyo #BrandOff",
        },
        "japan-used-instrument-market-scraper": {
            "display": "Japan Used Instrument Prices",
            "category": "中古楽器",
            "hashtags": "#中古楽器 #ギター #ベース #シンセ #Digimart #Ishibashi",
        },
        "japan-offmall-market-scraper": {
            "display": "Japan Used Goods Prices",
            "category": "中古総合",
            "hashtags": "#ハードオフ #オフモール #中古カメラ #中古時計 #中古楽器",
        },
        "surugaya-japan-hobby-prices": {
            "display": "Surugaya Hobby Prices",
            "category": "ホビー",
            "hashtags": "#駿河屋 #ホビー #フィギュア #アニメグッズ",
        },
        "mandarake-auction-scraper": {
            "display": "Mandarake Auction Prices",
            "category": "オークション",
            "hashtags": "#まんだらけ #オークション #希少フィギュア",
        },
        "tackleberry-japan-fishing-tackle-scraper": {
            "display": "TackleBerry Fishing Tackle",
            "category": "釣具",
            "hashtags": "#タックルベリー #釣具 #リール #ロッド",
        },
        "yahoo-auctions-japan-scraper": {
            "display": "Yahoo Auctions Japan",
            "category": "オークション",
            "hashtags": "#ヤフオク #中古カメラ #中古時計 #中古楽器",
        },
        "dlsite-scraper": {
            "display": "DLsite Price Data",
            "category": "同人/ゲーム",
            "hashtags": "#DLsite #同人 #ゲーム #価格データ",
        },
        "dmm-scraper": {
            "display": "DMM Price Data",
            "category": "動画/ゲーム",
            "hashtags": "#DMM #動画 #ゲーム #価格データ",
        },
        "kitamura-japan-used-camera-scraper": {
            "display": "Kitamura Used Camera",
            "category": "中古カメラ",
            "hashtags": "#キタムラ #中古カメラ #カメラ転売",
        },
        "jackroad-used-watch-scraper": {
            "display": "Jackroad Used Watch",
            "category": "中古時計",
            "hashtags": "#ジャックロード #中古時計 #ロレックス",
        },
        "komehyo-japan-brand-scraper": {
            "display": "Komehyo Brand Prices",
            "category": "中古ブランド",
            "hashtags": "#コメ兵 #中古ブランド #バッグ #時計",
        },
        "eurostat-indicators": {
            "display": "Eurostat Indicators",
            "category": "統計データ",
            "hashtags": "#Eurostat #EU統計 #経済指標",
        },
        "world-bank-indicators": {
            "display": "World Bank Indicators",
            "category": "統計データ",
            "hashtags": "#WorldBank #世界銀行 #経済指標 #開発データ",
        },
        "goo-net-car-scraper": {
            "display": "Goo-net Car Prices",
            "category": "中古車",
            "hashtags": "#グーネット #中古車 #車価格",
        },
        "biglemon-machinery-scraper": {
            "display": "BigLemon Machinery",
            "category": "重機/建機",
            "hashtags": "#ビッグレモン #重機 #建設機械",
        },
        "digimart-japan-used-instrument-scraper": {
            "display": "Digimart Used Instruments",
            "category": "中古楽器",
            "hashtags": "#デジマート #中古楽器 #ギター #ベース",
        },
        "golfpartner-used-club-scraper": {
            "display": "GolfPartner Used Clubs",
            "category": "ゴルフ",
            "hashtags": "#ゴルフパートナー #中古ゴルフクラブ #ゴルフ",
        },
        "kensho-high-value-leads": {
            "display": "Kensho High Value Leads",
            "category": "リード獲得",
            "hashtags": "#リード獲得 #B2B #営業リスト",
        },
        "mandarake-auction-scraper": {
            "display": "Mandarake Auction",
            "category": "オークション",
            "hashtags": "#まんだらけ #オークション",
        },
        "mercari-japan-search-scraper": {
            "display": "Mercari Japan Search",
            "category": "メルカリ",
            "hashtags": "#メルカリ #転売 #せどり",
        },
        "japan-jepx-mcp": {
            "display": "JEPX Power Price MCP",
            "category": "電力",
            "hashtags": "#JEPX #電力取引 #スポット価格",
        },
    }
    return mapping.get(actual_name, {
        "display": actual_name,
        "category": "データ",
        "hashtags": "#データ #スクレイピング #Apify",
    })


# 週2投稿用ローテーション文言（16種 = 週×スロットで独立選択）。raw ≤280 字を維持。
# {actor_display}/{category}/{hashtags}/{store_url}/{actor_url}/{price_usd} は pick_text 時に置換される。
WEEKLY_TWEETS: list[str] = [
    "Apify Storeで {actor_display} 公開中。{category} 価格データをJSONで取得。\n"
    "PPE課金 ${price_usd}/件・無料枠あり。\n"
    "👉 {actor_url} {hashtags}\n"
    "📊 週次分析（無料サンプル）: {gumroad_url}",
    "{actor_display} — 日本の{category}価格を週次追跡。\n"
    "リセラー/アナリスト向けクリーンJSON・$0.005/件。\n"
    "Apify Storeで試す 👉 {actor_url} {hashtags}\n"
    "📊 無料サンプル: {gumroad_url}",
    "新着: {actor_display} が Apify Store に追加。\n"
    "{category}の実勢価格をAPIで取得。無料枠でお試し可。\n"
    "{hashtags} #ApifyStore\n"
    "📊 週次サンプル: {gumroad_url}",
    "日本{category}市場の価格インテリジェンス、週次CSVで配信。\n"
    "{actor_display} で競合価格・仕入れ判断を自動化。\n"
    "従量課金なら初期費用ゼロ。詳細👇 {actor_url} {hashtags}\n"
    "無料サンプル: {gumroad_url}",
    "リセラー必見: {actor_display} で日本{category}の実売価格を把握。\n"
    "店頭/EC/オークション横断の生データをJSONで。\n"
    "即実行可能・従量課金。{actor_url} {hashtags} #リセール #アービトラージ\n"
    "📊 無料サンプル: {gumroad_url}",
    "日本{category}市場の価格トレンドを今週も反映。\n"
    "{actor_display} でモデル/年式/コンディション別に精度アップ。\n"
    "外部ユーザー募集中 — 無料枠で試すだけ。{actor_url} {hashtags}\n"
    "📊 週次分析（無料サンプル）: {gumroad_url}",
    "クロスボーダー仕入れに {actor_display}。\n"
    "日本国内の{category}実勢価格をAPIで取得、為替・送料込みで利益計算。\n"
    "Pay-per-event $0.005。無料枠から開始 👉 {actor_url} {hashtags}\n"
    "無料サンプル: {gumroad_url}",
    "データ駆動型リセールの武器: {actor_display}。\n"
    "{category}の売れ筋・値上がり傾向・在庫回転を週次データで可視化。\n"
    "Apify Store ならインフラ不要・即日運用。{actor_url} {hashtags}\n"
    "📊 無料サンプル: {gumroad_url} #データ分析 #マーケットインテリジェンス",
    "Apify Store新着: {actor_display} で{category}価格を即API化。\n"
    "従量課金・無料枠あり。{actor_url} {hashtags}\n"
    "📊 週次サンプル: {gumroad_url}",
    "リセール分析の決定版: {actor_display}。\n"
    "{category}実売データをJSONで週次更新。PPE $0.005/件。\n"
    "無料で試す 👉 {actor_url} {hashtags}\n"
    "📊 無料サンプル: {gumroad_url} #リセール #アービトラージ",
    "日本{category}市場の価格モニタリング、今週も更新。\n"
    "{actor_display} で仕入れ判断・在庫評価を自動化。\n"
    "初期費用ゼロで開始 {actor_url} {hashtags}\n"
    "📊 週次分析（無料サンプル）: {gumroad_url}",
    "クロスボーダー向け {actor_display} 最新版。\n"
    "日本{category}実勢価格・為替・送料込みで利益試算。\n"
    "PPE課金 $0.005、無料枠から {actor_url} {hashtags}\n"
    "無料サンプル: {gumroad_url}",
    "データ駆動リセールに {actor_display}。\n"
    "{category}売れ筋・トレンド・回転率を週次可視化。\n"
    "インフラ不要・即日 {actor_url} {hashtags}\n"
    "📊 無料サンプル: {gumroad_url} #データ分析 #マーケットインテリジェンス",
    "Apify PPEアクター {actor_display} で{category}価格取得。\n"
    "従量課金・無料枠あり。{actor_url} {hashtags}\n"
    "📊 週次サンプル: {gumroad_url} #ApifyStore #データセット",
]


def pick_actors_for_promo(
    today: date,
    max_actors: int = 3,
) -> list[dict[str, Any]]:
    """プロモ対象アクターを選出する。

    優先順位:
    1. external_runs=0 のアクター
    2. 24h以上起動間隔が空いているアクター
    3. 価格が高い（収益インパクト大）アクター
    """
    external_state = load_external_runs_state()
    last_trigger = external_state.get("last_trigger", {})
    prices = load_ppe_prices()

    now = datetime.now(UTC)
    candidates: list[dict[str, Any]] = []

    for actor_id, last_ts_str in last_trigger.items():
        try:
            last_ts = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
        except ValueError:
            last_ts = now - timedelta(hours=48)  # 古い扱い

        hours_since = (now - last_ts).total_seconds() / 3600
        if hours_since < 24:
            continue  # 24h経過していないものはスキップ

        # 実名を特定（PRIORITY_ACTORSから逆引き）
        actual_name = None
        for actor_info in PRIORITY_ACTORS:
            if actor_info["fallback_id"] == actor_id:
                actual_name = actor_info["actual_name"]
                break
        if not actual_name:
            continue

        price = prices.get(actual_name, 0.0)
        display_info = get_actor_display_info(actual_name)

        candidates.append({
            "actor_id": actor_id,
            "actual_name": actual_name,
            "price_usd": price,
            "hours_since_last_trigger": hours_since,
            "display": display_info["display"],
            "category": display_info["category"],
            "hashtags": display_info["hashtags"],
        })

    # ソート: 価格降順 → 経過時間降順
    candidates.sort(key=lambda x: (-x["price_usd"], -x["hours_since_last_trigger"]))

    return candidates[:max_actors]


# PRIORITY_ACTORS は apify_ppe_external_runner.py からコピー（同期必須）
PRIORITY_ACTORS: list[dict[str, Any]] = [
    {"actual_name": "japan-used-camera-market-scraper", "fallback_id": "mQaZFo6up4YZKepC3", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-watch-market-scraper", "fallback_id": "gMqdrS2evpcybSZc2", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-luxury-brand-market-scraper", "fallback_id": "b0vuqa3ESvy2mOwFB", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-used-instrument-market-scraper", "fallback_id": "yN1R26HrV6C2MBKas", "priority": 1, "price_usd": 0.005},
    {"actual_name": "japan-offmall-market-scraper", "fallback_id": "Zh4kqcS4dYPWpFzBd", "priority": 1, "price_usd": 0.005},
    {"actual_name": "surugaya-japan-hobby-prices", "fallback_id": "F8Hl0a8Cx9bpJBrxR", "priority": 2, "price_usd": 0.005},
    {"actual_name": "mandarake-auction-scraper", "fallback_id": "q2E37PVTg5JcGOTEn", "priority": 2, "price_usd": 0.005},
    {"actual_name": "tackleberry-japan-fishing-tackle-scraper", "fallback_id": "wxMskoiHMPeeH2qAJ", "priority": 2, "price_usd": 0.005},
    {"actual_name": "yahoo-auctions-japan-scraper", "fallback_id": "8WBam4CPB72q9Rvsd", "priority": 2, "price_usd": 0.005},
    {"actual_name": "dlsite-scraper", "fallback_id": "6Z7tJ3plfUmAgGmbk", "priority": 3, "price_usd": 0.005},
    {"actual_name": "dmm-scraper", "fallback_id": "nUm22B2guMo8vXom6", "priority": 3, "price_usd": 0.002},
    {"actual_name": "kitamura-japan-used-camera-scraper", "fallback_id": "DOiD9y1NAJfLBcAjT", "priority": 3, "price_usd": 0.005},
    {"actual_name": "jackroad-used-watch-scraper", "fallback_id": "nWf9BR2ndMTYqKxNB", "priority": 3, "price_usd": 0.005},
    {"actual_name": "komehyo-japan-brand-scraper", "fallback_id": "Db3iY8FIRxPjPag7N", "priority": 3, "price_usd": 0.005},
    {"actual_name": "eurostat-indicators", "fallback_id": "pAxQ0lRyArudhK9Wx", "priority": 4, "price_usd": 0.004},
    {"actual_name": "world-bank-indicators", "fallback_id": "u2qsG1UfVHWsgl8Dg", "priority": 4, "price_usd": 0.003},
    {"actual_name": "goo-net-car-scraper", "fallback_id": "bgm5Gxn4BeBmoO7xD", "priority": 5, "price_usd": 0.002},
    {"actual_name": "biglemon-machinery-scraper", "fallback_id": "W9cXhDckzHd9RZWnQ", "priority": 5, "price_usd": 0.002},
    {"actual_name": "digimart-japan-used-instrument-scraper", "fallback_id": "FSuoQiX8OG4KuIQ9c", "priority": 5, "price_usd": 0.002},
    {"actual_name": "golfpartner-used-club-scraper", "fallback_id": "xPSQSSsdVjRwWQAiA", "priority": 5, "price_usd": 0.002},
]


# X 投稿上限（CJK 1文字 = 2 文字カウント。X の現行 API に準拠）。
# 英数字/記号は 1、CJK 範囲 (\u2E80-\u9FFF と広範囲の漢字) は 2 としてカウントする。
X_CHAR_LIMIT = 280


def x_text_len(text: str) -> int:
    """X の文字数上限判定用に CJK 文字を 2 文字としてカウントする。"""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def trim_to_x_limit(text: str, limit: int = X_CHAR_LIMIT) -> str:
    """X 投稿上限（デフォルト 280 文字、CJK 換算）に収める。

    末尾の「他: ...」から優先的に短くし、 Still over の場合は本文末尾を
    文切りの good break（句点/読点/空白）で truncation し、'…' を付与する。
    """
    if x_text_len(text) <= limit:
        return text

    # ステップ1: 「他: ...」部分を削除（先頭の 1 つだけ残す）
    head, sep, tail = text.partition(" 他: ")
    if sep:
        text = head
        if x_text_len(text) <= limit:
            return text

    # ステップ2: 末尾の good break で truncation
    budget = limit - 1  # '…' 分を予約
    out = ""
    cur = 0
    for ch in text:
        w = 2 if ord(ch) > 0x2E80 else 1
        if cur + w > budget:
            break
        out += ch
        cur += w

    # 直前の good break（句点/読点/空白/改行）なら区切りよく切る
    for cut in ("。", "、", " ", "\n"):
        idx = out.rfind(cut)
        if idx > len(out) * 0.5:  # 後半の cut のみ有効
            out = out[:idx]
            break

    return out.rstrip() + "…"


def pick_text(
    today: date,
    state: dict[str, Any],
    actors: list[dict[str, Any]],
    slot: str = "a",
    force: bool = False,
) -> tuple[str | None, str, dict[str, Any]]:
    """今日の文言を選ぶ。同週・同スロット投稿済みなら (None, reason, {})。"""
    key = week_key(today)
    posted = state.get("posted_weeks", {}).get(key, {})
    # 旧形式互換
    if slot not in posted and "tweet_id" in posted:
        posted = {"a": posted}
    if not force and slot in posted:
        prev = posted[slot] or {}
        tid = str(prev.get("tweet_id") or "")
        # 2026-10-03 修正: placeholder/unknown_* の偽IDを「投稿済み」と誤認していた。
        # 実際には投稿されていないのに以降の週次実行が全部スキップされ、
        # 外部導線が無言で死んでいた（state に Test placeholder が入っていた）。
        # 実ID（数字のみ）以外は未投稿として扱い、投稿を続行する。
        if tid.isdigit():
            return None, f"今週{slot}スロットは投稿済み (week={key}, tweet_id={tid})", {}
        if tid:
            print(f"[warn] 偽の投稿記録を無視します (week={key}, slot={slot}, tweet_id={tid!r})")

    iso = today.isocalendar()
    idx = _slot_index(iso.week, slot)
    raw = WEEKLY_TWEETS[idx]

    # 対象アクター情報を文言に埋め込む（最初のアクターを代表として使用、他は言及）
    primary = actors[0] if actors else {}
    actor_display = primary.get("display", "Apify Actor")
    category = primary.get("category", "データ")
    hashtags = primary.get("hashtags", "#Apify #データセット")
    price_usd = primary.get("price_usd", 0.005)
    actual_name = primary.get("actual_name", "")
    actor_url = APIFY_ACTOR_URLS.get(actual_name, APIFY_STORE_BASE)

    # 他アクターも言及（最大3件まで）。上限オーバー時に優先的にカット対象。
    other_names = [a["display"] for a in actors[1:3]] if len(actors) > 1 else []
    other_mention = f" 他: {', '.join(other_names)}" if other_names else ""

    text = raw.format(
        actor_display=actor_display,
        category=category,
        hashtags=hashtags,
        store_url=APIFY_STORE_BASE,
        actor_url=actor_url,
        price_usd=f"{price_usd:.3f}",
        gumroad_url=GUMROAD_PROMO_URL,
    ) + other_mention

    # X 文字数上限（CJK 換算 280）を遵守
    text = trim_to_x_limit(text)

    return text, "", {"primary_actor": primary, "all_actors": actors, "slot": slot, "week_key": key}


def log(msg: str, repo: Path) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    log_dir = repo / "logs"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "apify_store_promo.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def post_with_cdp(account_key: str, text: str, log_fn: Callable[[str], None]) -> str:
    """KenshoCDP (SeleniumBase CDP Mode + SOCKS5) でツイート投稿。

    戻り値: tweet_id (rest_id)
    """
    # 動的import（import時の副作用回避）
    sys.path.insert(0, str(REPO))
    from kensho.application.selenium_cdp import KenshoCDP

    log_fn(f"CDP起動: account={account_key}")

    with KenshoCDP(account_key=account_key, headless=True) as driver:
        # driver._sb は context manager 内では必ず非 None
        sb = driver._sb
        assert sb is not None

        # X.com にアクセス
        sb.open("https://x.com/compose/tweet")
        time.sleep(random.uniform(3, 6))

        # ツイート入力エリアを特定して入力
        # SeleniumBase CDP mode での要素特定
        tweet_box_selector = '[data-testid="tweetTextarea_0"]'
        try:
            sb.wait_for_element(tweet_box_selector, timeout=15)
        except Exception:
            # フォールバック: より汎用的なセレクタ
            tweet_box_selector = 'div[role="textbox"][data-testid="tweetTextarea_0"]'
            sb.wait_for_element(tweet_box_selector, timeout=10)

        # 人間らしいタイピング
        driver.human_type(tweet_box_selector, text)

        # 投稿ボタンをクリック
        post_button_selector = '[data-testid="tweetButtonInline"]'
        driver.human_click(post_button_selector)

        # 投稿完了待機 & tweet_id 取得
    #
    # X の SPA は投稿後、compose URL から /status/<id> へリダイレクトするが
    # ブラウザ状態によってはリダイレクト前に「投稿中」トーストが表示されるため、
    # URL に /status/ が現れるまでポーリング待機する（v2: fallback強化）。
    tweet_id = _wait_for_tweet_id(sb, account_key, text, log_fn)

    log_fn(f"[OK] 投稿成功 tweet_id={tweet_id}")
    return tweet_id


def _extract_status_id(url: str) -> str | None:
    """URL から tweet status id を抽出（クエリ/経路以降を切り捨て）。"""
    if not url or "/status/" not in url:
        return None
    try:
        return url.split("/status/")[1].split("?")[0].split("/")[0]
    except Exception:
        return None


def _wait_for_tweet_id(
    sb: Any,
    account_key: str,
    text: str,
    log_fn: Callable[[str], None],
    url_timeout: int = 30,
) -> str:
    """投稿後の tweet_id 取得（多重フォールバック）。

    戻り値は real tweet_id（15桁以上・数字のみ）。取得失敗時は例外をraiseし、
    unknown_* ダミーは一切返さない（偽記録防止: success criteria "excluding
    placeholder/unknown_*" を worker 判定で確実に外すため）。
    """
    deadline = time.time() + url_timeout
    current_url = sb.get_current_url()
    log_fn(f"投稿後URL(初期): {current_url}")

    # フェーズ1: 投稿直後の URL リダイレクト待機
    while time.time() < deadline:
        tid = _extract_status_id(sb.get_current_url())
        if tid and tid.isdigit() and len(tid) >= 15:
            log_fn(f"URLからtweet_id取得: {tid}")
            return tid
        time.sleep(random.uniform(1.0, 2.0))

    # フェーズ2: プロフィールの最新ツイートから取得（テキスト照合付き）
    #   X の SPA がリダイレクトしない場合、投稿直後のプロフィール 1 行目が
    #   当該ツイートになるため、内容照合で誤認を防ぐ。
    try:
        sb.open(f"https://x.com/{account_key}")
        time.sleep(random.uniform(2.0, 4.0))
        result = sb.execute_script(
            "() => {"
            "  const art = document.querySelector('article[data-testid=\"tweet\"]');"
            "  if (!art) return null;"
            "  const link = art.querySelector('a[href*=\"/status/\"]');"
            "  const txt = art.querySelector('[data-testid=\"tweetText\"]');"
            "  return {href: link ? link.getAttribute('href') : null,"
            "          text: txt ? txt.innerText : null};"
            "}"
        )
        if isinstance(result, dict):
            href = result.get("href")
            scraped = (result.get("text") or "").strip()
            log_fn(f"プロフィール最新ツイート: href={href} text={scraped[:60]!r}")
            tid = _extract_status_id(href or "")
            # テキスト照合: 投稿文の先頭60字が一致します
            if tid and scraped and text.strip()[:60] in scraped:
                log_fn(f"テキスト照合OK、tweet_id取得: {tid}")
                return tid
            elif tid:
                log_fn(f"WARN: tweet_id候选ありだがテキスト不一致: {tid}")
    except Exception as e:
        log_fn(f"プロフィールからの取得で例外: {type(e).__name__}: {e}")

    # フェーズ3: 再ポーリング（リダイレクトが遅い場合の最終手段）
    while time.time() < deadline:
        tid = _extract_status_id(sb.get_current_url())
        if tid and tid.isdigit() and len(tid) >= 15:
            log_fn(f"再ポーリングでtweet_id取得: {tid}")
            return tid
        time.sleep(random.uniform(1.5, 3.0))

    raise RuntimeError(
        "tweet_id取得失敗（URL/プロフィール/再ポーリングの全フォールバック失敗）。"
        "実際の投稿は完了している可能性があるため、状態記録は行わず例外をraiseする。"
    )


def post_with_playwright(account_key: str, text: str, log_fn: Callable[[str], None]) -> str:
    """Playwright Firefox でツイート投稿（kensho.application.browser 経路）。

    戻り値: tweet_id (rest_id)

    ★ プロキシ自動無効化:
      PROXY_MAP の SOCKS5 (172.26.80.1:108x) は実環境で timeout しており、
      プロモ投稿は1垢1週1投稿と負荷が低いため IP 分離不要。
      プロキシ到達性を自動検証し、接続不可なら USE_PROXY=0 で実行する。
    """
    log_fn(f"Playwright起動: account={account_key}")

    # 型import（循環回避のため遅延import）
    sys.path.insert(0, str(REPO))

    # ── プロキシ到達性自動検証 ──
    import socket
    proxy_reachable = False
    try:
        s = socket.socket()
        s.settimeout(3)
        s.connect(("172.26.80.1", 1081))
        s.close()
        proxy_reachable = True
    except Exception:
        pass
    if not proxy_reachable:
        log_fn("WARN: SOCKS5プロキシ(172.26.80.1:1081) に接続不可 → USE_PROXY=0 で実行")
        os.environ["USE_PROXY"] = "0"

    from kensho.application.browser import create_browser, close_browser

    pw, browser, ctx, page = create_browser(
        account_key=account_key, headless=True,
        proxy=None,  # プロキシ自動検証済み（接続不可なら USE_PROXY=0 設定済み）
    )

    try:
        # X.com にアクセス
        page.goto("https://x.com/compose/tweet", timeout=60000, wait_until="domcontentloaded")
        time.sleep(random.uniform(3, 6))

        # ツイート入力エリアを特定して入力（実測セレクタ: tweetTextarea_0 / tweetButton）
        # 注: tweetTextarea_0 が2要素マッチするため .first で絞る
        tweet_box_selector = '[data-testid="tweetTextarea_0"]'
        page.wait_for_selector(tweet_box_selector, timeout=15000)

        # 人間らしいタイピング
        element = page.locator(tweet_box_selector).first
        element.click()
        time.sleep(random.uniform(0.5, 1.5))

        for char in text:
            element.type(char, delay=random.uniform(80, 250))
            if random.random() < 0.08:
                time.sleep(random.uniform(0.3, 0.8))

        time.sleep(random.uniform(3, 6))

        # 投稿ボタンをクリック（実測セレクタ: [data-testid="tweetButton"]）
        post_button_selector = '[data-testid="tweetButton"]'
        page.locator(post_button_selector).first.click()

        # 投稿完了待機
        time.sleep(random.uniform(3, 5))

        # tweet_id 取得
        current_url = page.url
        log_fn(f"投稿後URL: {current_url}")

        tweet_id = None
        if "/status/" in current_url:
            try:
                tweet_id = current_url.split("/status/")[1].split("?")[0].split("/")[0]
            except Exception:
                pass

        # フォールバック: プロフィールから最新ツイートを取得
        if not tweet_id:
            page.goto(f"https://x.com/{account_key}", timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))
            latest_link = page.locator('article[data-testid="tweet"] a[href*="/status/"]').first
            href = latest_link.get_attribute("href")
            if href and "/status/" in href:
                tweet_id = href.split("/status/")[1].split("?")[0].split("/")[0]

        if not tweet_id:
            # ダミー不可（success criteria: excluding placeholder/unknown_*）
            raise RuntimeError("tweet_id取得失敗（URL/プロフィール双方で取得不可）")

        log_fn(f"[OK] 投稿成功 tweet_id={tweet_id}")
        return tweet_id
    finally:
        close_browser(pw, browser, log=None, label="promo_firefox")


WIN_TEMP = Path("/mnt/c/temp")
X_DRIVER_JS = REPO / "scripts" / "x_post_driver.js"


def post_with_windows_cdp(account_key: str, text: str, log_fn: Callable[[str], None]) -> str:
    """Windows の実 Chrome を CDP で操作して投稿する（2026-10-03 実測で唯一通る経路）。

    WSL の Linux Chrome/chromedriver は SIGTRAP で起動できず（uc_driver exited -5）、
    Playwright Firefox は X の入力欄を出せない。Windows Chrome + CDP + node だけが動く。
    戻り値は実ツイートID（数字のみ）。取れない場合は例外（偽の成功を返さない）。
    """
    import shutil
    import subprocess

    if not X_DRIVER_JS.exists():
        raise RuntimeError(f"driver が見つからない: {X_DRIVER_JS}")
    (WIN_TEMP / "x_body.txt").write_text(text, encoding="utf-8")
    shutil.copyfile(X_DRIVER_JS, WIN_TEMP / "x_post_driver.js")
    out_json = WIN_TEMP / "x_post_out.json"
    if out_json.exists():
        out_json.unlink()

    log_fn("Windows Chrome + CDP 経路で投稿します")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "cd C:\\temp; node x_post_driver.js x_body.txt C:\\temp\\x_post_out.json"],
            capture_output=True, text=True, timeout=420,
        )
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-3:]
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"windows-cdp タイムアウト: {e}") from e

    if not out_json.exists():
        raise RuntimeError(f"driver が結果を書かなかった: {tail}")
    res = json.loads(out_json.read_text(encoding="utf-8"))
    tweet_id = str(res.get("tweet_id") or "")
    if not tweet_id.isdigit():
        raise RuntimeError(f"実IDが取れなかった (status={res.get('status')}, log={tail})")
    log_fn(f"投稿成功: tweet_id={tweet_id} permalink={res.get('permalink')}")
    return tweet_id


def post_promo(account_key: str, text: str, log_fn: Callable[[str], None]) -> str:
    """環境変数 KENSHO_PROMO_BROWSER に従って投稿経路を選択。

    - win:  Windows Chrome + CDP + node（既定・唯一の動作経路）
    - firefox: Playwright Firefox
    - cdp:     SeleniumBase CDP Mode
    - auto:  win → firefox → cdp の順に試す

    2026-10-03 変更: 既定を win にした。firefox は X の入力欄を出せず、
    seleniumbase は WSL で uc_driver が SIGTRAP(-5) で即死するため、
    この2つを先に試すのは無駄な試行（＝BOTシグナルを増やす）でしかない。
    """
    mode = PROMO_BROWSER
    if mode in ("win", "windows", "cdp-win"):
        return post_with_windows_cdp(account_key, text, log_fn)
    if mode == "firefox":
        return post_with_playwright(account_key, text, log_fn)
    if mode == "cdp":
        return post_with_cdp(account_key, text, log_fn)
    # auto: 動く経路を先に
    try:
        return post_with_windows_cdp(account_key, text, log_fn)
    except Exception as e:
        log_fn(f"windows-cdp 経路失敗: {e}; firefox にフォールバック")
    try:
        return post_with_playwright(account_key, text, log_fn)
    except Exception as e:
        log_fn(f"firefox 経路失敗: {e}; seleniumbase にフォールバック")
        return post_with_cdp(account_key, text, log_fn)


def main() -> None:
    ap = argparse.ArgumentParser(description="Apify Store PPEアクター プロモーション週次自動投稿")
    ap.add_argument("--dry-run", action="store_true", help="投稿せず実行内容を表示")
    ap.add_argument("--force", action="store_true", help="週次dedupを無視")
    ap.add_argument("--slot", default="a", choices=["a", "b"], help="投稿スロット（a=月曜/b=金曜）")
    ap.add_argument("--state", default=str(STATE_FILE), help="週次stateパス")
    ap.add_argument("--date", default="", help="基準日 YYYY-MM-DD（省略=今日）")
    ap.add_argument("--max-actors", type=int, default=3, help="1投稿あたりの最大紹介アクター数")
    args = ap.parse_args()

    state_file = Path(args.state)
    today = date.fromisoformat(args.date) if args.date else date.today()

    state = _load_json(state_file)
    actors = pick_actors_for_promo(today, max_actors=args.max_actors)

    if not actors:
        log(f"対象アクターなし（全て24h以内に起動済み）", REPO)
        sys.exit(0)

    text, reason, meta = pick_text(today, state, actors, slot=args.slot, force=args.force)
    if text is None:
        log(f"スキップ: {reason}", REPO)
        sys.exit(0)

    key = week_key(today)
    log(f"対象週: {key} / slot={args.slot} / {ACCOUNT_KEY} / Apify Store PPEプロモ", REPO)
    log(f"紹介アクター: {', '.join(a['display'] for a in actors)}", REPO)
    log(f"ツイート内容: {text!r}", REPO)
    if len(text) > 280:
        log(f"WARN: 文字数 {len(text)}/280 超過", REPO)

    if args.dry_run:
        log("DRY-RUN: 投稿は実行していません。", REPO)
        sys.exit(2)

    # 投稿実行（KENSHO_PROMO_BROWSER で経路切り替え）
    try:
        tweet_id = post_promo(ACCOUNT_KEY, text, lambda m: log(m, REPO))
    except Exception as e:
        log(f"投稿失敗: {e}", REPO)
        sys.exit(1)

    # 状態記録
    posted_weeks = state.setdefault("posted_weeks", {})
    week_slot = posted_weeks.setdefault(key, {})
    week_slot[args.slot] = {
        "tweet_id": tweet_id,
        "text": text,
        "posted_at": datetime.now().isoformat(timespec="seconds"),
        "date": today.isoformat(),
        "slot": args.slot,
        "actors": [a["actual_name"] for a in actors],
    }
    _save_json(state_file, state)
    log(f"状態記録: {state_file} (tweet_id={tweet_id}, slot={args.slot})", REPO)


if __name__ == "__main__":
    main()