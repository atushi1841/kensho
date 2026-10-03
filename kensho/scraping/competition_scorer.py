"""
Competition Score — 懸賞の競争率スコア算出

低スコア = 低競争率 = 高優先度（先に応募すべき）
高スコア = 高競争率 = 低優先度（後で応募）

スコア要素:
- 応募者数推定（投稿エンゲージメント×加重）
- 賞品価格帯（高額ほど競争率高）
- 締切まで時間（長いほど競争が蓄積）
- 開催形態（全国型 vs 地方共同企画）
"""

from __future__ import annotations

import math
import re
from datetime import datetime
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
        _CONFIG_CACHE = raw.get("competition_scoring", {}) or {}
    else:
        _CONFIG_CACHE = {"enabled": True}
    return _CONFIG_CACHE


# 競争率スコアキー
COMPETITION_SCORE_KEY: str = "competition_score"


def compute_competition_score(item: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """1件の懸賞に対する競争率スコアを計算。

    戻り値:
        {
            "score": float,          # 総合競争率スコア（高い=高競争=低優先度）
            "factors": {             # 各要素のスコア
                "engagement": float, # エンゲージメント要素
                "prize": float,      # 賞品価値要素
                "deadline": float,   # 締切時間要素
                "event_type": float, # 開催形態要素
            },
            "factors_raw": {         # 元データ
                "estimated_applicants": int,
                "prize_value_jpy": int,
                "days_remaining": float,
                "is_national": bool,
            },
        }
    """
    if now is None:
        now = datetime.now()

    cfg = _load_config()
    if not cfg.get("enabled", True):
        return {"score": 50.0, "factors": {"engagement": 50.0, "prize": 50.0, "deadline": 50.0, "event_type": 50.0}, "factors_raw": {}}

    tweet_text: str = item.get("tweet_text", "") or ""
    winner_count: int = int(item.get("winner_count", 0) or 0)
    deadline: str = item.get("deadline", "") or ""
    prize_score: dict = item.get("prize_score", {}) or {}
    prize_value: int = int(prize_score.get("estimated_value_jpy", 0) or 0)
    source: str = item.get("source", "") or ""

    # ── 1. エンゲージメント要素（応募者数推定）──
    # tweet_id が snowflake → 投稿時刻推定（古いほど応募者集まりやすい）
    tweet_id_str: str = item.get("tweet_id", "") or ""
    engagement_score: float = _calc_engagement_score(tweet_text, tweet_id_str, winner_count)

    # ── 2. 賞品価値要素 ─────────────────────────────────
    # 高額賞品ほど競争率が高い
    prize_score_val: float = _calc_prize_score(prize_value, cfg)

    # ── 3. 締切時間要素 ────────────────────────────────
    # 締切までの日数が長いほど競争が蓄積する
    days_remaining: float = _calc_days_remaining(deadline, now)
    deadline_score: float = _calc_deadline_score(days_remaining, cfg)

    # ── 4. 開催形態要素 ────────────────────────────────
    # 全国型 > 地方共同企画（全国型の方が競争率が高い）
    event_type_score: float = _calc_event_type_score(source, tweet_text, cfg)

    # ── 加重合成 ───────────────────────────────────────
    weights = cfg.get("weights", {"engagement": 0.35, "prize": 0.30, "deadline": 0.20, "event_type": 0.15})
    score = (
        engagement_score * weights.get("engagement", 0.35)
        + prize_score_val * weights.get("prize", 0.30)
        + deadline_score * weights.get("deadline", 0.20)
        + event_type_score * weights.get("event_type", 0.15)
    )

    # 0-100 にクリップ
    score = max(0.0, min(100.0, score))

    return {
        "score": round(score, 2),
        "factors": {
            "engagement": round(engagement_score, 2),
            "prize": round(prize_score_val, 2),
            "deadline": round(deadline_score, 2),
            "event_type": round(event_type_score, 2),
        },
        "factors_raw": {
            "estimated_applicants": int(engagement_score * 10),  # 概算
            "prize_value_jpy": prize_value,
            "days_remaining": round(days_remaining, 1),
            "is_national": event_type_score > 50.0,
        },
    }


def _calc_engagement_score(tweet_text: str, tweet_id_str: str, winner_count: int) -> float:
    """エンゲージメントベースの応募者数推定スコア（0-100）."""
    score: float = 50.0  # 基準値

    # winner_count が大きい = 応募しやすい（競争はむしろ低い）
    # ただし、winner_count が多い = 人気の懸賞 = 競争も高い
    # 両側面を考慮: winner_count が増えると競争率も上がるが当選確率も上がる
    # ここでは「応募者数推定」として扱う（高い = 竞争激烈）
    if winner_count > 0:
        # logスケールで圧縮（1000名で上限）
        wc_log = math.log1p(winner_count) / math.log1p(1000.0)
        score += wc_log * 20.0  # 最大 +20

    # ツイートIDが古い = すでに多くの応募者が集まっている可能性
    if tweet_id_str:
        try:
            tweet_ts = _snowflake_to_datetime(int(tweet_id_str))
            age_days = (datetime.now() - tweet_ts).days
            if age_days > 7:
                score += min(15.0, age_days * 0.5)  # 7日以上は優先加成
        except (ValueError, OSError):
            pass

    # ツイート本文のエンゲージメント指標
    # フォロー/RT/いいね の呼び出しが多いほど人気
    follow_count = len(re.findall(r"フォロー", tweet_text))
    rt_count = len(re.findall(r"RT|リポスト", tweet_text, re.IGNORECASE))
    like_count = len(re.findall(r"いいね|高評価", tweet_text, re.IGNORECASE))

    engagement_signals = follow_count + rt_count + like_count
    if engagement_signals >= 5:
        score += 15.0
    elif engagement_signals >= 3:
        score += 10.0
    elif engagement_signals >= 1:
        score += 5.0

    return max(0.0, min(100.0, score))


def _snowflake_to_datetime(snowflake: int) -> datetime:
    """Twitter snowflake ID から的大時刻を復元."""
    _TWITTER_EPOCH_MS = 1288834974657
    ms = (snowflake >> 22) + _TWITTER_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000.0)


