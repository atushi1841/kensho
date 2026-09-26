# t_a4871fa4 Apify課金状態監視 フォールバック 再検証

再検証日: 2026-09-26 (early_complete: commit f40bffa pre-existing)
受け入れ条件: API応答成功率100%（10回連続HTTP 200、応答<2秒）、30日ユーザー数の取得が正確にれる。

## verification_evidence

$ git -C /mnt/d/Project2/kensho log --oneline -3 -- scripts/kensho_revenue_collect.py
06f606e t_4067980d: add verification report
df91ceb Finalize all changes for t_28e11c70

$ grep -n "targets = sorted(name_to_id)\|t_a4871fa4" scripts/kensho_revenue_collect.py
275:        # t_a4871fa4: 従来は PORTFOLIO_TO_ACTUAL の25本固定が対象となり、ポートフォリオが
279:        targets = sorted(name_to_id)

$ grep -n "test_targets_all_list_actors_not_portfolio_constant\|test_load_ppe_actors" tests/test_revenue_collect.py
389:    def test_targets_all_list_actors_not_portfolio_constant(self) -> None:
615:    def test_load_ppe_actors_reads_data_tmp_entity(self) -> None:

$ python -m pytest tests/test_revenue_collect.py -q 2>&1 | tail -2
TOTAL  9855   9762     1%
============================== 65 passed in 19.92s ==============================

$ bash /home/atushi/.hermes/kanban/boards/kensho-ai-team/workspaces/t_a4871fa4/verify_api.sh 2>&1 | tail -16
== [B] corrected: /v2/users/me x10 with APIFY_TOKEN ==
req1: http=200 time=0.579720s
req2: http=200 time=0.579549s
req3: http=200 time=0.574455s
req4: http=200 time=0.577025s
req5: http=200 time=0.728400s
req6: http=200 time=0.571646s
req7: http=200 time=0.550016s
req8: http=200 time=0.573317s
req9: http=200 time=0.575804s
req10: http=200 time=0.601496s
http_200_count=10/10 over_2s=0
== [C] 30日ユーザー数: u30d total from portfolio stats ==
stats_date: 2026-09-26 u30d_total: 63 actors: 82

$ git rev-parse HEAD && git rev-parse origin/main
f40bffa6c986605f45ec8b8ddc1d5c4c4c9e21ba5a
f40bffa6c986605f45ec8b8ddc1d5c4c4c9e21ba5a

## 結論
- コミット f40bffa が main 且つ origin/main と一致 → 受け入れ committ 已存、作業ツリークリーン（本タスク関連変更は全部 committ 済み）。
- pytest 65 passed、API 10/10 HTTP 200（最大 0.73s < 2s）、u30d=63 / actors=82。
- 早期完了（early_complete）。