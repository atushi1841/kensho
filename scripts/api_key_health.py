#!/usr/bin/env python3
"""全プロファイルのAPI鍵健全性を応募前に判定する読取専用監視。

2026-09-23: チーム5プロファイルの OpenRouter 鍵401で dispatcher worker
が rc=0 clean exit を繰り返し応募が停止した。これを防ぐため、
応募前に全プロファイルの認証状態を HTTP 状態 (200/401/429/timeout)
で検査する。

本スクリプトは読取専用。鍵の自動置換・provider/model切替・X操作は行わない。
不正プロファイル (401) を検出したら該当バッチスキップのための構造化ログ・
health指標に記録し、通知フラグを立てるのみ。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict, cast
from urllib.parse import quote_plus

import httpx

HERMES_PROFILES = Path(os.environ.get("HERMES_PROFILES", "/home/atushi/.hermes/profiles"))

# 対象プロファイル（チーム5: critic / worker / qa / revenue-worker / revenue-qa）。
# kensho-sweeps は実行側オーケストレータで .env が別構成のため除外（既定はチーム5）。
DEFAULT_PROFILES = [
    "kensho-critic",
    "kensho-worker",
    "kensho-qa",
    "kensho-revenue-worker",
    "kensho-revenue-qa",
]


class ProviderDef(TypedDict):
    name: str
    url: str
    header: Callable[[str], dict[str, str]]


# プロバイダ定義: env変数名 → (認証エンドポイント, ヘッダー生成callable)
# 実測エンドポイント (2026-09-23):
#   OpenRouter  /api/v1/key                       200=valid 401=invalid
#   Fireworks  /inference/v1/models               200=valid 401=invalid
#   DeepSeek   /v1/models                         200=valid 401=invalid (現状全401=死)
#   Groq       /openai/v1/models                  200=valid
#   Gemini     /v1beta/models (x-goog-api-key)   200=valid
# NOUS（nonexistent dedup）は現状エンドポイントが実測不能のため unknown 扱い。
PROVIDERS: dict[str, ProviderDef] = {
    "OPENROUTER_API_KEY": {
        "name": "openrouter",
        "url": "https://openrouter.ai/api/v1/key",
        "header": lambda k: {"Authorization": f"Bearer {k}"},
    },
    "FIREWORKS_API_KEY": {
        "name": "fireworks",
        "url": "https://api.fireworks.ai/inference/v1/models",
        "header": lambda k: {"Authorization": f"Bearer {k}"},
    },
    "DEEPSEEK_API_KEY": {
        "name": "deepseek",
        "url": "https://api.deepseek.com/v1/models",
        "header": lambda k: {"Authorization": f"Bearer {k}"},
    },
    "GROQ_API_KEY": {
        "name": "groq",
        "url": "https://api.groq.com/openai/v1/models",
        "header": lambda k: {"Authorization": f"Bearer {k}"},
    },
    "GEMINI_API_KEY": {
        "name": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models",
        "header": lambda k: {"x-goog-api-key": k},
    },
}

DEFAULT_TIMEOUT = 15  # 秒（タスク仕様: 15秒timeout検出）
OK_STATUS = frozenset({200})


@dataclass
class ProviderStatus:
    provider: str
    http_status: int | None = None
    state: str = "unknown"  # ok / auth_fail(401,403) / rate_limited(429) / timeout / unreachable / missing
    detail: str = ""
    latency_ms: int | None = None


@dataclass
class ProfileResult:
    profile: str
    checked: int = 0
    providers: list[ProviderStatus] = field(default_factory=list)
    state: str = "unknown"  # ok / has_error / unknown / no_key

    def classify(self) -> None:
        # 全プロバイダ ok → profile ok。1つでも auth_fail/rate_limited/timeout → has_error
        # 1つでも検出可だが全部 unknown（エンドポイント不能）→ unknown
        detected = [p for p in self.providers if p.state != "missing"]
        error = [p for p in self.providers if p.state in ("auth_fail", "rate_limited", "timeout", "unreachable")]
        if error:
            self.state = "has_error"
        elif detected and all(p.state == "ok" for p in detected):
            self.state = "ok"
        elif not detected:
            self.state = "no_key"
        else:
            self.state = "unknown"


def load_env_file(profile: str) -> dict[str, str]:
    """.env を読んで key=value dict を返す（鍵値は呼び出し側でログに出さない）"""
    results: dict[str, str] = {}
    envp = HERMES_PROFILES / profile / ".env"
    if not envp.exists():
        return results
    for line in envp.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        results[k.strip()] = v.strip()
    return results


def check_provider(
    prof_name: str, env_var: str, prov: ProviderDef, timeout: int, dry_run: bool
) -> ProviderStatus:
    """1プロバイダの鍵を認証状態で検査する（読取専用）。鍵値は決して返さない/ログしない。"""
    env = load_env_file(prof_name)
    key_value = env.get(env_var)
    if not key_value:
        return ProviderStatus(provider=prov["name"], state="missing", detail="鍵が.envに未設定")

    url = prov["url"]
    header_fn = prov["header"]
    headers = header_fn(key_value)

    start = time.monotonic()
    try:
        if dry_run:
            # dry-runは実HTTPを叩かず「存在キー + 正常時200想定」のスキャン（変更なしの確認用途）
            # 実際の疎通は常時モードで行う。ここではキー存在確認のみ。
            lat = int((time.monotonic() - start) * 1000)
            return ProviderStatus(provider=prov["name"], state="ok", detail="dry-run(キー存在のみ)", latency_ms=lat)
        r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        lat = int((time.monotonic() - start) * 1000)
        if r.status_code in OK_STATUS:
            return ProviderStatus(
                provider=prov["name"], http_status=r.status_code, state="ok",
                detail="認証OK", latency_ms=lat,
            )
        if r.status_code in (401, 403):
            return ProviderStatus(
                provider=prov["name"], http_status=r.status_code, state="auth_fail",
                detail="認証失効・拒否", latency_ms=lat,
            )
        if r.status_code == 429:
            return ProviderStatus(
                provider=prov["name"], http_status=r.status_code, state="rate_limited",
                detail="レート制限", latency_ms=lat,
            )
        if r.status_code >= 500:
            return ProviderStatus(
                provider=prov["name"], http_status=r.status_code, state="unreachable",
                detail=f"サーバーエラー {r.status_code}", latency_ms=lat,
            )
        # その他 (404 など) → エンドポイント不適合として unknown 扱い
        return ProviderStatus(
            provider=prov["name"], http_status=r.status_code, state="unknown",
            detail=f"HTTP {r.status_code}", latency_ms=lat,
        )
    except httpx.TimeoutException:
        lat = int((time.monotonic() - start) * 1000)
        return ProviderStatus(provider=prov["name"], state="timeout", detail=f"timeout {timeout}s", latency_ms=lat)
    except (httpx.ConnectError, httpx.NetworkError):
        lat = int((time.monotonic() - start) * 1000)
        return ProviderStatus(provider=prov["name"], state="unreachable", detail="ネットワーク到達不能", latency_ms=lat)
    except Exception as e:  # pragma: no cover
        lat = int((time.monotonic() - start) * 1000)
        return ProviderStatus(provider=prov["name"], state="unknown", detail=str(e)[:80], latency_ms=lat)


def mask_key(key: str) -> str:
    """認証鍵文字列をログ安全化（先頭4+末尾4のみ）。鍵値の完全形を絶対に返さない。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def _notify_api_key_health(metrics: dict[str, object]) -> None:
    """不正プロファイル検出時に Telegram / stdout で通知する（読取専用・鍵値非表示）。"""
    error_profiles: list[str] = cast(list[str], metrics.get("error_profiles", []))
    if not error_profiles:
        return
    state_counts: dict[str, int] = cast(dict[str, int], metrics.get("state_counts", {}))
    msg = f"⚠️ API鍵健全性: 要対応プロファイル {', '.join(error_profiles)}（状態: {state_counts}）"
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel = os.environ.get("TELEGRAM_HOME_CHANNEL", "")
    if token and channel:
        try:
            url = (
                f"https://api.telegram.org/bot{token}/sendMessage"
                f"?chat_id={channel}&text={quote_plus(msg)}&parse_mode=HTML"
            )
            r = httpx.get(url, timeout=10)
            if r.status_code == 200:
                return
        except Exception:
            pass
    print(f"[通知/api_key_health] {msg}", flush=True)


