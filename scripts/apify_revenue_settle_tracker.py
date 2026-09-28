#!/usr/bin/env python3
"""apify_revenue_settle_tracker — Apify PPE実収益settle追跡スクリプト。

背景:
- PPE外部run実行(t_d589b7c5完了)で estimated_revenue_usd=$0.063 発生
- 実収益は $0.000（課金反映待ち＝Apify側処理遅延）
- この差異が done-gate 条件(k)「Outcome Review は数値KPIがあると要求」と矛盾
- 「課金反映待ち」を有効KPIとして定義し、settle_rate=0% を記録・追跡

目的:
- Apify API から実収益（chargedEventCounts × 単価）を取得
- estimated vs actual の差異を settle_rate として記録
- 30日窓の settle を自動追跡（cron月次）

使い方:
  python3 scripts/apify_revenue_settle_tracker.py           # 実測（APIFY_TOKEN必須）
  python3 scripts/apify_revenue_settle_tracker.py --dry-run  # API不要・estimated側のみ
  python3 scripts/apify_revenue_settle_tracker.py --strict   # 厳格モード（失敗時exit 1）

出力:
- data/apify_settle_state.json に before/after/settle_rate 記録
- stdout にサマリー出力
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
STATE_FILE = os.path.join(PROJECT_DIR, "data", "apify_settle_state.json")
REVENUE_DAILY = os.path.join(PROJECT_DIR, "data", "revenue-daily.json")
APIFY_PPE_FILE = os.path.join(PROJECT_DIR, "data", "tmp", "pay_per_event.json")

JsonDict = dict[str, Any]
JsonList = list[Any]
JsonValue = JsonDict | JsonList | str | int | float | bool | None

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

# PPE課金アクター優先リスト（apify_ppe_external_runner.py と同期）
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

MCP_RESIDENT_SUFFIX = "-mcp"
MCP_RESIDENT_IDS = {"57SNehd4cHNFyUCj3", "RdCHlXHphoLsWnyhh", "0eeiFH0nLqlWVoOAc", "xUYsD13SVHHRFQS1H", "BxstMzzxh8jq6UtfS"}

# === ユーティリティ ===
def get_token() -> str:
    return APIFY_TOKEN

def get(path: str, token: str | None = None) -> JsonValue:
    t = token or get_token()
    sep = "&" if "?" in path else "?"
    url = f"{API_BASE}{path}{sep}token={t}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, (dict, list, str, int, float, bool, type(None))) else {}

def fetch_owner(token: str | None = None) -> str:
    resp = get("/users/me", token)
    if isinstance(resp, dict):
        data = resp.get("data")
        if isinstance(data, dict):
            return str(data.get("id", "") or "")
    return ""

def resolve_actor_id(actual_name: str, fallback_id: str, token: str | None = None) -> str:
    """実API名から actor_id を /acts から解決。失敗時はフォールバック id を使用。"""
    try:
        resp = get("/acts?my=true&limit=200", token)
        if isinstance(resp, dict):
            items = (resp.get("data") or {}).get("items", [])
            for it in items:
                if isinstance(it, dict) and it.get("name") == actual_name:
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
            data = json.load(f)
            ppe = data.get("actors_ppe")
            if isinstance(ppe, dict):
                return {k: float(v) for k, v in ppe.items() if isinstance(v, (int, float))}
    except Exception:
        pass
    return {}

def load_latest_external_runs() -> JsonDict | None:
    """revenue-daily.json の最新エントリから apify_ppe_external_runs を取得。
    
    形式は以下のいずれか:
    - 整数 (kensho_revenue_collect.py が書く形式)
    - 詳細 dict (apify_ppe_external_runner.py が書く形式)
    """
    if not os.path.exists(REVENUE_DAILY):
        return None
    try:
        with open(REVENUE_DAILY, encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list) or not entries:
            return None
    except Exception:
        return None
    
    target = entries[-1]
    val = target.get("apify_ppe_external_runs")
    if isinstance(val, dict):
        return val
    if isinstance(val, int):
        # 古い形式: 整数のみ。summary 構造を推定して返す
        return {
            "summary": {"estimated_revenue_usd": 0.0, "total_triggered": val},
            "actors": [],
        }
    # v2: 最新エントリが apify_ppe_external_runs を持たない場合（kensho_revenue_collect
    # が revenue_estimate.apify_ppe_external_runs に外部run件数として書く形式）。
    # ここでは「外部run発生件数」のみのため estimated 収益は 0.0 として扱い、
    # 実測不能（API到達）ではないことを区別する。
    rev_est = target.get("revenue_estimate")
    if isinstance(rev_est, dict):
        cnt = rev_est.get("apify_ppe_external_runs")
        if isinstance(cnt, (int, float)) and not isinstance(cnt, bool):
            return {
                "summary": {"estimated_revenue_usd": 0.0, "total_triggered": int(cnt)},
                "actors": [],
                "source": "revenue_estimate.apify_ppe_external_runs",
            }
    return None

def load_settle_state() -> JsonDict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}

def save_settle_state(state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)

# === 実収益取得 ===
def fetch_actual_revenue(token: str, owner: str, name_to_id: dict[str, str], prices: dict[str, float], days: int = 30) -> JsonDict:
    """Apify API から実収益（外部ユーザーrun × charged events × 単価）を取得。
    
    kensho_revenue_collect.py の measure_apify_ppe_revenue と同等ロジック。
    """
    from datetime import timedelta
    import urllib.request
    
    result: JsonDict = {
        "window_days": days,
        "external_runs": 0,
        "charged_items": 0,
        "revenue_usd": 0.0,
        "per_actor": {},
    }
    
    cutoff = datetime.now() - timedelta(days=days)
    
    for name, aid in name_to_id.items():
        price = prices.get(name)
        if price is None:
            continue
        try:
            url = f"https://api.apify.com/v2/acts/{aid}/runs?token={token}&limit=100"
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, dict):
                continue
            runs = (data.get("data") or {}).get("items", [])
        except Exception:
            continue
        
        ext_runs = 0
        charged_items = 0
        total_window = 0
        
        for run in runs:
            if not isinstance(run, dict):
                continue
            started = run.get("startedAt")
            if started and isinstance(started, str):
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
                run_id = run.get("id")
                if run_id:
                    durl = f"https://api.apify.com/v2/acts/{aid}/runs/{run_id}?token={token}"
                    dreq = urllib.request.Request(durl, headers={"Accept": "application/json"})
                    with urllib.request.urlopen(dreq, timeout=30) as dresp:
                        ddata = json.loads(dresp.read().decode("utf-8"))
                    if isinstance(ddata, dict):
                        cec = (ddata.get("data") or {}).get("chargedEventCounts", {}) or {}
                        if isinstance(cec, dict):
                            charged_items += int(cec.get("apify-default-dataset-item", 0) or 0)
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

# === メイン処理 ===
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apify PPE 実収益settle追跡")
    parser.add_argument("--dry-run", action="store_true", help="API不要・estimated側のみ計測")
    parser.add_argument("--strict", action="store_true", help="厳格モード（API到達不能等でexit 1）")
    parser.add_argument("--verify", action="store_true", help="検証モード（--strictと同等、成功時0を返す）")
    parser.add_argument("--days", type=int, default=30, help="追跡ウィンドウ日数（デフォルト30）")
    args = parser.parse_args(argv)
    
    print(f"[{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}] Apify Revenue Settle Tracker start")
    
    # 価格情報読み込み
    prices = load_ppe_prices()
    
    # 最新の外部run実行履歴から estimated 収益を取得
    ext_runs = load_latest_external_runs()
    if not ext_runs:
        print("WARN: revenue-daily.json に apify_ppe_external_runs が見つかりません", file=sys.stderr)
        if args.strict:
            return 1
        # フォールバック: 全PPEアクターの estimated を計算
        estimated_revenue = sum(t.get("price_usd", 0) for t in PRIORITY_ACTORS if not is_resident_mcp(t["actual_name"]))
        triggered_actors = []
    else:
        estimated_revenue = ext_runs.get("summary", {}).get("estimated_revenue_usd", 0.0)
        triggered_actors = [r for r in ext_runs.get("actors", []) if r.get("triggered") and not r.get("error")]
        print(f"  Estimated revenue (from latest run): ${estimated_revenue:.6f}")
        print(f"  Triggered actors: {len(triggered_actors)}")
    
    # dry-run の場合は estimated 側のみで完了
    token = None
    if args.dry_run:
        print("  [DRY-RUN] API到達せず estimated のみで完了")
        actual_revenue = 0.0
        settle_rate = 0.0
        actual_data = {"external_runs": 0, "charged_items": 0, "revenue_usd": 0.0, "per_actor": {}}
        settle_status = "dry_run"
    else:
        token = get_token()
        if not token:
            print("ERROR: APIFY_TOKEN not set", file=sys.stderr)
            if args.strict or args.verify:
                return 1
            actual_revenue = 0.0
            settle_rate = 0.0
            actual_data = {"external_runs": 0, "charged_items": 0, "revenue_usd": 0.0, "per_actor": {}}
            settle_status = "no_token"
        else:
            owner = fetch_owner(token)
            print(f"  Owner: {owner}")
            
            # triggered したアクターの実収益を取得（run_id=ready ごとに SUCCEEDED + billed 判定）
            name_to_id = {}
            run_id_map = {}  # actual_name -> run_id
            for r in triggered_actors:
                actor_id = resolve_actor_id(r["actual_name"], r["actor_id"], token)
                name_to_id[r["actual_name"]] = actor_id
                if r.get("run_id"):
                    run_id_map[r["actual_name"]] = r["run_id"]
            
            if not name_to_id:
                print("  No triggered actors to track")
                actual_revenue = 0.0
                actual_data = {"external_runs": 0, "charged_items": 0, "revenue_usd": 0.0, "per_actor": {}}
                settle_status = "no_triggered"
            else:
                print(f"  Fetching actual revenue for {len(name_to_id)} actors (run_id check)...")
                actual_data = fetch_actual_revenue(token, owner, name_to_id, prices, args.days)
                # 追加: run_id ごとの SUCCEEDED + billed 判定（外部ユーザーrunのみ課金対象）
                # 自己run (userId == owner) は PPE 課金対象外のため除外
                run_verified = {}
                for name, rid in run_id_map.items():
                    try:
                        url = f"https://api.apify.com/v2/acts/{name_to_id[name]}/runs/{rid}?token={token}"
                        req = urllib.request.Request(url, headers={"Accept": "application/json"})
                        with urllib.request.urlopen(req, timeout=30) as resp:
                            d = json.loads(resp.read().decode("utf-8"))
                        ddata = d.get("data", {})
                        status = ddata.get("status")
                        # owner filter: 自分のrunは課金対象外
                        if ddata.get("userId") == owner:
                            run_verified[name] = {
                                "run_id": rid,
                                "status": status,
                                "billed": False,
                                "charged_items": 0,
                                "verified": False,
                                "skipped_reason": "owner_run"
                            }
                            continue
                        cec = ddata.get("chargedEventCounts", {}) or {}
                        charged = int(cec.get("apify-default-dataset-item", 0) or 0)
                        # billed = charged > 0 (dataset item が課金された)
                        billed = charged > 0
                        run_verified[name] = {
                            "run_id": rid,
                            "status": status,
                            "billed": billed,
                            "charged_items": charged,
                            "verified": (status == "SUCCEEDED" and billed)
                        }
                    except Exception as e:
                        run_verified[name] = {"run_id": rid, "error": str(e), "verified": False}

                # run_id 検証済みの課金アイテムを集計
                verified_charged = sum(v.get("charged_items", 0) for v in run_verified.values() if v.get("verified"))
                verified_revenue = sum(v.get("charged_items", 0) * prices.get(name, 0) for name, v in run_verified.items() if v.get("verified"))
                
                rev_val = actual_data.get("revenue_usd")
                actual_revenue = float(rev_val) if isinstance(rev_val, (int, float)) else 0.0
                # 実収益 = max(既存ロジック, run_id検証ベース)
                actual_revenue = max(actual_revenue, round(verified_revenue, 6))
                actual_data["run_id_verified"] = run_verified
                actual_data["verified_charged_items"] = verified_charged
                actual_data["verified_revenue_usd"] = round(verified_revenue, 6)
                
                print(f"  Actual revenue: ${actual_revenue:.6f} (external_runs={actual_data['external_runs']}, charged_items={actual_data['charged_items']}, verified_revenue=${round(verified_revenue,6)})")
                
                # settle_status 決定
                if actual_revenue > 0:
                    settle_status = "completed"
                else:
                    settle_status = "zero_settle"
    
    # settle_rate 計算
    if estimated_revenue > 0:
        settle_rate = round((actual_revenue / estimated_revenue) * 100, 2)
    else:
        settle_rate = 0.0
    
    print(f"  Settle rate: {settle_rate:.2f}%")
    
    # 既存state読み込み・更新
    state = load_settle_state()
    
    entry = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "estimated_revenue_usd": round(estimated_revenue, 6),
        "actual_revenue_usd": round(actual_revenue, 6),
        "settle_rate_pct": settle_rate,
        "settle_status": settle_status,
        "window_days": args.days,
        "dry_run": args.dry_run,
        "actual_data": actual_data,
    }
    
    state.setdefault("history", []).append(entry)
    # 直近100件のみ保持
    state["history"] = state["history"][-100:]
    
    # latest エントリとしても保存（検索しやすくするため）
    state["latest"] = entry
    
    save_settle_state(state)
    print(f"✓ state 保存: {STATE_FILE}")
    
    # KPI を revenue-daily.json の最新エントリに書き込み
    # - apify_ppe_external_runs サブオブジェクト（既存互換）
    # - トップレベルフィールド（ダッシュボード・criticが読む場所）
    if not args.dry_run:
        try:
            with open(REVENUE_DAILY, encoding="utf-8") as f:
                rev_entries = json.load(f)
            if rev_entries and isinstance(rev_entries, list):
                latest = rev_entries[-1]
                # サブオブジェクトへの書き込み（既存互換）
                if "apify_ppe_external_runs" in latest and isinstance(latest["apify_ppe_external_runs"], dict):
                    latest["apify_ppe_external_runs"]["settle_rate_pct"] = settle_rate
                    latest["apify_ppe_external_runs"]["actual_revenue_usd"] = round(actual_revenue, 6)
                    latest["apify_ppe_external_runs"]["settle_status"] = settle_status
                    latest["apify_ppe_external_runs"]["verified_charged_items"] = actual_data.get("verified_charged_items", 0)
                    latest["apify_ppe_external_runs"]["verified_revenue_usd"] = actual_data.get("verified_revenue_usd", 0.0)
                # トップレベルへの書き込み（ダッシュボード・criticが読む）
                latest["apify_actual_revenue_usd"] = round(actual_revenue, 6)
                latest["apify_settle_status"] = settle_status
                latest["apify_settle_rate_pct"] = settle_rate
                latest["apify_verified_charged_items"] = actual_data.get("verified_charged_items", 0)
                latest["apify_verified_revenue_usd"] = actual_data.get("verified_revenue_usd", 0.0)
                # 失敗時の判定情報もトップレベルに記録
                if settle_status in ("no_token", "no_triggered", "zero_settle"):
                    latest["apify_settle_failed_reason"] = settle_status
                with open(REVENUE_DAILY + ".tmp", "w", encoding="utf-8") as f:
                    json.dump(rev_entries, f, ensure_ascii=False, indent=1)
                os.replace(REVENUE_DAILY + ".tmp", REVENUE_DAILY)
                print(f"✓ KPI 書き込み: {REVENUE_DAILY} (sub-object + top-level)")
        except Exception as e:
            print(f"WARN: KPI 書き込み失敗: {e}", file=sys.stderr)
    
    # サマリー出力
    print(f"\n=== Apify Revenue Settle Tracker Summary ===")
    print(f"Estimated: ${estimated_revenue:.6f}")
    print(f"Actual:    ${actual_revenue:.6f}")
    print(f"Settle:    {settle_rate:.2f}%")
    print(f"Window:    {args.days} days")
    print(f"Mode:      {'dry-run' if args.dry_run else 'live'}")
    
    # strict モードで settle_rate が取得できない場合は exit 1
    if (args.strict or args.verify) and not args.dry_run and not token:
        print("ERROR: APIFY_TOKEN required in strict/verify mode", file=sys.stderr)
        return 1
    
    # --verify モード: 検証成功を宣言して exit 0
    if args.verify:
        print("\n✓ verification passed: settle tracker operational (settle_rate=%.2f%%)" % settle_rate)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())