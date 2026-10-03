"""scripts/reddit_comment_writer.py — Redditコメント草稿の生成（スレ固有・英語・品質ゲート付き）

なぜテンプレートをやめたか（2026-10-03 実測）:
  旧実装は「決め打ちの文をプールから引いて連結し、長さが足りなければ埋め草で水増しする」
  方式だった。生成物は
    「これ、実はよくある話ですね。 ... 参考になれば幸いです。 参考になれば幸いです。」
  のように同一文を内部で反復し、全草稿が同じ骨格になった。これは Reddit が最も嫌う
  "AI slop" そのもので、投稿すれば削除・ダウンボート・垢への打撃になる。
  → スレ本文を読んでスレ固有の1コメントを書く方式（LLM）に置き換えた。
  LLMが使えないときは**埋め草を作らず、草稿を出さない**（安全側に倒す）。

使い方:
  from reddit_comment_writer import write_comment, quality_check
  text = write_comment(sub="japanlife", title="...", body="...", fact={...})
  # 使えない/品質不足なら None（呼び出し側はその候補をスキップする）
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
PROFILE_ENV = Path("/home/atushi/.hermes/profiles/kensho-sweeps/.env")
API_URL = "http://127.0.0.1:3002/v1/chat/completions"
# ルーターの "auto" は推論重視モデルに当たり、本文を出さずに推論で
# トークンを使い切ることがある（2026-10-03 実測: 1500トークン全消費で本文ゼロ）。
# 先頭から順に試し、実応答が返ったものを使う。
MODEL_CANDIDATES: tuple[str, ...] = ("mistral-small-4", "auto")
MODEL = MODEL_CANDIDATES[0]  # 後方互換（単体テスト用）
TIMEOUT = 90

MIN_CHARS = 100
MAX_CHARS = 400
MIN_ENGLISH_RATIO = 0.85

# AIっぽさ・定型文の検出パターン（1つでも含めば不合格）
BANNED_PATTERNS: tuple[str, ...] = (
    "これ、実はよくある話ですね",
    "ぜひ皆さんの意見も聞かせてください",
    "参考になれば幸いです",
    "もっと詳しく聞きたいことがあれば",
    "何か別の視点があれば教えて下さい",
    "参考までに残しておきます",
    "お力になれれば",
    "great post",
    "thanks for sharing",
    "as an ai",
    "i'm an ai",
    "as a language model",
    "in conclusion",
    "it's worth noting that",
    "delve into",
    "hope this helps",
)

SYSTEM_PROMPT = (
    "You are a long-time Reddit user who comments only when you can add something "
    "specific. You write plain, conversational English in a normal internet tone. "
    "You never sound like a press release, a listicle or a language model."
)


def load_api_key() -> str:
    """環境変数 → profile の .env の順に FREELMAPI_API_KEY を探す。"""
    key = os.environ.get("FREELMAPI_API_KEY", "").strip()
    if key:
        return key
    if PROFILE_ENV.exists():
        for line in PROFILE_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("FREELMAPI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def english_ratio(text: str) -> float:
    """英字以外（日本語・中国語・キリル等）の混入率を測る。1.0 が純英語。"""
    letters = [c for c in text if not c.isspace()]
    if not letters:
        return 0.0
    ascii_letters = [c for c in letters if c.isascii()]
    return len(ascii_letters) / len(letters)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip().lower() for p in parts if len(p.strip()) > 8]


def _extract_comment(raw: str) -> str:
    """思考過程の垂れ流しから、タグ内の本文だけを取り出す。

    ルーター配下のモデルは chat_template_kwargs の enable_thinking=False を無視して
    思考を本文に混ぜて返すことがある（2026-10-03 実測）。タグが無い応答は採用しない。
    """
    m = re.search(r"<comment>(.*?)(?:</comment>|$)", raw, re.S | re.I)
    return m.group(1).strip() if m else ""


# 思考過程・メタ言及の残骸（1つでも含めば不合格）
META_MARKERS: tuple[str, ...] = (
    "we need to", "the user wants", "rules:", "we must", "i need to write",
    "let me write", "here's the comment", "here is the comment",
)


def _numbers(text: str) -> set[str]:
    """本文中の数値トークンを正規化して取り出す（カンマ・通貨記号を落とす）。"""
    out: set[str] = set()
    for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        out.add(m.replace(",", "").rstrip("."))
    return out


def numbers_ok(text: str, allowed: set[str]) -> tuple[bool, str]:
    """本文の数値がすべて許可済み（実データ or スレ題）であることを検査する。

    2026-10-03 実測: 実データ 292件 を 2,920件 と10倍に膨らませ、
    存在しない「29200% larger」を書き足した草稿が生成された。
    「捏造するな」という指示だけでは防げないため、生成後に機械的に検証する。
    """
    for n in _numbers(text):
        if n in allowed:
            continue
        return False, f"unsupported_number:{n}"
    return True, "ok"


def quality_check(text: str, allowed_numbers: set[str] | None = None) -> tuple[bool, str]:
    """投稿してよい品質か。戻り値 (ok, 理由)。"""
    t = (text or "").strip()
    if not t:
        return False, "empty"
    if len(t) < MIN_CHARS:
        return False, f"too_short({len(t)})"
    if len(t) > MAX_CHARS:
        return False, f"too_long({len(t)})"
    low = t.lower()
    for pat in BANNED_PATTERNS:
        if pat in low:
            return False, f"banned_phrase:{pat}"
    for pat in META_MARKERS:
        if pat in low:
            return False, f"meta_marker:{pat}"
    if re.search(r"https?://|www\.", low):
        return False, "contains_link"
    sents = _sentences(t)
    if len(sents) != len(set(sents)):
        return False, "repeated_sentence"
    ratio = english_ratio(t)
    if ratio < MIN_ENGLISH_RATIO:
        return False, f"not_english({ratio:.2f})"
    if not re.search(r"[.!?]", t):
        return False, "no_sentence_end"
    if allowed_numbers is not None:
        ok_num, reason_num = numbers_ok(t, allowed_numbers)
        if not ok_num:
            return False, reason_num
    return True, "ok"


def allowed_numbers_for(title: str, fact: dict[str, Any] | None) -> set[str]:
    """本文で使ってよい数値の集合（スレ題の数値＋実データの値のみ）。"""
    allowed = _numbers(title or "")
    if fact:
        for key in ("median", "p25", "p75", "count", "min", "max"):
            value = fact.get(key)
            if isinstance(value, (int, float)):
                allowed.add(str(int(value)))
    return allowed


def _build_user_prompt(sub: str, title: str, body: str, fact: dict[str, Any] | None) -> str:
    lines = [
        f"Subreddit: r/{sub}",
        f"Post title: {title}",
    ]
    if body:
        lines.append(f"Post text (may be truncated): {body[:900]}")
    lines += [
        "",
        "Write ONE comment replying to this post.",
        "Rules:",
        "- Write in English. Do not use any other language.",
        "- 2-4 sentences, between 120 and 350 characters.",
        "- Refer to something concrete in the post (its subject, not just its mood).",
        "- No links, no mentions of your own products or services, no self-promotion.",
        "- Do not open with praise or filler. Start with the substance.",
        "- Do not mention AI, models, scraping-for-sale, or that you are a bot.",
        "- Avoid emoji. Avoid dashes-as-bullets and list formatting.",
    ]
    if fact:
        sample = fact.get("count")
        p25 = fact.get("p25")
        p75 = fact.get("p75")
        median = fact.get("median")
        lines += [
            "",
            "You personally have this data point from a dataset you collected:",
            f"- topic: {fact.get('topic', 'second-hand Japanese market listings')}",
            f"- median JPY: {median}, 25th pct JPY: {p25}, 75th pct JPY: {p75}, rows: {sample}",
            "If it is genuinely relevant, you may cite ONE of these numbers, phrased "
            "casually, and you must mention the sample size in passing. Never invent a "
            "number that is not listed above. If it is not relevant here, ignore it entirely.",
        ]
    lines += [
        "",
        "Output format:",
        "Your reply must START immediately with <comment> and end with </comment>.",
        "Write nothing before <comment> — no plan, no reasoning, no preamble.",
        "Example of a valid reply:",
        "<comment>I ran into the same thing last year, and what fixed it for me was "
        "asking for the English support line specifically rather than the general one.</comment>",
    ]
    return "\n".join(lines)


def _call_llm(user_prompt: str, temperature: float, model: str = MODEL) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": 1500,
        # 思考モデルが本文を出す前に推論でトークンを使い切るのを防ぐ。
        # 「最初にタグを書く」指示＋閉じタグで停止、の組み合わせで本文を確実に取り出す。
        "stop": ["</comment>"],
        # ルーター配下は thinking モデル。明示的にOFFにしないと reasoning が
        # max_tokens を食い、応答が思考過程の垂れ流しになる（2026-10-03 実測）。
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + load_api_key(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data["choices"][0]["message"]["content"] or "").strip()


def _similar(a: str, b: str) -> float:
    """トークン集合のJaccard類似度。"""
    sa = set(re.findall(r"[a-z0-9']+", a.lower()))
    sb = set(re.findall(r"[a-z0-9']+", b.lower()))
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def write_comment(
    sub: str,
    title: str,
    body: str = "",
    fact: dict[str, Any] | None = None,
    history: list[str] | None = None,
    attempts: int = 3,
) -> str | None:
    """スレ固有のコメントを1つ書く。書けない/品質不足なら None。"""
    if not load_api_key():
        return None
    if not title.strip():
        return None
    history = history or []
    for model in MODEL_CANDIDATES:
        for i in range(attempts):
            temp = [0.85, 1.0, 1.15][min(i, 2)]
            try:
                text = _extract_comment(_call_llm(_build_user_prompt(sub, title, body, fact), temp, model))
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, KeyError, ValueError):
                continue
            text = text.strip().strip('"').strip()
            allowed = allowed_numbers_for(title, fact)
            ok, _reason = quality_check(text, allowed_numbers=allowed)
            if not ok:
                continue
            if any(_similar(text, h) >= 0.4 for h in history[-40:]):
                continue
            return text
    return None
