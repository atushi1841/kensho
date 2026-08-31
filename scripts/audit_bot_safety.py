#!/usr/bin/env python3
"""BOT安全監査 — audit.jsonlに対して以下のBOTシグナルを検査する。

1. 深夜(00:00-07:59)のアクション     → 深夜ガード(no_action_window 00-07)の機能確認
2. 5秒未満のアクション間隔           → ACCOUNT_SAFETY_RULESの連続アクション規制確認
3. 同一ツイート(tweet_id)への複数種アクション → 同一ツイート多重アクション禁止の確認
4. 同一主催者(screen_name)へのフォロー過多 → 単一hostへの集中フォロー監視
5. 同一垢の1時間あたりアクション数   → hourly上限(max_actions_per_hour)確認

使い方:
    python3 scripts/audit_bot_safety.py [date] [--today] [--state]
    date省略時は「昨日」を検査。dateはYYYY-MM-DD形式。
    --today : date省略時の対象を「今日」にする（時間毎監視用）
    --state : 既報シグナルをstateファイルで抑制し、NEW分のみ出力（時間毎監視用）
              date省略+--state のときは --today を意味する
    date省略+フラグなし = 昨日の完全監査（毎日1:00の確定監査と互換）

出力: 問題がなければ何も出さない(終了コード0)。問題があれば該当行を出力(終了コード1)。
      cronのmonitor判定: 出力が空=安全 / 出力あり=要確認。
"""

from __future__ import annotations

import collections
import datetime
import json
import sys
from datetime import timedelta, timezone
from pathlib import Path

ACCOUNTS = ["atushi16", "kudou", "chugakujuken", "zin20120731", "TankanNotes", "inobase1-4", "toushiwatch"]
AUDIT_PATH = Path(__file__).resolve().parent.parent / "data" / "audit.jsonl"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
STATE_PATH = Path(__file__).resolve().parent.parent / "data" / ".audit_bot_safety_state.json"
STATE_KEEP_DAYS = 3  # state保持日数（それより古い日付は掃除）

MIN_ACTION_GAP = 5.0  # 秒。これ未満の2アクション間隔は規制違反


def _load_night_hours() -> set[int]:
    """config.yaml の orchestrator.no_action_window から深夜窓を読む。既定は 00:00-07:59。"""
    try:
        import yaml

        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        win = cfg.get("orchestrator", {}).get("no_action_window")
        if win and len(win) == 2:
            start_h = int(str(win[0])[:2])  # "00:00" → 0
            end_h = int(str(win[1])[:2])  # "07:00" → 7
            if end_h < start_h:
                end_h += 24
            return set(h % 24 for h in range(start_h, end_h))
    except Exception:
        pass
    return set(range(0, 8))


MIN_ACTION_GAP = 5.0  # 秒。これ未満の2アクション間隔は規制違反
MAX_FOLLOWS_PER_OWNER = 4  # 同一主催者への1日当たりフォロー上限(人間らしさ)
MAX_ACTIONS_PER_HOUR: int = 25  # 時間あたり上限(config rate_limits.max_actions_per_hour=25)


