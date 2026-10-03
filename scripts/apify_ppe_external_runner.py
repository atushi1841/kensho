#!/usr/bin/env python3
"""apify_ppe_external_runner — Apify PPE アクターの外部run自動起動スクリプト。

背景:
- PPE課金アクター72本が公開済みだが、外部run=0件で実績収益$0/月
- Gumroad販売も0で停滞継続
- 収集→応募の自動化は完了済みだが「作る」から「売れる」の自動化が未実装

目的:
- 主要PPEアクターを週1以上で自動起動し、外部run数>0を達成
- 月間実績収益>$0（PPE課金アクターの有効run）を実現

使い方:
  python3 scripts/apify_ppe_external_runner.py            # 全PPEアクター起動（本実行）
  python3 scripts/apify_ppe_external_runner.py --top 10   # 上位10件のみ
  python3 scripts/apify_ppe_external_runner.py --dry-run  # テストモード
  python3 scripts/apify_ppe_external_runner.py --actor NAME  # 指定actorのみ

出力:
- 起動結果サマリーをstdoutに出力
- data/apify_ppe_external_runs_state.json に履歴保存
- revenue-daily.json 当日エントリに `apify_ppe_external_runs` メトリクス追記
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

# === 設定 ===
PROJECT_DIR = "/mnt/d/Project2/kensho"
API_BASE = "https://api.apify.com/v2"
STATE_FILE = os.path.join(PROJECT_DIR, "data", "apify_ppe_external_runs_state.json")
REVENUE_DAILY = os.path.join(PROJECT_DIR, "data", "revenue-daily.json")
APIFY_PPE_FILE = os.path.join(PROJECT_DIR, "data", "tmp", "pay_per_event.json")

# APIFY_TOKEN 読み込み（.env対応）
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
        pass

_load_env_file()
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip() or os.environ.get("APIFY_TOKEN_DEFAULT", "").strip()

# 起動対象アクター優先度（価格降順 → 収益インパクト大）
# price_usd が高い順で、外部ユーザーが実行しやすい汎用アクターを優先
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
    # $0.004/$0.003 アクター
    {"actual_name": "eurostat-indicators", "fallback_id": "pAxQ0lRyArudhK9Wx", "priority": 4, "price_usd": 0.004},
    {"actual_name": "world-bank-indicators", "fallback_id": "u2qsG1UfVHWsgl8Dg", "priority": 4, "price_usd": 0.003},
    # $0.002 アクター
    {"actual_name": "goo-net-car-scraper", "fallback_id": "bgm5Gxn4BeBmoO7xD", "priority": 5, "price_usd": 0.002},
    {"actual_name": "biglemon-machinery-scraper", "fallback_id": "W9cXhDckzHd9RZWnQ", "priority": 5, "price_usd": 0.002},
    {"actual_name": "digimart-japan-used-instrument-scraper", "fallback_id": "FSuoQiX8OG4KuIQ9c", "priority": 5, "price_usd": 0.002},
    {"actual_name": "golfpartner-used-club-scraper", "fallback_id": "xPSQSSsdVjRwWQAiA", "priority": 5, "price_usd": 0.002},
]

# MCP常駐型アクター（通常runだとTIMED-OUTになるため起動除外）
MCP_RESIDENT_SUFFIX = "-mcp"
MCP_RESIDENT_IDS = {"57SNehd4cHNFyUCj3", "RdCHlXHphoLsWnyhh", "0eeiFH0nLqlWVoOAc", "xUYsD13SVHHRFQS1H", "BxstMzzxh8jq6UtfS"}

# 起動間隔（同一アクターの連続起動防止用）
# 2026-10-04 t_ab4e4024: 24hに固定（週1cron実行対応。72hだと隔週実行になるため）
MIN_INTERVAL_HOURS = 24

# 実行タイムアウト上書き
RETRY_TIMEOUT_OVERRIDES = {
    "57SNehd4cHNFyUCj3": 7200,  # japan-market-mcp
    "RdCHlXHphoLsWnyhh": 600,   # japan-fuel-price-mcp
}

# === ユーティリティ ===

def get_token() -> str:
    return APIFY_TOKEN

def get(path: str, token: str | None = None) -> dict | list:
    t = token or get_token()
    sep = "&" if "?" in path else "?"
    url = f"{API_BASE}{path}{sep}token={t}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def post(path: str, payload: dict, token: str | None = None) -> dict:
    t = token or get_token()
    sep = "&" if "?" in path else "?"
    url = f"{API_BASE}{path}{sep}token={t}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_owner(token: str | None = None) -> str:
    resp = get("/users/me", token)
    return (resp.get("data") or {}).get("id", "")

def resolve_actor_id(actual_name: str, fallback_id: str, token: str | None = None) -> str:
    """実API名から actor_id を /acts から解決。失敗時はフォールバック id を使用。"""
    try:
        resp = get("/acts?my=true&limit=200", token)
        items = resp.get("data", {}).get("items", [])
        for it in items:
            if it.get("name") == actual_name:
                return it.get("id") or fallback_id
    except Exception:
        pass
    return fallback_id

def is_resident_mcp(name: str, actor_id: str = "") -> bool:
    return name.endswith(MCP_RESIDENT_SUFFIX) or actor_id in MCP_RESIDENT_IDS

def load_ppe_prices() -> dict[str, float]:
    """pay_per_event.json の actors_ppe（実API名 → 単価）を読み込む。"""
    if not os.path.exists(APIFY_PPE_FILE):
        return {}
    try:
        with open(APIFY_PPE_FILE, encoding="utf-8") as f:
            return dict(json.load(f).get("actors_ppe") or {})
    except Exception:
        return {}

def load_state() -> dict[str, Any]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)

def should_trigger(state: dict[str, Any], actor_id: str) -> bool:
    """同一アクターの前回起動から MIN_INTERVAL_HOURS 経過しているか判定。"""
    last = state.get("last_trigger", {}).get(actor_id)
    if not last:
        return True
    try:
        ts = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if datetime.now(UTC) - ts > timedelta(hours=MIN_INTERVAL_HOURS):
            return True
    except ValueError:
        return True
    return False

def record_trigger(state: dict[str, Any], actor_id: str) -> None:
    state.setdefault("last_trigger", {})[actor_id] = datetime.now(UTC).isoformat()

# === メイン処理 ===

def trigger_actor_run(
    actual_name: str,
    actor_id: str,
    price_usd: float,
    token: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """1アクター分のrunをキューイング。"""
    result = {
        "actual_name": actual_name,
        "actor_id": actor_id,
        "price_usd": price_usd,
        "triggered": False,
        "run_id": None,
        "status": None,
        "error": None,
    }
    
    if dry_run:
        result["triggered"] = True
        result["run_id"] = "DRY-RUN"
        return result
    
    try:
        timeout_secs = RETRY_TIMEOUT_OVERRIDES.get(actor_id)
        payload = {"waitForFinish": 0}
        if timeout_secs is not None:
            payload["timeoutSecs"] = timeout_secs
        
        resp = post(f"/acts/{actor_id}/runs", payload, token)
        body = resp.get("data", resp) if isinstance(resp, dict) else {}
        run_id = str(body.get("id") or "?")
        status = str(body.get("status", "")).lower()
        
        # クォータ枯渇チェック
        if run_id == "?" and status in ("quota-exceeded", "paused"):
            result["error"] = f"quota state={status}"
            return result
        
        result["triggered"] = True
        result["run_id"] = run_id
        result["status"] = status or body.get("status", "QUEUED")
        
    except urllib.error.HTTPError as e:
        if e.code == 402:
            result["error"] = "HTTP 402 quota exceeded"
        else:
            result["error"] = f"HTTP {e.code}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    
    return result

def attach_to_daily(results: list[dict[str, Any]]) -> bool:
    """revenue-daily.json の最新エントリに `apify_ppe_external_runs` を追記。"""
    if not os.path.exists(REVENUE_DAILY):
        return False
    try:
        with open(REVENUE_DAILY, encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list) or not entries:
            return False
    except Exception:
        return False
    
    # 最新エントリを使用（JST基準で収集されるため UTC 今日とズレる可能性がある）
    target = entries[-1]
    
    payload = {
        "triggered_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "actors": [
            {
                "actual_name": r.get("actual_name", "?"),
                "actor_id": r.get("actor_id", "?"),
                "price_usd": r.get("price_usd", 0),
                "triggered": r.get("triggered", False),
                "run_id": r.get("run_id"),
                "status": r.get("status"),
                "error": r.get("error"),
                "skipped": r.get("skipped", False),
                "reason": r.get("reason", ""),
            }
            for r in results
        ],
        "summary": {
            "total_triggered": sum(1 for r in results if r.get("triggered")),
            "total_failed": sum(1 for r in results if r.get("error")),
            "estimated_revenue_usd": sum(r.get("price_usd", 0) for r in results if r.get("triggered") and not r.get("error")),
        },
    }
    
    target["apify_ppe_external_runs"] = payload
    
    try:
        with open(REVENUE_DAILY, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apify PPE 外部run自動起動")
    parser.add_argument("--top", type=int, default=0, help="上位N件のみ実行（0=全件）")
    parser.add_argument("--priority", type=int, default=0, help="優先度N以下のみ（1=最高）")
    parser.add_argument("--actor", type=str, help="指定actorのみ（actual_nameまたはactor_id）")
    parser.add_argument("--dry-run", action="store_true", help="記録・実行なしで表示のみ")
    parser.add_argument("--force", action="store_true", help="間隔チェックを無視して強制実行")
    args = parser.parse_args(argv)
    
    token = get_token()
    if not token and not args.dry_run:
        # トーキン未設定は失敗扱いせずスキップ（=v162 方針: 設定待機状態を壊さない）
        print("TOKEN_NOT_SET: APIFY_TOKEN 未設定のため外部run起動をスキップします")
        return 0

    owner = fetch_owner(token) if token else ""
    if owner:
        print(f"[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}] Apify PPE external runner start — owner={owner}")
    else:
        print(f"[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}] Apify PPE external runner start — dry-run (no token)")

    # 価格情報読み込み
    prices = load_ppe_prices()
    
    # 対象アクター決定
    targets = PRIORITY_ACTORS
    if args.actor:
        targets = [t for t in targets if args.actor in (t["actual_name"], t["fallback_id"])]
    if args.priority:
        targets = [t for t in targets if t["priority"] <= args.priority]
    if args.top:
        targets = targets[:args.top]
    
    # 間隔チェック用state
    state = load_state()
    
    results = []
    triggered_count = 0
    failed_count = 0
    
    for t in targets:
        actual_name = t["actual_name"]
        fallback_id = t["fallback_id"]
        price_usd = t.get("price_usd", prices.get(actual_name, 0))
        
        actor_id = resolve_actor_id(actual_name, fallback_id, token)
        
        # MCP常駐型はスキップ
        if is_resident_mcp(actual_name, actor_id):
            print(f"  [SKIP] {actual_name}: MCP resident (no auto-trigger)")
            results.append({
                "actual_name": actual_name,
                "actor_id": actor_id,
                "price_usd": price_usd,
                "triggered": False,
                "skipped": True,
                "reason": "MCP resident",
            })
            continue
        
        # 間隔チェック
        if not args.force and not should_trigger(state, actor_id):
            print(f"  [SKIP] {actual_name}: interval < {MIN_INTERVAL_HOURS}h")
            results.append({
                "actual_name": actual_name,
                "actor_id": actor_id,
                "price_usd": price_usd,
                "triggered": False,
                "skipped": True,
                "reason": "interval",
            })
            continue
        
        # 起動実行
        result = trigger_actor_run(actual_name, actor_id, price_usd, token, args.dry_run)
        results.append(result)
        
        if result["triggered"] and not result["error"]:
            triggered_count += 1
            print(f"  [TRIGGERED] {actual_name}: run={result['run_id'][:8]} status={result['status']} price=${price_usd}")
            record_trigger(state, actor_id)
        elif result["error"]:
            failed_count += 1
            print(f"  [FAILED] {actual_name}: {result['error']}")
        else:
            print(f"  [SKIPPED] {actual_name}: {result.get('reason', 'unknown')}")
    
    # 保存
    if not args.dry_run:
        save_state(state)
        print(f"✓ state 保存: {STATE_FILE}")
        
        wrote = attach_to_daily(results)
        if wrote:
            print(f"✓ revenue-daily.json に apify_ppe_external_runs 追記")
        else:
            print("⚠ 当日エントリが revenue-daily.json に無いため metric 未追記（state は保存済み）", file=sys.stderr)
    
    # サマリー
    total_price = sum(r.get("price_usd", 0) for r in results if r.get("triggered") and not r.get("error"))
    print(f"\n=== Apify PPE External Runner Summary ===")
    print(f"Targeted: {len(targets)} | Triggered: {triggered_count} | Failed: {failed_count} | Skipped: {len([r for r in results if r.get('skipped')])}")
    print(f"Estimated revenue (if all succeed): ${total_price:.4f}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())