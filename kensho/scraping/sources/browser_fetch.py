"""Cloudflare ボットチャレンジ対策の実ブラウザ取得（fail-open / t_c0e0563d）。

2026-09-24 の実測結論:
- knshow.com の 502 は Cloudflare の origin 障害（同一IPの実ブラウザでも 502、robots.txt は
  cf-cache-status: STALE = origin 再検証失敗によるキャッシュ配信）。ブラウザ化では解決しない。
- 本モジュールが効くのは 403/503 + "Just a moment..." の CF ボットチャレンジのケース。
  その分類の時のみ knshow.fetch_knshow_listing がここを呼ぶ。

設計上の制約（実測に基づく）:
- Windows Chrome の CDP(http://127.0.0.1:9222) は使わない。WSL からは到達できず、Windows 側
  Chrome は --remote-debugging-port 無しで常駐しているため 9222 自体が閉じている（実測）。
- 代わりに WSL 側の patchright chromium（~/.cache/ms-playwright に導入済み）を headless 起動する。
- 一切の失敗（patchright 不在 / 起動不能 / タイムアウト / 例外）で None を返し、呼出側は
  従来 httpx 経路の結果をそのまま使う（fail-open = 収集全体を止めない）。
"""

from __future__ import annotations

_PAGE_TIMEOUT_MS: int = 30000
_LAUNCH_ARGS: tuple[str, ...] = ("--no-sandbox", "--disable-dev-shm-usage")
_UA: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def fetch_via_browser(url: str, *, timeout_ms: int = _PAGE_TIMEOUT_MS) -> tuple[int, str] | None:
    """実ブラウザ（patchright chromium headless）で url を取得して (status, html) を返す。

    失敗（patchright 不在・起動不能・例外・タイムアウト）はすべて None を返す。例外は投げない。
    """
    try:
        from patchright.sync_api import sync_playwright
    except Exception:  # noqa: BLE001 — patchright 未導入環境では経路ごと無効化（fail-open）
        return None

    browser = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=list(_LAUNCH_ARGS))
            ctx = browser.new_context(locale="ja-JP", timezone_id="Asia/Tokyo", user_agent=_UA)
            page = ctx.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            status: int = int(resp.status) if resp is not None else 0
            return status, page.content()
    except Exception:  # noqa: BLE001 — fail-open（収集全体を止めない）
        return None
    finally:
        try:
            if browser is not None:
                browser.close()
        except Exception:  # noqa: BLE001 — close 失敗は無視
            pass
