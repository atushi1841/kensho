# 収益化QA検証結果: 2026-09-02（4回目・09:2x実行）

> 収益化QA Agent（kensho-revenue-qa）検証記録
> 前回QA（07:15）の「PPE未適用」判定を覆す重大な再検証結果

## 検証サマリー

| 検証項目 | 前回判定(07:15) | 今回実測(09:2x) | 備考 |
|---------|----------------|----------------|------|
| Apify PPE課金適用 | **未適用**（pricingInfo空） | **適用済み 57/61件** | 前回は名前ベースAPIが失敗しただけ |
| ターゲット5アクター | pricing={} | 全$0.002/件・isPublic=True | camera/watch/luxury/instrument/offmall |
| pay_per_event.json | 表示名のまま（不一致） | **実API名に修正済み** | QA指摘対応完了 |
| Gumroad価格 | 14.99ドルのまま | **9.99ドル（bundle_info更新）** | 実行痕あり・実ページ未確認 |
| RapidAPI公開化 | 未着手 | 未着手（blocked継続） | t_82ce3202 |
| nightly-worker 402 | 残高不足 | — | フォールバック鎖は正常系に復帰か |

## Apify実測（2026-09-02 09:1x・全61件IDベース再検証）

- **方法の訂正**: 前回QAは `/v2/acts/{アクター名}`（名前ベース）で個別APIを呼び、`record-or-token-not-found` が返ったため「pricingInfo空」と誤判定した。**正しくは `/v2/acts/{アクターID}`（IDベース）で呼ぶ必要がある**（名前では解決できない）。
- **結果**: 61件中57件にPPE課金（PAY_PER_EVENT）が適用済みであることを確認。
  - ターゲット5アクター: `japan-used-camera-market-scraper` / `japan-watch-market-scraper` / `japan-luxury-brand-market-scraper` / `japan-used-instrument-market-scraper` / `japan-offmall-market-scraper` → すべて **$0.002/件（apify-default-dataset-item）・isPublic=True**
  - `japan-market-mcp`（runs=587・最大使用）: イベント課金 $0.001（camera/watch/luxury/instrument-market-search）
  - `surugaya-japan-hobby-prices`: isPublic=False だが課金設定あり（$0.01/surugaya-search）
  - **未適用4件のみ**: dmm-scraper / rakuten-market-scraper / rakuten-debug-fetch / tabelog-debug-fetch（すべて非公開・デバッグ系）
- **pay_per_event.json**: 実API名に修正済み。noteに「全アクター既にPPE適用済み」と明記。

## Gumroad実測

- `bundle_info.json`: price=**9.99**・price_updated_at=2026-09-02 ✅
- 実行痕: `ss_price_done.png`(08:53) / `ss_price_verify.png`(08:59) / `ss_price_error.png`(08:32) → 08:32エラー後、08:53-08:59に再試行成功の痕跡
- **未確認**: 公開ページでの最終価格（商品URL不明・Gumroad APIは401で外部確認不能）。CDPでの実ページ確認が残務

## RapidAPI実測

- 21本（公開20・非公開1）・全FREEMIUM。前回から変化なし。
- 非公開: Japan OffMall Used Goods Price Stats API (Chinese)（t_82ce3202 block継続）

## 3軸評価（収益化QA）

```json
{
  "evaluation": {
    "technical": {
      "score": 8,
      "assessment": "Worker実装は実は正しかった。PPE課金57/61件適用済み・pay_per_event.jsonは実API名に修正済み。前回QAの検証方法（名前ベースAPI）に問題があった。残課題はGumroad実ページ確認のみ",
      "evidence": "curl /v2/acts/{ID} で全61件検証。ターゲット5アクター全$0.002/件・isPublic=True。未適用は非公開デバッグ系4件のみ"
    },
    "business_kpi": {
      "score": 6,
      "assessment": "57アクターへのPPE課金により使用量×課金の収益基盤が確立。ただし現状売上0のまま。RapidAPI非公開1本の公開化・Gumroad告知が次の収益トリガー",
      "evidence": "revenue-daily.json: 売上$0継続。PPE課金は今後の使用量に応じた収益（現時点の実売上はゼロ）"
    },
    "cost_efficiency": {
      "score": 7,
      "assessment": "検証コストは妥当（API呼び出し~70回）。ただし前回QAの誤判定により再検証コストが発生。QA側の検証手順に名前ベース→IDベースの教訓を反映すべき",
      "evidence": "本QAで61件のIDベース検証+個別確認を実施。前回QAとの二重作業が発生"
    }
  },
  "self_review_quality": {
    "valid": false,
    "notes": "前回QA(07:15)の自己レビューに検証方法の誤りあり。名前ベースAPIのnot-foundを「pricingInfo空」と誤判定し、Workerの正しい実装を「未適用」と誤って報告した。エラー応答（record-or-token-not-found）を正しく解釈できていなかった"
  },
  "verdict": "conditional_pass",
  "next_steps": [
    "Gumroad実ページで価格9.99ドルを最終確認（CDPまたは公開URL特定）",
    "QA検証手順に「Apify個別APIはIDベースで呼ぶ」を明記（notepad教訓済み）",
    "RapidAPI非公開1本の公開化（t_82ce3202）を次の収益Workerで着手",
    "Gumroad Reddit告知（t_f1005efc）ブロック解除の推進"
  ]
}
```

## 判定

**conditional_pass（実装は正しい・QA検証方法に要修正）**

Workerの実装（PPE課金57件・Gumroad価格9.99ドル）は実測で確認できた。前回QAの「未適用」報告はQA側の検証ミスであり、Workerを責めるべきではない。残る未確認はGumroad公開ページの最終価格のみ。

## 教訓（notepad保存済み）

- **Apify個別APIは名前ではなくIDで呼ぶ**: `/v2/acts/{name}` は record-or-token-not-found を返すが、これは「存在しない」ではなく「名前解決不可」。`/v2/acts/{id}` で取得すること。リストAPI（`/v2/acts?my=true`）からIDを得る
- 前回QAの誤判定により、誤った申し送り（「PPE未適用」）が1日分記録された。**検証失敗時はエラー応答自体を確認してから「空」と判断する**
