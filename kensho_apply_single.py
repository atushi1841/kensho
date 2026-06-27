#!/usr/bin/env python3
"""Kensho Single Apply — 手動CLI: 1垢の応募を実行（ForceBindIP不要、orchestratorは直接呼び出し）"""
from __future__ import annotations
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from core.encoding import guard_stdio
guard_stdio()
from application.applier import apply_for_account  # noqa: E402

if __name__ == '__main__':
    from argparse import ArgumentParser
    _p = ArgumentParser(description='Kensho 単一アカウント応募（CLI）')
    _p.add_argument('account', help='アカウントキー (例: atushi16)')
    _p.add_argument('max_n', type=int, nargs='?', default=10, help='最大処理件数（省略時10）')
    _p.add_argument('--dry-run', action='store_true', help='実際に応募せずログのみ')
    _args = _p.parse_args()

    succ, err = apply_for_account(_args.account, _args.max_n, dry_run=_args.dry_run)
    print(f'\nRESULT: {succ} success, {err} errors')
    sys.exit(1 if err > 0 else 0)
