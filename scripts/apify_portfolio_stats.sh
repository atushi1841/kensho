#!/usr/bin/env bash
# apify_portfolio_stats.sh — Apify ポートフォリオ全アクターの日次統計（repo正本 / profile へ同期して cron が実行）
#
# 出力: /mnt/d/Project2/apify-portfolio-stats.json（日次追記・直近30件）
# 消費者: scripts/kensho_revenue_collect.py (APIFY_STATS / collect_apify) / scripts/apify_seo_effect.py
#
# t_7630a248 (2026-09-25) の修正内容 — 14日間の偽ゼロ（9/12〜9/25 全アクター users/runs=0）の根絶:
#   (1) 認証: 旧版は `-H "Authorization: Bearer ***"` というリテラルを送って全アクター HTTP 401 となり、
#       それでも 0 を追記して "OK appended" を出していた（偽成功）。実トークンを Bearer で送る。
#   (2) 列挙: 旧版は 25 本の固定配列。ポートフォリオは 82 本に成長しており 57 本(70%)が集計外だった。
#       ライブ API `GET /v2/acts?my=true` から動的列挙する（ALIASES で既存25本の短縮キーは後方互換維持）。
#   (3) 失敗契約: トークン/API 死・全件失敗なら **追記せず exit 1**。部分失敗は追記＋api_errors/partial で
#       exit 2（cron が error として可視化）。401 を 0 として記録する経路を構造的に消す。
#   (4) external 集計: ヘルパー apify_portfolio_runs.py の未定義関数 `_apify_token()` による例外→無言0 を
#       やめ、本スクリプト内で runs を直接ページング集計（runs=0 のアクターは API を叩かない）。
#
# 終了コード: 0=全件成功 / 1=致命的（追記なし） / 2=部分失敗（追記あり・partial マーカー）
#
# テスト用環境変数: APIFY_STATS_OUT / APIFY_TOKEN / APIFY_STATS_DATE / APIFY_EXTERNAL_DAYS /
#                  APIFY_SELF_ID / APIFY_STATS_MAX_ACTORS / APIFY_TOKEN_ENV_FILE
set -uo pipefail

OUT="${APIFY_STATS_OUT:-/mnt/d/Project2/apify-portfolio-stats.json}"
ENV_FILE="${APIFY_TOKEN_ENV_FILE:-/mnt/d/Project2/kensho/.env}"

# D:ドライブマウント待機（既定 OUT を使う cron 実行時のみ）
if [ "$OUT" = "/mnt/d/Project2/apify-portfolio-stats.json" ]; then
  for _i in $(seq 1 30); do
    if [ -d /mnt/d/Project2 ]; then break; fi
    sleep 10
  done
  [ -d /mnt/d/Project2 ] || { echo "[FAIL] D:ドライブ未マウント — 追記せず終了"; exit 1; }
fi

# トークン解決: 環境変数 → .env の APIFY_TOKEN_DEFAULT（表示層でマスクしないこと）
TOKEN="${APIFY_TOKEN:-}"
if [ -z "$TOKEN" ] && [ -f "$ENV_FILE" ]; then
  TOKEN="$(grep -m1 '^APIFY_TOKEN_DEFAULT=' "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d '\r\n')"
fi
if [ -z "$TOKEN" ]; then
  echo "[FAIL] APIFY_TOKEN 未設定（env も $ENV_FILE も空）— 追記せず終了"
  exit 1
fi

export APIFY_TOKEN="$TOKEN"
export APIFY_STATS_OUT="$OUT"
export APIFY_EXTERNAL_DAYS="${APIFY_EXTERNAL_DAYS:-30}"
export APIFY_SELF_ID="${APIFY_SELF_ID:-VMz6nlpHoGIjTeSXS}"
export APIFY_STATS_MAX_ACTORS="${APIFY_STATS_MAX_ACTORS:-0}"
export APIFY_STATS_DATE="${APIFY_STATS_DATE:-$(date +%Y-%m-%d)}"

