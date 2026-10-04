# t_e2b43c47: Apify Actor Description SEO Boost + dev.to Cross-Posting

## verification_evidence

$ python3 scripts/apify_seo_full_apply.py --apply --limit 0 --sleep 0.2
total=86 changed=86 applied=86 failed=0
csv: reports/apify-seo-full/apify-seo-full-2026-10-04.csv

$ curl -s https://dev.to/api/articles/4794070 -H "User-Agent: Mozilla/5.0" | python3 -c "import json,sys; d=json.load(sys.stdin); print('ID:', d['id'], '| Title:', d['title'])"
ID: 4794070 | Title: Apifyで日本市場の価格データを自動収集: 86個のアクターを公開

$ curl -s https://dev.to/api/articles/4794072 -H "User-Agent: Mozilla/5.0" | python3 -c "import json,sys; d=json.load(sys.stdin); print('ID:', d['id'], '| Title:', d['title'])"
ID: 4794072 | Title: MCPサーバー6本をMCP公式レジストリに登録した結果

$ curl -s https://dev.to/api/articles/4794073 -H "User-Agent: Mozilla/5.0" | python3 -c "import json,sys; d=json.load(sys.stdin); print('ID:', d['id'], '| Title:', d['title'])"
ID: 4794073 | Title: 懸賞応募自動化のリアル: 3万円の収益を生んだコード

$ python3 scripts/devto_internal_links.py --apply
公開記事: 8本
要追記 id=4794073 ... PUT 200 / read-back 反映=True
対象外 id=4794072 ... 既存
既存 id=4794070 ... 既存

$ python3 -c "import json; d=json.load(open('reports/apify-seo-full/apify-seo-full-2026-10-04.json')); print('applied:', sum(1 for x in d if x.get('status')=='applied'), '/', len(d))"
applied: 86 / 86

## 成果物

- reports/apify-seo-full/apify-seo-full-2026-10-04.json (86 actors updated)
- reports/apify-seo/devto-links.json (1 link applied)
- dev.to article URLs:
  - https://dev.to/atu_ino_ed473db24d76d234a/apifyderi-ben-shi-chang-nojia-ge-detawozi-dong-shou-ji-86ge-noakutawogong-kai-56hh
  - https://dev.to/atu_ino_ed473db24d76d234a/mcpsaba6ben-womcpgong-shi-rezisutorinideng-lu-sitajie-guo-2lph
  - https://dev.to/atu_ino_ed473db24d76d234a/xuan-shang-ying-mu-zi-dong-hua-noriaru-3mo-yuan-noshou-yi-wosheng-ndakodo-3b0c

## outcome

- metric: apify_descriptions_updated
- before: 0
- after: 86
