"""
Kensho Task Builder — config.yaml → schtasks コマンド生成
"""
from __future__ import annotations

import subprocess, os, yaml
from pathlib import Path
from typing import Any

# デフォルト値（config.yaml から動的取得するためのフォールバック）
DEFAULT_PYTHON: str = r'C:\Users\1F\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe'
DEFAULT_PROJECT_DIR: str = r'D:\Project2\kensho'

# 起動時に config.yaml から動的に読み込む
_config_path = Path(__file__).parent.parent / 'config.yaml'
if _config_path.exists():
    try:
        with open(_config_path) as _f:
            _cfg: dict[str, Any] = yaml.safe_load(_f)
        _gen = _cfg.get('general', {})
        # config.yaml の python パスを直接使う
        PYTHON = _gen.get('python', DEFAULT_PYTHON)
        PROJECT_DIR = _gen.get('project_dir', DEFAULT_PROJECT_DIR)
    except Exception:
        PYTHON = DEFAULT_PYTHON
        PROJECT_DIR = DEFAULT_PROJECT_DIR
else:
    PYTHON = DEFAULT_PYTHON
    PROJECT_DIR = DEFAULT_PROJECT_DIR


def run_schtasks(args: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """schtasksコマンド実行"""
    cmd = ['schtasks'] + args
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        out = r.stdout.decode('cp932', errors='replace')
        err = r.stderr.decode('cp932', errors='replace') if r.stderr else ''
        return r.returncode, out, err
    except subprocess.TimeoutExpired:
        return -1, '', 'Timeout'
    except Exception as e:
        return -1, '', str(e)

def delete_task(name: str) -> str:
    """タスク削除（存在しなくてもエラーにしない）"""
    full = f'Kensho\\{name}'
    rc, out, err = run_schtasks(['/delete', '/tn', full, '/f'])
    if rc == 0:
        return f'  ✅ 削除: {full}'
    elif '存在' in err or '指定され' in err:
        return f'  ⏭️  なし: {full}'
    else:
        return f'  ⚠️  削除失敗({rc}): {full}'

def create_task(name: str, script: str, args: list[str] | None, sched_type: str, sched_val: int) -> str:
    """タスク作成"""
    full = f'Kensho\\{name}'
    cmd_parts = [PYTHON, script]
    if args:
        cmd_parts.extend(args)
    cmd = ' '.join(cmd_parts)
    
    if sched_type == 'minute':
        trigger = ['/sc', 'minute', '/mo', str(sched_val)]
    else:
        return f'  ❌ 不明なsched_type: {sched_type}'
    
    rc, out, err = run_schtasks(
        ['/create', '/tn', full, '/tr', cmd, '/f', '/it'] + trigger
    )
    
    if rc == 0 and ('SUCCESS' in out or '成功' in out):
        return f'  ✅ 作成: {full} ({sched_type}:{sched_val})'
    else:
        return f'  ❌ 失敗({rc}): {full}\n     {out[:200]}\n     {err[:200]}'

def build_all(cfg: dict[str, Any]) -> list[str]:
    """
    config.yaml の内容から全タスクを作成。
    常に2タスクのみ生成:
      - Kensho\Keepalive (5分おき)
      - Kensho\Orchestrator (15分おき)
    """
    results = []
    
    # Keepalive（5分おき）
    interval = cfg.get('keepalive', {}).get('interval_minutes', 5)
    results.append(
        create_task('Keepalive', os.path.join('keepalive', 'checker.py'), None, 'minute', interval)
    )
    
    # Orchestrator（15分おき）
    orch_interval = cfg.get('orchestrator', {}).get('interval_minutes', 15)
    results.append(
        create_task('Orchestrator', 'orchestrator.py', None, 'minute', orch_interval)
    )
    
    return results
