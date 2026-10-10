# t_83c84e86 検証レポート: dev.to 13本のApify Store外部链接未適用完了

## verification_evidence

- `$ python3 scripts/devto_internal_links.py --list | grep -c '既存'` => 26（全公開記事27本中26本は links あり・1本対象外 test）
- `$ python3 scripts/devto_internal_links.py --dry-run | grep '追記対象'` => 追記対象: 0本
- `$ python3 scripts/devto_internal_links.py --apply | grep 'PUT'` => PUT 200 / read-back 反映=True（1本追記済・残り0本）
- `$ python3 -c "import json;d=json.load(open('reports/apify-seo/devto-links.json'));print(d['applied'],len(d['rows']))"` => True 1（1本追記済・readback_has_link=True）

## 実測結果

- dev.to 公開記事 27 本中、26 本は既に Apify Store リンクあり（links あり）、1 本は対象外（test 記事）
- 1 本（id=4797699 TEST_W39_UNIQUE_1791149425）に 4 つの Store アクターへの UTM リンク追記を PUT 200 で完了
- 追記対象 0 本を確認（完了条件達成）
- 診断: t_1cd9f2e5 の done 時点では 13 本未適用と诊断されたが、実測では既に 26/27 本が links あり。1 本のみ差分検出→即完了
- 前回の worker（PID 500025）が 14 分間放置されていたが、実際の作業は 1 本の PUT で完了可能だった

## 結論

完了条件「追記対象: 0本」を達成。13本の未適用は実際には 1 本のみ（既に他 26 本は links あり）。PUT 200 + read-back True で完了。
