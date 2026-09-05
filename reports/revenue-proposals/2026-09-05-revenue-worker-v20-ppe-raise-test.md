# revenue-worker PPE 価格値上げ A/B テスト記録 (2026-09-05)

## タスク
- Kanban: `t_c4343276`「Apify価格値上げテスト」（本件）
- 仕様元: `t_ed0e05b2`（critic v19-C: japan-offmall PPE price 0.002→0.005 USD A/B test）

## 実施内容
critic v19-C 仕様どおり、需要最大の `japan-offmall-market-scraper` のみを
PPE 単価 **$0.002/件 → $0.005/件**（2.5倍）に値上げした。他上位4本（camera/watch/luxury/instrument）は $0.002/件 のまま = 対照群。

### 変更前スナップショット（全5本、全て公開・PAY_PER_EVENT・margin 0.2・単エントリ）
| アクター | ID | datasetItemUsd |
|----------|-----|-----------------|
| japan-offmall-market-scraper | Zh4kqcS4dYPWpFzBd | 0.002 → 0.005 |
| japan-used-camera-market-scraper | mQaZFo6up4YZKepC3 | 0.002 |
| japan-watch-market-scraper | gMqdrS2evpcybSZc2 | 0.002 |
| japan-luxury-brand-market-scraper | b0vuqa3ESvy2mOwFB | 0.002 |
| japan-used-instrument-market-scraper | yN1R26HrV6C2MBKas | 0.002 |

### 変更（Apify API 直接 PUT、既存+新規エントリ方式）
```
PUT /v2/acts/Zh4kqcS4dYPWpFzBd  {"pricingInfos": [旧エントリ, 新エントリ]}
新エントリ: apify-default-dataset-item.eventPriceUsd = 0.005
            createdAt/startedAt = 2026-09-04T15:55Z（= 9/5 00:55 JST）
```

### 変更後検証（外部 read-back、9/5 実測）
- offmall: raw GET で `pricingInfos` が2エントリ化
  - `[0]` createdAt=2026-08-10  datasetItemUsd=0.002（旧）
  - `[1]` createdAt=2026-09-04T15:55Z  datasetItemUsd=0.005（**有効・最新**）
- 対照群4本: 単エントリ $0.002 のまま（変更なし）を再確認
- isPublic=True（公開維持）、apifyMarginPercentage=0.2 維持

## 付随バグ修正：収集スクリプトが旧エントリを読む問題（重要）
`scripts/kensho_revenue_collect.py` の `fetch_apify_pricing()` が
`pricing_infos[0]`（先頭エントリ）を単価として読んでいた。
値上げで offmall が2エントリ化したため、そのままでは日次収益計測が
**旧 $0.002/件**を読み、A/B の7日後判定リスク・復帰誤判断の元になる。

→ **有効価格は最後（最新）の pricingInfos エントリ**として `[-1]` に修正。
（skill に複数回記載の落とし穴: 「価格確認は最後のエントリが有効」。）

加えて `pay_per_event.json`（API失敗時のフォールバック）の
offmall 単価を 0.002→0.005 に更新。

### テスト（tests/test_revenue_collect.py に追加）
- `TestFetchApifyPricing::test_uses_last_entry_as_active_price` — 2エントリ化した
  actor で最後エントリ（$0.005/件）を有効単価として返すことを mock で検証。
→ **PASS 確認済み**（.venv/bin/python -m pytest）
- ファイル内の他19テストは PASS（`TestMainIntegration` 3件は事前からのハング:
  main() が `update_gumroad_state_via_cdp()`＝Chrome/CDP起動を mock していない
  既存問題で、本変更と無関係）。

## ベースライン（判定アンカー、9/5 realtime）
`GET /v2/acts/{id}/runs` 直近7日ウィンドウ:
| アクター | 7d total | 7d external |
|----------|----------|--------------|
| offmall（値上げ対象） | 35 | 0 |
| camera（対照） | 7 | 0 |
| watch（対照） | 7 | 0 |
| luxury（対照） | 7 | 0 |
| instrument（対照） | 7 | 0 |

※ 外部ユーザー run は全アクター0件（既知の通り外部需要がまだ0）。
値上げの即時収益効果は理論値（外部利用発生時のみ顕在化）。判定は
total runs を需要プロキシとして使う。

## 判定ルール（critic v19-C 仕様）
- **7日後（9/12 00:55 JST 以降）** 再評価
- offmall の run が **30%超下落** → $0.002/件に復帰
- 下落が30%未満 or 横ばい/増加 → 値上げ維持（$0.005/件継続）
- 追跡データ源: `data/revenue-daily.json`（日次収集。本修正後は offmall=$0.005 で計測）

### 復帰コマンド（必要時）
`python3 ppe_test.py raise_price Zh4kqcS4dYPWpFzBd 0.002`
（確認: `python3 ppe_test.py raw Zh4kqcS4dYPWpFzBd`）

## 申し送り
- t_ed0e05b2（critic v19-C 仕様カード）は本実装で実行済み。重複再実行を避けるためコメント・統合要。
- 7日後判定は新規カード `t_<recheck>` に委譲（作成済み）。
- 収益0の根本は外部ユーザー0件（58アクター全run自己起因）。値上げA/Bは歪み検証であり、需要側施策（SEO/露出）が並行必須。
