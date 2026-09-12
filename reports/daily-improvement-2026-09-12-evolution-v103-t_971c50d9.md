# 2026-09-12 evolution v103: workerタイムアウト対策 進捗チェックポイント＋再開プロトコル

カード: t_971c50d9（assignee=kensho-worker）

## 根拠（実測）
- 90/90 Iteration budget枯渇による再ディスパッチが構造化：t_742cfd52（Agent timeout x2）、run319/321（9/9）、t_c186bf62（実装完了済みなのに再検証ループで枯渇）の3件。
- 再ディスパッチはゼロから再走するため、進捗が永続化されていないと枯渇のたびに全イテレーションコストが捨てられる。

## 採用パターン
Durable execution / checkpoint-resume。Temporal の「Event History で各ステップを永続化し、失敗時に進捗保持済み状態から再開」考え方を、kanbanカード＋コメントの軽量チェックポイントで再現（LangGraph checkpointer の thread_id resume と同系）。出典: https://docs.temporal.io/evaluate/understanding-temporal

## 実装（3面＋補助スクリプト）
1. **nightly-worker cron prompt**（5e8ec4984bba、kensho-sweeps）: 「## 進捗チェックポイント＋再開プロトコル（critic v103）」節を追加（3360→4148字）。マイルストーンごとに `[checkpoint] step N done: <成果1行>` 打刻必須／再開時は既存チェックポイントを読んで完了stepスキップ／完了条件充足即done・再検証QA委譲（v76恒久化）。`hermes -p kensho-sweeps cron edit --prompt` で適用、jobs.json永続化を再読込で実測確認（checkpoint節=True）。バックアップ: jobs.json.bak-v103。
2. **ai-team-improvementスキル**（~/.hermes/profiles/kensho-sweeps/skills/software-development/ai-team-improvement/SKILL.md）: 「## 進捗チェックポイント＋再開プロトコル（2026-09-12追加・evolution v103・最重要）」節として教訓永続化。
3. **kensho-worker SOUL.md**:dispatcherワーカー自身の絶対ルールとして同文面を追記（本セッションが実際にstep打刻しながら進め、実証済み）。
4. **scripts/iteration_budget_count.py**: 成功指標カウンタ。ボードJSONから 'Iteration budget' ヒットと status=blocked 件数を分離集計、--since でepoch int比較（v102教訓: created_atはint、文字列スライス比較禁止）。絶対パス実行。

## 効果測定（ゲート日 2026-09-12、窓 14日 = 〜2026-09-26）
- 目標: 新規『Iteration budget exhausted(90/90)』によるblocked=0件
- 検証: `python3 /mnt/d/Project2/kensho/scripts/iteration_budget_count.py --since 2026-09-12`
- 実施前baseline実測: all-time全文hit=2（t_2aead8aa=v76カード、t_971c50d9=本カード。いずれも枯渇そのものでなく**本文言及**のfalse positive）、blocked NOW=0。→ カウンタは「説明として言及するカード」を拾う性質があるため、判定は blocked NOW と実行ログ併用が正しい（スキル§注意に明記済み）。

## 失敗時代替案
14日で再発1件以上なら、コメント追記方式を「カード本文のProgressセクション書き換え更新」方式に強化する（コメント追記は古い進行と混在するため）。

## 検証記録（t_971c50d9 分有）
- 実装修正3面: nightly-worker cron prompt / ai-team-improvementスキル / kensho-worker SOUL.md
- 補助スクリプト: scripts/iteration_budget_count.py（本リレポートと同一コミット 0775aae に含む）
- 受入条件: ①3面へ再開プロトコル収録 ②成功指標コマンド絶対パスで実走 ③リレポート永続化

## 自己レビュー（Reflexion）
{"self_review":{"what_was_done":"v103再開プロトコルをworker cron prompt・ai-team-improvementスキル・kensho-worker SOULの3面へ適用し、成功指標カウンタscripts/iteration_budget_count.pyを実装・実走。本タスク自身で[checkpoint] step打刻をdogfooding実証。","what_went_well":["3面の適用先を事前確定（skill所在=kensho-sweeps、prompt所在=nightly-worker）してから編集し空振りが無かった","カウンタにblocked分離を追加し、本文言及false positiveを構造的に切り分けられた"],"mistakes_or_risks":["全文マッチのカウンタはv76/v103自身のカードを恒久false positiveとして拾い続ける（--sinceとblocked NOWで吸収、スキルに注意書き）","nightly-critic/qa側はスコープ外（本文がworker限定）→ criticが枯渇してもチェックポイント無しのままなので、必要なら次evolutionで横展開"],"learned":"チェックポイントプロトコルは『打刻=進捗永続化、検証=QA』とv76と役割を分離すると矛盾なく共存できる","confidence":8,"verification_evidence":"下記 verification_evidence セクションの実測引用4件"}}

## verification_evidence

$ python3 /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_971c50d9/apply_worker_prompt.py
→ persisted len: 4148 / has checkpoint section: True / has step marker cmd: True / state: scheduled enabled: True last_status: ok

$ python3 /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_971c50d9/verify_prompt.py
→ len: 4148 | has v103: True | last_status: ok

$ python3 /mnt/d/Project2/kensho/scripts/iteration_budget_count.py --since 2026-09-12
→ Iteration budget exhausted tasks (since 2026-09-12): 1 | blocked NOW: 0 / - t_971c50d9（本カード本文言及のみ・枯渇blockedゼロ）

$ grep -c "checkpoint" /home/atushi/.hermes/profiles/kensho-worker/SOUL.md
→ 3
