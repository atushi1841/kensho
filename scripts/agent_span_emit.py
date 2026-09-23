#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""エージェント実行テレメトリ emit — OTel GenAI semconv 準拠の span JSONL (t_8158cb49).

1実行=1行の span を `data/agent_spans/YYYY-MM-DD.jsonl` へ**追記**する。
既存行は一切書き換えない（append-only）。キー名は OpenTelemetry GenAI
semantic conventions (gen-ai-agent-spans) の名前をそのまま使う:

  gen_ai.operation.name        : "invoke_agent" 固定（エージェント呼び出し）
  gen_ai.provider.name         : LLMプロバイダ (deepseek 等)
  gen_ai.agent.name            : critic | worker | qa（ロール。プロファイル名から正規化）
  gen_ai.agent.id              : 生のプロファイル名 (kensho-qa 等)
  gen_ai.request.model         : 使用モデル
  gen_ai.conversation.id       : kanban task_id または session_id
  gen_ai.usage.input_tokens    : 入力token
  gen_ai.usage.output_tokens   : 出力token
  duration_ms                  : 実行時間(msec)
  error.type                   : 失敗時のみ（成功時は省略）

出典: https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-agent-spans.md

secret値（APIキー等）は span に書かない。値は json.dumps(ensure_ascii=True) により
ASCII エスケープされるため、1 span = 1 物理行が常に保証される。

使用法:
  python3 scripts/agent_span_emit.py --agent kensho-qa --model deepseek-v4-flash \\
      --task-id t_xxx --tokens-in 100 --tokens-out 50 --duration-ms 1200
  python3 scripts/agent_span_emit.py --agent kensho-worker --model deepseek-v4-flash \\
      --conversation-id sess_abc --duration-ms 900 --error-type timeout
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import time
from datetime import date as _date
from pathlib import Path
from typing import Any

# ─── 契約 ────────────────────────────────────────────────────────────────────
OPERATION_NAME = "invoke_agent"
AGENT_ROLES: tuple[str, ...] = ("critic", "worker", "qa")
DEFAULT_PROVIDER = "deepseek"
SPAN_DIR_ENV = "KENSHO_AGENT_SPANS_DIR"

#: 1 span に必ず存在するキー（欠落は下流の集計・QA検証で FAIL 扱い）
REQUIRED_FIELDS: tuple[str, ...] = (
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.agent.name",
    "gen_ai.request.model",
    "gen_ai.conversation.id",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "duration_ms",
)
#: 追加の必須キー（traceability 用。OTel の span フィールド名に合わせる）
AUX_FIELDS: tuple[str, ...] = ("gen_ai.agent.id", "time_unix_nano", "span_id")
OPTIONAL_FIELDS: tuple[str, ...] = ("error.type",)

_ERROR_TYPE_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SEP_RE = re.compile(r"[-_/ .:]+")


def project_root() -> Path:
    """リポジトリルート（env KENSHO_PROJECT_DIR 優先、無ければこのスクリプトの親の親)."""
    env = os.environ.get("KENSHO_PROJECT_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]


def resolve_span_dir(out_dir: str | os.PathLike[str] | None = None) -> Path:
    """span 出力ディレクトリ（CLI > env > <repo>/data/agent_spans)."""
    if out_dir is not None:
        return Path(out_dir)
    env = os.environ.get(SPAN_DIR_ENV)
    if env:
        return Path(env)
    return project_root() / "data" / "agent_spans"


def normalize_agent(agent: str) -> str:
    """プロファイル名 → ロール(critic|worker|qa) へ正規化する。

    "kensho-qa" / "kensho-revenue-qa" → "qa"、"kensho-worker" → "worker"。
    どのロールにも該当しない場合は ValueError（無言で worker に倒さない）。
    """
    key = (agent or "").strip().lower()
    if not key:
        raise ValueError("agent が空です")
    if key in AGENT_ROLES:
        return key
    parts = [p for p in _SEP_RE.split(key) if p]
    for role in AGENT_ROLES:
        if role in parts:
            return role
    raise ValueError(f"未知の agent: {agent!r} (許可: {', '.join(AGENT_ROLES)} を含む名前)")


def build_span(
    *,
    agent: str,
    model: str,
    conversation_id: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int = 0,
    error_type: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    now_ns: int | None = None,
    span_id: str | None = None,
) -> dict[str, Any]:
    """OTel GenAI semconv 準拠の span dict を組み立てる（純粋関数・I/O なし)."""
    if not (model or "").strip():
        raise ValueError("model が空です")
    if not (conversation_id or "").strip():
        raise ValueError("conversation_id (task_id / session_id) が空です")
    if not (provider or "").strip():
        raise ValueError("provider が空です")
    for name, value in (("tokens_in", tokens_in), ("tokens_out", tokens_out), ("duration_ms", duration_ms)):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name} は整数で指定してください: {value!r}")
        if value < 0:
            raise ValueError(f"{name} は 0 以上で指定してください: {value}")
    if error_type is not None and not _ERROR_TYPE_RE.match(error_type):
        raise ValueError(f"error.type の形式が不正: {error_type!r} (^[A-Za-z0-9._-]{{1,64}}$)")

    span: dict[str, Any] = {
        "gen_ai.operation.name": OPERATION_NAME,
        "gen_ai.provider.name": provider.strip(),
        "gen_ai.agent.name": normalize_agent(agent),
        "gen_ai.agent.id": agent.strip(),
        "gen_ai.request.model": model.strip(),
        "gen_ai.conversation.id": conversation_id.strip(),
        "gen_ai.usage.input_tokens": tokens_in,
        "gen_ai.usage.output_tokens": tokens_out,
        "duration_ms": duration_ms,
        "time_unix_nano": now_ns if now_ns is not None else time.time_ns(),
        "span_id": span_id or secrets.token_hex(8),
    }
    if error_type is not None:
        # 成功時はキー自体を持たせない（error.type の有無が成否の判定子）
        span["error.type"] = error_type
    return span


