#!/usr/bin/env python3
"""cron レジストリ守衛（スケジューラ自身の死を帯域外で検知する）。

背景（2026-09-29 実測・約14時間の全cron停止事故）:
  jobs.json が二重ラップ（{'jobs': {'jobs': [...], 'updated_at': ...}}）に壊れ、
  cron/jobs.py の load_jobs() が「IDキー付きマップ」として読み替えた結果
  非dict要素 2件（'jobs', 'updated_at'）を全部スキップして **ジョブ0件** になった。
  - ticker は成功する（heartbeat は新鮮）→ `hermes cron status` は正常と出す
  - 851回も "Skipping 2 non-dict entries" 警告が出たが拾う監視が居ない
  - 検知系（kensho-cron-watchdog / misfire / max-auto-mode-test）は **すべてHermes cronのジョブ** =
    スケジューラが死ぬと同時に自分たちも死ぬ（自己観測の盲点）
  - 結果: 06:32〜20:40 の間、critic/worker/qa は1度も動かず無反応

この守衛は Hermes cron に依存しない（OS crontab から毎30分実行される）。
1. jobs.json の形（`{'jobs': [ ... ], 'updated_at': ...}` であること）を検査
   - 既知の二重ラップ型なら --repair で決定的に1階層剥がして原子的に入替える
2. ジョブ件数 0 件を検知
3. executions.db の最終 claim 時刻が閾値超過（= スケジューラ停止）を検知
4. alerts.log に "Skipping 2 non-dict entries" が出ていないか検知

終了コード: 0=問題なし / 1=問題あり（stdout の内容を notify.sh に渡せる）
使い方:
  python3 scripts/cron_registry_guard.py            # 検査のみ
  python3 scripts/cron_registry_guard.py --repair    # 既知の二重ラップを自動修復
  python3 scripts/cron_registry_guard.py --selftest  # 修復ロジックの自己検証
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))
CRON_DIR = Path("/home/atushi/.hermes/profiles/kensho-sweeps/cron")
JOBS_FILE = CRON_DIR / "jobs.json"
EXEC_DB = CRON_DIR / "executions.db"
ERRORS_LOG = Path("/home/atushi/.hermes/profiles/kensho-sweeps/logs/errors.log")
STATE_FILE = Path("/home/atushi/.hermes/profiles/kensho-sweeps/state/cron_registry_guard_state.json")

# every-5m の firewatch-orphan-killer があるため、これだけ90分間動きが無ければ死亡と断定してよい
STALE_MINUTES = 90
ALERT_COOLDOWN_HOURS = 6


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST)


def _atomic_write_json(path: Path, payload: dict) -> None:
    """mkstemp + fsync + os.replace で原子的に入替える（Hermes本体と同じ方式）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".guard_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def inspect_shape(raw) -> tuple[str, dict | None]:
    """戻り値: (状態, 修復に必要なペイロード or None)。

    ok             … 正規形 {'jobs': [list], 'updated_at': str}
    double_wrapped … {'jobs': {'jobs': [list], 'updated_at': str}}（2026-09-29事故の型）
    unknown        … それ以外（勝手に触らない）
    """
    if not isinstance(raw, dict):
        return "unknown", None
    jobs = raw.get("jobs")
    if isinstance(jobs, list):
        return "ok", None
    if isinstance(jobs, dict):
        inner = jobs.get("jobs")
        if isinstance(inner, list):
            return "double_wrapped", {"jobs": inner, "updated_at": jobs.get("updated_at")}
        if isinstance(inner, dict):
            # 三重以上は推測で直さない
            return "unknown", None
    return "unknown", None


