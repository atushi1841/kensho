#!/usr/bin/env python3
"""japan-market-data README に Apify Store 外部リンクを追加する。

対象リポジトリ: japan-market-data (https://github.com/atushi1841/japan-market-data)
対象アクター: Apify Store 上 totalRuns>=100 の PPE アクター（上限12本）
追加セクション: "## Apify Store"（既存README末尾に追加、既存セクション破壊なし）

実測データソース: data/apify_actors_detail_snapshot.json（stats.totalRuns）
成功指標: README内 apify.com リンク数 0→>=10
"""
import json
import os
import subprocess
import sys

REPO_LOCAL = "/mnt/d/Project2/japan-market-data"
SNAPSHOT = "/mnt/d/Project2/kensho/data/apify_actors_detail_snapshot.json"
MAX_ACTORS = 12
SECTION_HEADER = "## Apify Store"


def load_actors(path):
    d = json.load(open(path, encoding="utf-8"))
    results = []
    for a in d:
        if not isinstance(a, dict):
            continue
        stats = a.get("stats") or {}
        tr = stats.get("totalRuns", 0) or 0
        name = a.get("name", "")
        aid = a.get("id", "")
        if tr >= 100 and name:
            results.append((tr, name, aid))
    results.sort(key=lambda x: -x[0])
    return results[:MAX_ACTORS]


def actor_url(name):
    return f"https://apify.com/store/actors/{name}"


def build_section(actors):
    lines = [SECTION_HEADER, ""]
    for tr, name, aid in actors:
        lines.append(
            f"- [{name}]({actor_url(name)}) — Apify Store actor (total runs: {tr})"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    actors = load_actors(SNAPSHOT)
    if not actors:
        print("ERROR: totalRuns>=100 のアクターが見つかりません")
        return 1
    print(f"対象アクター {len(actors)} 件:")
    for tr, name, aid in actors:
        print(f"  {tr:>5} runs | {name} | {aid}")

    readme_path = os.path.join(REPO_LOCAL, "README.md")
    if not os.path.exists(readme_path):
        print(f"ERROR: README not found at {readme_path}")
        return 1

    with open(readme_path, encoding="utf-8") as f:
        content = f.read()

    # 既存セクションの重複を防ぐ
    if SECTION_HEADER in content:
        print(f"NOTE: '{SECTION_HEADER}' は既に存在するため、更新します")
        # 既存セクションを削除してから追加
        idx = content.index(SECTION_HEADER)
        content = content[:idx].rstrip() + "\n\n"

    section = build_section(actors)
    new_content = content.rstrip() + "\n\n" + section

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    # 検証: リンク数
    link_count = new_content.count("apify.com/store/actors/")
    print(f"\n追加後 README 内 apify.com リンク数: {link_count}")
    if link_count < 10:
        print(f"WARNING: リンク数が10未満 ({link_count})")
        return 1

    # git add + commit
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "kensho-revenue-worker"
    env["GIT_AUTHOR_EMAIL"] = "kensho-revenue-worker@kensho.local"
    env["GIT_COMMITTER_NAME"] = "kensho-revenue-worker"
    env["GIT_COMMITTER_EMAIL"] = "kensho-revenue-worker@kensho.local"

    subprocess.run(
        ["git", "-C", REPO_LOCAL, "add", "README.md"],
        check=True, env=env,
    )
    subprocess.run(
        ["git", "-C", REPO_LOCAL, "commit", "-m",
         f"docs: add Apify Store links to README ({len(actors)} actors, {link_count} links)"],
        check=True, env=env,
    )
    subprocess.run(
        ["git", "-C", REPO_LOCAL, "push", "origin", "main"],
        check=True, env=env,
    )
    print("git push 完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())