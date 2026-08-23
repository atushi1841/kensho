"""
Kensho Account Discovery — 関連懸賞アカウントの自動発見
v1.0: collected.jsonから懸賞垢を抽出 + Web検索で新規発見

使い方:
    python -m kensho.scraping.account_discovery  [--search] [--limit N]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from kensho.core.config import load as load_config


def extract_handles_from_collected(collected_path: str | None = None) -> list[dict[str, Any]]:
    """collected.json から全 x_url のスクリーンネームを抽出・集計"""
    cfg = load_config()
    data_dir = Path(cfg["general"]["project_dir"]) / "data"
    collected_path = collected_path or str(data_dir / "collected.json")

    try:
        with open(collected_path, encoding="utf-8") as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[Discovery] collected.json 読み込みエラー: {e}")
        return []

    # collected.json構造: {"collected": [{...}]}
    items = raw.get("collected", []) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []

    handle_counter: Counter = Counter()
    handle_details: dict[str, dict] = {}

    x_url_pattern = re.compile(r"https?://(?:www\.)?(?:x\.com|twitter\.com)/([A-Za-z0-9_]+)")

    for item in items:
        if not isinstance(item, dict):
            continue
        x_url = item.get("x_url", "")
        if not x_url:
            continue
        m = x_url_pattern.search(x_url)
        if not m:
            continue
        handle = m.group(1).lower()

        # 自アカウントは除外
        if handle in ("atushi16", "kudou", "chugakujuken", "zin20120731", "tankan"):
            continue

        handle_counter[handle] += 1

        # 最初に見つけたURLを保存
        if handle not in handle_details:
            handle_details[handle] = {
                "handle": handle,
                "count": 0,
                "sample_urls": [],
            }

        if len(handle_details[handle]["sample_urls"]) < 3:
            handle_details[handle]["sample_urls"].append(x_url)

    # 集計結果の更新
    for handle in handle_details:
        handle_details[handle]["count"] = handle_counter[handle]

    # 出現回数降順でソート
    sorted_handles = sorted(handle_details.values(), key=lambda x: -x["count"])

    return sorted_handles


def search_new_accounts(limit: int = 20) -> list[dict[str, Any]]:
    """Web検索で新規懸賞アカウントを発見"""
    from kensho.tools.web_search import web_search

    queries = [
        "プレゼント企画 X 抽選 フォロー RT いいね",
        "懸賞 プレゼント RT フォロー 募集中 X",
        "プレゼントキャンペーン X 抽選 2026",
        "フォロー＆RT プレゼント 募集中",
        "抽選でプレゼント X 懸賞 アカウント",
    ]

    seen = set()
    results = []

    for query in queries:
        print(f"[Discovery] 検索中: {query[:40]}...")
        try:
            data = web_search(query, limit=5)
            snippets = data.get("data", {}).get("web", [])
            for s in snippets:
                url = s.get("url", "")
                title = s.get("title", "")
                desc = s.get("description", "")

                # x.com/twitter.com のURLからハンドル抽出
                m = re.search(
                    r"https?://(?:www\.)?(?:x\.com|twitter\.com)/"
                    r"([A-Za-z0-9_]+)",
                    url,
                )
                if m:
                    handle = m.group(1).lower()
                    if handle not in seen and handle not in (
                        "atushi16",
                        "kudou",
                        "chugakujuken",
                        "zin20120731",
                        "tankan",
                        "home",
                        "explore",
                        "notifications",
                        "messages",
                        "compose",
                        "search",
                        "settings",
                        "i",
                        "intent",
                        "hashtag",
                        "share",
                    ):
                        seen.add(handle)
                        results.append({
                            "handle": handle,
                            "source": "web_search",
                            "url": url,
                            "title": title,
                            "snippet": desc[:120] if desc else "",
                        })
                        if len(results) >= limit:
                            return results
        except Exception as e:
            print(f"  [SKIP] 検索エラー: {e}")
            continue

    return results


def discover_accounts(search: bool = False, limit: int = 30) -> dict[str, Any]:
    """関連アカウント発見メイン"""
    cfg = load_config()
    data_dir = Path(cfg["general"]["project_dir"]) / "data"

    # 1. collected.json から既知アカウント抽出
    print("[Discovery] collected.json からハンドル抽出中...")
    known = extract_handles_from_collected()
    print(f"  抽出件数: {len(known)} アカウント")

    # 2. 必要に応じてWeb検索
    new_accounts = []
    if search:
        print("[Discovery] Web検索で新規発見中...")
        new_accounts = search_new_accounts(limit)
        print(f"  新規発見: {len(new_accounts)} アカウント")

    # 3. 結果を統合
    result = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "known_accounts": known[:50],  # 出現頻度TOP50
        "new_accounts": new_accounts,
        "stats": {
            "total_known": len(known),
            "total_distinct_handles": len(set(a["handle"] for a in known)),
            "new_discovered": len(new_accounts),
        },
    }

    # 4. ファイル保存
    output_path = data_dir / "discovered_accounts.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[Discovery] 保存完了: {output_path}")

    # 5. サマリー表示
    print("\n【発見サマリー】")
    print(f"  既知アカウント: {result['stats']['total_distinct_handles']} 種")
    print(f"  Web検索発見: {result['stats']['new_discovered']} 件")
    print("\n【トップ10 懸賞アカウント】")
    for i, acct in enumerate(known[:10], 1):
        print(f"  {i:2d}. @{acct['handle']:25s} {acct['count']:4d}回")

    return result


if __name__ == "__main__":
    search_flag = "--search" in sys.argv or "-s" in sys.argv
    limit = 30
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
    discover_accounts(search=search_flag, limit=limit)
