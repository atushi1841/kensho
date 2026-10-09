# 収益QAレポート 2026-10-10 v6（05:20 JST）

## ループ健康度
- score=39（WARN）、stagnation_streak=3、priority=new_proposals、blocked=0、running=3
- 減点の主因: artifact_age_penalty=30 — t_bafd539a/t_d03a52b0 の artifact_age=inf
- **実測で誤検知と確定**: `pgrep -af 'kanban task t_'` で両ワーカー生存PID確認
  （t_d03a52b0=PID 1185560、t_bafd539a=PID 1221054）。盤面は done 886→888/1h で活発。
  → 「streak=3=停滞」は監視の誤判定。自動復旧阻害系（高優先）として
  修正カード **t_8852e33d**（artifact算出にPID生存+running<4h除外を追加）を起票。

## 検証済み成果物
- **t_957e7220（done 05:11, commit 89985be+0626b65e）**: dev.to/Qiita公開前デデアップゲート
  （publish_devto.py `find_existing_articles` L100/L193、dedup_devto.py 120行、py_compile OK）。
  QA実測再検証: `GET /api/articles/me/published` 直近27件で **重複タイトル0件**（before: 6組以上）。
  完了条件1・2充足。evidence.json+verification.md 両方リポジトリ内。
- t_e0a0f6cc（done）: mechatoku=16/appare=4 の検証レポート 2aa609e でコミット済。

## Apify外部流入（ライブ計測・runs API直叩き）
- 85 actor合計 totalRuns=3106。直近run（10-10 03:00 JST窓）は全て自走パイプライン。
- japan-luxury-brand-market-cn の直近6run全件 userId=VMz6nlpHoGIjTeSXS
  = **fruitful_quintessence（自垢）とID解決で確定** → 外部流入0継続（推測でなくuserId実測）。
- 外部流入判定は「userId≠自垢」フィルタが決定論的（時刻窓フィルタより正確）。次回からこの方法。

## 観点別分割検証（delegate_task 本ジョブ未設定→単一パス5観点・代替案条項）
1. コード品質 8/10: dedup実装は正規化タイトル一致+dry-run既定で良好。テスト追加なし(-1)
2. BOT検出リスク 9/10: dev.to DELETEは自己記事のみ、API正規経路。連投なし
3. 設計一貫性 8/10: 既存publishスクリプト内蔵ゲートでcron経路も自動的に保護
4. テスト充足 6/10: dedup_devto.py のユニットテスト無し。システムpythonにpytestモジュール無し（venv外実行）
5. ライブ計測 7/10: dev.to 27件/重複0実測。Apify userIdフィルタで外部0確定。view数API取得不可（reactions 0のみ確認）
→ 観点別検出: 2観点（テスト充足・ライブ計測の改善点）= 基準1.2以上

## 3軸評価
{"evaluation":{"technical":{"score":8,"assessment":"dedupゲート実装は正しくpush済み、重複0を実測再検証","evidence":"commit 89985be/0626b65e + dev.to API 27件 dup=0"},"business_kpi":{"score":4,"assessment":"重複解消でview集中化の見込みだが外部流入・views>=30は未達","evidence":"Apify runs userId全件自垢=外部0、reactions 0"},"cost_efficiency":{"score":8,"assessment":"新規設定ゼロ・既存スクリプト改修のみ、API呼び数少","evidence":"publish系3ファイル287行追加のみ"}},"loop_health":{"score":39,"stagnation_streak":3,"verdict":"monitor_false_positive(実盤面は活発)"},"verdict":"conditional_pass"}

## 申し送り
- 監視の助言ロジックは「生存性」を看不到にすると健全盤面を停滞と誤判定しpark誤爆する（t_8852e33d）
- 未コミットの config.yaml/actor_weekly_run.py/untracked5件は running ワーカー所有（非介入継続）
- dev.to APIはUser-Agent無しで403 Forbidden Bots → curl/pythonとも UA必須（QA教訓）
