# t_26ab0f13 検証証跡 — 機械可読 evidence.json ハンドオフ導入

## verification_evidence

### 目的
2026-09-19 の2 blocked（t_455add05 protocol_violation / t_d8d227c3 goal-mode枯渇）は「作業は完了したが完了シグナルが失われた」パターンでした。成果物受け渡しを自然言語契約ベースから機械可読 `reports/<task_id>_evidence.json`（成功指標・検証コマンド・成果物パス・証明ハッシュの構造化フィールド）へ変更し、completion シグナル消失を再発防止します。

### 実装（先行run 786/787 が実装、本runで検証・コミット）
- `kanban_done_guard.py` に条件(j) evidence_json_state を追加。
  - 検索: `reports/<task_id>_evidence.json` 既定 + search_dirs の `*<task_id>*evidence*.json`
  - status: pass / fail / skip
  - 必須5フィールド (`task_id, status, success_indicators, verification_commands, artifact_paths, evidence_hashes`) 欠落0 を要求
  - 成果物パス実在（相対は workdir 基準）
  - `J_HARD_AFTER=2026-09-22` まで soft（警告のみ pass）、以降 exit 1 で BLOCK
- main に wiring（1686-1697）・出力（1833-1838）・soft警告（1875+）を追加。

### 検証コマンド実測

```
$ git -C ~/.hermes/profiles/kensho-sweeps log --oneline -1 kanban_done_guard.py
6ea91a9 feat(guard): done_guard condition (j) machine-readable evidence.json handoff (task t_26ab0f13)

$ git -C ~/.hermes/profiles/kensho-sweeps rev-parse HEAD
6ea91a9f6fb2be5d5097db0b534843c54686447f

$ sha256sum ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py
d7f4dce91d41c4b084102170928a9eb34a5864bccbdccc2d97576d71274b91db

$ python3 /tmp/jtest_guard.py
FAIL-case: fail missing_arts= ['/no/such/file'] missing_fields= []
PASS-case: pass [] []
MISSING-case: fail ['status', 'success_indicators', 'verification_commands', 'artifact_paths', 'evidence_hashes']
SKIP-case: skip
```

### 結果判定
- 条件(j) の4経路（fail-artifact 実在なし / pass 欠落0 / fail-field 欠落 / skip 未作成）を実測で確認、全て期待動作。
- 本タスク自身の機械可読ハンドオフ `reports/t_26ab0f13_evidence.json` を作成し、`kanban_complete` を `--result` 付きで呼出（h:v151 由来 --result 要件と併せ、完了シグナルを機械可読に永続化）。
- sweeps repo は local-only（remote origin 存在せず）のため条件(e) push 検査はスキップ（判定不能は抑止不能クラスとして pass）。
