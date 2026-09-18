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
実コマンド出力の引用（$ cmd 行 → 実出力）。

$ git log --oneline -1
→ fabcd08 fix(research): gate X-direct search (twscrape) to non-apply hours - t_9cc18ba0

$ python -m pytest tests/test_collector.py -q
→ 54 passed in 14.11s

$ python -m pytest tests/test_collector.py::TestResearchAllowed -q
→ 6 passed in 12.45s

$ PYTHONPATH=/mnt/d/Project2/kensho python /tmp/research_gate_check.py
→ research_hours = [3]
→ apply-active 12:00 -> False
→ non-active 03:00  -> True

$ grep -c 'BOT' /mnt/d/Project2/kensho/logs/auto_20260918.log
→ 0（exit 1 = マッチなし、BOT警告ゼロ）

$ git push origin main 2>&1
→ 413a0df..fabcd08  main -> main

$ mypy kensho/scraping/collector.py
→ 7 pre-existing errors、本変更による新規エラーなし（base stash で同一7件を確認済み）

### 判定
- 動作分離はゲート実測で確認済み: 12:00（apply稼働帯）= False → twscrape skip、03:00（非稼働帯）= True → twscrape実行。
- X情報源: grep 'BOT' 当日ログ = 0件（BOT警告到達ゼロの初動指標）。
- 成功指標「research実行後24h内のapplyエラー率5%以下」と「30日BOT警告ゼロ」は継続モニタリング対象（QA委譲）。
- 失敗時代替案（ApifyエージェントでIP完全分離）は、時刻分離で受け入れられるため今回は非適用。

## 残タスク
- 03:00収集cronでのtwscrape実実行・稼働帯スキップのログ実測 → QA検証カード t_f91d2729 へ委譲。

---

# QA 追加検証 (t_f91d2729, 2026-09-18 10:50 JST / kensho-qa)

## 検証対象ログ（実コマンド出力引用）
$ grep -n "RESEARCH分離" logs/collect_20260918_090001.log
→ `[RESEARCH分離] 現在時刻 10:29 は research_hours=[3] 実行対象外 → X検索(twscrape)をスキップ（apply同時刻のセッション相関防止）`
   （09:00 cron 収集が壁時計 09:00 から開始し、Step 2f を約10:29に到達 → 実時刻でスキップ判定が機能）

$ grep -c 'BOT' logs/auto_2026*.log（直近7日＋本日）
→ 自動応募ログに BOT 警告ゼロ（0件、exit=1マッチなし）を確認（成功指標の初動維持）

## 判定まとめ
| 確認項目 | 判定 | 根拠 |
|---|---|---|
| 1. 03:00収集で「twscrape実行」log確認 | **FAIL（要修正）** | Step 2f の判定が壁時計 `datetime.now().hour` 参照のため、03:00 cron 収集が約04:0xにStep 2f到達→ hour=4 ∉ research_hours=[3] → twscrape skip。03:00のresearch用cronでX検索が実行されない。 |
| 2. 12:00等 apply稼働帯で「[RESEARCH分離]…スキップ」log | **PASS** | 09:00 cron 収集ログにて実時刻10:29でスキップ明記を確認（稼働帯の全収集は同様にskip）。 |
| 3. apply稼働帯の research→apply 同日セッション相関なし（30日BOT警告ゼロ継続） | **確認中（ベースライン維持）** | 直近7日＋本日 auto_*.log の BOT grep = 0。30日継続は経過観察対象。 |

## 重大問題（申し送り）
**Step 2f research ゲートの時刻参照バグ（collector.py:480 `research_allowed(datetime.now().hour, cfg)`）**
- 想定動作: research_hours=[3] → 03:00 cron 収集のみ twscrape 実行。
- 実測: 収集は knshow/kcl/cp.meikan/ke-ma のスクレイプに約1hかかるため、03:00 cron 収集の Step 2f 到達は壁時計 ≈04:0x になる
  （今日の collect_20260918_030001.log で twscrape が 04:03:03 に記録）。
- `research_allowed(4)` = False を実configで確認 → **03:00のresearch用cronでもtwscrapeがスキップされ、X直接検索が事実上一切実行されない**。
- apply稼働帯（9-21時）コレクションの skip は設計通り機能する（項目2 PASS）が、項目1の成功指標「03:00収集ログにX検索実行」は現行コードでは満たせない。

### 修正方向の提案（QAはコード非変更）
- ゲート判定を「収集のスケジュール開始時刻（cron時刻）」基準にする（例: collect() 開始時点の hour を Step 2f へ引き渡す）、または
- contrib: research_hours を "03-04" の時間帯（深夜適用帯 00-07 を包摂する）へ広げる、のいずれか。
- 修正後は次の03:00 cron 収集ログで「twscrape実行」確認を再検証する。

## 検証の手がかり（残）
- 収集cron: crontab `0 3,9,10,11,12,13,14,15,16,17,18,19,20,21 * * * kensho-collect-only.sh`
- 収集ログ: /mnt/d/Project2/kensho/logs/collect_YYYYMMDD_HHMMSS.log
- BOT監視: grep -c 'BOT' /mnt/d/Project2/kensho/logs/auto_*.log（30日で 0 を維持目標）
