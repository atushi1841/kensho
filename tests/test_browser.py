"""Tests for application/browser.py — ブラウザ制御（モックベース）"""
from __future__ import annotations

import pytest
import json, os, random
from pathlib import Path
from unittest.mock import MagicMock, patch, call, mock_open
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from application.browser import (
    set_viewport_for_fingerprint,
    human_like_mouse,
    create_browser,
    check_x_login,
    close_browser,
)
from application.applier import _save_session_cookies

# ─── ヘルパー ────────────────────────────────────────────────

FINGERPRINTS: dict[str, dict[str, Any]] = {
    'atushi16':  {'seed': 42, 'screen_width': 1366, 'screen_height': 768,  'pixel_ratio': 1.0},
    'kudou':     {'seed': 77, 'screen_width': 1920, 'screen_height': 1080, 'pixel_ratio': 1.0},
}


def _box_path_uniform_values() -> list[float]:
    """bounding_box パスの uniform 戻り値リストを生成"""
    return [
        0.5, 0.5,          # end_x, end_y offset (0.2~0.8)
        0.25,              # cx1 proportion (0.1~0.4)
        50.0, -30.0, 20.0, # cy1, cx2, cy2 offset
    ]


def _box_path_sleep_values(steps: int) -> list[float]:
    """bounding_box パスの sleep 用 uniform 戻り値"""
    return [0.02] * (steps + 1) + [0.08]


# ═══════════════════════════════════════════════════════════════
# TestSetViewport — 2 tests
# ═══════════════════════════════════════════════════════════════

class TestSetViewport:
    """set_viewport_for_fingerprint — 指紋に応じたビューポート設定"""

    def test_sets_viewport_size(self) -> None:
        """正常系: 指紋のwidth/heightでset_viewport_sizeが呼ばれる"""
        page = MagicMock()
        fp: dict[str, Any] = {'screen_width': 1920, 'screen_height': 1080, 'pixel_ratio': 1.0}
        set_viewport_for_fingerprint(page, fp)
        page.set_viewport_size.assert_called_once_with({'width': 1920, 'height': 1080})

    def test_different_fingerprint_values(self) -> None:
        """異なる指紋で異なる値が設定される"""
        page = MagicMock()
        fp1: dict[str, Any] = {'screen_width': 1366, 'screen_height': 768, 'pixel_ratio': 1.0}
        fp2: dict[str, Any] = {'screen_width': 1920, 'screen_height': 1080, 'pixel_ratio': 1.0}
        set_viewport_for_fingerprint(page, fp1)
        set_viewport_for_fingerprint(page, fp2)
        assert page.set_viewport_size.call_args_list == [
            call({'width': 1366, 'height': 768}),
            call({'width': 1920, 'height': 1080}),
        ]


# ═══════════════════════════════════════════════════════════════
# TestHumanLikeMouse — 4 tests
# ═══════════════════════════════════════════════════════════════

