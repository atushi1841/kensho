#!/usr/bin/env python3
"""BOT安全監査 — audit.jsonlに対して以下のBOTシグナルを検査する。

1. 深夜(00:00-07:59)のアクション     → 深夜ガード(no_action_window 00-07)の機能確認
2. 5秒未満のアクション間隔           → ACCOUNT_SAFETY_RULESの連続アクション規制確認
3. 同一ツイート(tweet_id)への複数種アクション → 同一ツイート多重アクション禁止の確認
4. 同一主催者(screen_name)へのフォロー過多 → 単一hostへの集中フォロー監視
5. 同一垢の1時間あたりアクション数   → hourly上限(max_actions_per_hour)確認
6. 日跨ぎ規則性(直近7日)             → 同一分(HH:MM)の反復日数・日次件数CVの正規性シグナル監視
   (critic v143 / research-20260913.md 提案B。X検出は「量より規則性」。
   読み取り専用監査であり、応募ロジックや config.yaml の batch_jitter_minutes は本監査の対象外)
   閾値の根拠（cron */15 グリッド + stagger 0〜9分の設計エンベロープからの導出）は
   下部 REGULARITY_* の定数コメントを参照（t_3f48a43e で再校正）。

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
import re
import statistics
import sys
from datetime import timedelta, timezone
from pathlib import Path

ACCOUNTS = ["atushi16", "kudou", "zin20120731", "TankanNotes", "inobase1-4", "toushiwatch"]
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
# ★ t_33113bb7 (B): MAX_ACTIONS_PER_HOUR の hardcoded 25 を廃止。
#   config.yaml rate_limits.max_actions_per_hour を参照する。設定読込失敗時のフォールバックは25。
def _load_max_actions_per_hour() -> int:
    """config.yaml の rate_limits.max_actions_per_hour を読み込む（フォールバック25）。"""
    try:
        import yaml  # noqa: PLC0415

        cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        v = cfg.get("rate_limits", {}).get("max_actions_per_hour")
        if v is not None:
            return int(v)
    except Exception:
        pass
    return 25

# critic v143: 検査6 日跨ぎ規則性（research-20260913.md 提案B、直近7日、読み取り専用監査）
#
# ── 閾値の根拠（設計エンベロープからの導出 / t_3f48a43e 再校正 2026-09-24） ──
# 設計エンベロープ: 応募セッションは cron `*/15`（:00/:15/:30/:45 分のグリッド）で起動し、
#   実行開始の stagger は 0〜9分（kensho-auto-apply.sh: STAGGER_MOD=${KENSO_STAGGER_MOD:-10}）。
#   よって「同一バッチ枠」の日次初動分は [B, B+9] の10値に収まり、その一様乱数の母集団
#   stdevは 9/√12 ≒ 2.6分。つまり stdev<2.5分 は「設計上到達可能」（旧コメントの『到達不能』
#   は誤り）。単一枠モデルのシミュレーション（2026-09-24, 20万試行）では 7日窓の 41%/垢/週 が
#   stdev<2.5 に入る。→ 生stdevは設計外の指紋にならないため発火条件から外し診断表示のみに降格。
# 発火条件は次の2つのみ（いずれも「設計エンベロープ外の指紋」）:
#   (1) REGULARITY_REPEAT_DAYS_MIN=4: 7日窓で同一分(HH:MM)が4日以上。staggerが乱数である限り
#       単一枠仮定でも発生率 2.7%/垢/週（2枠混在で 0.4%）。実データ12窓（2026-09-13〜24）の
#       垢別最大反復は2日、直近7日窓（終端09-24）でも atushi16/kudou/TankanNotes すべて2日
#       → 余裕2倍。7日すべて同一分（機械的正確さを注入したfixture）は当然 >=4 で発火する。
#   (2) REGULARITY_COUNT_CV=0.01: 日次件数がほぼ完全に同数（量の完全固定）。実測CVは
#       0.144〜0.285（同窓）→ 余裕14倍。旧値0.15は「日次件数が固定設計」のため恒常的に
#       下回り偽陽性100%だった（atushi16 CV0.07 / TankanNotes CV0.03 実測）。
REGULARITY_WINDOW_DAYS = 7  # 直近7日（対象日を含む）
REGULARITY_MIN_DAYS = 3  # この日数未満なら統計不能として判定しない
REGULARITY_REPEAT_DAYS_MIN = 4  # 同一分(HH:MM)がこの日数以上出現 → 正規性シグナル
REGULARITY_COUNT_CV = 0.01  # 日次件数のCVがこれ未満 → 正規性シグナル（ほぼ完全固定のみ）


def _regularity_signals(date_s: str) -> list[str]:
    """検査6: 直近7日の垢別『初動時刻の反復パターン』『日次件数のCV』から、設計エンベロープ
    （cron */15 グリッド + stagger 0〜9分）から外れた機械的パターンを検出する。

    発火条件: (1) 同一分(HH:MM)が REGULARITY_REPEAT_DAYS_MIN 日以上＝stagger乱数が実質無効、
    (2) 日次件数CV < REGULARITY_COUNT_CV＝量が完全固定。初動stdevは診断値であり発火条件では
    ない（根拠は上部の閾値コメント）。読み取り専用: 応募ロジック・config.yaml には触れない。
    """
    try:
        end = datetime.date.fromisoformat(date_s)
    except ValueError:
        return []
    window = {(end - timedelta(days=i)) for i in range(REGULARITY_WINDOW_DAYS)}
    first_min: dict[str, dict[datetime.date, int]] = collections.defaultdict(dict)
    counts: dict[str, dict[datetime.date, int]] = collections.defaultdict(dict)
    try:
        f = open(AUDIT_PATH, encoding="utf-8")
    except OSError:
        return []
    with f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            acct = r.get("account")
            if acct not in ACCOUNTS:
                continue
            ts = r.get("timestamp", "")
            try:
                j = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=9)))
            except (ValueError, TypeError):
                continue
            d = j.date()
            if d not in window:
                continue
            m = j.hour * 60 + j.minute
            if d not in first_min[acct] or m < first_min[acct][d]:
                first_min[acct][d] = m
            counts[acct][d] = counts[acct].get(d, 0) + 1

    signals: list[str] = []
    for acct in ACCOUNTS:
        # 初動 = 当該日の全監査行（status不問）の最小時刻(JST, 分)。件数 = 同全行数。
        starts = [first_min[acct][d] for d in sorted(first_min[acct])]
        days_n = len(starts)
        if days_n < REGULARITY_MIN_DAYS:
            continue  # データ不足（新垢・稼働停止期間など）は判定しない

        cs = [counts[acct][d] for d in sorted(counts[acct])]

        # (1) 同一分(HH:MM)の反復日数 — 設計外の指紋（stagger乱数が実質無効化されている）
        repeated = {m: c for m, c in collections.Counter(starts).items()
                    if c >= REGULARITY_REPEAT_DAYS_MIN}
        # (2) 日次件数CV — 量がほぼ完全固定されている
        cv_s = (statistics.pstdev(cs) / statistics.mean(cs)) if cs and statistics.mean(cs) > 0 else float("inf")
        # 診断値（発火条件ではない）: 初動stdev・件数mean
        stdev_s = statistics.pstdev(starts) if days_n >= 2 else float("inf")

        if not repeated and cv_s >= REGULARITY_COUNT_CV:
            continue

        reasons: list[str] = []
        for minute, cnt in sorted(repeated.items()):
            reasons.append(
                f"初動{minute // 60:02d}:{minute % 60:02d}が{days_n}日中{cnt}日一致"
                f"（stagger 0〜9分では設計上起こらない機械的パターン）"
            )
        if cv_s < REGULARITY_COUNT_CV:
            reasons.append(f"件数CV{cv_s:.3f}(<{REGULARITY_COUNT_CV}) - 日次件数がほぼ完全固定")
        signals.append(
            f"[正規性] {date_s} {acct} "
            + "・".join(reasons)
            + f" (診断: 初動stdev{stdev_s:.1f}分・件数mean{statistics.mean(cs):.0f}"
            + " → batch時刻ジッタ改修は別カードでGO提案)"
        )
    return signals


def _dedupe_key(problem: str) -> str:
    """--state（時間毎監視）の既報抑制キーを作る。

    旧実装は問題文全体をキーにしていたため、診断値（件数mean など）が run ごとに微動する
    だけで同一パターンが別シグナル扱いされ、state に重複追記＋毎時再通知されていた
    （実測: 09-23 kudou は stdev9.9固定のまま mean 違いで4件記録）。
    検査6(正規性)のキーは「対象日 + 垢 + 検出種別 + 該当分」に正規化し、可変の診断値
    （stdev/CV/mean/一致日数）を除去する。検査1〜5の行は同一性が明確なため原文をキーにする。
    """
    if not problem.startswith("[正規性]"):
        return problem
    key = problem.split(" (診断:", 1)[0]
    key = re.sub(r"\d+日一致", "N日一致", key)
    key = re.sub(r"件数CV[\d.]+\(<[\d.]+\)", "件数CV", key)
    return key


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
    """stateファイルを書き込む。古い日付は掃除。

    格納するのは `_dedupe_key()` で正規化したキー（可変の診断値を含まない）。
    これにより同一パターンが run ごとに別シグナルとして再追記・再通知されない。
    """
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
    #   ★ 2026-08-29: フォロー/RT/いいねの複数実行は当選条件（フォロー&RT&いいね）を満たすために必要な正常行動のため、シグナルにしない（ユーザー定義）。
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
    # ★ t_33113bb7 (B): 閾値は config.yaml rate_limits.max_actions_per_hour から動的読込。
    #   従来はモジュール定数 MAX_ACTIONS_PER_HOUR=25 の hardcoded で、
    #   config 側が 15 に下げても監査は旧閾値25のまま（実測で15→25の乖離が検出できず）。
    _max_per_hour: int = _load_max_actions_per_hour()
    hourly = collections.Counter()
    for ts, jst, acct, at, tgt, status in rows:
        if status == "success":
            hourly[(acct, jst.strftime("%H"))] += 1
    for (acct, hh), c in hourly.items():
        if c > _max_per_hour:
            problems.append(f"[過集中] {date_s} {acct} {hh}時台に{c}アクション (上限{_max_per_hour}/時)")

    # 6) 日跨ぎ規則性（critic v143 提案B・直近7日、読み取り専用）
    problems.extend(_regularity_signals(date_s))

    # ★ 2026-08-27: --state 時は既報シグナルを抑制し、NEW分のみ報告（時間毎監視用）
    #   ★ 2026-09-24 (t_3f48a43e): キーを _dedupe_key() による正規化キーへ変更。
    #     旧実装は問題文全体（件数mean等の可変診断値を含む）をキーにしていたため、
    #     同一パターンが run ごとに別物として再追記・毎時再通知されていた（鳴り続け）。
    if "--state" in sys.argv:
        state = _load_state()
        known = set(state.get(date_s, []))
        keys = [_dedupe_key(p) for p in problems]
        new_problems = [p for p, k in zip(problems, keys) if k not in known]
        if problems:
            state[date_s] = sorted(set(known) | set(keys))
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