"""
Kensho Utils — サブプロセス実行（統一エラーハンドリング）
"""
from __future__ import annotations

import subprocess, sys
from typing import Any


def run(cmd: list[str], timeout: int = 60, capture: bool = True, encoding: str = 'cp932') -> dict[str, Any]:
    """
    サブプロセスを実行し、結果を返す。
    エンコーディング問題（cp932/utf-8）に対応。

    Returns:
        dict with keys: returncode, stdout, stderr, success
    """
    kwargs: dict[str, Any] = {'timeout': timeout}
    if capture:
        kwargs['capture_output'] = True
        kwargs['text'] = False

    try:
        r = subprocess.run(cmd, **kwargs)
        stdout: str = r.stdout.decode(encoding, errors='replace') if r.stdout else ''
        stderr: str = r.stderr.decode(encoding, errors='replace') if r.stderr else ''

        return {
            'returncode': r.returncode,
            'stdout': stdout,
            'stderr': stderr,
            'success': r.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            'returncode': -1,
            'stdout': '',
            'stderr': 'Timeout',
            'success': False,
        }
    except Exception as e:
        return {
            'returncode': -2,
            'stdout': '',
            'stderr': str(e),
            'success': False,
        }


def run_pwsh(script: str, timeout: int = 15) -> dict[str, Any]:
    """PowerShellスクリプト実行"""
    return run(
        ['powershell', '-NoProfile', '-Command', script],
        timeout=timeout
    )
