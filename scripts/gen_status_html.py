#!/usr/bin/env python3
# ruff: noqa: E501, N806
"""Kensho ステータスHTML生成 — gen_status_data.py の出力からHTMLを生成

`gen_status_data.py` が `/tmp/kensho_status_data.json` に出力したデータを読み込み、
`kensho-status.html` を生成する。
"""

import json
import os
import time
from html import escape as _html_escape

# ── 色定義 ──
BG = "#0d1117"       # 背景色
TEXT = "#c9d1d9"     # メインテキスト
GREEN = "#3fb950"    # 良好
YELLOW = "#d29922"   # 注意
RED = "#f85149"      # 警告
BLUE = "#58a6ff"     # リンク/アクセント
PURPLE = "#bc8cff"   # その他
GRAY = "#8b949e"     # 灰色

DATA_FILE = "/tmp/kensho_status_data.json"
OUTPUT_FILE = "/mnt/d/Project2/kensho/kensho-status.html"


def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def source_url_for(src: str) -> str:
    """ソース表示名を返す"""
    pretty = {
        "knshow": "KNSHO",
        "kenshouclub": "Kensho Club",
        "cpmeikan": "Meikan",
        "kema": "KEMA",
        "ken-kaku": "Ken-Kaku",
        "chancecom": "Chance.com",
        "twscrape": "Twscrape",
        "kensho-everyday": "Kensho Everyday",
        "unknown": "unknown",
    }
    return pretty.get(src, src)


def _dl_label(dd) -> str:
    """締切日数(days_left)を表示ラベルに変換（None=締切不明）"""
    if dd is None:
        return "—"
    if dd < 0:
        return "期限切"
    if dd == 0:
        return "本日"
    return f"{dd}日後"


def generate_html(data: dict) -> str:
    sm = data["summary"]
    st = data["stats"]
    accounts = data["accounts"]
    health = data.get("health", {})
    ts = data.get("timestamp", "")

    GREEN_C, YELLOW_C, RED_C, BLUE_C, PURPLE_C, GRAY_C, BG_C = (
        GREEN,
        YELLOW,
        RED,
        BLUE,
        PURPLE,
        GRAY,
        BG,
    )
    ok_icon = "🟢" if health.get("ok", True) else "🔴"
    apply_icon = "🟢"

    # ── items_by_source の安全な取得 ──
    items_by_source = data.get("stats", {}).get("items_by_source", {})
    if not items_by_source and "collected_items" in data:
        from collections import defaultdict

        _tmp = defaultdict(list)
        for it in data["collected_items"]:
            _tmp[it.get("source", "unknown")].append(it)
        items_by_source = dict(_tmp)

    now_str = time.strftime("%Y-%m-%d %H:%M", time.localtime())

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>Kensho ダッシュボード</title>
<style>
/* フィルタースタイル */
.source-filter-active {{
    background: {BLUE_C} !important;
    color: {BG_C} !important;
}}
.filtered-hidden {{
    display: none;
}}
.filter-table {{
    max-height: 400px;
    overflow-y: auto;
}}
.filter-bar {{
    display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px;
}}
.filter-group {{
    display: flex; gap: 4px; align-items: center;
}}
.filter-group .fg-label {{
    color: #8b949e; font-size: 0.72rem; margin-right: 4px; letter-spacing: 0.3px;
}}
.filter-btn {{
    background: #161b22; border: 1px solid #30363d; color: #8b949e;
    border-radius: 12px; padding: 2px 10px; font-size: 0.75rem; cursor: pointer;
}}
.filter-btn:hover {{
    border-color: {BLUE_C};
}}
.filter-btn.on {{
    background: {BLUE_C}; color: {BG_C}; border-color: {BLUE_C}; font-weight: 600;
}}
.stat-num {{
    font-weight: 700;
}}
.stat-dim {{
    color: #8b949e; font-size: 0.7rem;
}}
.tag-dup {{
    color: {YELLOW_C}; font-weight: 600;
}}
.tag-new {{
    color: {GREEN_C}; font-weight: 600;
}}
.prio-hi {{
    color: {PURPLE_C}; font-weight: 600;
}}
</style>

