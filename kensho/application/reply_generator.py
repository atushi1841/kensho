"""
Kensho Reply Generator — ツイート内容に応じた自然なリプライ生成
v3.3: application/applier.py から抽出
"""

from __future__ import annotations

import random
from typing import Any

_REPLY_TEMPLATES: list[str] = [
    "参加します！",
    "応募しました😊",
    "当たりますように🙏",
    "楽しみです！",
    "ぜひ欲しいです✨",
    "いいですね👍",
    "これ気になってました！",
    "絶対欲しいです🔥",
    "応募させていただきます🙌",
    "当選楽しみにしてます！",
]


def generate_reply(tweet_text: str) -> str:
    """ツイート内容に応じた自然なリプライを生成（公開関数）"""
    text: str = tweet_text.lower()

    if any(w in text for w in ["プレゼント", "キャンペーン", "懸賞", "抽選"]):
        templates: list[str] = [
            "参加します！当たりますように🙏",
            "キャンペーン参加しました✨",
            "ぜひ当たってほしいです😊",
        ]
    elif any(w in text for w in ["感想", "教えて", "コメント", "リプライ"]):
        templates = [
            "素敵な企画ですね！",
            "面白そうです👍",
            "気になってました✨",
        ]
    elif any(w in text for w in ["春", "夏", "秋", "冬", "季節"]):
        season: str = "春" if "春" in text else "夏" if "夏" in text else "秋" if "秋" in text else "冬"
        templates = [
            f"{season}らしい素敵な企画ですね！",
            f"{season}を感じます😊",
        ]
    else:
        templates = _REPLY_TEMPLATES

    return random.choice(templates)


def human_type(page: Any, element: Any, text: str) -> None:
    """人間らしいタイピング（1文字ずつランダム間隔）"""
    import time

    element.focus()
    for char in text:
        page.keyboard.type(char, delay=random.randint(30, 150))
        if random.random() < 0.05:
            time.sleep(random.uniform(0.5, 2))
    time.sleep(random.uniform(0.3, 1.0))
