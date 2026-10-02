"""simple_rt_classifier — LLMで「フォロー＋リポスト(RT)だけで応募完了するか」を判定するモジュール。

背景 (2026-08-28):
- 従来の keyword_flag（ブラックリスト）では「フォロー+RTだけ」と判定される案件の約半分が
  実際には追加操作（外部サイトX連携・動画認証・キーワード入力・診断・写真/ハッシュタグ投稿等）を
  必要としており、無駄なRT/フォローを消費していた（25件サンプルでFLAG率52%）。
- キーワードの付け外しはいたちごっこ（「結果をチェック」削除→漏れ 等）のため、
  LLMによる自然言語判定に切り替える。
- 実測: 対象4件(FLAG)+正常3件(OK) = 7/7正解（当時 minimax/minimax-m3:free 採用）。
- ★ 公式DeepSeek APIキーは最後の砦のため**絶対に使わない**（ユーザー指摘 2026-08-28）。
- ★ 判定LLMは **freellmapi（`http://127.0.0.1:3002/v1` / model=auto）のみ**を使う
  （2026-10-01 ユーザー指示「AI関連すべて freellmapi に統一」）。

fail-open 設計: どんな失敗でも UNKNOWN を返し、応募側は従来挙動（応募継続）になる。
"""

from __future__ import annotations

import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from kensho.core.circuit_breaker import BreakerConfig, get_breaker, load_breaker_config, snapshots

API_URL: str = "http://127.0.0.1:3002/v1/chat/completions"
# ★ 2026-10-01: ユーザー指示「AI関連すべて freellmapi に統一」により、判定LLMを
#   freellmapi（OpenAI互換ルーター / model=auto）に一本化。ローカルvLLM・外部API直叩きは廃止。
#   qwen3.8-27b は thinking モデルのため chat_template_kwargs で enable_thinking=False を明示する
#   （OFFにしないと reasoning トークンが max_tokens を食い、content が空になる事象がある）。
FREELMAPI_KEY_NAME: str = "FREELMAPI_API_KEY"
BAI_API_KEY_UNAME: str = FREELMAPI_KEY_NAME  # 旧名の後方互換エイリアス
DEFAULT_MODEL: str = "auto"
FALLBACK_API_URL: str = "http://127.0.0.1:3002/v1/chat/completions"
FALLBACK_MODEL: str = "auto"
SECOND_FALLBACK_MODEL: str = "auto"
DEFAULT_BATCH_SIZE: int = 8

# ★ t_96c94435 (2026-09-23): プロバイダ別サーキットブレーカー名。
#   連続失敗が閾値に達したプロバイダは一定時間「遮断」され、遮断中は冷たい呼び出しを
#   せず即フォールバックする（＝死んでいるプロバイダへの再試行は0件）。
#   閾値・クールダウンは config.yaml `collection.llm_breaker` で動的調整。
#   モデル名・優先順は 2026-10-01 のユーザー指示で freellmapi/auto に統一。
BREAKER_BAI: str = "freellmapi"
# ★ 2026-10-01: freellmapi への再試行段（別ブレーカーで1回だけ再挑戦）。
BREAKER_BAI_RETRY: str = "freellmapi_retry"
BREAKER_OPENROUTER: str = BREAKER_BAI_RETRY  # 旧名の後方互換エイリアス


def _resolve_breaker_config(breaker_config: dict[str, Any] | None) -> BreakerConfig:
    """呼び出し元指定の閾値dict → 無指定なら config.yaml から解決。"""
    if breaker_config is not None:
        return BreakerConfig.from_mapping(breaker_config)
    return load_breaker_config()


def breaker_snapshot() -> dict[str, dict[str, Any]]:
    """プロバイダ別遮断状態のスナップショット（可視化・health指標用）。"""
    return snapshots()


# Hermes profile側 .env（本番実行時はここに OPENROUTER_API_KEY がある。2026-08-28）
# テストで monkeypatch できるようモジュール定数化（テスト分離のため）
PROFILE_ENV_FILE: Path = Path("/home/atushi/.hermes/profiles/kensho-sweeps/.env")

# 判定プロンプト（実測で7/7正解のものを使用）
PROMPT: str = """あなたはX(Twitter)の懸賞応募条件を判定するシステムです。
与えられたツイートの応募方法を読み、**「フォロー＋リポスト(RT)だけで応募完了するか」** を判定してください。

判定基準:
- フォローとリポスト(RT)だけが応募方法で、追加操作が必要ない場合 → "OK"
- 追加操作（外部サイト/動画視聴/認証/キーワード入力/診断/写真投稿/
  ハッシュタグ投稿/アンケート/DM送信等）が必要な場合 → "FLAG"
- 「当選者への連絡方法(DMで連絡等)」「結果チェック」は追加操作に含めない。応募条件のみで判断。
- テキストが途中で切れていても、書かれている範囲で判断してよい。

JSON の配列のみを出力:
[{"id": "...", "decision": "OK|FLAG", "reason": "簡単な理由"}]
"""


