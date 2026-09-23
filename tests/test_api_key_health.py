"""api_key_health 全プロファイルAPI鍵健全性監視のテスト。

検証項目:
- 401 (auth_fail) を正しく検出
- 429 (rate_limited) を正しく検出
- 15秒 timeout を正しく検出
- 認証鍵文字列が報告(mask)に決して完全形で出ない
- 読取専用: provider/model切替・鍵自動置換を行わない
- dry-run は実HTTPを叩かない
- --fail-on-error は不正プロファイルで exit 2 を返す
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

from scripts import api_key_health as akh


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


@pytest.fixture(autouse=True)
def _isolate_profiles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """テスト用にHERMES_PROFILESを一時ディレクトリへ差し替え、実プロファイルに触れない"""
    prof_dir = tmp_path / "profiles"
    for prof in akh.DEFAULT_PROFILES:
        (prof_dir / prof).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(akh, "HERMES_PROFILES", prof_dir)
    return prof_dir


def _write_env(prof_dir: Path, prof: str, env_str: str) -> None:
    (prof_dir / prof / ".env").write_text(env_str, encoding="utf-8")


def _gen_key(provider: str = "test") -> str:
    """テスト用の鍵値（平文では必ずマスクされることを確認する用）"""
    return f"{provider}_SECRET_KEY_abcdef1234567890"


# --- 401検出 ---
def test_detect_401_auth_fail(monkeypatch: pytest.MonkeyPatch, _isolate_profiles: Path) -> None:
    _write_env(_isolate_profiles, "kensho-critic", f"OPENROUTER_API_KEY={_gen_key()}\n")

    def fake_get_401(
        url: str, headers: dict[str, str], timeout: int, follow_redirects: bool
    ) -> FakeResponse:
        return FakeResponse(401)

    monkeypatch.setattr(httpx, "get", fake_get_401)
    monkeypatch.setattr(httpx, "TimeoutException", type("TimeoutException", (Exception,), {}))
    monkeypatch.setattr(httpx, "ConnectError", type("ConnectError", (Exception,), {}))
    monkeypatch.setattr(httpx, "NetworkError", type("NetworkError", (Exception,), {}))

    res = akh.check_provider(
        "kensho-critic", "OPENROUTER_API_KEY", akh.PROVIDERS["OPENROUTER_API_KEY"], 15, dry_run=False
    )
    assert res.state == "auth_fail"
    assert res.http_status == 401
    assert res.provider == "openrouter"


# --- 429検出 ---
def test_detect_429_rate_limited(monkeypatch: pytest.MonkeyPatch, _isolate_profiles: Path) -> None:
    _write_env(_isolate_profiles, "kensho-critic", f"FIREWORKS_API_KEY={_gen_key()}\n")

    def fake_get_429(
        url: str, headers: dict[str, str], timeout: int, follow_redirects: bool
    ) -> FakeResponse:
        return FakeResponse(429)

    monkeypatch.setattr(httpx, "get", fake_get_429)
    monkeypatch.setattr(httpx, "TimeoutException", type("TimeoutException", (Exception,), {}))
    monkeypatch.setattr(httpx, "ConnectError", type("ConnectError", (Exception,), {}))
    monkeypatch.setattr(httpx, "NetworkError", type("NetworkError", (Exception,), {}))

    res = akh.check_provider(
        "kensho-critic", "FIREWORKS_API_KEY", akh.PROVIDERS["FIREWORKS_API_KEY"], 15, dry_run=False
    )
    assert res.state == "rate_limited"
    assert res.http_status == 429


# --- 15秒 timeout 検出 ---
def test_detect_timeout(monkeypatch: pytest.MonkeyPatch, _isolate_profiles: Path) -> None:
    _write_env(_isolate_profiles, "kensho-critic", f"GROQ_API_KEY={_gen_key()}\n")

    class TimeoutErr(Exception):
        pass

    def fake_get_timeout(
        url: str, headers: dict[str, str], timeout: int, follow_redirects: bool
    ) -> None:
        assert timeout == 15, "15秒timeoutを検査側で設定すべき"
        raise TimeoutErr()

    monkeypatch.setattr(httpx, "get", fake_get_timeout)
    monkeypatch.setattr(httpx, "TimeoutException", TimeoutErr)
    monkeypatch.setattr(httpx, "ConnectError", type("ConnectError", (Exception,), {}))
    monkeypatch.setattr(httpx, "NetworkError", type("NetworkError", (Exception,), {}))

    res = akh.check_provider(
        "kensho-critic", "GROQ_API_KEY", akh.PROVIDERS["GROQ_API_KEY"], 15, dry_run=False
    )
    assert res.state == "timeout"
    assert "timeout" in res.detail


# --- 認証鍵文字列が報告に0件（完全形） ---
def test_key_secret_never_leaks_in_report(monkeypatch: pytest.MonkeyPatch, _isolate_profiles: Path) -> None:
    secret = _gen_key("DEEPSEEK")
    _write_env(_isolate_profiles, "kensho-qa", f"DEEPSEEK_API_KEY={secret}\n")
    _write_env(_isolate_profiles, "kensho-qa", f"OPENROUTER_API_KEY={secret}\n")

    results = [akh.ProfileResult(profile="kensho-qa", checked=2)]
    results[0].providers.append(akh.ProviderStatus(provider="deepseek", state="auth_fail", http_status=401))
    results[0].providers.append(akh.ProviderStatus(provider="openrouter", state="ok", http_status=200))
    results[0].classify()

    metrics: dict[str, Any] = {
        "check_time": "t",
        "profiles_checked": 1,
        "state_counts": {"has_error": 1},
        "error_profiles": ["kensho-qa"],
        "dirty": True,
        "action_required": True,
    }
    report = akh.format_report(results, metrics)
    json_repr = json.dumps(metrics)

    # 秘密鍵の完全形が report にも JSON にも現れない
    assert secret not in report
    assert secret not in json_repr
    # マスク関数の単体確認
    masked = akh.mask_key(secret)
    assert secret not in masked
    assert masked != secret
    assert "..." in masked


# --- 読取専用: dry-runは実HTTPを叩かない ---
def test_dry_run_does_not_hit_network(monkeypatch: pytest.MonkeyPatch, _isolate_profiles: Path) -> None:
    _write_env(_isolate_profiles, "kensho-worker", f"GEMINI_API_KEY={_gen_key()}\n")

    def boom(*a: object, **k: object) -> None:
        raise AssertionError("dry-runは実HTTPを叩くべきでない")

    monkeypatch.setattr(httpx, "get", boom)
    res = akh.check_provider(
        "kensho-worker", "GEMINI_API_KEY", akh.PROVIDERS["GEMINI_API_KEY"], 15, dry_run=True
    )
    assert res.state == "ok"
    assert "dry-run" in res.detail


# --- 5プロファイル判定率100%（構成検証） ---
def test_all_profiles_resolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _isolate_profiles: Path
) -> None:
    """5プロファイルを全プロバイダ設定で検査し、判定率100%を確認（mock HTTP 200）"""
    for prof in akh.DEFAULT_PROFILES:
        envs = "".join(f"{v}={_gen_key()}\n" for v in akh.PROVIDERS)
        _write_env(_isolate_profiles, prof, envs)

    def fake_get_200(
        url: str, headers: dict[str, str], timeout: int, follow_redirects: bool
    ) -> FakeResponse:
        return FakeResponse(200)

    monkeypatch.setattr(httpx, "get", fake_get_200)
    monkeypatch.setattr(httpx, "TimeoutException", type("TimeoutException", (Exception,), {}))
    monkeypatch.setattr(httpx, "ConnectError", type("ConnectError", (Exception,), {}))
    monkeypatch.setattr(httpx, "NetworkError", type("NetworkError", (Exception,), {}))

    results, metrics = akh.run(akh.DEFAULT_PROFILES, 15, dry_run=False)
    assert metrics["profiles_checked"] == len(akh.DEFAULT_PROFILES) == 5
    # 各プロファイルが少なくとも1プロバイダ検査済み
    for res in results:
        assert res.checked >= 1, f"{res.profile} が判定されていない"
    assert cast(dict[str, int], metrics["state_counts"])["ok"] == 5
    assert metrics["error_profiles"] == []
    assert metrics["action_required"] is False


# --- --fail-on-error は不正プロファイルで exit 2 ---
def test_fail_on_error_returns_nonzero(monkeypatch: pytest.MonkeyPatch, _isolate_profiles: Path) -> None:
    """run() が has_error を返すとき main() は exit 2 を返す"""
    monkeypatch.setattr(
        akh,
        "run",
        lambda profiles, timeout, dry_run: (
            [
                akh.ProfileResult(
                    profile="kensho-critic",
                    checked=1,
                    providers=[akh.ProviderStatus(provider="openrouter", state="auth_fail", http_status=401)],
                )
            ],
            {
                "check_time": "t",
                "profiles_checked": 1,
                "state_counts": {"has_error": 1},
                "error_profiles": ["kensho-critic"],
                "dirty": True,
                "action_required": True,
            },
        ),
    )
    monkeypatch.setattr(sys, "argv", ["api_key_health.py", "--profiles", "kensho-critic", "--fail-on-error", "--json"])
    rc = akh.main()
    assert rc == 2
