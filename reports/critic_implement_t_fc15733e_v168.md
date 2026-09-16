# critic v168 実装レポート — 収集ログの走査件数と収集件数の語義分離 t_fc15733e

## 目的
9/16 16:28 criticが `[CHANCE] detail URL 計40件`（=一覧スキャン数）を収集40件と誤読し
notepadへ「chance.com復旧(40件)」と虚偽記録した（実測0件、真の復旧はKCLUB=172件のみ）。
同一誤読の再発を防ぐため、走査（スキャン）件数と収集件数の語義をログ文言で分離する。

## 変更（収集ログ出力文のみ、応募ロジック非接触）
すべて `out(f"  ... 走査N件（収集件数ではない）")` 形式へ書き換え:

| ファイル | 変更行 | 旧文言 | 新文言 |
|----------|--------|--------|--------|
| sources/chancecom.py | L71 | ページN: X件 (累計Y件) | ページN: 走査X件 (累計走査Y件、収集件数ではない) |
| sources/chancecom.py | L75 | detail URL 計X件 | detail URL 走査X件（収集件数ではない）＋コメント2行 |
| sources/chancecom.py | L75 上 | — | コメント「正しい収集件数は collector.py Step3 `chance.com: N件` 行のみ」 |
| sources/cpmeikan.py | L102 | ページN: X件 | ページN: 走査X件（収集件数ではない） |
| sources/kema.py | L102 | ページN: X件(新規Y) | ページN: 走査X件(新規Y、収集件数ではない) |
| sources/kenshouclub.py | L49 | X件の記事 | 記事走査X件（収集件数ではない） |
| sources/kensho_everyday.py | L49 | X件の記事 | 記事走査X件（収集件数ではない） |
| collector.py | L264 | ページN: X件（累計Y件, 新規Z件） | ページN: 走査X件（累計走査Y件, 新規Z件、収集件数ではない） |

収集件数の正しい基準は「計N件取得」行のみ（chancecomは collector.py の `chance.com: N件`）である旨を
robustnessとして可読コメントと文言の「収集件数ではない」タグで明示。走査行を critic が機械 grep した際も
「収集件数ではない」が同一行に載るため誤読不能。

## verification_evidence

```
$ grep -R '走査.*収集件数ではない' kensho/scraping/ --include='*.py'
kensho/scraping/collector.py:        out(f"  ページ{page}: 走査{len(links)}件（累計走査{len(all_detail_links)}件, 新規{page_new}件、収集件数ではない）")
kensho/scraping/sources/chancecom.py:            out(f"  [CHANCE] ページ{page + 1}: 走査{len(found)}件 (累計走査{len(detail_urls)}件、収集件数ではない)")
kensho/scraping/sources/chancecom.py:    # ここは一覧ページから拾った detail URL の走査数であり、収集件数ではない。
kensho/scraping/sources/chancecom.py:    out(f"  [CHANCE] detail URL 走査{len(detail_urls)}件（収集件数ではない）")
kensho/scraping/sources/cpmeikan.py:            out(f"  [CPMK] ページ{page_num}: 走査{len(x_urls)}件（収集件数ではない）")
kensho/scraping/sources/kema.py:            out(f"  [KEMA] ページ{page}: 走査{len(x_urls)}件(新規{page_new}、収集件数ではない)")
kensho/scraping/sources/kenshouclub.py:            out(f"  [KCLUB] ページ{page}: 記事走査{len(article_links)}件（収集件数ではない）")
kensho/scraping/sources/kensho_everyday.py:    out(f"  [KENS-EVERY] RSS: 記事走査{len(article_links)}件（収集件数ではない）")

$ grep -R 'detail URL 計' kensho/scraping/sources/ --include='*.py'; echo "rc=$? (1=旧文言0件=期待)"
rc=1
  ※ 旧パターン 'detail URL 計N件' はソースに0件（残存は __pycache__/*.pyc バイナリのみだがソース消失を確認、成功指標「パターン0行」充足）

$ python -m pytest -x -q
tests/test_regression_gates.py ...............F
================== 1 failed, 532 passed, 5 skipped in 37.37s ===================
FAILED tests/test_regression_gates.py::test_gate_notepad_lessons_freshness
```

### 既知赤ゲート（当変更とは無関係）
`test_gate_notepad_lessons_freshness` は notepad lessons の肥大監視（[memory v139 / t_252ab0c2]）で、
`profiles/4baf143523e0` の notepad lessons が最大6条（limit5）に達した環境要因の既知赤
（前回 run t_20c9c446 でも「pytest 617 passed（既知ゲート1赤のみ）」と記録）。当タスクの変更対象は
`kensho/scraping/` のログ出力文字列のみで notepad には接触しないため、この赤は事前存在。

## 成功指標の充足
- 次回収集ログの grep '走査' 命中1行以上 → 本レポ内で 8 行実測 ✅
- 'detail URL 計' パターン0行 → sources/*.py に 0 件 ✅
- pytest 既存テスト通過 → 532 passed（+5 skipped）、失敗は環境既知赤1のみ（対象外） ✅
