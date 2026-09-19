"""X投稿リンクの無料読み取りモジュール（fxtwitter API + oEmbed フォールバック）

ユーザーがHermesにX投稿リンクを貼った時に、内容（本文・投稿者・日時・統計・メディア等）を
完全無料で自動読み取りする仕組み。

データソース（両方とも完全無料・APIキー不要）:
1. **fxtwitter API** (`api.fxtwitter.com`) — 本文・作者詳細・統計（いいね/RT/閲覧）・メディアを完全取得
2. **X公式oEmbed** (`publish.twitter.com/oembed`) — fxtwitter失敗時のフォールバック

機能:
1. URL正規化（不要パラメータ除去）
2. fxtwitter APIによる投稿詳細の無料取得（プライマリ）
3. oEmbed APIによるフォールバック取得
4. 本文・ハッシュタグ・メンション・統計・メディアの抽出
5. 人間が読めるMarkdown形式への整形
"""

from __future__ import annotations

import html as html_module
import json
import re
import ssl
import urllib.parse
import urllib.request
from typing import Any

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_CTX = ssl.create_default_context()


def is_x_tweet_url(url: str) -> bool:
    """X/Twitterの投稿URLか判定（アカウントページや特殊ページは除外）"""
    url_lower: str = url.lower()
    if "x.com" not in url_lower and "twitter.com" not in url_lower:
        return False
    if "/status/" not in url_lower:
        return False
    return True


def clean_x_url(url: str) -> str:
    """トラッキングパラメータ（?s=...&t=...）を除去したクリーンURLを返す"""
    return url.split("?")[0].split("#")[0]


def extract_tweet_id(url: str) -> str | None:
    """X投稿URLからtweet_idを抽出"""
    clean_url = clean_x_url(url)
    match = re.search(r"(?:x\.com|twitter\.com)/[^/]+/status/(\d+)", clean_url)
    return match.group(1) if match else None


def extract_username(url: str) -> str | None:
    """X投稿URLからユーザー名を抽出"""
    clean_url = clean_x_url(url)
    match = re.search(r"(?:x\.com|twitter\.com)/([^/]+)/status/\d+", clean_url)
    if not match:
        return None
    name = match.group(1)
    if name in ("home", "search", "explore", "settings", "messages", "notifications", "login"):
        return None
    return name


def _fetch_json(url: str, timeout: float = 8.0) -> dict[str, Any] | None:
    """JSON APIを取得する（fxtwitter用）"""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _read_fxtwitter(clean_url: str, username: str, tweet_id: str, timeout: float = 8.0) -> dict[str, Any] | None:
    """fxtwitter APIから完全な投稿情報を取得（プライマリ）"""
    api_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"
    data = _fetch_json(api_url, timeout)
    if not data or data.get("code") != 200:
        return None

    tweet = data.get("tweet") or {}
    author = tweet.get("author") or {}

    # メディア情報の抽出
    media = tweet.get("media")
    media_info: list[str] = []
    if media:
        if images := media.get("photos"):
            media_info = [img.get("url", "") for img in images]
        if video := media.get("video"):
            media_info.append(video.get("url", ""))

    return {
        "status": "success",
        "source": "fxtwitter",
        "url": clean_url,
        "tweet_id": tweet_id,
        "username": username,
        "author_name": author.get("name") or username,
        "author_url": f"https://x.com/{username}",
        "text": tweet.get("text", ""),
        "created_at": tweet.get("created_at"),
        "hashtags": re.findall(r"#(\w+)", tweet.get("text", "")),
        "mentions": re.findall(r"@(\w+)", tweet.get("text", "")),
        "expanded_links": {},
        "stats": {
            "replies": tweet.get("replies"),
            "retweets": tweet.get("retweets"),
            "likes": tweet.get("likes"),
            "bookmarks": tweet.get("bookmarks"),
            "views": tweet.get("views"),
        },
        "author_bio": author.get("description"),
        "followers": author.get("followers"),
        "media_urls": media_info,
        "html": "",
    }


