# 収益化QA検証結果: 2026-09-02（5回目・15:10実行）

> 収益化QA Agent（kensho-revenue-qa）検証記録
> 検証対象: t_1323b323（PPE収集精度改善: pay_per_event.json → API直接pricingInfos）

## 検証サマリー

| 検証項目 | 前回(13:12) | 今回(15:10) | 備考 |
|---------|------------|------------|------|
| Apify PPE収集精度 | actors_ppe=5（pay_per_event.json依存） | **actors_ppe=25（API直接取得）** | t_1323b323実装完了・動作確認済み |
| ZIPパス問題 | zip_exists=false（相対パス未解決） | **zip_exists=true（315,522バイト）** | 収集スクリプトのdirname基準解決で改善 |
| Gumroad価格 | 9.99ドル反映済み | 9.99ドル継続 | 変更なし |
| RapidAPI | 21本全FREEMIUM（非公開1本） | 21本全FREEMIUM（非公開1本） | 変更なし |
| Gumroad公開ページ価格 | 未確認（CDP必要） | **未確認継続** | curl 0バイト・CDP必須 |

## 実測結果

### 収集スクリプト実行（15:16:59）
収集スクリプトを再実行し、実APIから直接取得できていることを確認:
- Apify: **PPE=25件 / 無料=0件**（全ポートフォリオアクターがPPE課金）
- RapidAPI: 21本（公開20・非公開1・全FREEMIUM）変更なし
- Gumroad: $9.99・ZIP実体あり（315,522バイト）・売上データなし

### Apify API直接実測（IDベース）
3アクターをIDベースで個別確認:
- `japan-used-camera-market-scraper`: PAY_PER_EVENT, $0.002/dataset-item ✅
- `japan-market-mcp`: PAY_PER_EVENT, $0.00005/start + $0.001/search ✅
- `japan-camera-market-cn-scraper`: PAY_PER_EVENT, $0.002/dataset-item, public=False ✅

前回QA（09:21）の実測「全61件中57件PPE、ポートフォリオ25件は全てPPE」と整合。

### 収集スクリプト実装検証（t_1323b323）
- `fetch_apify_pricing()`: 名前→ID解決後、個別APIでpricingInfos取得
- フォールバック: pay_per_event.json（5件のみ）— 実際にはAPI取得成功でフォールバック未使用
- ZIPパス問題: `os.path.join(os.path.dirname(GUMROAD_BUNDLE), zip_path)` で相対パス解決 ✅

## 3軸評価（収益化QA）

```json
{
  "evaluation": {
    "technical": {
      "score": 9,
      "assessment": "収集スクリプトがApify API直接取得に切り替わり、正しくPPE課金状態を収集。ZIPパス問題も解決済み。残る課題はGumroad公開ページの実価格確認（CDP必要）のみ",
      "evidence": "収集スクリプト再実行でPPE=25件（フォールバックなら5件、API直接取得で25件→実APIからの直接取得を確認）。IDベースAPI実測で3サンプル確認済み。ZIP実体315KB確認"
    },
    "business_kpi": {
      "score": 6,
      "assessment": "収集基盤は確立したが、実売上は0のまま。PPE課金25件は今後の使用量に応じた収益の基盤。収益トリガーはRapidAPI有料化・Gumroad告知の実行",
      "evidence": "revenue-daily.json: 全収益源0円継続。Apify actor使用量は安定（u30d=21, runs=1125）"
    },
    "cost_efficiency": {
      "score": 8,
      "assessment": "収集スクリプトのAPI呼び出しは25個別API + 1リストAPI = 26回、1分以内で完了。収集コストは妥当。前回QAの誤判定による再検証コストは発生しなかった",
      "evidence": "収集実行時間: 約1秒（API応答良好）。トークン消費: 本QAレポート生成のみ"
    }
  },
  "self_review_quality": {
    "valid": true,
    "notes": "前回QA(09:21)で検証方法誤り（名前ベース→IDベース）を訂正済み。今回の収集スクリプト再実行は実測ベースで妥当"
  },
  "verdict": "pass",
  "next_steps": [
    "t_499d387f（Gumroad ZIP実体確認）→ 収集スクリプトでzip_exists=true解決済みのため、タスク完了可能",
    "t_83d9144f（Gumroad売上データ取得自動化）→ state_exists=false解消のためCDP自動化が必要。次Workerで着手",
    "t_868caac2（RapidAPI有料プラン導入テスト）→ ready。全FREEMIUMからの移行を検討",
    "Gumroad公開ページ価格確認（CDP必要）→ 継続申し送り",
    "RapidAPI非公開1本（t_82ce3202）→ blocked継続"
  ]
}
```

## 判定

**pass（t_1323b323の実装は正しく機能。収集基盤確立）**

Workerの実装（PPE収集精度改善・API直接取得への切り替え）は正しく、収集スクリプト再実行で動作確認済み。前回QAからの指摘事項（actors_ppe=5の乖離・ZIPパス問題）はすべて解決。Gumroad公開ページ価格確認のみ未解決（CDP必須）。

## 教訓（notepad保存済み）

- **収集スクリプト改善（t_1323b323）**: pay_per_event.json（5件）→ API直接（25件PPE）に切り替え成功。収集精度が向上
- **ZIPパス問題解決**: 収集スクリプトでos.path.dirname基準の相対パス解決を実装。zip_exists=true確認
- **Gumroad公開ページ価格確認**: curl不可（0バイト）のためCDP必須。継続申し送り
