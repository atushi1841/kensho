"""既存のcollected.jsonの重複をx_urlベースで統合"""

from __future__ import annotations

import json
from collections import Counter

SRC: str = "D:/Project2/kensho/data/collected.json"
DST: str = "D:/Project2/kensho/data/collected_deduped.json"

with open(SRC, encoding="utf-8") as f:
    d: dict = json.load(f)

items: list[dict] = d.get("collected", [])
before: int = len(items)

# x_urlベースで統合
merged_map: dict[str, dict] = {}
for item in items:
    xurl: str = item.get("x_url", "")
    key: str = xurl if xurl else item.get("detail_url", "")
    if key in merged_map:
        old_a: dict = merged_map[key].get("applied", {})
        new_a: dict = item.get("applied", {})
        for k, v in new_a.items():
            if v is not None:
                old_a[k] = v
        if item.get("deadline") and not merged_map[key].get("deadline"):
            merged_map[key]["deadline"] = item["deadline"]
            merged_map[key]["winner_count"] = item.get("winner_count", 0)
        if item.get("keyword_flag", False):
            merged_map[key]["keyword_flag"] = True
    else:
        merged_map[key] = dict(item)

d["collected"] = list(merged_map.values())
after: int = len(d["collected"])

x_urls = [i.get("x_url", "") for i in d["collected"] if "/status/" in i.get("x_url", "").lower()]
dup: dict = {k: v for k, v in Counter(x_urls).items() if v > 1}

print(f"統合前: {before}件")
print(f"統合後: {after}件")
print(f"削減: {before - after}件")
print(f"残りの重複: {len(dup)}件")
print(f"keyword_flag=true: {sum(1 for i in d['collected'] if i.get('keyword_flag', False))}件")

with open(DST, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print(f"保存: {DST}")

# 元ファイルと置き換え
import shutil  # noqa: E402

shutil.move(DST, SRC)
print("置き換え完了")
