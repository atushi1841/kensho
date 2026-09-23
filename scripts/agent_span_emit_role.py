#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""役割終了時のエージェント実行テレメトリ自動 emit（t_4ec92f06 / additive 配線）。

t_8158cb49 が用意した span 層（`scripts/agent_span_emit.py`）は「手動実行でしか
JSONL が増えない」= 本番フローに未配線だった（2026-09-24 QA 実測: 自動生成 span 0 件）。
本スクリプトは、critic / worker / qa のレポート生成が通る**共通ヘルパーの末尾ステップ**
（`kensho-kanban-sync.sh <role>`）から 1 行で呼べる「安全版 emit 入口」を提供する。

設計上の契約（テレメトリは本番を壊してはならない）:

1. **例外を投げない**: 内部で `agent_span_emit.try_emit_span()` を使い、失敗理由は
   stderr の 1 行警告に落とす。呼び出し側の終了コードを変えない（配線側も `|| true`）。
2. **既定 exit 0**: 役割を特定できない・span を書けない等の異常でも exit 0。
   `--strict` を付けたときだけ exit 2（テスト・人手検証用。本番配線では使わない）。
3. **role を捏造しない**: 役割が特定できないときは span を書かずに警告だけ出す
   （誤ラベル span で集計を汚すより、欠測の方がまし）。
4. **secret を書かない**: span に入るのは role / model / task_id / 数値のみ。
   （APIキー・トークンは読まない。`agent_span_emit` 側の契約をそのまま継承）

解決順（左が優先）:
  role        : --agent/--role > $KENSHO_AGENT_ROLE > $KENSHO_PROFILE > $HERMES_PROFILE
  model       : --model > $KENSHO_MODEL > $HERMES_MODEL > <profile>/config.yaml の model.default > unknown
                （役割名だけ渡された場合は kensho-revenue-<role> → kensho-<role> → kensho-sweeps の順に探索）
                ※ cron ジョブは jobs.json で model を固定していることがある。実測名を残したい
                  呼び出し側は `KENSHO_MODEL=<jobs.json の model>` を渡すこと（既定は prof config）。
  conversation: --task-id > --conversation-id > $KENSHO_TASK_ID > $KENSHO_CONVERSATION_ID
                > $HERMES_KANBAN_TASK > <profile 名>
  duration    : --duration-ms > $KENSHO_DURATION_MS > 0
  error-type  : --error-type > $KENSHO_ERROR_TYPE > （成功時は省略）

使用法:
  python3 scripts/agent_span_emit_role.py --agent worker --task-id t_xxx --duration-ms 1234
  KENSHO_AGENT_ROLE=qa python3 scripts/agent_span_emit_role.py --verbose
  python3 scripts/agent_span_emit_role.py --agent critic --dry-run   # 書き込まずに span を表示
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_span_emit as emit  # noqa: E402  (同一 scripts/ ディレクトリの共用モジュール)

#: role 解決に使う環境変数（左が優先）
ROLE_ENV_VARS: tuple[str, ...] = ("KENSHO_AGENT_ROLE", "KENSHO_PROFILE", "HERMES_PROFILE")
#: model 解決に使う環境変数
MODEL_ENV_VARS: tuple[str, ...] = ("KENSHO_MODEL", "HERMES_MODEL")
#: conversation.id 解決に使う環境変数
CONVERSATION_ENV_VARS: tuple[str, ...] = (
    "KENSHO_TASK_ID",
    "KENSHO_CONVERSATION_ID",
    "HERMES_KANBAN_TASK",
)
DURATION_ENV_VAR = "KENSHO_DURATION_MS"
ERROR_TYPE_ENV_VAR = "KENSHO_ERROR_TYPE"
PROVIDER_ENV_VAR = "KENSHO_PROVIDER"
#: model がどこからも分からないときの値（空文字は span 契約違反なので固定文字列）
UNKNOWN_MODEL = "unknown"
#: プロファイル config.yaml の探索ルート（env で差し替え可＝テスト用）
PROFILES_DIR_ENV = "HERMES_PROFILES_DIR"
DEFAULT_PROFILES_DIR = Path.home() / ".hermes" / "profiles"
#: 役割名（critic/worker/qa）しか渡されていない時の config.yaml 探索候補
ROLE_PROFILE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "critic": ("kensho-revenue-critic", "kensho-critic", "kensho-sweeps"),
    "worker": ("kensho-revenue-worker", "kensho-worker", "kensho-sweeps"),
    "qa": ("kensho-revenue-qa", "kensho-qa", "kensho-sweeps"),
}

_MODEL_DEFAULT_RE = re.compile(r"^\s+default:\s*[\"']?([^\"'\s#]+)")


def first_env(names: Sequence[str]) -> str | None:
    """names のうち最初に非空で設定されている環境変数の値を返す."""
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


def profile_model_default(profile: str, profiles_dir: Path | None = None) -> str | None:
    """<profiles_dir>/<profile>/config.yaml の model.default を読む（読めなければ None）.

    依存を増やさないため YAML パーサは使わず、トップレベル `model:` ブロック配下の
    最初の `default:` 行だけを拾う（config.yaml はフラットな2階層が前提）。
    """
    if not profile:
        return None
    root = profiles_dir or Path(os.environ.get(PROFILES_DIR_ENV) or DEFAULT_PROFILES_DIR)
    cfg = root / profile / "config.yaml"
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    in_model_block = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if not line.startswith((" ", "\t")):  # トップレベルキー
            in_model_block = stripped.startswith("model:")
            continue
        if in_model_block:
            m = _MODEL_DEFAULT_RE.match(line)
            if m:
                return m.group(1)
    return None