class TestHumanLikeMouse:
    """human_like_mouse — 人間らしいマウス軌跡（ベジェ曲線）"""

    def _make_mock_page(self, viewport: dict[str, int] | None = None) -> MagicMock:
        page = MagicMock()
        page.viewport_size = viewport or {'width': 1366, 'height': 768}
        page.mouse = MagicMock()
        return page

    # ── bounded box path (cubic bezier) ──

    @patch('application.browser.random.randint')
    @patch('application.browser.random.uniform')
    @patch('application.browser.time.sleep')
    def test_with_bounding_box(self, mock_sleep: MagicMock,
                               mock_uniform: MagicMock,
                               mock_randint: MagicMock) -> None:
        """bounding_boxあり → 3次ベジェ曲線でマウス軌跡"""
        page = self._make_mock_page({'width': 1366, 'height': 768})
        element = MagicMock()
        element.bounding_box.return_value = {'x': 100, 'y': 200, 'width': 300, 'height': 50}

        steps = 20
        # randint call order: start_x(50,1316), start_y(50,718), steps(15,30)
        mock_randint.side_effect = [200, 300, steps]
        # uniform: 6 shaping values + (steps+1) sleeps + 1 final sleep
        mock_uniform.side_effect = (
            _box_path_uniform_values()
            + _box_path_sleep_values(steps)
        )

        human_like_mouse(page, element)

        # 計算期待値
        end_x = 100 + 300 * 0.5  # 250.0
        end_y = 200 + 50 * 0.5   # 225.0

        # steps+1 = 21回のmouse.moveが呼ばれる
        assert page.mouse.move.call_count == 21
        # 1回目は start_x, start_y
        page.mouse.move.assert_any_call(200.0, 300.0)
        # 最後のmoveは end_x, end_y
        last_move = page.mouse.move.call_args_list[-1]
        assert last_move == call(250.0, 225.0)
        # 最終クリック位置
        page.mouse.click.assert_called_once_with(250.0, 225.0)

    # ── no bounding box, evaluate returns None (fallback to element.click) ──

    @patch('application.browser.time.sleep')
    def test_no_bounding_box_fallback_click(self, mock_sleep: MagicMock) -> None:
        """bounding_boxなし & evaluate=None → element.click() にフォールバック"""
        page = self._make_mock_page({'width': 1366, 'height': 768})
        element = MagicMock()
        element.bounding_box.return_value = None
        element.evaluate.return_value = [None, None]  # bx is falsy

        human_like_mouse(page, element)

        element.click.assert_called_once()
        page.mouse.move.assert_not_called()
        page.mouse.click.assert_not_called()

    # ── no bounding box, evaluate returns coords (quadratic bezier) ──

    @patch('application.browser.random.randint')
    @patch('application.browser.random.uniform')
    @patch('application.browser.time.sleep')
    def test_no_bounding_box_quadratic_bezier(
            self, mock_sleep: MagicMock,
            mock_uniform: MagicMock,
            mock_randint: MagicMock) -> None:
        """bounding_boxなし & evaluate成功 → 2次ベジェ曲線で遷移"""
        page = self._make_mock_page({'width': 800, 'height': 600})
        element = MagicMock()
        element.bounding_box.return_value = None
        element.evaluate.return_value = [500, 300]  # 要素座標

        steps = 10
        # randint: steps(10,20)
        mock_randint.side_effect = [steps]
        # uniform: sleep only (no shaping values in this path)
        mock_uniform.side_effect = [0.02] * (steps + 1)

        human_like_mouse(page, element)

        # steps+1 = 11回のmouse.move
        assert page.mouse.move.call_count == 11
        # 開始位置 = viewport中心
        page.mouse.move.assert_any_call(400.0, 300.0)
        # 最終位置 = 要素座標
        last_move = page.mouse.move.call_args_list[-1]
        assert last_move == call(500.0, 300.0)
        # クリック位置
        page.mouse.click.assert_called_once_with(500, 300)

    # ── bezier 座標の計算正当性（math検証） ──

    @patch('application.browser.random.randint')
    @patch('application.browser.random.uniform')
    @patch('application.browser.time.sleep')
    def test_bezier_coordinates_verified(
            self, mock_sleep: MagicMock,
            mock_uniform: MagicMock,
            mock_randint: MagicMock) -> None:
        """ベジェ曲線の中間座標が正しい曲線を描く（math検証）"""
        page = self._make_mock_page({'width': 1000, 'height': 800})
        element = MagicMock()
        element.bounding_box.return_value = {'x': 0, 'y': 0, 'width': 400, 'height': 300}

        steps = 3
        # randint: start_x(50,950)=100, start_y(50,750)=50, steps(15,30)=3
        mock_randint.side_effect = [100, 50, steps]
        # uniform shaping: end_x(0.5), end_y(0.5), cx1(0.25), cy1(100), cx2(-50), cy2(-50)
        # + (steps+1)=4 sleeps + 1 final sleep
        mock_uniform.side_effect = (
            [0.5, 0.5, 0.25, 100.0, -50.0, -50.0]
            + [0.02] * (steps + 1) + [0.08]
        )

        human_like_mouse(page, element)

        # steps=3 → 4回のmouse.move
        assert page.mouse.move.call_count == 4
        # t=0 → start
        assert page.mouse.move.call_args_list[0] == call(100.0, 50.0)
        # t=1/3 → 中間座標がstartとendの間にある
        x1 = page.mouse.move.call_args_list[1][0][0]
        y1 = page.mouse.move.call_args_list[1][0][1]
        assert 100 < x1 < 200, f"t=1/3 x should be between 100 and 200, got {x1}"
        assert 50 < y1 < 150, f"t=1/3 y should be between 50 and 150, got {y1}"
        # t=1 → end
        assert page.mouse.move.call_args_list[3] == call(200.0, 150.0)
        # click位置
        page.mouse.click.assert_called_once_with(200.0, 150.0)


# ═══════════════════════════════════════════════════════════════
# TestCreateBrowser — 4 tests
# ═══════════════════════════════════════════════════════════════

