"""collected.json の None 汚染（応募済みフラグの消滅）を audit.jsonl から復元する。

背景:
  - collector.py が収集時に全アカウントキーを None 初期化
  - state.py の save_collected_safe が None(src) で応募済み日付(dst)を上書きするバグ
    （本修正で解決済みだが、既存データの消滅分を今ここで救済する）
  - audit.jsonl は追記専用で消えない → RT成功(tweet_id) / フォロー成功(screen_name) が真の応募記録

# 復元規則 (安全側):
#  - x_url から tweet_id と screen_name を抽出
#  - audit にその垢が RT成功 → applied[ac]=その日時(follow成功より確実)
#  - audit にフォロー成功があるが RT記録なし → applied[ac]=フォロー日時
#  - follow_state.json にフォロー成功がある → applied[ac]=その日時
#  - applied[ac] がすでに日付strなら触らない（現在値優先）
"""

import argparse
import collections
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

# ── 引数解析 ──
parser = argparse.ArgumentParser(description="collected.json の None 汚染を audit.jsonl から復元する。")
parser.add_argument(
    "--dry-run",
    action="store_true",
    help="復元内容を表示するのみで、実際の書込みは行わない。バックアップも作成しない。",
)
args = parser.parse_args()

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
COLLECTED = DATA / "collected.json"
AUDIT = DATA / "audit.jsonl"
FOLLOW_STATE = DATA / "follow_state.json"
BACKUP_DIR = DATA / "backups"

# バックアップ（--dry-run 時は作成しない）
if args.dry_run:
    print("[DRY-RUN] 書込みなし・バックアップなし（--dry-run）")
else:
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = BACKUP_DIR / f"collected.json.{ts}.bak"
    shutil.copy(COLLECTED, bak)
    print(f"[BACKUP] {bak}")

