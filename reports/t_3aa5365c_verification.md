# 検証証跡: t_3aa5365c — TCG価格データセット商品化(蓄積cron+値動きAPI+Gumroad出品委譲)

## summary (t_3aa5365c)
- t_3aa5365c の蓄積cronを登録・稼働確認: crontab `30 7 * * *` → scripts/tcg_price_collect_cron.sh、システムcron daemon稼働、データセットが360→480 obsへ増加(commit 9b4282b/11f379a)。
- t_3aa5365c の値動きクエリAPI/MCPを実装・テスト: scripts/tcg_price_query.py(current/history/top_movers) + tcg_price_mcp.py(FastMCP, japan-market-mcpパターン)、tests/test_tcg_price_query.py 全7 passed。
- t_3aa5365c の GitHub SEO確認: atushi1841/suruga-ya-scraper に suruga-ya/tcg/pokemon/japan topics設定済み(gh確認)。
- Gumroad出品はデータ成熟(500+obs/複数日)待ちかつセッションCookie失効のため、kensho-revenue-qaへ子カード t_7969ef3d 委譲(t_3aa5365c から)。

## verification_evidence

$ crontab -l | grep tcg
> 30 7 * * * /mnt/d/Project2/kensho/scripts/tcg_price_collect_cron.sh >> /mnt/d/Project2/kensho/logs/tcg_collect_cron.log 2>&1
> (登録済み。pgrep -x cron → cron RUNNING)

$ wc -l data/tcg_dataset/accumulated.jsonl
> 480 data/tcg_dataset/accumulated.jsonl   (初期360 → 480 obsへ蓄積増加、commit 9b4282b→11f379a)

$ python3 scripts/tcg_price_query.py --current "リザードン"
> {"found": true, "query": "リザードン", "matches": 24, ... "collected_at": "2026-09-22T00:19:54Z"}
> (値動きクエリエンジンが実データに対して正常応答)

$ python3 -m pytest tests/test_tcg_price_query.py -v
> ============================== 7 passed in 16.58s ==============================

$ gh repo view atushi1841/suruga-ya-scraper --json repositoryTopics
> "suruga-ya", "tcg", "pokemon", "japan" (設定済み)

## Acceptance criteria
- [x] 蓄積cronが動作し、少なくとも1日の蓄積ログ/サイズ増加を確認できる(cron稼働・daemon RUNNING・360→480 obs、複数snapshot commit)
- [x] 値動きAPIの入出力スキーマ(1エンドポイント以上)が実装・テストされている(current/history/top_movers + MCP, 7 passed)
- [~] Gumroad(または選択チャネル)への出品物が存在、URL・価格・説明文が確定している → データ成熟+新Cookie待ち、子 t_7969ef3d へ委譲(revenue-QA担当)
- [x] 実装部分(収益系タスクの検証は kensho-revenue-qa へ委譲)

## 委譲
- Gumroad出品・収益QA → t_7969ef3d (assignee=kensho-revenue-qa, parents=[t_3aa5365c])
