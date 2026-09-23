#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""エージェント実行テレメトリ集計 — span JSONL から agent別 KPI を出す (t_8158cb49).

`scripts/agent_span_emit.py` が追記する `data/agent_spans/YYYY-MM-DD.jsonl` を読み、
agent (gen_ai.agent.name) 別に 実行数 / 成功率 / 平均duration / token合計 /
エラー種別内訳 を表出力する（`--json` で構造化出力）。

cron 安全: ファイル不在・空ファイル・壊れた行・型不正値は **警告のみで exit 0**。
壊れた行はスキップして残りの有効 span で集計を続ける。

使用法:
  python3 scripts/agent_span_report.py --date $(date +%F)
  python3 scripts/agent_span_report.py --date 2026-09-23 --json
  python3 scripts/agent_span_report.py --file /path/to/spans.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from agent_span_emit import REQUIRED_FIELDS, resolve_span_dir

AGENT_KEY = "gen_ai.agent.name"
ERROR_KEY = "error.type"
TOKENS_IN_KEY = "gen_ai.usage.input_tokens"
TOKENS_OUT_KEY = "gen_ai.usage.output_tokens"
DURATION_KEY = "duration_ms"
MODEL_KEY = "gen_ai.request.model"
PROVIDER_KEY = "gen_ai.provider.name"


