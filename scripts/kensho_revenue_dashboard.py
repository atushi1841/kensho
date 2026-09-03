#!/usr/bin/env python3
"""kensho_revenue_dashboard — 収益ダッシュボードHTML生成。

revenue-daily.json を読み込み、収益状況を可視化したHTMLを生成する。
出力: /mnt/d/Project2/kensho/revenue-status.html
cronで毎日収集後に自動生成される。
"""
import json
import os
from datetime import datetime
from typing import Any, Dict, List

PROJECT_DIR = "/mnt/d/Project2/kensho"
DATA_FILE = os.path.join(PROJECT_DIR, "data", "revenue-daily.json")
OUTPUT = os.path.join(PROJECT_DIR, "revenue-status.html")


def load_data() -> List[Dict[str, Any]]:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            result: List[Dict[str, Any]] = json.load(f)
            return result
    except Exception:
        return []


def render(entries: List[Dict[str, Any]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not entries:
        return f"<html><body><h1>収益ダッシュボード</h1><p>データなし</p><p>更新: {now}</p></body></html>"

    last = entries[-1]
    apify = last.get("apify", {})
    rapidapi = last.get("rapidapi", {})
    gumroad = last.get("gumroad", {})
    rev = last.get("revenue_estimate", {})

    # 直近の推移（7日分）
    recent = entries[-7:]
    trend_rows = ""
    for e in recent:
        trend_rows += f"<tr><td>{e.get('date','?')}</td><td>{e.get('apify',{}).get('total_runs',0)}</td><td>{e.get('apify',{}).get('total_users_30d',0)}</td><td>{e.get('rapidapi',{}).get('apis_total',0)}</td><td>{e.get('rapidapi',{}).get('apis_private',0)}</td></tr>"

    # Apify詳細（使用量順）
    apify_details = sorted(apify.get("details", []), key=lambda x: x.get("runs", 0), reverse=True)
    apify_rows = ""
    for d in apify_details[:15]:
        apify_rows += f"<tr><td>{d.get('name','?')}</td><td>{d.get('users',0)}</td><td>{d.get('u30d',0)}</td><td>{d.get('runs',0)}</td></tr>"

    # RapidAPI詳細
    rap_rows = ""
    for d in rapidapi.get("details", []):
        vis = "🔓" if d.get("visibility") == "PUBLIC" else "🔒"
        rap_rows += f"<tr><td>{vis}{d.get('name','?')}</td><td>{d.get('visibility','?')}</td><td>{d.get('pricing','?')}</td></tr>"

    # 収益機会
    opp_list = "".join(f"<li>✅ {o}</li>" for o in last.get("opportunities", []))
    warn_list = "".join(f"<li>⚠️ {w}</li>" for w in last.get("warnings", []))
    if not opp_list:
        opp_list = "<li>なし</li>"
    if not warn_list:
        warn_list = "<li>なし</li>"

    # Gumroad詳細
    gum_rows = ""
    for d in gumroad.get("details", []):
        gum_rows += f"<tr><td>{d.get('title','?')}</td><td>${d.get('price','?')}</td><td>{d.get('zip_size',0)} B</td></tr>"

    # Gumroad売上サマリー（CDPで取得した実値を表示 — state_exists=false解消の目印）
    gum_state_exists = gumroad.get("state_exists", False)
    gum_balance = gumroad.get("balance_usd")
    gum_total = gumroad.get("total_earnings_usd")
    gum_last7 = gumroad.get("last_7_days_usd")
    gum_login = gumroad.get("login_ok")
    gum_collected = gumroad.get("collected_at", "?")
    gum_state_color = "#3fb950" if gum_state_exists else "#d29922"
    gum_state_label = "✓ 取得済み" if gum_state_exists else "✗ 未取得"
    gum_login_label = (
        "✓ ログインOK" if gum_login is True
        else "✗ セッション失効" if gum_login is False
        else "— 不明"
    )
    def _fmt_money(v: object) -> str:
        return f"${v:.2f}" if isinstance(v, (int, float)) else "—"
    gum_sales_card = f"""
<div class="card">
<div class="card-title">Gumroad 売上（CDP自動取得）</div>
<div class="grid-3">
<div class="stat-card"><div class="stat-val" style="color:{gum_state_color}">{gum_state_label}</div><div class="stat-label">データ取得</div></div>
<div class="stat-card"><div class="stat-val">{_fmt_money(gum_total)}</div><div class="stat-label">総収益</div></div>
<div class="stat-card"><div class="stat-val" style="color:#58a6ff">{_fmt_money(gum_balance)}</div><div class="stat-label">残高</div></div>
</div>
<p class="sub" style="margin-top:8px">
直近7日: {_fmt_money(gum_last7)} / 直近28日: {_fmt_money(gumroad.get('last_28_days_usd'))} /
ログイン: {gum_login_label} / 取得時刻: {gum_collected}
</p>
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>Kensho 収益ダッシュボード</title>
<style>
body{{font-family:-apple-system,'Segoe UI',Meiryo,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:20px}}
h1{{font-size:1.4rem;border-bottom:1px solid #21262d;padding-bottom:8px}}
.card{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:16px;margin-bottom:14px}}
.card-title{{font-weight:600;margin-bottom:10px;color:#58a6ff}}
.grid-3{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.stat-card{{text-align:center;padding:12px;background:#0d1117;border-radius:6px}}
.stat-val{{font-size:1.6rem;font-weight:700;color:#3fb950}}
.stat-label{{font-size:0.75rem;color:#8b949e;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
td,th{{padding:5px 8px;border-bottom:1px solid #21262d;font-size:0.82rem;text-align:left}}
th{{color:#8b949e;font-weight:600}}
.sub{{color:#8b949e;font-size:0.8rem;margin-bottom:12px}}
ul{{margin:0;padding-left:20px}}
li{{font-size:0.85rem;margin-bottom:4px}}
</style>
</head>
<body>
<h1>💰 Kensho 収益ダッシュボード</h1>
<div class="sub">更新: {now} | 収集日: {last.get('date','?')}</div>

<div class="card">
<div class="card-title">収益サマリー</div>
<div class="grid-3">
<div class="stat-card"><div class="stat-val">${rev.get('total_monthly',0)}</div><div class="stat-label">月間収益見込み</div></div>
<div class="stat-card"><div class="stat-val" style="color:#58a6ff">{apify.get('actors_total',0)}</div><div class="stat-label">Apifyアクター</div></div>
<div class="stat-card"><div class="stat-val" style="color:#d29922">{rapidapi.get('apis_total',0)}</div><div class="stat-label">RapidAPI API</div></div>
</div>
<p class="sub" style="margin-top:8px">{rev.get('note','')}</p>
</div>

<div class="card">
<div class="card-title">収益機会と警告</div>
<p><strong>収益機会:</strong></p>
<ul>{opp_list}</ul>
<p><strong>警告:</strong></p>
<ul>{warn_list}</ul>
</div>

<div class="card">
<div class="card-title">Apify アクター使用量（直近15本）</div>
<table>
<tr><th>アクター</th><th>総ユーザー</th><th>30日ユーザー</th><th>総runs</th></tr>
{apify_rows}
</table>
</div>

<div class="card">
<div class="card-title">RapidAPI API一覧（{rapidapi.get('apis_total',0)}本）</div>
<table>
<tr><th>API</th><th>可視性</th><th>価格設定</th></tr>
{rap_rows}
</table>
</div>

<div class="card">
<div class="card-title">Gumroad商品</div>
<table>
<tr><th>商品</th><th>価格</th><th>ZIPサイズ</th></tr>
{gum_rows}
</table>
</div>

{gum_sales_card}

<div class="card">
<div class="card-title">直近7日の推移</div>
<table>
<tr><th>日付</th><th>Apify runs</th><th>Apify u30d</th><th>RapidAPI API数</th><th>非公開API</th></tr>
{trend_rows}
</table>
</div>

<div class="sub">Kensho 収益ダッシュボード v1 — {now}</div>
</body>
</html>
"""


def main() -> None:
    entries = load_data()
    html = render(entries)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ revenue-status.html 生成完了 ({len(entries)} entries)")
    print(f"  出力: {OUTPUT}")


if __name__ == "__main__":
    main()