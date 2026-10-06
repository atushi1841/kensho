# Verification Report: pytest 失敗3件の調査

## 対象テスト
1. `tests/test_regression_gates.py::test_loop_health_band_reset_invariant`
2. `tests/test_agent_eval_harness.py::test_sim_three_consecutive`
3. `tests/test_revenue_collect.py::TestV94PpeFallbackPath::test_load_ppe_actors_reads_data_tmp_entity`

## 実行したコマンドと検証結果
- 1. `git -C /mnt/d/Project2/kensho log --oneline -5`
  直近のコミットログを取得し、リポジトリの状態を確認。
- 2. `python -m pytest -q --no-cov tests/test_regression_gates.py::test_loop_health_band_reset_invariant tests/test_agent_eval_harness.py::test_sim_three_consecutive tests/test_revenue_collect.py::TestV94PpeFallbackPath::test_load_ppe_actors_reads_data_tmp_entity`
  対象の3テストを実行し、失敗状況を再現・確認。
- 3. `python3 -c "import sys; sys.path.insert(0, '/mnt/d/Project2/kensho/scripts'); import kensho_revenue_collect as krc; print(krc.load_ppe_actors())"`
  PPEフォールバックローダーの挙動を直接検証。

## 結論
各テストの失敗原因を特定し、共有リポジトリの不整合や環境依存（実ボードの状態・一時ファイルの有無）であることを確認した。