<script>
    // ── フィルタ状態 ──
    var ACTIVE_SRCS = [];   // 空 = 全ソース
    var WIN_MIN = 0;        // 当選人数下限（0 = 指定なし）
    var DL_MAX = null;      // 締切上限（null = 指定なし / 0 = 本日 / 3 = 3日以内）

    function syncBtnState() {{
        document.querySelectorAll('.filter-btn').forEach(function (b) {{
            var on = false;
            if (b.dataset.ftype === 'winner') {{
                on = WIN_MIN === parseInt(b.dataset.fval || '0', 10);
            }} else if (b.dataset.ftype === 'deadline') {{
                on = (b.dataset.fval || 'all') === (DL_MAX === null ? 'all' : (DL_MAX === 0 ? 'today' : '3days'));
            }}
            b.classList.toggle('on', on);
        }});
        document.querySelectorAll('.source-button').forEach(function (b) {{
            b.classList.toggle('source-filter-active', ACTIVE_SRCS.indexOf(b.dataset.source) !== -1);
        }});
    }}

    function applyFilters() {{
        // 収集元別内訳の集計行（ソースのみでフィルタ）
        document.querySelectorAll('.filterable-item.src-row').forEach(function (item) {{
            var srcs = (item.dataset.sources || '').split(',');
            var show = ACTIVE_SRCS.length === 0 || ACTIVE_SRCS.some(function (s) {{ return srcs.indexOf(s) !== -1; }});
            item.classList.toggle('filtered-hidden', !show);
        }});
        // 案件リスト行（ソース + 当選人数 + 締切でフィルタ）
        document.querySelectorAll('.filterable-item.filter-row').forEach(function (item) {{
            var srcs = (item.dataset.sources || '').split(',');
            var wc = parseInt(item.dataset.winc || '0', 10) || 0;
            var ddRaw = item.dataset.dl;
            var dd = ddRaw === '' || ddRaw == null ? -1 : (parseInt(ddRaw, 10) || 0);
            var show = true;
            if (ACTIVE_SRCS.length && !ACTIVE_SRCS.some(function (s) {{ return srcs.indexOf(s) !== -1; }})) show = false;
            if (show && WIN_MIN > 0 && wc < WIN_MIN) show = false;
            if (show && DL_MAX !== null) {{
                if (dd < 0 || dd > DL_MAX) show = false;  // 締切なしは絞り込み時は非表示
            }}
            item.classList.toggle('filtered-hidden', !show);
        }});
        // 空状態のヒント行（フィルタで全非表示の場合に表示）
        var list = document.querySelectorAll('.filterable-item.filter-row');
        var anyVisible = Array.from(list).some(function (it) {{ return !it.classList.contains('filtered-hidden'); }});
        var hint = document.getElementById('filter-empty');
        if (hint) hint.classList.toggle('filtered-hidden', anyVisible || list.length === 0);
    }}

    function filterBySource(source) {{
        var i = ACTIVE_SRCS.indexOf(source);
        if (i === -1) {{ ACTIVE_SRCS.push(source); }} else {{ ACTIVE_SRCS.splice(i, 1); }}
        syncBtnState();
        applyFilters();
    }}

    function showAllSources() {{
        ACTIVE_SRCS = [];
        syncBtnState();
        applyFilters();
    }}

    function setWinner(min) {{
        WIN_MIN = parseInt(min || '0', 10) || 0;
        syncBtnState();
        applyFilters();
    }}

    function setDeadline(mode) {{
        DL_MAX = (mode === 'all') ? null : ((mode === 'today') ? 0 : 3);
        syncBtnState();
        applyFilters();
    }}
