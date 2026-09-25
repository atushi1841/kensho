#!/usr/bin/env python3
"""gumroad_freshness — criticレポート用の「Gumroad鮮度・失効」セクション生成器。

背景（2026-09-25 実測 / t_61d0db99 受入基準3）:
 日次収集は Cookie 失効時でも `login_ok: false` の state を書いて exit 0 で終わる。
 失効は revenue-daily.json の warnings に入るが、critic の Telegram レポート
 （kensho-revenue-report.sh）に Gumroad の記述が1行も無く、ユーザーに届かなかった。
 → さらに commit 45be8f0（2026-09-19）が同スクリプトを古い控えで上書きし、
  直近収益データのセクション自体が消失していた（lost update）。

本スクリプトは「読むだけ」で、Cookie等の秘密値は一切出力しない。
失効・24時間超の停滞を検出したら【要対応】を明示する。
レポート用途なので、状態ファイルが無い/壊れている場合も exit 0（レポート自体を殺さない）。

CLI:
  python3 gumroad_freshness.py [--state PATH] [--revenue-daily PATH]
                               [--now ISO8601] [--stale-hours N] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

# 本番の既定パス（テスト・検証は引数で隔離する）
DEFAULT_STATE = "/mnt/d/Project2/kensho/data/gumroad_state.json"
DEFAULT_DAILY = "/mnt/d/Project2/kensho/data/revenue-daily.json"
DEFAULT_STALE_HOURS = 24.0

# 収益記録(revenue-daily.json)とライブstateの乖離検出器（リポジトリ側の単一ソース）
#   2026-09-25 t_3dbc1fbe: 7:05の日次収集後にCookieが復旧しても当日entryが失効のまま残る
#   （実測 login_ok=false(07:11) / ライブ=true(13:19)）ため、修復コマンドをレポートに明示する。
RECONCILE_SCRIPT = "/mnt/d/Project2/kensho/scripts/revenue_record_reconcile.py"
RECONCILE_TIMEOUT_S = 20.0

HEADING = "## 3.5 Gumroad鮮度・失効"


def _divergence(daily_path: str, state_path: str) -> dict[str, object] | None:
    """revenue_record_reconcile --json を呼び、乖離があればその内容を返す（失敗時 None）。"""
    if not os.path.exists(RECONCILE_SCRIPT):
        return None
    import subprocess

    try:
        r = subprocess.run(
            [sys.executable, RECONCILE_SCRIPT, "--daily", daily_path, "--state", state_path, "--json"],
            capture_output=True,
            text=True,
            timeout=RECONCILE_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode not in (0, 1):
        return None
    try:
        payload = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None
    if not isinstance(payload, dict) or not payload.get("diverged"):
        return None
    return payload


def _read_json(path: str) -> object | None:
    """JSONを読む。存在しない/壊れている場合は None（例外にしない）。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _parse_ts(value: object) -> datetime | None:
    """ISO8601文字列を naive datetime として解釈（読めなければ None）。"""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _last_daily_gumroad(path: str) -> dict[str, object]:
    """revenue-daily.json の最終エントリから gumroad 節を取り出す（無ければ空）。"""
    data = _read_json(path)
    if not isinstance(data, list) or not data:
        return {}
    last = data[-1]
    if not isinstance(last, dict):
        return {}
    gum = last.get("gumroad")
    return gum if isinstance(gum, dict) else {}


