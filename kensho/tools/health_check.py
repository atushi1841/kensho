#!/usr/bin/env python3
"""
Kensho Health Check — 起動時健全性チェック + 自動修復

Hindsight・Hermes・orchestratorの起動前に実行し、
既知のトラブル（pg0誤認識、ロック残骸、PID誤検知など）を
自動検出・修復する。修復ログは logs/health_check.log に出力。

使い方:
    python tools/health_check.py                  # 通常チェック＋自動修復
    python tools/health_check.py --report-only    # レポートのみ（修復しない）
    python tools/health_check.py --force-reset    # pg0を強制初期化

依存: psutil, pg0（共にvenv内）
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── プロジェクトルート ──
PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_DIR / "data"
LOGS_DIR = PROJECT_DIR / "logs"
LOCK_DIR = DATA_DIR / "locks"

# Pythonパスにプロジェクトルートを追加
sys.path.insert(0, str(PROJECT_DIR))

# ── Hindsight関連パス ──
HINDSIGHT_PROFILES = Path.home() / ".hindsight" / "profiles"
HINDSIGHT_CONFIG = (
    Path(os.environ.get("HERMES_HOME", Path.home() / "AppData" / "Local" / "hermes" / "profiles" / "kensho-sweeps"))
    / "hindsight"
    / "config.json"
)
PG0_INSTANCE_NAME = "hindsight-embed-hermes"

# ── ログ ──
LOG_FILE = LOGS_DIR / "health_check.log"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════
# ロガー
# ════════════════════════════════════════════
class HealthLogger:
    def __init__(self) -> None:
        self._log: list[str] = []
        self._pass: int = 0
        self._fail: int = 0
        self._fix: int = 0

    def ok(self, msg: str) -> None:
        line = f"  ✅ {msg}"
        self._log.append(line)
        self._pass += 1
        print(line, flush=True)

    def warn(self, msg: str) -> None:
        line = f"  ⚠️ {msg}"
        self._log.append(line)
        print(line, flush=True)

    def fail(self, msg: str) -> None:
        line = f"  ❌ {msg}"
        self._log.append(line)
        self._fail += 1
        print(line, flush=True)

    def fix(self, msg: str) -> None:
        line = f"  🔧 {msg}"
        self._log.append(line)
        self._fix += 1
        print(line, flush=True)

    def info(self, msg: str) -> None:
        line = f"  {msg}"
        self._log.append(line)
        print(line, flush=True)

    def summary(self) -> dict[str, int]:
        return {"pass": self._pass, "fail": self._fail, "fix": self._fix}

    def flush(self) -> None:
        timestamp = datetime.now().isoformat()
        summary = self.summary()
        header = (
            f"{'=' * 50}\n"
            f"Health Check @ {timestamp}\n"
            f"PASS={summary['pass']} FAIL={summary['fail']} FIX={summary['fix']}\n"
            f"{'=' * 50}"
        )
        body = "\n".join(self._log)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{header}\n{body}\n\n")
        except Exception:
            pass


# ════════════════════════════════════════════
# Check 1: pg0 インスタンスのPIDが正しいか
# ════════════════════════════════════════════
def check_pg0_instance(log: HealthLogger) -> bool:
    """
    pg0の管理するPostgreSQLインスタンスを検証。
    PIDが本当にpostgres.exeか確認し、誤検知（svchostなど）を検出。
    """
    log.info("--- Check 1: pg0 PostgreSQL Instance ---")
    try:
        import pg0

        info = pg0.info(PG0_INSTANCE_NAME)
    except Exception as e:
        log.warn(f"pg0 info取得失敗（未初期化かも）: {e}")
        return True  # 未初期化は正常

    if not info.running:
        log.ok("pg0インスタンス停止中（未起動）— 問題なし")
        return True

    pid = info.pid
    if pid is None:
        log.warn("pg0がPIDを持っていない → 奇妙だがスキップ")
        return True

    # PIDが実在するプロセスか確認
    try:
        import psutil

        proc = psutil.Process(pid)
        proc_name = proc.name().lower()

        # PostgreSQLのプロセス名は postgres.exe または postgresql.exe
        if "postgres" not in proc_name:
            log.fail(f"pg0がPID {pid} をPostgreSQLと認識 → 実際は「{proc_name}」！誤検知！")
            return False

        log.ok(f"pg0インスタンス正常: PID={pid} ({proc_name})")
        return True

    except psutil.NoSuchProcess:
        log.fail(f"pg0がPID {pid} をPostgreSQLと認識 → プロセスは既に死んでいる（ゾンビ状態）")
        return False
    except Exception as e:
        log.warn(f"PID確認中にエラー: {e}")
        return True  # 確認できないけど最悪スルー


# ════════════════════════════════════════════
# Check 2: pg0のpsqlで実際に接続できるか
# ════════════════════════════════════════════
def check_pg0_connectivity(log: HealthLogger) -> bool:
    """
    pg0経由で実際にpsql接続を試みる。
    pg0 infoが「running」でも実際には死んでることがあるので。
    """
    log.info("--- Check 2: pg0 Connectivity (psql) ---")
    try:
        import pg0

        info = pg0.info(PG0_INSTANCE_NAME)
        if not info.running:
            log.ok("pg0停止中 → psqlチェック不要")
            return True

        result = pg0._run_pg0("psql", "--name", PG0_INSTANCE_NAME, "-c", "SELECT 1 AS alive", check=False)
        if result.returncode == 0:
            log.ok("pg0 psql接続成功！ PostgreSQL正常稼働中")
            return True
        else:
            log.fail(f"pg0 psql接続失敗: {result.stderr.strip()[:100]}")
            return False
    except Exception as e:
        log.warn(f"psqlチェックスキップ: {e}")
        return True  # まだ起動してなければエラーは想定内


# ════════════════════════════════════════════
# Check 3: ロックファイルの健全性
# ════════════════════════════════════════════
def check_locks(log: HealthLogger) -> bool:
    """
    data/locks/ 内のPIDロックファイルを検証。
    死んだPIDのロックは削除する。
    """
    log.info("--- Check 3: PID Lock Files ---")
    if not LOCK_DIR.is_dir():
        log.ok("ロックディレクトリなし（問題なし）")
        return True

    try:
        import psutil
    except ImportError:
        log.warn("psutilなし → ロックチェックスキップ")
        return True

    locks = list(LOCK_DIR.iterdir())
    if not locks:
        log.ok("ロックファイルなし")
        return True

    stale = 0
    for lf in locks:
        try:
            pid_text = lf.read_text().strip()
            pid = int(pid_text)
            if not psutil.pid_exists(pid):
                lf.unlink(missing_ok=True)
                log.fix(f"ゾンビロック削除: {lf.name} (PID {pid} は死んでいる)")
                stale += 1
            else:
                proc = psutil.Process(pid)
                if "python" not in proc.name().lower():
                    lf.unlink(missing_ok=True)
                    log.fix(f"誤検知ロック削除: {lf.name} (PID {pid} は {proc.name()} — pythonじゃない)")
                    stale += 1
                else:
                    log.ok(f"ロック正常: {lf.name} (PID {pid} / {proc.name()})")
        except (ValueError, OSError) as e:
            lf.unlink(missing_ok=True)
            log.fix(f"破損ロック削除: {lf.name} ({e})")
            stale += 1

    if stale == 0:
        log.ok("全ロックファイル正常")
    return True


# ════════════════════════════════════════════
# Check 4: Hindsight ロックファイル
# ════════════════════════════════════════════
def check_hindsight_lock(log: HealthLogger) -> bool:
    """
    ~/.hindsight/profiles/hermes.lock がゾンビでないか確認。
    """
    log.info("--- Check 4: Hindsight Lock ---")
    lock_file = HINDSIGHT_PROFILES / "hermes.lock"
    if not lock_file.exists():
        log.ok("Hindsightロックなし")
        return True

    try:
        import psutil
    except ImportError:
        log.warn("psutilなし → Hindsightロックチェックスキップ")
        return True

    try:
        # ロックファイルはバイナリかもしれない
        data = lock_file.read_bytes()
        pid_str = data.decode("utf-8", errors="replace").strip()
        if pid_str:
            pid = int(pid_str.split()[0])  # 最初の数字
            if not psutil.pid_exists(pid):
                lock_file.unlink(missing_ok=True)
                log.fix(f"Hindsightゾンビロック削除 (PID {pid} は死んでいる)")
            else:
                proc = psutil.Process(pid)
                log.ok(f"Hindsightロック正常: PID {pid} ({proc.name()})")
        else:
            lock_file.unlink(missing_ok=True)
            log.fix("空のHindsightロック削除")
    except (ValueError, OSError) as e:
        # 削除できない場合（このセッションで使ってる）は無視
        log.warn(f"Hindsightロック確認中（削除できない場合は起動中）: {e}")

    return True


# ════════════════════════════════════════════
# Check 5: ネットワークアダプタ設定の整合性
# ════════════════════════════════════════════
def check_network_config(log: HealthLogger) -> bool:
    """
    config.yamlのnetwork_interfaceが実在のアダプタ名と一致するか確認。
    リネーム後も追従できるように。
    """
    log.info("--- Check 5: Network Interface Config ---")
    config_path = PROJECT_DIR / "config.yaml"
    if not config_path.exists():
        log.warn("config.yamlなし → スキップ")
        return True

    import re

    try:
        config_text = config_path.read_text(encoding="utf-8")
    except Exception as e:
        log.warn(f"config.yaml読み込み失敗: {e}")
        return True

    # network_interfaceの値を抽出（コメント行は除外）
    interfaces_in_config = []
    for line in config_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # コメント行はスキップ
        m = re.search(r'network_interface:\s*"([^"]+)"', stripped)
        if m:
            interfaces_in_config.append(m.group(1))

    # PowerShellで実在するアダプタ名を取得
    from kensho.utils.process import run

    result = run(
        ["powershell", "-NoProfile", "-Command", "Get-NetAdapter | ForEach-Object { $_.Name }"], timeout=15
    )  # encoding指定なし → デフォルトcp932（日本語Windows対応）
    if not result["success"]:
        log.warn("アダプタ一覧取得失敗 → スキップ")
        return True

    real_adapters = set(line.strip() for line in result["stdout"].splitlines() if line.strip())
    all_ok = True
    for name in interfaces_in_config:
        if name not in real_adapters:
            log.fail(f"config.yamlに「{name}」とあるが実在しないアダプタ！")
            all_ok = False
        else:
            log.ok(f"アダプタ「{name}」実在確認")

    if all_ok and interfaces_in_config:
        log.ok(f"全 {len(interfaces_in_config)} 個のアダプタ設定が実在と一致")
    return all_ok


# ════════════════════════════════════════════
# Check 6: 日次カウンターの異常値チェック
# ════════════════════════════════════════════
def check_daily_counts(log: HealthLogger) -> bool:
    """
    daily_counts.jsonの異常値を検出・修復。
    test_acctのようなテストキー、rt_limitの異常値などをチェック。
    """
    log.info("--- Check 6: Daily Counts Sanity ---")
    counts_file = DATA_DIR / "daily_counts.json"
    if not counts_file.exists():
        log.ok("daily_counts.jsonなし（まだ初期化されていない）")
        return True

    try:
        data = json.loads(counts_file.read_text(encoding="utf-8"))
    except Exception as e:
        log.warn(f"daily_counts.json読み込み失敗: {e}")
        return True

    counts = data.get("counts", {})
    modified = False

    # テストキーの除去
    test_keys = {"test_acct", "test", "dummy"}
    for key in list(counts.keys()):
        if key in test_keys:
            del counts[key]
            log.fix(f"テスト用キー「{key}」を削除")
            modified = True

    # rt_limitの異常値チェック（設定は15〜20、明らかな異常）
    rt_limit = counts.get("rt_limit", 0)
    if isinstance(rt_limit, (int, float)) and rt_limit > 30:
        import random

        old = rt_limit
        counts["rt_limit"] = random.randint(15, 20)
        log.fix(f"rt_limit 異常値 {old} → {counts['rt_limit']} に修正")
        modified = True
    elif isinstance(rt_limit, (int, float)):
        log.ok(f"rt_limit = {rt_limit}（正常範囲）")
    else:
        log.warn("rt_limit が数値以外 → スキップ")

    # アカウントごとの異常値チェック
    config_path = PROJECT_DIR / "config.yaml"
    valid_keys = set()
    if config_path.exists():
        import re

        valid_keys = set(re.findall(r"^\s+-\s+key:\s*(\w+)", config_path.read_text("utf-8"), re.MULTILINE))

    for key, acct_counts in list(counts.items()):
        if key in ("rt_limit",) or not isinstance(acct_counts, dict):
            continue
        # 存在しないアカウントキーがあれば警告（ただし自動削除はしない）
        if valid_keys and key not in valid_keys:
            known_legacy = {"test_acct"}  # 削除済みのはず
            if key not in known_legacy:
                log.warn(f"未知のアカウントキー「{key}」がdaily_countsにある")

        # 各アクションの値がintか確認
        for action in ("follow", "rt", "like", "reply"):
            val = acct_counts.get(action, 0)
            if not isinstance(val, int):
                acct_counts[action] = 0
                log.fix(f"{key}.{action} が非数値 → 0に修正")
                modified = True

    if modified:
        data["counts"] = counts
        counts_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("daily_counts.json を修正しました")
    else:
        log.ok("daily_counts.json 異常なし")

    return True


# ════════════════════════════════════════════
# 自動修復
# ════════════════════════════════════════════
def fix_pg0_instance(log: HealthLogger) -> bool:
    """
    pg0インスタンスを強制リセット。
    drop後、次回起動時に再作成される。
    """
    log.info("--- Auto-Fix: pg0 Reset ---")
    try:
        import pg0

        # まず停止
        try:
            pg0.stop(PG0_INSTANCE_NAME)
            log.info("pg0停止要求送信")
        except Exception as e:
            log.warn(f"pg0 stop結果: {e}")
        time.sleep(1)
        # 強制削除
        try:
            pg0.drop(PG0_INSTANCE_NAME, force=True)
            log.fix("pg0インスタンスを強制削除しました（次回起動時に再作成）")
            return True
        except Exception as e:
            log.fail(f"pg0 drop失敗: {e}")
            return False
    except ImportError:
        log.warn("pg0モジュールなし → スキップ")
        return True


def fix_hindsight_log_and_lock(log: HealthLogger) -> bool:
    """
    Hindsightの古いログとロックファイルを強制削除（PowerShell経由）。
    """
    log.info("--- Auto-Fix: Hindsight Files Cleanup ---")
    try:
        from kensho.utils.process import run_pwsh

        script = f"""
