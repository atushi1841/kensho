#!/usr/bin/env python3
# ruff: noqa: E501, N806
"""Kensho ステータスHTML生成 — gen_status_data.py の出力からHTMLを生成"""

import glob
import json
import os
import time

DATA_FILE = "/tmp/kensho_status_data.json"
OUTPUT_FILE = "/mnt/d/Project2/kensho/kensho-status.html"

ACCOUNT_ADAPTERS = {
    # account: (アダプタ名, SSID, 回線種別)
    "atushi16": ("自宅有線LAN", "RJ45直結", "自宅"),
    "kudou": ("kudou_RM10JE_B", "RM10JE_B", "povo"),
    "chugakujuken": ("chugakujuken_RM10JE_S", "RM10JE_S", "povo"),
    "zin20120731": ("zin_AW6povo", "AiR-WiFi_6_povo", "povo"),
    "TankanNotes": (
        "Tankan_ETH3",
        "LAN直結",
        "ワイモバイル",
    ),  # 2026-09-10: HR01 Wi-Fi不良→ワイモバイルHR01ルーターのLANポートへUSB有線直結(Realtek USB FE)。アダプタ名=イーサネット 3→Tankan_ETH3にリネーム
    # "inobase1-4": ("inobase1-4", "ino1_4_oppo_r5a", "povo"),  # 2026-09-01: 凍結（code 64）→ dashboard除外
    "toushiwatch": (
        "toushiwatch_airtra1",
        "2_povo_AW",
        "povo",
    ),  # 2026-08-31: royal破棄→toushiwatch。air-tra1モバイルWiFi
}

# UNUSED（応募停止済み）: cron再生成でも維持されるようハードコード（2026-08-17）
UNUSED_ADAPTERS: dict[str, tuple[str, str, str]] = {}


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


# ── Hermes LLMプロバイダ構成（config.yamlから動的読取） ──────────────
HERMES_PROFILES = {
    "kensho-sweeps": "/home/atushi/.hermes/profiles/kensho-sweeps/config.yaml",
    "tai": "/home/atushi/.hermes/profiles/tai/config.yaml",
}

try:
    import yaml
except Exception:
    yaml = None


def _safe_str(v):
    return v if isinstance(v, str) and v else "—"


def _model_label(cfg):
    """config['model'] → 表示用ラベル"""
    if not isinstance(cfg, dict):
        return "—"
    mod = _safe_str(cfg.get("default") or cfg.get("model"))
    base = _safe_str(cfg.get("base_url"))
    if mod and mod != "—":
        label = f"{mod}"
        if base and base != "—":
            # 冗長なscheme/pathは省く
            host = base.replace("https://", "").replace("http://", "").split("/")[0]
            label += f"  <span class='num'>({host})</span>"
        return label
    return base if base != "—" else "—"


