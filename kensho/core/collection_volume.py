"""collection_volume — 収集ボリューム指標（本日収集実績・累計）の単一情報源。

背景（2026-09-23 / t_5e16a983 の申し送り）:
  revenue-status.html の「本日収集実績」は手作業でHTMLへ追記された値であり、
  data/revenue-daily.json の collectors.collected_today も手書き値だった。
  そのため (a) ダッシュボードを再生成するとカードごと消える、
  (b) 翌日以降も同じ値（222固定）が残り続ける、という虚偽報告リスクがあった。
  本モジュールを唯一の集計元とし、収集スクリプト・ダッシュボード・整合性チェッカーが
  同じ数値を共有する。

集計定義（明示）:
  collected_today : 当日の収集ログ logs/collect_<YYYYMMDD>_*.log に出現した
                    ユニークX URL数。走査件数ではなく「収集URL件数」で、重複は1件に丸める。
                    収集が0件だったrunは0として扱う（ログにURL行が無いため）。
  collected_total : data/collected.json の collected リスト件数（累計・重複排除済み）。

使い方:
    from kensho.core import collection_volume
    stats = collection_volume.volume_stats()
    # -> {"collected_today": 478, "collected_total": 1191, ...}
"""

from __future__ import annotations

import json
import re
from datetime import date as _date
from pathlib import Path
from typing import Any

# プロジェクト既定ディレクトリ（呼び出し元が上書き可能）
DEFAULT_PROJECT_DIR = Path("/mnt/d/Project2/kensho")

# 収集ログに記録される懸賞ツイートURL（x.com / twitter.com 両対応）
_X_STATUS_URL = re.compile(r"https?://(?:x|twitter)\.com/[A-Za-z0-9_]+/status/\d+")


def _resolve_project_dir(project_dir: str | Path | None) -> Path:
    return Path(project_dir) if project_dir is not None else DEFAULT_PROJECT_DIR


def resolve_day(day: str | None = None) -> str:
    """集計対象日を YYYY-MM-DD で返す（未指定なら実行日）。"""
    if day:
        return day
    return _date.today().strftime("%Y-%m-%d")


def _log_paths(project_dir: Path, day: str) -> list[Path]:
    logs = project_dir / "logs"
    if not logs.is_dir():
        return []
    return sorted(logs.glob(f"collect_{day.replace('-', '')}_*.log"))


def count_today_runs(project_dir: str | Path | None = None, day: str | None = None) -> int:
    """当日の収集ログ本数（収集が実際に走ったrun数）。"""
    return len(_log_paths(_resolve_project_dir(project_dir), resolve_day(day)))


def count_today_collected(project_dir: str | Path | None = None, day: str | None = None) -> int:
    """当日の収集ログに出現したユニークX URL数。"""
    urls: set[str] = set()
    for path in _log_paths(_resolve_project_dir(project_dir), resolve_day(day)):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        urls.update(_X_STATUS_URL.findall(text))
    return len(urls)


def count_total_collected(project_dir: str | Path | None = None) -> int:
    """data/collected.json の累計収集件数（重複排除済み）。"""
    path = _resolve_project_dir(project_dir) / "data" / "collected.json"
    if not path.is_file():
        return 0
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    items = data.get("collected", []) if isinstance(data, dict) else data
    return len(items) if isinstance(items, list) else 0


def volume_stats(project_dir: str | Path | None = None, day: str | None = None) -> dict[str, Any]:
    """ダッシュボード/収集スクリプトが共有する収集ボリューム指標。"""
    resolved = _resolve_project_dir(project_dir)
    target_day = resolve_day(day)
    return {
        "collected_today": count_today_collected(resolved, target_day),
        "collected_total": count_total_collected(resolved),
        "collected_today_date": target_day,
        "collected_today_runs": count_today_runs(resolved, target_day),
        "collected_today_source": f"logs/collect_{target_day.replace('-', '')}_*.log",
    }
