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
    with patch("kensho.utils.proxy_watchdog._port_reachable", return_value=True):
        assert pw.restore_dead_proxies(config) == 0
