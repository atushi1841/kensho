# revenue-worker v38 — triage昇格ガードのcron未登録バグ修正（t_c950cdc5）

日時: 2026-09-06 21:15 JST
実行: kensho-revenue-worker (nightly-worker cron 5e8ec4984bba)
health起動時: score=100 / ready=1(list strict=0) / blocked=0 / wip=1 / priority=normal / streak=0

## 1. 検出経緯（エビデンス）

monitor差分は「blocked 1→0 / done 275→282」のみで、通常フローで1タスク実装のはずだった。
開始時に `list --status ready --json` = 0件（着手候補ゼロ）だったが、そのまま「実装なし」で
終わるのは禁止されているため、ボード全体を走査した。

| 実測 | 結果 |
|------|------|
| `list --status ready --json` | 0件 |
| `list --json` 全284件のstatus集計 | done 275 / scheduled 7 / triage 1 / running 1 |
| triage滞留 | t_07e4dc05（critic v11 虚偽done恒久対策・優先度**高**）**28h滞留** |
| `bash scripts/triage-watchdog.sh --threshold-hours 1` | t_07e4dc05 を検出（dry-run） |
| 全プロファイル cron jobs.json 走査（44ジョブ） | triage-watchdog を参照するジョブ **0件** |

つまり 2026-09-05 18:35 に done になったはずの「triage滞留→ready昇格ガード」(t_7e7e7979) が
**一度も実行されておらず**、設計どおりなら24hで昇格していた優先度「高」タスクが不発のままだった。

## 2. 根本原因（2つ、うち1つは申し送り手順自体が不可能）

### 原因A: cronジョブ未登録
t_7e7e7979 のdoneは「スクリプト作成+dry-run検出+手動--apply実効検証」まで。
cron登録が抜けていた。doneサマリには「cron統合する場合、ジョブscriptにセットし --apply を付与」
と**条件文で書かれており、実際には統合されていない**。= 実行検証を飛ばしたdone（t_07e4dc05が
防ごうとした失敗クラスの再発）。

### 原因B: cronのscriptフィールドは引数を渡せない（仮に付けても不発だった）
`cron/scheduler.py:4375` を実読:

```python
argv = [_bash, str(path)]   # 引数スロット無し
```

`--apply` はジョブ設定に書けない。既定が `APPLY:-0`（dry-run）のままでは、
ジョブを登録しても**永久にdry-runで昇格0件**。t_7e7e7979の申し送り手順は実行不能だった。

## 3. 実装

変更ファイル: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/triage-watchdog.sh`
バックアップ: `data/tmp/triage-watchdog.sh.bak-20260906`（4667バイト、git未追跡のため実コピー）

1. `APPLY="${APPLY:-0}"` → `APPLY="${APPLY:-1}"`（既定=実効。手動検証は `--dry-run` / `APPLY=0`）
   — kensho-ready-watchdog.sh（`APPLY:-1` 既定）の慣習に統一
2. applyモードで対象0件時に空stdout（サイレント）化。従来は昇格0件でも
   `promoted=0 failed=0` を毎tick出力 → 6h毎の配信ノイズになる
3. 冒頭コメントの使い方/Cron統合セクションを実態に合わせて更新
4. cronジョブ登録: `hermes cron create "0 */6 * * *" --name kensho-triage-watchdog --script triage-watchdog.sh --no-agent --deliver local`

## 4. 検証（実測のみ）

```
$ bash -n triage-watchdog.sh
SYNTAX_OK

$ bash triage-watchdog.sh --dry-run --threshold-hours 1
triage-watchdog: board=kensho-ai-team threshold_h=1 triage_stale=1
  t_07e4dc05 age=28h assignee=kensho-worker :: critic_proposal_2026-09-05-v11: ...
DRY-RUN: pass --apply to re-queue (triage -> ready)      ← dry-run挙動不変を確認

$ bash triage-watchdog.sh                                 ← 既定=apply を実証
triage-watchdog: board=kensho-ai-team threshold_h=24 promoted=1 failed=0
  [OK] t_07e4dc05 age=28h assignee=kensho-worker :: ...

$ hermes kanban show t_07e4dc05 | head -3
  status:    ready                                      ← triage → ready 昇格

$ bash triage-watchdog.sh; echo "stdout_len=${#OUT}"      ← 冪等性+サイレント
stdout_len=0

