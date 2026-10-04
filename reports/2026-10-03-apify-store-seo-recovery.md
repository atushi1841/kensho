# Apify Store SEO 復旧 — 2026-10-03（実測ベース）

## 結論（先に3行）

1. **Store SEO は「死んで」いなかった。** 30キーワード中27語で自社が検索結果に出現、8語で1〜4位。
   過去2回の「死んでいる」判定は、どちらも API の読み違いだった（下記「罠」参照）。
2. **本当の律速は順位ではなく需要。** 最大需要のキーワード「mercari japan」でも
   **上位5件の合計 users30d = 50/月**。需要がある語では我々は18〜20位、順位が良い語は需要がほぼ0。
3. **文言を直しても順位は動かなかった（実測 ±0位）。** 順位を決めているのは users30d
   （mercari: 自社1 vs 1位29）。つまり Store 内SEOは上限が低く、伸ばすべきは「外から人を連れる導線」。

## 1. 直したもの（すべて read-back 検証済み）

| 対象 | 症状 | 対応 | 検証 |
|---|---|---|---|
| `scripts/apify_seo_audit.py` | **401 で1本も動かず**（actors=0） | `get_apify_token()` を恒久修正: 絶対パスの `.env` を読み `APIFY_TOKEN`→`APIFY_TOKEN_DEFAULT` の順でフォールバック | 再走で **78本 / 149件** の改善候補を検出 |
| `mercari-japan-search-scraper` の説明文 | 末尾が壊れ文（`...Pay-per-event per item scraped largest.`、201字） | 人間品質の277字に書き直し | PUT 200 / read-back 一致 / 語尾「`Billing is pay-per-result.`」 |
| カテゴリ空き枠 3本 | カテゴリが2個しか無く、競合が使う語が入っていない | 空き枠に充填（`ai-model-price-api`, `japan-mhlw-medical`, `japan-crowdfunding-trend-feed`） | PUT 200 / read-back 一致 |
| `japan-minimum-wage-mcp` のカテゴリ | （自分の検証操作で一時的に既存3個を消した） | 和集合で復元 → 最終的に元の3個に確定 | read-back `['MCP_SERVERS','DEVELOPER_TOOLS','AI']` |

**新設した計器**（次回以降の前後比較用）
- `scripts/apify_store_rank.py` — 指定キーワードでの自社順位を実測（`--compare` で前後比較）
- `scripts/apify_store_opportunity.py` — 需要×勝てるか でキーワード機会を並べる
- `scripts/apify_seo_desc_repair.py` — 壊れた説明文の検出と修復（`--apply`）

## 2. 実測データ

### 2-1. 順位（30キーワード走査、depth 100）
```
keyword                       需要(top5u30)  当社順位  1位
mercari japan                          50        18   mercari-japan-scraper        ←弱い
yahoo auctions japan                   24        20   yahoo-auctions-sold-scraper  ←弱い
japan real estate                      14         9   suumo-scraper
japan kakaku price                      6         1   自社(cn)
japan weather api                       5         2
japan car price                         5         2
nendoroid price                         5         2
japan used instrument guitar            4         1   自社
mandarake                               4         1   自社
japan spent camera                      4         2
anime figure price                      3         1   自社(1位が自社でu30=0)
...
japan hotel price                       4       圏外   当該アセットが無い（コピーでは解決しない）
```

### 2-2. なぜ mercari は18位なのか
```
mercari japan 1位 = mercari-japan-scraper  users30d=29 / runs=133,051
自社            = mercari-japan-search-scraper users30d=1  / runs=153
→ 使用実績が2桁違う。タイトルは両者とも "Mercari Japan ... Scraper" で語は既に揃っている。
```

### 2-3. 文言修正の効果測定（mercari の説明文を201→277字に改善）
```
keyword                    before    after  差
mercari japan                  18       18  +0位
yahoo auctions japan           20       20  +0位
japan used camera               2        2  +0位
anime figure price              1        1  +0位
```
→ **順位は文言では動かない。** 149件の改善候補のうち copy 系（missing_keywords 49、
title_keyword_gap 19、short_description 25）を全部適用しても、期待できるのは
「圏外→出現」だけで順位上昇は見込めない。この事実は投資判断として重要。

## 3. API の罠（3つ。すべて実測で確定）

| 罠 | 誤った読み | 正しい読み |
|---|---|---|
| 一覧APIの `isPublic` | 88本すべて非公開に見えた | **詳細API** `/acts/{user}~{name}` で1本ずつ。実際は78本が公開 |
| 一覧APIの `description` | 壊れた説明文が0件に見えた | 詳細APIで読む。mercari は詳細でのみ検出できた |
| 無認証の `/v2/store` | `items=[]` ＝ Store非掲載と誤判定 | count は返るが items は空。**認証付きなら count=77/items=77** |

さらに `categories` は **最大3個**（4個目で HTTP 400）。既に3個埋まっているアクターは
入れ替え判断が必要で、34件の missing_categories のうち実際に充填できたのは空き枠のあった3本のみ。

## 4. 結論と次の一手（推奨）

Store 内SEOは上限が低い。理由は実測で明確:
- 需要そのものが小さい（最大の語でも上位5件合計 50人/月）
- 自社は主要語にほぼ全部出ている（27/30）＝ これ以上「入る」余地が少ない
- 順位は使用実績で決まり、それは Store 内の文言では作れない

したがって伸ばすべきは **Store の外から人を連れてくる導線**。優先順:
1. **MCP ディレクトリへの登録**（Smithery / Glama / mcp.so 等）
   — 自社は MCP 系アクターを持ち、今まさに人が探している場所。Store SEOより期待値が高い
2. **dev.to 既存3記事 → 該当 Store ページへの内部リンク**（記事は生存確認済み HTTP 200）
3. **X でのピンポイント告知**（W40で実績あり。UTMで計測済み）

## verification_evidence

```
$ python3 scripts/apify_seo_audit.py --csv ... --json ...   → actors=78 findings=149（401修正後）
$ python3 scripts/apify_store_rank.py（mercari）             → 18位 / 説明文改善後も 18位（+0）
$ python3 scripts/apify_store_desc_repair.py                 → 走査86本 / 対象0本（修復完了）
$ python3 scripts/apify_store_opportunity.py                 → 30語走査・27語で自社出現
$ python3 -c "GET /acts/ODh1F4XP5sLlXu6Ep"                   → categories=['MCP_SERVERS','DEVELOPER_TOOLS','AI']（復元）
$ python3 -c "PUT categories に4個目"                        → HTTP 400（上限3の実測）
$ python3 -c "GET /acts/fruitful_quintessence~mercari-..."   → description 277字 / read-back 一致
```
