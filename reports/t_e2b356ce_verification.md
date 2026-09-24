# t_e2b356ce 検証レポート — status/<acct>.json の偽 dead_proxy（1 tick 誤判定）恒久対策

- タスク: t_e2b356ce（assignee: kensho-worker / 実行者: kensho-revenue-worker cron 5e8ec4984bba）
- 実装: `scripts/gen_status_data.py`（根拠行フィルタの是正）＋ `scripts/generate-status.sh`（同一 tick の PROXY-CHECK 完走待ち）
- 背景: run#2 が同一実装を書いたまま `kanban_complete` を呼ばずに終了（rc=0 protocol violation）し、実装が未コミットのまま残っていた。本実行で実装内容を実測検証し、成立に必須だった「順序」の欠落を追加した。

## 1. 何が壊れていたか（実装2ファイルの役割）

1. `scripts/gen_status_data.py` — `data/status/<acct>.json` を書く唯一の経路。根拠行は `logs/auto_*.log` の `[PROXY-CHECK] alive=[..] dead=[..] restored=..` 行。
   - 旧実装は「当日ログの**最後の** PROXY-CHECK 行」を無条件採用 → 生成時刻より前に完走した前 tick の行（死骸）を根拠に `status=dead_proxy` を書いた（2026-09-25 01:15 実測: 実測 alive=[1081,1082,1085] に対し dead=[1081,1084] を記録＝1 tick 偽 dead）。
   - 新実装は「**生成時刻-2分以降**の行のみ採用」。該当行が無ければ `None` を返し、呼出側の `if _row_ts is not None:` が成立しないため **status を書き換えない（前回値保持）**。
2. `scripts/generate-status.sh` — crontab の `*/15` で `kensho-auto-apply.sh` と**同時刻**に起動する。apply tick の PROXY-CHECK は tick 開始の16〜34秒後に書かれるため、待たずに生成すると新実装は常に「該当行なし」となり **status が無音で凍結**する（偽 dead は消えるが proxy 状態監視そのものが死ぬ）。
   - 対策として、tick が動いている間だけ「同一 tick の `[PROXY-CHECK]` 行」が現れるまで最大60秒待つループを追加（20分以上 tick が無い＝パイプライン停止中は即座に諦める）。

## 2. 実測検証

### 2-1. 実ログ再現（本日 24 tick を、その時点のログ内容で新旧比較）

`scratch/replay_filter2.py` で「生成時刻より未来の行は見えない」条件を再現:

- 生成 = tick+5秒（現行 cron と同じ分に起動）: 新実装は **採用0/23 = 一切書かない（凍結）**
- 生成 = tick+40秒（待ちループ後）: 新実装は **採用23/23・一致23/23・不一致0**
- 01:15 tick の事故再現（生成=tick+40s）: 新実装は `採用ts=2026-09-25 01:15:01 alive=[1081, 1082, 1085] dead=[1084]`＝実測と一致（旧挙動の `dead=[1081,1084]` を書かない）

### 2-2. 待ちループの単体検証（`scripts/generate-status.sh` から本文を切り出して実行）

- A: 直近tick(60秒前)に PROXY-CHECK あり → 0.0秒で即抜け
- B: 直近tick(2秒前)に PROXY-CHECK なし → 5.1秒後に追記すると抜ける（＝待機が効いている）
- C: 直近tickが25分前（停止中）→ 0.0秒で即抜け（無駄待ちしない）

### 2-3. 回帰テスト

`pytest -q tests/test_gen_status_proxy_time_filter.py` = **4 passed**（①最新行採用 ②前tick行スキップ ③同tick複数行の最新採用 ④時刻行なしはスキップ）

### 2-4. ライブ検証（2026-09-25 06:15 tick・本番cron経路）

`bash scripts/generate-status.sh` を 06:15:04 に起動 → 待ちループが同一 tick の PROXY-CHECK（06:15:04 行）を検出 → 06:15:26 に status を書き込み、06:15:33 に完了（所要28.5秒）。

- `/tmp/kensho_status_data.json` の `proxy.ts` = **2026-09-25 06:15:04**（tick 開始時刻と一致＝採用した根拠行が**前tick(06:00:04)ではなく同一tick**であることの直接証拠）
- `data/status/*.json`（すべて `updated=2026-09-25T06:15:26`）: atushi16(1081)=alive / kudou(1082)=alive / TankanNotes(1085)=alive / zin20120731(1084)=dead_proxy → **実測 alive=[1081,1082,1085]・dead=[1084] と全一致（不一致0）**
- toushiwatch(1087)=unchecked（当該 tick の PROXY-CHECK 対象外のため）= 期待どおり。inobase1-4 は当日更新のない運用外垢。
- 偽 dead_proxy（alive リストの port を dead_proxy と書く）の同時発生 = **0件**。

## 3. 成功指標への対応

