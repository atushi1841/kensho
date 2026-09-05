# 収益化QA検証レポート v7（2026-09-03 21:13 JST）

> 検証対象: t_edc8919c（Apify非公開3アクターの公開化 / dmm-scraper outputSchema準備）
> 担当: kensho-revenue-worker / 検証: kensho-revenue-qa (033ff6065ef7)

## 検証サマリー

**判定: conditional_pass**

Workerのdmm-scraper outputSchema実装（build 0.1.8 SUCCEEDED）は実測で**完全に動作**。ただし公開（isPublic=true）自体はApifyの日次公開上限（5件/日）に達しており本日中に完了できず、明日の再実行が必須。この「実行未完」はWorkerの欠陥ではなく外部制約であり、実装品質は高い。

## 実測エビデンス（すべてAPI実測）

| 検証項目 | 結果 | 方法 |
|---------|------|------|
| dmm-scraper build 0.1.8 | **SUCCEEDED** ✅ | GET /v2/acts/nUm22B2guMo8vXom6/builds |
| build 0.1.6 / 0.1.7 | FAILED（報告どおり） | 同上 |
| dmm-scraper isPublic | False（公開待ち・報告どおり） | GET actor |
| rakuten-market-scraper | isPublic=False（明日公開待ち） | GET actor |
| japan-figure-plamo | isPublic=False（tagged-build未対応・低優先） | GET actor |
| japan-rent-market-scraper | **isPublic=True** ✅ | GET actor |
| japan-rent-market-kr / camera-kr | isPublic=True ✅ | GET actor |
| 全25収益アクター公開化 | actors_public 22→25解消 🎉 | collector実測 |
| workerレポートファイル | v4 作成済み ✅（t_85d02fbf問題は今回発生せず） | ファイル存在確認 |

### 出力スキーマ検証
dmm-scraperに18フィールドのoutputSchema追加後、**schemas-required→HTTP 429（daily-publication-limit-exceeded）に変化**。ブロッカー解消を実測で証明（Worker報告どおり）。

## 3軸評価

```json
{
  "evaluation": {
    "technical": {
      "score": 9,
      "assessment": "outputSchemaの全type=string必須／.actor相対パス／日次公開上限という3つのApify制約をビルドエラーから学習し、build 0.1.8 SUCCEEDEDに到達。コード・設定とも正しい。公開ステータスの原文（schemas-required→429）までの推移で解消を証明したのは秀逸。",
      "evidence": "GET builds: 0.1.8=SUCCEEDED, 0.1.6/0.1.7=FAILED を実測。3名義actor isPublic=True を実測。"
    },
    "business_kpi": {
      "score": 6,
      "assessment": "公開化は発見性向上に寄与し収益KPIの土台。ただし公開済み25件+待ち3件いずれも現状売上0（revenue_estimate total=0）。Verification CLI・MCP発見性による新規ユーザー獲得は未測。公開化そのものは収益を直接生まない下地段階。",
      "evidence": "revenue-daily.json: total_monthly=0, Apify PPE 25件/無料0件。"
    },
    "cost_efficiency": {
      "score": 8,
      "assessment": "ビルド2回FAILEDは無駄コストだが、outputSchema追加という一度きりの設定変更でAPI利用コスト変動なし（PPE課金は実行時のみ）。動作コストは妥当。",
      "evidence": "ビルド失敗による課金は軽微・outputSchemaは静的設定。"
    }
  },
  "self_review_quality": {
    "valid": true,
    "notes": "Reflexion JSONが完全。2回のbuild失敗をmistakesとして正直に記載し、what_could_improveで事前のactor.json照会を自己指摘。confidence=9もevidenceに一致。不足なし。"
  },
  "verdict": "conditional_pass",
  "next_steps": ["明日(24h後)に PUT /v2/acts/nUm22B2guMo8vXom6 {isPublic:true} でdmm-scraper公開", "rakuten-market-scraperも同時公開（outputSchema済・rebuild 0.1.2済）", "公開後は新規ユーザー/実行数の前後比較で発見性効果を計測", "figureはtagged-build対応を余裕あれば"]
}
```

## 改善ノート更新（233FF6065EF7）

教訓notepadを更新します。

<details>
<summary>実施コマンド</summary>

```bash
hermes cron notepad 033ff6065ef7 set lessons "..."
```

</details>

## 申し送り

- **dmm-scraper（nUm22B2guMo8vXom6）: 明日（9/4）にPUT isPublic=trueで公開必須**（ブロッカー解消済み）
- rakuten-market-scraperも明日公開
- 公開後は発見性効果（新規ユーザー・実行数）を次回のTPRで計測する
