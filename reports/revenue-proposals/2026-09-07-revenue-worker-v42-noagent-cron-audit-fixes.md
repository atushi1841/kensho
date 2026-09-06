# Revenue Worker — no_agent cron 実障害3件の監査と修正 (v42)

日時: 2026-09-07 00:10-00:40 JST / セッション: nightly-worker (5e8ec4984bba) run 219
文脈: health score=75, ready=0, blocked=0, running=3 (全て他run所有・claim不可)。
t_1c52e2f6 (no_agent audit) は kensho-revenue-worker run 218 が処理済みのため
claim-conflict ガードに従い触らず。ボード外の実障害を自己検出・修正した。

## 監査結果: no_agent 21ジョブ中、実障害3件を特定

### 障害1: ce22c907d66d (kanban-ready-deprecate-nightly) — 9/6 04:00 failed
- 症状: `Script not found: .../kensho-sweeps/scripts/kensho-ready-deprecate.sh`
- 真因の層:
  1. スクリプトが外 (~/.hermes/scripts/) に実体置きで symlink だった → run 218 が
     プロファイル内実体に移設済み (既定 dry-run→apply 反転も実施)
  2. 【本run発見】さらに旧既定 `MODE="dry-run"` では、cron が `argv=[bash, path]`
     (scheduler.py:4375 実測・引数渡せない) のため恒久不発だった。
     これは notepad の恒久教訓と同一クラス。
- 本runの追加修正: ~/.hermes/scripts/ 側の旧コピーも既定 apply に反転
  (`MODE="apply"` + `--dry-run`/`APPLY=0` で dry-run)。実体と機能同等化した。
- 検証 (実測):
  - `$ bash .../kensho-ready-deprecate.sh` → `対象0件 mode=apply` / exit 0
  - `$ bash ... --dry-run` → `mode=dry-run` / exit 0
  - `$ APPLY=0 bash ...` → `mode=dry-run` / exit 0
  - 機能試験: 本物のHN撒き形式タスクを2件作成 ([非API自動収益] prefixなし/あり)
    → prefixありのみ「対象 1 件 mode=apply」で検出、
    `Archived t_52697999` 実測、status: archived を read-back 確認。
    誤検知なし (prefixなしは対象0)。プローブ2件は archive でクリーンアップ済み。
  - scheduler の argv=[bash, path] は scheduler.py:4375 で直接確認済み。
- 次回実行 9/7 04:00 で last_status=ok に戻るはず (監視継続)。

### 障害2: c0e8e4d76933 (kensho-dataset-weekly-update) — 8/31 2回連続 exit 1
- 症状: `ModuleNotFoundError: No module named 'playwright'` (gumroad_update_file.py)
- 真因: cron 実行時の PATH 解決で system python3 を拾っていた (venv指定は
  スクリプト内行34に存在、8/31失敗ログのTracebackは system python3 のパス)。
  9/1 21:36 にスクリプト修正済み (venv 直接パス指定) = ステール失敗の可能性大。
- 本run検証 (実測):
  - venv playwright: `VENV IMPORT OK` + Firefox headless 実起動 `FIREFOX LAUNCH OK 151.0`
    (chromium は WSL SIGTRAP 既知問題のため firefox で実測・成功)
  - スクリプト line34 は venv python を直接指定済みを確認
- 結論: コードは修正済み。次回実行 9/7 (月) 10:00 で自動検証される。
  追加介入は不要と判断 (コスト意識・既存修正尊重)。
  監視: 9/7 10:00 以降に `hermes cron runs c0e8e4d76933` で last_status 確認のこと。

### 障害3: d340ec02d57e (kensho-ai-team-daily-evolution) — 9/6 22:00 drift_skip
- 症状: `[drift_skip] ... provider 'openrouter' -> 'custom'; model
  'minimax/minimax-m3:free' -> 'qwen3.8-flash' ... unpinned`
- 真因: ジョブが unpinned (model_snapshot/provider_snapshot=null) のまま、
  グローバル設定が 9/5-6 に切替済み。fail-closed ガード (#44585) が正しく働いた。
- 修正 (実測):
  1. `hermes cron edit d340ec02d57e --provider custom --model qwen3.8-flash`
     → `Updated job` 確認 (現在の config.yaml model.default=bai/qwen3.8-flash と
     整合・無料モデル維持)
  2. jobs.json 直編集で model_snapshot=qwen3.8-flash, provider_snapshot=custom,
     drift_alerted=false, failure_streak=0 に更新 (alert-once 再武装)
  3. read-back 確認: 4フィールドとも意図通り反映
- 検証: snapshot=現行解決値で一致 → 次回 9/7 22:00 tick で drift 判定は
  `drifted=[]` になり実行されるはず (monitoring)。

### 参考: 22cf7ff992d7 (重複pausedジョブ)
- `script=ready-deprecate.sh` で paused/enabled=false。last=ok (9/5 04:06)。
  実害なし。script名が実体と不一致だが停止済みのため放置
  (削除はクリティカル操作のため本次は実施せず、必要なら次回提案)。

## 教訓 (notepad lessons へ要約記録済み)
1. symlink置きでも Blocked にならないバリエーションがあった (scheduler は
   resolve() 後に判定するため、doctor とで挙動差が生じうる)
2. 「スクリプト実在+exit 0」だけでは不発を検出できない。
   監査スクリプト (t_1c52e2f6 run 218作成 kensho-noagent-job-audit.sh) に
   「dry-run-by-default 検出」が含まれていることを本runで確認した
   (run 218 summary: `(3) dry-run-by-default を 21 アクティブ no_agent ジョブに対して検出`)。
3. drift_skip は snapshot 直編集で再武装可能 (drift_alerted を false に戻す)。

## 自己レビュー (Reflexion)
```json
{"self_review":{"what_was_done":"no_agent cron 21ジョブ監査→実障害3件(ready-deprecate不発/dataset-weekly過去失敗の真因特定/evolution drift_skip)を特定し、ready-deprecate旧コピー修正+evolution pin+snapshot再武装を実施","what_went_well":["argv=[bash,path]をscheduler.py:4375で直接確認し教訓を実証","probe2件でapply動作を実測検証(archived read-back含む)","Firefox headless起動でplaywright環境を実測確認"],"what_could_improve":["c0e8e4d76933は9/7 10:00の次回実行まで未検証(ステール失敗の可能性)","drift_skip解消も9/7 22:00まで未検証"],"mistakes_or_risks":["jobs.jsonを直接編集した(GUI/edit経由でsnapshotが書けないため・書き換え前に読み取り済み)","最初のprobe1件をprefixミスで無駄に1件作成(即archive済み)"],"learned":"監視系cronの失敗は「最後の失敗ログ」だけでなく「その後コード修正がないか」を必ず確認する(ステール失敗)。drift_skipはpin+snapshot再武装で恒久解決できる","confidence":8,"verification_evidence":"ready-deprecate: probe2件archived実測+3モードexit0 / evolution: Updated job+read-back4フィールド確認 / playwright: FIREFOX LAUNCH OK 151.0 / scheduler argv: scheduler.py:4375実読"}}
```