def check_jobs(repair: bool) -> tuple[bool, str]:
    if not JOBS_FILE.exists():
        return False, "🔴 jobs.json が存在しない（cron レジストリ消失の可能性）"
    try:
        raw = json.loads(JOBS_FILE.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # JSON破損
        return False, f"🔴 jobs.json をパースできない: {exc}"

    state, payload = inspect_shape(raw)
    if state == "unknown":
        return False, "🔴 jobs.json の形が未知（手動確認が必要）: " + json.dumps(
            {k: type(v).__name__ for k, v in raw.items()}, ensure_ascii=False
        )

    if state == "double_wrapped":
        n = len(payload["jobs"]) if payload else 0
        if repair:
            assert payload is not None
            _atomic_write_json(JOBS_FILE, payload)
            return False, (
                f"🔴 jobs.json が二重ラップで全ジョブ読込不能（{n}件）→ **1階層剥がして自動修復済**。"
                "以後の火は次ティックから復帰する。"
            )
        return False, (
            f"🔴 jobs.json が二重ラップで全ジョブ読込不能（{n}件）。"
            "`python3 scripts/cron_registry_guard.py --repair` を実行すること。"
        )

    jobs = raw.get("jobs") or []
    active = [j for j in jobs if isinstance(j, dict) and j.get("enabled")]
    if not jobs:
        return False, "🔴 jobs.json のジョブ件数が 0 件"
    if not active:
        return False, f"🔴 有効ジョブが 0 件（登録 {len(jobs)} 件すべて無効）"
    return True, f"✅ jobs.json 正常（登録{len(jobs)}件 / 有効{len(active)}件）"


def check_freshness() -> tuple[bool, str]:
    if not EXEC_DB.exists():
        return False, "🔴 executions.db が存在しない"
    try:
        con = sqlite3.connect(f"file:{EXEC_DB}?mode=ro", uri=True)
        row = con.execute("select max(claimed_at) from executions").fetchone()
        con.close()
    except Exception as exc:
        return False, f"🔴 executions.db を読めない: {exc}"
    if not row or not row[0]:
        return False, "🔴 executions.db に実行痕跡が1件も無い"
    try:
        last = dt.datetime.fromisoformat(row[0])
    except ValueError:
        return False, f"🔴 claimed_at を解釈できない: {row[0]!r}"
    if last.tzinfo is None:
        last = last.replace(tzinfo=JST)
    age = (now_jst() - last).total_seconds() / 60.0
    if age > STALE_MINUTES:
        return False, (
            f"🔴 Hermes cron スケジューラ停止疑い: 最終実行 {last:%m-%d %H:%M} "
            f"（{age:.0f}分前 / 閾値{STALE_MINUTES}分）"
        )
    return True, f"✅ 直近実行 {age:.0f} 分前"


def check_warnings() -> tuple[bool, str]:
    if not ERRORS_LOG.exists():
        return True, "✅ alerts.log なし"
    try:
        with ERRORS_LOG.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(max(0, ERRORS_LOG.stat().st_size - 4_000_000))
            tail = fh.read()
    except Exception as exc:
        return False, f"🔴 alerts.log を読めない: {exc}"
    hits = [ln for ln in tail.splitlines() if "non-dict entries" in ln]
    if not hits:
        return True, "✅ jobs 読込警告なし"
    # 修復（jobs.json の最終書込）より古い警告は歴史として無視する
    try:
        repaired_at = dt.datetime.fromtimestamp(JOBS_FILE.stat().st_mtime, JST)
    except OSError:
        repaired_at = None
    fresh = []
    for ln in hits:
        try:
            seen0 = dt.datetime.strptime(ln[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
        except ValueError:
            continue
        if repaired_at is None or seen0 > repaired_at:
            fresh.append(ln)
    if not fresh:
        return True, f"✅ jobs 読込警告なし（修復 {repaired_at:%m-%d %H:%M} 以降）" if repaired_at else "✅ jobs 読込警告なし"
    hits = fresh
    stamp = hits[-1][:19]
    try:
        seen = dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
    except ValueError:
        seen = now_jst()
    age_h = (now_jst() - seen).total_seconds() / 3600.0
    if age_h <= ALERT_COOLDOWN_HOURS:
        return False, f"🔴 jobs 読込失敗警告 {len(hits)}件（最終 {stamp}）: スケジューラがジョブを読めていない"
    return True, f"✅ jobs 読込警告は古い（最終 {stamp}）"


def should_notify(signature: str) -> bool:
    """同一シグネチャは ALERT_COOLDOWN_HOURS 時間ごとに1回だけ通知する。"""
    now = now_jst()
    state = {}
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        state = {}
    last = state.get(signature)
    if last:
        try:
            if (now - dt.datetime.fromisoformat(last)).total_seconds() < ALERT_COOLDOWN_HOURS * 3600:
                return False
        except ValueError:
            pass
    state[signature] = now.isoformat()
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass
    return True


def run(repair: bool) -> int:
    results = [check_jobs(repair), check_freshness(), check_warnings()]
    bad = [msg for ok, msg in results if not ok]
    lines = [f"[cron_registry_guard {now_jst():%m-%d %H:%M}]"]
    lines += [msg for _, msg in results]
    if not bad:
        return 0
    lines.append("")
    lines.append("対処: jobs.json の形が壊れた場合は --repair、スケジューラ停止は gateway 再起動。")
    text = "\n".join(lines)
    # 問題シグネチャごとにクールダウンして通知
    sig = "|".join(sorted({m.split(":")[0] for m in bad}))
    if should_notify(sig):
        print(text)
        return 1
    return 1  # 問題は残るが通知はクールダウン中 → 出力なしで非ゼロ


def selftest() -> int:
    """修復ロジックを一時ファイルで検証（本番 jobs.json には触らない）。"""
    import shutil

    tmpdir = Path(tempfile.mkdtemp(prefix="guard_selftest_"))
    try:
        good = {"jobs": [{"id": "a", "enabled": True}], "updated_at": "2026-09-29T06:31:54+09:00"}
        wrapped = {"jobs": good}

        st, payload = inspect_shape(good)
        assert st == "ok" and payload is None, st
        st, payload = inspect_shape(wrapped)
        assert st == "double_wrapped", st
        assert payload == good, payload
        st, _ = inspect_shape({"jobs": {"jobs": {"jobs": []}}})
        assert st == "unknown", st
        st, _ = inspect_shape([1, 2])
        assert st == "unknown", st

        # 実際に書き込んで読み直す
        target = tmpdir / "jobs.json"
        _atomic_write_json(target, wrapped)  # 二重ラップ状態を再現
        raw = json.loads(target.read_text(encoding="utf-8"))
        st, payload = inspect_shape(raw)
        assert st == "double_wrapped" and payload is not None
        _atomic_write_json(target, payload)
        raw = json.loads(target.read_text(encoding="utf-8"))
        st, payload = inspect_shape(raw)
        assert st == "ok" and len(raw["jobs"]) == 1, raw.keys()
        print("selftest OK")
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="cron レジストリ守衛（帯域外）")
    ap.add_argument("--repair", action="store_true", help="既知の二重ラップ型を自動修復する")
    ap.add_argument("--selftest", action="store_true", help="修復ロジックの自己検証のみ")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    return run(args.repair)


if __name__ == "__main__":
    sys.exit(main())
