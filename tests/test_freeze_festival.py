"""
Tests for kensho/utils/freeze_festival.py — 凍結祭りモニタリング（提案52）
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.utils.freeze_festival import (
    check_and_update,
    get_action_scale,
    load_state,
    save_state,
)

TODAY = date.today().isoformat()


def make_cfg(project_dir: Path, **overrides: object) -> dict:
    cfg: dict = {
        "general": {"project_dir": str(project_dir)},
        "freeze_festival": {
            "enabled": True,
            "scale": 0.5,
            "valid_days": 3,
            "search_query": "凍結祭り",
        },
    }
    cfg["freeze_festival"].update(overrides)
    return cfg


class TestGetActionScale:
    def test_no_state_default_1(self, tmp_path: Path) -> None:
        """stateなし → 1.0（通常運用）"""
        assert get_action_scale(make_cfg(tmp_path)) == 1.0

    def test_observed_recent_half(self, tmp_path: Path) -> None:
        """観測中（当日） → scale 0.5"""
        save_state(
            make_cfg(tmp_path),
            {"last_checked": TODAY, "observed": True, "evidence": ["凍結祭り発生"]},
        )
        assert get_action_scale(make_cfg(tmp_path)) == 0.5

    def test_observed_stale_returns_1(self, tmp_path: Path) -> None:
        """観測情報がvalid_days(3日)より古い → 1.0（通常運用に戻す）"""
        save_state(
            make_cfg(tmp_path),
            {"last_checked": "2026-08-20", "observed": True, "evidence": []},
        )
        assert get_action_scale(make_cfg(tmp_path)) == 1.0

    def test_disabled_returns_1(self, tmp_path: Path) -> None:
        """enabled=False → 観測中でも1.0"""
        save_state(
            make_cfg(tmp_path),
            {"last_checked": TODAY, "observed": True, "evidence": []},
        )
        cfg = make_cfg(tmp_path, enabled=False)
        assert get_action_scale(cfg) == 1.0


class TestCheckAndUpdate:
    def test_observed_when_wave_titles(self, tmp_path: Path) -> None:
        """「凍結祭り発生中」を示すタイトルが2件以上 → observed=True・state保存"""
        cfg = make_cfg(tmp_path)
        with patch(
            "kensho.utils.freeze_festival._search",
            return_value=[
                "【速報】Xで大規模な凍結祭りが発生中",
                "Xの凍結祭りでフォロワー急減の報告相次ぐ",
                "Xの凍結祭りとは？原因と対策を解説",  # 常設解説 → 波判定されない
            ],
        ):
            assert check_and_update(cfg) is True
        state = load_state(cfg)
        assert state["observed"] is True
        assert state["last_checked"] != ""
        assert len(state["evidence"]) == 2

    def test_not_observed_with_single_wave(self, tmp_path: Path) -> None:
        """波タイトル1件のみ → observed=False（ノイズ判定）"""
        cfg = make_cfg(tmp_path)
        with patch(
            "kensho.utils.freeze_festival._search",
            return_value=["Xで大規模な凍結祭りが発生中"],
        ):
            assert check_and_update(cfg) is False
        assert load_state(cfg)["observed"] is False

    def test_not_observed_when_evergreen_only(self, tmp_path: Path) -> None:
        """常設解説記事のみ（波キーワードなし）→ observed=False"""
        cfg = make_cfg(tmp_path)
        with patch(
            "kensho.utils.freeze_festival._search",
            return_value=[
                "Xの凍結祭りとは？原因と対策を解説",
                "「凍結祭り」のYahoo!リアルタイム検索",
            ],
        ):
            assert check_and_update(cfg) is False
        assert load_state(cfg)["observed"] is False

    def test_fail_open_on_search_error(self, tmp_path: Path) -> None:
        """検索失敗（SearXNG不通等） → observed=Falseで通常運用継続（fail-open）"""
        cfg = make_cfg(tmp_path)
        with patch("kensho.utils.freeze_festival._search", return_value=[]):
            assert check_and_update(cfg) is False
        assert load_state(cfg)["observed"] is False

    def test_only_once_per_day(self, tmp_path: Path) -> None:
        """当日チェック済みなら再検索しない（2回目は検索関数を呼ばない）"""
        cfg = make_cfg(tmp_path)
        save_state(cfg, {"last_checked": TODAY, "observed": False, "evidence": []})
        with patch(
            "kensho.utils.freeze_festival._search",
            return_value=["Xで大規模な凍結祭りが発生中", "Xの凍結祭りで急減"],
        ) as m:
            assert check_and_update(cfg) is False  # 当日既チェック → observedのまま
            m.assert_not_called()