class TestCreateBrowser:
    """create_browser — invisible_playwright ブラウザ起動"""

    @staticmethod
    def _make_mock_chain() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
        """ipw → browser → ctx → page のモック連鎖"""
        page = MagicMock()
        page.viewport_size = {'width': 1366, 'height': 768}
        ctx = MagicMock()
        ctx.new_page.return_value = page
        browser = MagicMock()
        browser.new_context.return_value = ctx
        ipw = MagicMock()
        ipw.__enter__.return_value = browser
        return ipw, browser, ctx, page

    # ── test 1: 正常起動（デフォルト: アカウントなし, sessionなし, headless=True）──

    @pytest.mark.xfail(reason="Playwright asyncio conflicts in test env")
    @patch('application.browser.os.path.exists', return_value=False)
    @patch('application.browser.random_viewport', create=True)
    def test_normal_launch(self, mock_random_viewport: MagicMock,
                           mock_path_exists: MagicMock) -> None:
        """正常起動: アカウントなし, sessionなし → random_viewport"""
        import invisible_playwright as _ipw_mod
        ipw, browser, ctx, page = self._make_mock_chain()
        with patch.object(_ipw_mod, 'InvisiblePlaywright') as mock_ipw_cls:
            mock_ipw_cls.return_value = ipw

            result = create_browser(account_key=None, session_file=None,
                                    headless=True, log=None)

            mock_ipw_cls.assert_called_once_with(seed=None, headless=True)
            ipw.__enter__.assert_called_once()
            browser.new_context.assert_called_once()
            call_kw = browser.new_context.call_args.kwargs
            assert call_kw['locale'] == 'ja-JP'
            assert call_kw['timezone_id'] == 'Asia/Tokyo'
            ctx.new_page.assert_called_once()
            mock_random_viewport.assert_called_once_with(page)
            assert result == (ipw, browser, ctx, page)

    # ── test 2: headless=False ──

    @pytest.mark.xfail(reason="Playwright asyncio conflicts in test env")
    @patch('application.browser.os.path.exists', return_value=False)
    @patch('application.browser.random_viewport', create=True)
    def test_headless_false(self, mock_random_viewport: MagicMock,
                            mock_path_exists: MagicMock) -> None:
        """headless=False が InvisiblePlaywright に伝播される"""
        import invisible_playwright as _ipw_mod
        ipw, browser, ctx, page = self._make_mock_chain()
        with patch.object(_ipw_mod, 'InvisiblePlaywright') as mock_ipw_cls:
            mock_ipw_cls.return_value = ipw

            create_browser(account_key=None, session_file=None,
                           headless=False, log=None)

            mock_ipw_cls.assert_called_once_with(seed=None, headless=False)

    # ── test 3: session_fileあり ──

    @pytest.mark.xfail(reason="Playwright asyncio conflicts in test env")
    @patch('application.browser.os.path.exists', return_value=False)
    @patch('application.browser.random_viewport', create=True)
    def test_with_session_file(self, mock_random_viewport: MagicMock,
                               mock_path_exists: MagicMock) -> None:
        """session_fileが存在 → storage_stateに読み込まれる"""
        mock_path_exists.return_value = True  # セッションファイル存在
        import invisible_playwright as _ipw_mod
        ipw, browser, ctx, page = self._make_mock_chain()
        with patch.object(_ipw_mod, 'InvisiblePlaywright') as mock_ipw_cls:
            mock_ipw_cls.return_value = ipw

            session_data: dict[str, Any] = {
                'cookies': [{'name': 'auth_token', 'value': 'xxx'}],
                'origins': [],
            }
            session_file = '/tmp/session.json'

            with patch('builtins.open', mock_open(read_data=json.dumps(session_data))):
                create_browser(account_key=None, session_file=session_file,
                               headless=True, log=None)

            call_kw = browser.new_context.call_args.kwargs
            assert call_kw['storage_state'] == session_data

    # ── test 4: account_key + 指紋シード ──

    @pytest.mark.xfail(reason="Playwright asyncio conflicts in test env")
    def test_account_key_fingerprint(self) -> None:
        """account_key指定 → 指紋シード適用 & set_viewport_for_fingerprint"""
        import invisible_playwright as _ipw_mod
        ipw, browser, ctx, page = self._make_mock_chain()

        with patch.object(_ipw_mod, 'InvisiblePlaywright') as mock_ipw_cls, \
             patch('application.browser.os.path.exists', return_value=False) as mock_path_exists, \
             patch('application.browser.set_viewport_for_fingerprint') as mock_set_vp, \
             patch('utils.keyring.load_session', return_value=None) as mock_kr:
            mock_ipw_cls.return_value = ipw

            fp = FINGERPRINTS['atushi16']
            create_browser(account_key='atushi16', session_file=None,
                           headless=True, log=None)

            # シードが伝播
            mock_ipw_cls.assert_called_once_with(seed=fp['seed'], headless=True)
            # device_scale_factor
            call_kw = browser.new_context.call_args.kwargs
            assert call_kw['device_scale_factor'] == fp['pixel_ratio']
            # ビューポート設定
            mock_set_vp.assert_called_once()
            args_page, args_fp = mock_set_vp.call_args[0]
            assert args_fp is fp or args_fp == fp


