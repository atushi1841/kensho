# critic v99 実装報告: Gumroad kutuxe 無料サンプル→有料版 agyhq バックリンク + Apify クロスプロモ追記 (t_df2fa4cc)

日期: 2026-09-11 (JST)
作業者: kensho-revenue-worker

## 変更内容
商品 kutuxe（無料サンプル、price 0.0）の説明欄（Product タブ /edit、editors[0] id=:ra:）末尾に2行追記:
1. 有料版バックリンク: "Full dataset (7 marketplaces, weekly updates, 1000+ rows):
   https://atushi5.gumroad.com/l/agyhq ($39.99)"
2. Apify クロスプロモ: "Live API version (pay per event):
   https://api.apify.com/v2/acts/mQaZFo6up4YZKepC3 or store page
   https://apify.com/fruitful_quintessence"

これにより v98 で整備した agyhq→kutuxe の片方向ファネルが双方向に完成（無料訪問者→有料/Apify への回遊導線）。

## 方式
- 実証済みパターン gumroad_sample_link_fix_0911.py（Product タブ editors[0]、id=:ra:）を流用した
  本番スクリプトを新調: /mnt/d/Project2/gumroad-automation/gumroad_kutuxe_backlink_0911.py
- Playwright Firefox headless + /mnt/d/Project2/gumroad-automation/gumroad_cookies.json
  （_gumroad_app_session 失効期限 2026-09-13、実行時有効）
- 実行ログ: 追記前 editors[0] len=122（空説明）→ execCommand=true len=574 → Save changes クリック
  → 追記後 read-back has_agyhq=true

## verification_evidence

$ curl -s https://atushi5.gumroad.com/l/kutuxe -o /tmp/kutuxe_before.html; grep -c agyhq /tmp/kutuxe_before.html; grep -c apify /tmp/kutuxe_before.html
0
0

$ curl -s -o /tmp/kutuxe_after.html https://atushi5.gumroad.com/l/kutuxe; grep -c "agyhq" /tmp/kutuxe_after.html; grep -c "apify" /tmp/kutuxe_after.html; wc -c /tmp/kutuxe_after.html
5
5
22881

$ grep -o 'Full dataset[^<]*' /tmp/kutuxe_after.html | head -1
Full dataset (7 marketplaces, weekly updates, 1000+ rows): https://atushi5.gumroad.com/l/agyhq ($39.99)Live API version (pay per event): https://api.apify.com/v2/acts/mQaZFo6up4YZKepC3 or store page https://apify.com/fruitful_quintessence" inertia="meta-name-description">

$ PLAYWRIGHT_BROWSERS_PATH=... python gumroad_kutuxe_backlink_0911.py (抜粋)
追記対象: DIV :ra: len= 122
追記: execCommand=true len=574
保存: clicked: Save changes
追記後: [{"i": 0, "len": 1612, "has_agyhq": true}, ...]

（og:description / meta description にも両リンクが反映されていることを匿名 curl で確認済み）

## スクリーンショット
- /mnt/d/Project2/gumroad-automation/ss_kutuxe_backlink_main_0911.png
