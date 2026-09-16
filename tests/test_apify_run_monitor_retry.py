"""apify_run_monitor.py 再実行統一 + MCP常駐除外 + retry budget テスト (t_cdcfc7aa).

背景（run54先行調査のギャップ）:
- needs_retry は最新 **runs** で失敗を判定するのに、queue_run は timeout 未指定時
  /acts/{id}/builds しか叩かず run が再生成されなかった（実効ゼロ）。→ /runs へ統一。
- MCP常駐actor（japan-market-mcp等）は通常runだと必ずTIMED-OUT→Apifyエラーメール再発源。
  自動再試行対象外にする。
- RETRY_LIMIT=3 が「取得run数」にしか使われておらず、失敗継続actorを毎回再試行していた。
  stateファイルで24h窓の実试行上限を強制する。
"""

from __future__ import annotations

import importlib.util
import json
import urllib.error
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("apify_run_monitor", REPO / "scripts" / "apify_run_monitor.py")
mod = importlib.util.module_from_spec(_SPEC)  # type: ignore[arg-type]
_SPEC.loader.exec_module(mod)  # type: ignore[union-attr]


class _Resp:
    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_queue_run_uses_runs_endpoint_without_timeout(monkeypatch) -> None:
    """timeout未指定でも /acts/{id}/runs をPOSTすること（builds戻し禁止・run再生成の実効性）."""
    captured: dict = {}

    def fake_urlopen(req, timeout=None):  # noqa: ANN001, ANN201
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data.decode())
        return _Resp({"data": {"id": "runXYZ123456", "status": "READY"}})

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    out = mod.queue_run("actTEST", timeout_secs=None)
    assert "/acts/actTEST/runs" in captured["url"]
    assert "/builds" not in captured["url"]
    assert captured["method"] == "POST"
    assert captured["body"] == {"waitForFinish": 0}
    assert out["data"]["id"] == "runXYZ123456"


def test_queue_run_passes_timeout_override(monkeypatch) -> None:
    captured: dict = {}

    def fake_urlopen(req, timeout=None):  # noqa: ANN001, ANN201
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _Resp({"data": {"id": "runT1"}})

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    mod.queue_run("57SNehd4cHNFyUCj3", timeout_secs=7200)
    assert "/runs" in captured["url"]
    assert captured["body"]["timeoutSecs"] == 7200


def test_resident_mcp_detection() -> None:
    # 名前末尾 -mcp（サーバー型）は自動再試行対象外
    assert mod.is_resident_mcp("japan-market-mcp") is True
    assert mod.is_resident_mcp("japan-fuel-price-mcp") is True
    # IDOverrideリストも対象外にフォールバック
    assert mod.is_resident_mcp("renamed-unknown", "57SNehd4cHNFyUCj3") is True
    # 通常スクレイパーactorは従来どおり再試行対象
    assert mod.is_resident_mcp("amazon-paapi-jp-actor") is False


def test_retry_budget_window_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APIFY_MONITOR_STATE", str(tmp_path / "state.json"))
    state = mod.load_state()
    assert mod.retry_allowed(state, "actA") is True
    now = datetime.now(UTC)
    state["actA"] = [(now - timedelta(hours=i)).isoformat() for i in range(mod.RETRY_LIMIT)]
    assert mod.retry_allowed(state, "actA") is False, "24h窓内でRETRY_LIMIT回再試行済みなら打ち切り"
    # 窓外（古い試行）はプリーンされて復活する
    old = [(now - timedelta(hours=25)).isoformat() for _ in range(mod.RETRY_LIMIT)]
    assert mod.prune_attempts(old) == []
    state["actB"] = old + [now.isoformat()]
    assert mod.retry_allowed(state, "actB") is True
    # record_retry + save/load往復（old 3件は窓外pruneされ、now 1件+新規1件=2件が正しい挙動）
    mod.record_retry(state, "actB")
    mod.save_state(state)
    reloaded = mod.load_state()
    assert len(reloaded["actB"]) == 2
    assert reloaded["actB"] == mod.prune_attempts(reloaded["actB"])


def test_prune_attempts_drops_invalid() -> None:
    ok = datetime.now(UTC).isoformat()
    assert mod.prune_attempts(["not-a-date", ok, ""]) == [ok]


def test_http_error_types_importable() -> None:
    # 402ガードが参照する例外型が正しく解決できること（urllib.error.HTTPError）
    from email.message import Message

    err = urllib.error.HTTPError("https://api.apify.com", 402, "payment required", Message(), BytesIO(b"{}"))
    assert err.code == 402
