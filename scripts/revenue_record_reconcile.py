#!/usr/bin/env python3
"""revenue_record_reconcile — 日次収益記録(revenue-daily.json)とライブstateの乖離を検出・修復。

背景（2026-09-25 実測 / t_3dbc1fbe）:
  日次収益収集は 7:05 の1回だけ。Cookie失効で `login_ok=false` の entry が書かれた後、
  同日中に Cookie が復旧して収集が成功しても当日 entry は失効のまま残る（記録が実態と食い違う）。

  実測:
    - `data/revenue-daily.json` の 2026-09-25 entry: gumroad.login_ok=false /
      last_success_at=2026-09-25T07:07:35 / warnings=[Gumroadログインセッション失効]
    - 同時点のライブ `data/gumroad_state.json`（13:19更新）: login_ok=true / sales_page_ok=true
    - さらに 07:11 entry は collectors.gumroad_ok=true + login_ok=false の自己矛盾
      （修正 6e8ab13 前のコードの名残）を保持していた

対策の方針:
  - 乖離の定義: 「当日 entry の gumroad 節」と「ライブ state」の差、および
    `collectors.gumroad_ok` と同一規則による再計算値の差。
  - 修復は **ライブ state の値のみから再導出**（値の捏造はしない）。
  - ミラーするキー集合と gumroad_ok 規則は本番 `kensho_revenue_collect` の
    単一ソース（`GUMROAD_STATE_MIRROR_KEYS` / `gumroad_collector_flags`）を import して使う
    （テスト側で再実装しない＝意味論ドリフト防止）。
  - 過去日 entry は触らない（state は最新1日分のみ・entry の date と state の日付一致を必須）。
  - 書き込みは tmp + os.replace の原子的置換（部分書きでJSONを壊さない）。

CLI:
  python3 scripts/revenue_record_reconcile.py            # --check（既定・読み取りのみ）
  python3 scripts/revenue_record_reconcile.py --apply    # 当日entryを修復
  python3 scripts/revenue_record_reconcile.py --json     # 機械可読サマリのみ

終了コード: 0=乖離なし or 修復済み / 1=乖離あり（check時・未修復）
マーカー（grep用）: revenue-reconcile OK|SKIP|DIVERGED|APPLIED
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kensho_revenue_collect import (  # noqa: E402
    GUMROAD_STATE_MIRROR_KEYS,
    gumroad_collector_flags,
    gumroad_ok_flag,
    gumroad_state_fields,
)

DEFAULT_DAILY = "/mnt/d/Project2/kensho/data/revenue-daily.json"
DEFAULT_STATE = "/mnt/d/Project2/kensho/data/gumroad_state.json"

MARK_OK = "revenue-reconcile OK"
MARK_SKIP = "revenue-reconcile SKIP"
MARK_DIVERGED = "revenue-reconcile DIVERGED"
MARK_APPLIED = "revenue-reconcile APPLIED"

EXIT_OK = 0
EXIT_DIVERGED = 1

# 復旧時に消してよい警告（失効系のみ）。他ソースの警告は残す。
STALE_WARNING_MARKERS = ("失効", "Cookie再エクスポート", "再エクスポート")


def _read_json(path: str) -> Any:
    """JSONを読む。無い/壊れている場合は None（例外にしない）。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _parse_ts(value: Any) -> datetime | None:
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


def _day(value: Any) -> str | None:
    """ISO8601文字列から YYYY-MM-DD 部分を取り出す（判定不能なら None）。"""
    ts = _parse_ts(value)
    if ts is not None:
        return ts.date().isoformat()
    if isinstance(value, str) and len(value) >= 10:
        return value[:10]
    return None


def detect(daily_path: str, state_path: str) -> dict[str, Any]:
    """乖離を検出する（読み取りのみ・ファイルは書かない）。"""
    result: dict[str, Any] = {
        "applicable": False,
        "diverged": False,
        "entry_date": None,
        "state_date": None,
        "reason": "",
        "differences": [],
        "collectors_mismatch": False,
        "live": {},
    }
    entries = _read_json(daily_path)
    if not isinstance(entries, list) or not entries:
        result["reason"] = "revenue-daily.json が無い/空/壊れている"
        return result
    last = entries[-1]
    if not isinstance(last, dict):
        result["reason"] = "最終entryがdictでない"
        return result
    entry_date = last.get("date")
    result["entry_date"] = entry_date

    state = _read_json(state_path)
    if not isinstance(state, dict) or not state:
        result["reason"] = "ライブ gumroad_state.json が無い/空/壊れている"
        return result
    state_ts = (
        _parse_ts(state.get("collected_at"))
        or _parse_ts(state.get("last_success_at"))
        or _parse_ts(state.get("last_attempt_at"))
    )
    state_date = _day(state.get("collected_at")) or _day(state.get("last_success_at")) or _day(
        state.get("last_attempt_at")
    )
    result["state_date"] = state_date
    if not entry_date or not state_date:
        result["reason"] = "entry/state の日付が判定できない"
        return result
    if str(entry_date) != str(state_date):
        result["reason"] = f"日付不一致（entry={entry_date} state={state_date}）— 過去日は再導出しない"
        return result

    entry_gum = last.get("gumroad")
    if not isinstance(entry_gum, dict):
        entry_gum = {}
        last["gumroad"] = entry_gum
    entry_ts = _parse_ts(entry_gum.get("collected_at"))
    if entry_ts is not None and state_ts is not None and entry_ts > state_ts:
        result["reason"] = (
            f"ライブstateの方が古い（entry={entry_gum.get('collected_at')} > state={state.get('collected_at')}）"
        )
        return result

    result["applicable"] = True
    live = gumroad_state_fields(state)
    result["live"] = live

    diffs: list[dict[str, Any]] = []
    for key in GUMROAD_STATE_MIRROR_KEYS:
        if key not in live:
            continue
        if key not in entry_gum or entry_gum[key] != live[key]:
            diffs.append({"key": key, "record": entry_gum.get(key, "<無し>"), "live": live[key]})
    collectors = last.get("collectors")
    record_flag = gumroad_ok_flag(dict(entry_gum))
    live_flag = gumroad_ok_flag({**entry_gum, **live})
    rec_flag = collectors.get("gumroad_ok") if isinstance(collectors, dict) else None
    # 乖離の2面: ①記録内の自己矛盾（collectors が自分の gumroad 節と食い違う。
    #   実測 2026-09-25 07:11 entry の collectors.gumroad_ok=true + login_ok=false）
    #   ②修復後の期待値（ライブstate基準）との不一致
    result["collectors_flags"] = {"record": rec_flag, "from_record_gumroad": record_flag, "live": live_flag}
    result["collectors_mismatch"] = isinstance(collectors, dict) and (
        rec_flag != record_flag or rec_flag != live_flag
    )
    result["differences"] = diffs
    result["diverged"] = bool(diffs) or bool(result["collectors_mismatch"])
    if not result["diverged"]:
        result["reason"] = "記録とライブstateは一致"
    else:
        result["reason"] = f"乖離 {len(diffs)}キー" + ("＋collectors.gumroad_ok" if result["collectors_mismatch"] else "")
    return result


