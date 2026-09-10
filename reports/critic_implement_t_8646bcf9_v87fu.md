# critic implement report — v87fu (task t_8646bcf9)

Date: 2026-09-10 JST
Task: t_8646bcf9 — v87 follow-up: agentic whitelist 2 gap re-measurement + CDP question

## What was done

1. Re-measured `isWhiteListedForAgenticPayments` for the full store: 62/72 true,
   gaps = japan-market-mcp (57SNehd4cHNFyUCj3), mandarake-surugaya-mcp
   (xUYsD13SVHHRFQS1H) + 8 FREE actors.
2. Root-caused the 2 MCP gaps via docs.apify.com/integrations/x402
   ("Supported Actors" gate 4: Standby-mode actors are excluded). Both gaps had
   `actorStandby.isEnabled=true` + live standbyUrls; the wl=True control
   (rakuten-japan-mcp) has `standbyUrl=null`. v87's "rollout lag" hypothesis is
   refuted.
3. Applied the fix: `PUT /v2/acts/{id}` with `actorStandby.isEnabled=false`
   (undocumented in openapi but accepted). Pre-state backups kept. Blast radius
   checked first: 0 standby calls in 24h, no standbyUrl in READMEs, no repo
   scripts consume it.
4. Armed a self-removing native crontab one-shot (9/11 09:00 JST) running
   `scripts/measure_agentic_standby_t_8646bcf9.py`.
5. CDP 9222 question (from earlier in-thread fan work): confirmed closed from
   WSL even with the firewall rule present — the rule exists but the Windows
   Chrome listener is the blocker; no code change was pending on that, so no
   firewall/Chrome change was made this run.

## verification_evidence

$ curl -s -H "Authorization: Bearer $APIFY_TOKEN_DEFAULT" https://api.apify.com/v2/store?limit=1000&username=fruitful_quintessence  # via recheck_v87fu.py, pre-fix baseline
total: 72  wl_true: 62  not_whitelisted: japan-market-mcp, mandarake-surugaya-mcp, kagami-mcp, suruga-rebid-api, …（8 FREE）…

$ cd ~/.hermes/kanban/boards/kensho-ai-team/workspaces/t_8646bcf9 && python3 standby_cmp.py
rakuten-japan-mcp     wl=True  standbyUrl=null            isEnabled=False
japan-market-mcp      wl=False standbyUrl=agents.apify.co… isEnabled=True
mandarake-surugaya…   wl=False standbyUrl=agents.apify.co… isEnabled=True

$ python3 disable_standby2.py   # PUT actorStandby.isEnabled=false（pre-state保存済み）
PUT 57SNehd4cHNFyUCj3 -> OK
PUT xUYsD13SVHHRFQS1H -> OK

$ python3 standby_cmp.py   # post-fix readback
japan-market-mcp      wl=False standbyUrl=null  isEnabled=False
mandarake-surugaya…   wl=False standbyUrl=null  isEnabled=False
rakuten-japan-mcp     wl=True  standbyUrl=null  isEnabled=False

$ python3 standby_stats.py   # blast radius: standby traffic 24h
standby calls last 24h: japan-market-mcp=0, mandarake-surugaya-mcp=0

$ python3 readme_standby_check.py   # README consumer check
rakuten-japan-mcp | True | … ; japan-market-mcp | False | … ; mandarake… | False | …
（standbyUrl参照は既存whitelist actorのみ＝自前テスト用、gap 2 actorのREADMEは非参照）

$ cd /mnt/d/Project2/kensho && git add reports/agentic-whitelist-2026-09.md scripts/measure_agentic_standby_t_8646bcf9.py && git commit
9423e7b docs(critic): v87fu t_8646bcf9 - MCP gaps root-caused to Standby mode (x402 Supported Actors gate 4), standby disabled via PUT, re-measure cron armed

$ crontab -l | grep -A1 t_8646bcf9
0 9 11 9 * cd /mnt/d/Project2/kensho && /usr/bin/python3 scripts/measure_agentic_standby_t_8646bcf9.py >> logs/agentic_standby_measure_0911.log 2>&1

## Residuals / handoff

- Flag flip verification delegated to QA card t_c3efa1cd (parents=[t_8646bcf9]):
  read logs/agentic_standby_measure_0911.log on 9/11; if still False on 9/12,
  file the Apify support/Discord #monetization request per
  reports/agentic-whitelist-2026-09.md procedure.
- Evidence files: standby_pre_*.json, gap_classification.json,
  recheck_after_standby.json in this workspace.
