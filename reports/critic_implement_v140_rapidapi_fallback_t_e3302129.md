# critic v140: RapidAPI収集 read timeout→last-known-stateフォールバック — 実装記録 (t_e3302129)

- 変更1: scripts/kensho_revenue_collect.py — collect_rapidapi() をリトライ対応に再構成。
  GraphQL取得を `_rapidapi_fetch_apis()` に分離し、失敗時リトライ1回（backoff 5秒、
  RAPIDAPI_MAX_RETRIES/RAPIDAPI_RETRY_BACKOFF定数）。全試行失敗時は
  data/revenue_rapidapi_state.json（成功収集時のみ保存されるlast-known-state）を復元し、
  apis_total を0にしない。error / fallback="last_known_state" /
  fallback_state_saved_at / last_known_total / last_known_error を結果に記録。
- 変更2: build_revenue_summary() 頂層に collectors 健全性レコード
  （apify_ok/rapidapi_ok/gumroad_ok＋フォールバック発動時は
  rapidapi_cache_fallback/state_saved_at/rapidapi_error と last_known_total/last_known_error、
  警告文言も追加）。rebuild時にキャッシュフォールバックであることを頂層で判別可能にする。
- 根拠: 9/13 03:45 run で read timeout (timeout=15) → apis_total=0 虚偽報告を実測
  （直前5日間は22で安定）。t_88424523 の last_status=ok と矛盾していた。
- テスト: tests/test_revenue_collect.py に TestV140RapidapiFallback 5件 +
  TestV140CollectorsTopLayer 2件追加（成功時state保存、初回timeout→リトライ復旧、
  全滅→state復元、state無し→0維持、auth欠如即return、頂層collectors/last_known記録）。

## verification_evidence

（t_e3302129 実装検証：pytest回帰 + 本番スクリプトlive実行 + 受け入れコマンド相当のjq確認）

```
$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_revenue_collect.py -q
============================== 50 passed in 9.16s ==============================
```

```
$ python3 -m pytest tests/test_revenue_collect.py -q -k V140 -p no:cacheprovider 2>&1 | grep -E "passed|failed"
======================= 7 passed, 43 deselected in 8.95s =======================
```

```
$ python3 scripts/kensho_revenue_collect.py  # 04:50 live実行（抜粋）
▶ RapidAPI収集...
  ✓ API数: 23
      公開: 20, 非公開: 3, FREEMIUM: 23
✓ revenue-daily.json 更新完了 (12 entries, 日付: 2026-09-13)
```

```
$ jq -c '{date: .[-1].date, apis_total: .[-1].rapidapi.apis_total, collectors: .[-1].collectors}' data/revenue-daily.json && jq -c '{saved_at, apis_total}' data/revenue_rapidapi_state.json
{"date":"2026-09-13","apis_total":23,"collectors":{"apify_ok":true,"rapidapi_ok":true,"gumroad_ok":true}}
{"saved_at":"2026-09-13T04:57:56","apis_total":23}
```

受け入れコマンド（`d[-1].rapidapi.apis_total` / state の apis_total）は 23 / last_known=23。
想定値22に対し+1されたのは収集時に実APIが23本（中国語・韓国語・ポルトガル語版含め
t_25a7704e 以降1本増）であるためで、「0ではない・last_known一致」の成立条件は満たす。

```
$ python3 -m mypy scripts/kensho_revenue_collect.py 2>&1 | tail -1
Found 2 errors in 1 file (checked 1 source file)
```
（2件はHEAD時点から存在する既存エラー: requests stub欠落 / 既存type:ignore unused。
 git show HEAD版へのmypy実行で同一2件を確認済み＝本変更で新規増加ゼロ）

```
$ git diff --stat scripts/kensho_revenue_collect.py tests/test_revenue_collect.py
 scripts/kensho_revenue_collect.py | 208 ++++++++++++++++++++++++++++----------
 tests/test_revenue_collect.py     | 128 +++++++++++++++++++++++
```

## 申し送り

- フォールバック経路（全滅→state復元・頂層last_known_*）はユニットテストで検証済み。
  本番での自然発動は次回timeout時に revenue-daily.json の collectors.rapidapi_cache_fallback
  で確認できる（QAカードで追検証）。
- Gumroad CDP収集は今回のrunでもtimeout-mark（前回値使用・既存v60設計どおり、本カード対象外）。
