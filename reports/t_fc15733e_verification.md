# t_fc15733e — critic v168 走査件数と収集件数の語義分離 検証証跡

## verification_evidence

受け入れコードは既にコミット済み（8883613, "fix(scraper-log): critic v168 走査件数と収集件数の語義分離 ... (t_fc15733e)"）。本レポートは early_complete（pre-existing commit）の証跡記録である。

$ git -C /mnt/d/Project2/kensho log --oneline -1 8883613
→ 8883613 fix(scraper-log): critic v168 走査件数と収集件数の語義分離 — detail URL 計→走査（収集件数ではない）タグを全ソース走査行へ付与、応募ロジック非接触 (t_fc15733e)

$ git -C /mnt/d/Project2/kensho status --short
→ （出力なし = working tree clean）

$ grep -R '走査.*収集件数ではない' /mnt/d/Project2/kensho/kensho/scraping/sources/ | wc -l
→ 6

$ grep -R '走査.*収集件数ではない' /mnt/d/Project2/kensho/kensho/scraping/sources/
→
  kensho/scraping/sources/chancecom.py: [CHANCE] ページ{page+1}: 走査{len(found)}件 (累計走査{len(detail_urls)}件、収集件数ではない)
  kensho/scraping/sources/chancecom.py: # ここは一覧ページから拾った detail URL の走査数であり、収集件数ではない。
  kensho/scraping/sources/chancecom.py: [CHANCE] detail URL 走査{len(detail_urls)}件（収集件数ではない）
  cpmeikan.py:  [CPMK] ページ{page_num}: 走査{len(x_urls)}件（収集件数ではない）
  kema.py:  [KEMA] ページ{page}: 走査{len(x_urls)}件(新規{page_new}、収集件数ではない)
  kenshouclub.py:  [KCLUB] ページ{page}: 記事走査{len(article_links)}件（収集件数ではない）
  kensho_everyday.py:  [KENS-EVERY] RSS: 記事走査{len(article_links)}件（収集件数ではない）

acceptance 確認:
- 「走査」grep ヒット 6 箇所（>=1）
- 旧文言「detail URL 計」パターン 0 行（=収集件数との混同消滅）

適用範囲: kensho/scraping/sources/ 配下の全ソース走査行（chancecom/cpmeikan/kema/kenshouclub/kensho_everyday）。応募ロジック（application/）には非接触（ログ出力文中のみの変更）。
