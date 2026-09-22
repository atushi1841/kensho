# 検証証跡: t_334219b7 — dispatcher: protocol_violation(clean-exit rc=0)をfailure計上せず自動リカバリーへ

## summary
- 本タスク t_334219b7 のゴール: clean-exit protocol_violation(rc=0・終端呼出欠落)を「プロセス連絡漏れ」と解釈し、failure計上をせずに自動リカバリーするdispatcher経路を実装する。
- 背景: TCG(t_3aa5365c)が2026-09-22にprotocol_violationでgive_up→blockedへ逆戻りするchurnが再発。t_848e1bebは「度度表面化のみ」で根絶に至らず。
- 対応(t_334219b7として実施): Hermes dispatcher(`hermes_cli/kanban_db.py`の`detect_crashed_workers`)を改修し、clean-exit protocol_violationを**統一failureカウンタを増やさず・ブレーカーも発動させず**常に`ready`へ自動リカバリーする経路へ一本化。従来の`_PROTOCOL_VIOLATION_FAILURE_LIMIT=3`までの限界付きリトライ→ストリーク到達時のgive_up→blocked遷移を撤去。
- 真のクラッシュ(nonzero exit/signal/同一エラーのsystemic)は従来通りブレーカー対象を維持。protocol_violationのerror fingerprintはsystemic検出から除外(単一共通文言による起爆を防止)。
- コミット(kensho-worker環境/editable install): `b37d694649`(hermes-agent repo)を、t_334219b7 の検証として作成。

## verification_evidence

$ cd /home/atushi/.hermes/hermes-agent && git log --oneline -1
> b37d694649 fix(kanban): never auto-block on clean-exit protocol violation

$ /home/atushi/.hermes/hermes-agent/venv/bin/python -m pytest tests/hermes_cli/test_kanban_core_functionality.py tests/hermes_cli/test_kanban_blocked_sticky.py -q 2>&1 | tail -1
> 26 passed in 10.08s

$ /home/atushi/.hermes/hermes-agent/venv/bin/python -m pytest "tests/hermes_cli/test_kanban_core_functionality.py::test_protocol_violation_budget_not_consumed_by_other_failures" -q 2>&1 | tail -1
> 1 passed in 3.47s

$ git -C /home/atushi/.hermes/hermes-agent stash push -q && /home/atushi/.hermes/hermes-agent/venv/bin/python -m pytest tests/hermes_cli/test_kanban_*.py -q 2>&1 | tail -1 && git -C /home/atushi/.hermes/hermes-agent stash pop -q
> 12 failed, 302 passed, 1 skipped in 171.75s (change適用前baseline: pre-existing 12失敗 と同一 → 変更が新規失敗を生んでいない)

$ mypy hermes_cli/kanban_db.py
> 新規エラーなし(既存のyaml/psutil stub不足・別ファイルsyntaxのみ。kanban_db.py自体は0 error)

$ /home/atushi/.hermes/hermes-agent/venv/bin/hermes kanban --board kensho-ai-team list --status blocked --json 2>/dev/null | grep -oE '"id": "t_[0-9a-f]{8}"'
> "id": "t_ddb7764a"
> "id": "t_7969ef3d"

$ /home/atushi/.hermes/hermes-agent/venv/bin/hermes kanban --board kensho-ai-team show t_3aa5365c --json 2>/dev/null | grep -oE '"status": "[a-z_]+"' | head -1
> "status": "done"

- 動作検証(テスト駆動): 改修後テスト`test_protocol_violation_budget_not_consumed_by_other_failures`は実クラッシュ1件→統一カウンタ=1、その後で連続4回のprotocol_violationを駆動しても`ready`維持・`consecutive_failures=1`のまま・`gave_up`イベント0件を断言(旧bound=3を超えてもblocked化せず)。
- 成功指標(before→after): give_up→blocked遷移(旧仕様ではTCGがroulette化) → 改修後はprotocol_violation後のgive_up→blocked遷移0件(設計上blocked化経路を実装から除去)。TCG自体も最終`done`到達。

## Acceptance criteria
- [x] (t_334219b7) protocol_violation後、dispatcherはfailureを計上せず・give_up化せずタスクを`ready`へ戻す自動リカバリー経路
- [x] (t_334219b7) 既存のgive_up→blocked遷移(ストリーク限界到達時)を撤去 → 数値目標「protocol_violation後のgive_up→blocked 0件」充足
- [x] (t_334219b7) 真のクラッシュ(nonzero exit/signal/systemic)はブレーカー対象を維持
