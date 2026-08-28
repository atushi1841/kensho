"""Tests for kensho/scraping/simple_rt_classifier.py — LLMによるフォロー+RT判定"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.simple_rt_classifier import (  # noqa: E402
    _extract_json,
    _load_api_key,
    classify_collected_items,
    classify_texts,
)


class _FakeResp:
    def __init__(self, json_data: dict[str, Any]) -> None:
        self._json = json_data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self._json


def _ok_response(decisions: list[tuple[str, str]]) -> _FakeResp:
    items = [{"id": i, "decision": d, "reason": "r"} for i, d in decisions]
    import json as _json

    return _FakeResp({"choices": [{"message": {"content": _json.dumps(items, ensure_ascii=False)}}]})


class TestExtractJson:
    def test_plain_array(self) -> None:
        assert _extract_json('[{"id": "a", "decision": "OK"}]') == [{"id": "a", "decision": "OK"}]

    def test_code_fence(self) -> None:
        c = '```json\n[{"id": "a", "decision": "FLAG"}]\n```'
        assert _extract_json(c) == [{"id": "a", "decision": "FLAG"}]

    def test_surrounding_text(self) -> None:
        c = '結果です。\n[{"id": "a", "decision": "OK"}]\n以上'
        assert _extract_json(c) == [{"id": "a", "decision": "OK"}]

    def test_garbage(self) -> None:
        assert _extract_json("not json") is None
        assert _extract_json("") is None


class TestLoadApiKey:
    def test_bom_env_file(self, tmp_path: Path) -> None:
        p = tmp_path / ".env"
        p.write_bytes(b"\xef\xbb\xbfDEEPSEEK_API_KEY=sk-test123\n")
        assert _load_api_key(tmp_path) == "sk-test123"

    def test_missing_key(self, tmp_path: Path) -> None:
        assert _load_api_key(tmp_path) == ""


class TestClassifyTexts:
    def test_normal(self, monkeypatch: Any) -> None:
        called: list[dict[str, Any]] = []

        def fake_post(url: str, **kwargs: Any) -> _FakeResp:
            called.append(kwargs["json"])
            return _ok_response([("t1", "FLAG"), ("t2", "OK")])

        monkeypatch.setattr("kensho.scraping.simple_rt_classifier.httpx.post", fake_post)
        res = classify_texts(
            [("t1", "フォロー＆リポストキャンペーン"), ("t2", "①フォロー ②リポストで完了")],
            api_key="sk-test",
        )
        assert res == {"t1": "FLAG", "t2": "OK"}
        assert called and called[0]["model"] == "deepseek-v4-flash"
        assert called[0]["messages"][0]["role"] == "system"

    def test_fail_open_on_error(self, monkeypatch: Any) -> None:
        def fake_post(url: str, **kwargs: Any) -> _FakeResp:
            raise RuntimeError("network down")

        monkeypatch.setattr("kensho.scraping.simple_rt_classifier.httpx.post", fake_post)
        res = classify_texts([("t1", "text")], api_key="sk-test")
        assert res == {"t1": "UNKNOWN"}

    def test_empty_content_retry(self, monkeypatch: Any) -> None:
        """推論トークン枯渇で本文空 → max_tokens を上げて再試行"""
        calls: list[int] = []

        def fake_post(url: str, **kwargs: Any) -> _FakeResp:
            max_tokens: int = kwargs["json"]["max_tokens"]
            calls.append(max_tokens)
            if max_tokens == 2000:
                # 本文空（reasoningのみ）
                return _FakeResp({"choices": [{"message": {"content": ""}}]})
            return _ok_response([("t1", "FLAG")])

        monkeypatch.setattr("kensho.scraping.simple_rt_classifier.httpx.post", fake_post)
        res = classify_texts([("t1", "text")], api_key="sk-test")
        assert res == {"t1": "FLAG"}
        assert calls == [2000, 4000]

    def test_no_api_key_fail_open(self, monkeypatch: Any) -> None:
        res = classify_texts([("t1", "text")], api_key="")
        assert res == {"t1": "UNKNOWN"}


class TestClassifyCollectedItems:
    def test_sets_flags_and_skips_non_targets(self, monkeypatch: Any) -> None:
        def fake_post(url: str, **kwargs: Any) -> _FakeResp:
            batch = kwargs["json"]["messages"][1]["content"]
            ids = [b["id"] for b in __import__("json").loads(batch)]
            return _ok_response([(i, "FLAG") for i in ids])

        monkeypatch.setattr("kensho.scraping.simple_rt_classifier.httpx.post", fake_post)
        items = [
            {"tweet_id": "1", "tweet_text": "追加操作が必要", "keyword_flag": False},  # → FLAG
            {"tweet_id": "2", "tweet_text": "フォロー＆リポストで完了", "keyword_flag": False},  # → FLAG(モック)
            {"tweet_id": "3", "tweet_text": "引用RT", "keyword_flag": True},  # 対象外
            {"tweet_id": "4", "tweet_text": "", "keyword_flag": False},  # 対象外（本文なし）
            {"tweet_id": "5", "tweet_text": "x", "keyword_flag": False, "simple_rt_ok": "OK"},  # 対象外（済）
            {"tweet_id": "6", "tweet_text": "y", "keyword_flag": False},  # tweet_id無し → 対象外
        ]
        for it in items:
            if it["tweet_id"] == "6":
                del it["tweet_id"]
        classified, flag_n, unknown_n = classify_collected_items(items, api_key="sk-test")
        assert classified == 2
        assert flag_n == 2
        assert unknown_n == 0
        assert items[0]["simple_rt_ok"] == "FLAG"
        assert items[1]["simple_rt_ok"] == "FLAG"
        assert "simple_rt_ok" not in items[2]
        assert "simple_rt_ok" not in items[3]
        assert items[4]["simple_rt_ok"] == "OK"  # 既存値は変更しない

    def test_no_targets(self) -> None:
        items = [{"tweet_id": "1", "keyword_flag": True, "tweet_text": "x"}]
        assert classify_collected_items(items, api_key="sk-test") == (0, 0, 0)
