# t_c4e810c6 検証エビデンス — 収集元別内訳可視化 & 即時フィルタUI

Task: [機能強化] 懸賞ダッシュボード(kensho-status.html)の収集元別内訳可視化&即時フィルタUIの実装
Date: 2026-09-23

## 実装内容
- `scripts/gen_status_data.py`: 収集元別内訳パネル用 `stats.source_stats`(label/total/applied/pending/dup/new_today)・`stats.items_by_source`・フィルタ用案件リスト `items`(source/source_display/deadline_days/winner_count/applied/high_prio) を出力。本日新着は `data/status/source_new_day.json` の初回run基準増分で算出。
- `scripts/gen_status_html.py`: 収集元カード(`.source-button[data-source]`)+収集元別内訳テーブル(`.filterable-item.src-row[data-sources]`)+案件リスト(`.filterable-item.filter-row[data-sources][data-winc][data-dl]`)にレンダリング。軽量JS(`filterBySource`/`setWinner`/`setDeadline`/`applyFilters`)で当選人数(100/1000人以上)・締切(本日/3日以内)・収集元で即時絞込。QA指摘(JS定義のみでレンダリング欠落)を解消。

## verification_evidence
```
$ python3 -m py_compile scripts/gen_status_data.py scripts/gen_status_html.py
  -> PY_COMPILE OK
$ python3 scripts/gen_status_data.py
  -> DATA_OK
$ python3 scripts/gen_status_html.py
  -> [OK] /mnt/d/Project2/kensho/kensho-status.html (827869 bytes)
$ grep -o "source-button" kensho-status.html | wc -l
  -> 10 (9収集元ボタン+JS定義)
$ grep -o "filterable-item src-row" kensho-status.html | wc -l
  -> 9
$ grep -o "filterable-item filter-row" kensho-status.html | wc -l
  -> 1162
$ grep -o "data-sources=" kensho-status.html | wc -l; grep -o "data-winc" kensho-status.html | wc -l
  -> 1171 / 1162
$ grep -o "filterBySource\|setWinner(\|setDeadline(" kensho-status.html | wc -l
  -> 10 / 4 / 4
$ grep -o "収集元別 有効" kensho-status.html | wc -l
  -> 1 (source_statsパネルrendering確認)
$ python3 /tmp/_check_tc4.py  (JSON payload検証)
  -> source_stats keys: [unknown,knshow,kenshouclub,cpmeikan,kensho-everyday,kema,ken-kaku,chancecom,twscrape]
  -> knshow total=82 pending=37 / kenshouclub total=288 pending=180 / cpmeikan total=12 / kema total=18
  -> items (filter rows): 1162
```

## 結論
3要件すべて充足。
1. 収集元別内訳可視化: source_statsパネル(有効/重複/本日新着)をkensho-status.htmlにレンダリング確認。
2. 即時フィルタUI: 当選人数・締切・収集元の3条件でブラウザ側JSにより即時絞込(クラス/属性のレンダリングをgrepで確認)。
3. データ更新フロー: gen_status_data.py→gen_status_html.py がエラーなく実行され、最新集計がHTML(827KB)へ反映。
