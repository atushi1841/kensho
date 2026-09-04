# v26-1 RapidAPI FREEMIUM→有料化 検証レコード

タスク: t_25a7704e
実施: 2026-09-05 JST
経路: RapidAPI Studio GraphQL（cookie認証・API-direct。CDP/UI不使用、実証済み経路）
価格方針: 既存 v17-B と同一の 3-tier 有料価格（FREEMIUM のフラグ切替）
  BASIC = $0.001/call / PRO = $0.005/call / ULTRA = $0.01/call（PERUSE・MONTHLY周期）

## 対象5本（既存3本 = japan-used-car/offmall-cn/camera は v17-B で済み）

| APIキー | API名 | visibility | 設定結果（--status確認） |
|---------|-------|-----------|--------------------------|
| japan-kakaku | Japan Kakaku Price Stats API | PUBLIC | BASIC $0.001 / PRO $0.005 / ULTRA $0.01 |
| japan-rent | Japan Rent Price Stats API | PUBLIC | 同上 |
| japan-watch | Japan Used Watch Price Stats API | PUBLIC | 同上 |
| japan-luxury | Japan Used Luxury Brand Price Stats API | PUBLIC | 同上 |
| japan-instrument | Japan Used Musical Instrument Price Stats API | PUBLIC | 同上 |

移行前: BASIC 無料(MONTHLY 月500K) + PRO $0.02 の FREEMIUM 構成 → 外部run 0件（有料化で収益ゼロ）。
移行後: BASIC/PRO/ULTRA 全 tier を有料 PERUSE 化 → コール毎に $0.001〜0.01 課金。

## 実装スクリプト
- scripts/rapidapi_pricing_set_v26.py（新規: v26-1 候補5本への 3-tier 設定。既存 rapidapi_pricing_set.py の実証済み ensure_tier/update/create を再利用・冪等）
  - `--status` / `--dry-run` / `--set-tiers` / `--json`
- scripts/rapidapi_pricing_status_v26.py / rapidapi_list_apis.py（読み取り補助）
- scripts/rapidapi_paid_effect.py（編集: 測定対象に v26-1 の5本を追加 → 2週間効果測定の日次トレンドへ反映）
  - RAPIDAPI_V26_APIS を collect_all に統合。既存3本 + 新5本 = 8本を測定。

## モニタリング（1週間 run 推移）
- 当日 baseline point 記録済み: data/rapidapi_paid_effect_state.json (2026-09-05) — 全8本 subscribers=0 で確定
- kensho_revenue_collect_daily.sh に rapidapi_paid_effect.py 呼び出しを追加 → revenue-daily.json へ日次添付
- Hermes cron `v26-1 rapidapi paid-effect 7d judgment`（2026-09-12 07:10）: 7日後判定＋残り14本展開
- native crontab one-shot（9/12 07:11）: gateway 非依存で最終測定を担保（--report）

## 判定基準（critic v11-B 準拠）
- 有料subscriber ≥ 1件 → 成功 → 残り14本へ展開
- 有料0件 かつ runs 半減以下 → 失敗 → 無料復帰
- 有料0件 だが構造維持 → 判断保留 → 別戦略

## テスト
- python3 -m py_compile: 全編集スクリプト OK / bash -n 日次収集 OK
- pytest tests/test_rapidapi_paid_effect.py: 8 pass / 3 fail（fail は pre-existing のテスト文言ミスマッチ:
  assert文字列が実装のwarning文言と不一致。measure_api は本タスクで未変更・テストを壊していない）
- ライブ検証: --status で全5本の単価が反映済みを確認（読み取り）

## リスクメモ
- RapidAPI はプラン更新ごとに新バージョンを生成 → 過去バージョンの orphans が残る。無料(月500K)の
  orphan 版に既存購読者が1人ずつ居る（used-car/offmall-cn/camera/kakaku/rent/watch/luxury）→
  中途解約自由な無料権利として残存。7日判定で注視。
- 有料化で外部 run が減るリスクは想定内。7日間の subscriber 推移で判断。