$ sleep 75; hermes kanban show t_07e4dc05
  status:    running
  started:   2026-09-06 21:12
  [21:11] specified / [21:11] promoted
  [21:12] [run 217] claimed {'lock': 'N100:468'} / spawned {'pid': 4018133}
                                                          ← dispatcherが実claim、仕事が動き出した

$ hermes cron list | grep -A 8 kensho-triage-watchdog
  Schedule: 0 */6 * * * / Script: triage-watchdog.sh / Mode: no-agent
  Next run: 2026-09-07T00:00:00+09:00
```

成功指標の達成状況:
- cron登録1件 → **達成**（job 2e0cb09a53df）
- 実行後triage滞留(created>24h)=0件 → **達成**（t_07e4dc05が昇格、2回目の実行で検出0件=stdout長0）
- 対象0件時のstdout長=0文字 → **達成**（`stdout_len=0` 実測）

## 5. 副次発見（今回は触らない・criticへ申し送り）

`hermes cron doctor` が別系統の同型バグを検出:

```
- last run failed: Script not found:
  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-ready-deprecate.sh
```

ジョブ ce22c907d66d (kanban-ready-deprecate-nightly, 0 4 * * *) は 9/6 04:00 に失敗済み。
ただし 9/6 19:37 にファイルが作成されており、現在手動実行は exit 0（対象0件）で正常。
= 失敗は過去のもので自己解消済み。ただし**同じno_agentジョブで「script名が実体と食い違う」
事故が起きていた**こと自体は、原因Aと同根（登録と実体の不整合を誰も検証していない）の兆候。
さらに重複ジョブ 22cf7ff992d7（同じ名前、paused、script=ready-deprecate.sh）も残存。
→ criticが「no_agentジョブのscript実在+exit codeの定期監査」を提案する価値あり。

## 6. Reflexion

```json
{"self_review":{"what_was_done":"triage昇格ガード(t_7e7e7979)がcron未登録で不発だった実バグを自己検出。triage-watchdog.shを既定apply化+0件サイレント化し、no_agent cronジョブ kensho-triage-watchdog(2e0cb09a53df, 0 */6 * * *)を登録。28h滞留していた優先度『高』タスク t_07e4dc05 をtriage→ready昇格、dispatcherが即時claim(run217)して実作業が開始されたことを実測確認。","what_went_well":["ready=0で『実装なし終了』になりかけたところでボード全体走査に切り替え、構造的バグを自己検出した","cronが引数を渡せない(scheduler.py:4375 argv=[bash,path])ことを推測でなくソース実読で確定させ、既定apply化という正しい修正を選んだ","dry-run挙動不変・冪等性・サイレント・実claimの4点を個別コマンドで実測した","変更前にgit未追跡スクリプトの実コピーバックアップを取った"],"what_could_improve":["done検証時に『cronに登録されたか』を1行でよいから確認する習慣が軍団全体に無い。t_07e4dc05そのものが対策タスクであり、それがtriageで不発だった皮肉を教訓化すべき","ready-deprecate.shのscript名不一致(9/6 04:00失敗)を今回見つけたが、別タスク化して追跡するほど深追いしなかった（範囲は1タスクに絞った）"],"mistakes_or_risks":["triage-watchdog.shはprofile repo(/home/atushi/.hermes/profiles/kensho-sweeps)のgit未追跡。バックアップはdata/tmpの実コピーのみで、恒久版管理には入っていない","6h毎の昇格は24h閾値に対して過剰頻度ではないが、triageが大量発生する運用に変えると昇格ラッシュになる（現状triage=0なのでリスク低）"],"learned":"no_agent cronジョブの『done』はスクリプト作成では成立しない。cronは bash <path> で引数不可のため、(1)既定が実効モードであること、(2)ジョブが実際に登録されていること、の2点を必ず実測してからdoneにする。次回からworkerのdone判定チェックリストに『hermes cron list / runs <job_id> でlast_status=okを確認』を追加する。","confidence":9,"verification_evidence":"bash -n SYNTAX_OK / dry-run triage_stale=1 / apply promoted=1 failed=0 / t_07e4dc05 status=ready→running (run217 claimed pid4018133) / 2回目実行 stdout_len=0 / hermes cron list に kensho-triage-watchdog 0 */6 * * * no-agent 登録確認"}}
```
