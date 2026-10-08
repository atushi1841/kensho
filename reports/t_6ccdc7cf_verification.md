## verification_evidence

$ cd /mnt/d/Project2/kensho && python3 devto_weekly_pipeline.py --apply 2>&1 | tail -5
============================================================
[2026-10-08 16:04:55] dev.to Auto-Posting Pipeline START
============================================================
[PIPELINE] DEVTO_API_KEY: RzLm...[REDACTED]dy7r (valid_format=True)
[PIPELINE] Blog: /mnt/d/Project2/apify-sales-funnel/blog
[PIPELINE] Published state: /mnt/d/Project2/apify-sales-funnel/blog/.published.json (18 record(s))

--- Phase 0: Sync draft articles from journalism/drafts ---
[SYNC] 0 file(s) synced

--- Phase 1: Discovering draft articles ---
Found 18 markdown candidate(s) / 未公開 0
[INFO] 未公開候補はありません（新規記事の追加待ち）

$ cd /mnt/d/Project2/kensho && python3 scripts/devto_internal_links.py --apply 2>&1 | tail -5
公開記事: 39本
  既存 id=4815781 MCPサーバーで日本の中古ECデータをAIエージェントから呼び出す方法
  既存 id=4814776 MLIT Japan Property Prices — Free Data for AI Agents & Rea
  既存 id=4814639 Kensho Apify MCP — Japanese Market Data via Model Context 
追記対象: 0本  -> /mnt/d/Project2/kensho/reports/apify-seo/devto-links.json

$ cd /mnt/d/Project2/kensho && git add devto_weekly_pipeline.py
[main 3333312] fix: devto_weekly_pipeline remove duplicate call to devto_internal_links.py (task t_6ccdc7cf)
 1 file changed, 4 deletions(-)
$ cd /mnt/d/Project2/kensho && git push origin main 2>&1
To https://github.com/atushi1841/kensho.git
   d85a552..3333312  main -> main
