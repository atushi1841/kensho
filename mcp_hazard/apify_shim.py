"""Apify Actor shim — ローカル実行時は no-op。

Apify環境(APIFY_CONTAINER_PORTあり)では本物の apify.Actor を使い、
ローカルでは charge() 等を no-op にする。
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_USE_REAL = bool(os.environ.get("APIFY_CONTAINER_PORT"))

if _USE_REAL:
    try:
        from apify import Actor as _Actor  # type: ignore
    except ImportError:  # pragma: no cover
        _Actor = None  # type: ignore
else:
    _Actor = None  # type: ignore


class _ShimActor:
    """ローカル用 no-op Actor。"""

    @staticmethod
    async def charge(event_name: str, *, count: int = 1) -> None:
        logger.debug("shim charge: %s x%d (no-op)", event_name, count)

    @staticmethod
    async def init() -> None:
        return None

    @staticmethod
    async def push_data(data: Any) -> None:  # noqa: ANN401
        logger.debug("shim push_data (no-op)")


Actor: Any = _Actor if (_USE_REAL and _Actor is not None) else _ShimActor