- 偽 dead_proxy の同時発生 0件/24h → 実ログ再現で不一致0（24 tick 分）＋ライブ1 tick で不一致0。**10 tick 連続観察は QA タスクへ委譲**（親子リンク付きで起票）。
- `generate-status.sh` 直後の `atushi16.json.status` が同一 tick の alive 判定と一致 → ライブ検証で実測（1/10。残9回は QA）。
- 既存テスト緑（4 passed）。

## 4. 変更ファイルとロールバック

- `scripts/gen_status_data.py`（フィルタ実装・docstring 是正）
- `scripts/generate-status.sh`（待ちループ追加）
- ロールバック: 上記2ファイルを `git revert <commit>` 相当で戻すだけで旧挙動に復帰（データ形式の変更なし）。

## 5. 申し送り

- 待ちループは「crontab を触らずに順序問題を解く」案。より決定的なのは crontab のステータス生成を `1-59/15 * * * *`（apply tick の1分後）へずらす案で、併用も可能（待ちループは即抜けになるだけ）。
- `posix_spawn` 等の make 系並行作業が `data/status/*.json` を巻き戻す事故が 05:23 に観測された（内容 `updated=04:30:03` のまま mtime だけ 05:23:56）。共有リポジトリでの `git checkout -- <file>` / `git restore` は禁止（兄弟タスクの成果を消す）。

## 6. 追記（2026-09-25 06:45〜07:01・kensho-revenue-worker cron 5e8ec4984bba / commit 6fd250f）

### 6-1. t_e2b356ce: 待ちループ上限 60s → 120s（余裕不足の是正）

- 実測（9/20〜9/25 の6日分）: PROXY-CHECK 所要の最大は **69.5s**（9/24）、9/25 は 57.2s。旧60sは余裕5sしか無く、ポーリング間隔5sと合わせて完走行を取り逃す（＝t_e2b356ce が消したかった「無音凍結」への逆戻り）リスクがあった。
- `scripts/generate-status.sh` に `WAIT_TIMEOUT=120` を定数化（検証ヘルパーが同値を読む＝ドリフト防止）。ループは行が現れ次第即抜けるため、通常 tick の追加コストはゼロ。

### 6-2. t_e2b356ce: 検証ヘルパーの忠実化

- `scripts/verify_status_proxy_same_tick.py`: 生成時刻を「tick+40s 固定」から**待ちループ模擬**（完走+最大5s、WAIT_TIMEOUT で打ち切り）へ変更。WAIT_TIMEOUT は `generate-status.sh` から読む。
- 旧ヘルパーは 03:15 tick（所要57.2s）を「不一致」と誤判定していた（生成=tick+40s では完走前のため）。忠実化後は **28 tick 中 28 一致・不一致0**。

### 6-3. t_e2b356ce: 回帰テストの本番書き込み副作用を除去（実測で発覚）

- `tests/test_gen_status_proxy_time_filter.py` は `from scripts.gen_status_data import _filter_proxy_check_rows` していたため、**テスト実行が生成パイプライン本体を走らせ**、本番 `/tmp/kensho_status_data.json` を書き換えていた（実測 06:49: `proxy.ts` が空に上書き）。回帰テストが本番データを壊す構造は t_e2b356ce の趣旨（偽 status を書かない）と正面から矛盾する。
- 副作用の無い AST 取り出し（`load_filter()`）へ変更。修正後は pytest 前後でパネルの mtime が**不変**（下記エビデンス）。

### 6-4. t_e2b356ce: ライブ検証（07:00 tick・本番cron経路・新スクリプト）

- 07:00 tick の PROXY-CHECK は 16.6s で完走 → 新しい待ちループが同一 tick 行を検出し 07:00:35 に書き込み。
- `proxy.ts=2026-09-25 07:00:06`（tick 開始と一致・前tick 06:45 ではない）、`checked=True`、alive/dead は実測どおり、`data/status/*.json` の updated も 07:00:35 → **不一致0**。

### 6-5. t_e2b356ce 作業中に観測した重大な環境事故（要対応・別カード案件）

- 並行実行中の兄弟 worker（kensho-worker / t_20f49e54）が**共有ワークツリーで `git commit` → `git reset --hard HEAD~1` を繰り返し**、06:46〜06:58 に7回観測（reflog）。t_e2b356ce の成果物 commit 6fd250f も **06:56:08 に HEAD~1 リセットでローカルから消された**（origin には push 済みのため `git fetch && git merge --ff-only origin/main` で復旧）。
- 06:53:59/06:54:07 の連続リセットでは既存コミット ea78e29 も枝から落ち、`scripts/verify_status_proxy_same_tick.py` が作業ツリーから消えた（本カードの作業が消えた回数: 3回）。
- 影響: 兄弟タスクの**未コミット成果とコミットが無予告で消える**。t_e2b356ce の検証は3回やり直しになった。
- 推奨対策: done_guard の検証のように commit/reset を伴う作業は**専用 worktree（`git worktree add`）または scratch clone** で行い、共有ワークツリーでは `reset --hard` / `checkout -- <file>` / `stash` を禁止（t_9db50654 の「stash退避禁止」と同じクラス。恒久ゲート化を推奨）。

## verification_evidence