def _read_oembed(clean_url: str, username: str, tweet_id: str, timeout: float = 8.0) -> dict[str, Any] | None:
    """X公式oEmbed APIから投稿情報を取得（フォールバック）"""
    oembed_url = "https://publish.twitter.com/oembed" + f"?url={urllib.parse.quote(clean_url)}"
    try:
        req = urllib.request.Request(oembed_url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None

    html_str = data.get("html", "")
    p_match = re.search(r"<p[^>]*>(.*?)</p>", html_str, re.DOTALL)
    text = re.sub(r"<[^>]+>", "", p_match.group(1)) if p_match else ""
    text = html_module.unescape(text).strip()

    date_match = re.search(r">([A-Z][a-z]+ \d+, \d{4})<", html_str)
    created_at = date_match.group(1) if date_match else None

    return {
        "status": "success",
        "source": "oembed",
        "url": clean_url,
        "tweet_id": tweet_id,
        "username": username,
        "author_name": data.get("author_name") or username,
        "author_url": data.get("author_url"),
        "text": text,
        "created_at": created_at,
        "hashtags": re.findall(r"#(\w+)", text),
        "mentions": re.findall(r"@(\w+)", text),
        "expanded_links": {},
        "stats": {},
        "author_bio": None,
        "followers": None,
        "media_urls": [],
        "html": html_str,
    }


def read_x_tweet(url: str, timeout: float = 8.0) -> dict[str, Any]:
    """X投稿リンクを無料で読み取る（fxtwitter優先、失敗時oEmbed）

    Args:
        url: X投稿URL（例: https://x.com/username/status/123456789）
        timeout: APIリクエストのタイムアウト秒数

    Returns:
        status: "success" | "error"
        url, tweet_id, username, author_name, author_url: 基本情報
        text: 本文, created_at: 投稿日時
        hashtags, mentions: ハッシュタグ・メンション
        stats: {replies, retweets, likes, bookmarks, views}
        media_urls: 画像・動画URL一覧
        author_bio, followers: 作者プロフィール
        error: エラー内容（失敗時）
    """
    if not is_x_tweet_url(url):
        return {
            "status": "error",
            "url": url,
            "error": "有効なX投稿URLではありません（例: https://x.com/username/status/123456789）",
        }

    clean_url = clean_x_url(url)
    tweet_id = extract_tweet_id(url)
    username = extract_username(url)

    # プライマリ: fxtwitter
    result = _read_fxtwitter(clean_url, username or "", tweet_id or "", timeout)
    if result:
        return result

    # フォールバック: oEmbed
    result = _read_oembed(clean_url, username or "", tweet_id or "", timeout)
    if result:
        return result

    return {
        "status": "error",
        "url": clean_url,
        "tweet_id": tweet_id,
        "username": username,
        "error": "投稿情報を取得できませんでした（両APIとも接続失敗・公開投稿でない可能性）",
    }


def format_tweet_summary(tweet_info: dict[str, Any]) -> str:
    """読み取り結果を人間が読みやすいJapanese Markdown形式に整形する"""
    if tweet_info.get("status") == "error":
        return "❌ エラー: " + str(tweet_info.get("error"))

    author_name = tweet_info.get("author_name", "不明")
    username = tweet_info.get("username", "不明")
    created_at = tweet_info.get("created_at", "日時不明")
    text = tweet_info.get("text", "（本文なし）").strip()
    hashtags = tweet_info.get("hashtags", []) or []
    stats = tweet_info.get("stats", {}) or {}
    media_urls = tweet_info.get("media_urls", []) or []
    author_bio = tweet_info.get("author_bio")
    followers = tweet_info.get("followers")

    def fmt_count(n):
        if n is None:
            return "-"
        return f"{n:,}"

    lines = [
        f"**👤 投稿者**: {author_name} (@{username})",
        f"**📅 投稿日時**: {created_at}",
        f"**🔗 URL**: {tweet_info.get('url')}",
        "",
        "**📝 本文**:",
    ]

    if text:
        lines.append("> " + text.replace("\n", "\n> "))
    else:
        lines.append("> （テキストなし・画像/リンク投稿）")

    if hashtags:
        lines.append("")
        lines.append("**🏷️ ハッシュタグ**: " + ", ".join("#" + h for h in hashtags))

    # 統計情報
    if any(stats.values()):
        lines.append("")
        lines.append("**📊 エンゲージメント**:")
        lines.append(
            f"- 💬 返信 {fmt_count(stats.get('replies'))}  /  🔁 RT {fmt_count(stats.get('retweets'))}  /  ❤️ いいね {fmt_count(stats.get('likes'))}"
        )
        lines.append(
            f"- 🔖 ブックマーク {fmt_count(stats.get('bookmarks'))}  /  👁️ 閲覧 {fmt_count(stats.get('views'))}"
        )

    # メディア情報
    if media_urls:
        lines.append("")
        lines.append("**🖼️ 添付メディア**:")
        for m in media_urls[:5]:
            lines.append(f"- {m}")

    # 作者プロフィール
    if author_bio:
        lines.append("")
        lines.append(f"**👤 プロフィール**: {author_bio[:120]}")
        if followers is not None:
            lines.append(f"  フォロワー: {fmt_count(followers)}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sample = sys.argv[1] if len(sys.argv) > 1 else "https://x.com/huku_ryu/status/2097242538839093742"
    res = read_x_tweet(sample)
    print(format_tweet_summary(res))
