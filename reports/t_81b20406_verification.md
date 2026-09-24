# t_81b20406 検証レポート — 幽霊assignee検出ガード

## verification_evidence

### ガード挙動（実測・4件のコマンド出力）

```
$ python3 scripts/kensho_hunter_guard.py check --title "test-guard-t81b20406-real" --body "test body" --assignee kensho-worker
[hunter-guard] OK unique theme and real assignee: 'test-guard-t81b20406-real' key=hunter-20260924-409ccb40
hunter-20260924-409ccb40
→ rc=0（起票可・決定的キー出力）
```

```
$ python3 scripts/kensho_hunter_guard.py check --title "test-guard-t81b20406-ghost" --body "test body" --assignee critic-a
[hunter-guard] BLOCKED ghost assignee: 'critic-a' not in real profiles list
ghost assignee: critic-a
→ rc=2（幽霊assignee = 起票中止・明示ブロック）
```

```
$ python3 scripts/kensho_hunter_guard.py check --title "test-guard-t81b20406-none" --body "test body"
[hunter-guard] OK unique theme: 'test-guard-t81b20406-none' key=hunter-20260924-84174fb5
hunter-20260924-84174fb5
→ rc=0（assignee未指定でも起票可）
```

```
$ python3 scripts/kensho_hunter_guard.py assignee_check --assignee orchestrator
[hunter-guard] BLOCKED ghost assignee: 'orchestrator' not in real profiles list
→ rc=1（assignee_check CLI: 幽霊=1 / 実在=0）
```

### 成功指標（board全体）

```
$ hermes kanban --board kensho-ai-team assignees | grep -c ' no '
0
→ 幽霊assignee 0件（実在10プロファイルのみ）
```

### コード整合性

```
$ python3 /tmp/syntax_check.py
OK /mnt/d/Project2/kensho/scripts/kensho_hunter_guard.py
OK /mnt/d/Project2/kensho/scripts/kensho-opportunity-discovery.py
ALL SYNTAX OK
```

### コミット証跡

```
$ git log --oneline -1
dac0265 t_81b20406: 幽霊assignee検出ガード強化（exit 2 明文化）+ board-assignees.md 作成
```

### 変更ファイル（3）

- `scripts/kensho_hunter_guard.py` — check コマンドで幽霊assigneeを exit 2 で明示ブロック
- `scripts/kensho-opportunity-discovery.py` — 生成プロンプトに `--assignee` + board-assignees.md 参照を追加
- `references/board-assignees.md` — 実在10プロファイル一覧（唯一の真実源）を新規作成

### 次のステップ

- 親完了で子タスク `t_e1407687`（assignee=kensho-revenue-worker）が ready 自動昇格
- QAは `hermes kanban --board kensho-ai-team assignees | grep -c ' no '` → 0 の1行検証で確認可