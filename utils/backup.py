"""
Kensho Backup Utility — 懸賞データのバックアップ・復旧管理
v1.0: collected.json / daily_counts.json の安全な保存と自動復旧
"""
from __future__ import annotations

import json, os, time, glob, re
from datetime import datetime
from pathlib import Path
from shutil import copy2
from typing import Any

# バックアップ設定
BACKUP_DIR_NAME = 'backups'
MAX_BACKUPS = 20


def safe_save_json(filepath: str | Path, data: Any, label: str = 'data') -> None:
    """
    collected.json などの重要なJSONファイルを安全に保存する。
    保存前に自動バックアップを取得し、クラッシュ時のデータ消失を防ぐ。
    """
    path = Path(filepath)
    backup_dir = path.parent / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 既存ファイルがあればバックアップ
    if path.exists() and path.stat().st_size > 0:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f'{path.name}.{ts}.bak'
        backup_path = backup_dir / backup_name
        try:
            copy2(str(path), str(backup_path))
            if backup_path.stat().st_size == 0:
                backup_path.unlink()
                print(f'[BACKUP] ⚠️ {backup_name}: 空ファイル → 破棄')
            else:
                print(f'[BACKUP] ✅ {backup_name}')
        except Exception as e:
            print(f'[BACKUP] ❌ バックアップ失敗: {e}')

    # 古いバックアップを削除
    _cleanup_old_backups(backup_dir, path.name)

    # 新データを一時ファイルに書き込み → リネーム（アトミック保存）
    tmp_path = path.with_suffix('.tmp')
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(path)
        count = len(data.get("collected", data)) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0
        print(f'[SAVE] ✅ {label}保存完了 ({count}件)')
    except Exception as e:
        print(f'[SAVE] ❌ 保存失敗: {e}')
        _try_restore_from_backup(path, label)


def _cleanup_old_backups(backup_dir: Path, filename: str) -> None:
    """古いバックアップを削除"""
    backups: list[Path] = sorted(backup_dir.glob(f'{filename}.*.bak'))
    while len(backups) > MAX_BACKUPS:
        oldest = backups.pop(0)
        try:
            oldest.unlink()
        except Exception:
            pass


def _try_restore_from_backup(filepath: str | Path, label: str = 'data') -> None:
    """バックアップから復元を試みる"""
    backup_dir = Path(filepath).parent / BACKUP_DIR_NAME
    backups: list[Path] = sorted(backup_dir.glob(f'{Path(filepath).name}.*.bak'))
    if not backups:
        print(f'[RESTORE] ❌ {label}: 復元できるバックアップなし')
        return

    for backup_path in reversed(backups):
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                data: Any = json.load(f)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            restore_count = len(data.get("collected", data)) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0
            print(f'[RESTORE] ✅ {label}: {backup_path.name} から復元完了 ({restore_count}件)')
            return
        except Exception as e:
            print(f'[RESTORE] ⚠️ {backup_path.name} からの復元失敗: {e}')
            continue

    print(f'[RESTORE] ❌ {label}: すべてのバックアップが破損')


def try_recover_collected(processed_file: str | Path, collected_file: str | Path, account_keys: list[str]) -> bool:
    """
    collected.json が失われた場合、processed.json の履歴から
    収集済みURLのリストを再構築するためのスタブを作成する。
    """
    col_path = Path(collected_file)
    if col_path.exists() and col_path.stat().st_size > 500:
        return False

    if col_path.exists() and col_path.stat().st_size == 0:
        backup_dir = col_path.parent / BACKUP_DIR_NAME
        backups: list[Path] = sorted(backup_dir.glob(f'{col_path.name}.*.bak'))
        if backups:
            print(f'[RECOVER] 🔄 collected.jsonが空 → バックアップから復元試行')
            _try_restore_from_backup(col_path, 'collected.json')
            if col_path.exists() and col_path.stat().st_size > 500:
                return True

    print(f'[RECOVER] ⚠️ collected.json が見つからないか空です')
    print(f'[RECOVER] ⚠️ processed.json に {_count_processed(processed_file)}件の履歴がありますが、')
    print(f'[RECOVER] ⚠️ 応募状態（applied）の情報は失われています')
    print(f'[RECOVER] ⚠️ 新規収集を実行してください')
    return True


def _count_processed(processed_file: str | Path) -> int:
    """processed.jsonの件数を取得"""
    try:
        with open(processed_file, 'r') as f:
            data: dict[str, Any] = json.load(f)
        return len(data.get('ids', []))
    except Exception:
        return 0


def verify_collected_integrity(collected_file: str | Path, processed_file: str | Path) -> dict[str, Any]:
    """
    collected.json の整合性チェック。
    processed.json と比較して異常に少ない場合は警告。
    """
    try:
        with open(collected_file, 'r') as f:
            col_data: dict[str, Any] = json.load(f)
        col_count: int = len(col_data.get('collected', []))
    except Exception:
        col_count = 0

    try:
        with open(processed_file, 'r') as f:
            proc_data: dict[str, Any] = json.load(f)
        proc_count: int = len(proc_data.get('ids', []))
    except Exception:
        proc_count = 0

    result: dict[str, Any] = {
        'ok': True,
        'collected_count': col_count,
        'processed_count': proc_count,
    }

    if proc_count > 0 and col_count == 0:
        result['ok'] = False
        result['message'] = f'⚠️ collected.json が空です（processed.json: {proc_count}件）'
    elif proc_count > 100 and col_count < 5:
        result['ok'] = False
        result['message'] = f'⚠️ collected.json が異常に少ないです（{col_count}件 / processed: {proc_count}件）'
    elif col_count > 0:
        result['message'] = f'✅ collected.json: {col_count}件 / processed.json: {proc_count}件'
    else:
        result['message'] = f'📭 collected.json: 0件、processed.json: 0件（初期状態）'

    return result