def _load_target_date() -> str:
    """対象日付を決定する。--todayがあれば今日、なければ昨日（後方互換）。"""
    use_today = "--today" in sys.argv
    # --state のみの場合は --today を意味する
    if not use_today and "--state" in sys.argv and len(sys.argv) <= 2:
        use_today = True
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        return args[0]
    if use_today:
        return datetime.date.today().isoformat()
    return (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def _load_state() -> dict[str, list[str]]:
    """stateファイルを読み込む。存在しない/破損時は空dict。"""
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, list[str]]) -> None:
    """stateファイルを書き込む。古い日付は掃除。"""
    try:
        today = datetime.date.today()
        keep = {}
        for d, lines in state.items():
            try:
                dt = datetime.date.fromisoformat(d)
                if (today - dt).days <= STATE_KEEP_DAYS:
                    keep[d] = lines
            except (ValueError, TypeError):
                continue
        STATE_PATH.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    date_s = _load_target_date()
    if not AUDIT_PATH.exists():
        print(f"[audit_bot_safety] audit.jsonl なし: {AUDIT_PATH}")
        return 1

    problems: list[str] = []
    # 時系列データ: (timestamp, account, action_type, target, status)
    rows = []
    with open(AUDIT_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("account") not in ACCOUNTS:
                continue
            ts = r.get("timestamp", "")
            # ★ 2026-08-25: timestampはUTC。JST(+9)へ変換し、日付・時刻判定をJSTで行う。
            #   旧実装はUTCのまま比較 → JST昼間を「深夜」と誤警報していた。
            try:
                _jst = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(
                    timezone(timedelta(hours=9))
                )
            except (ValueError, TypeError):
                continue
            if _jst.date().isoformat() != date_s:
                continue
            rows.append((
                ts,
                _jst,  # JST対応 datetime（深夜/過集中判定に使う）
                r.get("account", ""),
                r.get("action_type", ""),
                r.get("target", ""),
                r.get("status", ""),
            ))

    if not rows:
        print(f"[audit_bot_safety] {date_s}: 成功アクションなし")
        return 0  # データがないのは安全側

    rows.sort(key=lambda x: x[0])

    # 1) 深夜アクション（深夜窓は config no_action_window から読む）
    night = collections.Counter()
    night_hours = _load_night_hours()
    for ts, jst, acct, at, tgt, status in rows:
        if jst.hour in night_hours:
            night[(acct, at)] += 1
    if night:
        for (acct, at), c in sorted(night.items()):
            problems.append(f"[深夜] {date_s} {acct} {at} {c}回 (深夜ガード未効? no_action_window 確認)")

    # 2) 5秒未満の間隔
    per_acct = collections.defaultdict(list)
    for ts, jst, acct, at, tgt, status in rows:
        if status == "success":
            per_acct[acct].append(jst)
    for acct, dts in per_acct.items():
        prev: datetime.datetime | None = None
        for dt in dts:
            if prev is not None:
                gap = (dt - prev).total_seconds()
                if gap < MIN_ACTION_GAP:
                    problems.append(f"[連続] {date_s} {acct} アクション間隔 {gap:.1f}s (<{MIN_ACTION_GAP}s)")
            prev = dt

    # 3) 同一ツイート(tweet_id)への複数種アクション
    #   ★ 2026-08-29: フォロー/RT/いいねの複数実行は当選条件（フォロー&RT&いいね）を
    #   満たすために必要な正常行動のため、シグナルにしない（ユーザー定義）。
    #   ただし「リプライ+他のアクション」は絶対ルール（いいね＋リプライ同時NG）違反なので検出する。
    tweet_actions: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for ts, jst, acct, at, tgt, status in rows:
        if status == "success" and str(tgt).isdigit():
            tweet_actions[(acct, tgt)].add(at)
    for (acct, tgt), kinds in tweet_actions.items():
        if len(kinds) >= 2 and "reply" in kinds:
            problems.append(f"[多重] {date_s} {acct} 同一ツイート{tgt}にリプライを含む複数アクション {sorted(kinds)}")

    # 4) 同一主催者へのフォロー過多
    owner_follows = collections.Counter()
    for ts, jst, acct, at, tgt, status in rows:
        if at == "follow" and status == "success" and not str(tgt).isdigit():
            owner_follows[(acct, tgt)] += 1
    for (acct, owner), c in owner_follows.items():
        if c > MAX_FOLLOWS_PER_OWNER:
            problems.append(f"[過フォロー] {date_s} {acct} → {owner} フォロー{c}回 (上限{MAX_FOLLOWS_PER_OWNER})")

    # 5) 1時間あたりアクション数
    hourly = collections.Counter()
    for ts, jst, acct, at, tgt, status in rows:
        if status == "success":
            hourly[(acct, jst.strftime("%H"))] += 1
    for (acct, hh), c in hourly.items():
        if c > MAX_ACTIONS_PER_HOUR:
            problems.append(f"[過集中] {date_s} {acct} {hh}時台に{c}アクション (上限{MAX_ACTIONS_PER_HOUR}/時)")

    # ★ 2026-08-27: --state 時は既報シグナルを抑制し、NEW分のみ報告（時間毎監視用）
    if "--state" in sys.argv:
        state = _load_state()
        known = set(state.get(date_s, []))
        new_problems = [p for p in problems if p not in known]
        if problems:
            state[date_s] = sorted(set(known) | set(problems))
            _save_state(state)
        problems = new_problems

    if problems:
        print(f"[audit_bot_safety] {date_s}: {len(problems)}件のBOTシグナル検出")
        for p in problems:
            print("  " + p)
        return 1

    print(f"[audit_bot_safety] {date_s}: BOTシグナルなし (深夜ゼロ・連続なし・単独アクション)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
