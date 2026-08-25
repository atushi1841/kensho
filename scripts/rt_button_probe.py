"""RTボタンDOM確認プローブ — Xの最新UIでRTボタンがどうなっているか検証する。

使い方:
    uv run python scripts/rt_button_probe.py [account_key]

動作:
- 指定アカウントのセッションでFirefoxを起動（Xログイン済み）
- collected.json から未応募ツイートを1件開く
- RTボタンのdata-testid / aria-label を列挙してダンプ（クリックしない）
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kensho.application.browser import check_x_login, close_browser, create_browser  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _pick_test_tweet(account: str) -> str:
    """collected.json から未応募のツイートURLを1件選ぶ（RT要件あり優先）。"""
    data = json.loads((ROOT / "data" / "collected.json").read_text(encoding="utf-8"))
    collected = data.get("collected", [])
    for e in collected:
        x_url = e.get("x_url", "")
        if not x_url or "/status/" not in x_url:
            continue
        applied = e.get("applied", {}) or {}
        if applied.get(account):
            continue
        return x_url
    # 全部応募済みなら先頭のツイートを使う（DOM確認なので応募済みでも可）
    for e in collected:
        x_url = e.get("x_url", "")
        if x_url and "/status/" in x_url:
            return x_url
    raise SystemExit("テスト用ツイートが見つからない")


def main() -> None:
    account = sys.argv[1] if len(sys.argv) > 1 else "atushi16"
    print(f"=== RTボタンDOM確認 (account={account}) ===")

    pw, browser, ctx, page = create_browser(account_key=account, headless=True)
    try:
        ok = check_x_login(page, screen_name=account)
        print(f"ログイン状態: {ok}")
        if not ok:
            print("  ※ ログイン失敗 — セッションが切れている可能性")
            return

        url = _pick_test_tweet(account)
        print(f"テストツイート: {url}")
        try:
            page.goto(url, timeout=40000, wait_until="domcontentloaded")
            time.sleep(6)
        except Exception:
            print("  [WARN] ツイートページにアクセスできません。Xホームにフォールバック")

        # ツイートページが開けなかったらXホーム（タイムライン）を開く
        if not page.query_selector_all("[data-testid]"):
            print("  → Xホーム（タイムライン）を開きます")
            try:
                page.goto("https://x.com/home", timeout=40000, wait_until="domcontentloaded")
                time.sleep(8)
            except Exception:
                pass

        # 全data-testidと全buttonのaria-labelをダンプ（XのUI変更でRTボタンが不明のため）
        print("\n--- 全data-testidダンプ（最大60件） ---")
        dump = page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('[data-testid]').forEach(el => {
                    const tid = el.getAttribute('data-testid');
                    const aria = el.getAttribute('aria-label') || '';
                    const tag = el.tagName;
                    out.push(tid + ' <' + tag + '>' + (aria ? ' | aria=' + aria.slice(0, 50) : ''));
                });
                return out.slice(0, 60);
            }"""
        )
        for line in dump:
            print(f"  {line}")

        print("\n--- 全buttonのaria-label（最大30件） ---")
        btns = page.evaluate(
            """() => {
                const out = [];
                document.querySelectorAll('button').forEach(el => {
                    const aria = el.getAttribute('aria-label') || el.textContent || '';
                    out.push((aria || '').trim().slice(0, 60));
                });
                return [...new Set(out)].slice(0, 30);
            }"""
        )
        for b in btns:
            print(f"  {b}")
    finally:
        close_browser(pw, browser, label="probe")
        print("\n=== 完了 ===")


if __name__ == "__main__":
    main()
