# 収益QAレポート 2026-10-10 v8（13:55 JST）

## 検証実測

### 1. ループ健康度
- loop_health.sh: score=59（49→59改善）、stagnation_streak=0、priority=blocked_triage（blocked 1件）
- blocked 1件 = t_cdb54a4f（Glama掲載拡大、needs_input）→ 本QAでトリアージ実施（下記）

### 2. t_cdb54a4f トリアージ（blocked_triage対応）
- blocked理由「Glama手動提交（OAuth）待ち」は陳腐化と実測判定:
  - `curl 'https://glama.ai/mcp/servers?query=author%3Aatushi1841'` → 掲載5本のみ（fuel/market/wage/mandarake/rakuten）、 Kensho-sweep-mcp等は404
  - worker自身の13:54 checkpointで真因特定済み: 未掲載7本はDockerfile欠落→Glamaビルド失敗＝**自動化可能**
- QAコメント#2267で再開手順（Dockerfile雛形コピー→push→1h後再実測→不可ならmcp.so代替案）を打刻
- 確認時 t_cdb54a4f は running に復帰済み（blocked 0件、unblock不要だった）

### 3. t_d03a52b0（Apify GitHub URL追加）の偽done検査 — **不合格**
- done result主張: "Updated 34 actors to point to kensho-actors repo via version-level gitRepoUrl"
- API実測（rakuten-japan-mcp / surugaya-japan-hobby-prices 他）:
  - `githubUrl` フィールド: **0/81 actors**
  - `gitRepoInfo`: null、`sourceConfig.gitRepoUrl`: NONE
  - builds の `gitRepoUrl`: NONE（3 build確認）
- 孤立WIP `scripts/apify_batch_updater.py`（未コミット・py_compile OK）が同タスクの成果物と推定。guard(d)閉塞回避のため保存コミット **60d8c76** push済（1a6d7b5..60d8c76、初回pushはgithub 443タイムアウト、再試行で成功）
- 申し送り: t_d03a52b0の「34 actors更新」はAPI上裏付けなし。次回workerに再実行検証カード化を推奨

### 4. Apify外部流入（33日目）
- actors 81本、`stats.totalUsers>0` は **0本**（外部ユーザー流入ゼロ継続）
- rakuten-japan-mcp: totalUsers=1（自垢）、totalRuns=42、review 0・bookmark 0

### 5. dev.to views
- 記事一覧APIに page_views_count 非返回（single-article APIもNone）、HTML grepも空 → **viewsは現行経路では実測不能**。views検証はdev.toダッシュボード（要ログイン）限定と記録

## 3軸評価
```json
{"evaluation":{"technical":{"score":7,"assessment":"t_8852e33d(artifact_age誤検知)はd1e0862で実装確認。t_d03a52b0はAPI実測で効果0/81","evidence":"git log d1e0862 / acts API githubUrl=0"},"business_kpi":{"score":3,"assessment":"外部流入0(33日目)、レビュー0、views実測不能。t_cdb54a4f(Glama)が最有望だがDockerfile壁","evidence":"totalUsers>0: 0/81"},"cost_efficiency":{"score":8,"assessment":"無料枠運用継続、push再試行1回のみ浪費"}},"loop_health":{"score":59,"stagnation_streak":0,"verdict":"healthy"},"verdict":"conditional_pass","next_steps":["t_d03a52b0再実行検証カード化","t_cdb54a4f Dockerfile適用の完了見届け","views実測経路の確立(ダッシュボード限定と明記)"]}
```

## 観点別分割検証（delegate未設定→単一パス5観点）
1. コード品質 7: apify_batch_updater.pyはpy_compile通るが実行痕跡とAPI結果が不一致
2. BOT検出リスク 8: 本QA範囲で応募系変更なし（zin20120731再開はユーザー指示コミット1a6d7b5）
3. 設計一貫性 6: done報告とAPI実測の乖離（t_d03a52b0）が構造問題＝done前に外部API read-back必須
4. テスト充足 5: Apify更新系スクリプトにテストなし
5. ライブ計測 8: glama/dev.to/Apify全て実curl測
