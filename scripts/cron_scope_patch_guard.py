#!/usr/bin/env python3
"""cron scopeパッチ守衛（hermes更新で消えたローカルパッチを帯域外で復旧する）。

背景（2026-10-01 実測・AIチーム通知が約9時間停止した事故）:
  - Hermes ゲートウェイが systemd ユーザーサービスとして動くと、cron のエージェント型
    ジョブは tools/process_registry.restart_safe_gateway_child_argv() により
    systemd スコープ (hermes-worker-cron-*.scope) へ派遣される。
  - WSL2 では scope 内の実ワークロードが数秒で無言死し、execution は 'unknown'
    (owner process died) になって Telegram 通知が出ない。no_agent ジョブは短時間で
    終わるため無事（= 監視の盲点になりやすい）。
  - 対策として process_registry.py にローカルパッチ（HERMES_CRON_NO_SCOPE=1 かつ
    cron経路なら in_process）＋ systemd drop-in を入れた。
  - **hermes 本体を更新するとパッチが消え**、cron エージェントジョブが再び即死する。

この守衛は Hermes cron に依存しない（OS crontab から毎30分実行）。
1. process_registry.py にパッチ痕跡があるか検査 → 無ければ --repair で再適用
2. drop-in cron-in-process.conf があるか検査 → 無ければ --repair で再作成
3. 稼働中ゲートウェイの環境に HERMES_CRON_NO_SCOPE=1 があるか検査（drop-in 追加後の
   再起動忘れを検知）→ 無ければ再起動
4. 再適用/再起動の直後は state に記録し、同一シグネチャは ALERT_COOLDOWN_HOURS で抑制

終了コード: 0=問題なし / 1=問題あり（stdout を notify.sh に渡して通知できる）
使い方:
  python3 scripts/cron_scope_patch_guard.py            # 検査のみ
  python3 scripts/cron_scope_patch_guard.py --repair   # 検出時にパッチ再適用/再起動
  python3 scripts/cron_scope_patch_guard.py --selftest # パッチ適用ロジックの自己検証
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

JST = dt.timezone(dt.timedelta(hours=9))

HERMES_AGENT = Path("/home/atushi/.hermes/hermes-agent")
TARGET = HERMES_AGENT / "tools" / "process_registry.py"
DROPIN_DIR = Path("/home/atushi/.config/systemd/user/hermes-gateway.service.d")
DROPIN = DROPIN_DIR / "cron-in-process.conf"
STATE_FILE = Path("/home/atushi/.hermes/profiles/kensho-sweeps/state/cron_scope_guard_state.json")

PATCH_MARKER = "kensho-sweeps local patch (2026-10-01)"
ANCHOR = (
    '    if not os.environ.get("INVOCATION_ID"):\n'
    '        return GatewayChildDispatch("in_process", command)\n'
)
PATCH_BLOCK = (
    "    # --- kensho-sweeps local patch (2026-10-01) ---\n"
    "    # WSL2: a cron job placed in a transient systemd scope\n"
    "    # (hermes-worker-cron-<job>-exec-<exec>.scope) exits silently a few seconds\n"
    "    # after start; the durable execution ends 'unknown' and nothing is delivered,\n"
    "    # while the same job run in-process completes normally (measured: one job,\n"
    "    # two paths, in-process=running vs scoped=dead in 5s). A cron job blocks its\n"
    "    # caller until it finishes, so in-process execution is correct here and is the\n"
    "    # documented WSL topology. Applies to the cron path only (outlives_parent is\n"
    "    # False for cron); fire-and-forget kanban workers keep its scope isolation.\n"
    "    # Enable with the systemd drop-in Environment=HERMES_CRON_NO_SCOPE=1.\n"
    "    # Revert by deleting this block and the drop-in.\n"
    '    if os.environ.get("HERMES_CRON_NO_SCOPE") == "1" and not outlives_parent:\n'
    '        return GatewayChildDispatch("in_process", command)\n'
    "    # --- end kensho-sweeps local patch ---\n"
)

DROPIN_CONTENT = """# 2026-10-01: WSL2でのcronエージェントジョブ即死対策（有効化スイッチ）
#
# 症状: 定時実行のエージェント型cronジョブが外部systemdスコープ
#       (hermes-worker-cron-<job>-exec-<exec>.scope) 内で数秒で無言終了し、
#       execution が 'unknown'(owner process died) になり Telegram 通知が出ない。
#
# 実装: tools/process_registry.restart_safe_gateway_child_argv() に
#       「HERMES_CRON_NO_SCOPE=1 かつ cron経路(outlives_parent=False)」なら
#       in_process を返すローカルパッチ。kanbanの長時間ワーカーは従来通り。
#       管理: scripts/cron_scope_patch_guard.py（OS crontab 30分おき）
#
# 重要: INVOCATION_ID は絶対に触らない。
#       2026-10-01 14:48 の試行で除去したところゲートウェイの自己識別ガードが
#       誤発火("A gateway is already running under systemd")し systemd 再起動ループ。
#
# ロールバック: このファイルを削除 → systemctl --user daemon-reload && systemctl --user restart hermes-gateway
[Service]
Environment="HERMES_CRON_NO_SCOPE=1"
"""

ALERT_COOLDOWN_HOURS = 6


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST)


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def should_notify(signature: str) -> bool:
    """同一シグネチャは ALERT_COOLDOWN_HOURS 時間ごとに1回だけ通知する。"""
    now = now_jst()
    state = _load_state()
    last = state.get(signature)
    if last:
        try:
            if (now - dt.datetime.fromisoformat(last)).total_seconds() < ALERT_COOLDOWN_HOURS * 3600:
                return False
        except ValueError:
            pass
    state[signature] = now.isoformat()
    _save_state(state)
    return True


def _gateway_main_pid() -> int | None:
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show", "hermes-gateway", "-p", "MainPID", "--value"],
            capture_output=True, text=True, timeout=15,
        )
        pid = int((out.stdout or "").strip() or 0)
        return pid or None
    except Exception:
        return None


def _running_jobs() -> list[str]:
    """現在 running の execution を返す（再起動で実行中ジョブを巻き添えにしないため）。"""
    import sqlite3

    db = Path("/home/atushi/.hermes/profiles/kensho-sweeps/cron/executions.db")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT job_id, started_at FROM executions WHERE status='running' ORDER BY started_at DESC"
        ).fetchall()
        con.close()
    except Exception:
        return []
    return [f"{j}({str(s)[:19]})" for j, s in rows]


def _restart_gateway(wait_quiet_seconds: int = 300) -> tuple[bool, str]:
    """drop-in/パッチ変更を稼働中ゲートウェイへ反映させる（daemon-reload + restart）。

    gateway の TimeoutStopSec=210 のため停止に数分かかる。timeout は余裕を取る。
    実行中ジョブがあると再起動で巻き添え（execution が 'unknown' 化）になるため、
    最大 wait_quiet_seconds だけ静穏窓を待ち、待てなければ次回tickに回す。
    """
    deadline = time.time() + wait_quiet_seconds
    while True:
        running = _running_jobs()
        if not running:
            break
        if time.time() >= deadline:
            return False, (
                "実行中ジョブが終わらないため再起動を見送り（次回tickで再試行）: "
                + ", ".join(running[:3])
            )
        time.sleep(10)
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=60)
        r = subprocess.run(
            ["systemctl", "--user", "restart", "hermes-gateway"],
            capture_output=True, text=True, timeout=420,
        )
        if r.returncode != 0:
            return False, f"gateway 再起動に失敗: {r.stderr.strip()[:200]}"
    except Exception as exc:
        return False, f"gateway 再起動で例外: {exc}"
    # restart 完了後、新しい MainPID が active になるまで待つ（直後の env 検査を正しくする）
    for _ in range(30):
        pid = _gateway_main_pid()
        state = subprocess.run(
            ["systemctl", "--user", "is-active", "hermes-gateway"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        if pid and state == "active":
            return True, f"gateway 再起動済 (PID {pid})"
        time.sleep(2)
    return False, "gateway 再起動後も active にならない（要手動確認）"


def check_patch_text(text: str) -> tuple[bool, str]:
    """パッチ痕跡と、効いている条件の両方を検査する（純粋関数・selftest 用）。"""
    if PATCH_MARKER not in text:
        return False, "missing"
    if 'if os.environ.get("HERMES_CRON_NO_SCOPE") == "1" and not outlives_parent:' not in text:
        return False, "incomplete"
    return True, "ok"


def apply_patch(text: str) -> tuple[str, str]:
    """パッチを冪等に当てる。戻り値: (新テキスト, 状態 ok/already/anchor_missing)。"""
    ok, why = check_patch_text(text)
    if ok:
        return text, "already"
    if PATCH_MARKER in text and why == "incomplete":
        return text, "incomplete"  # 中途半端な痕跡は推測で直さない
    if ANCHOR not in text:
        return text, "anchor_missing"
    return text.replace(ANCHOR, ANCHOR + PATCH_BLOCK, 1), "ok"


def check_patch(repair: bool) -> tuple[bool, str, bool]:
    """戻り値: (ok, メッセージ, 変更したか)。"""
    if not TARGET.exists():
        return False, f"🔴 対象が見つからない: {TARGET}", False
    try:
        text = TARGET.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"🔴 対象を読めない: {exc}", False

    ok, why = check_patch_text(text)
    if ok:
        return True, "✅ process_registry.py パッチ健在", False

    if why == "incomplete":
        return False, (
            "🔴 process_registry.py にパッチ痕跡があるが必須条件が欠けている"
            "（中途半端な状態）。手動確認が必要。"
        ), False

    if not repair:
        return False, (
            "🔴 process_registry.py のパッチが消失（hermes更新の可能性）。"
            "`python3 scripts/cron_scope_patch_guard.py --repair` で再適用できる。"
        ), False

    new_text, status = apply_patch(text)
    if status == "anchor_missing":
        return False, (
            "🔴 パッチ挿入点(INVOCATION_ID ガード)が見つからない。"
            "上流コードが変わった可能性 → 手動対応が必要。"
        ), False

    backup = TARGET.with_suffix(".py.guard_bak")
    try:
        shutil.copy2(TARGET, backup)
        tmp = TARGET.with_suffix(".py.guard_tmp")
        tmp.write_text(new_text, encoding="utf-8")
        py_compile.compile(str(tmp), doraise=True)  # 構文検証してから差し替え
        os.replace(tmp, TARGET)
    except Exception as exc:
        try:
            if backup.exists():
                shutil.copy2(backup, TARGET)
        except Exception:
            pass
        return False, f"🔴 パッチ再適用に失敗し元に戻した: {exc}", False
    finally:
        for p in (TARGET.with_suffix(".py.guard_tmp"),):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass

    ok_r, msg_r = _restart_gateway()
    return (
        False,
        "🟠 process_registry.py のパッチを再適用した（hermes更新で消えていた）；"
        + (msg_r if not ok_r else "gateway 再起動済（稼働中プロセスに反映）"),
        True,
    )


def check_dropin(repair: bool) -> tuple[bool, str, bool]:
    if not DROPIN.exists():
        if not repair:
            return False, (
                "🔴 systemd drop-in cron-in-process.conf が無い。"
                "`--repair` で再作成できる（要 gateway 再起動）。"
            ), False
        try:
            DROPIN_DIR.mkdir(parents=True, exist_ok=True)
            DROPIN.write_text(DROPIN_CONTENT, encoding="utf-8")
        except Exception as exc:
            return False, f"🔴 drop-in を作成できない: {exc}", False
        return False, "🟠 systemd drop-in cron-in-process.conf を再作成した", True

    try:
        body = DROPIN.read_text(encoding="utf-8")
    except Exception as exc:
        return False, f"🔴 drop-in を読めない: {exc}", False
    if 'HERMES_CRON_NO_SCOPE=1' not in body:
        return False, "🔴 drop-in に HERMES_CRON_NO_SCOPE=1 が無い（手動確認）", False
    return True, "✅ drop-in 健在", False


def check_live_env(repair: bool) -> tuple[bool, str, bool]:
    """稼働中ゲートウェイにスイッチが効いているか（再起動忘れの検知）。"""
    pid = _gateway_main_pid()
    if pid is None:
        return False, "🔴 hermes-gateway の MainPID を取得できない（サービス停止？）", False
    try:
        env = Path(f"/proc/{pid}/environ").read_bytes().decode("utf-8", "replace").split("\0")
    except Exception as exc:
        return False, f"🔴 ゲートウェイ {pid} の環境を読めない: {exc}", False
    if any(e == "HERMES_CRON_NO_SCOPE=1" for e in env):
        return True, f"✅ ゲートウェイ(PID {pid}) にスイッチ有効", False
    if not repair:
        return False, (
            f"🔴 ゲートウェイ(PID {pid}) に HERMES_CRON_NO_SCOPE=1 が無い"
            "（drop-in追加後の再起動忘れ）。`--repair` で再起動できる。"
        ), False
    ok_r, msg_r = _restart_gateway()
    if not ok_r:
        return False, f"🔴 {msg_r}", False
    return False, "🟠 ゲートウェイを再起動してスイッチを有効化した", True


def run(repair: bool) -> int:
    results = []
    changed = False
    for fn in (check_patch, check_dropin, check_live_env):
        ok, msg, did = fn(repair)
        results.append((ok, msg))
        changed = changed or did

    bad = [m for ok, m in results if not ok]
    if not bad and not changed:
        return 0

    lines = [f"[cron_scope_patch_guard {now_jst():%m-%d %H:%M}]"]
    lines += [m for _, m in results]
    lines.append("")
    lines.append(
        "背景: hermes更新でパッチが消えると、cronエージェント型ジョブがsystemdスコープ内で"
        "即死し Telegram 通知が止まる（2026-10-01事故）。"
    )

    text = "\n".join(lines)
    sig = "|".join(sorted({m.split(":")[0] for m in bad})) or "repaired"
    if should_notify(sig):
        print(text)
    return 1 if bad else 0


def selftest() -> int:
    """パッチ適用ロジックをメモリ上で検証（本番ファイルには触らない）。"""
    base = (
        "def f():\n"
        "    if not _IS_LINUX:\n"
        '        return "in_process"\n'
        + ANCHOR
        + '    return "scoped"\n'
    )
    # 未パッチ → 適用できる
    new, st = apply_patch(base)
    assert st == "ok", st
    assert PATCH_MARKER in new
    assert 'HERMES_CRON_NO_SCOPE") == "1" and not outlives_parent' in new
    assert new.index(PATCH_MARKER) < new.index('return "scoped"'), "挿入位置が不正"
    # 冪等
    again, st2 = apply_patch(new)
    assert st2 == "already" and again == new, st2
    # 検査関数
    assert check_patch_text(new)[0] is True
    assert check_patch_text(base)[0] is False
    # 挿入点が無い上流変化 → 推測で書かない
    _, st3 = apply_patch("def f():\n    return 1\n")
    assert st3 == "anchor_missing", st3
    # 構文検証が通ること（実テキストをコンパイル）
    import ast

    ast.parse(new)
    print("selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="cron scopeパッチ守衛（帯域外）")
    ap.add_argument("--repair", action="store_true", help="パッチ再適用・drop-in再作成・gateway再起動")
    ap.add_argument("--selftest", action="store_true", help="パッチ適用ロジックの自己検証のみ")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    return run(args.repair)


if __name__ == "__main__":
    sys.exit(main())
