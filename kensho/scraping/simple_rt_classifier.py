"""simple_rt_classifier — LLMで「フォロー＋リポスト(RT)だけで応募完了するか」を判定するモジュール。

背景 (2026-08-28):
- 従来の keyword_flag（ブラックリスト）では「フォロー+RTだけ」と判定される案件の約半分が
  実際には追加操作（外部サイトX連携・動画認証・キーワード入力・診断・写真/ハッシュタグ投稿等）を
  必要としており、無駄なRT/フォローを消費していた（25件サンプルでFLAG率52%）。
- キーワードの付け外しはいたちごっこ（「結果をチェック」削除→漏れ 等）のため、
  LLM（OpenRouter無料モデル）による自然言語判定に切り替える。
- 実測: 対象4件(FLAG)+正常3件(OK) = 7/7正解（minimax/minimax-m3:free 採用）。
- ★ 公式DeepSeek APIキーは最後の砦のため**絶対に使わない**（ユーザー指摘 2026-08-28）。
  OpenRouter の :free モデル（cost=0）のみ使用。

fail-open 設計: どんな失敗でも UNKNOWN を返し、応募側は従来挙動（応募継続）になる。
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

API_URL: str = "https://api.b.ai/v1/chat/completions"
# ★ 2026-09-07: 収集判定LLMを bai/qwen3.8-flash へ（新メインと統一）。
#   baiはOpenAI互換・chat_template_kwargs容認（enable_thinking無しでもOK）。
#   死英時は OpenRouter 無料枠（minimax-m3:free）へ自動フォールバック（収集を止めない）。
BAI_API_KEY_UNAME: str = "BAI_API_KEY"
DEFAULT_MODEL: str = "qwen3.8-flash"
FALLBACK_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
FALLBACK_MODEL: str = "minimax/minimax-m3:free"
DEFAULT_BATCH_SIZE: int = 8

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
    """メイン判定LLMのAPIキー（BAI_API_KEY）を取得。★公式DeepSeekは使わない。"""
    return _load_key_from_envs("BAI_API_KEY", project_root)


def _load_or_key(project_root: str | Path | None = None) -> str:
    """OpenRouterフォールバック用キー。"""
    return _load_key_from_envs("OPENROUTER_API_KEY", project_root)


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
    }
    # bai qwen3.8-flash: chat_template_kwargs不要（容認はされるが完答）。OpenRouter無料モデルは 429（レート制限）が頻発する → 指数バックオフで2回再試行
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
) -> str:
    """bai判定LLM優先。死活/エラー時だけOpenRouter無料枠へフォールバック（収集を止めない）。"""
    key = _load_api_key()
    if key:
        try:
            return _call_api(key, batch, model, max_tokens, timeout=timeout)
        except Exception:
            pass  # bai失敗 → OR退避へ
    or_key = _load_or_key()
    if not or_key:
        raise  # 両方ない場合はfail-open側でUNKNOWN扱い(呼び出し元except)
    payload_model = model
    return _call_api(or_key, batch, payload_model, max_tokens, timeout=timeout, url=FALLBACK_API_URL)


def classify_texts(
    pairs: list[tuple[str, str]],
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    project_root: str | Path | None = None,
    log: Any = None,
) -> dict[str, str]:
    """(id, tweet_text) のリストを LLM で分類。

    Returns:
        {id: "OK" | "FLAG" | "UNKNOWN"}
    - 例外・パース失敗・本文空は UNKNOWN（fail-open）
    - 小バッチ（既定8件）で送るのは、OpenRouter無料モデルのレート制限(429)と
      推論型モデルのトークン枯渇（本文空）を避けるため。
    """
    if not pairs:
        return {}
    if api_key is None:
        api_key = _load_api_key(project_root)
    # bai qwen3.8-flash は chat_template_kwargs不要・推理も完答（bai優先、OR退避は_fallbackが処理）

    result: dict[str, str] = {pid: "UNKNOWN" for pid, _ in pairs}
    for i in range(0, len(pairs), batch_size):
        batch = [{"id": pid, "text": txt[:800]} for pid, txt in pairs[i : i + batch_size]]
        try:
            content = _call_api_with_fallback(batch, model, max_tokens=2000)
            # 推論トークン枯渇で本文空 → 上限を増やして1回だけ再試行
            if not content.strip():
                content = _call_api_with_fallback(batch, model, max_tokens=4000)
            parsed = _extract_json(content) or []
            for item in parsed:
                rid = item.get("id")
                decision = (item.get("decision") or "").upper()
                if rid and decision in ("OK", "FLAG"):
                    result[rid] = decision
        except Exception as e:  # noqa: BLE001 — fail-open
            if log:
                log.write(f"[simple_rt] batch {i // batch_size + 1} 失敗 → UNKNOWN: {e}")
        time.sleep(0.5)  # OpenRouter無料モデルのレート制限対策（0.5秒間隔）
    return result


def classify_collected_items(
    items: list[dict[str, Any]],
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    log: Any = None,
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
    decisions = classify_texts(pairs, api_key=api_key, model=model, batch_size=batch_size, log=log)
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
