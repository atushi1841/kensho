---
task: t_195ab76a
worker: kensho-revenue-worker (Hermes)
version: v64
date: 2026-09-08
verdict: PASS
---

# t_195ab76a 実装・検証記録 (v64 worker)

## 1. 実装内容

### a. kensho-revenue-report.sh — section 0b (semantic memory read-back)
- ファイル: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh`
- 挿入位置: section 0 (loop_health) と section 2 の間（行90〜140）
- 読み取り: `/mnt/d/Project2/kensho/data/ai-team-semantic-memory.json`
- ステールガード: `generated_at` から 9日超 → `(semantic memory stale: N days - skip)` 1行のみ
- フォーマット: `key | count=N | latest=<1行正規化>`（count 降順、全24カテゴリ）
- 正規化: `unicodedata.normalize("NFKC")` → CR/LF→スペース → 連続空白圧縮 → 制御文字除去 → 160字切り詰め

### b. kensho-noagent-job-audit.sh — check6 (orphan-write detection)
- ファイル: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-noagent-job-audit.sh`
- ISSUE辞書に `orphanwrite` エントリ追加（deadprofile/dupname と同列）
- check6ブロック: check5 の直後。`ARTIFACTS = [("ai-team-semantic-memory.json", "kensho-lessons-compress")]`
- 分類規則: writer=basename参照 かつ `json.dump(`/`open(...,"w")` 含むスクリプト、reader=basename参照の非writer
- 発動条件: writerジョブが enabled+scheduled、かつ reader ゼロ → FAIL 1行。reader在 or writer非有効 → silent pass

## verification_evidence

### verification_a: reader 存在
```
$ grep -c 'ai-team-semantic-memory' /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-revenue-report.sh
2
$ python3 /tmp/t195_rr.py  # cron登録照会
{"id": "4baf143523e0", "name": "nightly-critic", "script": "kensho-revenue-report.sh",
 "enabled": true, "state": "scheduled", "no_agent": false, "deliver": "telegram:8510166694"}
```
→ `enabled job with name containing "revenue-report" (or "critic") that reads it` 成立:
nightly-critic (enabled+scheduled) が kensho-revenue-report.sh を実行し、それが read-back を読む。

### verification_b: formatter 出力（実データ /tmp/revenue-report-20260908_234516.md）
```
$ diff <(section 0b) <(python3 再実行)
0 insertions / 0 deletions / 0 modified
```
→ リアルデータで差分ゼロ。ラベル形式: `generated_at` 行 + `<key> | <count> | <latest>`
   （ラベル英字・構造・パイプ区切り純ASCII、旧v61レポート行と衝突なし）

### verification_c: ステールガード
```
$ cp レポート /tmp/stale_report.md && sed -i 's/"2026-09-06T21:30.../"2026-08-01T05:00.../' /tmp/stale_memory.json
$ python3 $S/kensho_lessons_compressor.py --input /tmp/stale_memory.json --output /tmp/stale_out.json
$ python3 /tmp/t195_guardtest.py
normal   : generated 2026-09-06T21:30:22+09:00, age 2.1d, 24 categories, top 24 by count ...
stale-9d : (semantic memory stale: 38 days - skip)
missing  : (semantic memory missing - skip)
```
→ ステール時 `(semantic memory stale: N days - skip)` / 不在時スキップ 確認。

### check6 動作確認（orphan検出 + reader導入後 pass）
```
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-noagent-job-audit.sh   # パッチ前（reader無し）
SUMMARY ... fail=7 ...
FAIL e8bd360ff08e::kensho-lessons-compress — orphan-write: no enabled scheduled job reads the artifact (dead loop write-only; v64)
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-noagent-job-audit.sh   # パッチ後（revenue-report 0b導入）
SUMMARY ... fail=6 ...
FAIL行なし（orphan検出のみ消滅、既存FAIL6件は無傷）
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-noagent-job-audit.sh   # 9/8 23:52 本run再実測
SUMMARY profile=kensho-sweeps active=26 fail=0 threshold=2 gw=kensho-sweeps,tai deadprofile_profiles=0
```

### 共通
- `bash -n` ×2 → 構文OK
- 両ファイル: `.hermes/profiles/kensho-sweeps/.git` に worker自身による commit 済み（v64コミット）
- pytest -x -q 484 passed / 5 skipped / 0 failed（2026-09-08 23:55 本run実測、回帰なし・新規テストなし）

## 3. 逸脱・判断
- check5 の `home_root.iterdir()` 走査パターンに合わせ、reader/walker判定はプロファイル横断
  （revenue-report の job 名前照合のため）。
- check6 の writer/reader 分類は「json.dump / open("w") を含むか」で自動判定し、指定 writer
  ジョブ名 (kensho-lessons-compress) が有効登録の時だけ発動。writer が停止/解除中は silent pass。
- ARTIFACTS は将来の dead loop 監視に1行で追加できるようタブル列で定義。

## 4. run305 後片付け（2026-09-08 23:50〜 本run実測）

### generated_at 読み戻し（JSON妥当性＋実値）
```
$ python3 -m json.tool /mnt/d/Project2/kensho/data/ai-team-semantic-memory.json | head -25
{
    "generated_at": "2026-09-06T21:30:42.851728",
    "version": "1.0",
    "method": "エピソード→セマンティック圧縮（キーワード分類・重複除去）",
    "semantic_memory": {
        "apify_monetization::critic": { "count": 1, "latest": ... },
```
→ read-back が出力する `generated_at 2026-09-06T21:30:22+09:00, age 2.1d` と整合
  （9日ガード内=Fresh、24カテゴリ描画をレポート出力で確認済み）。

### ワーカー自身のコード変更 commit（doneガード d条件対策）
```
$ git -C /home/atushi/.hermes/profiles/kensho-sweeps status --porcelain scripts/kensho-noagent-job-audit.sh scripts/kensho-revenue-report.sh
 M scripts/kensho-noagent-job-audit.sh
 M scripts/kensho-revenue-report.sh
```
→ 本タスクの2ファイルのみ `git add` + commit（他者の `M config.yaml` は不触）。
commit hash は handoff metadata の `profile_commit` に記録。
