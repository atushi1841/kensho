#!/usr/bin/env python3
"""
Kensho IP Binder — スレッドローカルなネットワークインターフェースバインド

ForceBindIPの代替。Pythonの socket.create_connection をモンキーパッチして、
スレッドごとに特定のIPアドレスにバインドする。

使い方:
    from core.ip_binder import set_interface, clear_interface

    set_interface("192.168.1.100")  # このスレッドの全ソケットをバインド
    # ... httpx/requests 等の通信 ...
    clear_interface()  # 解除

またはwith文:
    with bind_interface("192.168.1.100"):
        # このスレッドの全ソケットがバインドされる
"""
from __future__ import annotations

import socket
import threading
from contextlib import contextmanager
from typing import Any, Generator, Optional

# ── スレッドローカルストレージ ──
_local = threading.local()


def set_interface(bind_ip: str) -> None:
    """現在のスレッドのソケットを指定IPにバインド"""
    _local.bind_ip = bind_ip


def clear_interface() -> None:
    """現在のスレッドのIPバインドを解除"""
    _local.bind_ip = None


def get_bind_ip() -> Optional[str]:
    """現在のスレッドのバインドIPを取得"""
    return getattr(_local, 'bind_ip', None)


@contextmanager
def bind_interface(bind_ip: str) -> Generator[None, Any, None]:
    """with文で使えるIPバインドコンテキスト"""
    set_interface(bind_ip)
    try:
        yield
    finally:
        clear_interface()


# ── socket.create_connection のモンキーパッチ ──
_original_create_connection = socket.create_connection


def _bound_create_connection(
    address: tuple[str, int],
    timeout: float = socket._GLOBAL_DEFAULT_TIMEOUT,  # type: ignore[arg-type]
    source_address: tuple[str, int] | None = None,
    **kwargs: Any,
) -> socket.socket:
    """バインドIPが設定されていれば source_address に指定して接続"""
    bind_ip = get_bind_ip()
    if bind_ip and source_address is None:
        source_address = (bind_ip, 0)
    return _original_create_connection(
        address, timeout=timeout, source_address=source_address, **kwargs
    )


def apply_patch() -> None:
    """socket.create_connection をパッチ（起動時に1回だけ実行）"""
    socket.create_connection = _bound_create_connection


def revert_patch() -> None:
    """パッチを元に戻す（テスト用）"""
    socket.create_connection = _original_create_connection
