"""
Kensho DM Monitor — XのDMを巡回し、当選通知を自動検出
v1.0: Playwrightでhttps://x.com/messages にアクセス、未読DMを解析

使い方:
    from kensho.scraping.dm_monitor import check_dms
    found = check_dms(account_key='atushi16')

    # 特定垢のみ、全垢、または設定ファイル経由
    found = check_dms()                          # config.yaml の全垢を順次チェック
    found = check_dms(account_key='kudou')       # 指定垢のみ
"""

from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from kensho.application.browser import (
    check_x_login,
    close_browser,
    create_browser,
)
from kensho.core.config import load as load_config
from kensho.utils.notify import send_notification

# ── 当選検出キーワード（部分一致） ──
_WIN_KEYWORDS = [
    "当選",
    "当選者",
    "ご当選",
    "おめでとうございます",
    "おめでとう！",
    "賞品",
    "発送",
    "au Pay",
    "振込",
    "受け取り",
    "抽選結果",
    "当たり",
    "プレゼント当選",
    "ご連絡",
    "DMにて",
    "d払い",
    "PayPay",
    "商品発送",
    "発送しました",
]

_SKIP_KEYWORDS = [
    "RTで",
    "フォローで",
    "応募",
    "キャンペーン",
    "プレゼント企画",
]

_DM_URL = "https://x.com/messages"

# ── セレクタ（X v2 DOM構造に依存） ──
_CONVERSATION_ITEM = 'div[data-testid="conversation"]'
_UNREAD_BADGE = '[data-testid="unreadBadge"]'
_MESSAGE_TEXT = 'div[data-testid="messageEntry"]'
_CONVERSATION_NAME = 'div[data-testid="conversationInfo"] a span'


def _is_win_message(text: str) -> bool:
    """メッセージ本文に当選キーワードが含まれるか判定"""
    lower = text.lower()
    # スキップキーワードが含まれているか（応募関連の自動DMは除外）
    for skip in _SKIP_KEYWORDS:
        if skip.lower() in lower:
            return False
    # 当選キーワードチェック
    for kw in _WIN_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


def _load_wins_cache(data_dir: Path) -> dict[str, list[dict]]:
    """既存の当選ログを読込（重複検出用）"""
    path = data_dir / "dm_wins.json"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_wins_cache(data_dir: Path, wins: dict[str, list[dict]]) -> None:
    """当選ログを保存"""
    path = data_dir / "dm_wins.json"
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(wins, f, ensure_ascii=False, indent=2)
    print(f"[DM Monitor] 当選ログ保存: {path}")


def _is_already_recorded(sender_screen_name: str, message_text: str, wins: dict[str, list[dict]]) -> bool:
    """重複チェック: 同じ送信者から同じメッセージを既に記録済みか"""
    for entry in wins.get(sender_screen_name, []):
        if entry.get("message_text", "") == message_text:
            return True
    return False


