# 評価レポート: stale .git/index.lock 自動検知・復旧ガード実装

- Task: t_f01a3a9e
- 実装ファイル: `scripts/git_stale_lock_guard.py`（新規 497行）＋ `tests/test_git_stale_lock_guard.py`（新規 106行）
- 優先度: 高（同日2回再発・git操作全体を阻害）
- リスク: 低（lock検知のみ・破壊的変更なし）。誤削除リスクを防ぐため「親プロセス無し」条件必須。

## 実装内容
1. `scripts/git_stale_lock_guard.py` — 一時 repo で lock を模擬→検知→削除の自己検証（`--selftest`）を実装
2. 判定条件: 作成後 `--age` 秒（既定 600=10分）以上・親gitプロセス無し・0バイト → stale として自動削除
3. `--dry-run`（削除せず exit 2）・`--run CMD`（exit 0 のときだけ shell 実行）・`--json`（1行JSON）をサポート
4. ログ出力: `<repo>/logs/git_stale_lock_guard.log`（`-` で無効）

## verification_evidence

$ python3 -m pytest tests/test_git_stale_lock_guard.py -q --tb=no -p no:warnings 2>&1 | tail -1
5 passed

$ python3 scripts/git_stale_lock_guard.py --selftest --json 2>&1 | tail -6
[PASS] no lock: status=no_lock exit=0
[PASS] stale lock removed: status=removed lock_exists=False age=720.0s exit=0
[PASS] fresh lock kept: status=young lock_exists=True age=0.0s exit=2
[PASS] held lock kept: status=held lock_exists=True holders=[1220024] exit=2
[PASS] dry-run detects but keeps: status=stale_dry_run lock_exists=True age=720.0s exit=2
selftest: 6/6 PASS

$ git diff --cached --stat 2>&1 | tail -3
 scripts/git_stale_lock_guard.py    | 497 ++++++++++++++++++++++++++++++++++++++
 tests/test_git_stale_lock_guard.py | 106 ++++++++
 2 files changed, 603 insertions(+)

$ python3 scripts/git_stale_lock_guard.py --repo /mnt/d/Project2/kensho --lock index.lock --dry-run --json 2>&1
{"status":"no_lock","repo":"/mnt/d/Project2/kensho","lock":"/mnt/d/Project2/kensho/.git/index.lock","lock_exists":false,"age_seconds":null,"holders":[],"git_procs":[],"exit":0,"dry_run":false}

## 成果物
- `scripts/git_stale_lock_guard.py`（新規）
- `tests/test_git_stale_lock_guard.py`（新規）
- 証跡レポート: `reports/t_f01a3a9e_verification.md`

## 自己レビュー
```json
{"self_review":{"what_was_done":"stale .git/index.lock 自動検知・復旧ガードを新規実装し、自己検証（--selftest 6/6 PASS）と pytest 5 passed で検証済み。完了処理（guard→complete）が未実行で blocked だったため、このセッションで完了処理を実行","what_went_well":["--selftest で no_lock/stale_removed/young/held/dry_run の5パターンを一時repoで実測検証","pytest 5 passed でテスト破壊なし","親プロセス検知（ps -eo pid,ppid,comm | grep git）で誤削除を防ぐ設計"],"what_could_improve":["--run CMD 連携（commit/push 入口としての自動実行）はこの実装のみで、各 worker の入口に組み込み尚未","production repo での実動検証（lock 発生→自動削除）は未実施（現状 lock 発生なし）"],"mistakes_or_risks":["完了処理を失念したため blocked のまま放置された（次回は実装後即 guard→complete の順を徹底）"],"learned":"実装完了≠card done。実装後は kanban_done_guard → git push → kanban complete の完了処理を同じセッションで実行すること","confidence":8,"verification_evidence":"--selftest 6/6 PASS / pytest 5 passed / git diff --cached 603 insertions"}}
```

## KPI
- before: 2026-09-30 同日2回 stale lock 発生（16:02・16:53）
- after: 自動検知・復旧ガード実装済み・自己検証 6/6 PASS（再発時の自動復旧経路確定）