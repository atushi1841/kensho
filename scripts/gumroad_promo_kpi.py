#!/usr/bin/env python3
"""scripts/gumroad_promo_kpi.py — t_3848cbde Gumroad 販促KPI日次評価.

成功指標を毎日自動判定する:
  - 売上: Gumroad API /v2/sales（成功指標「1件以上/週」= 直近7日件数）
  - 訪問: data/gumroad_views_history.json（gumroad_views_collect.js 収集）から
          前日比 +%（成功指標「前日比+20%」）
  - 効果: Referrer の Twitter 経由 views（週次X販促の直接効果）

失敗時代替案（カード記載）: API 応答なし場合は data/gumroad_state.json（既存CDP
ダッシュボード収集・kensho_revenue_collect.py 経路）へフォールバックし、
sale 判定をダッシュボード値で行う。

出力:
  - stdout: 1行サマリ + 詳細
  - data/gumroad_promo_kpi_state.json: 直近評価結果（履歴は直近60件）
  - logs/gumroad_promo_kpi.log: 追記

使い方:
  python scripts/gumroad_promo_kpi.py           # API優先・失敗時ダッシュボードFP
  python scripts/gumroad_promo_kpi.py --strict  # API失敗を exit 1 にする
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data"
VIEWS_HISTORY = DATA_DIR / "gumroad_views_history.json"
DASHBOARD_STATE = DATA_DIR / "gumroad_state.json"
KPI_STATE = DATA_DIR / "gumroad_promo_kpi_state.json"
KPI_LOG = REPO / "logs" / "gumroad_promo_kpi.log"

GUMROAD_API = "https://api.gumroad.com/v2"
WEEKLY_SALES_TARGET = 1  # 成功指標: 1件以上/週
VIEW_GROWTH_TARGET_PCT = 20.0  # 成功指標: 訪問 前日比+20%


def load_env_token() -> str:
    """.env から GUMROAD_TOKEN を読む（環境変数優先）。"""
    tok = os.environ.get("GUMROAD_TOKEN", "")
    if tok:
        return tok
    env_file = REPO / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GUMROAD_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def api_sales_count(token: str, timeout: int = 30) -> dict[str, Any]:
    """API で全商品の売上件数を取得。{ok, sales, error}。

    /v2/sales は商品ID無指定で全売上を返す（実測 2026-09-26: success:true）。
    """
    if not token:
        return {"ok": False, "error": "GUMROAD_TOKEN empty"}
    req = urllib.request.Request(
        f"{GUMROAD_API}/sales",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}
    if not data.get("success"):
        return {"ok": False, "error": f"api success=false: {str(data)[:150]}"}
    sales = data.get("sales") or []
    # 直近7日件数（created_at が ISO のみ比較可能な場合は全件を週次件数扱いにしない）
    cutoff = (datetime.now().astimezone() - timedelta(days=7)).timestamp()
    week = 0
    for s in sales:
        created = s.get("created_at")
        try:
            ts = datetime.fromisoformat(str(created)).timestamp()
        except (TypeError, ValueError):
            ts = None
        if ts is None or ts >= cutoff:
            week += 1
    return {"ok": True, "total": len(sales), "week": week}


def dashboard_sales_fallback() -> dict[str, Any]:
    """失敗時代替案: 既存CDPダッシュボード収集 data/gumroad_state.json で判定。"""
    if not DASHBOARD_STATE.exists():
        return {"ok": False, "error": "gumroad_state.json なし"}
    try:
        st = json.loads(DASHBOARD_STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"ok": False, "error": f"state read: {e}"}
    return {
        "ok": True,
        "source": "dashboard_fallback",
        "login_ok": st.get("login_ok"),
        "last_success_at": st.get("last_success_at"),
        "total_sales": st.get("total_sales"),
        "last_7_days_usd": st.get("last_7_days_usd"),
    }


def load_views_history() -> dict[str, Any]:
    if VIEWS_HISTORY.exists():
        try:
            data = json.loads(VIEWS_HISTORY.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _is_twitter_referrer(src: str) -> bool:
    """Twitter 経由 referrer か的大文字小文字を区別しない柔軟判定（t_b8ec048a）。

    Gumroad referrer 表のキーは X ブラウザ経由で 'twitter.com'/'t.co' 等に
    正規化されるが、キー破損（例: 'Direct, email, IM' のみ）や表示形式の違いで
    'Twitter' 自体が存在しない場合がある。その場合は utm_source=tw / utm_source=twitter を
    探す（X 販促投稿が utm 付与済みなら検出可能）。
    """
    s = (src or "").lower()
    return any(k in s for k in ("twitter", "t.co", "x.com", "utm_source=tw", "utm_source=twitter"))


def _utm_twitter_views(referrers: dict[str, Any]) -> int:
    """utm_source=twitter を含む referrer の合計 views（t_b8ec048a）。

    X 販促投稿が utm 付与済みなら、referrer キーが 'Twitter' でなくても
    utm_source=twitter を含むキー（例: 'https://t.co/...?utm_source=twitter'）
    から検出できる。X 販促経由流入を utm 計測経路で独立判定するための別指標。
    """
    total = 0
    for src, v in (referrers or {}).items():
        if _is_twitter_referrer(src) and isinstance(v, (int, float)):
            total += int(v)
    return total


def views_dod(history: dict[str, Any], today: date) -> dict[str, Any]:
    """前日比 (dod) を計算。{prev_date, prev_views, date, views, pct, meets_target}。

    前日データ欠損時は pct=None（判定不能 = not met ではなく unknown）。

    twitter_views: referrers から Twitter 経由 views を集計。キーが 'Twitter'
    でなくても t.co/twitter.com/utm_source=twitter を柔軟検出する（t_b8ec048a）。
    検出不能な場合は None ではなく 0 を返す（X 販促経由流入=0 の明示的記録）。
    """
    cur_key = today.isoformat()
    prev_key = (today - timedelta(days=1)).isoformat()
    cur = history.get(cur_key) or {}
    prev = history.get(prev_key) or {}
    cv, pv = cur.get("views"), prev.get("views")
    referrers = cur.get("referrers") or {}
    out: dict[str, Any] = {
        "date": cur_key, "views": cv,
        "prev_date": prev_key, "prev_views": pv,
        "pct": None, "meets_target": None,
        "twitter_views": _utm_twitter_views(referrers),
        "twitter_referrers": [k for k in referrers if _is_twitter_referrer(k)],
    }
    if isinstance(cv, int) and isinstance(pv, int):
        if pv > 0:
            pct = (cv - pv) / pv * 100.0
            out["pct"] = round(pct, 1)
            out["meets_target"] = pct >= VIEW_GROWTH_TARGET_PCT
        else:
            # 0→1以上は無限増加。+∞ として達成扱い（0→0 は横ばい=未達）
            out["pct"] = None if cv == 0 else float("inf")
            out["meets_target"] = cv > 0
    return out


def evaluate(sales: dict[str, Any], views: dict[str, Any]) -> dict[str, Any]:
    """2つの成功指標を判定。"""
    week_count = sales.get("week") if sales.get("ok") else None
    sales_met = None if week_count is None else week_count >= WEEKLY_SALES_TARGET
    return {
        "sales_week_count": week_count,
        "sales_meets_target": sales_met,
        "sales_target": f">={WEEKLY_SALES_TARGET}/week",
        "views": views,
        "views_meets_target": views.get("meets_target"),
        "views_target": f"prev-day +{VIEW_GROWTH_TARGET_PCT:.0f}%",
    }


def save_kpi_state(result: dict[str, Any]) -> None:
    hist: list[Any] = []
    if KPI_STATE.exists():
        try:
            old = json.loads(KPI_STATE.read_text(encoding="utf-8"))
            hist = old.get("history", [])
        except (json.JSONDecodeError, OSError):
            hist = []
    hist.append({k: result.get(k) for k in ("date", "summary", "sales", "views", "eval")})
    KPI_STATE.write_text(
        json.dumps({**result, "history": hist[-60:]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Gumroad 販促KPI日次評価")
    ap.add_argument("--strict", action="store_true", help="API失敗時に exit 1")
    ap.add_argument("--date", default="", help="基準日 YYYY-MM-DD（省略=今日）")
    args = ap.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    token = load_env_token()

    sales = api_sales_count(token)
    sales_source = "api"
    if not sales.get("ok"):
        fb = dashboard_sales_fallback()
        if fb.get("ok"):
            sales = {"ok": True, "source": "dashboard_fallback", "total": fb.get("total_sales"),
                     "week": None, "fallback_reason": sales.get("error"), **fb}
            sales_source = "dashboard_fallback"
        else:
            sales_source = "failed"

    views = views_dod(load_views_history(), today)
    ev = evaluate(sales, views)

    def log(msg: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        KPI_LOG.parent.mkdir(exist_ok=True)
        with open(KPI_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    result = {
        "date": today.isoformat(),
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "sales": sales,
        "sales_source": sales_source,
        "views": views,
        "eval": ev,
        "summary": "",
    }
    parts = [
        f"sales_source={sales_source}",
        f"sales_week={ev['sales_week_count']}",
        f"sales_met={ev['sales_meets_target']}",
        f"views={views.get('views')}(prev={views.get('prev_views')})",
        f"dod={views.get('pct')}%",
        f"views_met={ev['views_meets_target']}",
        f"twitter_views={views.get('twitter_views')}",
    ]
    result["summary"] = " ".join(parts)
    log(f"KPI {result['summary']}")

    save_kpi_state(result)

    if not sales.get("ok") and args.strict:
        sys.exit(1)
    if sales_source == "failed" and args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