def check_dms(
    account_key: str | None = None,
    cfg: dict[str, Any] | None = None,
    log: Any = None,
) -> list[dict]:
    """
    XのDMを巡回し、当選通知を検出する。

    Args:
        account_key: チェックするアカウントのキー（None=全垢）
        cfg: config.yaml の内容（None=自動読込）
        log: ログライター

    Returns:
        新しく検出された当選DMのリスト
        [{"sender": "@xxx", "message_text": "...", "account_key": "atushi16",
          "detected_at": "2026-07-03T20:30:00", "conversation_url": "..."}, ...]
    """
    if cfg is None:
        cfg = load_config()

    accounts = cfg.get("accounts", [])
    data_dir = Path(cfg["general"]["project_dir"]) / "data"

    # 既存の当選ログ
    wins_cache = _load_wins_cache(data_dir)
    if account_key not in wins_cache:
        wins_cache[account_key] = []

    new_wins: list[dict] = []
    targets = [a for a in accounts if account_key is None or a["key"] == account_key]

    for acct in targets:
        key = acct["key"]
        display = acct.get("display", key)
        session_rel = acct.get("session", "")

        print(f"[DM Monitor] {display} のDMをチェック中...")

        try:
            pw, browser, ctx, page = create_browser(
                account_key=key,
                headless=True,
                log=log,
            )
        except Exception as e:
            print(f"[DM Monitor] {display} ブラウザ起動失敗: {e}")
            continue

        try:
            # ログイン確認
            if not check_x_login(page, log):
                print(f"[DM Monitor] {display} ログイン状態なし → スキップ")
                continue

            # DMページへ移動
            print("[DM Monitor] DMページに移動中...")
            try:
                page.goto(
                    _DM_URL,
                    timeout=60000,
                    wait_until="domcontentloaded",
                )
            except Exception as e:
                print(f"[DM Monitor] {display} DMページ遷移失敗: {e}")
                continue

            time.sleep(random.uniform(3, 6))

            # 会話リストを取得
            try:
                convos = page.query_selector_all(_CONVERSATION_ITEM)
            except Exception:
                convos = []

            if not convos:
                print(f"[DM Monitor] {display} 会話リストが見つかりません")
                continue

            print(f"[DM Monitor] {display} {len(convos)}件の会話を確認")

            for conv in convos:
                try:
                    # 未読バッジの有無
                    unread = conv.query_selector(_UNREAD_BADGE)
                    if not unread:
                        continue

                    # 送信者名の取得
                    try:
                        sender_el = conv.query_selector(_CONVERSATION_NAME)
                        sender = sender_el.inner_text().strip() if sender_el else "不明"
                    except Exception:
                        sender = "不明"

                    # 会話をクリック
                    try:
                        conv.click()
                        time.sleep(random.uniform(2, 4))
                    except Exception:
                        continue

                    # 最新メッセージの取得
                    try:
                        msgs = page.query_selector_all(_MESSAGE_TEXT)
                    except Exception:
                        msgs = []

                    latest_text = ""
                    if msgs:
                        try:
                            latest_text = msgs[-1].inner_text().strip()
                        except Exception:
                            pass

                    if not latest_text:
                        continue

                    # 短すぎるメッセージは除外
                    if len(latest_text) < 5:
                        continue

                    # 当選キーワードチェック
                    if _is_win_message(latest_text):
                        conv_url = page.url

                        if not _is_already_recorded(sender, latest_text, wins_cache):
                            win_entry = {
                                "sender": sender,
                                "message_text": latest_text,
                                "account_key": key,
                                "detected_at": datetime.now().isoformat(),
                                "conversation_url": conv_url,
                            }
                            new_wins.append(win_entry)
                            wins_cache.setdefault(key, []).append(win_entry)
                            print(f"[DM Monitor] ★ 当選DM検出! {display} ← {sender}: {latest_text[:100]}")
                            # Telegram通知
                            try:
                                _msg = (
                                    f"🎉 当選DM検出!\n"
                                    f"アカウント: {display}\n"
                                    f"送信者: {sender}\n"
                                    f"内容: {latest_text[:200]}"
                                )
                                send_notification("dm_win", _msg, account_key=key)
                            except Exception as _ne:
                                print(f"[DM Monitor] 通知エラー: {_ne}")
                        else:
                            print(f"[DM Monitor] 既知の当選DM（重複スキップ）: {sender}")

                except Exception as e:
                    print(f"[DM Monitor] 会話処理中エラー: {e}")
                    continue

        finally:
            try:
                close_browser(pw, browser, log)
            except Exception:
                pass

    # 当選ログを保存
    _save_wins_cache(data_dir, wins_cache)

    if new_wins:
        print(f"\n[DM Monitor] ★ 新規当選DM: {len(new_wins)}件")
    else:
        print("\n[DM Monitor] 新規当選DMなし")

    return new_wins


def list_dm_wins(data_dir: str | None = None) -> list[dict]:
    """保存済みの当選DM一覧を表示"""
    if data_dir is None:
        cfg = load_config()
        data_dir = Path(cfg["general"]["project_dir"]) / "data"
    else:
        data_dir = Path(data_dir)

    wins = _load_wins_cache(data_dir)
    all_wins: list[dict] = []
    for acct_key, entries in wins.items():
        for entry in entries:
            entry["account_key"] = acct_key
            all_wins.append(entry)

    all_wins.sort(key=lambda x: x.get("detected_at", ""), reverse=True)
    return all_wins


if __name__ == "__main__":
    # 単体実行
    import random

    check_dms()