def span_path(day: str, span_dir: str | os.PathLike[str] | None = None) -> Path:
    """指定日の JSONL パス（day は YYYY-MM-DD)."""
    return resolve_span_dir(span_dir) / f"{day}.jsonl"


def append_span(span: dict[str, Any], day: str, span_dir: str | os.PathLike[str] | None = None) -> Path:
    """span を 1 行として追記する。既存行には触れない（append モードのみ)."""
    path = span_path(day, span_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(span, ensure_ascii=True, sort_keys=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return path


def emit_span(
    *,
    agent: str,
    model: str,
    conversation_id: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    duration_ms: int = 0,
    error_type: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    day: str | None = None,
    span_dir: str | os.PathLike[str] | None = None,
) -> Path:
    """本番フローから呼ぶための in-process 入口（検証エラーは例外で通知)."""
    target_day = day or _date.today().isoformat()
    span = build_span(
        agent=agent,
        model=model,
        conversation_id=conversation_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        duration_ms=duration_ms,
        error_type=error_type,
        provider=provider,
    )
    return append_span(span, target_day, span_dir)


def try_emit_span(**kwargs: Any) -> Path | None:
    """テレメトリは本番を壊してはならない: 失敗しても例外を投げず None を返す.

    既存の応募/収集ロジックに 1 行で挿せるようにするための安全版。
    """
    try:
        return emit_span(**kwargs)
    except (ValueError, OSError) as e:  # 計測失敗で本番を止めない
        print(f"agent_span_emit: warning: span を書けませんでした: {e}", file=sys.stderr)
        return None


def parse_day(value: str | None) -> str:
    """YYYY-MM-DD / YYYYMMDD を受け付け、YYYY-MM-DD を返す."""
    if not value:
        return _date.today().isoformat()
    digits = value.replace("-", "").strip()
    if len(digits) != 8 or not digits.isdigit():
        raise ValueError(f"--date の形式が不正: {value!r} (YYYY-MM-DD)")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="OTel GenAI semconv 準拠の agent span を JSONL に追記")
    ap.add_argument("--agent", required=True, help="プロファイル名 (kensho-qa / kensho-worker / kensho-critic 等)")
    ap.add_argument("--model", required=True, help="使用モデル (gen_ai.request.model)")
    ap.add_argument("--task-id", default=None, help="kanban task_id (gen_ai.conversation.id)")
    ap.add_argument("--conversation-id", default=None, help="task_id の代わりに session_id を指定")
    ap.add_argument("--tokens-in", type=int, default=0, help="gen_ai.usage.input_tokens")
    ap.add_argument("--tokens-out", type=int, default=0, help="gen_ai.usage.output_tokens")
    ap.add_argument("--duration-ms", type=int, default=0, help="実行時間(msec)")
    ap.add_argument("--error-type", default=None, help="失敗時のみ (timeout / connection_error 等)")
    ap.add_argument("--provider", default=DEFAULT_PROVIDER, help="gen_ai.provider.name")
    ap.add_argument("--date", default=None, help="出力ファイル日付 YYYY-MM-DD (既定: 今日)")
    ap.add_argument("--out-dir", default=None, help=f"span 出力先ディレクトリ (既定: $ {SPAN_DIR_ENV} or <repo>/data/agent_spans)")
    ap.add_argument("--print-json", action="store_true", help="書き込んだ span を stdout にも出す")
    ap.add_argument("--dry-run", action="store_true", help="書き込まずに span を stdout へ出す")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    conversation_id = args.conversation_id or args.task_id
    if not conversation_id:
        print("agent_span_emit: --task-id か --conversation-id のどちらかが必要です", file=sys.stderr)
        return 2
    try:
        day = parse_day(args.date)
        span = build_span(
            agent=args.agent,
            model=args.model,
            conversation_id=conversation_id,
            tokens_in=args.tokens_in,
            tokens_out=args.tokens_out,
            duration_ms=args.duration_ms,
            error_type=args.error_type,
            provider=args.provider,
        )
        if args.dry_run:
            print(json.dumps(span, ensure_ascii=True))
            return 0
        path = append_span(span, day, args.out_dir)
    except (ValueError, OSError) as e:
        print(f"agent_span_emit: error: {e}", file=sys.stderr)
        return 2
    if args.print_json:
        print(json.dumps(span, ensure_ascii=True))
    print(f"agent_span_emit: appended 1 span -> {path} (agent={span['gen_ai.agent.name']}, "
          f"error.type={span.get('error.type', '-')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
