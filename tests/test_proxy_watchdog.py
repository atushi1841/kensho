"""Tests for kensho.utils.proxy_watchdog.

Covers the IPv4-wait helper (WiFi link-establishment race that caused
kensho_proxy.py to exit(2) on restart) and the wired-ethernet skip for atushi16.
"""

from unittest.mock import patch

from kensho.utils import proxy_watchdog as pw


def test_adapter_ipv4_returns_real_ip():
    with patch("kensho.utils.proxy_watchdog.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "10.0.0.5\r\n"
        assert pw._adapter_ipv4("zin_AW6povo") == "10.0.0.5"


def test_adapter_ipv4_filters_apipa():
    with patch("kensho.utils.proxy_watchdog.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "169.254.172.42\r\n"
        assert pw._adapter_ipv4("kudou_RM10JE_B") is None


def test_adapter_ipv4_skips_apipa_then_returns_real():
    with patch("kensho.utils.proxy_watchdog.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "169.254.172.42\r\n10.219.234.171\r\n"
        assert pw._adapter_ipv4("chugakujuken_RM10JE_S") == "10.219.234.171"


def test_adapter_ipv4_timeout_returns_none():
    with patch("kensho.utils.proxy_watchdog.subprocess.run", side_effect=TimeoutError()):
        assert pw._adapter_ipv4("foo") is None


def test_wait_for_adapter_ipv4_returns_after_lag():
    responses = iter([None, None, "192.168.16.136"])
    with (
        patch(
            "kensho.utils.proxy_watchdog._adapter_ipv4",
            side_effect=lambda adapter: next(responses),
        ),
        patch("kensho.utils.proxy_watchdog.time.sleep"),
    ):
        assert pw._wait_for_adapter_ipv4("zin_AW6povo", wait_seconds=5) == "192.168.16.136"


def test_wait_for_adapter_ipv4_timeout_returns_none():
    with (
        patch("kensho.utils.proxy_watchdog._adapter_ipv4", return_value=None),
        patch("kensho.utils.proxy_watchdog.time.sleep"),
    ):
        assert pw._wait_for_adapter_ipv4("foo", wait_seconds=1) is None


def test_restore_dead_proxies_skips_wired_ethernet():
    config = {"accounts": [{"key": "atushi16"}]}
    with patch("kensho.utils.proxy_watchdog._port_reachable", return_value=False):
        assert pw.restore_dead_proxies(config) == 0


def test_restore_dead_proxies_skips_alive():
    config = {"accounts": [{"key": "kudou"}]}
    with (
        patch("kensho.utils.proxy_watchdog._port_reachable", return_value=True),
        patch("kensho.utils.proxy_watchdog._check_egress", return_value=True),
    ):
        assert pw.restore_dead_proxies(config) == 0


def test_restore_dead_proxies_recovers_no_egress():
    """ポートLISTENINGだが疎通なし（WiFi半死）→ WiFi再接続+プロキシ再起動を試行"""
    config = {"accounts": [{"key": "TankanNotes"}]}
    with (
        patch("kensho.utils.proxy_watchdog._port_reachable", return_value=True),
        patch("kensho.utils.proxy_watchdog._check_egress", return_value=False),
        patch("kensho.utils.proxy_watchdog._adapter_ipv4", return_value="10.0.0.9"),
        patch("kensho.utils.proxy_watchdog._wait_for_adapter_ipv4", return_value="10.0.0.9"),
        patch("kensho.utils.proxy_watchdog.subprocess.run") as mock_run,
        patch("kensho.utils.proxy_watchdog.time.sleep"),
    ):
        # Get-NetAdapter は Up を返す
        mock_run.return_value.stdout = "Up"
        assert pw.restore_dead_proxies(config) == 1


def test_egress_returns_true():
    """SOCKS5経由で出口IP取得成功 → True"""
    import sys
    import types

    class FakeSock:
        def __init__(self) -> None:
            self._data = b"HTTP/1.0 200 OK\r\n\r\n1.2.3.4"

        def set_proxy(self, *a, **k) -> None: ...
        def settimeout(self, *a, **k) -> None: ...
        def connect(self, *a, **k) -> None: ...
        def send(self, *a, **k) -> None: ...
        def recv(self, n: int) -> bytes:
            d, self._data = self._data[:n], self._data[n:]
            return d

        def close(self) -> None: ...

    fake = types.ModuleType("socks")
    fake.socksocket = lambda: FakeSock()
    fake.SOCKS5 = 5  # proxy_watchdog が socks.SOCKS5 を参照するため必要
    sys.modules["socks"] = fake
    try:
        assert pw._check_egress(1085, timeout=2) is True
    finally:
        del sys.modules["socks"]


def test_egress_returns_false_on_error():
    """SOCKS5接続失敗 → False"""
    import sys
    import types

    class BadSock:
        def set_proxy(self, *a, **k) -> None: ...
        def settimeout(self, *a, **k) -> None: ...
        def connect(self, *a, **k) -> None:
            raise TimeoutError("timeout")

        def close(self) -> None: ...

    fake = types.ModuleType("socks")
    fake.socksocket = lambda: BadSock()
    fake.SOCKS5 = 5
    sys.modules["socks"] = fake
    try:
        assert pw._check_egress(1085, timeout=2) is False
    finally:
        del sys.modules["socks"]


def test_egress_import_error_returns_true():
    """PySocks未インストール環境では従来挙動（ポート疎通のみ）"""
    import sys

    saved = sys.modules.get("socks")
    sys.modules.pop("socks", None)
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "socks":
            raise ImportError("no socks")
        return real_import(name, *args, **kwargs)

    try:
        with patch("builtins.__import__", side_effect=fake_import):
            assert pw._check_egress(1085, timeout=2) is True
    finally:
        if saved is not None:
            sys.modules["socks"] = saved


def test_kill_listeners_invokes_powershell():
    """_kill_listeners がコマンドライン照合でkensho_proxyを殺すPowerShellを呼ぶ"""
    with patch("kensho.utils.proxy_watchdog.subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        assert pw._kill_listeners(1085) == 1
        cmd = " ".join(mock_run.call_args.args[0])
        assert "1085" in cmd
        assert "Stop-Process" in cmd
        assert "Get-CimInstance" in cmd
        assert "kensho_proxy" in cmd


def test_kill_listeners_handles_timeout():
    """PowerShellタイムアウト時は0を返す"""
    with patch("kensho.utils.proxy_watchdog.subprocess.run", side_effect=TimeoutError()):
        assert pw._kill_listeners(1085) == 0


def test_kill_listeners_handles_oserror():
    """OSError時は0を返す"""
    with patch("kensho.utils.proxy_watchdog.subprocess.run", side_effect=OSError()):
        assert pw._kill_listeners(1085) == 0
