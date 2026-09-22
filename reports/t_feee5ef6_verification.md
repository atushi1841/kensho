# t_feee5ef6 検証・実装レポート — kanban-sync ghost-card prevention (assignee + dedupe hardening)

本レポートはタスク t_feee5ef6（kensho-kanban-sync.sh の assignee 付与と dedupe 強化）の実装・検証記録。

## 修正対象
- ファイル: `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-kanban-sync.sh`（kensho-sweeps repo 管理、repo外スクリプト）
- コミット: `e43a1d0`（kensho-sweeps repo）

## 修正内容

### 対策[1]: critic create に --assignee kensho-worker を付与
- 旧: `hermes kanban create "critic_proposal_$TODAY: $SUMMARY" --body ...` → assignee=None の ghost カード（t_1f632bd0）が ready に放置され、dispatcher が無視。QA が ID1012 で検出し archive。
- 新: `--assignee kensho-worker` を付与。コメントで「assignee 必須（省略禁止）」を明記。

### 対策[2]: dedupe を body 参照も含む形に強化
- 旧: `list | grep -c "critic_proposal_$TODAY"` → title のみ照合。同じ提案が別タイトルのタスクで実装済み（例: knshow retry → t_18ecf0a5 done、body に "critic proposal 2026-09-22"）でも重複作成してしまう。
- 新: `list --json` で title と body の両方を照合。`critic_proposal_${TODAY}`（auto-created 形式）と `proposal ${TODAY}`（別タイトル実装の body 内表記）の両パターンで skip。
- 既定の list は archived を除外するため、整理済み ghost で再ブロックされることはない。
- ASCII-only ペイロード規則（v2）は維持。

## 成功指標との対応（t_feee5ef6 カード本文）
- 「ready 内の assignee=None カード 7日間 0件」: 本 run で ready AND assignee IS NULL = 0 を確認。既存の assignee=NULL タスクは全て archived / scheduled / done の過去分（新規 ready ghost なし）。
- 「既実装提案で重複カードを再作成しない」: 本 run の sync critic 実行で `[skip] existing task (dedupe)`（t_18ecf0a5 が body 参照で hit）。
- FALLBACK（pre-create guard）: sync を本 run で直接修正したため不要。

## verification_evidence
t_feee5ef6 の 検証実行コマンドと実出力（記録値は実走査のもの）。

```
$ bash -n /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-kanban-sync.sh && echo SYNTAX-OK
SYNTAX-OK
$ TODAY=$(date +%Y-%m-%d) && hermes kanban --board kensho-ai-team list --json 2>/dev/null | grep -E "critic_proposal_${TODAY}|proposal ${TODAY}" -c
1
$ bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-kanban-sync.sh critic
[skip] existing task (dedupe)
$ hermes kanban --board kensho-ai-team create "critic_proposal_$(date +%Y-%m-%d): __PROBE_assignee_test_delete__" --assignee kensho-worker --body "proposal file: PROBE" --json | grep -E '"assignee"|"status"'
  "assignee": "kensho-worker",
  "status": "ready",
$ python3 /tmp/verify_assignee.py
ready && assignee IS NULL count = 0
$ python3 /tmp/final_check.py
probe runs: 0
ready AND assignee IS NULL = 0
```

補足（実測）:
- プローブカード t_6730ef47 を create → assignee=kensho-worker で ready 化を実測確認後、即 archive で無効化（dispatcher 起動なし、task_runs=0）。ボードはクリーンに復帰。
- sync critic 本runは t_18ecf0a5（done, body "critic proposal 2026-09-22"）を dedupe 検出 → `[skip]`。要件どおり重複作成なし。
- 実装は kensho-sweeps repo commit e43a1d0 で git 追跡済み。

## changed_files
- /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-kanban-sync.sh（v3: --assignee 付与 + body 参照 dedupe。commit e43a1d0）
- /mnt/d/Project2/kensho/reports/t_feee5ef6_verification.md（本レポート）
