"""
Kensho Prize Scorer — ツイート本文から賞品価値を推定・スコアリング
v1.0: 金額抽出 + 商品種別認識 + 優先度計算

使い方:
    score_prize(tweet_text: str, rt_count: int) -> dict
    戻り値: {"estimated_value_jpy": int, "items": [...], "priority": 0.0-3.0}
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_CONFIG_CACHE: dict[str, Any] | None = None


def _load_config() -> dict[str, Any]:
    global _CONFIG_CACHE
    cached = _CONFIG_CACHE
    if cached is not None:
        return cached
    cfg_path = Path(__file__).resolve().parents[2] / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        _CONFIG_CACHE = raw.get("prize_scoring", {}) or {}
    else:
        _CONFIG_CACHE = {"enabled": True}
    return _CONFIG_CACHE


def _clean_amount_str(s: str) -> int:
    """'10,000万円' や '1万円' を数値に変換"""
    s = s.replace(",", "").replace(" ", "")
    if "万" in s:
        num_part = s.replace("万円", "").replace("万", "")
        try:
            return int(float(num_part) * 10000)
        except ValueError:
            return 0
    s = s.replace("円相当", "").replace("円分", "").replace("円", "")
    try:
        return int(float(s))
    except ValueError:
        return 0


def score_prize(tweet_text: str, rt_count: int = 0, like_count: int = 0) -> dict:
    """ツイートを解析して賞品スコアを返す

    戻り値:
        estimated_value_jpy: 推定金額（円）
        items: 検出された賞品リスト
        priority: 優先度倍率 (1.0=通常, 3.0=最重要)
    """
    cfg = _load_config()
    if not cfg.get("enabled", True):
        return {"estimated_value_jpy": 0, "items": [], "priority": 1.0}

    text = tweet_text.lower()
    result = {"estimated_value_jpy": 0, "items": [], "priority": 1.0}

    # ── 金額抽出 ──
    max_value = 0
    for pattern in cfg.get("jpy_patterns", []):
        compiled = re.compile(pattern)
        for match in compiled.finditer(tweet_text):
            val = _clean_amount_str(match.group())
            max_value = max(max_value, val)
    result["estimated_value_jpy"] = max_value

    # ── 商品種別検出 ──
    found_items = []
    for category, pattern in [
        ("現金", r"現金"),
        ("Amazonギフト券", r"Amazon.*ギフト券?|ギフト券"),
        ("旅行", r"旅行|宿泊|温泉"),
        ("家電", r"家電|スマホ|タブレット"),
        ("ゲーム機", r"Switch|PS5|ゲーム機"),
        ("商品券", r"商品券|図書券"),
        ("QUOカード", r"QUOカード|クオカード"),
    ]:
        if re.search(pattern, tweet_text, re.IGNORECASE):
            found_items.append(category)
    result["items"] = found_items

    # ── 優先度計算 ──
    multipliers = cfg.get("priority_multipliers", {})
    priority = 1.0

    # 金額ベースの優先度
    if max_value >= 100000:
        priority = max(priority, 2.5)
    elif max_value >= 50000:
        priority = max(priority, 2.0)
    elif max_value >= 10000:
        priority = max(priority, 1.5)
    elif max_value >= 3000:
        priority = max(priority, 1.2)

    # 商品種別ベースの優先度
    for item in found_items:
        for pattern, mult in multipliers.items():
            if re.search(pattern, item, re.IGNORECASE):
                priority = max(priority, mult)

    # RT/いいね数ベースの補正（人気懸賞は信頼性高い）
    total_engagement = rt_count + like_count
    if total_engagement >= 1000:
        priority *= 1.3
    elif total_engagement >= 500:
        priority *= 1.15

    result["priority"] = round(priority, 2)
    return result


def format_prize_info(score: dict) -> str:
    """ダッシュボード表示用に整形"""
    parts = []
    if score["estimated_value_jpy"] > 0:
        parts.append(f"💰 {score['estimated_value_jpy']:,}円相当")
    if score["items"]:
        parts.append("🎁 " + ", ".join(score["items"]))
    priority = score["priority"]
    if priority > 1.5:
        parts.append(f"⭐ 優先度{priority:.1f}")
    elif priority > 1.0:
        parts.append(f"優先度{priority:.1f}")
    return " | ".join(parts) if parts else ""


# CLIテスト用
if __name__ == "__main__":
    tests = [
        "🎊 RT&フォローでAmazonギフト券1万円分が当たる！",
        "【当選】抽選で現金100万円プレゼント！応募はRT&いいね",
        "QUOカード500円分を抽選でプレゼント",
        "新作スマホが当たるキャンペーン実施中",
    ]
    for t in tests:
        s = score_prize(t, rt_count=50)
        print(f"[{s['priority']:.1f}] {t[:40]}... → ¥{s['estimated_value_jpy']:,} {s['items']}")
