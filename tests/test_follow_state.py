"""FollowStateManagerのテスト — 過フォロー防止ロジックの動作保証。"""

from __future__ import annotations

import json
from pathlib import Path

from kensho.application.follow_state_manager import (
    MAX_FOLLOWS_PER_OWNER_PER_DAY,
    FollowStateManager,
)


def _make_manager(tmp_path: Path, account: str = "test_acct") -> FollowStateManager:
    """一時ディレクトリのfollow_state.jsonを使うマネージャを返す。"""
    return FollowStateManager(account, state_path=tmp_path / "follow_state.json")


def test_should_follow_initial(tmp_path: Path) -> None:
    """初期状態ではフォローして良い。"""
    m = _make_manager(tmp_path)
    assert m.should_follow("mobage_campaign") is True


def test_follow_limit_enforced(tmp_path: Path) -> None:
    """同一主催者へのフォローは上限まで許可、超過は拒否。"""
    m = _make_manager(tmp_path)
    for _ in range(MAX_FOLLOWS_PER_OWNER_PER_DAY):
        assert m.should_follow("owner1") is True
        m.record_follow("owner1")
    # 上限超過 → 拒否
    assert m.should_follow("owner1") is False


def test_other_owner_not_affected(tmp_path: Path) -> None:
    """別の主催者には影響しない。"""
    m = _make_manager(tmp_path)
    for _ in range(MAX_FOLLOWS_PER_OWNER_PER_DAY):
        m.record_follow("ownerA")
    assert m.should_follow("ownerB") is True


def test_persist_across_instances(tmp_path: Path) -> None:
    """記録はファイルに永続化され、別インスタンスからも読める。"""
    path = tmp_path / "follow_state.json"
    m1 = FollowStateManager("acct1", state_path=path)
    m1.record_follow("ownerX")
    m2 = FollowStateManager("acct1", state_path=path)
    assert m2.should_follow("ownerX") is True
    m2.record_follow("ownerX")
    # ファイルに書き込まれている
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["acct1"]["followed"]["ownerX"]) == 2


def test_account_isolation(tmp_path: Path) -> None:
    """アカウント間でフォロー記録は分離される。"""
    m1 = _make_manager(tmp_path, "acct1")
    m2 = _make_manager(tmp_path, "acct2")
    for _ in range(MAX_FOLLOWS_PER_OWNER_PER_DAY):
        m1.record_follow("ownerY")
    assert m1.should_follow("ownerY") is False
    assert m2.should_follow("ownerY") is True
