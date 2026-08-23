"""既存 collected.json の x_url 重複エントリを解消するワンオフスクリプト
collector.py の新マージロジックと同一の統合処理を既存データに適用する。
用法: /home/atushi/kensho-venv/bin/python scripts/dedupe_collected.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA = Path(__file__).resolve().parent.parent / "data"
COLLECTED = DATA / "collected.json"


def main() -> None:
    with open(COLLECTED, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("collected", [])
    before = len(items)
    print(f"処理前: {before}件")

    x_url_index = {}
    for item in items:
        xu = item.get("x_url", "")
        if not xu:
            x_url_index.setdefault(f"__no_xurl__{item.get('detail_url', '')}", item)
            continue
        if xu not in x_url_index:
            x_url_index[xu] = item
        else:
            base = x_url_index[xu]
            base_applied = base.get("applied") or {}
            new_applied = item.get("applied") or {}
            merged_applied = {}
            for src in (new_applied, base_applied):
                for k, v in src.items():
                    if v not in (None, ""):
                        merged_applied[k] = v
                    elif k not in merged_applied:
                        merged_applied[k] = v
            base["applied"] = merged_applied
            btxt = base.get("tweet_text", "") or ""
            itxt = item.get("tweet_text", "") or ""
            if len(itxt) > len(btxt):
                base["tweet_text"] = itxt
            if not base.get("deadline") and item.get("deadline"):
                base["deadline"] = item["deadline"]

    merged = list(x_url_index.values())
    after = len(merged)
    print(f"処理後: {after}件 (重複解消 {before - after}件)")

    # バックアップ
    import shutil

    bak = COLLECTED.with_suffix(f".json.{__import__('datetime').datetime.now():%Y%m%d_%H%M%S}.bak")
    shutil.copy(COLLECTED, bak)
    print(f"バックアップ: {bak}")

    data["collected"] = merged
    data["dedupe_applied_at"] = __import__("datetime").datetime.now().isoformat()
    from kensho.utils.backup import safe_save_json

    safe_save_json(COLLECTED, data, "collected.json")
    print("保存完了")


if __name__ == "__main__":
    main()