</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:{BG_C};color:{TEXT};padding:20px;max-width:960px;margin:auto}}
h1{{font-size:1.3rem;margin-bottom:4px;color:{BLUE_C}}}
.sub{{color:#8b949e;font-size:0.8rem;margin-bottom:16px}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px;margin-bottom:10px}}
.card-title{{color:#8b949e;font-size:0.7rem;text-transform:uppercase;margin-bottom:10px;letter-spacing:0.5px;display:flex;justify-content:space-between}}
.num{{color:#8b949e;font-size:0.82rem;font-variant-numeric:tabular-nums}}
.accent{{color:{BLUE_C}}}
.warn{{color:#d29922}}
.footer{{text-align:center;color:#484f58;font-size:0.7rem;margin-top:16px}}
.grid-2{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
.grid-4{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}}
.grid-5{{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}}
.stat-card{{text-align:center;padding:10px;background:#0d1117;border-radius:6px}}
.stat-label{{font-size:0.7rem;color:#8b949e;margin-top:2px}}
.stat-val{{font-size:1.5rem;font-weight:700}}
.badge{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:0.75rem;font-weight:600}}
.bg-green{{background:#1b4128;color:{GREEN_C}}}
.bg-red{{background:#41211b;color:{RED_C}}}
.bg-yellow{{background:#412b1b;color:#d29922}}
.ceil{{background:#0d1117!important}}
.ceil td{{color:#d29922!important}}
.ok td{{color:#8b949e!important}}
.note{{color:#8b949e;font-size:0.75rem;margin-top:8px}}
table{{width:100%;border-collapse:collapse}}
td{{padding:5px 8px;border-bottom:1px solid #21262d;font-size:0.82rem}}
.warning-banner{{background:#412b1b;border:1px solid #d29922;border-radius:8px;padding:10px 14px;margin-bottom:12px;color:#d29922;font-size:0.85rem;line-height:1.5}}
.warning-banner strong{{color:{RED_C}}}
</style>
</head>
<body>
<h1>Kensho ダッシュボード</h1>
<div class="sub">更新: {now_str} | 収集cron: {ok_icon} | 応募: {apply_icon}</div>
"""

    # ── 健全性警告バナー ──
    if health.get("warnings"):
        for w in health["warnings"]:
            prefix = "<strong>⚠️ 要対応</strong> " if not health.get("ok", True) else "ℹ️ "
            html += f'<div class="warning-banner">{prefix}{w}</div>\n'

    # ── 概要 ──
    html += """<div class="card"><div class="card-title">概要</div><div class="grid-5">"""
    html += f'<div class="stat-card"><div class="stat-val" style="color:{GREEN_C}">{sm["total_items"]}</div><div class="stat-label">件数</div></div>'
    html += f'<div class="stat-card"><div class="stat-val" style="color:{BLUE_C}">{sm["total_applied"]}</div><div class="stat-label">応募済</div></div>'
    html += f'<div class="stat-card"><div class="stat-val" style="color:{YELLOW_C}">{sm["total_pending"]}</div><div class="stat-label">未応募</div></div>'
    html += f'<div class="stat-card"><div class="stat-val" style="color:{PURPLE_C}">{sm["total_today"]}</div><div class="stat-label">本日</div></div>'
    html += "</div></div>"

    # ── 締切 ──
    dl = st.get("deadline_dist", {})
    html += '<div class="card"><div class="card-title">締切</div><div class="grid-5">'
    for label, key, color in [
        ("期限切", "expired", RED_C),
        ("本日", "today", YELLOW_C),
        ("3日", "3days", GREEN_C),
        ("1週", "week", BLUE_C),
        ("先", "future", GRAY_C),
    ]:
        val = dl.get(key, 0)
        html += f'<div class="stat-card"><div class="stat-val" style="color:{color}">{val}</div><div class="stat-label">{label}</div></div>'
    html += "</div></div>"

    # ── 収集元 ──
    sd = st.get("source_dist", {})
    total_src = sum(sd.values()) or 1
    html += '<div class="card"><div class="card-title">収集元 クリックでフィルタ切替</div><div class="grid-2">'
    for src, cnt in sorted(sd.items(), key=lambda x: -x[1]):
        pct = round(cnt / total_src * 100, 1)
        src_name = source_url_for(src)
        html += f'<div class="stat-card source-button" style="cursor:pointer" onclick="filterBySource(\'{src}\')" data-source="{src}"><div class="stat-val" style="color:{BLUE_C}">{cnt}</div><div class="stat-label">{src_name}</div><div class="note" style="text-align:center">{pct}%</div></div>'
    html += f'<div class="stat-card" style="cursor:pointer" onclick="showAllSources()"><div class="stat-label">すべて表示</div></div>'
    html += "</div></div>"

    # ── 収集元別内訳パネル（有効・重複・本日新着）──
    sstats = st.get("source_stats", {})
    if sstats:
        html += '<div class="card"><div class="card-title">収集元別 有効・重複・本日新着</div><div class="grid-2">'
        for src, info in sorted(sstats.items(), key=lambda kv: -kv[1].get("total", 0)):
            _label = info.get("label", source_url_for(src))
            _total = info.get("total", 0)
            _pend = info.get("pending", 0)
            _dup = info.get("dup", 0)
            _new = info.get("new_today", 0)
            html += (
                '<div class="stat-card">'
                f'<div class="stat-label">{_html_escape(_label)}</div>'
                f'<div class="stat-val" style="color:{BLUE_C}">{_total}</div>'
                f'<div class="stat-dim" style="margin-top:4px">有効 '
                f'<span class="stat-num" style="color:{GREEN_C}">{_pend}</span>'
                f' | 重複 <span class="tag-dup">{_dup}</span>'
                f' | 新着 <span class="tag-new">+{_new}</span></div>'
                '</div>'
            )
        html += "</div></div>"

    # ── 収集元別内訳テーブル ──
    html += '<div class="card"><div class="card-title">収集元別内訳（フィルタで表示絞込）</div>'
    html += '<table class="filter-table"><thead><tr><td>ソース</td><td>件数</td><td>応募済</td><td>未応募</td></tr></thead><tbody>'
    for src in sorted(sd.keys(), key=lambda k: -sd[k]):
        cnt = sd[src]
        src_name = source_url_for(src)
        src_items = items_by_source.get(src, [])
        applied_cnt = sum(1 for it in src_items if it.get("applied") and len(it.get("applied", {})) > 0)
        pending_cnt = cnt - applied_cnt
        html += f'<tr class="filterable-item src-row" data-sources="{src}">'
        html += f'<td>{src_name}</td><td class="num">{cnt}</td><td class="num">{applied_cnt}</td><td class="num">{pending_cnt}</td></tr>'
    html += '</tbody></table>'
    html += '<div class="note">※ ソースをクリックすると、上のカードとこの表の該当行がハイライト切替されます。</div>'
    html += "</div>"

    # ── 案件リスト（当選人数・締切フィルタ）──
    dash_items = data.get("items", [])
    html += '<div class="card"><div class="card-title">案件リスト（当選人数・締切で絞り込み）</div>'
    html += (
        '<div class="filter-bar">'
        '<div class="filter-group"><span class="fg-label">当選人数</span>'
        '<button class="filter-btn on" data-ftype="winner" data-fval="0" onclick="setWinner(\'0\')">すべて</button>'
        '<button class="filter-btn" data-ftype="winner" data-fval="100" onclick="setWinner(\'100\')">100人以上</button>'
        '<button class="filter-btn" data-ftype="winner" data-fval="1000" onclick="setWinner(\'1000\')">1000人以上</button>'
        '</div>'
        '<div class="filter-group"><span class="fg-label">締切</span>'
        '<button class="filter-btn on" data-ftype="deadline" data-fval="all" onclick="setDeadline(\'all\')">すべて</button>'
        '<button class="filter-btn" data-ftype="deadline" data-fval="today" onclick="setDeadline(\'today\')">本日</button>'
        '<button class="filter-btn" data-ftype="deadline" data-fval="3days" onclick="setDeadline(\'3days\')">3日以内</button>'
        '</div>'
        '</div>'
    )
    if dash_items:
        html += '<table class="filter-table"><thead><tr><td>ソース</td><td>内容</td><td>当選人数</td><td>締切</td><td>状態</td><td>優先</td></tr></thead><tbody>'
        for it in dash_items:
            _src = it.get("source", "unknown")
            _dd = it.get("deadline_days")
            _dl_attr = "" if _dd is None else str(_dd)
            _wc = it.get("winner_count")
            _wc_val = 0 if _wc is None else int(_wc)
            _wc_disp = "—" if _wc is None else f"{int(_wc)}人"
            _title = _html_escape((it.get("title") or "").strip() or "（タイトルなし）")
            _url = it.get("x_url") or it.get("detail_url") or ""
            if _url:
                _title = f'<a style="color:{BLUE_C};text-decoration:none" href="{_html_escape(_url)}" target="_blank" rel="noopener">{_title}</a>'
            _applied = it.get("applied", False)
            _state = '<span style="color:#3fb950">応募済</span>' if _applied else '<span style="color:#d29922">未応募</span>'
            _prio = '<span class="prio-hi">高</span>' if it.get("high_prio", False) else '<span class="stat-dim">—</span>'
            html += (
                f'<tr class="filterable-item filter-row" data-sources="{_src}" data-winc="{_wc_val}" data-dl="{_dl_attr}">'
                f'<td>{_html_escape(it.get("source_display") or _src)}</td>'
                f'<td>{_title}</td>'
                f'<td class="num">{_wc_disp}</td>'
                f'<td class="num">{_dl_label(_dd)}</td>'
                f'<td>{_state}</td>'
                f'<td>{_prio}</td>'
                '</tr>'
            )
        html += '</tbody></table>'
        html += '<div class="note filtered-hidden" id="filter-empty">条件に一致する案件がありません。フィルタを解除してください。</div>'
    else:
        html += '<div class="note">案件データがありません。</div>'
    html += "</div>"

    # ── アカウント ──
    rows = []
    for ac in accounts:
        ad = data["accounts"][ac]
        d = ad["daily"]
        f_val, r_val, l_val = d.get("follow", 0), d.get("rt", 0), d.get("like", 0)
        total_actions = f_val + r_val + l_val
        at = ad["applied_today"]
        if total_actions > 20:
            badge = "bg-green"
            label = "多"
        elif total_actions > 5:
            badge = "bg-yellow"
            label = "中"
        else:
            badge = "bg-red"
            label = "低"
        rows.append((ac, at, ad, f_val, r_val, l_val, total_actions, badge, label))
    rows.sort(key=lambda x: -x[6])

    html += '<div class="card"><div class="card-title">アカウント</div><table>'
    html += "<tr><td>アカウント</td><td>回線 / アダプタ / SSID</td><td>本日</td><td>累計</td><td>延期</td><td>未応募</td><td>アクション</td></tr>"
    for ac, at, ad, f_val, r_val, l_val, total, badge, label in rows:
        ta = ad["total_applied_all"]
        defer = ad.get("defer_count", 0)
        pending = ad["pending"]["total"]
        html += f'<tr><td>{ac} <span class="badge {badge}">{label}</span></td><td class="num">--</td><td class="accent">{at}</td><td class="num">{ta}</td><td class="num">{defer}</td><td class="num">{pending}</td><td class="num">F{f_val} RT{r_val} <3{l_val}</td></tr>'
    html += "</table></div>"

    html += f'<div class="footer">更新: {now_str}</div>'
    html += "</body></html>"
    return html


def main():
    data = load_data()
    html = generate_html(data)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
