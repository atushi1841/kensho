#!/usr/bin/env python3
"""
Kensho Daemon — 常駐デーモン、窓ゼロ、3スレッド並列実行
v2.0: Linux対応（WSL2対応）
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import time
import traceback
from typing import Any

# ── エンコーディングガード ──
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)  # type: ignore[union-attr]
    except Exception:
        sys.stdout.reconfigure(line_buffering=True)

# ── パス設定 ──
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
LOG_DIR = os.path.join(BASE, 'logs')
LOCK_DIR = os.path.join(DATA_DIR, 'locks')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(LOCK_DIR, exist_ok=True)

PYTHON = sys.executable
ORCHESTRATOR = os.path.join(BASE, 'orchestrator.py')
KEEPALIVE = os.path.join(BASE, 'keepalive', 'checker.py')

# ── PIDファイルで二重起動防止 ──
PID_PATH_LOCK = os.path.join(LOCK_DIR, 'daemon.pid')
try:
    if os.path.exists(PID_PATH_LOCK):
        with open(PID_PATH_LOCK) as f:
            old_pid_str = f.read().strip()
        if old_pid_str:
            old_pid = int(old_pid_str)
            # 既存プロセスが生きているか確認
            try:
                os.kill(old_pid, 0)  # シグナル0 = 生存確認専用
                print(f"[DAEMON] 既存デーモン (PID {old_pid}) が稼働中 → 終了")
                sys.exit(0)
            except OSError:
                pass  # プロセスが死んでいる → PIDファイルを上書き
except (ValueError, OSError):
    pass

# ── PIDファイル（Watchdog用）──
PID_PATH = os.path.join(LOCK_DIR, 'daemon.pid')
try:
    with open(PID_PATH, 'w') as f:
        f.write(str(os.getpid()))
except Exception:
    pass


# ── OS別プロセスキル ──
def _kill_firefox() -> None:
    """Firefox / geckodriver プロセスを強制終了"""
    try:
        for pname in ['firefox', 'geckodriver']:
            subprocess.run(
                ['pkill', '-f', pname],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    except Exception:
        pass


# ── ログ ──
def log(msg: str) -> None:
    ts = time.strftime('%H:%M:%S')
    today = time.strftime('%Y-%m-%d')
    logfile = os.path.join(LOG_DIR, today, f'daemon_{today}.log')
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    line = f'[{ts}] [DAEMON] {msg}'
    print(line, flush=True)
    try:
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        # ログファイル書き込み失敗は致命的ではない
        pass

def log_sub(name: str, exit_code: Any) -> None:
    ts = time.strftime('%H:%M:%S')
    today = time.strftime('%Y-%m-%d')
    logfile = os.path.join(LOG_DIR, today, f'daemon_{today}.log')
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    tag = {'KEEP': 'KEEP', 'ORCH': 'ORCH', 'PROXY': 'PROXY'}.get(name, name)
    line = f'[{ts}] [{tag}] exit={exit_code}'
    print(line, flush=True)
    try:
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        # ログファイル書き込み失敗は致命的ではない
        pass


# ── スレッド監視ラッパー（例外⇒再起動）──
def _run_with_restart(name: str, fn: Any, interval: int = 5) -> None:
    """スレッド関数をラップし、例外発生時に再起動する"""
    while True:
        try:
            fn()
        except Exception as e:
            log(f'[{name}] スレッド異常終了: {e} → {interval}秒後に再起動')
            log(f'[{name}] traceback: {traceback.format_exc()[-200:]}')
            time.sleep(interval)
            log(f'[{name}] 再起動します')


# ── スレッド1: keepalive（5分おき）──
def thread_keepalive() -> None:
    interval = 300  # 5分
    while True:
        time.sleep(interval)
        try:
            r = subprocess.run(
                [PYTHON, KEEPALIVE],
                cwd=BASE, capture_output=True, timeout=60,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
            )
            log_sub('KEEP', r.returncode)
        except subprocess.TimeoutExpired:
            log_sub('KEEP', 124)
        except Exception as e:
            log_sub('KEEP', str(e)[:20])


# ── スレッド2: orchestrator（15分おき）──
def thread_orchestrator() -> None:
    while True:
        try:
            # capture_output=True は Windows で Errno 22 を引き起こす（pipe→print→CRT EINVAL）
            # → ファイルに直接リダイレクト
            log_ts = time.strftime('%Y%m%d_%H%M%S')
            log_today = time.strftime('%Y-%m-%d')
            orch_log = os.path.join(LOG_DIR, log_today, f'orch_daemon_{log_ts}.log')
            os.makedirs(os.path.dirname(orch_log), exist_ok=True)
            with open(orch_log, 'w', encoding='utf-8') as orch_out:
                r = subprocess.run(
                    [PYTHON, ORCHESTRATOR],
                    cwd=BASE, stdout=orch_out, stderr=subprocess.STDOUT,
                    timeout=600,
                    env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
                )
            log_sub('ORCH', r.returncode)
        except subprocess.TimeoutExpired:
            log_sub('ORCH', 124)
            # ゾンビ掃除
            _kill_firefox()
        except Exception as e:
            log_sub('ORCH', str(e)[:20])


# ── メイン ──
def main() -> None:
    log('=== Kensho Daemon 起動 ===')
    log(f'PID: {os.getpid()}, CWD: {BASE}')
    log(f'Python: {PYTHON}')
    log(f'Platform: {platform.system()}')

    # ゾンビ掃除（初回）
    _kill_firefox()

    # スレッド起動（_run_with_restart でラップして例外時再起動）
    threads = [
        ('keepalive', thread_keepalive),
        ('orchestrator', thread_orchestrator),
    ]
    for name, fn in threads:
        t = threading.Thread(target=_run_with_restart, args=(name, fn), daemon=True, name=name)
        t.start()
        log(f'スレッド起動: {name}')

    log('初回サイクル完了。常駐開始')

    # メインスレッドを生かし続ける
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log('停止信号受信 → グレースフルシャットダウン')
        log('Firefoxプロセスをクリーンアップ中...')
        _kill_firefox()
        log('停止完了')
        sys.exit(0)

if __name__ == '__main__':
    main()
