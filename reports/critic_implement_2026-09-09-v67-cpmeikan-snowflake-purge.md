# critic v67 実装報告 — cpmeikan deadline 空・滞留パージ（snowflake 年齢 14d）

タスク: t_b1bb39d0 | 実装日: 2026-09-09 | commit: c126bbd

## 背景 / エビデンス
- cp.meikan 一覧ページは期限を抽出できず deadline 空のまま滞留。`_is_expired(deadline="")` は
  False を返すため期限切れ除去をすり抜け、収集のたびに同一ツイートが再生成されて
  backfill(03:45)の成果を毎朝リセットする（非空率 82.5% → 7.8% の振動）。
- 実装前ベースライン（operator 04:55 補足 + 実測一致）: deadline_empty=83 / stale_gt14d=57 / total=602。

## 実装（提案A・本命）
`kensho/scraping/collector.py` マージ後パージ（L497付近）を二段に拡張:
- `_is_expired(deadline)` — 従来の日付ベース除去（変更なし）
- `_is_stale_empty_deadline(item, now)` — deadline 空 かつ
  `_snowflake_ts_ms(tweet_id)` で復元した生成時刻が `_STALE_TWEET_DAYS=14` 超なら除去。

snowflake 復元: `(int(tweet_id) >> 22) + 1288834974657`。閾値は定数化（失敗時 21日へ緩和可能）。

対象は全ソースだが、deadline 空は cpmeikan 83件（他ソース 0件）なので実質 cpmeikan 専用。
applier・応募ロジックには一切触れない（リスク低）。

提案B（backfill_local への cpmeikan 明示許可）は A で本命が解消されるためスキップ
（提案側も A 導入後は任意と明記）。

## 検証（実測）
- テスト追加: tests/test_collector.py に `TestSnowflakeStalePurge` 5件（roundtrip / stale>14d True /
  recent<14d False / deadline 有は委譲 / 非数値 id False）。
- pytest 全件: 489 passed, 5 skipped（実装前と同数、回帰なし）。
- ruff check / ruff format: Passed（pre-commit hook 両方）。
- 実データシミュレーション（未コミットの collected.json に実関数適用）:
  - total 602 → 545（57件除去、90.5% = ±20%帯内）
  - cpmeikan deadline 空 83 → 26（残りは生成日<14日でapply対象として適切に維持）
  - = operator ベースライン stale=57 と完全一致。QA は次回収集 tick 後に stale_gt14d=0 を確認。

## 注意点
- タスク body の QA 1行コマンドは TypeError を含む（`<<` を float に適用 → unsupported operand）。
  正しくは閾値 `int` 化してから `<< 22` する。QA 再現コマンド固定版:
  python3 -c "import json,time;d=json.load(open('data/collected.json',encoding='utf-8'));no=[i for i in d['collected'] if not i.get('deadline') and str(i.get('source'))=='cpmeikan'];cut=int((int(time.time()*1000)-14*86400*1000-1288834974657)<<22);old=[i for i in no if str(i.get('tweet_id','')).isdigit() and int(i['tweet_id'])<cut];print('deadline_empty',len(no),'stale_gt14d',len(old))"

## 残タスク
- collected.json は現状 57件の stale が残存（収集は次 tick まで走らないため）。次回収集でパージされる。
  成功指標1（実装翌日以降2 tick 連続で stale=0）は 9/10 の収集後に QA が確認する。