def parse_day(value: str | None) -> str:
    """YYYY-MM-DD / YYYYMMDD を受け付け YYYY-MM-DD を返す（既定: 今日)."""
    from datetime import date as _date

    if not value:
        return _date.today().isoformat()
    digits = value.replace("-", "").strip()
    if len(digits) != 8 or not digits.isdigit():
        raise ValueError(f"--date の形式が不正: {value!r} (YYYY-MM-DD)")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def _as_nonneg_int(value: Any) -> int | None:
    """token/duration 値の正規化。bool・負値・非数値は None（不正）.  float は整数化."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value >= 0 and float(value).is_integer():
        return int(value)
    return None


def load_spans(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """JSONL を読み (有効span, 警告リスト) を返す。欠落行・壊れた行はスキップ+警告."""
    warnings: list[str] = []
    if not path.exists():
        warnings.append(f"span ファイルがありません: {path}")
        return [], warnings
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        warnings.append(f"span ファイルを読めません: {path} ({e})")
        return [], warnings

    spans: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip():
            continue  # 空行（末尾改行など）は正常
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            warnings.append(f"{path.name}:{lineno}: 壊れたJSON行をスキップ")
            continue
        if not isinstance(row, dict):
            warnings.append(f"{path.name}:{lineno}: JSON object でない行をスキップ")
            continue
        missing = [f for f in (*REQUIRED_FIELDS, AGENT_KEY) if f not in row]
        if missing:
            warnings.append(f"{path.name}:{lineno}: 必須フィールド欠落をスキップ {missing}")
            continue
        agent = row.get(AGENT_KEY)
        if not isinstance(agent, str) or not agent.strip():
            warnings.append(f"{path.name}:{lineno}: {AGENT_KEY} が不正な行をスキップ")
            continue
        span = dict(row)
        for key in (TOKENS_IN_KEY, TOKENS_OUT_KEY, DURATION_KEY):
            normalized = _as_nonneg_int(row.get(key))
            if normalized is None:
                warnings.append(f"{path.name}:{lineno}: {key}={row.get(key)!r} を 0 として集計")
                normalized = 0
            span[key] = normalized
        err = row.get(ERROR_KEY)
        if err is not None and not isinstance(err, str):
            warnings.append(f"{path.name}:{lineno}: {ERROR_KEY} が文字列でないため error 扱い")
            span[ERROR_KEY] = str(err)
        spans.append(span)
    return spans, warnings


def aggregate(spans: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """agent 別に 実行数/成功数/成功率/平均duration/token合計/エラー内訳 を集計する."""
    buckets: dict[str, dict[str, Any]] = {}
    for span in spans:
        agent = str(span.get(AGENT_KEY))
        b = buckets.setdefault(agent, {
            "runs": 0, "ok": 0, "errors": 0, "duration_total": 0,
            "tokens_in": 0, "tokens_out": 0, "error_types": {},
            "models": {}, "providers": {},
        })
        b["runs"] += 1
        b["duration_total"] += span.get(DURATION_KEY, 0)
        b["tokens_in"] += span.get(TOKENS_IN_KEY, 0)
        b["tokens_out"] += span.get(TOKENS_OUT_KEY, 0)
        error_type = span.get(ERROR_KEY)
        if error_type:
            b["errors"] += 1
            b["error_types"][str(error_type)] = b["error_types"].get(str(error_type), 0) + 1
        else:
            b["ok"] += 1
        model = span.get(MODEL_KEY)
        if isinstance(model, str) and model:
            b["models"][model] = b["models"].get(model, 0) + 1
        provider = span.get(PROVIDER_KEY)
        if isinstance(provider, str) and provider:
            b["providers"][provider] = b["providers"].get(provider, 0) + 1

    out: dict[str, dict[str, Any]] = {}
    for agent in sorted(buckets, key=lambda a: (-buckets[a]["runs"], a)):
        b = buckets[agent]
        runs = b["runs"]
        out[agent] = {
            "runs": runs,
            "ok": b["ok"],
            "errors": b["errors"],
            "success_rate": round(100.0 * b["ok"] / runs, 1) if runs else 0.0,
            "avg_duration_ms": round(b["duration_total"] / runs, 1) if runs else 0.0,
            "tokens_in": b["tokens_in"],
            "tokens_out": b["tokens_out"],
            "tokens_total": b["tokens_in"] + b["tokens_out"],
            "error_types": dict(sorted(b["error_types"].items(), key=lambda kv: (-kv[1], kv[0]))),
            "models": b["models"],
            "providers": b["providers"],
        }
    return out


def build_report(spans: list[dict[str, Any]], warnings: list[str], *, day: str, source: Path,
                 skipped: int = 0) -> dict[str, Any]:
    """集計結果を JSON 構造にまとめる（集計値は aggregate と同一の情報源)."""
    agents = aggregate(spans)
    return {
        "date": day,
        "source": str(source),
        "spans_valid": len(spans),
        "spans_skipped": skipped,
        "agents": agents,
        "totals": {
            "runs": sum(a["runs"] for a in agents.values()),
            "ok": sum(a["ok"] for a in agents.values()),
            "errors": sum(a["errors"] for a in agents.values()),
            "tokens_in": sum(a["tokens_in"] for a in agents.values()),
            "tokens_out": sum(a["tokens_out"] for a in agents.values()),
        },
        "warnings": warnings,
    }


def render_text(report: dict[str, Any]) -> str:
    """人間が読む表出力（ASCII 罫線・固定幅)."""
    lines = [
        f"agent_span_report date={report['date']} source={report['source']}",
        f"  spans_valid={report['spans_valid']} spans_skipped={report['spans_skipped']} "
        f"warnings={len(report['warnings'])}",
    ]
    agents: dict[str, dict[str, Any]] = report["agents"]
    if not agents:
        lines.append("  (有効な span がありません)")
        return "\n".join(lines)

    header = f"  {'agent':<10} {'runs':>5} {'ok':>5} {'err':>5} {'succ%':>7} {'avg_ms':>9} {'tok_in':>8} {'tok_out':>8}  error_types"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for agent, a in agents.items():
        errs = ", ".join(f"{k}={v}" for k, v in a["error_types"].items()) or "-"
        lines.append(
            f"  {agent:<10} {a['runs']:>5} {a['ok']:>5} {a['errors']:>5} {a['success_rate']:>7.1f} "
            f"{a['avg_duration_ms']:>9.1f} {a['tokens_in']:>8} {a['tokens_out']:>8}  {errs}"
        )
    t = report["totals"]
    lines.append(
        f"  {'TOTAL':<10} {t['runs']:>5} {t['ok']:>5} {t['errors']:>5} "
        f"{(round(100.0 * t['ok'] / t['runs'], 1) if t['runs'] else 0.0):>7.1f} "
        f"{'':>9} {t['tokens_in']:>8} {t['tokens_out']:>8}"
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="agent span JSONL の agent別集計")
    ap.add_argument("--date", default=None, help="対象日 YYYY-MM-DD (既定: 今日)")
    ap.add_argument("--file", default=None, help="JSONL を直接指定（既定: <span_dir>/<date>.jsonl）")
    ap.add_argument("--out-dir", default=None, help="span ディレクトリ（既定: env KENSHO_AGENT_SPANS_DIR or <repo>/data/agent_spans）")
    ap.add_argument("--json", action="store_true", help="JSON で出力")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        day = parse_day(args.date)
        source = Path(args.file) if args.file else (resolve_span_dir(args.out_dir) / f"{day}.jsonl")
        spans, warnings = load_spans(source)
        # skipped = 壊れた行/欠落行の警告数（空行警告は出さない）
        skipped = len([w for w in warnings if "スキップ" in w])
        report = build_report(spans, warnings, day=day, source=source, skipped=skipped)
    except (ValueError, OSError) as e:  # cron 安全: 例外でも exit 0
        print(f"agent_span_report: warning: {e}", file=sys.stderr)
        print(json.dumps({"date": args.date, "agents": {}, "warnings": [str(e)]}, ensure_ascii=True))
        return 0

    for w in warnings:
        print(f"agent_span_report: warning: {w}", file=sys.stderr)
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
