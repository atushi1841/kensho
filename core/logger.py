"""
Kensho Logger — ログ出力・日次サマリー生成
"""
from __future__ import annotations

import sys, os, time
from pathlib import Path
from datetime import datetime

BASE: Path = Path(__file__).parent.parent
LOGS_DIR: Path = BASE / 'logs'
SUMMARY_DIR: Path = LOGS_DIR / 'summary'


def ensure_dirs() -> Path:
    """日付フォルダを作成"""
    today: str = datetime.now().strftime('%Y-%m-%d')
    day_dir: Path = LOGS_DIR / today
    day_dir.mkdir(parents=True, exist_ok=True)
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    return day_dir


def make_path(prefix: str, suffix: str = 'log') -> Path:
    """ログファイルパスを生成（例: logs/2026-06-18/apply_kudou_153000.log）"""
    day_dir: Path = ensure_dirs()
    ts: str = datetime.now().strftime('%H%M%S')
    return day_dir / f'{prefix}_{ts}.{suffix}'


class LogWriter:
    """ファイル＋標準出力への同時書き込み"""

    def __init__(self, path: str | Path, echo: bool = True) -> None:
        self.path: Path = Path(path)
        self.echo: bool = echo
        self._file = open(self.path, 'w', encoding='utf-8')

    def write(self, msg: str) -> None:
        ts: str = datetime.now().strftime('%H:%M:%S')
        line: str = f'[{ts}] {msg}'
        self._file.write(line + '\n')
        self._file.flush()
        if self.echo:
            print(line, flush=True)

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> 'LogWriter':
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object) -> None:
        self.close()
        return None


def write_daily_summary() -> Path | None:
    """日次サマリーを Markdown で生成（Obsidianで読める形式）"""
    today: str = datetime.now().strftime('%Y-%m-%d')
    day_dir: Path = LOGS_DIR / today
    if not day_dir.exists():
        return None

    log_files: list[Path] = sorted(day_dir.glob('*.log'))

    summary: list[str] = []
    summary.append(f'# 📊 Kensho 日次サマリー {today}')
    summary.append('')
    summary.append(f'**生成:** {datetime.now().strftime("%Y-%m-%d %H:%M")} JST')
    summary.append('')
    summary.append('## 実行ログ')
    summary.append('')
    summary.append('| 時刻 | 種別 | ファイル |')
    summary.append('|------|------|---------|')

    for f in log_files:
        name: str = f.stem
        parts: list[str] = name.split('_')
        kind: str = parts[0] if parts else 'unknown'
        ts: str = parts[-1] if len(parts) > 1 else '??????'
        time_str: str = f'{ts[:2]}:{ts[2:4]}:{ts[4:6]}' if len(ts) == 6 else ts
        summary.append(f'| {time_str} | {kind} | `{f.name}` |')

    summary.append('')
    summary.append('---')
    summary.append('*自動生成されました*')

    out_path: Path = SUMMARY_DIR / f'{today}.md'
    out_str: str = '\n'.join(summary) + '\n'
    with open(str(out_path), 'w', encoding='utf-8') as fh:
        fh.write(out_str)

    return out_path
