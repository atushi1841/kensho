#!/usr/bin/env python3
"""kensho_revenue_collect — 全収益源の日次実測データ収集。

毎日1回（critic実行前）に実行され、以下を収集して revenue-daily.json に追記する:
  1. Apify: ポートフォリオ全アクターの使用量（既存のapify-portfolio-stats.jsonから）
  2. RapidAPI: 全APIの可視性・価格設定・基本情報（GraphQL）
  3. Gumroad: 商品情報（既存のbundle_info.jsonから）
  4. 収益サマリー: 課金状態・公開状態の集計

出力: /mnt/d/Project2/kensho/data/revenue-daily.json（日次追記、直近90日保持）
"""

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from typing import Any

PROJECT_DIR = "/mnt/d/Project2/kensho"

# 収集ボリューム指標（本日収集実績/累計）の単一情報源（2026-09-23・手書き値の自動化）
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
from kensho.core import collection_volume  # noqa: E402


# ── 簡易.envローダー（9/7追加: 401対策。dotenv無しのstandalone実装） ──
def _load_env_file() -> None:
    env_path = os.path.join(PROJECT_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass  # .env読み取り失敗しても収集は継続


_load_env_file()

DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT = os.path.join(DATA_DIR, "revenue-daily.json")
APIFY_STATS = "/mnt/d/Project2/apify-portfolio-stats.json"
# v94 (t_360dd497): フォールバック実体は data/tmp/pay_per_event.json（619B, 9/5）。
# 誤パス "/mnt/d/Project2/kensho/pay_per_event.json" は実在せず load_ppe_actors()={} →
# 全件free誤判定（9/11 04:20再発）の原因。両候補を試す（第一候補=実体のあるdata/tmp）。
APIFY_PPE_CANDIDATES = [
    "/mnt/d/Project2/kensho/data/tmp/pay_per_event.json",
    "/mnt/d/Project2/kensho/pay_per_event.json",
]
APIFY_PPE = APIFY_PPE_CANDIDATES[0]  # 後方互換参照（外部スクリプト向け・実読込はCANDIDATES側）
PRICING_CACHE = os.path.join(DATA_DIR, "apify_pricing_cache.json")  # v94項目4: 24hキャッシュ
PRICING_CACHE_TTL_H = 24.0
RAPIDAPI_AUTH = "/mnt/d/Project2/goo-net-car-scraper/rapidapi_auth.json"
GUMROAD_BUNDLE = "/mnt/d/Project2/gumroad-automation/bundle_info.json"
GUMROAD_STATE = os.path.join(DATA_DIR, "gumroad_state.json")
RAPIDAPI_PAID_EFFECT_STATE = os.path.join(DATA_DIR, "rapidapi_paid_effect_state.json")  # t_868caac2 v-effect
# v140 (t_e3302129): RapidAPI収集 read timeout時のlast-known-stateフォールバック（0本虚偽報告防止）
RAPIDAPI_STATE = os.path.join(DATA_DIR, "revenue_rapidapi_state.json")
RAPIDAPI_MAX_RETRIES = 1  # 初回失敗後の再試行回数（backoff 5秒）
RAPIDAPI_RETRY_BACKOFF = 5.0
GUMROAD_SCRIPT = os.path.join(PROJECT_DIR, "scripts", "gumroad_sales_collect.js")
GUMROAD_NODE = "/mnt/c/Program Files/nodejs/node.exe"
# 提案A (t_d7db4ef7): Gumroad初売上を記録する受入基準ファイル。
# kensho_revenue_collect 実行時に、gumroad_state.json が実売上を示せば追記される。
GUMROAD_SALES_LOG = os.path.join(DATA_DIR, "gumroad_sales.log")
MAX_ENTRIES = 90  # 直近90日保持

# Gumroad CDP収集の恒久対策（t_cfe11a7c / critic v60）:
# 根因は「深夜早朝にWindows Chrome/CDPが未起動」+「固定プロファイル起動が既存Chromeに
# ハンドオフされCDPが立たず、nodeの起動待ちが90秒を超えてTimeoutExpired → 前回値凍結」。
# CDPの事前チェック・自動起動・起動待ちは node（gumroad_sales_collect.js, Windows側）で
# 実施する。理由: 本スクリプト(WSL側Python)は Windows localhost:CDP に接続できないため、
# ポート判定はWindows側のnodeでのみ正しく行える。Pythonは一度のsubprocess実行で
# 起動(最大45秒)＋収集を丸ごと渡し、合計時限をここで保証する（起動/収集の分離=node内封じ込め）。
GUMROAD_TOTAL_TIMEOUT = 240.0  # CDP起動(≤45s)+ページ収集の合計上限（従来の90秒→240秒）

# actors_ppe=0 異常検出時の自動再収集設定（9/3 00:20異常の再発防止: t_fc85c305）
RETRY_DELAY_SECONDS = 3.0  # 再収集までの待機秒数
MAX_APIFY_RETRIES = 2  # 再収集の最大試行回数（初回含め最大3回）

# Apify APIトークン（環境変数優先・無ければ既知のデフォルト）
APIFY_TOKEN_DEFAULT = os.environ.get("APIFY_TOKEN_DEFAULT", "")


def get_apify_token() -> str:
    """Apify APIトークンを取得（環境変数優先、無ければ既知のデフォルト）。"""
    return os.environ.get("APIFY_TOKEN", "") or APIFY_TOKEN_DEFAULT


def check_apify_health() -> dict[str, Any]:
    """Apify APIの健康状態を確認する。"""
    token = get_apify_token()
    result: dict[str, Any] = {
        "status": "down",
        "endpoint": "both",
        "http_code": 0,
        "error": None,
        "recovered": False,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    import requests as _req

    # 1) /v2/acts?my=true (メインエンドポイント)
    try:
        r = _req.get(
            f"https://api.apify.com/v2/acts?my=true&token={token}",
            timeout=10,
        )
        result["http_code"] = r.status_code
        if r.status_code == 200:
            result["status"] = "ok"
            result["endpoint"] = "acts"
        elif r.status_code == 404:
            result["status"] = "degraded"
            result["error"] = "404: token失効またはendpoint変更の可能性"
        elif r.status_code == 401:
            result["status"] = "degraded"
            result["error"] = "401: トークン無効"
        else:
            result["status"] = "degraded"
            result["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        result["error"] = f"acts接続失敗: {type(e).__name__}"

    # 2) /v2/users/me (補助エンドポイント)
    try:
        r2 = _req.get(
            f"https://api.apify.com/v2/users/me?token={token}",
            timeout=10,
        )
        if r2.status_code != 200:
            if result["status"] == "ok":
                result["status"] = "degraded"
                result["endpoint"] = "acts+users/me"
                result["error"] = f"users/me: HTTP {r2.status_code}"
    except Exception as e:
        if result["status"] == "ok":
            result["status"] = "degraded"
            result["error"] = f"users/me接続失敗: {type(e).__name__}"

    return result


def _save_pricing_cache(pricing: dict[str, dict[str, Any]]) -> None:
    """fetch_apify_pricing 成功結果を data/apify_pricing_cache.json に保存（v94項目4）。

    t_fda64102 (2026-09-25): 部分取得（25件中一部のみ/0件）で既存キャッシュが縮小し、
    次回の判定が free/unknown へ化ける事故を防ぐ。24h以内の既存エントリはマージして
    保持し、取得件数（fetched）とキャッシュ由来件数（merged_from_cache）を記録する。
    """
    try:
        fresh = {k: v for k, v in pricing.items() if not k.startswith("_")}
        merged = dict(_load_pricing_cache())  # 24h以内の既存のみ
        merged.update(fresh)  # 今回取得分を優先
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "fetched": len(fresh),
            "merged_from_cache": len(merged) - len(fresh),
            "pricing": merged,
        }
        os.makedirs(os.path.dirname(PRICING_CACHE), exist_ok=True)
        with open(PRICING_CACHE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  ⚠️ pricingキャッシュ書込失敗（収集は継続）: {e}")


def _load_pricing_cache() -> dict[str, dict[str, Any]]:
    """24h以内のpricingキャッシュを返す。無ければ空dict（v94項目4）。"""
    if not os.path.exists(PRICING_CACHE):
        return {}
    try:
        with open(PRICING_CACHE, encoding="utf-8") as f:
            payload = json.load(f)
        saved_at = datetime.fromisoformat(str(payload.get("saved_at", "")))
        age_h = (datetime.now() - saved_at).total_seconds() / 3600.0
        if age_h > PRICING_CACHE_TTL_H:
            return {}
        pricing = payload.get("pricing") or {}
        return dict(pricing) if isinstance(pricing, dict) else {}
    except Exception:
        return {}


def fetch_apify_pricing() -> dict[str, dict[str, Any]]:
    """Apify APIからポートフォリオ全アクターの課金状態を直接取得。

    pay_per_event.json のような静的ファイルに依存せず、Apify APIの
    pricingInfosを正とする（t_1323b323: PPE collection accuracy）。

    返り値: {実API名: {pricing_model, price, is_public}}
    API失敗時は空dictを返し、呼び出し側で pay_per_event.json にフォールバックする。
    """
    import requests

    token = get_apify_token()
    result: dict[str, dict[str, Any]] = {}
    # v94 (t_360dd497) 項目2: 個別アクター取得失敗でループ全体を放棄しない
    # （9/11 04:20実測: 25本途中でConnectTimeout → result={} → フォールバック空振り）。
    # 1本は try/except+continue、連続3本失敗で以降を打ち切る（レート制限/不通の連鎖防止）。
    consecutive_failures = 0
    # ── 事前健康度チェック（404/token失効検出・早期フォールバック） ──
    health = check_apify_health()
    if health["status"] == "down":
        print(f"  ⚠️ Apify API不通(健康度チェック): {health.get('error', '不明')} → キャッシュへフォールバック")
        cached = _load_pricing_cache()
        if cached:
            print(f"  ↑ pricingキャッシュ（24h以内）を使用: {len(cached)}件")
            return cached
        return {}
    try:
        # 1. 全アクターのID一覧を取得
        resp = requests.get(f"https://api.apify.com/v2/acts?my=true&token={token}", timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        items = data.get("items", [])
        name_to_id = {a.get("name"): a.get("id") for a in items if a.get("id")}

        # 2. ポートフォリオ対象アクターの個別情報を取得（pricingInfosは個別APIでのみ返る）
        targets = sorted(set(PORTFOLIO_TO_ACTUAL.values()))
        for actual_name in targets:
            aid = name_to_id.get(actual_name)
            if not aid:
                continue
            if consecutive_failures >= 3:
                print(
                    f"  ⚠️ Apify pricing個別取得を打ち切り（連続{consecutive_failures}失敗）"
                    ": 残り本は部分結果/キャッシュで代替"
                )
                break
            try:
                r = requests.get(f"https://api.apify.com/v2/acts/{aid}?token={token}", timeout=30)
                if r.status_code != 200:
                    consecutive_failures += 1
                    continue
                consecutive_failures = 0
                act = r.json().get("data", {})
            except Exception as e:
                consecutive_failures += 1
                print(f"  ⚠️ Apify pricing個別取得失敗 {actual_name}: {type(e).__name__}（_CONTINUE_）")
                continue
            pricing_infos = act.get("pricingInfos", []) or []
            model = pricing_infos[-1].get("pricingModel") if pricing_infos else "FREE"
            price: float | None = None
            if model == "PAY_PER_EVENT" and pricing_infos:
                events = pricing_infos[-1].get("pricingPerEvent", {}).get("actorChargeEvents", {})
                # デフォルトの結果アイテム単価を採用（無ければ最小のイベント単価）
                evt = events.get("apify-default-dataset-item")
                if evt and evt.get("eventPriceUsd") is not None:
                    price = float(evt["eventPriceUsd"])
                else:
                    prices = [e.get("eventPriceUsd") for e in events.values() if e.get("eventPriceUsd") is not None]
                    if prices:
                        price = float(min(prices))
            result[actual_name] = {
                "pricing_model": model,
                "price": price,
                "is_public": bool(act.get("isPublic")),
                "id": aid,
            }
        if result:
            # v94項目4: 取得成功時は24hキャッシュへ保存（次回API失敗時の代替）
            _save_pricing_cache(result)
            if name_to_id and len(result) * 2 < len([v for v in PORTFOLIO_TO_ACTUAL.values() if v in name_to_id]):
                # 取得件数がポートフォリオ対象の過半数に満たない → 部分結果として明示
                result["_partial"] = {"fetched": len(result)}  # type: ignore[typeddict-item]
    except Exception as e:
        print(f"  ⚠️ Apify pricing API取得失敗: {e}（キャッシュ→pay_per_event.jsonにフォールバック）")
        cached = _load_pricing_cache()
        if cached:
            print(f"  ↑ pricingキャッシュ（24h以内）を使用: {len(cached)}件")
        return cached
    if not result:
        # 連続失敗で打ち切り（0件）→ 例外経路と同様にキャッシュを代替として試す（v94）
        cached = _load_pricing_cache()
        if cached:
            print(f"  ↑ pricing個別取得0件 — キャッシュ（24h以内）を使用: {len(cached)}件")
        return cached
    return result


# ポートフォリオ表示名 → Apify実API名（pay_per_event.jsonは実API名で記録されるため変換が必要）
PORTFOLIO_TO_ACTUAL = {
    "japan-camera-market": "japan-used-camera-market-scraper",
    "japan-watch-market": "japan-watch-market-scraper",
    "japan-luxury-market": "japan-luxury-brand-market-scraper",
    "japan-instrument-market": "japan-used-instrument-market-scraper",
    "japan-offmall-market": "japan-offmall-market-scraper",
    "japan-market-mcp": "japan-market-mcp",
    "japan-rent-market": "japan-rent-market-scraper",
    "japan-rent-market-cn": "japan-rent-market-cn",
    "japan-rent-market-kr": "japan-rent-market-kr",
    "japan-property-market": "japan-property-market-scraper",
    "japan-property-market-cn": "japan-property-market-cn",
    "japan-property-market-kr": "japan-property-market-kr",
    "japan-kakaku-price-search": "japan-kakaku-price-search",
    "japan-kakaku-price-search-cn": "japan-kakaku-price-search-cn",
    "japan-kakaku-price-search-kr": "japan-kakaku-price-search-kr",
    "camera-cn": "japan-camera-market-cn-scraper",
    "camera-kr": "japan-camera-market-kr-scraper",
    "watch-cn": "japan-watch-market-scraper-cn",
    "watch-kr": "japan-watch-market-scraper-kr",
    "luxury-cn": "japan-luxury-brand-market-cn",
    "luxury-kr": "japan-luxury-brand-market-kr",
    "instrument-cn": "japan-used-instrument-market-cn",
    "instrument-kr": "japan-used-instrument-market-kr",
    "offmall-cn": "japan-offmall-market-cn",
    "offmall-kr": "japan-offmall-market-kr",
}


def measure_apify_ppe_revenue(
    name_to_id: dict[str, Any],
    prices: dict[str, float | None],
    days: int = 30,
) -> dict[str, Any]:
    """PPE設定済みアクターの外部ユーザー課金収益を実測する（t_4de26f84: 7日後判定基盤）。

    Apifyの収益は「外部ユーザーのrun × charged events × 単価」で発生する。
    自分（owner）のrunは accountedChargedEventCounts=0 で課金されないため、
    userId != owner のrunのみを集計対象とする。

    list viewは chargedEventCounts を返さないため、外部ユーザーrunに絞って
    detail view（/runs/{id}）を個別取得する（API負荷最小化）。

    返り値: {
      "window_days": days,
      "external_runs": 外部ユーザーrun総数,
      "charged_items": 課金対象dataset-item総数,
      "revenue_usd": 推定収益（charged_items × 単価の合計）,
      "per_actor": {name: {external_runs, charged_items, revenue_usd, total_runs_window}},
      "error": (失敗時)
    }
    """
    from datetime import timedelta

    import requests

    token = get_apify_token()
    result: dict[str, Any] = {
        "window_days": days,
        "external_runs": 0,
        "charged_items": 0,
        "revenue_usd": 0.0,
        "per_actor": {},
    }
    try:
        owner = (
            requests
            .get(f"https://api.apify.com/v2/users/me?token={token}", timeout=30)
            .json()
            .get("data", {})
            .get("id")
        )
        if not owner:
            result["error"] = "owner id 取得失敗"
            return result
    except Exception as e:
        result["error"] = f"owner取得例外: {e}"
        return result

    cutoff = datetime.now() - timedelta(days=days)
    for name, aid in name_to_id.items():
        price = prices.get(name)
        if price is None:
            continue
        try:
            resp = requests.get(
                f"https://api.apify.com/v2/acts/{aid}/runs?token={token}&limit=100",
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            runs = resp.json().get("data", {}).get("items", [])
        except Exception:
            continue

        ext_runs = 0
        charged_items = 0
        total_window = 0
        for run in runs:
            started = run.get("startedAt")
            if started:
                try:
                    st = datetime.fromisoformat(started.replace("Z", "+00:00")).replace(tzinfo=None)
                    if st < cutoff:
                        continue
                except Exception:
                    pass
            total_window += 1
            if run.get("userId") == owner:
                continue  # 自分のrunは課金対象外
            ext_runs += 1
            # 外部ユーザーrunのみdetail取得してcharged eventsを確認
            try:
                dr = requests.get(
                    f"https://api.apify.com/v2/acts/{aid}/runs/{run.get('id')}?token={token}",
                    timeout=30,
                )
                if dr.status_code == 200:
                    cec = dr.json().get("data", {}).get("chargedEventCounts", {}) or {}
                    charged_items += cec.get("apify-default-dataset-item", 0)
            except Exception:
                pass

        actor_rev = charged_items * price
        result["external_runs"] += ext_runs
        result["charged_items"] += charged_items
        result["revenue_usd"] += actor_rev
        result["per_actor"][name] = {
            "external_runs": ext_runs,
            "charged_items": charged_items,
            "revenue_usd": round(actor_rev, 6),
            "total_runs_window": total_window,
        }
    result["revenue_usd"] = round(result["revenue_usd"], 6)
    return result


def load_ppe_actors() -> dict[str, float]:
    """pay_per_event.json からPPE設定済みアクター（実API名 → 単価）を読み込む。

    v94 (t_360dd497): 誤パス（実体なし）で全件free誤判定が起きたため、
    APIFY_PPE_CANDIDATES を順に試し、最初に読めたファイルを使う。
    APIFY_PPE（先頭候補・外部からpatchable）も候補に含める。
    """
    data: Any = None
    candidates = (
        [APIFY_PPE, *APIFY_PPE_CANDIDATES] if APIFY_PPE not in APIFY_PPE_CANDIDATES else list(APIFY_PPE_CANDIDATES)
    )
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            break
        except Exception:
            continue
    if not isinstance(data, dict):
        return {}
    return dict(data.get("actors_ppe", {}))


def _is_ppe_zero_anomaly(apify_result: dict[str, Any]) -> bool:
    """Apify収集結果が actors_ppe=0 異常かを判定する（t_fc85c305）。

    異常条件:
      - アクターが1件以上ある（Total > 0）
      - PPE課金アクターが0件
      - 無料アクターも0件
      - 詳細レコードに price が存在するものがない（集計バグ／API失敗のサイン）

    9/3 00:20: actors_ppe=0 / actors_free=0 を再現する集計バグを検出する。
    フォールバック正常時（pay_per_event.json）は price を持つ詳細が出るため、
    「Total>0 かつ price付き詳細0件かつfreeも0件」を真の異常シグナルとする。
    """
    if apify_result.get("error"):
        return False
    total = apify_result.get("actors_total", 0)
    ppe = apify_result.get("actors_ppe", 0)
    free = apify_result.get("actors_free", 0)
    if total <= 0 or ppe > 0:
        return False
    # v94 (t_360dd497): billing=unknown（API失敗+フォールバック空）は ppe=0 異常の新版。
    # 9/11 04:20の検知ギャップ（ppe=0/free=25が素通り）を塞ぐ。
    if apify_result.get("actors_unknown", 0) > 0:
        return True
    if free > 0:
        return False
    # 詳細レコードに price が1件も無い → 真の異常（APIもfallbackも空振り）
    priced_count = sum(1 for d in apify_result.get("details", []) if d.get("price") is not None)
    return priced_count == 0


def _retry_apify_collect() -> dict[str, Any]:
    """Apify収集を再試行し、最良の結果を返す（t_fc85c305）。

    初回 collect_apify() が actors_ppe=0 異常だった場合に呼ばれる。
    MAX_APIFY_RETRIES 回まで再試行し、いずれも異常の場合は最後の結果をそのまま返す。
    """
    best: dict[str, Any] = {}
    for attempt in range(1, MAX_APIFY_RETRIES + 1):
        time.sleep(RETRY_DELAY_SECONDS)
        print(f"  ↻ Apify再収集 {attempt}/{MAX_APIFY_RETRIES} 回目...")
        retried = collect_apify()
        if not _is_ppe_zero_anomaly(retried):
            print(f"  ✓ 再収集 {attempt} 回目で正常値取得: actors_ppe={retried.get('actors_ppe', 0)}")
            return retried
        # 正常な値（price付き詳細あり）を保持しておく
        priced = sum(1 for d in retried.get("details", []) if d.get("price") is not None)
        if priced > 0 and not best:
            best = retried
    return best if best else retried


def collect_apify() -> dict[str, Any]:
    """Apifyポートフォリオ統計を読み込む（既存のapify_portfolio_stats.shの出力を利用）。

    actor課金状態（PPE/無料）は Apify API の pricingInfos を直接参照して判定する。
    API取得失敗時は pay_per_event.json をフォールバックとして使用する（t_1323b323）。
    """
    result: dict[str, Any] = {
        "source": "apify",
        "actors_total": 0,
        "actors_public": 0,
        "actors_ppe": 0,
        "actors_free": 0,
        "actors_unknown": 0,
        "total_users_30d": 0,
        "external_users_total": 0,
        "total_runs": 0,
        "details": [],
    }
    if not os.path.exists(APIFY_STATS):
        result["error"] = "Apify stats file not found"
        return result

    # 課金状態はApify APIのpricingInfosを正とする（pay_per_event.jsonはフォールバック）
    api_pricing = fetch_apify_pricing()
    api_pricing = {k: v for k, v in api_pricing.items() if not k.startswith("_")}
    cached_pricing = _load_pricing_cache()  # t_fda64102: API部分失敗時の第2ソース（24h以内）
    ppe_actors = load_ppe_actors()  # フォールバック用
    use_api = bool(api_pricing)
    # v94項目3: APIもフォールバックファイルも空 → 「無料」と断定せず unknown 扱い
    fallback_empty = not ppe_actors

    try:
        with open(APIFY_STATS, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or not data:
            result["error"] = "Empty or invalid format"
            return result

        # 最新エントリ
        latest = data[-1]
        result["date"] = latest.get("date", "?")
        for k, v in latest.items():
            if not isinstance(k, str):
                continue
            if k == "date":
                continue
            if isinstance(v, dict):
                actual_name = PORTFOLIO_TO_ACTUAL.get(k, k)
                if use_api and actual_name in api_pricing:
                    info = api_pricing[actual_name]
                    billing = "ppe" if info["pricing_model"] == "PAY_PER_EVENT" else "free"
                    price = info["price"]
                    is_public = info["is_public"]
                elif actual_name in cached_pricing:
                    # t_fda64102: APIが部分取得（一部アクター欠落）でも、24h以内のキャッシュに
                    # 既知エントリがあればそれを第2ソースとして使う（誤free判定の防止）。
                    info = cached_pricing[actual_name]
                    billing = "ppe" if info["pricing_model"] == "PAY_PER_EVENT" else "free"
                    price = info["price"]
                    is_public = info["is_public"]
                elif use_api:
                    # t_fda64102: API自体は生きているが、このアクターの pricing が取れなかった場合。
                    # pay_per_event.json に載っている場合のみ ppe として救済し、それ以外は
                    # 「無料設定」と断定せず unknown にする（9/19に20本を誤ってfree報告した根因）。
                    price = ppe_actors.get(actual_name)
                    billing = "ppe" if price is not None else "unknown"
                    is_public = True
                elif not use_api and fallback_empty:
                    # v94項目3: API失敗＋pay_per_event.jsonも不在/空 → 課金状態不明。
                    # 「無料設定」と断定すると収益判断を誤る（9/11 04:20誤報の再発防止）。
                    billing = "unknown"
                    price = None
                    is_public = True
                else:
                    # フォールバック: pay_per_event.json
                    price = ppe_actors.get(actual_name)
                    billing = "ppe" if price is not None else "free"
                    is_public = True  # ポートフォリオ統計は公開アクターのみ想定
                if billing == "ppe":
                    result["actors_ppe"] += 1
                elif billing == "unknown":
                    result["actors_unknown"] += 1
                else:
                    result["actors_free"] += 1
                result["total_runs"] += v.get("runs", 0)
                result["total_users_30d"] += v.get("u30d", 0)
                # external_users系はkensho-revenue-report.shが消費（profile版から統合）
                result["external_users_total"] += v.get("external_users", 0)
                result["details"].append({
                    "name": k,
                    "actual_name": actual_name,
                    "users": v.get("users", 0),
                    "u30d": v.get("u30d", 0),
                    "external_users": v.get("external_users", 0),
                    "external_runs": v.get("external_runs", 0),
                    "runs": v.get("runs", 0),
                    "billing": billing,
                    "price": price,
                    "is_public": is_public,
                })
        result["actors_total"] = len(result["details"])
        if use_api:
            result["actors_public"] = sum(1 for d in result["details"] if d.get("is_public"))
        else:
            result["actors_public"] = result["actors_total"]  # フォールバック: 全件公開と仮定

        # PPE実収益計測（t_4de26f84: 7日後判定基盤）— 外部ユーザー課金のみ集計
        # api_pricing に id が入っていればそれを使い、無ければ取得しない（フォールバック）
        ppe_name_to_id = {
            d["actual_name"]: api_pricing[d["actual_name"]].get("id")
            for d in result["details"]
            if d.get("billing") == "ppe" and d["actual_name"] in api_pricing and api_pricing[d["actual_name"]].get("id")
        }
        ppe_prices = {d["actual_name"]: d.get("price") for d in result["details"] if d.get("billing") == "ppe"}
        if ppe_name_to_id:
            result["ppe_revenue"] = measure_apify_ppe_revenue(ppe_name_to_id, ppe_prices)
    except Exception as e:
        result["error"] = str(e)

    return result


def _rapidapi_fetch_apis() -> list[dict[str, Any]]:
    """GraphQLで自アカウントの全APIノードを取得する（失敗時は例外を送出）。

    v140 (t_e3302129): 従来 collect_rapidapi() 内にインラインだった処理を
    リトライ対応のため分離。read timeout等の例外は呼び出し側で捕捉する。
    """
    import requests

    with open(RAPIDAPI_AUTH, encoding="utf-8") as f:
        auth = json.load(f)
    return _rapidapi_fetch_with_auth(requests, auth)


def _rapidapi_fetch_with_auth(requests: Any, auth: dict[str, Any]) -> list[dict[str, Any]]:
    # Cookieパース
    cookies: dict[str, str] = {}
    if isinstance(auth.get("cookies"), str):
        for part in auth["cookies"].split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k] = v

    headers = {
        "content-type": "application/json",
        "csrf-token": auth.get("csrf_token", ""),
        "origin": "https://rapidapi.com",
        "rapid-client": "provider-dashboard-service",
        "referer": "https://rapidapi.com/_studio/",
        "x-entity-id": auth.get("entity_id", ""),
    }

    query = """
    query GetApis($where: ApiWhereInput) {
      apis(where: $where) {
        nodes {
          id
          name
          visibility
          pricing
          currentVersion {
            id
            name
            versionStatus
          }
        }
      }
    }
    """
    variables = {"where": {"ownerId": [auth.get("entity_id", "")]}}
    payload = {"operationName": "GetApis", "variables": variables, "query": query}

    resp = requests.post(
        "https://rapidapi.com/gateway/graphql",
        headers=headers,
        cookies=cookies,
        json=payload,
        timeout=15,
    )
    data = resp.json()
    apis = data.get("data", {}).get("apis", {}).get("nodes", [])
    return list(apis)


def _save_rapidapi_state(result: dict[str, Any]) -> None:
    """成功収集時のみ last-known-state を保存する（v140）。"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        payload = {
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "apis_total": result.get("apis_total", 0),
            "apis_public": result.get("apis_public", 0),
            "apis_private": result.get("apis_private", 0),
            "apis_freemium": result.get("apis_freemium", 0),
            "details": result.get("details", []),
        }
        with open(RAPIDAPI_STATE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  ⚠️ RapidAPI last-known-state保存失敗: {e}")


def _load_rapidapi_state() -> dict[str, Any] | None:
    """last-known-stateを読み込む（v140）。無ければ None。"""
    if not os.path.exists(RAPIDAPI_STATE):
        return None
    try:
        with open(RAPIDAPI_STATE, encoding="utf-8") as f:
            state = json.load(f)
        return state if isinstance(state, dict) else None
    except Exception:
        return None


def collect_rapidapi() -> dict[str, Any]:
    """RapidAPIの全API情報をGraphQLで取得。

    v140 (t_e3302129): read timeoutで apis_total=0 の虚偽報告が発生した（9/13実測）。
    対策: ①失敗時リトライ1回（backoff 5秒）②それでも失敗時は last-known-state
    （data/revenue_rapidapi_state.json）を復元し、error と fallback フラグを残す。
    """
    result: dict[str, Any] = {
        "source": "rapidapi",
        "apis_total": 0,
        "apis_public": 0,
        "apis_private": 0,
        "apis_freemium": 0,
        "details": [],
    }
    if not os.path.exists(RAPIDAPI_AUTH):
        result["error"] = "RapidAPI auth file not found"
        return result

    # リトライ（初回+RAPIDAPI_MAX_RETRIES回、backoff秒）
    apis: list[dict[str, Any]] | None = None
    last_err: str = ""
    for attempt in range(1 + RAPIDAPI_MAX_RETRIES):
        if attempt > 0:
            print(f"  ↻ RapidAPI収集リトライ {attempt}/{RAPIDAPI_MAX_RETRIES}（{RAPIDAPI_RETRY_BACKOFF:.0f}秒待機）...")
            time.sleep(RAPIDAPI_RETRY_BACKOFF)
        try:
            apis = _rapidapi_fetch_apis()
            break
        except Exception as e:
            last_err = str(e)
            apis = None

    if apis is not None:
        result["apis_total"] = len(apis)
        for a in apis:
            vis = a.get("visibility", "UNKNOWN")
            pricing = a.get("pricing", "UNKNOWN")
            if vis == "PUBLIC":
                result["apis_public"] += 1
            else:
                result["apis_private"] += 1
            if pricing == "FREEMIUM":
                result["apis_freemium"] += 1
            result["details"].append({
                "id": a.get("id", ""),
                "name": a.get("name", "?"),
                "visibility": vis,
                "pricing": pricing,
                "version": a.get("currentVersion", {}).get("name", "?"),
                "version_status": a.get("currentVersion", {}).get("versionStatus", "?"),
            })
        if result["apis_total"] > 0:
            _save_rapidapi_state(result)
        return result

    # 全試行失敗 → last-known-state フォールバック（0本虚偽報告の防止）
    result["error"] = last_err
    state = _load_rapidapi_state()
    if state and state.get("apis_total", 0) > 0:
        result["apis_total"] = state["apis_total"]
        result["apis_public"] = state.get("apis_public", 0)
        result["apis_private"] = state.get("apis_private", 0)
        result["apis_freemium"] = state.get("apis_freemium", 0)
        result["details"] = state.get("details", [])
        result["fallback"] = "last_known_state"
        result["fallback_state_saved_at"] = state.get("saved_at")
        print(
            "  ⚠️ RapidAPI収集失敗 — last-known-state復元: "
            f"apis_total={result['apis_total']} (state {state.get('saved_at')})"
        )
        # 頂層記録用（build_revenue_summaryが読む）
        result["last_known_total"] = state["apis_total"]
        result["last_known_error"] = last_err
    return result


def _to_windows_path(path: str) -> str:
    """WSLパス（/mnt/d/...）をWindowsパス（D:\\...）に変換する。"""
    if path.startswith("/mnt/"):
        drive = path[5].upper()
        rest = path[7:].replace("/", "\\")
        return f"{drive}:\\{rest}"
    return path


def _persist_last_success_at() -> None:
    """収集成功時のみ gumroad_state.json の last_success_at を更新（鮮度判定用）。"""
    try:
        if not os.path.exists(GUMROAD_STATE):
            return
        with open(GUMROAD_STATE, encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            state = {}
        # Only update last_success_at if login was successful
        if state.get("login_ok", False):
            state["last_success_at"] = datetime.now().isoformat(timespec="seconds")
        with open(GUMROAD_STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ last_success_at永続化失敗: {e}")


def _extract_sale_fields(state: dict[str, Any]) -> dict[str, Any]:
    """gumroad_state.json から売上記録に必要なフィールドを安全に取り出す。"""
    total_sales = state.get("total_sales", 0)
    total_earnings = state.get("total_earnings_usd")
    return {
        "total_sales": total_sales if isinstance(total_sales, (int, float)) else 0,
        "total_earnings_usd": total_earnings if isinstance(total_earnings, (int, float)) else None,
        "balance_usd": state.get("balance_usd"),
        "login_ok": state.get("login_ok", True),
        "collected_at": state.get("collected_at") or datetime.now().isoformat(timespec="seconds"),
    }


def record_gumroad_sales(
    state_file: str | None = None,
    log_file: str | None = None,
) -> bool:
    """Gumroad実売上があれば data/gumroad_sales.log に追記する（提案A受入基準）。

    gumroad_state.json（CDP収集結果）が実売上（total_sales>0 または
    total_earnings_usd>0）を示した場合のみ1行追記する。既に記録済みの
    collected_at は重複追記しない（収集runごとに最大1行）。

    返り値: 売上行を書き込んだ場合は True、売上ゼロまたは追記不要なら False。
    """
    sf = state_file or GUMROAD_STATE
    lf = log_file or GUMROAD_SALES_LOG
    if not os.path.exists(sf):
        return False
    try:
        with open(sf, encoding="utf-8") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            return False
    except Exception:
        return False

    fields = _extract_sale_fields(state)
    has_sale = fields["total_sales"] > 0 or bool(fields["total_earnings_usd"])
    if not has_sale:
        return False

    line = (
        f"{fields['collected_at']} total_sales={fields['total_sales']}"
        f" earnings_usd={fields['total_earnings_usd']}"
        f" balance_usd={fields['balance_usd']} login_ok={fields['login_ok']}\n"
    )

    # 重複防止: 同一 collected_at の行が既にある場合は追記しない
    try:
        os.makedirs(os.path.dirname(lf) or ".", exist_ok=True)
        if os.path.exists(lf):
            with open(lf, encoding="utf-8") as f:
                existing = f.read()
            if existing:
                marker = f"{fields['collected_at']} total_sales="
                last_line = existing.splitlines()[-1]
                if marker in last_line:
                    return False
        with open(lf, "a", encoding="utf-8") as f:
            f.write(line)
        print(f"✓ Gumroad売上を記録: data/gumroad_sales.log ({line.strip()})")
        return True
    except Exception as e:
        print(f"  ⚠️ gumroad_sales.log 追記失敗: {e}")
        return False


def update_gumroad_state_via_cdp() -> bool:
    """CDP（nodeスクリプト）でGumroad売上データを取得し、gumroad_state.jsonを更新する。

    事前CDPチェック・Chrome自動起動・起動待ちは Windows側の node スクリプト
    （gumroad_sales_collect.js の ensureChrome）内で完結する。
    WSL側Pythonは Windows localhost:CDP に接続できないため、ポート判定・起動は
    Windows側nodeでのみ正しく行える（歴史的観察: 127.0.0.1:9222 がWSLから常にCLOSED）。

    - タイムアウト分離: node内部で起動待ち（最大45秒）→ ページ収集の順に処理し、
      Python側は1回のsubprocessに GUMROAD_TOTAL_TIMEOUT(240秒) をかける
      （従来の timeouts=90秒 が、Chrome起動の遅延でTimeoutExpired→前回値凍結を起こしていた）。
    - 成功時のみ last_success_at を永続化。
    - 失敗しても既存の gumroad_state.json があれば収集は継続（呼び出し側でフォールバック）。
    """
    if not os.path.exists(GUMROAD_NODE):
        print("  ⚠️ node.exeが見つかりません — Gumroad売上データは前回値を使用")
        return False
    if not os.path.exists(GUMROAD_SCRIPT):
        print("  ⚠️ gumroad_sales_collect.jsが見つかりません — Gumroad売上データは前回値を使用")
        return False

    try:
        r = subprocess.run(
            [GUMROAD_NODE, _to_windows_path(GUMROAD_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=GUMROAD_TOTAL_TIMEOUT,
        )
        if r.stdout:
            for line in r.stdout.strip().splitlines():
                print(f"    {line}")
        if r.returncode != 0:
            if r.stderr:
                print(f"fail-mark ⚠️ Gumroad売上取得失敗 (rc={r.returncode}): {r.stderr.strip()[:200]}")
            else:
                print(f"fail-mark ⚠️ Gumroad売上取得失敗 (rc={r.returncode})")
            return False
        # 成功時のみ last_success_at を永続化（鮮度表示の基準）
        _persist_last_success_at()
        return True
    except subprocess.TimeoutExpired:
        print(
            f"timeout-mark ⚠️ Gumroad売上取得がタイムアウト（{GUMROAD_TOTAL_TIMEOUT:.0f}秒・CDP起動+収集）— 前回値を使用"
        )
        return False
    except Exception as e:
        print(f"fail-mark ⚠️ Gumroad売上取得エラー: {e} — 前回値を使用")
        return False


def collect_gumroad() -> dict[str, Any]:
    """Gumroad商品情報を読み込む（bundle_info.json + gumroad_state.json）。

    Note: 受入基準ファイル gumroad_sales.log への追記は record_gumroad_sales()
    が担う（main() 内で collect_gumroad 直後に呼ばれる）。
    """
    result: dict[str, Any] = {
        "source": "gumroad",
        "products": 0,
        "details": [],
        "state_exists": False,
    }
    # bundle_info.json
    if os.path.exists(GUMROAD_BUNDLE):
        try:
            with open(GUMROAD_BUNDLE, encoding="utf-8") as f:
                bundle = json.load(f)
            # bundle_info.json の zip は相対パスのため bundle のあるディレクトリ基準で解決する
            zip_path = bundle.get("zip", "")
            if zip_path and not os.path.isabs(zip_path):
                zip_path = os.path.join(os.path.dirname(GUMROAD_BUNDLE), zip_path)
            result["products"] = 1
            result["details"].append({
                "title": bundle.get("title", "?"),
                "price": bundle.get("price", "?"),
                "zip_exists": bool(zip_path) and os.path.exists(zip_path),
                "zip_size": os.path.getsize(zip_path) if zip_path and os.path.exists(zip_path) else 0,
            })
        except Exception as e:
            result["bundle_error"] = str(e)
    # gumroad_state.json
    if os.path.exists(GUMROAD_STATE):
        result["state_exists"] = True
        try:
            with open(GUMROAD_STATE, encoding="utf-8") as f:
                state = json.load(f)
            # 売上情報があれば取得
            if isinstance(state, dict):
                for k in [
                    "sales",
                    "revenue",
                    "total_sales",
                    "total_revenue",
                    "balance_usd",
                    "last_7_days_usd",
                    "last_28_days_usd",
                    "total_earnings_usd",
                    "login_ok",
                    "collected_at",
                    "last_success_at",
                ]:
                    if k in state:
                        result[k] = state[k]
        except Exception:
            pass
    return result


def build_revenue_summary(
    apify: dict[str, Any],
    rapidapi: dict[str, Any],
    gumroad: dict[str, Any],
    volume: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """全収益源を集約したサマリーを生成。

    volume: 収集ボリューム指標（未指定なら collection_volume から実データ集計）。
            テストで決定的な値を注入するための入口（2026-09-23）。
    """
    now = datetime.now()
    entry: dict[str, Any] = {
        "date": now.strftime("%Y-%m-%d"),
        "collected_at": now.isoformat(),
        "apify": apify,
        "rapidapi": rapidapi,
        "gumroad": gumroad,
    }

    # 収益改善機会の自動検出
    opportunities = []
    warnings = []

    # Apify: 公開アクターが課金設定無し（PPE設定があれば正常）
    # v94項目3: 課金状態不明（API失敗+フォールバック空）を「無料設定」と断定しない
    if apify.get("actors_unknown", 0) > 0:
        warnings.append("Apify課金状態不明（API超時+フォールバック欠損）— 「無料」ではありません")
    elif apify.get("actors_total", 0) > 0 and apify.get("actors_ppe", 0) == 0:
        warnings.append("Apify公開アクター全件が無料設定（PPE課金なし）")
    elif apify.get("actors_ppe", 0) > 0:
        ppe_names = [d.get("name", "?") for d in apify.get("details", []) if d.get("billing") == "ppe"]
        opportunities.append(f"Apify PPE課金アクター {apify.get('actors_ppe')}件: {', '.join(ppe_names[:5])}")

    # RapidAPI: 非公開APIがある
    if rapidapi.get("apis_private", 0) > 0:
        private_names = [d["name"] for d in rapidapi.get("details", []) if d.get("visibility") != "PUBLIC"]
        pn_joined = ", ".join(private_names[:5])
        opportunities.append(f"RapidAPI非公開API {len(private_names)}本: {pn_joined}")

    # Gumroad: 売上データがない / 売上ゼロ
    gumroad_earnings = gumroad.get("total_earnings_usd")
    if not gumroad.get("state_exists"):
        warnings.append("Gumroad売上データ未取得（ブラウザ自動化が必要）")
    elif gumroad_earnings is None or gumroad_earnings <= 0:
        if gumroad.get("login_ok") is False:
            warnings.append("Gumroadログインセッション失効（Cookie再エクスポートが必要）")
        else:
            warnings.append("Gumroad売上ゼロ継続（販促施策の実行候補）")
    else:
        opportunities.append(f"Gumroad売上 ${gumroad_earnings:.2f} USD（測定基盤稼働中）")

    # 使用量の多いアクター
    if apify.get("details"):
        high_usage = sorted(
            [d for d in apify["details"] if d.get("u30d", 0) > 0],
            key=lambda x: x.get("u30d", 0),
            reverse=True,
        )[:5]
        if high_usage:
            hu_str = ", ".join(f"{d['name']}(u30d={d['u30d']})" for d in high_usage)
            opportunities.append(f"Apify高使用量アクター: {hu_str}")

    entry["opportunities"] = opportunities
    entry["warnings"] = warnings

    # v140 (t_e3302129): collector健全性/top層last-known記録（rebuild時フォールバックを明示）
    collectors: dict[str, Any] = {
        "apify_ok": "error" not in apify,
        "rapidapi_ok": "error" not in rapidapi,
        "gumroad_ok": bool(gumroad.get("state_exists")),
    }
    # 2026-09-23 (t_5e16a983申し送り): 収集ボリュームを実データから自動計上。
    #   従来は revenue-status.html のカードと collectors.collected_today を手書きしており、
    #   ダッシュボード再生成でカードが消える／値が222のまま固定化する虚偽リスクがあった。
    try:
        _volume = volume if volume is not None else collection_volume.volume_stats(PROJECT_DIR)
        collectors["collected_today"] = _volume["collected_today"]
        collectors["collected_total"] = _volume["collected_total"]
        collectors["collected_today_source"] = _volume["collected_today_source"]
        collectors["collected_today_runs"] = _volume["collected_today_runs"]
    except Exception as e:  # noqa: BLE001 — 計測失敗で収集全体は止めない
        warnings.append(f"収集ボリューム集計に失敗（dashboardは前回値表示）: {e}")
    if rapidapi.get("fallback") == "last_known_state":
        collectors["rapidapi_cache_fallback"] = True
        collectors["rapidapi_fallback_state_saved_at"] = rapidapi.get("fallback_state_saved_at")
        collectors["rapidapi_error"] = rapidapi.get("error")
        entry["last_known_total"] = rapidapi.get("last_known_total")
        entry["last_known_error"] = rapidapi.get("last_known_error")
        warnings.append(
            f"RapidAPI収集失敗（last-known-stateフォールバックで apis_total={rapidapi.get('apis_total')} を表示、"
            f"state鮮度 {rapidapi.get('fallback_state_saved_at')}）"
        )
    entry["collectors"] = collectors
    # Gumroad: 売上があれば収益見積もりに反映
    gumroad_monthly = gumroad.get("total_earnings_usd") or 0
    gumroad_note = f"Gumroad売上 ${gumroad_monthly:.2f} USD" if gumroad_monthly > 0 else "Gumroad売上なし"
    # Apify PPE実収益（t_4de26f84: 外部ユーザー課金の実測値、30日窓）
    ppe_rev = apify.get("ppe_revenue", {}) or {}
    apify_ppe_monthly = ppe_rev.get("revenue_usd", 0) or 0
    apify_ext_runs = ppe_rev.get("external_runs", 0)
    entry["revenue_estimate"] = {
        "apify_monthly": apify_ppe_monthly,  # PPE実収益（外部ユーザーcharged_items×単価）
        "rapidapi_monthly": 0,  # FREEMIUMのみ（上限到達）
        "gumroad_monthly": gumroad_monthly,
        "total_monthly": round(apify_ppe_monthly + gumroad_monthly, 6),  # 実測値の合計
        "apify_ppe_external_runs": apify_ext_runs,
        "note": (
            f"現状: Apify PPE課金 {apify.get('actors_ppe', 0)}件"
            f"（外部run {apify_ext_runs}件→実収益 ${apify_ppe_monthly:.4f}）、"
            f"無料 {apify.get('actors_free', 0)}件"
            + (f"、課金状態不明 {apify.get('actors_unknown', 0)}件" if apify.get("actors_unknown", 0) > 0 else "")
            + f"、RapidAPI全FREEMIUM、{gumroad_note}。"
            f"課金設定で月1-3万円のポテンシャル"
        ),
    }

    return entry


def attach_apify_ppe_external_views_keys(
    entry: dict[str, Any],
) -> dict[str, Any]:
    """revenue-daily.json エントリに `apify_ppe_external_views_keys` を追記（v18-B / t_b6684e7b）。

    測定スクリプト scripts/apify_ppe_external_views.py が保存した state から、
    当日の測定メトリクスを読み込みエントリに設定する（ネットワーク不要・純粋読み取り）。
    """
    state_path = "/mnt/d/Project2/kensho/data/apify_ppe_external_views_state.json"
    if not os.path.exists(state_path):
        return entry
    try:
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return entry
    today = datetime.now().strftime("%Y-%m-%d")
    for m in (state.get("points") or {}).values():
        if m.get("point_date") != today:
            continue
        per: dict[str, Any] = {}
        for key, mm in (m.get("per_actor") or {}).items():
            per[key] = {
                fld: mm.get(fld)
                for fld in ("actual_name", "external_views", "total_runs", "u30d", "bookmarks", "seo_present")
            }
        entry["apify_ppe_external_views_keys"] = {
            "point": m.get("point"),
            "point_date": m.get("point_date"),
            "baseline": m.get("baseline"),
            "measured_at": m.get("measured_at"),
            "proxy_note": (
                "external_views = 外部(owner以外)ユーザー累積run (Apify公開APIで唯一取得可能な外部エンゲージメント信号)"
            ),
            "actors": per,
        }
        break
    return entry


def attach_rapidapi_paid_effect_keys(
    entry: dict[str, Any],
) -> dict[str, Any]:
    """revenue-daily.json エントリに `rapidapi_paid_effect` を追記（t_868caac2）。

    測定スクリプト scripts/rapidapi_paid_effect.py が保存した state から当日の
    有料プラン効果メトリクスを読み込みエントリに設定する（ネットワーク不要・純粋読み取り）。
    2週間効果測定（FREEMIUM→PAID）の日毎トレンド元として使う。
    """
    if not os.path.exists(RAPIDAPI_PAID_EFFECT_STATE):
        return entry
    try:
        with open(RAPIDAPI_PAID_EFFECT_STATE, encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        return entry
    today = datetime.now().strftime("%Y-%m-%d")
    points = state.get("points") or {}
    if today not in points:
        # 当日分が無ければ直近の point を付与（古い方が無いより良い）
        if not points:
            return entry
        point_date = max(points.keys())
        point = points[point_date]
        point = {**point, "point_date": today, "note": "当日point未取得・直近値で代用"}
    else:
        point = points[today]
    per: dict[str, Any] = {}
    for key, mm in (point.get("per_api") or {}).items():
        per[key] = {
            fld: mm.get(fld)
            for fld in ("visibility", "subscribers", "warnings", "paid_plan_active", "tier_effective_prices")
        }
    entry["rapidapi_paid_effect"] = {
        "point": point.get("point"),
        "point_date": point.get("point_date"),
        "measured_at": point.get("measured_at"),
        "note": point.get("note"),
        "apis": per,
    }
    return entry


def append_to_file(entry: dict[str, Any]) -> None:
    """revenue-daily.jsonに追記（日付ごとに1件のみ・直近90日保持）。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    entries: list[dict[str, Any]] = []
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, encoding="utf-8") as f:
                entries = json.load(f)
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []
    # 同日エントリは上書き（日付ごとに1件のみ保持）
    entry_date = entry.get("date")
    if entry_date:
        entries = [e for e in entries if e.get("date") != entry_date]
    entries.append(entry)
    # 直近MAX_ENTRIES件だけ保持
    entries = entries[-MAX_ENTRIES:]
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
    print(f"✓ revenue-daily.json 更新完了 ({len(entries)} entries, 日付: {entry_date})")


def main() -> None:
    print("【kensho_revenue_collect】収益データ収集開始")
    print(f"  実行時刻: {datetime.now().isoformat()}")
    print()

    # 1. Apify
    print("▶ Apify収集...")
    apify = collect_apify()
    apify_ok = "error" not in apify
    print(f"  {'✓' if apify_ok else '✗'} アクター数: {apify.get('actors_total', '?')}")
    if apify.get("details"):
        print(f"      総runs: {apify.get('total_runs')}, 総u30d: {apify.get('total_users_30d')}")
        ppe = apify.get("actors_ppe", 0)
        free = apify.get("actors_free", 0)
        print(f"      課金: PPE={ppe}件, 無料={free}件")

    # 1.5 actors_ppe=0 異常検出時の自動再収集（t_fc85c305: 9/3 00:20異常の再発防止）
    if _is_ppe_zero_anomaly(apify):
        print("  ⚠️ actors_ppe=0 異常を検出 — 自動再収集を実行します")
        retried = _retry_apify_collect()
        if not _is_ppe_zero_anomaly(retried):
            apify = retried
            print(f"  ✓ 再収集で復旧: actors_ppe={apify.get('actors_ppe', 0)}")
        else:
            print("  ✗ 再収集後も異常継続 — 警告フラグ付きで保存")
            apify["anomaly_ppe_zero"] = True
            apify["anomaly_detected_at"] = datetime.now().isoformat()

    # 2. RapidAPI
    print("▶ RapidAPI収集...")
    rapidapi = collect_rapidapi()
    rap_ok = "error" not in rapidapi
    print(f"  {'✓' if rap_ok else '✗'} API数: {rapidapi.get('apis_total', '?')}")
    print(
        f"      公開: {rapidapi.get('apis_public')}, 非公開: {rapidapi.get('apis_private')}, "
        f"FREEMIUM: {rapidapi.get('apis_freemium')}"
    )

    # 3. Gumroad
    print("▶ Gumroad収集...")
    # CDPで売上データを更新（Chrome自動起動込み・失敗時は前回値で継続）
    gumroad_updated = update_gumroad_state_via_cdp()
    gumroad = collect_gumroad()
    # 提案A (t_d7db4ef7): 実売上があれば受入基準ファイル data/gumroad_sales.log に追記
    record_gumroad_sales()
    print(f"  {'✓' if gumroad.get('products', 0) > 0 else '?'} 商品数: {gumroad.get('products', '?')}")
    if gumroad.get("details"):
        for d in gumroad["details"]:
            print(f"      商品: {d.get('title')}, 価格: ${d.get('price')}")
    if gumroad.get("state_exists"):
        login_ok = gumroad.get("login_ok", True)
        earnings = gumroad.get("total_earnings_usd")
        print(
            f"  {'✓' if login_ok else '✗'} 売上データ: state_exists=True, login_ok={login_ok}"
            + (f", total_earnings=${earnings:.2f} USD" if earnings is not None else "")
        )
    elif not gumroad_updated:
        print("  ⚠️ Gumroad売上データなし（state_exists=False）— CDP収集は失敗・stateファイル未作成")

    # 4. 集約
    print("▶ 収益サマリー生成...")
    entry = build_revenue_summary(apify, rapidapi, gumroad)
    # v18-B: Apify PPE 外部view計測メトリクス（state から添付）
    entry = attach_apify_ppe_external_views_keys(entry)
    # t_868caac2: RapidAPI 有料プラン効果（2週間測定）当日指標（state から添付）
    entry = attach_rapidapi_paid_effect_keys(entry)
    if entry.get("opportunities"):
        print("  収益機会:")
        for o in entry["opportunities"]:
            print(f"    ✅ {o}")
    if entry.get("warnings"):
        print("  警告:")
        for w in entry["warnings"]:
            print(f"    ⚠️ {w}")

    # 5. 保存
    append_to_file(entry)
    print()
    print("完了。")


if __name__ == "__main__":
    main()
