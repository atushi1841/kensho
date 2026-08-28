"""simple_rt_backfill_dryrun — 既存poolのsimple_rt_ok未設定をLLM分類し統計のみ出力（書込なし）"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from kensho.scraping.simple_rt_classifier import _load_api_key, classify_texts

data_file = Path(__file__).parent.parent / "data" / "collected.json"
with open(data_file, encoding="utf-8") as f:
    d = json.load(f)
items = d.get("collected", [])
candidates = [
    it
    for it in items
    if not it.get("keyword_flag")
    and (it.get("tweet_text") or "").strip()
    and it.get("tweet_id")
    and not it.get("simple_rt_ok")
]

print(f"collected.json 総件数: {len(items)}")
print(f"未判定候補（keyword_flag=False & tweet_textあり & simple_rt_ok未設定）: {len(candidates)}件")

api_key = _load_api_key()
if not api_key:
    print("ERROR: DEEPSEEK_API_KEY not found")
    sys.exit(1)

# バッチで分類
pairs = [(it["tweet_id"], it["tweet_text"]) for it in candidates]
print(f"分類開始: {len(pairs)}件 → {max(1, len(pairs) // 8)}バッチ")
t0 = time.time()
decisions = classify_texts(pairs, api_key=api_key, batch_size=8, log=None)
elapsed = time.time() - t0

flag_n = sum(1 for v in decisions.values() if v == "FLAG")
ok_n = sum(1 for v in decisions.values() if v == "OK")
unknown_n = sum(1 for v in decisions.values() if v == "UNKNOWN")
missed = len(pairs) - len(decisions)

print("\n=== バックテスト結果（読み取り専用、書き込みなし） ===")
print(f"分類件数: {len(decisions)}/{len(pairs)}（未処理: {missed}）")
print(f"FLAG（追加操作必要）: {flag_n} ({flag_n / max(len(decisions), 1) * 100:.0f}%)")
print(f"OK（フォロー+RTで可）: {ok_n} ({ok_n / max(len(decisions), 1) * 100:.0f}%)")
print(f"UNKNOWN（判定不能）: {unknown_n} ({unknown_n / max(len(decisions), 1) * 100:.0f}%)")
print(f"経過時間: {elapsed:.0f}秒")

# 既に応募済みのFLAG（無駄応募の実害）
applied_waste = 0
for it in candidates:
    dec = decisions.get(it.get("tweet_id"), "UNKNOWN")
    if dec == "FLAG":
        ap = it.get("applied") or {}
        applied = [k for k, v in ap.items() if v]
        if applied:
            applied_waste += 1
            print(f"  無駄応募済み FLAG: {it['tweet_id']} applied_by={applied}")
print(f"無駄応募済み（FLAGなのに応募）: {applied_waste}件")
