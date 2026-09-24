# 2026-09-20 夜間収益化QA

## 結論

条件付き合格。対象の実装・実測は合格だが、回帰ゲート2件と未回収の自動復旧障害が残るため、ループ全体の最終合格ではない。

## ループ健康度

- 健康度：100
- 停滞連続：0
- 優先度：通常
- 準備完了：0
- 実行中：1（t_f473c9aa）
- 停止中：2（t_ddb7764a、t_9271d891）
- ゾンビ：0
- 判定：健全。ただし t_9271d891 は自動復旧を阻害する高優先案件。

## 三軸評価

```json
{"evaluation":{"technical":{"score":7,"assessment":"対象実装は実測合格。一方、完了結果空欄と終了呼出欠落を検出","evidence":"t_dfc1ae10 guard合格、pytest793合格/5skip/2失敗"},"business_kpi":{"score":9,"assessment":"Apify実測と非エックス分離実績は有効","evidence":"Apify HTTP200・store74件、非エックス成功率93.7%・収集449件"},"cost_efficiency":{"score":8,"assessment":"無料自動切替設定を確認。bai残存はない","evidence":"kensho-revenue-worker default=auto/provider=freellmapi、bai残存0"}},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":false,"notes":"t_3cc98f43はresult空欄、t_9271d891は終了呼出なし"},"verdict":"conditional_pass","next_steps":["t_f473c9aa完了後にt_9271d891を再実行","空resultとsilent exitの回帰修正","zin20120731のプロキシ復旧確認"]}
```

## 観点別分割検証

- コード品質：7点。対象差分と証跡は整合。未回収の終了呼出欠落あり。
- ボット検出リスク：9点。新規の多重・過フォロー・同一文言連投は確認されず。
- 設計一貫性：8点。収益ワーカーは自動切替方針に整合。別プロファイルの設定変更なし。
- テスト充足：6点。全800件中793合格・5件スキップ・2件失敗。失敗は回帰ゲートで検出済み。
- ライブ計測：8点。ApifyはHTTP200・74件。プロキシは1081、1082、1085生存、1084は死亡。

## 証跡

- `reports/t_dfc1ae10_verification.md`：guard合格、コミット押収済み。
- `reports/apify-integrated-qa-t_3cc98f43.md`：実測記録あり。
- `reports/t_9e8a1b2c-proxy-status-cause.md`：プロキシ状態の原因記録あり。
- `pytest -q`：793合格、5スキップ、2失敗。
- `git status --porcelain`：コード変更なし。

## 申し送り

t_9271d891は `ai-team-improvement` スキル未導入による未知スキルエラーで2回終了し、自動復旧できていない。t_f473c9aaでスキル導入中。完了後は対象を再実行し、`[checkpoint] step 0` と結果非空を確認する。
