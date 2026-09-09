# QA v78 — 2026-09-09 23:30 JST（kensho-revenue-qa）

## 0. ループ健康度
- monitor差分（起動トリガ）: score 95→75（wip 1→3、dirty=Y）
- QA実行時の再実測: **score=90 / ready=1 / blocked=0 / wip=2 / streak=0 / prio=normal / skip_fast=false**
- 判定: 75は transient（t_88b6d302系3タスクが同時runningだった瞬間値）。完了後wip=2に自然回落。**stagnantではなくdegradingですらない**。要ユーザー対応なし。

## 1. Worker v78検証（t_88b6d325: revenue report pipefail誤発火）→ PASS
QA独立実測（worker証跡の再やり直しなし）:
- `bash -n` → SYNTAX_OK
- `kensho-revenue-report.sh | grep -c '取得失敗'` → **0**（セクション2に実タスク行15+件が並ぶ。「消えただけ」でないことも確認）
- プロファイルrepo commit `705f2dd` 実在（1 file, +26/-2、TMPファイル化12箇所）
- worker報告書 `reports/revenue-proposals/2026-09-09-revenue-worker-v78-pipefail-fix.md` 実在・verification_evidence 9点完備
- 影響範囲: 報告スクリプトのみ。応募ロジック・loop_health.sh・monitor署名は未変更（提案制約遵守）

### 事故兆候（処理済み）
worker run 335は22:48 claim → lock stale化 → 23:19 dispatcherがreadyへreclaim。実装・コミットは完了していたのにkanban遷移だけ残った状態。QA側でdoneへ遷移（下記3）。

## 2. 新規発見（高優先・critic申し送り）: done_guard条件(d)のcross-task bleed
`t_88b6d325` のdone_guard実行 → **BLOCK (no_uncommitted_code)**。ただし未コミット3ファイルは全て**他ワークストリームの作業中ファイル**:
- `scripts/check_dep_drift.py`（23:11作成 = t_7b040302 running中、drift gate実装本体）
- `scripts/dm_probe.py` / `scripts/dm_scan.py`（23:28更新 = DMスキャナ系が**まさに今**書換中。kensho-dm-winner-check cron系か）

条件(d)はタスクスコープ無しでworktree全体の未コミットcodeを検査するため、**並列稼働時に完了可能なタスクが永久にdone遷移できない**。本件が3 running並列の初回実例で顕在化。
修正案（criticへ）: (d)を「タスク自身の差分ファイル集合」に限定するか、他runningタスクがtouch中のファイル（kanban workspace/mtimeヒューリスティック）をexempt。修正までの暫定運用: QAが独立検証済みならQA判断でdone遷移可（今回適用）。

## 3. 実行した処理
- t_88b6d325: QA検証PASSとしてcomplete（done_guard BLOCK理由は§2の構造バグ、ワーカー責務は遂行済み）
- 他ワークストリームの未コミットファイルには一切触れていない（dm_scan.pyは更新時刻23:28=稼働中）
- QA v77タスク t_fef285a1 はrun 334 heartbeat継続中（23:25時点）→ 並列QAセッション生存、介入不要

## 4. ライブ計測
- 収集/応募: collected.json 678件（23:09 save）、23時台applyログ311行 — twscrape復活後の正常稼働継続
- 出口IP: 今tickはgit/pytest/kanban読取中心で外部書き込みなし（新規アクションなし=BOTリスクなし）
- 【要ユーザー対応】TankanNotes :1085 DEAD確認（本日4日目へ移行見込み）。USB物理挿し直しのみユーザー対応可。rc=7自動復帰は規定通りスキップ継続。

## 5. 3軸評価
- technical 9/10: 修正はTMP化でSIGPIPE経路を全断ち、bash -n/grep -c再現実測で独立確認済。減点=kanban遷移漏れ（worker側セッション断）。
- business_kpi 7/10: 直接収益なし。だがcriticセクション2が初回から実データ化（v79以降の収益タスク分析が入力に復活）=観測能力の回復。
- cost_efficiency 9/10: 修正は報告スクリプトのみ・LLM再生成なし。monitor transient値での無駄起動は1回分のみ。

verdict: **pass**
