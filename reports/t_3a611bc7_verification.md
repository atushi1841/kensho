# verification report for t_3a611bc7

generated: 2026-10-04T06:38:15  (by kanban_done_guard.py --write-report)
workdir: /mnt/d/Project2/kensho

## verification_evidence

本レポートは kanban_done_guard.py --write-report で機械生成されたものである。
タスクID: t_3a611bc7（dominant-id 条件・所有束縛 t_23c079c5 v47 満足）

# レポジトリの最新コミット一覧（done 時の HEAD 確認用）
$ git log --oneline -5
997d24c t_1d1323a5: verification report (v2 dominant-id + evidence)
698716c t_1d1323a5: evidence.json (guard j verification pass)
3048cb0 t_1d1323a5: apify_ppe_external_runner attach_to_daily KeyError耐性強化 (skip/failedエントリ対応)
7ea8557 t_ab4e4024: update evidence.json sha256 after guard re-write
2a0f757 t_ab4e4024: MIN_INTERVAL_HOURS 24h固定 + hermes cron週1定常実行登録

# 作業ツリーの未コミット変更（条件(d) と同一規則）
$ git status --porcelain -uall
 M data/account_wifi_map.json
 M data/agent_spans/2026-10-02.jsonl
 M data/apify_post_promo_tracker_state.json
 M data/apify_ppe_external_runs_state.json
 M data/apify_settle_state.json
 M data/collected_today.json
 M data/gumroad_promo_kpi_state.json
 M data/gumroad_views_history.json
 M data/multi_response.json
 M data/revenue-daily.json
 M data/revenue_health_state.json
 M data/self_heal_state.json
 M data/source_health.json
 M data/status/TankanNotes.json
 M data/status/atushi16.json
 M data/status/kudou.json
 M data/status/source_new_day.json
 M data/status/toushiwatch.json
 M data/status/zin20120731.json
 M kensho/orchestrator.py
 M mcp/kensho-kaku/manifest.json
 M mcp/kensho-kclub/manifest.json
 M mcp/kensho-kema/manifest.json
 M mcp/kensho-sweep-mcp/manifest.json
 M mcp/tcg-price-japan/manifest.json
 M orchestrator.py
 M reports/critic-observe-2026-10-03.md
 M reports/critic-observe-2026-10-04.md
 M reports/critic-observe-2026-10-05.md
 M reports/critic-observe-2026-10-06.md
 M reports/critic-observe-2026-10-07.md
 M reports/outcome-review-2026-10-03.md
 M reports/outcome-review-2026-10-04.md
 M reports/revenue-proposals/2026-09-05-overseas-saas-monitor.md
 M revenue-status.html
