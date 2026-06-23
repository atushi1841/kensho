"""
Kensho Config — YAML設定ファイルの読み込み・バリデーション
"""
from __future__ import annotations

import yaml, os
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH: Path = Path(__file__).parent.parent / 'config.yaml'


def load(path: str | Path | None = None) -> dict[str, Any]:
    """config.yaml を読み込み、バリデーションして返す"""
    resolved: Path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not resolved.exists():
        raise FileNotFoundError(f"Config not found: {resolved}")

    with open(resolved, encoding='utf-8') as f:
        cfg: dict[str, Any] = yaml.safe_load(f)

    validate(cfg)
    fill_defaults(cfg)
    return cfg


def validate(cfg: dict[str, Any]) -> None:
    """必須項目の存在チェック"""
    errors: list[str] = []

    if 'accounts' not in cfg or not cfg['accounts']:
        errors.append("accounts: 必須（1垢以上定義）")

    for i, acct in enumerate(cfg.get('accounts', [])):
        if 'key' not in acct:
            errors.append(f"accounts[{i}]: key がありません")
        if 'session' not in acct:
            errors.append(f"accounts[{i}]: session がありません")
        if 'schedule' not in acct or 'batches' not in acct.get('schedule', {}):
            errors.append(f"accounts[{i}]: schedule.batches がありません")

    if 'collection' not in cfg:
        errors.append("collection: 必須")

    if 'keepalive' not in cfg or 'interfaces' not in cfg['keepalive']:
        errors.append("keepalive.interfaces: 必須")

    if errors:
        raise ValueError("Config validation errors:\n" + "\n".join(errors))


def fill_defaults(cfg: dict[str, Any]) -> None:
    """デフォルト値で補完"""
    g: dict[str, Any] = cfg.setdefault('general', {})
    g.setdefault('project_dir', str(Path(__file__).parent.parent))
    g.setdefault('log_retention_days', 30)
    g.setdefault('session_warn_days', 3)

    n: dict[str, Any] = cfg.setdefault('notify', {})
    n.setdefault('discord_webhook', '')
    n.setdefault('windows_toast', False)

    col: dict[str, Any] = cfg.setdefault('collection', {})
    col.setdefault('source', 'https://knshow.com')
    col.setdefault('times', ['09:00', '13:00', '18:00'])
    col.setdefault('max_items', 200)

    ka: dict[str, Any] = cfg.setdefault('keepalive', {})
    ka.setdefault('interval_minutes', 5)
    ka.setdefault('interfaces', [])

    orch: dict[str, Any] = cfg.setdefault('orchestrator', {})
    orch.setdefault('interval_minutes', 15)
    orch.setdefault('max_accounts_per_run', 2)
    orch.setdefault('apply_timeout', 600)
    orch.setdefault('priority', 'round_robin')