python3 - <<'PY'
"""Apify ポートフォリオ統計の収集本体（t_7630a248）。"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.apify.com/v2"
TOKEN = os.environ["APIFY_TOKEN"]
OUT = os.environ["APIFY_STATS_OUT"]
DAYS = int(os.environ.get("APIFY_EXTERNAL_DAYS", "30"))
SELF = os.environ.get("APIFY_SELF_ID", "VMz6nlpHoGIjTeSXS")
MAX_ACTORS = int(os.environ.get("APIFY_STATS_MAX_ACTORS", "0") or "0")
DATE = os.environ.get("APIFY_STATS_DATE") or time.strftime("%Y-%m-%d")
PAGE = 100
MAX_PAGES = 40

# actual_name -> 既存の短縮キー（kensho_revenue_collect.PORTFOLIO_TO_ACTUAL / apify_seo_effect.py との互換）
ALIASES = {
    "japan-used-camera-market-scraper": "japan-camera-market",
    "japan-watch-market-scraper": "japan-watch-market",
    "japan-luxury-brand-market-scraper": "japan-luxury-market",
    "japan-used-instrument-market-scraper": "japan-instrument-market",
    "japan-offmall-market-scraper": "japan-offmall-market",
    "japan-market-mcp": "japan-market-mcp",
    "japan-rent-market-scraper": "japan-rent-market",
    "japan-rent-market-cn": "japan-rent-market-cn",
    "japan-rent-market-kr": "japan-rent-market-kr",
    "japan-property-market-scraper": "japan-property-market",
    "japan-property-market-cn": "japan-property-market-cn",
    "japan-property-market-kr": "japan-property-market-kr",
    "japan-kakaku-price-search": "japan-kakaku-price-search",
    "japan-kakaku-price-search-cn": "japan-kakaku-price-search-cn",
    "japan-kakaku-price-search-kr": "japan-kakaku-price-search-kr",
    "japan-camera-market-cn-scraper": "camera-cn",
    "japan-camera-market-kr-scraper": "camera-kr",
    "japan-watch-market-scraper-cn": "watch-cn",
    "japan-watch-market-scraper-kr": "watch-kr",
    "japan-luxury-brand-market-cn": "luxury-cn",
    "japan-luxury-brand-market-kr": "luxury-kr",
    "japan-used-instrument-market-cn": "instrument-cn",
    "japan-used-instrument-market-kr": "instrument-kr",
    "japan-offmall-market-cn": "offmall-cn",
    "japan-offmall-market-kr": "offmall-kr",
}

def api_get(path, retries=2, timeout=30):
    """(http_status, payload) を返す。ネットワーク失敗は status=0。"""
    url = f"{API}{path}"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.load(resp)
        except urllib.error.HTTPError as exc:
            # 401/403/404 はリトライしても無駄 → 即返す（偽ゼロを作らない）
            return exc.code, None
        except Exception:
            if attempt >= retries:
                return 0, None
            time.sleep(3.0)
    return 0, None

def _iso_ts(text):
    try:
        return time.mktime(time.strptime(str(text)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
    except Exception:
        return None

def count_external(actor_id, days):
    """直近 days 日の run をページングし (external_users, external_runs, error) を返す。"""
    cutoff = time.time() - days * 86400
    users = set()
    runs = 0
    offset = 0
    while True:
        status, payload = api_get(
            f"/acts/{actor_id}/runs?desc=1&limit={PAGE}&offset={offset}", retries=1
        )
        if status != 200 or payload is None:
            return len(users), runs, f"runs HTTP {status}"
        data = payload.get("data", {}) or {}
        items = data.get("items", []) or []
        if not items:
            break
        reached = False
        for item in items:
            ts = _iso_ts(item.get("startedAt") or "")
            if ts is not None and ts < cutoff:
                reached = True
                break
            uid = item.get("userId")
            if uid and uid != SELF:
                users.add(uid)
                runs += 1
        total = data.get("total", len(items))
        if reached or offset + len(items) >= total or (offset // PAGE) + 1 >= MAX_PAGES:
            break
        offset += len(items)
    return len(users), runs, None

def main():
    status, payload = api_get("/acts?my=true&limit=1000")
    if status != 200 or not payload:
        print(f"[FAIL] アクター一覧の取得に失敗（HTTP {status}）— 追記せず終了（偽ゼロの根絶）")
        return 1
    items = (payload.get("data", {}) or {}).get("items", []) or []
    if not items:
        print("[FAIL] アクターが 0 件（API 異常）— 追記せず終了")
        return 1
    if MAX_ACTORS > 0:
        items = items[:MAX_ACTORS]

    entry = {}
    ok = 0
    errors = 0
    ext_errors = 0
    for item in items:
        aid = str(item.get("id") or "")
        actual = str(item.get("name") or aid)
        if not aid:
            errors += 1
            continue
        status, payload = api_get(f"/acts/{aid}")
        if status != 200 or not payload:
            errors += 1
            print(f"  [WARN] {actual}: actor 取得失敗 HTTP {status}")
            continue
        stats = (payload.get("data", {}) or {}).get("stats", {}) or {}
        users = int(stats.get("totalUsers", 0) or 0)
        u30d = int(stats.get("totalUsers30Days", 0) or 0)
        runs = int(stats.get("totalRuns", 0) or 0)
        ext_users, ext_runs = 0, 0
        if runs > 0 and DAYS > 0:
            ext_users, ext_runs, err = count_external(aid, DAYS)
            if err:
                ext_errors += 1
                print(f"  [WARN] {actual}: external 集計失敗（{err}）")
        entry[ALIASES.get(actual, actual)] = {
            "users": users,
            "u30d": u30d,
            "runs": runs,
            "external_users": ext_users,
            "external_runs": ext_runs,
        }
        ok += 1

    if ok == 0:
        print("[FAIL] 全アクターの取得に失敗 — 追記せず終了（偽ゼロの根絶）")
        return 1

    ext_total = sum(v["external_users"] for v in entry.values())
    record = {"date": DATE}
    record.update(entry)
    record["external_users_total"] = ext_total
    record["api_errors"] = errors + ext_errors
    record["partial"] = bool(errors or ext_errors)

    data = []
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                data = loaded
        except Exception as exc:  # 破損ファイルは退避して継続（無言で消さない）
            print(f"  [WARN] 既存ファイル読取失敗（{type(exc).__name__}）— 新規リストで再構築")
            data = []
    data.append(record)
    data = data[-30:]

    out_dir = os.path.dirname(OUT)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    tmp = f"{OUT}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)

    users_total = sum(v["users"] for v in entry.values())
    u30d_total = sum(v["u30d"] for v in entry.values())
    runs_total = sum(v["runs"] for v in entry.values())
    print(
        f"summary date={DATE} actors={ok}/{len(items)} api_errors={record['api_errors']} "
        f"users={users_total} users30d={u30d_total} runs={runs_total} "
        f"external_users_total={ext_total} out={OUT}"
    )
    if record["partial"]:
        print(f"[PARTIAL] {record['api_errors']} 件失敗（追記は実施・要確認）")
        return 2
    print("[OK] all actors collected")
    return 0

if __name__ == "__main__":
    sys.exit(main())
PY
rc=$?
exit "$rc"
