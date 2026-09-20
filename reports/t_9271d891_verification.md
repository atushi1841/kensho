# t_9271d891 verification report — AIチーム検証の3層化ハーネス

## 実装内容
- `scripts/agent_eval_harness.py` — component(L1) / trace(L2) / sim(L3) の3層判定。
  - L1: loop_health JSON / evidence.json(条件j必須6フィールド) / notepad構造化 / kanban同期ペイロードASCII
  - L2: handoff完全性 / game-of-telephone消失検出 / 状態遷移許容表 / 依存ゲート
  - L3: 一時ディレクトリ+モックCLI(本番API非接触)で cron相当の連続3実行、状態永続、本番分離検証
- `tests/test_agent_eval_harness.py` — 各層>=3、合計28テスト(判定シナリオ超過充足)。

## verification_evidence
専用テスト実行:
```
$ .venv/bin/python -m pytest tests/test_agent_eval_harness.py -q
28 passed in 14.92s
```
dry-runゲート(全19判定・層カバレッジ・疑似3連続・本番分離):
```
$ python3 scripts/agent_eval_harness.py --dry-run
agent_eval_harness: 19/19 scenarios executed correctly (gate pass=True)
layers: {'component': 8, 'trace': 8, 'sim': 3}  (each>=3 required => True)
sim 3連続実行 成功判定率100% => True
```
疑似本番の本番Kanban・notepad前後一致:
```
$ python3 scripts/agent_eval_harness.py --dry-run --json
sim_isolation ok=True Kanban件数前後一致, notepad一致 (本番変更0件)
```
commit/push:
```
$ git log --oneline -1
72f3f19 t_9271d891: 3層検証ハーネス 証跡レポート+機械可読evidence
$ git status --short --branch
## main...origin/main
```