def _calc_prize_score(prize_value_jpy: int, cfg: dict[str, Any]) -> float:
    """賞品価値ベースの競争率スコア（0-100）."""
    if prize_value_jpy <= 0:
        return 30.0  # 価値不明は中程度

    thresholds: dict[str, float] = cfg.get("prize_thresholds", {
        "1000000": 100.0,  # 100万円以上
        "500000": 90.0,    # 50万円以上
        "100000": 80.0,    # 10万円以上
        "50000": 70.0,     # 5万円以上
        "10000": 60.0,     # 1万円以上
        "5000": 50.0,      # 5000円以上
        "1000": 40.0,      # 1000円以上
        "0": 30.0,         # それ以外
    })

    # 文字列キーを数値に変換してソート
    sorted_thresholds = sorted(
        [(int(k), v) for k, v in thresholds.items()],
        key=lambda x: -x[0]
    )

    for threshold, score in sorted_thresholds:
        if prize_value_jpy >= threshold:
            return float(score)
    return 30.0


def _calc_days_remaining(deadline: str, now: datetime) -> float:
    """締切までの日数を計算（負値は期限切れ）."""
    if not deadline:
        return 999.0  # 期限不明は長時間と扱う

    try:
        dl_date = datetime.strptime(deadline, "%Y-%m-%d")
        delta = (dl_date.date() - now.date()).days
        return float(delta)
    except ValueError:
        return 999.0


def _calc_deadline_score(days_remaining: float, cfg: dict[str, Any]) -> float:
    """締切時間ベースの競争率スコア（0-100）.

    締切まで時間がない = 競争が低くなる（応募者が集まらない）
    締切まで時間がある = 競争が高くなる（応募者が蓄積する）
    """
    short_threshold = float(cfg.get("short_deadline_threshold_days", 3))

    if days_remaining < 0:
        return 0.0  # 期限切れ
    elif days_remaining <= short_threshold:
        # 短期間 = 競争率低
        return max(0.0, 30.0 * (days_remaining / short_threshold))
    else:
        # 長期間 = 競争率高（logスケールで圧縮）
        max_days = float(cfg.get("max_deadline_days", 30))
        normalized = min(1.0, (days_remaining - short_threshold) / (max_days - short_threshold))
        return 30.0 + 70.0 * normalized


def _calc_event_type_score(source: str, tweet_text: str, cfg: dict[str, Any]) -> float:
    """開催形態ベースの競争率スコア（0-100）.

    全国型 = 高競争率（応募者数が多い）
    地方共同企画 = 低競争率（応募者数が少ない）
    """
    # 地方・地域キーワード
    local_patterns = cfg.get("local_patterns", [
        r"地方", r"地域", r"県", r"市", r"町村",
        r"○○県", r"○○市",  # 具体的な地名
    ])

    is_local = False
    for pattern in local_patterns:
        if re.search(pattern, tweet_text):
            is_local = True
            break

    if is_local:
        return 25.0  # 地方共同企画 = 低競争

    # 企業・ブランド名から全国キャンペーンを判定
    national_indicators = cfg.get("national_indicators", [
        r"全国", r"日本全国", r"日本一",
        r"メーカー", r"ブランド", r"企業",
    ])
    for pattern in national_indicators:
        if re.search(pattern, tweet_text):
            return 70.0  # 全国型 = 高競争

    # ソースによるヒント
    if source in ("knshow", "ken-kaku"):
        # 専門サイトで拾ったものは全国キャンペーン居多
        return 55.0
    elif source in ("kenshouclub", "kenshofan"):
        # ブログ系は地方キャンペーンも混在
        return 45.0

    return 50.0  # デフォルト


def compute_batch_competition_scores(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """バッチ全体に対する競争率スコアを一括計算。

    戻り値:
        {tweet_id: {"score": float, "factors": {...}, ...}}
    """
    result: dict[str, dict[str, Any]] = {}
    now = datetime.now()

    for item in items:
        tweet_id = item.get("tweet_id", "") or item.get("x_url", "") or ""
        if not tweet_id:
            continue

        score_data = compute_competition_score(item, now)
        result[tweet_id] = score_data

    return result


def save_competition_scores(scores: dict[str, dict[str, Any]], output_path: Path) -> None:
    """競争率スコアをJSONに保存."""
    import json
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(scores, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[WARN] competition_score 保存失敗: {e}")


# ── CLI テスト用 ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    test_items = [
        {
            "tweet_text": "フォロー＆RTでAmazonギフト券1万円分が当たる！",
            "winner_count": 5,
            "deadline": "2026-10-10",
            "prize_score": {"estimated_value_jpy": 10000},
            "source": "knshow",
            "tweet_id": "1234567890123456789",
        },
        {
            "tweet_text": "東京のイベントで抽選で商品券が当たる！地方限定",
            "winner_count": 100,
            "deadline": "2026-10-20",
            "prize_score": {"estimated_value_jpy": 5000},
            "source": "kenshouclub",
            "tweet_id": "9876543210987654321",
        },
    ]

    for item in test_items:
        score = compute_competition_score(item)
        print(f"Score: {score['score']:.2f}")
        print(f"  Factors: {score['factors']}")
        print(f"  Raw: {score['factors_raw']}")
        print()
