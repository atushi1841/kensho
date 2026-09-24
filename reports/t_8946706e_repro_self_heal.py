#!/usr/bin/env python3
"""t_8946706e 再現スクリプト（読み取り専用・本番には触れない）.

`self_heal.py` の修正前（git ref の HEAD 版）と修正後（作業ツリー版）を
**同じ入力で** 走らせ、BOTシグナル増幅の原因だった3つの挙動を before/after で実測する。

  1. セッション失効（no_auth_session）の失敗に何回リトライするか
     → 旧: attempts=3（ブラウザ起動＋Xログイン再試行が3回）/ 新: attempts=1（即停止＋当該垢のみ遮断）
  2. 毎時cron（run間隔60分 > cooldown30分）で failure ceiling が発動するか
     → 旧: 3連続失敗しても遮断されない（first_fail_time 固定）/ 新: 3回目で遮断
  3. failure ceiling のキーが垢単位か（1垢の失効が他垢の成功でリセットされないか）
     → 旧: apply 全体キー → 他垢の成功でリセット（遮断不発）/ 新: apply:<acct> ごとに独立

使い方:
    python reports/t_8946706e_repro_self_heal.py [git-ref]
    # git-ref 既定 = HEAD（= 修正前の self_heal.py）
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
TASK = "t_8946706e"
_BASE = {"min_delay_sec": 0, "max_delay_sec": 0, "notify_on_error": False,
         "max_attempts": 3, "failure_ceiling_consecutive": 3,
         "failure_ceiling_cooldown_minutes": 30}


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_before(ref: str, dest: Path) -> Any:
    """git ref から取り出した修正前 self_heal.py を読み込む。"""
    src = subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:kensho/core/self_heal.py"],
                         capture_output=True, text=True, check=True).stdout
    dest.write_text(src, encoding="utf-8")
    return _load_module(dest, "self_heal_before")


def load_after() -> Any:
    return _load_module(REPO / "kensho" / "core" / "self_heal.py", "self_heal_after")


def _mkproj(root: Path, name: str) -> Path:
    p = root / name
    (p / "data").mkdir(parents=True, exist_ok=True)
    (p / "logs").mkdir(parents=True, exist_ok=True)
    return p


def _cfg(proj: Path, **over: Any) -> dict[str, Any]:
    sh = dict(_BASE)
    sh.update(over)
    return {"general": {"project_dir": str(proj)}, "self_healing": sh}


def install_clock(mod: Any, offset: list[timedelta]) -> None:
    """`datetime.now()` を任意時刻にずらす（run間隔60分を実時間を待たずに再現する）。"""

    class _Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> "datetime":  # type: ignore[override]
            return datetime.now(tz) + offset[0]

    mod.datetime = _Clock


def _ceiling_state(proj: Path) -> dict[str, Any]:
    path = proj / "data" / "self_heal_state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("ceilings", {})


# ── scenario 1: セッション失効への盲目的リトライ ────────────────────────────
def scenario_fatal_retry(mod: Any, root: Path) -> dict[str, Any]:
    proj = _mkproj(root, "fatal")
    loop = mod.SelfHealingLoop(cfg=_cfg(proj), pipeline="apply",
                               context={"key": "apply:zin20120731"})
    calls: list[int] = []

    def op() -> tuple[int, int]:
        calls.append(1)
        return (0, 1)  # apply 0 success 1 errors（= セッション失効で1件も成功しない）

    def validator(value: Any = None, *, exception: Any = None, context: Any = None) -> Any:
        # 修正前の applier はこの失敗を「一般エラー（recoverable=True）」として返していた
        return mod.RecoverySignal(kind="no_auth_session", recoverable=True, severity="error",
                                  message="apply 0 success 1 errors (no_auth_session)")

    r = loop.run(op, validator=validator, recoveries=["jitter_retry"])
    st = _ceiling_state(proj)
    return {
        "operation_calls(browser+login回数)": len(calls),
        "attempts": r.attempts,
        "events": [e.action for e in loop.events],
        "blocked(apply:zin20120731)": loop.is_blocked("apply:zin20120731"),
        "ceilings": {k: v.get("count") for k, v in st.items()},
    }


# ── scenario 2: 毎時cronでも ceiling が発動するか ──────────────────────────
def scenario_hourly_ceiling(mod: Any, root: Path) -> dict[str, Any]:
    proj = _mkproj(root, "hourly")
    offset = [timedelta(0)]
    install_clock(mod, offset)
    history: list[dict[str, Any]] = []
    for hour in range(3):
        offset[0] = timedelta(hours=hour)  # 09:00 / 10:00 / 11:00
        loop = mod.SelfHealingLoop(cfg=_cfg(proj, max_attempts=1), pipeline="collection")
        loop.run(lambda: (_ for _ in ()).throw(RuntimeError("collection boom")))
        st = _ceiling_state(proj)
        entry = st.get("collection", {})
        history.append({
            "run": f"T+{hour}h",
            "count": entry.get("count"),
            "first_fail_time": entry.get("first_fail_time"),
            "last_fail_time": entry.get("last_fail_time"),
            "blocked_until": entry.get("blocked_until"),
            "is_blocked": loop.is_blocked(),
        })
    return {"runs": history, "blocked_after_3rd": history[-1]["is_blocked"]}


# ── scenario 3: ceiling のキーが垢単位か ─────────────────────────────────
def scenario_account_key(mod: Any, root: Path) -> dict[str, Any]:
    """毎時cron相当（run間隔60分）で、失効垢Aの失敗が他垢Bの成功に巻き込まれるかを実測する。

    修正前: applier は context に key を渡さず、ceiling キーは "apply" 全体。
            → A失敗(count=1) → B成功(reset=0) → A失敗(1) → … と振動し、3連続に到達しない。
    修正後: キーは "apply:<acct>"。Aの失敗だけが数えられ、Bの成功はAのカウンタに触れない。
    """

    def run_case(case: str, use_key: bool) -> dict[str, Any]:
        proj = _mkproj(root, f"keys_{case}")
        offset = [timedelta(0)]
        install_clock(mod, offset)
        sh_cfg = _cfg(proj, max_attempts=1)

        def loop_for(acct: str) -> Any:
            ctx = {"key": f"apply:{acct}"} if use_key else {}
            return mod.SelfHealingLoop(cfg=sh_cfg, pipeline="apply", context=ctx)

        key_a = "apply:acctA" if use_key else "apply"
        history: list[dict[str, Any]] = []
        # 毎時run: 奇数時間はA(失効垢)が失敗、偶数時間はB(健全垢)が成功
        for hour in range(6):
            offset[0] = timedelta(hours=hour)
            if hour % 2 == 0:  # A の run（失効垢 → 0 success 1 errors）
                la = loop_for("acctA")
                la.run(lambda: (0, 1),
                       validator=lambda value=None, *, exception=None, context=None: mod.RecoverySignal(
                           kind="no_auth_session", recoverable=False, severity="error",
                           message="apply 0 success 1 errors (no_auth_session)"))
                history.append({"run": f"T+{hour}h", "actor": "acctA(失効)",
                                "A_blocked": la.is_blocked(key_a)})
            else:  # B の run（健全垢 → 成功）
                lb = loop_for("acctB")
                lb.run(lambda: (1, 0), validator=lambda value=None, **kw: None)
                history.append({"run": f"T+{hour}h", "actor": "acctB(成功)",
                                "A_blocked": lb.is_blocked(key_a)})
        st = _ceiling_state(proj)
        return {
            "history": history,
            "A_failures": sum(1 for h in history if h["actor"].startswith("acctA")),
            "A_blocked_at_end": history[-1]["A_blocked"],
            "ceiling_keys": {k: v.get("count") for k, v in st.items()},
        }

    return {
        "before_style(apply 全体キー)": run_case("wide", use_key=False),
        "after_style(apply:<acct> キー)": run_case("peracct", use_key=True),
    }


def main() -> int:
    ref = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    with tempfile.TemporaryDirectory(prefix="t_8946706e_repro_") as td:
        root = Path(td)
        before = load_before(ref, root / "self_heal_before.py")
        after = load_after()

        # 前段の時計(offset)を使う scenario はモジュール単位で差し替えるため、ここで都度設定する
        out = {
            "task": TASK,
            "before_ref": subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", ref],
                                         capture_output=True, text=True, check=True).stdout.strip(),
            "scenario1_session_failure_retry": {
                "before": scenario_fatal_retry(before, root / "b"),
                "after": scenario_fatal_retry(after, root / "a"),
            },
            "scenario2_hourly_ceiling": {
                "before": scenario_hourly_ceiling(before, root / "b"),
                "after": scenario_hourly_ceiling(after, root / "a"),
            },
            "scenario3_ceiling_key_per_account": {
                "before_module": scenario_account_key(before, root / "b"),
                "after_module": scenario_account_key(after, root / "a"),
            },
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