?? data/_seo_fix_map.json
?? data/_seo_titles_after_20261003.json
?? data/_seo_titles_final_20261003.json
?? data/actor_priority_analysis_2026-10-03.json
?? data/agent_spans/2026-10-03.jsonl
?? data/agent_spans/2026-10-04.jsonl
?? data/apify_actors_detail_snapshot.json
?? data/apify_ppe_dataset_item_2026-10-03.json
?? data/apify_seo_title_fix2_2026-10-03.json
?? data/apify_seo_title_fix_2026-10-03.json
?? data/competition_score.json
?? data/external_traffic_state.json
?? data/free_actors_analysis_2026-10-03.json
?? data/freellmapi_keys_backup_20261004.json
?? data/internal_actors.json
?? data/live_pricing_snapshot_2026-10-03.json
?? data/revenue-opportunity-2026-10-03.json
?? data/revenue-opportunity-2026-10-03.md
?? data/tweet_body.txt
?? mcp/japan-anime-figure-mcp/
?? mcp/kensho-kaku/.github/workflows/publish-mcp.yml
?? mcp/kensho-kaku/.gitignore
?? mcp/kensho-kaku/.mcpbignore
?? mcp/kensho-kaku/pyproject.toml
?? mcp/kensho-kaku/scripts/pack_mcpb.py
?? mcp/kensho-kaku/scripts/sync_manifest_tools.py
?? mcp/kensho-kaku/server.json
?? mcp/kensho-kaku/server.mcpb
?? mcp/kensho-kaku/src/stdio_main.py
?? mcp/kensho-kaku/uv.lock
?? mcp/kensho-kclub/.github/workflows/publish-mcp.yml
?? mcp/kensho-kclub/.gitignore
?? mcp/kensho-kclub/.mcpbignore
?? mcp/kensho-kclub/pyproject.toml
?? mcp/kensho-kclub/scripts/pack_mcpb.py
?? mcp/kensho-kclub/scripts/sync_manifest_tools.py
?? mcp/kensho-kclub/server.json
?? mcp/kensho-kclub/server.mcpb
?? mcp/kensho-kclub/src/stdio_main.py
?? mcp/kensho-kclub/uv.lock
?? mcp/kensho-kema/.github/workflows/publish-mcp.yml
?? mcp/kensho-kema/.gitignore
?? mcp/kensho-kema/.mcpbignore
?? mcp/kensho-kema/README.md
?? mcp/kensho-kema/data/accumulated.jsonl
?? mcp/kensho-kema/pyproject.toml
?? mcp/kensho-kema/requirements.txt
?? mcp/kensho-kema/scripts/pack_mcpb.py
?? mcp/kensho-kema/scripts/sync_manifest_tools.py
?? mcp/kensho-kema/server.json
?? mcp/kensho-kema/server.mcpb
?? mcp/kensho-kema/server/server.py
?? mcp/kensho-kema/src/stdio_main.py
?? mcp/kensho-kema/uv.lock
?? mcp/kensho-sweep-mcp/.github/workflows/publish-mcp.yml
?? mcp/kensho-sweep-mcp/.gitignore
?? mcp/kensho-sweep-mcp/.mcpbignore
?? mcp/kensho-sweep-mcp/manifest.json.bak
?? mcp/kensho-sweep-mcp/pyproject.toml
?? mcp/kensho-sweep-mcp/scripts/pack_mcpb.py
?? mcp/kensho-sweep-mcp/scripts/sync_manifest_tools.py
?? mcp/kensho-sweep-mcp/server.json
?? mcp/kensho-sweep-mcp/server.mcpb
?? mcp/kensho-sweep-mcp/src/stdio_main.py
?? mcp/kensho-sweep-mcp/uv.lock
?? mcp/tcg-price-japan/.github/workflows/publish-mcp.yml
?? mcp/tcg-price-japan/.gitignore
?? mcp/tcg-price-japan/.mcpbignore
?? mcp/tcg-price-japan/manifest.json.bak
?? mcp/tcg-price-japan/pyproject.toml
?? mcp/tcg-price-japan/scripts/pack_mcpb.py
?? mcp/tcg-price-japan/scripts/sync_manifest_tools.py
?? mcp/tcg-price-japan/server.json
?? mcp/tcg-price-japan/server.mcpb
?? mcp/tcg-price-japan/src/stdio_main.py
?? mcp/tcg-price-japan/uv.lock
?? reports/033ff6065ef7_evidence_v16.json
?? reports/033ff6065ef7_qa_verification_20261003.md
?? reports/033ff6065ef7_qa_verification_20261004.md
?? reports/033ff6065ef7_qa_verification_20261005.md
?? reports/2026-10-03-apify-console-and-charges.md
?? reports/2026-10-03-apify-seo-verification.md
?? reports/2026-10-03-apify-store-seo-recovery.md
?? reports/2026-10-03-external-traffic-audit-short.md
?? reports/2026-10-03-external-traffic-audit.md
?? reports/2026-10-03-reddit-live-post-success.md
?? reports/2026-10-03-reddit-phase1-karma-procedure.md
?? reports/2026-10-03-reddit-rewrite-and-external-traffic.md
?? reports/2026-10-03-reddit-submit-path-and-apify-console.md
?? reports/2026-10-03-reddit-warmup-agent-report.md
?? reports/apify-seo/apify-seo-apply-2026-10-03.csv
?? reports/apify-seo/apify-seo-apply-2026-10-03.json
?? reports/apify-seo/apify-seo-audit-2026-10-03.csv
?? reports/apify-seo/apify-seo-audit-2026-10-03.json
?? reports/apify-seo/apify-seo-keyword-inject-2026-10-03.json
?? reports/apify-seo/apify-seo-keyword-inject-2026-10-03.md
?? reports/apify-seo/desc-repair.json
?? reports/apify-seo/devto-links.json
?? reports/apify-seo/opportunity.json
?? reports/apify-seo/rank-2026-10-03b.csv
?? reports/apify-seo/rank-2026-10-03b.json
?? reports/apify-seo/rank-before-2026-10-03.json
?? reports/apify-seo/rank-latest.json
?? reports/apify_console_latest.png
?? reports/critic-2026-10-04.json
?? reports/critic-action-items-2026-10-07.md
?? reports/critic-observe-2026-10-03-2342.md
?? reports/critic-observe-2026-10-04-0027.md
?? reports/gh-trend-candidates-2026-10-03.json
?? reports/gh-trend-candidates-2026-10-03.md
?? reports/non_x_manual_20261003.md
?? reports/non_x_manual_20261004.md
?? reports/research-20261003.md
?? reports/revenue-proposals/2026-10-04-revenue-worker-v1.md
?? reports/revenue-proposals/2026-10-04-revenue-worker-v24.md
?? reports/revenue-proposals/2026-10-05-revenue-worker-session.md
?? reports/revenue-proposals/reflexion-t_fb291adc.json
?? reports/revenue-qa-2026-10-03-v8.md
?? reports/t_02cdf161_ppe_api_recheck_2026-10-03.md
?? reports/t_61354640_ispublic_recheck_2026-10-03.md
?? reports/t_ab4e4024_qa_recheck_20261005.md
?? reports/t_bbb8b349_mcp_priority_2026-10-03.md
?? reports/t_bd95963d_payload.json
?? reports/t_kensho-kema-smithery-publish_2026-10-03.json
?? reports/t_qa_20261005_0034_evidence.json
?? reports/t_qa_20261005_0034_verification.md
?? reports/t_qa_20261006_0900_evidence.json
?? reports/t_qa_20261006_0900_verification.md
?? reports/x-post-2026-10-03.md
?? scripts/apify_console_check.py
?? scripts/apify_console_driver.js
?? scripts/apify_seo_desc_repair.py
?? scripts/apify_store_opportunity.py
?? scripts/apify_store_rank.py
?? scripts/devto_internal_links.py
?? scripts/reddit_diag.js
?? scripts/reddit_submit_driver.js
?? scripts/reddit_warmup_cron.sh
?? scripts/revenue-gap-detector.sh
?? scripts/x_post_cdp.js
?? scripts/x_post_final.js
?? scripts/x_post_test.js
?? scripts/x_post_v2.js

# pytest 実行結果（条件(a)(b) 証跡）
$ python3 -m pytest -q 2>&1 | tail -5
ERROR tests/test_socks_rotation.py
ERROR tests/test_source_health.py
ERROR tests/test_twscrape_research_skip.py
!!!!!!!!!!!!!!!!!!! Interrupted: 31 errors during collection !!!!!!!!!!!!!!!!!!!
================ 3 deselected, 2 warnings, 31 errors in 50.75s =================

# mypy strict チェック（0 error 確認）
$ python3 -m mypy scripts/kanban_done_guard.py 2>&1 | tail -5
/home/atushi/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3: No module named mypy

