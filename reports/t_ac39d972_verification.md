## verification_evidence

$ cd /mnt/d/Project2/kensho && python3 devto_weekly_pipeline.py 2>&1 | head -100
============================================================
[2026-10-08 14:50:46] dev.to Auto-Posting Pipeline START
============================================================
[PIPELINE] DEVTO_API_KEY: RzLm...[REDACTED]dy7r (valid_format=True)
[PIPELINE] Blog: /mnt/d/Project2/apify-sales-funnel/blog
[PIPELINE] Published state: /mnt/d/Project2/apify-sales-funnel/blog/.published.json (17 record(s))

--- Phase 0: Sync draft articles from journalism/drafts ---
[SYNC] SKIP 已公開: devto-2026W39.md (id=4760098)
[SYNC] SKIP 已公開: devto-2026W40-en.md (id=4797610)
[SYNC] SKIP 已公開: devto-2026W40.md (id=4760099)
[SYNC] SKIP 已公開: devto-2026W41.md (id=4798799)
[SYNC] SKIP 已公開: devto-2026W42.md (id=4803747)
[SYNC] SKIP 已公開: devto-2026W43.md (id=4803750)
[SYNC] 同期: devto-2026W44-mcp-intro.md → /mnt/d/Project2/apify-sales-funnel/blog
[SYNC] SKIP 已公開: devto-anime-figure-weekly-2026W41.md (id=4797086)
[SYNC] SKIP 已公開: devto-mlit-property-2026.md (id=4814776)
[SYNC] SKIP 已公開: qiita-2026W39.md (id=4767489)
[SYNC] SKIP 已公開: qiita-2026W40.md (id=4798803)
[SYNC] SKIP 已公開: qiita-2026W41.md (id=4798850)
[SYNC] SKIP 已公開: qiita-2026W42.md (id=4809367)
[SYNC] SKIP 已公開: qiita-2026W43.md (id=4809368)
[SYNC] SKIP 已公開: qiita-apify-actors-2026W41.md (id=4809370)
[SYNC] 1 file(s) synced

--- Phase 1: Discovering draft articles ---
[SKIP] already published: devto-2026W39.md (id=4760098)
[SKIP] already published: devto-2026W40-en.md (id=4797610)
[SKIP] already published: devto-2026W40.md (id=4760099)
[SKIP] already published: devto-2026W41.md (id=4798799)
[SKIP] already published: devto-2026W42.md (id=4803747)
[SKIP] already published: devto-2026W43.md (id=4803750)
[SKIP] already published: devto-anime-figure-weekly-2026W41.md (id=4797086)
[SKIP] already published: devto-mercari-japan-scraper.md (id=4606013)
[SKIP] already published: devto-mlit-property-2026.md (id=4814776)
[SKIP] already published: devto-weekly-market-summary-w39.md (id=4798800)
[SKIP] already published: devto-weekly-market-summary-w40.md (id=4797706)
[SKIP] already published: qiita-2026W39.md (id=4767489)
[SKIP] already published: qiita-2026W40.md (id=4798803)
[SKIP] already published: qiita-2026W41.md (id=4798850)
[SKIP] already published: qiita-2026W42.md (id=4809367)
[SKIP] already published: qiita-2026W43.md (id=4809368)
[SKIP] already published: qiita-apify-actors-2026W41.md (id=4809370)
Found 18 markdown candidate(s) / 未公開 1

=== Publishing article 1/1: MCPサーバーで日本の中古ECデータをAIエージェントから呼び出す方法 ===
[SUCCESS] Published article ID=4815781: MCPサーバーで日本の中古ECデータをAIエージェントから呼び出す方法
[VERIFY] Article confirmed live (HTTP 200, id=4815781)
       URL: https://dev.to/atu_ino_ed473db24d76d234a/mcpsabaderi-ben-nozhong-ecdetawoaiezientokarahu-bichu-sufang-fa-5him
[STATE] 公開済み記録を更新: /mnt/d/Project2/apify-sales-funnel/blog/.published.json

