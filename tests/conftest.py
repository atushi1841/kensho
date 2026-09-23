"""pytest 共通フィクスチャ。

t_96c94435: LLMプロバイダ遮断器（kensho/core/circuit_breaker.py）はプロセス内
レジストリでプロバイダ別に状態を共有する。テスト間で遮断状態が持ち越されると
「前のテストの連続失敗でbaiが遮断されたまま」となり、無関係なテストが
偽陽性/偽陰性になる。そのため各テストの前後でレジストリを空にする。
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from kensho.core.circuit_breaker import reset_all


@pytest.fixture(autouse=True)
def _reset_circuit_breakers() -> Iterator[None]:
    """プロバイダ遮断状態をテストごとに隔離する。"""
    reset_all()
    yield
    reset_all()