def apply(daily_path: str, state_path: str, now: datetime | None = None) -> dict[str, Any]:
    """当日entryの gumroad 節をライブ state から再導出して修復する。"""
    now = now or datetime.now()
    det = detect(daily_path, state_path)
    out: dict[str, Any] = dict(det)
    out["applied"] = False
    if not det["applicable"] or not det["diverged"]:
        return out

    entries = _read_json(daily_path)
    if not isinstance(entries, list) or not entries:
        out["reason"] = "修復時に revenue-daily.json を読めない"
        return out
    last = entries[-1]
    entry_gum = last.get("gumroad")
    if not isinstance(entry_gum, dict):
        entry_gum = {}
        last["gumroad"] = entry_gum
    live = det["live"]

    changed = [d["key"] for d in det["differences"]]
    prev_collected_at = entry_gum.get("collected_at")
    prev_login_ok = entry_gum.get("login_ok")

    entry_gum.update(live)
    flags = gumroad_collector_flags({**entry_gum, **live})
    collectors = last.get("collectors")
    if not isinstance(collectors, dict):
        collectors = {}
        last["collectors"] = collectors
    collectors.update(flags)

    removed: list[str] = []
    warnings = last.get("warnings")
    if live.get("login_ok") is True and isinstance(warnings, list):
        kept: list[Any] = []
        for w in warnings:
            if isinstance(w, str) and any(m in w for m in STALE_WARNING_MARKERS):
                removed.append(w)
            else:
                kept.append(w)
        last["warnings"] = kept

    last["gumroad_reconciled"] = {
        "at": now.isoformat(timespec="seconds"),
        "source": os.path.basename(state_path),
        "state_collected_at": live.get("collected_at"),
        "record_collected_at_before": prev_collected_at,
        "changed_keys": changed,
        "login_ok_before": prev_login_ok,
        "login_ok_after": entry_gum.get("login_ok"),
        "removed_stale_warnings": removed,
        "note": "日次7:05収集後にライブstateが更新されたため当日entryを再導出（scripts/revenue_record_reconcile.py）",
    }

    tmp = f"{daily_path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
    os.replace(tmp, daily_path)

    out["applied"] = True
    out["changed_keys"] = changed
    out["removed_stale_warnings"] = removed
    out["reason"] = f"再導出して修復（{len(changed)}キー・失効warning {len(removed)}件除去）"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="収益記録とライブstateの乖離 検出/修復")
    ap.add_argument("--daily", default=DEFAULT_DAILY)
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--apply", action="store_true", help="当日entryをライブstateから再導出して修復する")
    ap.add_argument("--json", action="store_true", help="機械可読サマリのみ出力")
    ap.add_argument("--now", default=None, help="検証用に現在時刻を固定（ISO8601）")
    args = ap.parse_args(argv)

    now = _parse_ts(args.now) if args.now else None
    res = apply(args.daily, args.state, now) if args.apply else detect(args.daily, args.state)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, default=str))
    else:
        date_note = f"entry_date={res.get('entry_date')} state_date={res.get('state_date')}"
        if not res["applicable"]:
            print(f"{MARK_SKIP} {date_note} — {res['reason']}")
        elif res.get("applied"):
            print(
                f"{MARK_APPLIED} {date_note} — {res['reason']} "
                f"changed_keys={res.get('changed_keys')}"
            )
        elif res["diverged"]:
            keys = ",".join(d["key"] for d in res["differences"])
            print(f"{MARK_DIVERGED} {date_note} keys=[{keys}] collectors_mismatch={res['collectors_mismatch']}")
            for d in res["differences"]:
                print(f"  - {d['key']}: 記録={d['record']!r} / ライブ={d['live']!r}")
        else:
            print(f"{MARK_OK} {date_note} — {res['reason']}")

    if res["applicable"] and res["diverged"] and not res.get("applied"):
        return EXIT_DIVERGED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
