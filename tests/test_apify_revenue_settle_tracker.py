"""Tests for scripts/apify_revenue_settle_tracker.py — owner-run filter regression (t_dcd41e9e).

apify_ppe_external_runner が owner 本人の token で run を起動するため、その run は
外部ユーザーrun ではない。settle 追跡の run_id_verified で userId==owner を
除外しないと、自己 run の課金(item) を実収益として誤計上していた（$1.80 偽収益）。
API は mock してネットワーク非依存で検証する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apify_revenue_settle_tracker as ast

OWNER = "VMz6nlpHoGIjTeSXS"


class _Resp:
    def __init__(self, status: int, payload: Any) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Any:
        return self._payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *a: Any) -> None:
        pass


def _mock_urlopen(req: Any, *args: Any, **kwargs: Any) -> _Resp:
    """urllib.request.urlopen のフェイク（Request の full_url を参照）。"""
    url = getattr(req, "full_url", str(req))
    # /users/me
    if "/users/me" in url:
        return _Resp(200, {"data": {"id": OWNER}})
    # list runs
    if "/runs?" in url or "/runs?" in url:
        return _Resp(200, {
            "data": {
                "items": [
                    {"id": "owner-run", "userId": OWNER, "startedAt": "2026-09-20T00:00:00Z"},
                    {"id": "ext-run", "userId": "ext-user-999", "startedAt": "2026-09-20T01:00:00Z"},
                ]
            }
        })
    # run detail
    if "/runs/" in url:
        if "owner-run" in url:
            return _Resp(200, {"data": {"userId": OWNER, "status": "SUCCEEDED",
                                         "chargedEventCounts": {"apify-default-dataset-item": 100}}})
        if "ext-run" in url:
            return _Resp(200, {"data": {"userId": "ext-user-999", "status": "SUCCEEDED",
                                         "chargedEventCounts": {"apify-default-dataset-item": 50}}})
        return _Resp(200, {"data": {"userId": "ext-user-999", "status": "SUCCEEDED",
                                     "chargedEventCounts": {"apify-default-dataset-item": 50}}})
    return _Resp(200, {"data": {"items": []}})


def test_owner_run_excluded_from_verified_revenue() -> None:
    """owner 本人の run は external_runs=0 (owner除外) になる。"""
    name_to_id = {"japan-camera": "act-cam"}
    prices = {"japan-camera": 0.005}
    with patch("apify_revenue_settle_tracker.urllib.request.urlopen", side_effect=_mock_urlopen):
        actual = ast.fetch_actual_revenue("tok", OWNER, name_to_id, prices, 30)
    # owner run は除外される → external_runs=1 (ext-runのみ)
    assert actual["external_runs"] == 1
    # owner run は detail 取得されないため charged_items=50 (ext-runのみ)
    assert actual["charged_items"] == 50
    assert actual["revenue_usd"] == 0.25


def test_external_run_counted_when_not_owner() -> None:
    """owner でない run は external_runs=1・収益として計上される。"""
    # 同じモックで外部runが含まれていることを確認
    name_to_id = {"japan-camera": "act-cam"}
    prices = {"japan-camera": 0.005}
    with patch("apify_revenue_settle_tracker.urllib.request.urlopen", side_effect=_mock_urlopen):
        actual = ast.fetch_actual_revenue("tok", OWNER, name_to_id, prices, 30)
    assert actual["external_runs"] == 1
    assert actual["charged_items"] == 50
    assert actual["revenue_usd"] == 0.25