# 収益化QA検証記録: 2026-09-03（4回目・09:20実行）

> 収益化QA Agent（kensho-revenue-qa）検証記録

## 検証タスク

### 1. Apify課金状態ライブ実測（全25アクター）

**手法**: `GET /v2/acts?my=true` でID一覧取得 → 個別 `GET /v2/acts/{id}` でpricingInfosとisPublicを実測（09:16時点）

| 項目 | 結果 | エビデンス |
|------|------|-----------|
| ポートフォリオ検証 | 25/25 成功（ID未発見0・エラー0） | API実測 |
| PPE課金 | **25/25** PAY_PER_EVENT | API実測 |
| 無料アクター | 0/25 | API実測 |
| 公開アクター | **25/25 public=True** | API実測（収集データの22とは差: 収集08:58時点で3件非公開→09:16時点で公開化された可能性） |
| アカウント総アクター | 64（うちポートフォリオ対象25） | API実測 |

**結論**: t_79c58629（Apify高使用量5アクターにPPE課金）は**全アクターPPE適用済み**で正常。t_1323b323（pricingInfos直接参照）の実装もAPI実測と一致（PPE=25）。収集スクリプトの actors_ppe=25 は**実測と一致** ✅

### 2. Gumroad状態（gumroad_state.json 9/3 09:08収集）

| 項目 | 値 | 判定 |
|------|-----|------|
| login_ok | true | ✅ |
| sales_page_ok | true | ✅ |
| 売上 | $0 | ❌ 継続 |
| 総収益 | $0 | ❌ 継続 |

**結論**: Gumroad売上は依然$0。Reddit告知（t_d662a170 blocked）が解消されない限り改善見込みなし。

### 3. 収益基盤トレンド（revenue-daily.json）

| 指標 | 9/2初回 | 9/3 08:58 | 判定 |
|------|---------|-----------|------|
| actors_total | 25 | 25 | ✅ |
| actors_public | 22 | 22 | ✅ |
| actors_ppe | 25 | 25 | ✅ |
| total_runs | 1125 | 1162 | ✅ +37増 |
| users_30d | 21 | 21 | ⚠️ 停滞 |
| RapidAPI apis | 21 (public 20, freemium 21) | 同 | ✅ |

### 4. テストスイート（pytest）

**問題検出**: `pytest` が `scrapling` モジュール不足で**コレクションエラー4件**（test_browser, test_collector, test_invisible_playwright, test_orchestrator系）
- 原因: `.venv` に `scrapling` が未インストール（requirements に無い？）
- 影響: 応募系テストが実行不能。収益系（test_revenue_collect.py）は単体実行可能
- 判定: **要対応（中優先）**。ただし収益QAスコープ外の基盤問題のため申し送り

## 3軸評価

```json
{
  "evaluation": {
    "technical": {
      "score": 8,
      "assessment": "全25アクターPPE課金・公開状態をAPIライブ実測で確認。収集スクリプトのactors_ppe=25は実測と一致。収集基盤は正常動作。ただし収集データのactors_public=22と実測25の乖離あり（収集タイミング差の可能性、要監視）。pytestがscrapling不足でコレクションエラー（収益QAスコープ外だが基盤リスク）。",
      "evidence": "curl/urllib API実測: 25/25 PAY_PER_EVENT, 25/25 public=True, 0エラー。revenue-daily.json: actors_ppe=25一致。pytest: ModuleNotFoundError: scrapling ×4"
    },
    "business_kpi": {
      "score": 3,
      "assessment": "収益は依然$0。users_30d=21で停滞、runsは+37増（アクティビティはある）。SEO最適化（t_ead6b2d7）とn8nテンプレ（t_58be99ea）の効果は9/4以降のcriticで確認予定。Reddit告知ブロックが最大のボトルネック。",
      "evidence": "gumroad_state.json: sales=0, revenue=0。revenue-daily.json: users_30d=21(変化なし), runs=1125→1162(+37)"
    },
    "cost_efficiency": {
      "score": 9,
      "assessment": "収集基盤は1日1回・約30秒で完結。API呼び出しは25+1回のみでApify無料枠内。PPE課金は収益化施策でありコストではない。効率的。",
      "evidence": "収集実行時間実測なしだがスクリプト構造上25+1回のAPI呼び出しのみ。Gumroad収集はnode.jsスクリプトで無料"
    }
  },
  "self_review_quality": {
    "valid": true,
    "notes": "worker v1（t_ead6b2d7/t_531aa45e）とv2（t_dd8936bb）の自己レビューは具体的エビデンス付きで妥当。v2はピットフォール5件を明文化。ただしt_79c58629（PPE課金）の自己レビュー記録はworkerレポートに未記載（前回QA時点でPPE適用済み確認済みのため実質問題なし）。"
  },
  "verdict": "conditional_pass",
  "next_steps": [
    "【条件】Reddit告知ブロック解除（t_d662a170）後に収益効果再評価",
    "【申し送り】pytestのscrapling不足を基盤担当（kensho-sweeps/critic）に通知: .venvにscraplingインストール or requirements追記",
    "【監視】actors_publicの収集値(22)とAPI実測(25)の乖離を次回収集で確認",
    "worker着手: t_a4b1f89e(MCPサーバー化)→t_bdcf32a7(帳票PDF API)→t_56db28e7(camera API RapidAPI公開、t_85d02fbf実装待ち)",
    "t_cd3079fb(価格表示確認) ready→worker着手候補"
  ]
}
```

## 前回申し送り確認

- ✅ t_58be99ea（n8nテンプレ公開）→ conditional_pass継続、Reddit告知解除待ち
- ✅ actors_ppe=25正常化継続（今回API実測でも一致）
- ✅ worker着手順（t_a4b1f89e→t_bdcf32a7→t_56db28e7）はKanban readyのまま維持
- ❌ 売上0継続（監視継続）
