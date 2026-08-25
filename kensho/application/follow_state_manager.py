"""フォロー状態管理 — follow_state.json の読み書きとフォロー済みチェック。

用途:
- 同一主催者への過剰フォロー防止（BOT検出回避）
- フォロー済み主催者リストの管理（1日N回まで制限）
- 追跡データの永続化

使い方:
    from kensho.application.follow_state_manager import FollowStateManager

    fsm = FollowStateManager("atushi16")
    if fsm.should_follow("mobage_campaign"):
        # フォロー実行
        fsm.record_follow("mobage_campaign")
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

# 同一主催者への1日フォロー上限（これを超えたらスキップ）
MAX_FOLLOWS_PER_OWNER_PER_DAY = 2

# フォロー状態ファイル
_STATE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "follow_state.json"

JST = datetime.timezone(datetime.timedelta(hours=9))


class FollowStateManager:
    """アカウントごとのフォロー状態管理。"""

    def __init__(self, account_key: str) -> None:
        self._account_key = account_key
        self._state: dict = self._load()

    def _load(self) -> dict:
        try:
            if _STATE_PATH.exists():
                return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save(self) -> None:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")

    def should_follow(self, screen_name: str) -> bool:
        """この主催者にフォローして良いか判定。上限超過ならFalse。"""
        today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
        entries = self._state.get(self._account_key, {}).get("followed", {}).get(screen_name, [])
        # 今日のフォロー回数
        today_count = sum(1 for d in entries if d == today)
        return today_count < MAX_FOLLOWS_PER_OWNER_PER_DAY

    def record_follow(self, screen_name: str) -> None:
        """フォロー成功を記録。"""
        today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
        self._state.setdefault(self._account_key, {}).setdefault("followed", {}).setdefault(screen_name, [])
        self._state[self._account_key]["followed"][screen_name].append(today)
        self._save()

    def get_today_follows(self, screen_name: str | None = None) -> list[str]:
        """今日フォローした主催者一覧（または特定主催者の今日のフォロー日時）。"""
        today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
        if screen_name:
            entries = self._state.get(self._account_key, {}).get("followed", {}).get(screen_name, [])
            return [d for d in entries if d == today]
        all_follows = self._state.get(self._account_key, {}).get("followed", {})
        result = []
        for name, dates in all_follows.items():
            if today in dates:
                result.append(name)
        return result
