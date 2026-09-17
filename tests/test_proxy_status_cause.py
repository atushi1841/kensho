"""t_9e8a1b2c: プロキシ死骸のステータス原因明記 — 純関数のテスト。

dead_proxy マーカー / 最終成功 / 最終エラー種別 / 停止理由 が構造化されることを保証する。
汎用化 build_proxy_panel が "全垢生存" と "死骸あり" を正しく分けることも確認する。
"""

from kensho.utils.proxy_watchdog import (
    PROXY_STATUS,
    account_proxy_status,
    build_proxy_panel,
)

ALIVE = [1081, 1082, 1084, 1085]
DEAD = [1087]


def test_proxy_status_schema_contains_dead_proxy():
    """受け入れ(numeric): grep 'dead_proxy' data/status/*.json が hit する元。"""
    assert "dead_proxy" in PROXY_STATUS


def test_dead_proxy_marks_dead_port():
    st = account_proxy_status(
        1087,
        ALIVE,
        DEAD,
        success_ts="2026-09-17T08:00Z",
        success_action="follow",
        last_error_type="http_0",
        dead_reason="アダプタ切断/復旧不可",
    )
    assert st["status"] == "dead_proxy"
    assert st["last_error_type"] == "http_0"
    assert "アダプタ切断" in st["stop_reason"]
    assert st["last_success"].startswith("2026-09-17T08:00Z")
    assert "dead_proxy" in st["status_schema"]


def test_alive_proxy_no_stop_reason():
    st = account_proxy_status(1081, ALIVE, DEAD, success_ts="2026-09-18T00:00Z", success_action="like")
    assert st["status"] == "alive"
    assert st["stop_reason"] == ""


def test_unchecked_when_port_not_in_both_lists():
    # 稼働対象外ポート（未チェック）は unchecked
    st = account_proxy_status(9999, ALIVE, DEAD)
    assert st["status"] == "unchecked"


def test_build_panel_flags_dead_account():
    accts = {
        a: account_proxy_status(p, ALIVE, DEAD)
        for a, p in [
            ("atushi16", 1081),
            ("kudou", 1082),
            ("zin20120731", 1084),
            ("TankanNotes", 1085),
            ("toushiwatch", 1087),
        ]
    }
    panel = build_proxy_panel(ALIVE, DEAD, restored=0, per_account=accts, ts="t")
    assert panel["ok"] is False
    assert ("toushiwatch", 1087) in panel["dead"]
    assert "atushi16" in panel["alive"]


def test_build_panel_reason_explicit_dead():
    accts = {"toushiwatch": account_proxy_status(1087, ALIVE, DEAD, dead_reason="egress不通")}
    # 死骸があると realworld 全垢の panel でも ok=False + reason 表示
    panel = build_proxy_panel(ALIVE, DEAD, restored=0, per_account=accts, ts="t")
    assert panel["ok"] is False
    assert "プロキシ不通" in panel["reason"]


def test_build_panel_all_alive_ok():
    accts = {"atushi16": account_proxy_status(1081, ALIVE, [])}
    panel = build_proxy_panel(ALIVE, [], restored=0, per_account=accts, ts="t")
    assert panel["ok"] is True
    assert panel["dead"] == []
    assert "正常" in panel["reason"]
