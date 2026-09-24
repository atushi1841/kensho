# nightly-critic レポート 2026-09-23 (21:20-21:40 JST)

## 0. ループ健康度
score=100 / streak=0 / ready=6→7 / blocked=1→2 / running=2 / escalation=false（priority=normal）

## 1. 前回提案の効果測定
- 幽霊assignee修復（9/23実施・8件）: 修復済みカードは全て ready/running へ復帰し永久滞留は0。★有効
- protocol violation crash: 24h crashed run=35（completed=16 / blocked=4 / reclaimed=3）。うち未回収=1（t_0b949bda）。9/23中の対策カード t_02a5afc4 は未着手。

## 2. 新規発見（実測）
(a) 【最大】kensho-worker / kensho-qa の primary が死んだ bai（balance=0）
  - `grep -n "provider: bai" ~/.hermes/profiles/kensho-worker/config.yaml` → line 3（model主系）
  - 実ログ: `⚠️ API call failed (attempt 1/5): BadRequestError [HTTP 400] Provider: custom Model: qwen3.8-flash Endpoint: https://api.b.ai/v1 ... balance=0 required=2508 ... code=insufficient_user_quota`
  - 直近24hのワーカーログ15本中7本に出現。1タスク最大41回（t_c4e810c6）。
  - 実害: 毎ターン「bai(死)→fireworks(412/timeout)→openrouter:free(15-21時枯渇)」の最大3ホップ。crashed run 35件/24h の主要因。
  - 対策: カード t_8290ea09（blocked=要ユーザーGO。config.yaml の provider 変更は境界リスト該当）
(b) t_0b949bda の blocked 真因 = カードに `skills=["feasibility-research"]` をピン留めしたが reassign 先 kensho-revenue-worker に当該スキルが無く `Error: Unknown skill(s)` で即死×2→gave_up。
  - 対応済: tasks.skills を NULL へ + unblock（21:29）。再発防止カード=t_757b8b5d（ready）
(c) 未コミット第三者コード kensho/scraping/collector.py（guarded_source 引数不整合＝ken-kaku 収集全停止）
  - 実測: `logs/collect_20260923_180002.log` 等は TypeError で Step 2c 以降停止、21:00 収集は ken-kaku 19件→Step2c 進行（data/source_health.json: ken-kaku attempts=21 failures=0）
  - 対応済: 21:28 に commit 290c480（回帰テスト tests/test_guarded_source_arity.py 4 passed）+ push
(d) regression gate: result_column_empty_after_v151 が赤（t_09cdb4a6, QA完結時 result 空）
  - 21:28:46 に result 補填され現在 value=0（GREEN）。恒久対策は nightly-qa プロンプトへの --result 必須明記。

## 3. gate 現況（scripts/regression_gates_ledger.py）
result_column_empty_after_v151=0 / protocol_violation_crash_24h=1（t_0b949bda・ready化済で次run回復見込み）/ checkpoint_missing=0 / notepad_bloat=0 / noagent_script=0

## 4. 提案
1. t_8290ea09（blocked・要ユーザーGO）: bai primary 排除。成功指標=24h `credit insufficient` 0件、検証=`grep -c ... | grep -v ":0" | wc -l` →0
2. t_757b8b5d（既存・ready）: 幽霊skill検出ガード — 本件(b)の恒久対策として妥当、追加提案不要
3. 新規提案は上記1件のみ（ready=7 < 10 のため上限内）

## 5. 申し送り
- gate テストはライブkanban.db参照のため、他タスクの完了直後に一時的に赤→workerの `pytest -x` 自己ループを阻害しうる（本日も途中で緑化）。恒久赤でなければ再実行で解消。
- fireworks fallback（deepseek-v4-flash-0731）は request timeout 継続。鎖の2番手が死んでいる点は bai排除と併せて要観察。

## 6. protocol violation の定量（21:45追記）
- 24h crashed=36: rc=0 silent exit(kanban未打刻)=32 (89%) / nonzero=2 (Unknown skill) / other=2
- 全期間 crashed=337 うち未打刻=325
- 実害例: t_8e1e4934 (QA) は run994(20:45-21:21)+run996(21:21-21:30) の2走で実作業完了後に kanban_complete 未打刻→readyへ差し戻り。t_02a5afc4(ready/未着手) が唯一の恒久対策。
