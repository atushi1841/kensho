"""回帰テスト: guarded_source への callable 受け渡しの引数整合（2026-09-23 追加）。

背景（実障害）:
    commit 1b55c7d (t_c5097d30) が ken-kaku 収集で
    ``guarded_source("ken-kaku", lambda out, ps, ak: scrape_kenkaku(out, ps, ak, ...))``
    と「引数なしの lambda」を渡した。``guarded_source`` は ``fn(*args)`` を呼ぶ実装のため
    実収集時に ``_collect_impl.<locals>.<lambda>() missing 3 required positional arguments``
    の TypeError となり、SelfHealingLoop が3回失敗して収集全体（Step 2c 以降）が停止した。
    実測: logs/collect_20260923_180002.log / 190001.log / 200001.log（3回連続 Traceback）。
    修正後: logs/collect_20260923_210002.log で Step 2b ken-kaku 19件 → Step 2c 進行を確認。

本テストは collector.py の全ての ``guarded_source(...)`` / ``_run_source(...)`` 呼び出しについて
「callable が、その後ろに渡された位置引数で実際に呼べるか」を静的に検証する。
ネットワーク不要・高速・決定的。

2026-09-24 更新 (t_b64c35ea): 予算付きラッパー ``_run_source(name, fn, *args)``
（run_budget 導入時に追加・中身は guarded_source へ委譲）も検証対象に含めた。
呼び出し側の名前が変わっても arity 不整合の検出能力は維持される。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import kensho.scraping.collector as collector

SRC_PATH = Path(collector.__file__)

#: 検証対象のラッパー名（いずれも ``fn(*args)`` で callable を呼ぶ実装）。
GUARD_WRAPPERS: tuple[str, ...] = ("guarded_source", "_run_source")


def _sig_from_lambda(node: ast.Lambda) -> inspect.Signature:
    """lambda の AST から inspect.Signature を組み立てる。"""
    params: list[inspect.Parameter] = []
    a = node.args
    n_pos = len(a.posonlyargs) + len(a.args)
    n_with_default = len(a.defaults)
    kw_with_default = dict(zip([p.arg for p in a.kwonlyargs], a.kw_defaults, strict=False))
    for i, arg in enumerate([*a.posonlyargs, *a.args]):
        has_default = i >= n_pos - n_with_default
        params.append(
            inspect.Parameter(
                arg.arg,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=inspect.Parameter.empty if not has_default else None,
            )
        )
    for arg in a.kwonlyargs:
        params.append(
            inspect.Parameter(
                arg.arg,
                inspect.Parameter.KEYWORD_ONLY,
                default=kw_with_default.get(arg.arg) or inspect.Parameter.empty,
            )
        )
    if a.vararg is not None:
        params.append(inspect.Parameter(a.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    if a.kwarg is not None:
        params.append(inspect.Parameter(a.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    return inspect.Signature(params)


def _resolve(node: ast.expr) -> Any:
    """Name/Attribute/partial(...) を collector モジュール名前空間から解決する。"""
    ns: dict[str, Any] = vars(collector)
    if isinstance(node, ast.Name):
        return ns.get(node.id)
    if isinstance(node, ast.Attribute):
        base = _resolve(node.value)
        return getattr(base, node.attr, None) if base is not None else None
    if isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Attribute) and node.func.attr == "partial")
        or (isinstance(node.func, ast.Name) and node.func.id == "partial")
    ):
        base = _resolve(node.args[0])
        # partial の keyword は実行時まで評価できないため「束縛済み」として名前だけ扱う
        prebound = {k.arg for k in node.keywords if k.arg}
        return ("partial", base, prebound)
    return None


def _can_bind(resolved: Any, n_args: int) -> bool:
    prebound: set[str] = set()
    if isinstance(resolved, tuple) and resolved and resolved[0] == "partial":
        _, resolved, prebound = resolved
    if resolved is None:
        return True  # 解決不能（動的）な場合は本テストの対象外
    if isinstance(resolved, inspect.Signature):
        sig = resolved
    else:
        try:
            sig = inspect.signature(resolved)
        except (TypeError, ValueError):
            return True
    remaining = [
        p for p in sig.parameters.values() if not (p.name in prebound and p.kind is p.KEYWORD_ONLY)
    ]
    try:
        inspect.Signature(remaining).bind(*[object()] * n_args)
    except TypeError:
        return False
    return True


def find_arity_violations(source: str) -> list[str]:
    """guarded_source / _run_source 呼び出しのうち、callable と位置引数が噛み合わないものを列挙。"""
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in GUARD_WRAPPERS or len(node.args) < 2:
            continue
        target, extra = node.args[1], node.args[2:]
        resolved: Any = _sig_from_lambda(target) if isinstance(target, ast.Lambda) else _resolve(target)
        if not _can_bind(resolved, len(extra)):
            violations.append(
                f"line {node.lineno}: guarded_source の callable に位置引数{len(extra)}個で呼べない "
                f"（fn(*args) 呼び出しで TypeError になる）"
            )
    return violations


def test_collector_guarded_source_calls_are_arity_safe() -> None:
    """collector.py の全 guarded_source 呼び出しが fn(*args) で実行可能であること。"""
    source = SRC_PATH.read_text(encoding="utf-8")
    violations = find_arity_violations(source)
    assert violations == [], f"guarded_source 引数不整合: {violations}"


def test_kenkaku_call_passes_three_positional_args() -> None:
    """ken-kaku は scrape_kenkaku(out, ps, ak, proxy=...) 形式で3位置引数が必要。"""
    source = SRC_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id in GUARD_WRAPPERS):
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            if node.args[0].value == "ken-kaku":
                found = True
                assert len(node.args) >= 5, (
                    "ken-kaku 呼び出しは callable + out/processed_set/account_keys の3引数が必要"
                )
    assert found, "ken-kaku の guarded_source/_run_source 呼び出しが見つからない"


def test_detector_checks_partial_bare_name() -> None:
    """負のコントロール: `from functools import partial` の素の Name 呼び出しでも arity を検証する。

    以前は ``functools.partial``（Attribute）しか解決できず、collector.py が実際に使う
    ``partial(...)``（Name）は「解決不能=対象外」として素通りしていた（＝検出力の穴）。
    """
    buggy = (
        "def _collect_impl():\n"
        "    items = _run_source(\n"
        '        "ken-kaku",\n'
        "        partial(scrape_kenkaku, proxy=p),\n"
        "        out,\n"
        "    )\n"
    )
    violations = find_arity_violations(buggy)
    assert len(violations) == 1, f"partial(Name) の arity 不整合を検出できない: {violations}"


def test_detector_catches_the_historical_bug() -> None:
    """検知器の負のコントロール: 1b55c7d のバグパターンを実際に検出できること。"""
    buggy = (
        "def _collect_impl():\n"
        "    items = guarded_source(\n"
        '        "ken-kaku",\n'
        "        lambda out, ps, ak: scrape_kenkaku(out, ps, ak, proxy=p),\n"
        "    )\n"
    )
    violations = find_arity_violations(buggy)
    assert len(violations) == 1, f"バグパターンを検出できない: {violations}"


def test_detector_accepts_fixed_pattern() -> None:
    """検知器の正のコントロール: partial + 位置3引数の修正版は違反ゼロ。"""
    fixed = (
        "def _collect_impl():\n"
        "    items = guarded_source(\n"
        '        "ken-kaku",\n'
        "        partial(scrape_kenkaku, proxy=p),\n"
        "        out,\n"
        "        ps,\n"
        "        ak,\n"
        "    )\n"
    )
    assert find_arity_violations(fixed) == []