_PROJECT_ENV_NAME: str = ".env"


def _load_key_from_envs(key_name: str, project_root: str | Path | None = None) -> str:
    """指定APIキーを プロジェクト.env → Hermes profile .env → 環境変数 の順で取得。"""
    root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent.parent
    candidates = [
        root / _PROJECT_ENV_NAME,
        PROFILE_ENV_FILE,
    ]
    for env_file in candidates:
        try:
            text = env_file.read_text(encoding="utf-8-sig")
            m = re.search(rf"{key_name}\s*=\s*[\"']?([A-Za-z0-9_\-]+)", text)
            if m:
                return m.group(1)
        except OSError:
            continue
    return os.environ.get(key_name, "")


def _load_api_key(project_root: str | Path | None = None) -> str:
    """メイン判定LLMのAPIキー（local qwen）。未設定なら開発用固定トークン。"""
    return _load_key_from_envs(FREELMAPI_KEY_NAME, project_root)


def _load_or_key(project_root: str | Path | None = None) -> str:
    """フォールバック段のキー（2026-09-30〜 local qwen 専用のため _load_api_key と同一）。

    関数名は呼び出し元・テスト互換のために据え置き。外部APIは使わない。
    """
    return _load_api_key(project_root)


def _extract_json(content: str) -> list[dict[str, Any]] | None:
    """LLM出力から JSON 配列を抽出（コードフェンス・前後文言を除去）。"""
    if not content:
        return None
    c = content.strip()
    c = re.sub(r"^```(?:json)?\s*", "", c)
    c = re.sub(r"\s*```$", "", c)
    start = c.find("[")
    end = c.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(c[start : end + 1])
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _call_api(
    api_key: str,
    batch: list[dict[str, str]],
    model: str,
    max_tokens: int,
    timeout: int = 90,
    url: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        # local qwen(thinking) は reasoning が max_tokens を食うため明示的にOFF
        "chat_template_kwargs": {"enable_thinking": False},
    }
    # local vLLM は通常429を返さないが、Windows wake-proxy 経由の一時失敗に備えて再試行
    endpoint = url or API_URL
    for attempt in range(3):
        resp = httpx.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 429 and attempt < 2:
            time.sleep(3 * (attempt + 1))
            continue
        resp.raise_for_status()
        break
    data = resp.json()
    return data["choices"][0]["message"].get("content", "") or ""


def _call_api_with_fallback(
    batch: list[dict[str, str]],
    model: str,
    max_tokens: int,
    timeout: int = 300,
    api_key: str | None = None,
    project_root: str | Path | None = None,
    breaker_config: dict[str, Any] | None = None,
) -> str:
    """local qwen 判定LLM優先。失敗時は同じ local qwen の再試行段へ（収集を止めない）。

    api_key/project_root が明示された場合はそれを優先（呼び出し元の解決を尊重）。

    ★ t_96c94435: 各プロバイダはサーキットブレーカー経由で呼ぶ。
      - 連続失敗が閾値（既定3）に達したプロバイダは遮断され、遮断中は
        `allow()` が False を返すため **冷たい呼び出しをせず** 即フォールバックする
        （freellmapi全滅時に毎バッチ叩く無駄をゼロにする）。
      - クールダウン経過後は半開プローブ1回で再試行（backoff）、成功で閉じる。
      - 優先順・モデル名は変更しない（禁止領域）。
    """
    cfg = _resolve_breaker_config(breaker_config)
    key = api_key if api_key is not None else _load_api_key(project_root)
    if key:
        llm_breaker = get_breaker(BREAKER_BAI, cfg)
        if llm_breaker.allow():
            try:
                content = _call_api(key, batch, model, max_tokens, timeout=timeout)
            except Exception:
                llm_breaker.record_failure()  # bai失敗 → OR退避へ
            else:
                llm_breaker.record_success()
                return content
    or_key = _load_or_key()
    if not or_key:
        raise RuntimeError("no available provider: local qwen失敗（または遮断中）かつキー無し")
    or_breaker = get_breaker(BREAKER_BAI_RETRY, cfg)
    # freellmapiへの再試行段（遮断中は冷たい呼び出しをせず即fail-openへ）
    if or_breaker.allow():
        try:
            content = _call_api(or_key, batch, FALLBACK_MODEL, max_tokens, timeout=timeout, url=FALLBACK_API_URL)
        except Exception:
            or_breaker.record_failure()
        else:
            or_breaker.record_success()
            return content
    # 二段目も同じ freellmapi/auto（別バッチで再挑戦）
    if or_breaker.allow():
        try:
            content = _call_api(or_key, batch, SECOND_FALLBACK_MODEL, max_tokens, timeout=timeout, url=FALLBACK_API_URL)
        except Exception:
            or_breaker.record_failure()
        else:
            or_breaker.record_success()
            return content
    raise RuntimeError("all providers unavailable: local qwen(再試行段)が遮断中または失敗")


