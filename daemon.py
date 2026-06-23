#!/usr/bin/env python3
"""
Kensho Daemon — 常駐デーモン、窓ゼロ、3スレッド並列実行
"""
from __future__ import annotations

import sys, os, json, time, subprocess, threading, atexit, ctypes, traceback
from typing import Any

# ── cp932ガード ──
os.environ['PYTHONIOENCODING'] = 'utf-8'
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)  # type: ignore[union-attr]
    except Exception:
        sys.stdout.reconfigure(line_buffering=True)

# ── コンソール窓を即座に隠す ──
try:
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
except Exception:
    pass

# ── パス設定 ──
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
LOG_DIR = os.path.join(BASE, 'logs')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

PYTHON = sys.executable
ORCHESTRATOR = os.path.join(BASE, 'orchestrator.py')
KEEPALIVE = os.path.join(BASE, 'keepalive', 'checker.py')

# ── Mutex: 二重起動防止 ──
import ctypes.wintypes
MUTEX_NAME = "KenshoDaemon_Mutex_v3"
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
if mutex and ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    ctypes.windll.kernel32.CloseHandle(mutex)
    sys.exit(0)

def _release_mutex() -> None:
    if mutex:
        ctypes.windll.kernel32.ReleaseMutex(mutex)
        ctypes.windll.kernel32.CloseHandle(mutex)
atexit.register(_release_mutex)

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
            ts = time.strftime('%H:%M:%S')
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
    interval = 900  # 15分
    while True:
        try:
            r = subprocess.run(
                [PYTHON, ORCHESTRATOR],
                cwd=BASE, capture_output=True, timeout=600,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
            )
            log_sub('ORCH', r.returncode)
        except subprocess.TimeoutExpired:
            log_sub('ORCH', 124)
            # ゾンビ掃除
            os.system('taskkill /F /IM firefox.exe 2>nul')
        except Exception as e:
            log_sub('ORCH', str(e)[:20])


# ── メイン ──
def main() -> None:
    log('=== Kensho Daemon 起動 ===')
    log(f'PID: {os.getpid()}, CWD: {BASE}')
    log(f'Python: {PYTHON}')

    # ゾンビ掃除（初回）
    os.system('taskkill /F /IM firefox.exe 2>nul')

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
        os.system('taskkill /F /IM firefox.exe 2>nul')
        log('停止完了')
        sys.exit(0)

if __name__ == '__main__':
    main()
