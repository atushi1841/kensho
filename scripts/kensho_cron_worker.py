#!/usr/bin/env python3
"""
Kensho Cron Worker — no_agent cron用
使い方:
  python scripts/kensho_cron_worker.py <account> [max_n]
  例: python scripts/kensho_cron_worker.py atushi16 15

ログファイル: logs/cron_{account}_YYYY-MM-DD_HHMMSS.log
"""
from __future__ import annotations
import sys, subprocess, time, json, os
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.encoding import guard_stdio, cp932_safe
guard_stdio()

PYTHON = r'C:\Users\1F\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
BASE = Path(__file__).parent
LOGS_DIR = BASE / 'logs'
DATA_DIR = BASE / 'data'
COLLECTED_FILE = DATA_DIR / 'collected.json'
LOGS_DIR.mkdir(exist_ok=True)

# 収集データの鮮度閾値（2時間以上経過で再収集）
REFRESH_THRESHOLD = timedelta(hours=2)

# ── ゾンビプロセス掃除 ──
def kill_zombies():
    """Firefox/Chromeのゾンビを確実に掃除"""
    for exe in ['firefox.exe']:
        for _ in range(3):  # 最大3回リトライ
            r = subprocess.run(['taskkill', '/F', '/IM', exe],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                time.sleep(1)  # プロセス終了待ち
            else:
                break  # もうプロセスがなくなった

def write_log(log_path, text):
    """ログファイルに追記（utf-8固定）"""
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(text)

def is_collection_stale():
    """収集データが2時間以上前のものかチェック"""
    if not COLLECTED_FILE.exists():
        return True  # ファイルがない＝収集が必要
    try:
        with open(COLLECTED_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        ts = data.get('timestamp', '')
        if not ts:
            return True
        collected_time = datetime.fromisoformat(ts)
        age = datetime.now() - collected_time
        return age > REFRESH_THRESHOLD
    except (json.JSONDecodeError, ValueError, OSError):
        return True  # 読めないなら再収集

def run_collect(log):
    """kensho_collect.py を実行（最大50件）"""
    log("--- Collect ---")
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    logpath = LOGS_DIR / f'collect_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    try:
        with open(logpath, 'w', encoding='utf-8') as lf:
            r = subprocess.run(
                [PYTHON, 'kensho_collect.py', '--max-items', '50', '--pages', '3'],
                cwd=str(BASE), stdout=lf, stderr=subprocess.STDOUT, timeout=300,
                env=env
            )
        try:
            with open(logpath, 'r', encoding='utf-8') as lf:
                content = lf.read()
            log(content[-500:] if content else "(no output)")
        except Exception:
            log("(log read failed)")
        if r.returncode != 0:
            log(f"WARN: collect exit code {r.returncode}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        log("ERROR: collect timed out (300s)")
        return False
    except Exception as e:
        log(f"ERROR: collect failed: {e}")
        return False

def run_apply(account, max_n, log):
    """kensho_apply_single.py を実行"""
    log(f"\n--- Apply ({account}, max={max_n}) ---")
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    logpath = LOGS_DIR / f'apply_{account}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    try:
        with open(logpath, 'w', encoding='utf-8') as lf:
            r = subprocess.run(
                [PYTHON, 'kensho_apply_single.py', account, str(max_n)],
                cwd=str(BASE), stdout=lf, stderr=subprocess.STDOUT, timeout=1200,
                env=env
            )
        try:
            with open(logpath, 'r', encoding='utf-8') as lf:
                content = lf.read()
            log(content[-1500:] if content else "(no output)")
        except Exception:
            log("(log read failed)")
        if r.returncode != 0:
            log(f"WARN: apply exit code {r.returncode}")
        return r.returncode
    except subprocess.TimeoutExpired:
        log("ERROR: apply timed out (1200s)")
        return 124
    except Exception as e:
        log(f"ERROR: apply failed: {e}")
        return 1

def main():
    if len(sys.argv) < 3:
        print("Usage: kensho_cron_worker.py <morning|apply> <account> [max_n]")
        print("  例: kensho_cron_worker.py morning zin 15")
        print("  例: kensho_cron_worker.py apply kudou 10")
        sys.exit(1)

    mode = sys.argv[1]
    account = sys.argv[2]
    max_n = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    # ログファイル設定
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    log_path = LOGS_DIR / f'cron_{account}_{mode}_{timestamp}.log'

    def log(msg):
        """標準出力（cp932セーフ）+ ログファイル"""
        safe_msg: str = cp932_safe(msg)
        print(safe_msg, flush=True)
        write_log(log_path, msg + '\n')

    log(f"=== Kensho Cron Worker ===")
    log(f"Mode: {mode}, Account: {account}, Max: {max_n}")
    log(f"Start: {time.strftime('%H:%M:%S')}")
    log(f"Log: {log_path}")

    # ゾンビプロセスを確実に掃除（Firefoxが残ってると次回起動時にハング）
    log("--- Zombie cleanup ---")
    kill_zombies()
    log("Done.")

    if mode == 'morning':
        # 朝モード: 常に収集+応募
        run_collect(log)
    elif mode == 'apply':
        # 通常モード: 収集データが古ければ再収集
        if is_collection_stale():
            log("--- 収集データが古いため再収集 ---")
            run_collect(log)
        else:
            log("--- 収集データは新鮮（スキップ） ---")
    else:
        log(f"ERROR: 不明なモード: {mode}")
        sys.exit(1)

    # 応募
    exit_code = run_apply(account, max_n, log)

    log(f"\n=== Done: {time.strftime('%H:%M:%S')} (exit={exit_code}) ===")
    sys.exit(exit_code if exit_code != 0 else 0)

if __name__ == '__main__':
    main()