```
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/cache/scratch/replay_filter2.py
ログ auto_20260925.log: PROXY-CHECK 24件
=== 事故再現（01:15 tick。実測 alive=[1081, 1082, 1085]）===
  生成=tick+40s 新実装: 採用ts=2026-09-25 01:15:01 alive=[1081, 1082, 1085] dead=[1084]
=== 全tick集計（gen_start=生成時刻-2分、その時点のログで判定）===
  生成=tick+5s（現行cron: applyと同時刻起動）  新実装(作業ツリー)  採用= 0 一致= 0 不一致= 0
  生成=tick+40s（ラッパー待機後）             新実装(作業ツリー)  採用=23 一致=23 不一致= 0

$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/cache/scratch/test_tick_wait.py
  a_fresh_with_row:   0.0s rc=0 out='LOOP_DONE'
  b_fresh_no_row_then_append:   5.1s rc=0 out='LOOP_DONE'
  c_stale_25min:   0.0s rc=0 out='LOOP_DONE'
判定: A(<5s)=True B(5〜20s,待機して追記で抜ける)=True C(<5s)=True
RESULT: PASS

$ bash -n scripts/generate-status.sh && echo "bash -n OK"
bash -n OK

$ python3 -m pytest -q tests/test_gen_status_proxy_time_filter.py -p no:cacheprovider
4 passed in 34.66s

$ bash scripts/generate-status.sh
[ok] account_wifi_map.json 更新 (0 fields, ports=[1081, 1082, 1085])
DATA_OK
[OK] 生成完了: /mnt/d/Project2/kensho/kensho-status.html

real	0m28.473s   （起動06:15:04 → 終了06:15:33）

$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/cache/scratch/verify_status_live.py
ログ最終 PROXY-CHECK: tick開始=2026-09-25 06:15:04 alive=[1081, 1082, 1085] dead=[1084]
  TankanNotes      port=1085 status=alive       一致 updated=2026-09-25T06:15:26.724399
  atushi16         port=1081 status=alive       一致 updated=2026-09-25T06:15:26.724399
  kudou            port=1082 status=alive       一致 updated=2026-09-25T06:15:26.724399
  toushiwatch      port=1087 status=unchecked   一致 updated=2026-09-25T06:15:26.724399
  zin20120731      port=1084 status=dead_proxy  一致 updated=2026-09-25T06:15:26.724399
RESULT: PASS

$ python3 -c "import json; p=json.load(open('/tmp/kensho_status_data.json'))['proxy']; print(p['ts'], p['checked'], p['alive'], p['dead'])"
2026-09-25 06:15:04 True ['TankanNotes', 'atushi16', 'kudou'] [['zin20120731', 1084]]
（tick開始時刻と一致＝前tick 06:00:04 ではなく同一 tick の行を採用した直接証拠）

--- 2026-09-25 06:45〜07:01 追記（t_e2b356ce / commit 6fd250f）---

$ python3 scripts/verify_status_proxy_same_tick.py
1) 再現: 28 tick 中 28 一致 / 0 不一致（WAIT_TIMEOUT=120s・打ち切り=0 tick）
2) ログ最終 tick: 2026-09-25 07:00:06 alive=[1081, 1082, 1085] dead=[1084]
   proxy.ts=2026-09-25 07:00:06 → 最終tickと一致
   TankanNotes port=1085 status=alive 一致 / atushi16 port=1081 status=alive 一致 / kudou port=1082 status=alive 一致 / toushiwatch port=1087 status=unchecked 一致 / zin20120731 port=1084 status=dead_proxy 一致
RESULT: PASS

$ python3 -m pytest tests/test_gen_status_proxy_time_filter.py -q -p no:cacheprovider --no-cov
7 passed in 2.42s

$ B=$(stat -c '%Y' /tmp/kensho_status_data.json); pytest 実行; A=$(stat -c '%Y' /tmp/kensho_status_data.json); echo "$B $A"
1790287235 1790287235   （mtime 不変＝テストが本番パネルを書き換えなくなった直接証拠）

$ bash -n scripts/generate-status.sh && echo "bash -n OK"
bash -n OK

$ grep -c "^WAIT_TIMEOUT=120" scripts/generate-status.sh
1

$ grep -nE "PROXY-CHECK" logs/auto_20260925.log | tail -1
2778:[PROXY-CHECK] alive=[1081, 1082, 1085] dead=[1084] restored=0 (16.6s)

$ stat -c '%y %n' /tmp/kensho_status_data.json data/status/atushi16.json
2026-09-25 07:00:35.878562959 +0900 /tmp/kensho_status_data.json
2026-09-25 07:00:35.731889900 +0900 data/status/atushi16.json
（07:00 tick・本番 cron 経路の generate-status.sh が新スクリプトで書き込み＝tick開始 07:00:06 の同一tick行を採用）

$ git log --oneline -1
6fd250f t_e2b356ce: 同一tick待ちを120sへ拡張 + 検証ヘルパー/回帰テストの副作用除去

$ git push origin main
   352d569..6fd250f  main -> main
```