def model_for_agent(agent: str, profiles_dir: Path | None = None) -> str | None:
    """agent（プロファイル名 or 役割名）に対応する config.yaml の model.default を探す."""
    candidates: list[str] = []
    if "-" in agent or agent not in ROLE_PROFILE_CANDIDATES:
        candidates.append(agent)
    try:
        role = emit.normalize_agent(agent)
    except ValueError:
        role = ""
    if role:
        for candidate in ROLE_PROFILE_CANDIDATES.get(role, ()):
            if candidate not in candidates:
                candidates.append(candidate)
    for candidate in candidates:
        model = profile_model_default(candidate, profiles_dir)
        if model:
            return model
    return None


def default_span_dir() -> Path:
    """span 出力先（env 優先、無ければ <repo>/data/agent_spans）."""
    return emit.resolve_span_dir()


def _warn(message: str) -> None:
    print(f"agent_span_emit_role: warning: {message}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="役割終了時の span 自動 emit（安全版・既定 exit 0）",
    )
    ap.add_argument("--agent", "--role", dest="agent", default=None,
                    help="役割 or プロファイル名 (critic / worker / qa / kensho-qa ...)")
    ap.add_argument("--task-id", default=None, help="kanban task_id (gen_ai.conversation.id)")
    ap.add_argument("--conversation-id", default=None, help="task_id の代わりに session_id 等")
    ap.add_argument("--model", default=None, help="使用モデル（未指定なら env → profile config）")
    ap.add_argument("--provider", default=None, help="gen_ai.provider.name（既定 deepseek）")
    ap.add_argument("--tokens-in", type=int, default=0)
    ap.add_argument("--tokens-out", type=int, default=0)
    ap.add_argument("--duration-ms", type=int, default=None)
    ap.add_argument("--error-type", default=None)
    ap.add_argument("--date", default=None, help="出力ファイル日付 YYYY-MM-DD（既定 今日）")
    ap.add_argument("--out-dir", default=None, help="span 出力先（既定 $KENSHO_AGENT_SPANS_DIR or data/agent_spans）")
    ap.add_argument("--dry-run", action="store_true", help="書き込まず span を stdout に出す")
    ap.add_argument("--verbose", action="store_true", help="成功時も 1 行 stdout に出す")
    ap.add_argument("--strict", action="store_true",
                    help="失敗時に exit 2（テスト・人手検証用。本番配線では使わない）")
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    agent = (args.agent or first_env(ROLE_ENV_VARS) or "").strip()
    if not agent:
        _warn("役割が特定できません（--agent か $KENSHO_AGENT_ROLE/$HERMES_PROFILE が必要）。span を書きません")
        return 2 if args.strict else 0

    try:
        emit.normalize_agent(agent)  # 検証のみ（未知 role は span を書かずに落とす）
    except ValueError as exc:
        _warn(f"{exc}。span を書きません")
        return 2 if args.strict else 0

    model = (args.model or first_env(MODEL_ENV_VARS) or model_for_agent(agent) or UNKNOWN_MODEL)
    conversation_id = (
        args.task_id
        or args.conversation_id
        or first_env(CONVERSATION_ENV_VARS)
        or agent
    )

    duration_raw = args.duration_ms
    if duration_raw is None:
        env_duration = first_env((DURATION_ENV_VAR,))
        try:
            duration_raw = int(env_duration) if env_duration is not None else 0
        except ValueError:
            duration_raw = 0
    duration_ms = max(0, int(duration_raw))

    kwargs: dict[str, Any] = {
        "agent": agent,
        "model": model,
        "conversation_id": conversation_id,
        "tokens_in": max(0, int(args.tokens_in)),
        "tokens_out": max(0, int(args.tokens_out)),
        "duration_ms": duration_ms,
    }
    error_type = args.error_type or first_env((ERROR_TYPE_ENV_VAR,))
    if error_type:
        kwargs["error_type"] = error_type
    provider = args.provider or first_env((PROVIDER_ENV_VAR,))
    if provider:
        kwargs["provider"] = provider

    if args.dry_run:
        try:
            span = emit.build_span(**kwargs)
        except ValueError as exc:
            _warn(f"span を組み立てられません: {exc}")
            return 2 if args.strict else 0
        print(json.dumps(span, ensure_ascii=True))
        return 0

    if args.out_dir:
        kwargs["span_dir"] = args.out_dir

    # 安全版: 例外を投げず None を返す（計測失敗で本番を止めない）
    written = emit.try_emit_span(**kwargs)
    if written is None:
        _warn(f"span を書けませんでした（role={agent}）。本処理の終了コードは変えません")
        return 2 if args.strict else 0

    if args.verbose:
        print(f"agent_span_emit_role: appended 1 span -> {written} "
              f"(agent={emit.normalize_agent(agent)}, model={model}, "
              f"conversation.id={conversation_id}, duration_ms={duration_ms})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