def load_hermes_config():
    """各プロフィールの主モデル / フォールバック / auxiliary / vision を読取"""
    out = {}
    for name, path in HERMES_PROFILES.items():
        info = {"ok": False, "primary": "—", "fallback": [], "aux": "—", "vision": "—"}
        try:
            with open(path) as f:
                d = yaml.safe_load(f) or {}
            info["ok"] = True
            info["primary"] = _model_label(d.get("model"))
            fb = d.get("fallback_providers") or []
            if isinstance(fb, str):
                fb = yaml.safe_load(fb) or []
            info["fallback"] = [_model_label(e) for e in fb if isinstance(e, dict)] if isinstance(fb, list) else []
            aux = d.get("auxiliary", {})
            # auxiliary は facedsのprovider/modelで代表表示。主model継承(inherit)は主モデル表示
            aux_prov = _safe_str((aux.get("title_generation") or {}).get("provider") if isinstance(aux, dict) else "")
            aux_mod = ""
            if isinstance(aux, dict) and isinstance(aux.get("title_generation"), dict):
                aux_mod = _safe_str(aux["title_generation"].get("model"))
            info["aux"] = (
                f"{aux_prov}/{aux_mod}" if aux_prov and aux_mod else (f"{aux_prov} (inherit)" if aux_prov else "—")
            )
            vis = aux.get("vision") or {}
            v_prov = _safe_str(vis.get("provider"))
            v_mod = _safe_str(vis.get("model"))
            info["vision"] = f"{v_prov}/{v_mod}" if v_prov and v_mod else (f"{v_prov} (inherit)" if v_prov else "—")
        except Exception:
            info["ok"] = False
        out[name] = info
    return out


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
<title>Kensho ダッシュボード</title>
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
.warning-banner{{background:#412b1b;border:1px solid {YELLOW};border-radius:8px;padding:10px 14px;margin-bottom:12px;color:{YELLOW};font-size:0.85rem;line-height:1.5}}
.warning-banner strong{{color:{RED}}}
</style>
</head>
<body>
<h1>Kensho ダッシュボード</h1>
<div class="sub">更新: {now} | 収集cron: {"🟢" if cron_running == "yes" else "🔴"} | 応募: {"🟢" if orch_running == "yes" else "🔴"}</div>
<div class="card"><div class="card-title">概要</div><div class="grid-5">
<div class="stat-card"><div class="stat-val" style="color:{GREEN}">{sm["total_items"]}</div><div class="stat-label">件数</div></div>
<div class="stat-card"><div class="stat-val" style="color:{BLUE}">{sm["total_applied"]}</div><div class="stat-label">応募済</div></div>
<div class="stat-card"><div class="stat-val" style="color:{YELLOW}">{sm["total_pending"]}</div><div class="stat-label">未応募</div></div>
<div class="stat-card"><div class="stat-val" style="color:{PURPLE}">{sm["total_today"]}</div><div class="stat-label">本日</div></div>
</div></div>
"""

    # ── 健全性警告バナー（2026-08-28追加）──
    health = data.get("health", {})
    if health.get("warnings"):
        for w in health["warnings"]:
            prefix = "<strong>⚠️ 要対応</strong> " if not health.get("ok", True) else "ℹ️ "
            html += f'<div class="warning-banner">{prefix}{w}</div>\n'

    # deadline
    dl = st.get("deadline_dist", {})
    html += '<div class="card"><div class="card-title">締切</div><div class="grid-5">'
    for label, key, color in [
        ("期限切", "expired", RED),
        ("本日", "today", YELLOW),
        ("3日", "3days", GREEN),
        ("1週", "week", BLUE),
        ("先", "future", GRAY),
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
        adapter, ssid, carrier = ACCOUNT_ADAPTERS.get(ac, ("", "", ""))
        adapter_display = f"[{carrier}] {adapter} ({ssid})" if adapter else "—"
        html += f'<tr><td>{ac} <span class="badge {badge}">{label}</span></td><td class="num">{adapter_display}</td><td class="accent">{at}</td><td class="num">{ta}</td><td class="num">{defer}</td><td class="num">{pending}</td><td class="num">F{f_val} RT{r_val} <3{l_val}</td></tr>'
    html += "</table></div>"

    # ── WiFiテザリング状態（watchdog集計） ──
    wifi = data.get("wifi", {})
    if wifi:

        def _sig_color(v):
            if v is None:
                return GRAY
            if v < 30:
                return RED
            if v < 55:
                return YELLOW
            return GREEN

        def _rssi_color(v):
            if v is None:
                return GRAY
            if v < -85:
                return RED
            if v < -72:
                return YELLOW
            return GREEN

        def _rate_color(r):
            if r is None:
                return GRAY
            if r < 10:
                return GREEN
            if r < 30:
                return YELLOW
            return RED

        html += '<div class="card"><div class="card-title">WiFi テザリング状態（常時監視）</div><table>'
        html += "<tr><td>アカウント</td><td>回線 / アダプタ / SSID</td><td>現信号%</td><td>Rssi(dBm)</td><td>本日</td><td>本日障害率</td><td>7日間障害率</td><td>状態</td></tr>"
        for ac in sorted(wifi.keys()):
            w = wifi[ac]
            # ACCOUNT_ADAPTERSを優先表示（現在の正しい構成）。実測adapter/ssidはwatchdog次回集計まで古いことがある
            acc = ACCOUNT_ADAPTERS.get(ac)
            if acc:
                adapter = acc[0]
                ssid = acc[1]
                carrier = acc[2]
            else:
                adapter = w.get("adapter") or "—"
                ssid = w.get("ssid", "")
                carrier = ""
            carrier_tag = f"[{carrier}] " if carrier else ""
            sig = w.get("signal")
            rssi = w.get("rssi")
            # 有線直結（LAN/RJ45）は Wi-Fi の信号値が存在しない。watchdogログの最終Wi-Fi値を
            # 誤表示しないよう "—" 固定にする（2026-09-13: TankanNotes LAN直結移行に伴う）
            if ssid in ("LAN直結", "RJ45直結"):
                sig = None
                rssi = None
            ok_t = w.get("ok_today", 0)
            fail_t = w.get("fail_today", 0)
            ok7 = w.get("ok_last7d", 0)
            fail7 = w.get("fail_last7d", 0)
            rate_t = fail_t / (ok_t + fail_t) * 100 if (ok_t + fail_t) else None
            rate7 = fail7 / (ok7 + fail7) * 100 if (ok7 + fail7) else None
            sig_disp = f"{sig}%" if sig is not None else "—"
            rssi_disp = f"{rssi}" if rssi is not None else "—"
            sig_cell = f'<span style="color:{_sig_color(sig)};font-weight:700">{sig_disp}</span>'
            rssi_cell = f'<span style="color:{_rssi_color(rssi)}">{rssi_disp}</span>'
            today_cell = f'<span class="accent">{fail_t}</span> / <span class="num">{ok_t}OK</span>'
            rate_t_disp = (
                f'<span style="color:{_rate_color(rate_t)};font-weight:700">{rate_t:.0f}%</span>'
                if rate_t is not None
                else '<span class="num">—</span>'
            )
            rate7_disp = (
                f'<span style="color:{_rate_color(rate7)}">{rate7:.0f}%</span>'
                if rate7 is not None
                else '<span class="num">—</span>'
            )
            cn = w.get("connected_now")
            if cn is True:
                state = '<span class="badge bg-green">接続中</span>'
            elif cn is False:
                state = '<span class="badge bg-red">切断</span>'
            else:
                state = '<span class="num">不明</span>'
            html += (
                f'<tr><td>{ac}</td><td class="num">{carrier_tag}{adapter} ({ssid})</td>'
                f"<td>{sig_cell}</td><td>{rssi_cell}</td>"
                f"<td>{today_cell}</td><td>{rate_t_disp}</td><td>{rate7_disp}</td><td>{state}</td></tr>"
            )
        html += "</table></div>"

    # ── UNUSED（応募停止済み）アカウント ──
    unused = data.get("unused_accounts", [])
    if unused:
        html += '<div class="card"><div class="card-title">応募停止アカウント</div><table>'
        html += "<tr><td>アカウント</td><td>アダプタ / SSID</td><td>状態</td></tr>"
        for u in unused:
            key = u.get("key", "")
            disp = u.get("display", key)
            reason = u.get("reason", "")
            adapter, ssid, carrier = UNUSED_ADAPTERS.get(key, ("—", "—", ""))
            adapter_display = (
                f"[{carrier}] {adapter} ({ssid})" if adapter and carrier else f"{adapter} ({ssid})" if adapter else "—"
            )
            html += f'<tr><td>{disp} <span class="badge bg-red">停止</span></td><td class="num">{adapter_display}</td><td class="num">{reason}</td></tr>'
        html += "</table></div>"

    # ── 日別×アカウント別 応募履歴 ──
    hist = data.get("history")
    if hist and hist.get("days"):
        hist_accounts = [
            ac
            for ac in accounts
            if any(
                ac in hist.get("applied", {}).get(d, {}) or ac in hist.get("actions", {}).get(d, {})
                for d in hist.get("days", [])
            )
        ]
        html += '<div class="card"><div class="card-title">応募履歴（14日）— 応募件数 / 成功アクション数</div><table>'
        html += (
            "<tr><td>日付</td>" + "".join(f'<td style="text-align:center">{ac}</td>' for ac in hist_accounts) + "</tr>"
        )
        for d in reversed(hist["days"]):
            applied_d = hist.get("applied", {}).get(d, {})
            actions_d = hist.get("actions", {}).get(d, {})
            cells = ""
            for ac in hist_accounts:
                a = applied_d.get(ac, 0)
                act = actions_d.get(ac, 0)
                color = "#3fb950" if a >= 15 else ("#d29922" if a >= 8 else ("#58a6ff" if a > 0 else "#8b949e"))
                cells += f'<td style="text-align:center"><span style="color:{color};font-weight:700">{a}</span> <span class="num">/ {act}</span></td>'
            html += f'<tr><td class="num">{d[5:]}</td>{cells}</tr>'
        html += "</table></div>"

    # sources
    sd = st.get("source_dist", {})
    total_src = sum(sd.values()) or 1
    html += '<div class="card"><div class="card-title">収集元</div><div class="grid-2">'
    for src, cnt in sorted(sd.items(), key=lambda x: -x[1]):
        pct = cnt / total_src * 100
        src_disp = "不明" if src == "unknown" else src
        html += f'<div class="stat-card"><div class="stat-val" style="font-size:1.1rem;color:{BLUE}">{cnt}</div><div class="stat-label">{src_disp} ({pct:.0f}%)</div></div>'
    html += "</div></div>"

    # prize
    pd = st.get("prize_dist", {})
    html += '<div class="card"><div class="card-title">賞品価格</div><div class="grid-4">'
    for label, key, color in [
        ("高", "high(3.0)", PURPLE),
        ("中高", "mid_high(2.5)", BLUE),
        ("中", "mid(2.0)", GREEN),
        ("低", "low(1.5)", YELLOW),
        ("無", "none(1.0)", GRAY),
        ("未評価", "unscored", "#484f58"),
    ]:
        val = pd.get(key, 0)
        html += f'<div class="stat-card"><div class="stat-val" style="font-size:1.1rem;color:{color}">{val}</div><div class="stat-label">{label}</div></div>'
    html += "</div></div>"

    # recent runs
    html += '<div class="card"><div class="card-title">直近実行</div><table><tr><td>時刻</td><td>結果</td><td>成功</td><td>エラー</td><td>アカウント</td><td>F</td><td>RP</td><td>❤</td></tr>'
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
    html += f'<div class="note">直近{total_count}回: 成功 <strong class="accent">{ok_count}</strong> / 失敗 <strong style="color:{RED}">{total_count - ok_count}</strong> — 成功率 <strong>{rate}%</strong></div>'
    html += "</div>"

    # ── Hermes LLMプロバイダ構成 ──
    hc = load_hermes_config()
    html += '<div class="card"><div class="card-title">Hermes モデル設定 (config.yaml)</div><table>'
    html += "<tr><td>プロフィール</td><td>主モデル</td><td>フォールバック</td><td>補助</td><td>視覚</td></tr>"
    for name, info in hc.items():
        fb_txt = "<br>".join(info["fallback"]) if info["fallback"] else '<span class="num">—</span>'
        badge = "" if info["ok"] else ' <span class="badge bg-red">設定エラー</span>'
        html += (
            f'<tr><td style="font-weight:600">{name}{badge}</td>'
            f'<td class="accent">{info["primary"]}</td>'
            f'<td class="num">{fb_txt}</td>'
            f'<td class="num">{info["aux"]}</td>'
            f'<td class="num">{info["vision"]}</td></tr>'
        )
    html += "</table>"
    html += '<div class="note">主モデル障害時はフォールバックを順に自動切替。全て <strong class="accent">無料枠</strong>が含まれる（kensho主=Fireworks有料 / tai主=OpenRouter無料）。</div></div>'

    html += f'<div class="footer">Kensho ダッシュボード v5 - {now}</div>'
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
