"""
Kensho FIFO Follower Manager — フォロー上限回避のための自動整理
古いフォローから順に解除し、最新2,000件以内に維持する。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE: Path = Path(__file__).parent.parent
DATA_DIR: Path = BASE / "data"
FOLLOW_STATE_FILE: Path = DATA_DIR / "follow_state.json"

MAX_FOLLOWS: int = 1800  # 上限2,000の90%で制御（余裕を持つ）
UNFOLLOW_BATCH: int = 50  # 1回の実行で解除する最大数
MIN_UNFOLLOW_AGE_DAYS: int = 7  # 最低7日間はフォローを維持


def load_follow_state() -> dict[str, Any]:
    if FOLLOW_STATE_FILE.exists():
        try:
            with open(FOLLOW_STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {"accounts": {}, "last_check": ""}


def save_follow_state(state: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(FOLLOW_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_session(account_key: str) -> tuple[str, str, str, str]:
    """(auth_token, ct0, session_path, x_username)"""
    import yaml

    config_path = BASE / "config.yaml"
    if not config_path.exists():
        return "", "", "", ""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for acct in cfg.get("accounts", []):
        if acct["key"] == account_key:
            session_path = BASE / acct["session"]
            x_username: str = acct.get("display", "").lstrip("@")
            if session_path.exists():
                with open(session_path, encoding="utf-8") as sf:
                    session_data = json.load(sf)
                cookies = {c["name"]: c["value"] for c in session_data.get("cookies", [])}
                return cookies.get("auth_token", ""), cookies.get("ct0", ""), str(acct["session"]), x_username
    return "", "", "", ""


async def get_following(account_key: str, auth_token: str, ct0: str) -> list[dict[str, Any]]:
    """twscrapeでフォロー一覧を取得"""
    from twscrape import API, gather

    api = API()
    cookie_str = f"auth_token={auth_token}; ct0={ct0}"
    await api.pool.add_account_cookies(f"fifo_{account_key}", cookie_str)

    try:
        user = await api.user_by_login(account_key)
        following = await gather(api.following(user.id, limit=2000))
        result = []
        for i, f in enumerate(following):
            result.append({
                "id": f.id,
                "username": f.username,
                "display_name": f.displayname or "",
                "followed_order": i,  # APIの返却順 = フォローした順（古い順）
            })
        return result
    except Exception as e:
        print(f"  [{account_key}] フォロー一覧取得エラー: {e}")
        return []


def unfollow_users(account_key: str, auth_token: str, ct0: str, user_ids: list[int]) -> int:
    """twitter-api-clientでフォロー解除"""
    from twitter.account import Account

    if not user_ids:
        return 0

    try:
        acct = Account(cookies={"auth_token": auth_token, "ct0": ct0})
        count = 0
        for uid in user_ids:
            try:
                acct.unfollow(uid)
                count += 1
                print(f"    ⛔ 解除 @{uid}")
                import time

                time.sleep(3)  # レート制限対策
            except Exception as e:
                print(f"    ❌ 解除失敗 {uid}: {e}")
        return count
    except Exception as e:
        print(f"  [{account_key}] Account初期化エラー: {e}")
        return 0


def manage_account(account_key: str, state: dict[str, Any]) -> dict[str, Any]:
    """1アカウントのフォロー管理"""
    print(f"  [{account_key}] チェック中...")

    auth_token, ct0, session_path, x_username = load_session(account_key)
    if not auth_token:
        print("    auth_tokenなし - スキップ")
        return state

    # Xユーザー名でフォロー一覧を取得
    username_to_query: str = x_username or account_key
    print(f"    Xユーザー名: {username_to_query}")
    following = asyncio.run(get_following(username_to_query, auth_token, ct0))
    if not following:
        print("    フォロー一覧が空 - スキップ")
        return state

    total = len(following)
    print(f"    現在のフォロー数: {total}/{MAX_FOLLOWS}")

    if total <= MAX_FOLLOWS:
        print("    上限未達 - スキップ")
        # 状態は保存
        acct_state = state.setdefault(account_key, {})
        acct_state["last_follow_count"] = total
        acct_state["last_check"] = datetime.now().isoformat()
        return state

    # 解除するユーザーを選択（古い順 = APIの返却順の早いもの）
    excess = total - MAX_FOLLOWS
    to_unfollow = min(excess, UNFOLLOW_BATCH)

    # 古い順にソート（followed_orderが小さい=古い）
    following.sort(key=lambda x: x["followed_order"])
    targets = following[:to_unfollow]

    print(f"    解除候補: {len(targets)}件（{excess}件超過中）")
    for t in targets[:5]:
        print(f"      @{t['username']} (id={t['id']})")

    # 実行
    user_ids = [t["id"] for t in targets]
    unfollowed = unfollow_users(account_key, auth_token, ct0, user_ids)

    # 状態更新
    acct_state = state.setdefault(account_key, {})
    acct_state["last_follow_count"] = total
    acct_state["last_unfollow_count"] = unfollowed
    acct_state["last_check"] = datetime.now().isoformat()
    acct_state["total_followed_ever"] = acct_state.get("total_followed_ever", 0) + total

    if unfollowed > 0:
        print(f"    ✅ {unfollowed}件解除完了（残り{total - unfollowed}）")

    return state


def main() -> None:
    print(f"[FollowManager FIFO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    state = load_follow_state()
    account_keys: list[str] = ["atushi16", "kudou", "chugakujuken", "zin20120731"]

    for key in account_keys:
        state = manage_account(key, state)
        print()

    save_follow_state(state)
    print(f"  保存完了 → {FOLLOW_STATE_FILE}")


if __name__ == "__main__":
    main()
