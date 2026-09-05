# 収益化Critic提案: 2026-09-03（1回目・00:26実行）

> 収益化Critic Agent（kensho-revenue-critic）分析記録

## 実データ（revenue-daily.json 2026-09-03 / 00:20収集）

| 収益源 | 状態 | 実測値 |
|--------|------|--------|
| Apify | アクター25本（公開25）/ 総runs 1125 / 30日ユーザー 21 | **actors_ppe=0 と報告（異常）** |
| RapidAPI | API 21本（公開20・非公開1）/ 全FREEMIUM | 変化なし |
| Gumroad | 商品1（$9.99 / ZIP 315KB実体あり） | 売上0継続 |

月間収益見込み: $0

## 前回からの変化

- **収集データの異常を検出**: 9/3 00:20収集エントリで actors_ppe=0 / actors_free=0 と報告。9/2 23:55収集では actors_ppe=25 だった。個別アクター詳細（japan-camera-market等）には billing=ppe / price=0.002 が設定されているため、**集計ロジックのバグ**（日付境界・初期化等）が疑われる。
- t_f14f35b8（applied復元漏れzin43件の原因究明）は done に更新済み。
- 収益Workerの新規実装なし継続（QA v7確認済み・2回連続）。

## 新規提案（2件）

### 提案1【高優先】収集スクリプトの actors_ppe 集計不具合調査
- **根拠（実データ）**: 9/3 00:20収集で actors_ppe=0（前回9/2 23:55は25）。収益基盤データの信頼性に関わるため高優先。
- **内容**: kensho_revenue_collect.py の actors_ppe/actors_free 集計ロジックを確認し修正。再収集で actors_ppe=25 を確認。
- **タスクID**: t_a0ba13c4

### 提案2【中優先】収益Workerの優先順位明確化
- **根拠（QA v7申し送り）**: readyタスク7件滞留・Worker新規実装なし2回連続。原因は優先順位不明確と分析。
- **内容**: 最優先3件（t_531aa45e Apify無料クレジット → t_dd8936bb カメラAPI → t_5009a3cf フィギュアAPI）を明示し、workerジョブへの優先順位注入を提案。
- **タスクID**: t_70ff100a

## 分析メモ
- 収集基盤は1回実行で全収益源を網羅する正常設計だが、actors_ppe 集計に回帰バグの可能性。優先調査が必要。
- blockedタスク（t_f1005efc / t_83d9144f / t_868caac2）はCDP・手動操作が必要なため後回し継続。
