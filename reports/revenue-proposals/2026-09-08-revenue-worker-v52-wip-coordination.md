# revenue-worker v52 — WIP整理・幽霊blocked復活・done_guard条件d解消 (2026-09-08)

## 起動背景
- monitor差分: `score=95|wip=0` → `score=75|wip=4`（critic v52 が10:31に新タスク2件投入+既存WIP2件で in_progress=4）
- loop_health advice.worker = 「通常フローで1タスク実装」だが、ready=0・他3件はライブセッション稼働中（run263/run264/run266 が heartbeat 確認済）。新規着手対象が存在せず、**WIP整理を1タスクの実装**として選定。

## 実施内容

### 1. t_4e678707（72h判定スケジュール）の幽霊blocked復活 → done
- 表示上 blocked だが、カード本体の作業（one-shot cron `32065be91940` 登録、9/11 10:00 JST発火、no-agent、telegram配信）は**完了・検証済**。run263系セッションが10:42にコメント記録済み。
- 残っていたのは done_guard 条件d（共有リポジトリの未コミットコード5件）のみ = **他レーンのWIPによる連鎖ブロック**（v51教訓の再発）。

### 2. 条件dの5件を分類・段階解消
| ファイル | 帰属 | 判断 |
|---|---|---|
| analyze_windows_0906.py | 9/6分析の使い捨てスクリプト（完了済み） | **当セッションでコミット**（ruff修正込み 3ea7aa0） |
| kensho-non-api-revenue-hunter.py / scripts/kanban_norm.py | t_58335360（run263稼働中） | 待機 → **11:04にrun263自身がコミット**（9c6eb4c、t_58335360 done確認済） |
| kensho/scraping/simple_rt_classifier.py / tests/test_simple_rt_classifier.py | classifier の bai/qwen3.8-flash 移行WIP | **モデル切替領域=ユーザー確認必須**のため自動コミット禁止。残置 |

### 3. guard --soft による done 許可（運用者判断）
- 条件a/b/cは充足（verification_evidence=True、引用19件、誤doneマーカー無）。
- 条件d残2件は「他レーンのモデル切替WIP」で本カードと無関係 → guard設計文書が認める soft 運用で done 化。
- 【要ユーザー対応】classifier WIP のコミット可否判断はレポートで明示（下記）。

## verification_evidence

```
$ python3 /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_4e678707
kanban_done_guard task=t_4e678707 -> BLOCK (1 not met: no_uncommitted_code)
  a verification_evidence : True / b command cites >=3 : True (count=19) / c no false-done marker : True
  d: uncommitted 5件 → 整理後2件（classifier+testのみ）に減少を確認

$ hermes cron list | grep -A8 "32065be91940"
32065be91940 [active] / Schedule: once at 2026-09-11 10:00 / Mode: no-agent / Deliver: telegram:8510166694
（スクリプト cfr_72h_judgment.py 実在: -rwxrwxr-x 3035B Sep 8 10:40）

$ cd /mnt/d/Project2/kensho && git add analyze_windows_0906.py && git commit
3ea7aa0 chore(analysis): commit finished 9/6 action-window analysis script (unblock done_guard cond d)
（pre-commit ruff check/format PASS、bare except→ValueError/JSONDecodeError 修正込み）

$ python3 -m pytest -q --no-cov
444 passed, 4 skipped in 115.54s

$ git log --oneline -2
9c6eb4c fix(hunter): t_58335360 all-status dedup guard ...（run263自身のコミット、待機→解消）

$ hermes kanban complete t_4e678707（guard --soft exit 0 確認後）
Completed t_4e678707

$ bash loop_health.sh
score=85 counts={'ready':0,'blocked':0,'in_progress':2,'done_total':314} priority=new_proposals
```

## 結果
- board: score 75→85、in_progress 4→2、done 312→314（t_58335360 は run263 が done 化）
- 残WIP2件（t_a07ac34d=run266稼働中、t_ff52eaf0=run264稼働中）はいずれもライブセッション保有。本セッションは claim せず（二重処理防止ルール遵守）

## 【要ユーザー対応】
- `simple_rt_classifier.py` の bai/qwen3.8-flash 移行diff（46+/39-、テスト14件PASS・mypy 0 error・BAI_API_KEYは3プロファイル.envに存在確認済）が**未コミットでワーキングツリーに滞留**。モデル切替領域のため当エージェントの判断ではコミットしない。
  - 承認なら: `cd /mnt/d/Project2/kensho && git add kensho/scraping/simple_rt_classifier.py tests/test_simple_rt_classifier.py && git commit -m "feat(classifier): switch to bai/qwen3.8-flash with OR fallback"`
  - 却下なら: `git checkout -- kensho/scraping/simple_rt_classifier.py tests/test_simple_rt_classifier.py`
- 放置中は done_guard 条件d が全収益タスクのdone化を連鎖ブロックし続ける（v51/v52と2回連続で同一要因）。

## Reflexion
```json
{"self_review":{"what_was_done":"WIP整理1タスク: t_4e678707の幽霊blockedを条件d解消+guard --softでdone化。analyze_windows_0906.pyをruff修正してコミット(3ea7aa0)、他レーンWIP(run263)のコミットを待機して確認(9c6eb4c)。classifier移行WIPはモデル切替領域として残置し要ユーザー対応に昇格。","what_well":["ライブセッション保有タスク(t_a07ac34d/t_58335360)に触れず二重処理を回避","heartsickなgit index.lock(9/7 18:18の0バイト残骸)をpgrepで生gitプロセス不在確認後に安全除去","pre-commit失敗(ruff/bare except、check-added-largeのstash競合)をその場で修正して通した"],"what_could_improve":["条件dの『他レーンWIPは待機』判断をもう少し早くできたらsoft適用までのコメント往復が1回減った","pytest全体実行のタイムアウト設定(300s→115sで完了)を最初から余裕をもって設定すべきだった"],"mistakes_or_risks":["guard --soft適用は条件dの趣旨(共有リポジトリ衛生)を一部緩和する。残diffが本カードと無関係であることの証跡をコメント+レポートに残した","classifier WIPが未コミットの間に収集cronが動くと、HEAD(a4dbd7a=ローカルqwen)と作業ツリー(bai)で挙動が分かれる。実害は作業ツリー実行側(bai移行済み)に寄っている"],"learned":"done_guard条件dは『使い捨て分析スクリプトの未追跡』でも発火する。分析系は作成時に即git addする運用が最小コスト。モデル切替WIPは鎖状ブロックの常態要因なので、criticに『未コミットWIPの年齢』をmonitor署名へ入れる提案を申し送りしたい。","confidence":8,"verification_evidence":"guard出力(a/b/c=True, d=5→2件)、cron 32065be91940 active表示、git log 3ea7aa0/9c6eb4c、pytest 444 passed、loop_health score=85/wip=2/done=314 すべて実測"}}
```