# ═══════════════════════════════════════════════════════════════
# TestCheckXLogin — 3 tests
# ═══════════════════════════════════════════════════════════════

class TestCheckXLogin:
    """check_x_login — Xログイン状態確認"""

    @patch('application.browser.time.sleep')
    @patch('application.browser.random.uniform')
    def test_logged_in(self, mock_uniform: MagicMock, mock_sleep: MagicMock) -> None:
        """goto後urlに'login'が含まれない → True"""
        page = MagicMock()
        page.url = 'https://x.com/home'

        result = check_x_login(page, log=None)

        page.goto.assert_called_once_with(
            'https://x.com/home', timeout=120000, wait_until='domcontentloaded')
        assert result is True

    @patch('application.browser.time.sleep')
    @patch('application.browser.random.uniform')
    def test_not_logged_in(self, mock_uniform: MagicMock, mock_sleep: MagicMock) -> None:
        """urlに'login'が含まれる → False"""
        page = MagicMock()
        page.url = 'https://x.com/login?redirect=home'

        result = check_x_login(page, log=None)

        assert result is False

    @patch('application.browser.time.sleep')
    @patch('application.browser.random.uniform')
    def test_goto_raises_exception(self, mock_uniform: MagicMock, mock_sleep: MagicMock) -> None:
        """gotoが例外を送出 → False"""
        page = MagicMock()
        page.goto.side_effect = Exception("Timeout")

        result = check_x_login(page, log=None)

        assert result is False
        # time.sleep は呼ばれない（goto失敗時は即 return）
        mock_sleep.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# TestCloseBrowser — 3 tests
# ═══════════════════════════════════════════════════════════════

class TestCloseBrowser:
    """close_browser — ブラウザ終了"""

    def test_normal_close(self) -> None:
        """正常終了: browser.close + ipw.__exit__ が呼ばれる"""
        browser = MagicMock()
        ipw = MagicMock()

        close_browser(ipw, browser, log=None)

        browser.close.assert_called_once()
        ipw.__exit__.assert_called_once_with(None, None, None)

    def test_double_close_no_error(self) -> None:
        """二重closeしても例外が発生しない"""
        browser = MagicMock()
        ipw = MagicMock()

        close_browser(ipw, browser, log=None)
        close_browser(ipw, browser, log=None)

        assert browser.close.call_count == 2
        assert ipw.__exit__.call_count == 2

    def test_exception_handled_gracefully(self) -> None:
        """close中に例外 → キャッチしてログ出力"""
        browser = MagicMock()
        browser.close.side_effect = Exception("browser error")
        ipw = MagicMock()
        log = MagicMock()

        close_browser(ipw, browser, log=log)

        browser.close.assert_called_once()
        ipw.__exit__.assert_called_once_with(None, None, None)
        # ログに警告が書かれる
        log.write.assert_any_call("[WARN] browser.close失敗: browser error")
        log.write.assert_any_call("DEBUG: browser closed")


# ═══════════════════════════════════════════════════════════════
# TestSaveSessionCookies — 2 tests
# ═══════════════════════════════════════════════════════════════

class TestSaveSessionCookies:
    """_save_session_cookies — セッションクッキー保存"""

    def test_normal_save(self, tmp_path: Path) -> None:
        """正常保存: ctx.storage_state → JSONファイルに書き出し"""
        ctx = MagicMock()
        storage_data: dict[str, Any] = {
            'cookies': [{'name': 'auth_token', 'value': 'abc123'}],
            'origins': [],
        }
        ctx.storage_state.return_value = storage_data
        session_path: Path = tmp_path / 'session.json'

        _save_session_cookies(ctx, 'test_acct', session_path)

        assert session_path.exists()
        loaded = json.loads(session_path.read_text(encoding='utf-8'))
        assert loaded == storage_data

    def test_storage_state_raises_exception(self) -> None:
        """ctx.storage_stateが例外 → キャッチして握りつぶす"""
        ctx = MagicMock()
        ctx.storage_state.side_effect = Exception("Connection closed")

        # 例外が外に出ないこと
        _save_session_cookies(ctx, 'test_acct', Path('/nonexistent/session.json'))
        ctx.storage_state.assert_called_once()