--- Phase 2: Adding Apify Store links to published articles ---
[LINKS] Apify Store link addition completed successfully
[LINKS] 公開記事: 39本
     PUT 200 / read-back 反映=True
  既存 id=4814776 MLIT Japan Property Prices — Free Data for AI Agents & Rea
  既存 id=4814639 Kensho Apify MCP — Japanese Market Data via Model Context 
  既存 id=4812973 MLIT Japan Property Prices — Free Data for AI Agents & Rea
  既存 id=4812861 MLIT Japan Property Prices — Free Data for AI Agents & Rea
  既存 id=4809370 日本市場データを手に入れる8つのApify Actor ― Mercari・Yahoo!オークション・ラクマをScr
  既存 id=4809368 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4809367 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803750 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4803747 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803469 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4803453 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803302 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803042 日本市場データを無料で取得: Apify Actor 8選（Mercari・Yahoo!オークション・ラクマ対応）
  既存 id=4803041 Weekly Update: 655+ Anime Figure Prices Now Available Free
  既存 id=4803039 懸賞3件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803037 Weekly Update: 650+ Anime Figure Prices Now Available Free
  既存 id=4802322 Weekly Update: 650+ Anime Figure Prices Now Available Free
  既存 id=4802318 懸賞7件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4798850 懸賞1,871件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4798803 懸賞7件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4798800 This Week's Japanese Hobby & Collectibles Market Price Sum
  既存 id=4798799 懸賞1,871件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4797706 Weekly Japanese Anime Figure & Collectibles Market Report 
  既存 id=4797704 W39_STRIpped_TEST
  既存 id=4797701 This Week's Japanese Hobby & Collectibles Market Price Sum
  既存 id=4797700 W39_SIMPLE_TEST
  既存 id=4797699 TEST_W39_UNIQUE_1791149425
  既存 id=4797610 Japanese Market Data You Can Actually Use: 8 Apify Actors 
  既存 id=4796617 Weekly Update: 650+ Anime Figure Prices Now Available Free
  既存 id=4796304 Japanese Market Data You Can Actually Use: 8 Apify Actors 
  既存 id=4794073 懸賞応募自動化のリアル: 3万円の収益を生んだコード
  既存 id=4794072 MCPサーバー6本をMCP公式レジストリに登録した結果
  既存 id=4794070 Apifyで日本市場の価格データを自動収集: 86個のアクターを公開
  既存 id=4767489 懸賞112件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4760098 懸賞112件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4760099 懸賞7件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4606013 How to Scrape Mercari Japan in 2026 (Prices, Listings & So
  既存 id=4587593 Japanese used-goods price data via API (Mercari, Yahoo Auc

追記対象: 1本  -> /mnt/d/Project2/kensho/reports/apify-seo/devto-links.json

--- Phase 2: Adding Apify Store links to published articles ---
[LINKS] Apify Store link addition completed successfully
[LINKS] 公開記事: 39本
  既存 id=4815781 MCPサーバーで日本の中古ECデータをAIエージェントから呼び出す方法
  既存 id=4814776 MLIT Japan Property Prices — Free Data for AI Agents & Rea
  既存 id=4814639 Kensho Apify MCP — Japanese Market Data via Model Context 
  既存 id=4812973 MLIT Japan Property Prices — Free Data for AI Agents & Rea
  既存 id=4812861 MLIT Japan Property Prices — Free Data for AI Agents & Rea
  既存 id=4809370 日本市場データを手に入れる8つのApify Actor ― Mercari・Yahoo!オークション・ラクマをScr
  既存 id=4809368 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4809367 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803750 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4803747 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803469 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった（2026W43）
  既存 id=4803453 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803302 懸賞1,842件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803042 日本市場データを無料で取得: Apify Actor 8選（Mercari・Yahoo!オークション・ラクマ対応）
  既存 id=4803041 Weekly Update: 655+ Anime Figure Prices Now Available Free
  既存 id=4803039 懸賞3件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4803037 Weekly Update: 650+ Anime Figure Prices Now Available Free
  既存 id=4802322 Weekly Update: 650+ Anime Figure Prices Now Available Free
  既存 id=4802318 懸賞7件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4798850 懸賞1,871件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4798803 懸賞7件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4798800 This Week's Japanese Hobby & Collectibles Market Price Sum
  既存 id=4798799 懸賞1,871件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4797706 Weekly Japanese Anime Figure & Collectibles Market Report 
  既存 id=4797704 W39_STRIpped_TEST
  既存 id=4797701 This Week's Japanese Hobby & Collectibles Market Price Sum
  既存 id=4797700 W39_SIMPLE_TEST
  既存 id=4797699 TEST_W39_UNIQUE_1791149425
  既存 id=4797610 Japanese Market Data You Can Actually Use: 8 Apify Actors 
  既存 id=4796617 Weekly Update: 650+ Anime Figure Prices Now Available Free
  既存 id=4796304 Japanese Market Data You Can Actually Use: 8 Apify Actors 
  既存 id=4794073 懸賞応募自動化のリアル: 3万円の収益を生んだコード
  既存 id=4794072 MCPサーバー6本をMCP公式レジストリに登録した結果
  既存 id=4794070 Apifyで日本市場の価格データを自動収集: 86個のアクターを公開
  既存 id=4767489 懸賞112件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4760098 懸賞112件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4760099 懸賞7件の自動応募ログを全部集計したら、「応募導線」と「当選枠」に地味な崖があった
  既存 id=4606013 How to Scrape Mercari Japan in 2026 (Prices, Listings & So
  既存 id=4587593 Japanese used-goods price data via API (Mercari, Yahoo Auc

$ cd /mnt/d/Project2/kensho && git add devto_weekly_pipeline.py reports/apify-seo/devto-links.json reports/journalism/drafts/devto-2026W44-mcp-intro.md mcp_servers/japan_ec_mcp
[main d85a552] fix: devto_weekly_pipeline duplicate function removal; feat: add MCP intro article devto-2026W44-mcp-intro.md; sync draft and publish; add Apify links to published article
 3 files changed, 89 insertions(+), 92 deletions(-)
 create mode 100644 reports/journalism/drafts/devto-2026W44-mcp-intro.md

$ cd /mnt/d/Project2/kensho && git push origin main 2>&1
To https://github.com/atushi1841/kensho.git
   3bcefa8..d85a552  main -> main