# 1) audit 読み込み: RT成功 / follow成功 を垢別に
rt_ok = collections.defaultdict(set)  # account -> set(tweet_id)
rt_ts = collections.defaultdict(dict)  # account -> tweet_id -> ISO日時
follow_ok = collections.defaultdict(set)  # account -> set(screen_name)
follow_ts = collections.defaultdict(dict)  # account -> screen_name -> ISO日時
with open(AUDIT, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("status") != "success":
            continue
        ac = r.get("account", "")
        at = r.get("action_type")
        tgt = r.get("target") or ""
        ts_iso = r.get("timestamp", "")
        if not ac or not tgt:
            continue
        if at == "rt":
            rt_ok[ac].add(tgt)
            if ts_iso and tgt not in rt_ts[ac]:
                rt_ts[ac][tgt] = ts_iso
        elif at == "follow":
            follow_ok[ac].add(tgt)
            if ts_iso and tgt not in follow_ts[ac]:
                follow_ts[ac][tgt] = ts_iso

# 2) collected の各ツイートを復元
data = json.loads(COLLECTED.read_text(encoding="utf-8"))
items = data.get("collected", [])
restored = 0
restored_follow_state = 0
skipped_had_date = 0

# 2.5) follow_state.json から垢別のフォロー済み screen_name セットを構築
follow_state_done: dict[str, set[str]] = collections.defaultdict(set)
if FOLLOW_STATE.exists():
    try:
        with FOLLOW_STATE.open(encoding="utf-8") as f:
            fs_data = json.load(f)
        for ac, ac_data in fs_data.items():
            if isinstance(ac_data, dict):
                followed = ac_data.get("followed", {})
                if isinstance(followed, dict):
                    for screen_name, dates in followed.items():
                        if dates:  # 配列に1件以上あれば
                            follow_state_done[ac].add(screen_name)
    except Exception as e:
        print(f"[WARN] follow_state.json 読み込み失敗: {e}", flush=True)
if follow_state_done:
    print(
        f"  [follow_state] {sum(len(v) for v in follow_state_done.values())}垢のフォロー済みアカウント読み込み",
        flush=True,
    )

for it in items:
    x_url = it.get("x_url") or ""
    m = re.search(r"x\.com/([^/]+)/status/(\d+)", x_url)
    if not m:
        continue
    screen, tid = m.group(1), m.group(2)
    ap = it.get("applied")
    if not isinstance(ap, dict):
        it["applied"] = {}
        ap = it["applied"]

    for ac in list(ap.keys()):
        if isinstance(ap.get(ac), str) and not str(ap.get(ac)).startswith("DEFER"):
            skipped_had_date += 1
            continue  # 有効な日付が既にある → 触らない
        # この垢がRT成功してるか
        if ac in rt_ok and tid in rt_ok[ac]:
            rt_ts_val = rt_ts.get(ac, {}).get(tid)
            ap[ac] = rt_ts_val if rt_ts_val else f"{datetime.now().isoformat(timespec='seconds')}Z"  # RTあり=確実に成立
            restored += 1
            continue
        # フォロー成功があり、このツイートの作者をフォロー済み
        if ac in follow_ok and screen in follow_ok[ac]:
            fts = follow_ts.get(ac, {}).get(screen)
            ap[ac] = fts if fts else f"{datetime.now().isoformat(timespec='seconds')}Z"
            restored += 1
            continue
        # ★ 2026-08-28追加: follow_state.json にこの垢のフォロー記録がある
        if ac in follow_state_done and screen in follow_state_done[ac]:
            fts = follow_ts.get(ac, {}).get(screen)
            ap[ac] = fts if fts else f"{datetime.now().isoformat(timespec='seconds')}Z"
            restored += 1
            restored_follow_state += 1

# ★ 2026-09-02追加: 第2パス — applied dict にキー自体が存在しない垢も復元する。
#   これまでの第1パスは `ap.keys()` しか走査せず、キー欠落(エントリ未初期化)の垢は
#   永久に復元されなかった。RT/follow成功を全垢について検証し、キーを追加で補完する。
for it in items:
    x_url = it.get("x_url") or ""
    m = re.search(r"x\.com/([^/]+)/status/(\d+)", x_url)
    if not m:
        continue
    screen, tid = m.group(1), m.group(2)
    ap = it.get("applied")
    if not isinstance(ap, dict):
        it["applied"] = {}
        ap = it["applied"]
    for ac in sorted(set(rt_ok) | set(follow_ok) | set(follow_state_done)):
        if isinstance(ap.get(ac), str) and not str(ap.get(ac)).startswith("DEFER"):
            continue  # 既に日付あり
        if ap.get(ac) is not None:
            continue  # 既に日付/DEFERあり
        # キーが存在しないか None → audit/follow_stateから補完
        if ac in rt_ok and tid in rt_ok[ac]:
            rt_ts_val = rt_ts.get(ac, {}).get(tid)
            ap[ac] = rt_ts_val if rt_ts_val else f"{datetime.now().isoformat(timespec='seconds')}Z"
            restored += 1
        elif ac in follow_ok and screen in follow_ok[ac]:
            fts = follow_ts.get(ac, {}).get(screen)
            ap[ac] = fts if fts else f"{datetime.now().isoformat(timespec='seconds')}Z"
            restored += 1
        elif ac in follow_state_done and screen in follow_state_done[ac]:
            fts = follow_ts.get(ac, {}).get(screen)
            ap[ac] = fts if fts else f"{datetime.now().isoformat(timespec='seconds')}Z"
            restored += 1
            restored_follow_state += 1

if args.dry_run:
    print(
        f"[DRY-RUN] 復元予定 {restored} エントリ "
        f"(うちfollow_state由来 {restored_follow_state}) "
        f"/ 既に日付ありスキップ {skipped_had_date}"
    )
    print("垢別 復元後(予定)内訳:")
    after = data.get("collected", [])
else:
    COLLECTED.write_text(
        json.dumps(data, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(
        f"[DONE] 復元 {restored} エントリ "
        f"(うちfollow_state由来 {restored_follow_state}) "
        f"/ 既に日付ありスキップ {skipped_had_date}"
    )
    print("垢別復元内訳を表示（下部）:")
    after = json.loads(COLLECTED.read_text(encoding="utf-8"))["collected"]
for ac in ["atushi16", "kudou", "zin20120731", "TankanNotes", "inobase1-4"]:
    d = sum(1 for it in after if isinstance((it.get("applied") or {}).get(ac), str))
    n = sum(1 for it in after if (it.get("applied") or {}).get(ac) is None)
    print(f"  {ac:14s} 日付str={d:5d}  None={n:5d}")
