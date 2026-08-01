#!/usr/bin/env python3
"""
Kensho Hindsight Guard — Hindsight起動前ガード

HermesがHindsight（組み込みPostgreSQL）を起動する前に、
pg0の状態を厳密にチェックし、異常があれば自動修復する。

Orchestrator起動時にも呼ばれ、Hindsightが正常に動作することを保証する。

使い方:
    python tools/hindsight_guard.py                  # チェック＋自動修復
    python tools/hindsight_guard.py --check-only     # チェックのみ
    python tools/hindsight_guard.py --force-reset    # pg0強制リセット

戻り値:
    0 = 正常（Hindsight起動可能）
    1 = 警告あり（起動は可能だが推奨しない）
    2 = 異常（修復失敗、手動対応必要）
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = PROJECT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PG0_INSTANCE_NAME = "hindsight-embed-hermes"
LOG_FILE = LOGS_DIR / "hindsight_guard.log"


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def append_log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


# ════════════════════════════════════════════
# Step 1: pg0バイナリが利用可能か
# ════════════════════════════════════════════
def check_pg0_binary() -> bool:
    """pg0 Pythonモジュールがインポート可能か確認"""
    try:
        import pg0

        log(f"pg0 モジュール OK: {pg0.__file__}")
        append_log("pg0 モジュール OK")
        return True
    except ImportError as e:
        log(f"pg0 モジュールが見つからない: {e}", "ERROR")
        append_log(f"pg0 モジュール不明: {e}")
        return False


# ════════════════════════════════════════════
# Step 2: pg0インスタンスのPID正当性確認
# ════════════════════════════════════════════
def check_pg0_pid() -> tuple[bool, str]:
    """
    pg0 infoで取得したPIDが本当にpostgresプロセスか確認する。
    svchost.exeなどを誤認識していないか。

    Returns:
        (ok, description): ok=Trueなら正常、descriptionに詳細
    """
    import pg0

    try:
        info = pg0.info(PG0_INSTANCE_NAME)
    except json.JSONDecodeError:
        return (True, "pg0未初期化（初回起動待機中）")
    except Exception as e:
        return (True, f"pg0情報取得不可（想定内: {e})")

    if not info.running:
        return (True, "停止中（問題なし）")

    pid = info.pid
    if pid is None:
        return (True, "pg0 infoにPIDなし（未起動）")

    import psutil

    try:
        proc = psutil.Process(pid)
        proc_name = proc.name().lower()
        if "postgres" in proc_name:
            return (True, f"正常: PID {pid} = {proc_name}")
        else:
            return (False, f"異常: pg0はPID {pid} をPostgreSQLと認識 → 実際は「{proc_name}」！")
    except psutil.NoSuchProcess:
        return (False, f"異常: pg0はPID {pid} をPostgreSQLと認識 → プロセスは既に死んでいる（ゾンビ）")
    except Exception as e:
        return (True, f"確認不可（pg0起動前かも）: {e}")


# ════════════════════════════════════════════
# Step 3: psqlで実際に接続テスト
# ════════════════════════════════════════════
def check_pg0_psql() -> bool:
    """
    pg0経由で実際にpsql接続を試みる。
    pg0が「running」と言っていても実際にクエリが通るとは限らない。
    """
    import pg0

    try:
        info = pg0.info(PG0_INSTANCE_NAME)
        if not info.running:
            return True  # 停止中なら接続テスト不要
    except Exception:
        return True  # 未初期化ならスキップ

    result = pg0._run_pg0("psql", "--name", PG0_INSTANCE_NAME, "-c", "SELECT 1 AS alive", check=False)
    if result.returncode == 0:
        log("psql接続成功 — PostgreSQL正常稼働")
        append_log("psql接続OK")
        return True
    else:
        err = result.stderr.strip()[:150]
        log(f"psql接続失敗: {err}", "ERROR")
        append_log(f"psql接続失敗: {err}")
        return False


# ════════════════════════════════════════════
# Step 4: 起動中PostgreSQLプロセスの整合性確認
# ════════════════════════════════════════════
def check_running_postgres() -> int:
    """
    実際にport 5432でListenしているプロセスを確認。
    pg0/pg_ctlが管理していないPostgreSQLがポート衝突してないか確認。

    Returns:
        0 = 問題なし, 1 = 他にPostgreSQLあり, -1 = 確認不能
    """
    try:
        import psutil

        for conn in psutil.net_connections():
            if conn.laddr and conn.laddr.port == 5432 and conn.status == "LISTEN":
                try:
                    proc = psutil.Process(conn.pid)
                    log(f"port 5432: {proc.name()} (PID {conn.pid})")
                    if "postgres" in proc.name().lower():
                        return 0  # pg0のPostgreSQL
                    else:
                        log(f"⚠ 他プロセスがport 5432を使用中: {proc.name()}", "WARN")
                        return 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    return -1
        return 0  # Listenなし
    except Exception as e:
        log(f"port確認失敗: {e}", "WARN")
        return -1


# ════════════════════════════════════════════
# Step 5: Hindsight設定ファイルの存在確認
# ════════════════════════════════════════════
def check_hindsight_config() -> bool:
    """
    Hindsightの設定ファイルが存在し、必須項目があるか確認。
    """
    hermes_home = Path(
        os.environ.get("HERMES_HOME", Path.home() / "AppData" / "Local" / "hermes" / "profiles" / "kensho-sweeps")
    )
    config_path = hermes_home / "hindsight" / "config.json"

    if not config_path.exists():
        log("hindsight/config.json なし — まだセットアップされていない", "WARN")
        append_log("hindsight/config.json なし")
        return True  # ない場合は初回セットアップが必要だが、ガードの責務外

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        mode = config.get("mode", "unknown")
        provider = config.get("llm_provider", "")
        model = config.get("llm_model", "")
        log(f"config: mode={mode}, provider={provider}, model={model}")
        append_log(f"config OK: mode={mode}")
        return True
    except Exception as e:
        log(f"config.json読み込み失敗: {e}", "ERROR")
        append_log(f"config破損: {e}")
        return False


# ════════════════════════════════════════════
# 自動修復
# ════════════════════════════════════════════
def fix_pg0_reset() -> bool:
    """pg0インスタンスを強制リセット"""
    import pg0

    log("🔧 pg0 強制リセット開始...")
    append_log("pg0リセット開始")

    try:
        pg0.stop(PG0_INSTANCE_NAME)
        log("  stop: OK (または未起動)")
    except Exception as e:
        log(f"  stop: {e}")

    time.sleep(1)

    try:
        pg0.drop(PG0_INSTANCE_NAME, force=True)
        log("✅ drop: 完了。次回起動時に再作成されます")
        append_log("pg0リセット完了")
        return True
    except Exception as e:
        log(f"❌ drop失敗: {e}", "ERROR")
        append_log(f"pg0リセット失敗: {e}")
        return False


def fix_pg0_kill_zombie(bad_pid: int) -> bool:
    """誤認識しているPIDを強制終了（危険な場合のみ）"""
    import psutil

    try:
        proc = psutil.Process(bad_pid)
        name = proc.name()
        # svchostや重要なシステムプロセスは絶対に殺さない
        if name.lower() in ("svchost.exe", "wininit.exe", "services.exe", "lsass.exe", "csrss.exe"):
            log(f"🔧 PID {bad_pid} はシステムプロセス「{name}」→ 殺さずpg0リセットで対応", "WARN")
            return fix_pg0_reset()

        proc.kill()
        log(f"🔧 ゾンビPID {bad_pid} ({name}) を強制終了")
        append_log(f"PID {bad_pid} killed")
        time.sleep(1)
        return fix_pg0_reset()  # 確実にリセット
    except Exception as e:
        log(f"❌ PID {bad_pid} 終了失敗: {e}", "ERROR")
        return fix_pg0_reset()  # フォールバック


def fix_lock_file() -> None:
    """ゾンビロックファイルを削除"""
    lock_dir = PROJECT_DIR / "data" / "locks"
    if not lock_dir.is_dir():
        return

    import psutil

    for lf in lock_dir.iterdir():
        try:
            pid_text = lf.read_text().strip()
            pid = int(pid_text)
            if not psutil.pid_exists(pid):
                lf.unlink(missing_ok=True)
                log(f"🔧 ゾンビロック削除: {lf.name}")
        except Exception:
            pass


# ════════════════════════════════════════════
# メイン実行
# ════════════════════════════════════════════
def run_guard(check_only: bool = False, force_reset: bool = False) -> int:
    """
    ガードを実行する。

    Returns:
        0: 正常（Hindsight起動可能）
        1: 警告あり（pg0起動前にhealth_check推奨）
        2: 異常（修復失敗）
    """
    log("=" * 50)
    log(f"Hindsight Guard — {'CHECK ONLY' if check_only else 'AUTO-REPAIR'}")
    log(f"Started: {datetime.now().isoformat()}")
    log("=" * 50)
    append_log("=== Hindsight Guard Start ===")

    warnings = 0
    errors = 0

    # ── Step 1: pg0バイナリ ──
    if not check_pg0_binary():
        log("pg0バイナリなし → Hindsight未インストール", "ERROR")
        append_log("pg0バイナリなし")
        return 2

    # ── Step 2: pg0 PID正当性 ──
    pid_ok, pid_desc = check_pg0_pid()
    if not pid_ok:
        errors += 1
        log(f"⚠ {pid_desc}", "ERROR")
        append_log(f"PID異常: {pid_desc}")
        if not check_only and not force_reset:
            # 悪いPIDを特定してkill
            import pg0

            info = pg0.info(PG0_INSTANCE_NAME)
            if info.pid:
                fix_pg0_kill_zombie(info.pid)
                errors -= 1  # 修復試行
    else:
        log(f"✅ PID: {pid_desc}")

    # ── Step 2.5: port 5432確認 ──
    port_status = check_running_postgres()
    if port_status == 1:
        warnings += 1
        log("⚠ port 5432を他プロセスが使用中 → 確認推奨", "WARN")
        append_log("port 5432競合")

    # ── Step 3: psql接続テスト ──
    psql_ok = check_pg0_psql()
    if not psql_ok:
        errors += 1
        if not check_only:
            log("🔧 psql接続失敗 → pg0リセット試行...")
            if fix_pg0_reset():
                errors -= 1
                log("✅ pg0リセット成功！次回Hindsight起動時に再作成されます")
                append_log("pg0リセット成功")
            else:
                log("❌ pg0リセット失敗 → 手動対応が必要かも", "ERROR")
                append_log("pg0リセット失敗")

    # ── Step 4: Hindsight設定 ──
    if not check_hindsight_config():
        warnings += 1

    # ── Step 5: ロックファイルクリーン ──
    if not check_only:
        fix_lock_file()

    # ── force-reset ──
    if force_reset:
        log("🔧 --force-reset 指定のためpg0強制初期化")
        if fix_pg0_reset():
            log("✅ pg0初期化完了")
        # Hindsightロック削除
        hindsight_lock = Path.home() / ".hindsight" / "profiles" / "hermes.lock"
        hindsight_log = Path.home() / ".hindsight" / "profiles" / "hermes.log"
        for f in [hindsight_lock, hindsight_log]:
            try:
                if f.exists():
                    f.unlink(missing_ok=True)
                    log(f"🔧 {f.name} 削除")
            except Exception as e:
                log(f"⚠ {f.name} 削除失敗（起動中かも）: {e}")

    # ── 結果 ──
    log("=" * 50)
    if errors == 0 and warnings == 0:
        log("✅ Hindsight Guard: ALL CLEAR — 起動可能")
        append_log("Result: ALL CLEAR")
        return 0
    elif errors == 0:
        log(f"⚠ Hindsight Guard: CLEAR (warnings={warnings}) — 起動可能")
        append_log(f"Result: CLEAR (warnings={warnings})")
        return 0
    else:
        log(f"❌ Hindsight Guard: FAILED (errors={errors}, warnings={warnings})")
        append_log(f"Result: FAILED (errors={errors})")
        return 2


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kensho Hindsight Guard")
    parser.add_argument("--check-only", action="store_true", help="チェックのみ（修復しない）")
    parser.add_argument("--force-reset", action="store_true", help="pg0強制リセット")
    args = parser.parse_args()

    rc = run_guard(check_only=args.check_only, force_reset=args.force_reset)
    sys.exit(rc)
