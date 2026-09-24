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
```
