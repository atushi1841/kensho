"""
Kensho Cleanup — ゾンビプロセス掃除 + ログローテーション v3
firefox/geckodriver + 孤立python.exe を確実にkill。
orchestrator起動時に毎回実行される。
"""
from __future__ import annotations

import subprocess, time, os, re, shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

# 絶対にkillしてはいけないPID（daemon自身）
PROTECTED_PIDS: set[int] = set()


def _get_protected_pids() -> set[int]:
    """現在のdaemonプロセスツリーを保護リストに追加"""
    pids: set[int] = set()
    try:
        import psutil
        current = psutil.Process(os.getpid())
        pids.add(current.pid)
        parent = current.parent()
        if parent:
            pids.add(parent.pid)
            gp = parent.parent()
            if gp:
                pids.add(gp.pid)
    except Exception as _e:
        print(f"[CLEANUP] ProtectedPID取得失敗: {_e}", flush=True)
    return pids


def _is_daemon_or_child(pid: int) -> bool:
    """指定PIDがdaemonツリーに属するか判定"""
    try:
        import psutil
        p = psutil.Process(pid)
        if p.name().lower() == 'pythonw.exe':
            return True
        for pp in PROTECTED_PIDS:
            if pid == pp:
                return True
            try:
                if p.parent() and p.parent().pid == pp:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def kill_zombies(log: Any = None) -> dict[str, int]:
    """
    Firefox/Chromeのゾンビプロセス + 孤立python.exe を掃除。
    最大5回リトライ。daemonプロセスは絶対に殺さない。
    """
    global PROTECTED_PIDS
    PROTECTED_PIDS = _get_protected_pids()

    killed: dict[str, int] = {}
    targets: list[str | int] = []

    for exe in ['firefox.exe', 'geckodriver.exe']:
        targets.append(exe)

    # 孤立python.exe（daemon以外）
    try:
        r = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV', '/NH'],
            capture_output=True, timeout=10
        )
        out: str = r.stdout.decode('cp932', errors='replace')
        for line in out.strip().split('\n'):
            parts: list[str] = line.strip('"').split('","')
            if len(parts) >= 2:
                try:
                    pid: int = int(parts[1])
                    if not _is_daemon_or_child(pid):
                        targets.append(pid)
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass

    firefox_killed: int = 0
    python_killed: int = 0

    for exe in ['firefox.exe', 'geckodriver.exe']:
        for _ in range(3):
            kill_ret: int = os.system(f'taskkill /F /IM {exe} 2>nul')
            if kill_ret == 0:
                if exe == 'firefox.exe':
                    firefox_killed += 1
                time.sleep(0.5)
            else:
                break

    for pid in [p for p in targets if isinstance(p, int)]:
        if not _is_daemon_or_child(pid):
            try:
                kill_ret2 = os.system(f'taskkill /F /PID {pid} 2>nul')
                if kill_ret2 == 0:
                    python_killed += 1
            except Exception:
                pass

    killed['firefox'] = firefox_killed
    killed['python'] = python_killed

    if firefox_killed > 0 or python_killed > 0:
        msg = f"Zombie cleanup: firefox x{firefox_killed}, python x{python_killed}"
        if log:
            log.write(msg)
        else:
            print(msg)

    return killed


def _win_force_rmtree(path: str | Path) -> bool:
    """
    Windowsでshutil.rmtreeが[Errno 22]で死ぬのを回避。
    cmdのrd /s /q を使う → パス長制限・ロックに強い。
    """
    try:
        os.system(f'attrib -R "{path}\\"*.*" /S 2>nul')
        r = subprocess.run(
            ['cmd', '/c', f'rd /s /q "{path}"'],
            capture_output=True, timeout=30
        )
        if r.returncode == 0:
            return True
    except Exception:
        pass
    try:
        def _onerror(func: Any, p: str, exc_info: Any) -> None:
            try:
                os.chmod(p, 0o777)
                func(p)
            except Exception:
                pass
        shutil.rmtree(str(path), onerror=_onerror)
        return True
    except Exception:
        return False


def clean_old_logs(log_dir: str | Path, retention_days: int = 30, log: Any = None) -> int:
    """
    retention_daysより古いログファイル/フォルダを削除。
    config.yaml の log_retention_days の値を使うこと。
    Windows [Errno 22] Invalid argument 対策済み。
    """
    cutoff: datetime = datetime.now() - timedelta(days=retention_days)
    removed: int = 0

    if not os.path.isdir(log_dir):
        return 0

    for d in Path(log_dir).iterdir():
        if d.is_dir() and d.name.startswith('20'):
            try:
                dir_date: datetime = datetime.strptime(d.name, '%Y-%m-%d')
                if dir_date < cutoff:
                    if _win_force_rmtree(d):
                        removed += 1
            except ValueError:
                pass

    if removed > 0:
        msg = f"Log cleanup: removed {removed} old log directories (>={retention_days} days)"
        if log:
            log.write(msg)
        else:
            print(msg)

    return removed
