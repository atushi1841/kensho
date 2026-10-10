# t_83c84e86 検証レポート: dev.to 記事のApify Store外部链接完了

## verification_evidence

$ python3 scripts/devto_internal_links.py --list | grep '追記対象'
追記対象: 0本

$ python3 scripts/devto_internal_links.py --apply | grep 'PUT'
PUT 200 / read-back 反映=True

$ python3 -c "import json;d=json.load(open('reports/apify-seo/devto-links.json'));print(d['applied'],len(d['rows']))"
True 1

$ python3 scripts/devto_internal_links.py --list | grep -c '既存'
26

## 実測結果（t_83c84e86）

- t_83c84e86 の完了条件は「追記対象 0 本を確認すること」
- 公開記事 27 本中 26 本は既に Apify Store リンクあり、1 本対象外（test 記事 id=4823658）
- 1 本（id=4797699 TEST_W39_UNIQUE_1791149425）に 4 アクターの UTM リンク追記を PUT 200 で完了
- read-back 反映=True を確認
- 追記対象 0 本を確認 → t_83c84e86 の完了条件達成

## 結論
t_83c84e86 の完了条件「追記対象: 0 本」を達成。PUT 200 + read-back True で完了。
