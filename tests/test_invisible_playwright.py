"""invisible_playwright モジュールの単体テスト（upstream feder-cr版）"""

from __future__ import annotations

from invisible_playwright import InvisiblePlaywright


class TestInvisiblePlaywright:
    """InvisiblePlaywright コンストラクタの基本テスト"""

    def test_default_parameters(self) -> None:
        """デフォルト: seed=None（ランダム生成）, headless=False"""
        ipw = InvisiblePlaywright()
        assert isinstance(ipw.seed, int)
        assert ipw._headless is False

    def test_seed_int(self) -> None:
        """seed に整数を与える"""
        ipw = InvisiblePlaywright(seed=42)
        assert ipw.seed == 42

    def test_headless_true(self) -> None:
        """headless=True"""
        ipw = InvisiblePlaywright(headless=True)
        assert ipw._headless is True

    def test_humanize(self) -> None:
        """humanize=True"""
        ipw = InvisiblePlaywright(humanize=True)
        assert ipw._humanize is True

    def test_with_pin(self) -> None:
        """pin パラメータの受け渡し (有効な GPU persona を指定)"""
        # invisible-core 34.31.0 で pin 検証が厳格化: 実在する renderer を指定必須
        # 利用可能: 'ANGLE (Intel, Intel(R) HD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)' 等
        ipw = InvisiblePlaywright(pin={"gpu.renderer": "ANGLE (Intel, Intel(R) HD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"})
        assert ipw._pin["gpu.renderer"] == "ANGLE (Intel, Intel(R) HD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"

    def test_with_proxy(self) -> None:
        """proxy パラメータ"""
        ipw = InvisiblePlaywright(proxy={"server": "socks5h://127.0.0.1:1080"})
        assert ipw._proxy["server"] == "socks5h://127.0.0.1:1080"

    def test_with_locale(self) -> None:
        """locale パラメータ"""
        ipw = InvisiblePlaywright(locale="ja-JP")
        assert ipw._locale == "ja-JP"

    def test_with_timezone(self) -> None:
        """timezone パラメータ"""
        ipw = InvisiblePlaywright(timezone="Asia/Tokyo")
        assert ipw._timezone == "Asia/Tokyo"

    def test_extra_prefs(self) -> None:
        """extra_prefs パラメータ"""
        ipw = InvisiblePlaywright(extra_prefs={"security.tls.version.min": 3})
        assert ipw._extra_prefs["security.tls.version.min"] == 3


class TestUpstreamFeatures:
    """upstream invisible_playwright の特徴確認"""

    def test_context_manager_protocol(self) -> None:
        """__enter__ / __exit__ プロトコルを持つ"""
        ipw = InvisiblePlaywright()
        assert hasattr(ipw, "__enter__")
        assert hasattr(ipw, "__exit__")

    def test_no_stealth_script_method(self) -> None:
        """upstream に _stealth_script は存在しない"""
        ipw = InvisiblePlaywright()
        assert not hasattr(ipw, "_stealth_script")

    def test_no_pick_viewport_method(self) -> None:
        """upstream に _pick_viewport は存在しない"""
        ipw = InvisiblePlaywright()
        assert not hasattr(ipw, "_pick_viewport")

    def test_ensure_binary_exists(self) -> None:
        """ensure_binary 関数がインポート可能"""
        from invisible_playwright.download import ensure_binary

        assert callable(ensure_binary)
