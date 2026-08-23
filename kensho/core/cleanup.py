"""
Kensho Cleanup — ゾンビプロセス掃除 + ログローテーション v3
firefox/geckodriver + 孤立python.exe を確実にkill。
orchestrator起動時に毎回実行される。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
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
        proc_name = p.name().lower()
        try:
            cmdline = " ".join(p.cmdline()).lower()
        except Exception:
            cmdline = ""
        # Hermes 系（gateway / CLI / mcp watchdog）は絶対にkillしない。
        # Hermes の comm 名は "hermes" に変更されるため、psutil の name()
        # だけでは "python" を含まず、_get_linux_python_pids の cmdline 検出
        # には引っかかるのに保護から漏れる。ここで cmdline も併せて判定する。
        if "hermes" in cmdline or "hermes_cli" in cmdline or "mcp_stdio" in cmdline:
            return True
        if "python" in proc_name:
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


def kill_process_by_name(name: str, force: bool = True) -> bool:
    """プロセス名を指定して強制終了 (psutil)"""
    try:
        import psutil as _ps

        killed_any = False
        for proc in _ps.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == name.lower():
                    proc.kill()
                    killed_any = True
            except (_ps.NoSuchProcess, _ps.AccessDenied):
                continue
        return killed_any
    except (_ps.NoSuchProcess, _ps.AccessDenied, OSError):
        return False


def kill_process_by_pid(pid: int) -> bool:
    """指定PIDのプロセスを強制終了"""
    try:
        r = subprocess.run(["kill", "-9", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return r.returncode == 0
    except Exception:
        return False


def _get_linux_python_pids() -> list[int]:
    """Linux: ps aux から孤立pythonプロセスPID一覧を取得"""
    pids: list[int] = []
    try:
        r = subprocess.run(["ps", "aux"], capture_output=True, timeout=10, text=True)
        for line in r.stdout.splitlines():
            parts = line.split(None, 10)
            if len(parts) >= 11:
                try:
                    pid = int(parts[1])
                    cmd = parts[10]
                    # python プロセスを検出
                    if "python" in cmd.lower():
                        if not _is_daemon_or_child(pid):
                            pids.append(pid)
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass
    return pids


def kill_zombies(log: Any = None) -> dict[str, int]:
    """
    Kenshoが起動したFirefox/Chromeのゾンビプロセスを掃除。
    ユーザーが自分で開いたFirefoxは絶対に殺さない。
    最大5回リトライ。daemonプロセスは絶対に殺さない。
    """
    global PROTECTED_PIDS
    PROTECTED_PIDS = _get_protected_pids()

    killed: dict[str, int] = {}
    targets: list[str | int] = []

    # 対象プロセス名
    browser_exes = ["firefox", "geckodriver"]

    for exe in browser_exes:
        targets.append(exe)

    # 孤立pythonプロセス
    targets.extend(_get_linux_python_pids())

    firefox_killed: int = 0
    python_killed: int = 0

    # ユーザーのFirefoxを識別するため、親プロセスがpythonでなければスキップ
    def _is_kensho_firefox(exe_name: str) -> bool:
        """このexeのプロセスのうち、親がpythonのものだけ返す"""
        try:
            import psutil as _ps

            for proc in _ps.process_iter(["pid", "name", "ppid"]):
                try:
                    if proc.info["name"] and proc.info["name"].lower() == exe_name:
                        pp = _ps.Process(proc.info["ppid"])
                        if "python" in pp.name().lower():
                            return True
                except (_ps.NoSuchProcess, _ps.AccessDenied):
                    pass
        except Exception:
            pass
        return False

    # ユーザーFirefoxが動いているか事前確認
    user_firefox_active = False
    try:
        import psutil as _ps2

        browser_name = browser_exes[0]
        for proc in _ps2.process_iter(["pid", "name", "ppid"]):
            try:
                if proc.info["name"] and proc.info["name"].lower() == browser_name:
                    pp = _ps2.Process(proc.info["ppid"])
                    if "python" not in pp.name().lower():
                        user_firefox_active = True
                        break
            except (_ps2.NoSuchProcess, _ps2.AccessDenied):
                pass
    except Exception:
        pass

    if user_firefox_active and log:
        log.write("[CLEANUP] 🔒 ユーザーFirefox検出 → Kensho Firefoxのみkill")

    for exe in browser_exes:
        for _ in range(3):
            # ユーザーFirefoxがいる場合、親プロセスがpythonのFirefoxのみkill
            if user_firefox_active and exe == browser_exes[0]:
                if not _is_kensho_firefox(browser_exes[0]):
                    break  # Kensho Firefoxなし
            if kill_process_by_name(exe):
                firefox_killed += 1
                time.sleep(0.5)
            else:
                break

    for pid in [p for p in targets if isinstance(p, int)]:
        if not _is_daemon_or_child(pid):
            if kill_process_by_pid(pid):
                python_killed += 1

    killed["firefox"] = firefox_killed
    killed["python"] = python_killed

    if firefox_killed > 0 or python_killed > 0:
        msg = f"Zombie cleanup: firefox x{firefox_killed}, python x{python_killed}"
        if log:
            log.write(msg)
        else:
            print(msg)

    return killed


def _win_force_rmtree(path: str | Path) -> bool:
    """強制フォルダ削除"""
    try:
        shutil.rmtree(str(path))
        return True
    except Exception:
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
    """
    cutoff: datetime = datetime.now() - timedelta(days=retention_days)
    removed: int = 0

    if not os.path.isdir(log_dir):
        return 0

    for d in Path(log_dir).iterdir():
        if d.is_dir() and d.name.startswith("20"):
            try:
                dir_date: datetime = datetime.strptime(d.name, "%Y-%m-%d")
                if dir_date < cutoff:
                    if _win_force_rmtree(d):
                        removed += 1
            except ValueError:
                pass

    # 平置きログファイル（*.log）も mtime で判定して削除
    for f in Path(log_dir).glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass

    if removed > 0:
        msg = f"Log cleanup: removed {removed} old log items (>={retention_days} days)"
        if log:
            log.write(msg)
        else:
            print(msg)

    return removed
