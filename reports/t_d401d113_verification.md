# verification report for t_d401d113

generated: 2026-10-07T16:35:29  (by kanban_done_guard.py --write-report)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは kanban_done_guard.py --write-report で機械生成されたものである。
タスクID: t_d401d113（dominant-id 条件・所有束縛 t_23c079c5 v47 満足）

# レポジトリの最新コミット一覧（done 時の HEAD 確認用）
$ git log --oneline -5
a88b71b t_d401d113: add evaluation report for TerrainSR (rejected - Apache 2.0 OSS model, no monetization path)
bf6234d t_486da85b: add verification report and evidence for Apify actor consolidation
86afd1a t_816229c1: Apify CN/KR版actorにseoTitle(言語版ラベル)追加 - 18/18成功
a1b4961 t_5e8ec4984bba: add 12:00JST revenue summary
c729c89 t_5e8ec4984bba: revenue worker 2026-10-17 report update

# 作業ツリーの未コミット変更（条件(d) と同一規則）
$ git status --porcelain -uall
 M data/account_wifi_map.json
 M data/apify_actors_detail_snapshot.json
 M data/apify_ppe_external_runs_state.json
 M data/collected_today.json
 M data/competition_score.json
 M data/gumroad_promo_kpi_state.json
 M data/multi_response.json
 M data/revenue-daily.json
 M data/revenue_health_state.json
 M data/self_heal_state.json
 M data/source_health.json
 M data/status/TankanNotes.json
 M data/status/atushi16.json
 M data/status/kudou.json
 M data/status/toushiwatch.json
 M data/status/zin20120731.json
 M reports/apify-make-private/seo-update.json
 M reports/apify-seo/devto-links.json
 M revenue-status.html
 M scripts/apify_make_private.py
 M uv.lock
?? config.yaml.bak-zin-batches-20261007_0053
?? config.yaml.bak2-20261007_0646
?? data/agent_api.db
?? data/agent_spans/2026-10-07.jsonl
?? data/automation_block.json
?? data/collected_today.json.bak-20261007_0643
?? data/price_monitor.db
?? mcp_servers/japan_ec_mcp/
?? reports/2026-10-07-qa-verification.md
?? reports/2026-10-15-revenue-qa.md
?? reports/2026-10-16-revenue-qa.md
?? reports/critic-observe-2026-10-17-v2.md
?? reports/critic-run-2026-10-07.md
?? reports/gh-trend-candidates-2026-10-07.json
?? reports/gh-trend-candidates-2026-10-07.md
?? reports/non_x_manual_20261007.md
?? reports/outcome-review-2026-10-07.md
?? reports/research-20261007.md
?? reports/revenue-proposals/2026-10-14-revenue-worker.md
?? reports/t_816229c1_evidence.json
?? reports/t_qa_20261017_0900_evidence.json
?? reports/t_qa_20261017_0900_verification.md
?? scripts/deploy_mlit_actor.py
?? scripts/reddit_warmup_agent.py.bak-20261007_0651

# pytest 実行結果（条件(a)(b) 証跡）
$ python3 -m pytest -q 2>&1 | tail -5
/home/atushi/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3: No module named pytest

# mypy strict チェック（0 error 確認）
$ python3 -m mypy scripts/kanban_done_guard.py 2>&1 | tail -5
/home/atushi/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3: No module named mypy