def _log_openrouter_usage(project_root: str | Path | None = None) -> None:
    """Increment monthly counter for OpenRouter API calls."""
    try:
        root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent.parent
        usage_file = root / "data" / "openrouter_usage.json"
        usage_file.parent.mkdir(parents=True, exist_ok=True)
        today = datetime.date.today()
        key = f"{today.year}-{today.month:02d}"
        data = {}
        if usage_file.exists():
            try:
                with open(usage_file) as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[key] = data.get(key, 0) + 1
        with open(usage_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def classify_texts(
    pairs: list[tuple[str, str]],
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    project_root: str | Path | None = None,
    log: Any = None,
    breaker_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """(id, tweet_text) のリストを LLM で分類。

    Returns:
        {id: "OK" | "FLAG" | "UNKNOWN"}
    - 例外・パース失敗・本文空は UNKNOWN（fail-open）
    - 小バッチ（既定8件）で送るのは、local qwen の推論時間と
      ルーター配下プロバイダのトークン枯渇（本文空）を避けるため。
    - breaker_config: 遮断閾値の上書き（config.yaml `collection.llm_breaker` と同形式）。
      None なら config.yaml の値を用いる。
    """
    if not pairs:
        return {}
    if api_key is None:
        api_key = _load_api_key(project_root)
    # local qwen3.8-27b（thinking OFF固定、_call_api が chat_template_kwargs を付与）

    result: dict[str, str] = {pid: "UNKNOWN" for pid, _ in pairs}
    for i in range(0, len(pairs), batch_size):
        batch = [{"id": pid, "text": txt[:800]} for pid, txt in pairs[i : i + batch_size]]
        try:
            content = _call_api_with_fallback(
                batch,
                model,
                max_tokens=2000,
                api_key=api_key,
                project_root=project_root,
                breaker_config=breaker_config,
            )
            # 推論トークン枯渇で本文空 → 上限を増やして1回だけ再試行
            if not content.strip():
                content = _call_api_with_fallback(
                    batch,
                    model,
                    max_tokens=4000,
                    api_key=api_key,
                    project_root=project_root,
                    breaker_config=breaker_config,
                )
            parsed = _extract_json(content) or []
            for item in parsed:
                rid = item.get("id")
                decision = (item.get("decision") or "").upper()
                if rid and decision in ("OK", "FLAG"):
                    result[rid] = decision
        except Exception as e:  # noqa: BLE001 — fail-open
            if log:
                log.write(f"[simple_rt] batch {i // batch_size + 1} 失敗 → UNKNOWN: {e}")
        time.sleep(0.5)  # ローカルGPUの連続バッチ負荷を平準化（0.5秒間隔）
    return result


def classify_collected_items(
    items: list[dict[str, Any]],
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    log: Any = None,
    breaker_config: dict[str, Any] | None = None,
) -> tuple[int, int, int]:
    """collected の各アイテムに simple_rt_ok を設定して更新。

    - 対象: keyword_flag=False かつ tweet_text あり かつ simple_rt_ok 未設定のもの
    - FLAG/OK/UNKNOWN を item["simple_rt_ok"] に保存（UNKNOWN も保存して再判定を防ぐ）
    Returns: (classifed_count, flag_count, unknown_count)
    """
    targets = [
        it
        for it in items
        if not it.get("keyword_flag", False)
        and (it.get("tweet_text") or "").strip()
        and not it.get("simple_rt_ok")
        and it.get("tweet_id")
    ]
    if not targets:
        return (0, 0, 0)
    pairs = [(it["tweet_id"], it["tweet_text"]) for it in targets]
    decisions = classify_texts(
        pairs,
        api_key=api_key,
        model=model,
        batch_size=batch_size,
        log=log,
        breaker_config=breaker_config,
    )
    flag_n = 0
    unknown_n = 0
    for it in targets:
        dec = decisions.get(it["tweet_id"], "UNKNOWN")
        it["simple_rt_ok"] = dec
        if dec == "FLAG":
            flag_n += 1
        elif dec == "UNKNOWN":
            unknown_n += 1
    return (len(targets), flag_n, unknown_n)
