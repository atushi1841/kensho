# 検証レポート: research収集×applyのBOT検出相関リスク軽減 (t_9cc18ba0)

## 実施内容
research収集 = twscrapeによるX直接検索（唯一Xセッション/auth cookieを消費する収集ソース）を、
apply応募等活帯（orchestrator.no_action_window 既定 00:00〜07:00）から分離した。
config `collection.research_hours: [3]` により、apply非稼働の03:00収集cronのみX検索を実行し、
それ以外の収集時刻（cron `0 3,9,10,...,21`）では`research_allowed()`がFalseでtwscrapeをskipする。

実装: `kensho/scraping/collector.py` (`research_allowed()` + Step 2f ゲート)、
`config.yaml` (`research_hours: [3]`)、`tests/test_collector.py` (TestResearchAllowed 6件)。
受け入れコミット: `fabcd08`（origin/main へ push 済み）。

## verification_evidence
実コマンド出力を以下に引用する。

`$ git log --oneline -1`
→ fabcd08 fix(research): gate X-direct search (twscrape) to non-apply hours - t_9cc18ba0

`$ git status --porcelain -uall`（本タスク関連コード＝コミット済み）
→ M data/... （data/reports はデータchurnで除外対象）

`$ python -m pytest tests/test_collector.py -q`
→ 54 passed in 14.11s

`$ python -m pytest tests/test_collector.py::TestResearchAllowed -q`
→ 6 passed in 12.45s

`$ PYTHONPATH=/mnt/d/Project2/kensho python /tmp/research_gate_check.py`
→ research_hours = [3]
→ apply-active 12:00 -> False
→ non-active 03:00  -> True

`$ grep -c 'BOT' /mnt/d/Project2/kensho/logs/auto_20260918.log`
→ 0（exit 1 = マッチなし、BOT警告ゼロ）

`$ mypy kensho/scraping/collector.py`
→ 7 pre-existing errors、本変更による新規エラーなし（base stash で同一7件を確認済み）

`$ git push origin main 2>&1`
→ 413a0df..fabcd08  main -> main

### 判定
- 成功指標「research実行後24h内のapplyエラー率5%以下」: 継続モニタリング対象（収集cron 03:00以降の実測で確認）。
- 実装の動作分離は上記ゲート実測で確認済み: 12:00（apply稼働帯）= False → twscrape skip、03:00（非稼働帯）= True → twscrape実行。
- X情報源: grep 'BOT' 当日ログ = 0件（BOT警告到達ゼロの初動指標）。
- 失敗時代替案（ApifyエージェントでIP完全分離）は、時刻分離で受け入れられるため今回は非適用。

## 残タスク
- 30日のBOT警告ゼロ継続は監視に委譲（本変更適用後の実測を夜間QAで確認）。
- 収集cron時刻3ではtwscrapeが実際にリクエストされるため、初回03:00実行後のログでX検索実施を確認する。
  → 夜間QA検証カードへ委譲（kensho-qa）。
