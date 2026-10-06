# t_7658589a verification — dev.to SEO link addition

## verification_evidence

タスクID: t_7658589a

### 実施内容
dev.to週次SEO投稿パイプライン（scripts/devto_weekly_pipeline.py / scripts/publish_devto.py）に、Apify PPEアクターへの外部リンク追記を確認。

### 検証コマンド
$ python3 scripts/devto_internal_links.py --list
対象外: 31記事 / 追記対象: 0本
（全記事に apify.com/fruitful_quintessence リンク済）

$ cat reports/apify-seo/devto-links.json | python3 -c "import json,sys;d=json.load(sys.stdin);print('applied:',d.get('applied'),'| rows:',len(d.get('rows',[])))"
applied: True | rows: 0

$ grep -rl "apify.com/fruitful_quintessence" reports/journalism/drafts/ | wc -l
31

### 結果
全31記事にApify Storeリンク追記済み。追記対象0本 → 完了。
