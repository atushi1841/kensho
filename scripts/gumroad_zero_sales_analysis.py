#!/usr/bin/env python3
"""scripts/gumroad_zero_sales_analysis.py — t_2bc285ad Gumroad 零售上根本原因分析.

用法:
  python scripts/gumroad_zero_sales_analysis.py           # 完整根因分析报告
  python scripts/gumroad_zero_sales_analysis.py --verify  # 验收命令: 返回 0/1 且只打印 PASS/FAIL
"""

import argparse
import json
import os
import sys
from datetime import date, datetime

REPO = "/mnt/d/Project2/kensho"
D = REPO + "/data"

def load(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

def verify_success_criteria():
    """Verify success criteria from task body:
    - 商品ページviews ≥ 50 (0-2)
    - X投稿クリック率(CTR) ≥ 1% (unmeasurable)
    - 1ヶ月以内に初売上発生、または「撤退／価格改訂／商品改訂」判断
    """
    # Load latest data
    views_history = load(f"{D}/gumroad_views_history.json")
    kpi_state = load(f"{D}/gumroad_promo_kpi_state.json")
    
    # Get latest views (should be today)
    today = date.today().isoformat()
    today_views = views_history.get(today, {}).get("views")
    
    # Check views criterion: views ≥ 50
    views_ok = (today_views is not None and isinstance(today_views, int) and today_views >= 50)
    
    # Check sales criterion: any sales ever (weekly sales >= 1)
    sales_data = kpi_state.get("sales", {})
    week_sales = sales_data.get("week", 0) if isinstance(sales_data, dict) else 0
    sales_ok = (week_sales >= 1)
    
    # CTR is unmeasurable per task note -> treat as unknown, not a failure
    # Decision criterion: if no sales in 1 month -> we should retreat/reprice/rework
    # Since we have zero sales and zero views, we are in retreat territory
    
    return {
        "views_ok": views_ok,
        "sales_ok": sales_ok,
        "today_views": today_views,
        "week_sales": week_sales,
        "views_criterion_met": views_ok,
        "sales_criterion_met": sales_ok,
        "decision_needed": not (views_ok or sales_ok)  # If neither metric is good
    }

print("## 1. Product facts (Gumroad API /v2/products, live 2026-09-27)")
sc, body = None, None
import urllib.request, urllib.error
tok = os.environ.get("GUMROAD_TOKEN", "")
if not tok:
    for line in open(REPO + "/.env", encoding="utf-8"):
        if line.startswith("GUMROAD_TOKEN="):
            tok = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
req = urllib.request.Request("https://api.gumroad.com/v2/products",
                             headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        sc, body = r.status, json.loads(r.read().decode("utf-8", "ignore"))
except urllib.error.HTTPError as e:
    sc, body = e.code, e.read().decode("utf-8", "ignore")
print(f"status={sc} success={body.get('success') if isinstance(body, dict) else body}")
for p in (body.get("products") if isinstance(body, dict) else []) or []:
    print(f"  - {p.get('name')!r} price={p.get('price')} currency={p.get('currency')} "
          f"permalink={p.get('custom_permalink')} published={p.get('is_published')}")

print()
print("## 2. Sales ledger (Gumroad API /v2/sales, live)")
req = urllib.request.Request("https://api.gumroad.com/v2/sales",
                             headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        sd = json.loads(r.read().decode("utf-8", "ignore"))
    print(f"success={sd.get('success')} sales_count={len(sd.get('sales') or [])}")
except Exception as e:
    print(f"ERROR {type(e).__name__}: {e}")

print()
print("## 3. Dashboard state (data/gumroad_state.json)")
st = load(f"{D}/gumroad_state.json")
print(json.dumps(st, ensure_ascii=False, indent=1)[:600])

print()
print("## 4. Views history (data/gumroad_views_history.json)")
vh = load(f"{D}/gumroad_views_history.json")
for k in sorted(vh):
    v = vh[k]
    print(f"  {k}: views={v.get('views')} sales={v.get('sales')} total={v.get('total')} referrers={v.get('referrers')} login_ok={v.get('login_ok')}")

print()
print("## 5. X post history (data/gumroad_x_post_state.json)")
xp = load(f"{D}/gumroad_x_post_state.json")
for k in sorted(xp.get("posted", {})):
    r = xp["posted"][k]
    print(f"  {k}: tweet_id={r.get('tweet_id')} source={r.get('source','gumroad_x_post')} text={str(r.get('text'))[:90]!r}")

print()
print("## 6. X analytics (impressions) — latest per tweet")
xa = load(f"{D}/gumroad_x_analytics.json")
for tid, rec in xa.items():
    snaps = rec.get("snapshots", [])
    ok = [s["views"] for s in snaps if s.get("views") is not None]
    print(f"  tweet {tid} (date={rec.get('date')}): snapshots={len(snaps)} latest_views={ok[-1] if ok else None} max_views={max(ok) if ok else None}")

print()
print("## 7. KPI state latest")
kp = load(f"{D}/gumroad_promo_kpi_state.json")
print("  date:", kp.get("date"), "summary:", kp.get("summary"))
print("  sales:", json.dumps(kp.get("sales"), ensure_ascii=False))
print("  views:", json.dumps(kp.get("views"), ensure_ascii=False))

print()
print("## 8. Cross-post campaign state")
cp = load(f"{D}/gumroad_cross_post_state.json")
print(json.dumps(cp, ensure_ascii=False)[:800])

print()
print("## 9. Weekly promo state")
wp = load(f"{D}/gumroad_promo_weekly_state.json")
print(json.dumps(wp, ensure_ascii=False)[:800])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gumroad zero sales root cause analysis")
    parser.add_argument("--verify", action="store_true", help="Run verification and exit with code")
    args = parser.parse_args()
    
    if args.verify:
        result = verify_success_criteria()
        if result["views_ok"] and result["sales_ok"]:
            print("PASS")
            sys.exit(0)
        else:
            print("FAIL")
            print(f"  views={result['today_views']} (need ≥50): {'OK' if result['views_ok'] else 'FAIL'}")
            print(f"  week_sales={result['week_sales']} (need ≥1): {'OK' if result['sales_ok'] else 'FAIL'}")
            sys.exit(1)
    else:
        # Original full report (already printed above)
        pass