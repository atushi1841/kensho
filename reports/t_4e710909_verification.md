# t_4e710909 worker report — evolution v105 回帰ゲート (QA run490申し送り対応)

タスク: /mnt/d/Project2/kensho/reports/failure-taxonomy.md 台帳 + tests/test_regression_gates.py の
二重HOME障害を本質修正し、台帳が捕捉した実再発2件を是正して commit/push を完了した run489。

## 実施内容

1. tests/test_regression_gates.py: `GUARD = Path.home()/...` を `_resolve_guard()`（実体パスを
   実在候補から選択）へ差し替え。cron起動時の二重HOME（HOME=/home/atushi/.hermes/profiles/
   kensho-sweeps/home）でも検証可能に（QA run490申し送り対象）。
2. scripts/regression_gates_ledger.py: `HOME` 解決を board DB 実在判定で二重HOME非依存化。
3. 台帳が捕捉した実再発2件を是正:
   - t_46f09dc1 の native complete 空result 再発 → `hermes kanban edit` で result を後方補填
     （恒久 root fix は t_69888136 にQA起票済み）。
   - noagent_script_path 違反2件（dm_scan.py / apify_run_monitor.py 実体配置+登録script名是正）
     → 台帳 value=0、ratchet 1→0 に hard-zero 化。
4. git commit c9e4af9 → push (4537fc0..c9e4af9) 完了。

## verification_evidence

$ cd /mnt/d/Project2/kensho && python -m pytest tests/test_regression_gates.py -q
→ ===== 10 passed in 10.86s =====

$ HOME=/home/atushi/.hermes/profiles/kensho-sweeps/home python -m pytest tests/test_regression_gates.py -q
→ ===== 10 passed in 27.81s ===== (二重HOME設定でも全門通過 — QA run490障害の解消を実測)

$ python -m pytest -q
→ ===== 596 passed, 5 skipped in 87.01s ===== (フルスイート副作用なし)

$ python -m mypy scripts/regression_gates_ledger.py tests/test_regression_gates.py
→ Success: no issues found in 2 source files

$ python scripts/regression_gates_ledger.py
→ gates.result_column_empty_after_v151.value=0 / noagent_script_path_contract.value=0 / protocol_violation=0 / checkpoint=0

$ git log --oneline -1
→ c9e4af9 fix(evolution v105): regression gate noHOME-dependency + 2 real recurrences fixed (t_4e710909)

## 残タスク
なし（commit c9e4af9 をHEADとし、push済み。done_guardの完了条件は下記順で充足確認済み）。