def build_report(
    state_path: str,
    daily_path: str,
    now: datetime,
    stale_hours: float,
) -> tuple[list[str], dict[str, object]]:
    """セクション行と機械可読サマリを返す。"""
    state = _read_json(state_path)
    if not isinstance(state, dict):
        state = {}
    daily = _last_daily_gumroad(daily_path)

    login_ok = state.get("login_ok")
    if login_ok is None and "login_ok" in daily:
        login_ok = daily.get("login_ok")

    last_success = _parse_ts(state.get("last_success_at") or daily.get("last_success_at"))
    last_attempt = _parse_ts(state.get("last_attempt_at"))

    age_h: float | None = None
    if last_success is not None:
        age_h = max(0.0, (now - last_success).total_seconds() / 3600.0)

    alerts: list[str] = []
    if login_ok is False:
        alerts.append("Gumroadログインセッション失効（Cookie再エクスポートが必要）")
    if last_success is None:
        if state or daily:
            alerts.append("売上データの最終成功時刻が記録に無い（収集停止の疑い）")
    elif age_h is not None and age_h > stale_hours:
        alerts.append(f"売上データの最終成功が{age_h:.1f}時間前（{stale_hours:.0f}時間超＝収集停滞の疑い）")

    # 記録とライブstateの乖離（7:05収集後に復旧したケース）→ 修復コマンドを明示
    divergence = _divergence(daily_path, state_path)
    if divergence is not None:
        diffs = divergence.get("differences")
        keys = (
            ",".join(str(d.get("key")) for d in diffs if isinstance(d, dict))
            if isinstance(diffs, list)
            else ""
        )
        alerts.append(
            f"収益記録がライブ状態と乖離（entry={divergence.get('entry_date')}"
            f" / 記録キー=[{keys}]） → 修復: python3 {RECONCILE_SCRIPT} --apply"
        )

    lines: list[str] = []
    if not state and not daily:
        lines.append("- (gumroad_state.json / revenue-daily.json とも無し — 未収集)")
    else:
        lines.append(f"- login_ok: {login_ok}")
        if last_success is not None:
            lines.append(f"- 最終成功: {last_success.isoformat(timespec='seconds')}（{age_h:.1f}時間前）")
        else:
            lines.append("- 最終成功: 記録なし")
        if last_attempt is not None:
            lines.append(f"- 最終試行: {last_attempt.isoformat(timespec='seconds')}（失効時の記録）")
        src = state if state else daily
        sales = src.get("total_sales", src.get("sales"))
        earnings = src.get("total_earnings_usd", src.get("total_revenue"))
        if sales is not None or earnings is not None:
            money = f"${float(earnings):.2f}" if isinstance(earnings, (int, float)) else "n/a"
            lines.append(f"- 売上: {sales if sales is not None else 'n/a'}件 / {money} USD")
        warns = daily.get("warnings")
        if isinstance(warns, list):
            for w in warns:
                if isinstance(w, str) and ("umroad" in w or "ログイン" in w):
                    lines.append(f"- 収集ログ警告: {w}")

    if alerts:
        for a in alerts:
            lines.append(f"- 【要対応】{a}")
    elif state or daily:
        lines.append(f"- 鮮度: OK（{stale_hours:.0f}時間以内）")
    else:
        lines.append("- 鮮度: 判定不能（判定材料のstateが無い）")

    summary: dict[str, object] = {
        "login_ok": login_ok,
        "last_success_at": last_success.isoformat(timespec="seconds") if last_success else None,
        "last_attempt_at": last_attempt.isoformat(timespec="seconds") if last_attempt else None,
        "age_hours": None if age_h is None else round(age_h, 1),
        "record_diverged": divergence is not None,
        "alerts": alerts,
        "needs_action": bool(alerts),
    }
    return lines, summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gumroad鮮度・失効セクション生成（読み取り専用）")
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--revenue-daily", default=DEFAULT_DAILY)
    ap.add_argument("--now", default=None, help="検証用に現在時刻を固定（ISO8601）")
    ap.add_argument("--stale-hours", type=float, default=DEFAULT_STALE_HOURS)
    ap.add_argument("--json", action="store_true", help="機械可読サマリのみ出力")
    args = ap.parse_args(argv)

    now = _parse_ts(args.now) if args.now else datetime.now()
    if now is None:
        now = datetime.now()

    lines, summary = build_report(args.state, args.revenue_daily, now, args.stale_hours)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(HEADING)
        for line in lines:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())