def run(profiles: list[str], timeout: int, dry_run: bool) -> tuple[list[ProfileResult], dict[str, object]]:
    results: list[ProfileResult] = []
    for prof in profiles:
        env = load_env_file(prof)
        pr = ProfileResult(profile=prof)
        # このプロファイルに設定されているプロバイダのみ検査
        for env_var, prov in PROVIDERS.items():
            if env_var in env:
                pr.checked += 1
                pr.providers.append(check_provider(prof, env_var, prov, timeout, dry_run))
        pr.classify()
        results.append(pr)

    # health指標（集計）
    by_state: dict[str, int] = {}
    error_profiles: list[str] = []
    for res in results:
        by_state[res.state] = by_state.get(res.state, 0) + 1
        if res.state == "has_error":
            error_profiles.append(res.profile)
    state_counts: dict[str, int] = by_state

    metrics: dict[str, object] = {
        "check_time": datetime.now(UTC).isoformat(),
        "profiles_checked": len(results),
        "state_counts": state_counts,
        "error_profiles": error_profiles,
        "dirty": bool(error_profiles),
        "action_required": bool(error_profiles),  # 読取専用: 通知フラグのみ（自動変更はしない）
    }
    return results, metrics


def format_report(results: list[ProfileResult], metrics: dict[str, object]) -> str:
    state_counts: dict[str, int] = cast(dict[str, int], metrics["state_counts"])
    error_profiles: list[str] = cast(list[str], metrics["error_profiles"])
    lines: list[str] = []
    lines.append(f"# API鍵健全性 ({metrics['check_time']})")
    lines.append(f"プロファイル: {metrics['profiles_checked']} 検査 | 状態: {state_counts}")
    if error_profiles:
        lines.append("⚠️ 要対応プロファイル: " + ", ".join(error_profiles))
    else:
        lines.append("✅ 全プロファイル認証OK")
    lines.append("")
    lines.append("| プロファイル | プロバイダ | 状態 | HTTP | 詳細 |")
    lines.append("|---|---|---|---|---|")
    for res in results:
        if not res.providers:
            lines.append(f"| {res.profile} | (鍵設定なし) | {res.state} | - | - |")
        for p in res.providers:
            http = str(p.http_status) if p.http_status is not None else "-"
            lines.append(f"| {res.profile} | {p.provider} | {p.state} | {http} | {p.detail} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="全プロファイルのAPI鍵健全性を応募前に判定（読取専用）")
    ap.add_argument("--profiles", nargs="*", default=DEFAULT_PROFILES, help="検査対象プロファイル名（既定=チーム5）")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTPタイムアウト秒（既定15）")
    ap.add_argument("--dry-run", action="store_true", help="実HTTPを叩かずキー存在確認のみ（変更なし・読取確認）")
    ap.add_argument("--json", action="store_true", help="機械可読JSONのみ出力（health指標用）")
    ap.add_argument("--out", type=str, default="", help="結果JSONをこのファイルへ追記（構造化ログ）")
    ap.add_argument(
        "--fail-on-error",
        action="store_true",
        help="不正プロファイル検出時にexit 2でバッチスキップ判定を返す",
    )
    ap.add_argument(
        "--notify",
        action="store_true",
        help="不正プロファイル検出時に通知を行う（読取専用・鍵値非表示）",
    )
    args = ap.parse_args()

    results, metrics = run(args.profiles, args.timeout, args.dry_run)

    if args.json:
        print(json.dumps(metrics, ensure_ascii=False))
    else:
        print(format_report(results, metrics))

    if args.out:
        outp = Path(args.out)
        out_lines: list[dict[str, object]] = []
        if outp.exists() and outp.stat().st_size:
            out_lines = json.loads(outp.read_text(encoding="utf-8"))
        out_lines.append(metrics)
        outp.write_text(json.dumps(out_lines, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.notify:
        _notify_api_key_health(metrics)

    # 読取専用: 不正プロファイル存在時も exit code は 0（自動停止・自動変更はしない）。
    # --fail-on-error 付きで呼べば、応募前バッチが metrics['action_required'] を見てスキップできる。
    if args.fail_on_error and metrics["action_required"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