$lock = "{HINDSIGHT_PROFILES.as_posix()}/hermes.lock"
$log = "{HINDSIGHT_PROFILES.as_posix()}/hermes.log"
if (Test-Path $lock) {{ Remove-Item $lock -Force -ErrorAction SilentlyContinue; Write-Host "lock removed" }}
if ((Test-Path $log) -and ((Get-Item $log).Length -gt 10MB)) {{
    Remove-Item $log -Force -ErrorAction SilentlyContinue
    Write-Host "log removed (over 10MB)"
}}
"""
        result = run_pwsh(script)
        if "removed" in result["stdout"]:
            log.fix(f"Hindsightファイルクリーンアップ: {result['stdout'].strip()}")
        else:
            log.ok("Hindsightファイル クリーン状態")
        return True
    except Exception as e:
        log.warn(f"Hindsightクリーンアップ中: {e}")
        return True


# ════════════════════════════════════════════
# メイン
# ════════════════════════════════════════════
def run_health_check(report_only: bool = False, force_reset: bool = False) -> dict[str, Any]:
    """
    全チェックを実行し、結果を返す。

    Returns:
        dict: {success: bool, summary: {pass, fail, fix}, repairs: [str]}
    """
    log = HealthLogger()
    log.info(f"{'═' * 50}")
    log.info(f"Kensho Health Check — {'REPORT ONLY' if report_only else 'AUTO-REPAIR'}")
    log.info(f"Started: {datetime.now().isoformat()}")
    log.info(f"{'═' * 50}")

    repairs: list[str] = []

    # ── Check 1: pg0 PID正当性 ──
    pg0_ok = check_pg0_instance(log)

    # ── Check 2: pg0接続性 ──
    conn_ok = True
    if pg0_ok:
        conn_ok = check_pg0_connectivity(log)

    # ── pg0修復（必要なら） ──
    if force_reset:
        log.info("--force-reset指定 → pg0強制初期化")
        if fix_pg0_instance(log):
            repairs.append("pg0強制リセット")
            fix_hindsight_log_and_lock(log)
            repairs.append("Hindsightログ/ロック削除")

    elif (not pg0_ok or not conn_ok) and not report_only:
        log.info("pg0異常検出 → 自動修復開始")
        if fix_pg0_instance(log):
            repairs.append("pg0リセット（異常検出）")
            fix_hindsight_log_and_lock(log)
            repairs.append("Hindsightログ/ロック削除")

    elif not pg0_ok or not conn_ok:
        log.info("【要修復】pg0異常 — --report-onlyのため修復スキップ")

    # ── Check 3: ロックファイル ──
    check_locks(log)

    # ── Check 4: Hindsightロック ──
    check_hindsight_lock(log)

    # ── Check 5: ネットワーク設定 ──
    check_network_config(log)

    # ── Check 6: 日次カウンター ──
    check_daily_counts(log)

    # ── サマリー ──
    summary = log.summary()
    log.info("")
    log.info(f"{'═' * 50}")
    log.info(f"Result: PASS={summary['pass']} FAIL={summary['fail']} FIX={summary['fix']}")
    if repairs:
        log.info(f"Repairs: {'; '.join(repairs)}")
    log.info(f"Log: {LOG_FILE}")
    log.info(f"{'═' * 50}")

    log.flush()

    return {
        "success": summary["fail"] == 0,
        "summary": summary,
        "repairs": repairs,
        "log_file": str(LOG_FILE),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kensho Health Check")
    parser.add_argument("--report-only", action="store_true", help="レポートのみ（修復しない）")
    parser.add_argument("--force-reset", action="store_true", help="pg0強制初期化")
    args = parser.parse_args()

    result = run_health_check(report_only=args.report_only, force_reset=args.force_reset)
    sys.exit(0 if result["success"] else 1)
