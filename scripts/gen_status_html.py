#!/usr/bin/env python3
# ruff: noqa: E501, N806
"""Kensho ステータスHTML生成 — gen_status_data.py の出力からHTMLを生成"""

import glob
import json
import os
import time

DATA_FILE = "/tmp/kensho_status_data.json"
OUTPUT_FILE = "/mnt/d/Project2/kensho/kensho-status.html"


def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def heartbeat_age(path, max_minutes=35):
    """指定ファイルが max_minutes 分以内に更新されていれば 'yes'、なければ 'no'"""
    try:
        age = time.time() - os.path.getmtime(path)
        return "yes" if age < max_minutes * 60 else "no"
    except Exception:
        return "no"


def generate_html(data):
    log_files = glob.glob("/mnt/d/Project2/kensho/logs/auto_*.log")
    if log_files:
        latest_log = max(log_files, key=os.path.getmtime)
    else:
        latest_log = ""
    cron_running = heartbeat_age(latest_log) if latest_log else "no"
    orch_running = heartbeat_age("/mnt/d/Project2/kensho/data/orchestrator_heartbeat.json")
    now = data["pipeline"]["updated"]
    sm = data["summary"]
    st = data["stats"]

    BLUE = "#58a6ff"
    GREEN = "#3fb950"
    YELLOW = "#d29922"
    RED = "#f85149"
    GRAY = "#8b949e"
    BG = "#0d1117"
    CARD = "#161b22"
    BORDER = "#30363d"
    PURPLE = "#bc8cff"

    accounts = sorted(data["accounts"].keys())

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Kensho Dashboard v5</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:{BG};color:#c9d1d9;padding:20px;max-width:960px;margin:auto}}
h1{{font-size:1.3rem;margin-bottom:4px;color:{BLUE}}}
.sub{{color:{GRAY};font-size:0.8rem;margin-bottom:16px}}
.card{{background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:14px 16px;margin-bottom:10px}}
.card-title{{color:{GRAY};font-size:0.7rem;text-transform:uppercase;margin-bottom:10px;letter-spacing:0.5px;display:flex;justify-content:space-between}}
.num{{color:{GRAY};font-size:0.82rem;font-variant-numeric:tabular-nums}}
.accent{{color:{BLUE}}}
.warn{{color:{YELLOW}}}
.footer{{text-align:center;color:#484f58;font-size:0.7rem;margin-top:16px}}
.grid-2{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
.grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.grid-5{{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}}
.stat-card{{text-align:center;padding:10px;background:{BG};border-radius:6px}}
.stat-label{{font-size:0.7rem;color:{GRAY};margin-top:2px}}
.stat-val{{font-size:1.5rem;font-weight:700}}
.badge{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:600}}
.bg-green{{background:#1b4128;color:{GREEN}}}
.bg-red{{background:#41211b;color:{RED}}}
.bg-yellow{{background:#412b1b;color:{YELLOW}}}
.ceil{{background:#0d1117!important}}
.ceil td{{color:{YELLOW}!important}}
.ok td{{color:{GRAY}!important}}
.note{{color:{GRAY};font-size:0.75rem;margin-top:8px}}
table{{width:100%;border-collapse:collapse}}
td{{padding:5px 8px;border-bottom:1px solid #21262d;font-size:0.82rem}}
</style>
</head>
<body>
<h1>Kensho Dashboard v5</h1>
<div class="sub">更新: {now} | Cron: {"🟢" if cron_running == "yes" else "🔴"} | Orch: {"🟢" if orch_running == "yes" else "🔴"}</div>
<div class="card"><div class="card-title">summary</div><div class="grid-5">
<div class="stat-card"><div class="stat-val" style="color:{GREEN}">{sm["total_items"]}</div><div class="stat-label">items</div></div>
<div class="stat-card"><div class="stat-val" style="color:{BLUE}">{sm["total_applied"]}</div><div class="stat-label">applied</div></div>
<div class="stat-card"><div class="stat-val" style="color:{YELLOW}">{sm["total_pending"]}</div><div class="stat-label">pending</div></div>
<div class="stat-card"><div class="stat-val" style="color:{PURPLE}">{sm["total_today"]}</div><div class="stat-label">today</div></div>
</div></div>
"""

    # deadline
    dl = st.get("deadline_dist", {})
    html += '<div class="card"><div class="card-title">deadline</div><div class="grid-5">'
    for label, key, color in [
        ("expired", "expired", RED),
        ("today", "today", YELLOW),
        ("3days", "3days", GREEN),
        ("week", "week", BLUE),
        ("future", "future", GRAY),
    ]:
        val = dl.get(key, 0)
        html += f'<div class="stat-card"><div class="stat-val" style="color:{color}">{val}</div><div class="stat-label">{label}</div></div>'
    html += "</div></div>"

    # accounts
    rows = []
    for ac in accounts:
        ad = data["accounts"][ac]
        d = ad["daily"]
        f_val, r_val, l_val = d.get("follow", 0), d.get("rt", 0), d.get("like", 0)
        total_actions = f_val + r_val + l_val
        at = ad["applied_today"]
        if total_actions > 20:
            badge = "bg-green"
            label = "many"
        elif total_actions > 5:
            badge = "bg-yellow"
            label = "mid"
        else:
            badge = "bg-red"
            label = "new"
        rows.append((ac, at, ad, f_val, r_val, l_val, total_actions, badge, label))
    rows.sort(key=lambda x: -x[6])

    html += '<div class="card"><div class="card-title">accounts</div><table>'
    html += "<tr><td>account</td><td>today</td><td>total</td><td>DEFER</td><td>pending</td><td>actions</td></tr>"
    for ac, at, ad, f_val, r_val, l_val, total, badge, label in rows:
        ta = ad["total_applied_all"]
        defer = ad.get("defer_count", 0)
        pending = ad["pending"]["total"]
        html += f'<tr><td>{ac} <span class="badge {badge}">{label}</span></td><td class="accent">{at}</td><td class="num">{ta}</td><td class="num">{defer}</td><td class="num">{pending}</td><td class="num">F{f_val} RT{r_val} <3{l_val}</td></tr>'
    html += "</table></div>"

    # sources
    sd = st.get("source_dist", {})
    total_src = sum(sd.values()) or 1
    html += '<div class="card"><div class="card-title">sources</div><div class="grid-2">'
    for src, cnt in sorted(sd.items(), key=lambda x: -x[1]):
        pct = cnt / total_src * 100
        html += f'<div class="stat-card"><div class="stat-val" style="font-size:1.1rem;color:{BLUE}">{cnt}</div><div class="stat-label">{src} ({pct:.0f}%)</div></div>'
    html += "</div></div>"

    # prize
    pd = st.get("prize_dist", {})
    html += '<div class="card"><div class="card-title">prize value</div><div class="grid-4">'
    for label, key, color in [
        ("high", "high(3.0)", PURPLE),
        ("mid", "mid_high(2.5)", BLUE),
        ("midlo", "mid(2.0)", GREEN),
        ("low", "low(1.5)", YELLOW),
        ("none", "none(1.0)", GRAY),
        ("unscored", "unscored", "#484f58"),
    ]:
        val = pd.get(key, 0)
        html += f'<div class="stat-card"><div class="stat-val" style="font-size:1.1rem;color:{color}">{val}</div><div class="stat-label">{label}</div></div>'
    html += "</div></div>"

    # recent runs
    html += '<div class="card"><div class="card-title">recent runs</div><table><tr><td>time</td><td>result</td><td>ok</td><td>err</td><td>act</td><td>F</td><td>RT</td><td><3</td></tr>'
    for entry in data.get("recent_runs", [])[:25]:
        if entry["status"] == "ok":
            icon = "OK"
            cls = "ok"
        else:
            icon = "WARN"
            cls = "ceil"
        html += f'<tr class="{cls}"><td>{entry["time"]}</td><td>{icon}</td><td class="accent">{entry["success"]}</td><td class="num" style="color:{GRAY}">{entry["error"]}</td><td class="num">{entry["accounts"]}</td><td class="num">{entry["follow"]}</td><td class="num">{entry["rt"]}</td><td class="num">{entry["like"]}</td></tr>'
    html += "</table>"
    ok_count = sum(1 for e in data.get("recent_runs", []) if e["status"] == "ok")
    total_count = len(data.get("recent_runs", []))
    rate = f"{ok_count / total_count * 100:.1f}" if total_count > 0 else "N/A"
    html += f'<div class="note">last {total_count} runs: ok <strong class="accent">{ok_count}</strong> / err <strong style="color:{RED}">{total_count - ok_count}</strong> — success <strong>{rate}%</strong></div>'
    html += "</div>"

    html += f'<div class="footer">Kensho Dashboard v5 - {now}</div>'
    html += "</body></html>"
    return html


def main():
    data = load_data()
    html = generate_html(data)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
