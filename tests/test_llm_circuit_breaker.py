"""サーキットブレーカー（LLMプロバイダ故障遮断）のテスト — t_96c94435

対象:
- kensho/core/circuit_breaker.py（遮断器本体・閾値のconfig化）
- kensho/scraping/simple_rt_classifier.py の `_call_api_with_fallback` への配線
  （連続失敗で遮断 → 遮断中の同一プロバイダ再試行は0件 → 即フォールバック →
    クールダウン後は半開プローブ1回で backoff 再試行）

禁止領域（モデル名・プロバイダ優先順）が変更されていないことも固定する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.core.circuit_breaker import (  # noqa: E402
    BreakerConfig,
    CircuitBreaker,
    get_breaker,
    load_breaker_config,
    reset_all,
    snapshots,
)
from kensho.scraping import simple_rt_classifier as src  # noqa: E402


class _Clock:
    """テスト用の注入時計（time.monotonic の代替）。"""

    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class _FakeResp:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self._payload


def _decision_response(ids: list[str], decision: str = "OK") -> _FakeResp:
    content = json.dumps([{"id": i, "decision": decision, "reason": "r"} for i in ids], ensure_ascii=False)
    return _FakeResp({"choices": [{"message": {"content": content}}]})


def _ids_from_payload(kwargs: dict[str, Any]) -> list[str]:
    batch = json.loads(kwargs["json"]["messages"][1]["content"])
    return [str(b["id"]) for b in batch]


def _patch_providers(monkeypatch: Any, calls: dict[str, int], *, bai_ok: bool, or_ok: bool) -> None:
    """httpx.post を段（一次=bai / 再試行=bai_retry）別に差し替え、呼び出し回数を calls に数える。

    2026-09-29〜 両段とも B.AI（同一URL）なので、段の区別は Authorization のキーで行う。
    """

    def fake_post(url: str, **kwargs: Any) -> _FakeResp:
        auth = str((kwargs.get("headers") or {}).get("Authorization", ""))
        if "sk-or-test" in auth:  # 再試行段
            calls["bai_retry"] += 1
            if not or_ok:
                raise RuntimeError("B.AI再試行段が枯渇")
            return _decision_response(_ids_from_payload(kwargs))
        calls["bai"] += 1
        if not bai_ok:
            raise RuntimeError("bai全死（残高0）")
        return _decision_response(_ids_from_payload(kwargs))

    monkeypatch.setattr(src.httpx, "post", fake_post)
    monkeypatch.setattr(src, "_load_api_key", lambda *a, **k: "sk-bai-test")
    monkeypatch.setattr(src, "_load_or_key", lambda *a, **k: "sk-or-test")
    monkeypatch.setattr(src.time, "sleep", lambda *_a, **_k: None)  # バッチ間sleepを無効化


def _pairs(n: int) -> list[tuple[str, str]]:
    return [(f"t{i}", f"懸賞本文{i}") for i in range(n)]


# ════════════════════════════════════════════
# 閾値の config 化
# ════════════════════════════════════════════


class TestBreakerConfig:
    def test_defaults(self) -> None:
        cfg = BreakerConfig()
        assert cfg.failure_threshold == 3  # 成功指標: 連続失敗3回で遮断
        assert cfg.cooldown_seconds == 300.0
        assert cfg.backoff_multiplier == 2.0
        assert cfg.max_cooldown_seconds == 3600.0

    def test_from_mapping_overrides(self) -> None:
        cfg = BreakerConfig.from_mapping({
            "failure_threshold": 5,
            "cooldown_seconds": 10,
            "backoff_multiplier": 3.0,
            "max_cooldown_seconds": 60,
        })
        assert (cfg.failure_threshold, cfg.cooldown_seconds, cfg.backoff_multiplier, cfg.max_cooldown_seconds) == (
            5,
            10.0,
            3.0,
            60.0,
        )

    def test_from_mapping_invalid_values_fall_back(self) -> None:
        """不正値・None は既定値へ（遮断設定の誤記で収集が止まらないように）。"""
        cfg = BreakerConfig.from_mapping({"failure_threshold": "abc", "cooldown_seconds": None})
        assert cfg.failure_threshold == 3
        assert cfg.cooldown_seconds == 300.0
        # 0以下/1未満はクランプ（閾値0＝常時遮断やbackoff縮小を防ぐ）
        clamped = BreakerConfig.from_mapping({"failure_threshold": 0, "backoff_multiplier": 0.5})
        assert clamped.failure_threshold == 1
        assert clamped.backoff_multiplier == 1.0

    def test_from_mapping_none_is_default(self) -> None:
        assert BreakerConfig.from_mapping(None) == BreakerConfig()

    def test_load_from_yaml_and_env(self, monkeypatch: Any, tmp_path: Path) -> None:
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "collection:\n  llm_breaker:\n    failure_threshold: 4\n    cooldown_seconds: 45\n",
            encoding="utf-8",
        )
        loaded = load_breaker_config(cfg_file)
        assert (loaded.failure_threshold, loaded.cooldown_seconds) == (4, 45.0)
        # env で動的上書き（コード変更なしに閾値を調整できる）
        monkeypatch.setenv("KENSHO_LLM_BREAKER_THRESHOLD", "9")
        assert load_breaker_config(cfg_file).failure_threshold == 9

    def test_load_missing_file_uses_defaults(self, tmp_path: Path) -> None:
        assert load_breaker_config(tmp_path / "no_such_config.yaml") == BreakerConfig()


# ════════════════════════════════════════════
# 遮断器本体
# ════════════════════════════════════════════


class TestCircuitBreakerCore:
    def test_starts_closed(self) -> None:
        b = CircuitBreaker("p", clock=_Clock())
        assert b.state == "closed"
        assert b.allow() is True

    def test_opens_after_three_consecutive_failures(self) -> None:
        """成功指標: 連続失敗3回検知後に遮断（allow=False）。"""
        clock = _Clock()
        b = CircuitBreaker("p", BreakerConfig(failure_threshold=3, cooldown_seconds=300), clock)
        for _ in range(2):
            assert b.allow() is True
            b.record_failure()
        assert b.state == "closed" and b.consecutive_failures == 2
        assert b.allow() is True
        b.record_failure()  # 3回目
        assert b.state == "open"
        assert b.allow() is False  # 遮断
        assert b.blocked_count == 1

    def test_success_resets_consecutive_counter(self) -> None:
        clock = _Clock()
        b = CircuitBreaker("p", BreakerConfig(failure_threshold=3), clock)
        b.record_failure()
        b.record_failure()
        b.record_success()
        assert b.state == "closed" and b.consecutive_failures == 0
        b.record_failure()
        assert b.state == "closed"  # 連続でないので遮断しない

    def test_five_consecutive_failures_block_then_backoff_retry(self) -> None:
        """タスク検証コマンド: 連続失敗5回 → 遮断(再試行拒否) → backoff 再試行。

        5回の失敗試行のうち、遮断された後（4回目・5回目）は allow()=False となり
        プロバイダを叩かない。クールダウン経過後は半開プローブ1回だけ通し、
        失敗ならクールダウンが backoff 倍（300→600）に延長、成功で閉じる。
        """
        clock = _Clock()
        b = CircuitBreaker(
            "p",
            BreakerConfig(failure_threshold=3, cooldown_seconds=300, backoff_multiplier=2.0, max_cooldown_seconds=3600),
            clock,
        )
        attempted = 0
        blocked = 0
        for _ in range(5):
            if b.allow():
                attempted += 1
                b.record_failure()
            else:
                blocked += 1
        assert attempted == 3  # 遮断後は冷たい再試行をしない
        assert blocked == 2
        assert b.state == "open"
        assert b.cooldown_remaining() == 300.0

        # クールダウン未経過の間は依然として遮断（再試行0件）
        assert b.allow() is False
        assert b.blocked_count == 3

        # backoff 再試行: クールダウン経過 → 半開プローブ1回のみ許可
        clock.advance(300)
        assert b.allow() is True
        assert b.state == "half_open"
        assert b.allow() is False  # 多重プローブ禁止
        b.record_failure()
        assert b.state == "open"
        assert b.cooldown_seconds == 600.0  # 2倍に延長

        # さらに待てば再びプローブ可能 → 成功で closed に復帰
        clock.advance(600)
        assert b.allow() is True
        b.record_success()
        assert b.state == "closed"
        assert b.consecutive_failures == 0
        assert b.cooldown_seconds == 300.0  # 基本クールダウンへ戻る

    def test_cooldown_capped_by_max(self) -> None:
        clock = _Clock()
        b = CircuitBreaker(
            "p",
            BreakerConfig(failure_threshold=1, cooldown_seconds=100, backoff_multiplier=10.0, max_cooldown_seconds=250),
            clock,
        )
        b.record_failure()
        assert b.cooldown_seconds == 100.0
        for _ in range(3):
            clock.advance(b.cooldown_seconds)
            assert b.allow() is True
            b.record_failure()
        assert b.cooldown_seconds == 250.0  # 上限で頭打ち

    def test_snapshot_is_read_only_observability(self) -> None:
        clock = _Clock()
        b = CircuitBreaker("bai", BreakerConfig(failure_threshold=1), clock)
        b.record_failure()
        snap = b.snapshot()
        assert snap["name"] == "bai"
        assert snap["state"] == "open"
        assert snap["blocked_count"] == 0
        assert snap["total_failures"] == 1

    def test_registry_shares_state_per_provider(self) -> None:
        cfg = BreakerConfig(failure_threshold=1)
        b1 = get_breaker("bai", cfg)
        b1.record_failure()
        b2 = get_breaker("bai", cfg)
        assert b2 is b1 and b2.state == "open"
        # 別段も独立（bai が死んでも再試行段は影響を受けない）
        assert get_breaker("bai_retry", cfg).state == "closed"
        assert set(snapshots()) == {"bai", "bai_retry"}  # 直接生成した任意名（実配線名は src.BREAKER_* を参照）


# ════════════════════════════════════════════
# 呼び出しラッパーへの配線（遮断中の再試行0件）
# ════════════════════════════════════════════


class TestClassifierBreakerWiring:
    def test_open_breaker_makes_zero_cold_calls_and_falls_back(self, monkeypatch: Any, tmp_path: Path) -> None:
        """bai全死（残高0）: 3バッチ目で遮断 → 以降baiは0回、OpenRouterへ即フォールバック。"""
        calls = {"bai": 0, "bai_retry": 0}
        _patch_providers(monkeypatch, calls, bai_ok=False, or_ok=True)
        res = src.classify_texts(
            _pairs(5),
            api_key="sk-bai-test",
            batch_size=1,
            project_root=tmp_path,
            breaker_config={"failure_threshold": 3, "cooldown_seconds": 300},
        )
        assert res == {f"t{i}": "OK" for i in range(5)}  # フォールバックで収集は継続（fail-openではない）
        assert calls["bai"] == 3  # 遮断中(batch4,5)の同一プロバイダ再試行は0件
        assert calls["bai_retry"] == 5
        bai = snapshots()["freellmapi"]
        assert bai["state"] == "open"
        assert bai["blocked_count"] == 2  # 防いだ冷たい再試行=2件
        assert bai["consecutive_failures"] >= 3

    def test_fail_open_when_all_providers_blocked(self, monkeypatch: Any, tmp_path: Path) -> None:
        """全プロバイダ死 → 遮断後は冷たい呼び出し0件で UNKNOWN（fail-open維持）。"""
        calls = {"bai": 0, "bai_retry": 0}
        _patch_providers(monkeypatch, calls, bai_ok=False, or_ok=False)
        res = src.classify_texts(
            _pairs(5),
            api_key="sk-bai-test",
            batch_size=1,
            project_root=tmp_path,
            breaker_config={"failure_threshold": 3, "cooldown_seconds": 300},
        )
        assert res == {f"t{i}": "UNKNOWN" for i in range(5)}
        assert calls["bai"] == 3  # 遮断後は叩かない
        assert calls["bai_retry"] == 3  # バッチ1-3で(主/副)フォールバックモデルが失敗 → 遮断
        assert snapshots()["freellmapi_retry"]["state"] == "open"

    def test_threshold_from_config_dict_is_honored(self, monkeypatch: Any, tmp_path: Path) -> None:
        """閾値をconfig化（ここでは1）→ 1回の失敗で即遮断し、2バッチ目はbai0回。"""
        calls = {"bai": 0, "bai_retry": 0}
        _patch_providers(monkeypatch, calls, bai_ok=False, or_ok=True)
        res = src.classify_texts(
            _pairs(3),
            api_key="sk-bai-test",
            batch_size=1,
            project_root=tmp_path,
            breaker_config={"failure_threshold": 1, "cooldown_seconds": 60},
        )
        assert res == {f"t{i}": "OK" for i in range(3)}
        assert calls["bai"] == 1
        assert snapshots()["freellmapi"]["blocked_count"] == 2

    def test_classify_collected_items_passes_breaker_config(self, monkeypatch: Any, tmp_path: Path) -> None:
        calls = {"bai": 0, "bai_retry": 0}
        _patch_providers(monkeypatch, calls, bai_ok=False, or_ok=True)
        items: list[dict[str, Any]] = [
            {"tweet_id": "t0", "tweet_text": "本文", "keyword_flag": False},
            {"tweet_id": "t1", "tweet_text": "本文", "keyword_flag": False},
        ]
        classified, flag_n, unknown_n = src.classify_collected_items(
            items, api_key="sk-bai-test", batch_size=1, breaker_config={"failure_threshold": 1}
        )
        assert (classified, flag_n, unknown_n) == (2, 0, 0)
        assert items[0]["simple_rt_ok"] == "OK"
        assert calls["bai"] == 1  # 2件目は遮断により叩かない

    def test_success_keeps_breaker_closed(self, monkeypatch: Any, tmp_path: Path) -> None:
        """bai健全時は遮断されず、baiだけが使われる（従来挙動の維持）。"""
        calls = {"bai": 0, "bai_retry": 0}
        _patch_providers(monkeypatch, calls, bai_ok=True, or_ok=True)
        res = src.classify_texts(_pairs(3), api_key="sk-bai-test", batch_size=1, project_root=tmp_path)
        assert res == {f"t{i}": "OK" for i in range(3)}
        assert calls == {"bai": 3, "bai_retry": 0}
        assert snapshots()["freellmapi"]["state"] == "closed"

    def test_zero_cold_calls_while_breaker_open(self, monkeypatch: Any, tmp_path: Path) -> None:
        """成功指標: 遮断中の同一プロバイダ再試行を0件に。

        事前に3連続失敗で遮断状態を作ってから5バッチ走らせ、bai呼び出し=0件を実測する
        （クールダウン中のためプローブも発生しない）。
        """
        calls = {"bai": 0, "bai_retry": 0}
        _patch_providers(monkeypatch, calls, bai_ok=False, or_ok=True)
        bai = get_breaker(src.BREAKER_BAI, BreakerConfig(failure_threshold=3, cooldown_seconds=300))
        for _ in range(3):
            bai.record_failure()
        assert bai.state == "open"

        res = src.classify_texts(_pairs(5), api_key="sk-bai-test", batch_size=1, project_root=tmp_path)
        assert res == {f"t{i}": "OK" for i in range(5)}  # 即フォールバックで収集は継続
        assert calls["bai"] == 0  # 遮断中の同一プロバイダ再試行は0件
        assert calls["bai_retry"] == 5
        assert snapshots()["freellmapi"]["blocked_count"] == 5

    def test_before_after_cold_call_reduction(self, monkeypatch: Any, tmp_path: Path) -> None:
        """Outcome Review 用の before/after 実測（同一シナリオ・遮断なし vs 遮断あり）。

        5バッチ・bai全死シナリオで、
          (a) bai呼び出し総数
          (b) 連続失敗3回＝遮断条件成立後に発生した冷たい呼び出し数（＝遮断が防ぐべき件数）
        を実測する。閾値を無限大にした run は「遮断機構なし＝実装前挙動」の再現。
        """

        def run(threshold: int) -> dict[str, int]:
            reset_all()
            calls = {"bai": 0, "bai_retry": 0, "bai_after_threshold": 0}

            def fake_post(url: str, **kwargs: Any) -> _FakeResp:
                auth = str((kwargs.get("headers") or {}).get("Authorization", ""))
                if "sk-or-test" in auth:  # 再試行段（B.AI）は成功
                    calls["bai_retry"] += 1
                    return _decision_response(_ids_from_payload(kwargs))
                calls["bai"] += 1
                if calls["bai"] > 3:  # 3連続失敗＝遮断条件成立後の呼び出し
                    calls["bai_after_threshold"] += 1
                raise RuntimeError("bai全死（残高0）")

            monkeypatch.setattr(src.httpx, "post", fake_post)
            monkeypatch.setattr(src, "_load_api_key", lambda *a, **k: "sk-bai-test")
            monkeypatch.setattr(src, "_load_or_key", lambda *a, **k: "sk-or-test")
            monkeypatch.setattr(src.time, "sleep", lambda *_a, **_k: None)
            src.classify_texts(
                _pairs(5),
                api_key="sk-bai-test",
                batch_size=1,
                project_root=tmp_path,
                breaker_config={"failure_threshold": threshold, "cooldown_seconds": 300},
            )
            return calls

        before = run(10**9)  # 遮断なし＝実装前挙動
        after = run(3)  # 本実装（閾値3）
        assert before["bai"] == 5 and before["bai_after_threshold"] == 2
        assert after["bai"] == 3 and after["bai_after_threshold"] == 0


class TestForbiddenAreasUnchanged:
    """禁止領域（モデル切替・優先順）に触れていないことを固定する。"""

    def test_model_constants_unchanged(self) -> None:
        """2026-10-01 ユーザー指示で freellmapi/auto に統一 — 以後の逸脱を固定する。"""
        assert src.DEFAULT_MODEL == "auto"
        assert src.FALLBACK_MODEL == "auto"
        assert src.SECOND_FALLBACK_MODEL == "auto"
        assert src.API_URL == "http://127.0.0.1:3002/v1/chat/completions"
        assert src.FALLBACK_API_URL == "http://127.0.0.1:3002/v1/chat/completions"

    def test_priority_order_unchanged(self, monkeypatch: Any, tmp_path: Path) -> None:
        """一次段(freellmapi)優先 → 失敗時のみ再試行段(freellmapi) の順序が保たれている。

        2026-10-01〜 両段とも freellmapi の auto（ローカルvLLM/外部直叩きは廃止）。
        """
        urls: list[str] = []

        def fake_post(url: str, **kwargs: Any) -> _FakeResp:
            urls.append(url)
            auth = str((kwargs.get("headers") or {}).get("Authorization", ""))
            if "sk-or-test" in auth:  # 再試行段は成功
                return _decision_response(_ids_from_payload(kwargs))
            raise RuntimeError("freellmapi down")

        monkeypatch.setattr(src.httpx, "post", fake_post)
        monkeypatch.setattr(src, "_load_api_key", lambda *a, **k: "sk-bai-test")
        monkeypatch.setattr(src, "_load_or_key", lambda *a, **k: "sk-or-test")
        res = src.classify_texts(_pairs(1), api_key="sk-bai-test", project_root=tmp_path)
        assert res == {"t0": "OK"}
        assert "127.0.0.1:3002" in urls[0]
        assert "127.0.0.1:3002" in urls[1]
        assert all("openrouter" not in u for u in urls)  # 外部APIは一切呼ばない
        assert all("127.0.0.1:3002" in u for u in urls)  # freellmapi のみ
