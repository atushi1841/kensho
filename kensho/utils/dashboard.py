"""
Kensho Dashboard — 応募統計ダッシュボード生成
v1.0: collected.json + dm_wins.json からHTMLレポートを生成

使い方:
    python -m kensho.utils.dashboard            # デフォルト出力
    python -m kensho.utils.dashboard --open      # ブラウザで開く
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from kensho.core.config import load as load_config

DATA_DIR: Path | None = None


def _get_data_dir() -> Path:
    global DATA_DIR
    if DATA_DIR is None:
        cfg = load_config()
        DATA_DIR = Path(cfg["general"]["project_dir"]) / "data"
    return DATA_DIR


def _load_json(path: Path) -> dict | list:
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {} if path.suffix == ".json" and "wins" not in path.name else []
    return {} if "wins" not in path.name else []


# ── データ収集 ──


def collect_stats(collected_path: Path | None = None, dm_wins_path: Path | None = None) -> dict:
    """全統計を収集"""
    frozen_accounts = set()
    data_dir = _get_data_dir()

    collected_path = collected_path or data_dir / "collected.json"
    dm_wins_path = dm_wins_path or data_dir / "dm_wins.json"

    raw = _load_json(collected_path)
    dm_wins = _load_json(dm_wins_path)

    # collected.json の構造： {"collected": [{...}, ...]}
    if isinstance(raw, dict):
        items = raw.get("collected", [])
        if not items:
            items = [v for v in raw.values() if isinstance(v, dict) and "x_url" in v]
    elif isinstance(raw, list):
        items = [it for it in raw if isinstance(it, dict)]
    else:
        items = []

    from kensho.application.applier import _is_deferred

    stats: dict[str, Any] = {
        "total_items": len(items),
        "accounts": defaultdict(
            lambda: {
                "applied": 0,
                "pending": 0,
                "results": Counter(),
                "daily": Counter(),
                "by_result": Counter(),
            }
        ),
        "results_summary": Counter(),
        "dm_wins": defaultdict(list),
        "daily_totals": Counter(),
        "generated_at": datetime.now().isoformat(),
        "errors": [],
    }

    # 応募統計
    for item in items:
        if not isinstance(item, dict):
            continue
        applied = item.get("applied", {})
        results = item.get("results", {})

        for acct_key in applied.keys():
            val = applied.get(acct_key)
            if isinstance(val, str) and val:
                if not _is_deferred(val):
                    stats["accounts"][acct_key]["applied"] += 1

                    # 日次カウント
                    try:
                        day = datetime.fromisoformat(val).strftime("%Y-%m-%d")
                        stats["accounts"][acct_key]["daily"][day] += 1
                        stats["daily_totals"][day] += 1
                    except Exception:
                        pass

                    # 結果
                    result = results.get(acct_key, "unknown")
                    stats["accounts"][acct_key]["results"][result] += 1
                    stats["results_summary"][result] += 1
            else:
                stats["accounts"][acct_key]["pending"] += 1

    # 当選DM
    if isinstance(dm_wins, dict):
        for acct_key, entries in dm_wins.items():
            stats["dm_wins"][acct_key] = entries

    # アカウント別サマリー
    stats["account_summary"] = {}
    for acct_key, data in stats["accounts"].items():
        if acct_key in frozen_accounts:
            continue
        total = data["applied"] + data["pending"]
        ok_count = data["results"].get("ok", 0)
        total_results = sum(data["results"].values())
        error_count = total_results - ok_count
        error_rate = (error_count / total_results * 100) if total_results > 0 else 0.0
        stats["account_summary"][acct_key] = {
            "total": total,
            "applied": data["applied"],
            "pending": data["pending"],
            "ok": ok_count,
            "error_count": error_count,
            "error_rate": error_rate,
            "errors": {k: v for k, v in data["results"].items() if k != "ok" and k != "unknown"},
        }

    # アカウント健全性
    stats["health"] = {}
    for acct_key, data in stats["accounts"].items():
        if acct_key in frozen_accounts:
            continue
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_count = data["daily"].get(today_str, 0)
        total_results = sum(data["results"].values())
        err_rate = 0.0
        if total_results > 0:
            errors_only = total_results - data["results"].get("ok", 0)
            err_rate = errors_only / total_results

        if err_rate > 0.5:
            status = "🔴 要注意"
        elif err_rate > 0.2:
            status = "🟡 やや不良"
        elif today_count == 0 and data["applied"] > 0:
            status = "🟢 休止中"
        else:
            status = "🟢 正常"

        stats["health"][acct_key] = {
            "today": today_count,
            "error_rate": round(err_rate * 100, 1),
            "status": status,
        }

    return stats


# ── HTML生成 ──


def _color_for_result(result: str) -> str:
    if result == "ok":
        return "#28a745"
    elif result in ("tweet_deleted", "account_suspended", "page_not_found"):
        return "#dc3545"
    elif result == "tweet_unavailable":
        return "#ffc107"
    elif result == "goto_failed":
        return "#fd7e14"
    return "#6c757d"


def _label_for_result(result: str) -> str:
    labels = {
        "ok": "正常",
        "tweet_deleted": "削除",
        "account_suspended": "停止",
        "page_not_found": "不存在",
        "tweet_unavailable": "利用不可",
        "tweet_withheld": "非公開",
        "goto_failed": "遷移失敗",
        "unknown": "未分類",
    }
    return labels.get(result, result)


def generate_html(stats: dict) -> str:
    """統計データからダッシュボードHTMLを生成"""
    account_summary = stats["account_summary"]
    dm_wins = stats["dm_wins"]
    daily_totals = stats["daily_totals"]
    results_summary = stats["results_summary"]
    health_data = stats.get("health", {})

    # 集計値
    total_applied = sum(a["applied"] for a in account_summary.values())
    total_ok = sum(a["ok"] for a in account_summary.values())
    total_items = stats["total_items"]
    success_rate = f"{total_ok / total_applied * 100:.1f}" if total_applied > 0 else "N/A"

    # 結果内訳テーブル行
    result_rows = ""
    for acct_key, data in sorted(account_summary.items()):
        err_detail = " ".join(f"{_label_for_result(k)}={v}" for k, v in data["errors"].items())
        result_rows += f"""
        <tr>
            <td>@{acct_key}</td>
            <td>{data["applied"]}</td>
            <td>{data["pending"]}</td>
            <td>{data["ok"]}</td>
            <td>{err_detail if err_detail else "-"}</td>
            <td>{"{:d}".format(data["ok"] / data["applied"] * 100 if data["applied"] > 0 else 0)}%</td>
        </tr>"""

    # 結果内訳（全体）
    result_detail_rows = ""
    for result, count in sorted(results_summary.items(), key=lambda x: -x[1]):
        result_detail_rows += f"""
        <tr>
            <td>{_label_for_result(result)}</td>
            <td>{count}</td>
            <td style="color:{_color_for_result(result)}">●</td>
        </tr>"""

    # 日次活動行
    daily_rows = ""
    sorted_days = sorted(daily_totals.keys(), reverse=True)[:30]
    for day in sorted_days:
        daily_rows += f"""
        <tr>
            <td>{day}</td>
            <td>{daily_totals[day]}</td>
        </tr>"""

    # アカウント健全性行
    health_rows = ""
    for acct_key, h in sorted(health_data.items()):
        health_rows += f"""
        <tr>
            <td>@{acct_key}</td>
            <td>{h["today"]}</td>
            <td>{h["error_rate"]}%</td>
            <td>{h["status"]}</td>
        </tr>"""
    dm_rows = ""
    all_wins = []
    for acct_key, entries in dm_wins.items():
        for entry in entries:
            all_wins.append({**entry, "acct": acct_key})
    all_wins.sort(key=lambda x: x.get("detected_at", ""), reverse=True)
    for w in all_wins[:50]:
        sender = w.get("sender", "不明")
        detected = w.get("detected_at", "")[:19]
        acct = w.get("acct", w.get("account_key", "?"))
        dm_rows += f"""
        <tr>
            <td>{detected}</td>
            <td>@{acct}</td>
            <td>{sender}</td>
            <td>{sender}</td>
        </tr>"""

    dm_count = len(all_wins)
    dm_row_style = "" if dm_rows else 'style="display:none"'

    # アイコンフォント（HTML内SVGで代用）
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kensho 応募ダッシュボード</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, 'Helvetica Neue', 'Segoe UI', sans-serif;
       background: #0d1117; color: #c9d1d9; padding: 24px; }}
h1 {{ font-size: 1.5rem; color: #58a6ff; margin-bottom: 20px; }}
h2 {{ font-size: 1.1rem; color: #8b949e; margin: 24px 0 12px;
       border-bottom: 1px solid #21262d; padding-bottom: 6px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
         gap: 12px; margin-bottom: 20px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
         padding: 16px; text-align: center; }}
.card .value {{ font-size: 1.8rem; font-weight: 700; color: #f0f6fc; }}
.card .label {{ font-size: 0.8rem; color: #8b949e; margin-top: 4px; }}
.card.green .value {{ color: #3fb950; }}
.card.red .value {{ color: #f85149; }}
.card.yellow .value {{ color: #d29922; }}
.card.blue .value {{ color: #58a6ff; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #21262d;
          font-size: 0.88rem; }}
th {{ color: #8b949e; font-weight: 600; background: #161b22; }}
td {{ color: #c9d1d9; }}
tr:hover td {{ background: #1c2128; }}
.footer {{ margin-top: 24px; font-size: 0.78rem; color: #484f58;
           text-align: center; }}
.section {{ margin-bottom: 28px; }}
</style>
</head>
<body>
<h1>📊 Kensho 応募ダッシュボード</h1>
<p style="color:#8b949e;margin-bottom:20px;font-size:0.88rem">
    生成: {stats["generated_at"][:19]}
</p>

<div class="grid">
    <div class="card blue">
        <div class="value">{total_applied}</div>
        <div class="label">総応募</div>
    </div>
    <div class="card green">
        <div class="value">{total_ok}</div>
        <div class="label">正常成立</div>
    </div>
    <div class="card blue">
        <div class="value">{total_items}</div>
        <div class="label">収集件数</div>
    </div>
    <div class="card green">
        <div class="value">{success_rate}%</div>
        <div class="label">成功率</div>
    </div>
    <div class="card green">
        <div class="value">{dm_count}</div>
        <div class="label">当選DM</div>
    </div>
</div>

<div class="section">
<h2>📋 アカウント別応募状況</h2>
<table>
<thead>
<tr><th>アカウント</th><th>応募</th><th>未処理</th><th>正常</th><th>エラー</th><th>成功率</th></tr>
</thead>
<tbody>
{result_rows}
</tbody>
</table>
</div>

<div class="section">
<h2>📈 結果内訳</h2>
<table>
<thead>
<tr><th>結果</th><th>件数</th><th></th></tr>
</thead>
<tbody>
{result_detail_rows}
</tbody>
</table>
</div>

<div class="section">
<h2>📅 最近の活動（日次）</h2>
<table>
<thead>
<tr><th>日付</th><th>応募数</th></tr>
</thead>
<tbody>
{daily_rows}
</tbody>
</table>
</div>

<div class="section">
<h2>❤️ アカウント健全性</h2>
<table>
<thead>
<tr><th>アカウント</th><th>今日の応募</th><th>エラー率</th><th>状態</th></tr>
</thead>
<tbody>
{health_rows}
</tbody>
</table>
</div>

<div class="section" {dm_row_style}>
<h2>🏆 当選DM</h2>
<table>
<thead>
<tr><th>検出日時</th><th>アカウント</th><th>送信者</th><th>メッセージ</th></tr>
</thead>
<tbody>
{dm_rows}
</tbody>
</table>
</div>

<div class="footer">
Kensho Dashboard v1.0 &mdash; {datetime.now().strftime("%Y-%m-%d %H:%M")}
</div>
</body>
</html>"""
    return html


def generate_dashboard(output_path: str | None = None, open_browser: bool = False) -> str:
    """ダッシュボードHTMLを生成してファイル保存"""
    data_dir = _get_data_dir()

    if output_path is None:
        output_path = str(data_dir / "dashboard.html")

    print("[Dashboard] 統計収集...")
    stats = collect_stats()
    print("[Dashboard] HTML生成...")
    html = generate_html(stats)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    total_applied = sum(a["applied"] for a in stats["account_summary"].values())
    total_ok = sum(a["ok"] for a in stats["account_summary"].values())
    dm_count = sum(len(v) for v in stats["dm_wins"].values())

    print(f"[Dashboard] 完了: {output_path}")
    print(f"  総応募: {total_applied} | 正常: {total_ok} | 当選DM: {dm_count}")

    if open_browser:
        abs_path = os.path.abspath(output_path)
        try:
            if sys.platform == "win32":
                os.startfile(abs_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", abs_path])
            else:
                subprocess.run(["xdg-open", abs_path])
        except Exception as e:
            print(f"[Dashboard] ブラウザ起動失敗: {e}")

    return output_path


if __name__ == "__main__":
    open_flag = "--open" in sys.argv or "-o" in sys.argv
    generate_dashboard(open_browser=open_flag)
