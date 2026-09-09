# QA検証レポート v75 — 2026-09-09 17:40 JST（nightly-qa / 033ff6065ef7）

## 起動トリガー
monitor差分検出: `score=85→75`（wip 2→3, dirty N→Y）+ done 357→358

## ループ健康度（冒頭計測）
- score=75 / streak=0 / priority=new_proposals / skip_fast=false / blocked=0
- 減点内訳: `ready=0供給不足 -5` + `in_progress多3件 -20`
- 検証時（17:35）に再計測: **score=85 / wip=2 / dirty=N へ自動復帰**（run323失敗→t_e971e85a再claim + ワーカーコミット98ad717でdirty解消）。一時的スパイクで構造問題なし。

## 検収クローズ①: t_51542f18（v71 dead-sourceセンチネル+fixupxガード）→ **done**
前tickからの持ち越し検収。全項目実測PASS:
1. fixupx_guard.json: `2094291340540399946 fails=3 blocked=true blocked_at=16:18:04`（30日自動解除）✅
2. 17:00収集ログ: frontier_k 再試行 **0件**（受入基準「collect 16時以降で再試行0件」達成）✅
3. **センチネル初実戦**: 17:18収集で dead-source 3件を検知・Kanban自動投入:
   - t_27484abb knshow（18収集連続0件）ready
   - t_35da58ce twscrape（248収集連続0件・導入以来0件）ready
   - t_5ed34bc3 chance.com（20収集連続0件）ready
   → assignee=kensho-worker、ready 0→3件で供給不足も解消。機能はcommit 1207f6a（push済み）で確立済み。
4. worker run319/321は両方「Iteration budget exhausted (90/90)」で gave_up。**実装は既にコミット済みで、失敗は冗長な再検証ループが原因**（タスク自体の機能不全ではない）→ QAが検収完走し done クローズ。

## Worker実装検証: t_e971e85a（hunter drift再発防止）→ 暫定PASS（run324稼働中）
- commit 98ad717 push済み（origin/main同期、ahead=0）
- cron 8c1271fd2158 登録確認（daily 08:50 no_agent）
- 実測: `kensho_script_drift_check.py --json` → `checked=45, drift=0, missing=0, rc=0`（OK時サイレント契約も満たす）
- hunter本体 md5: repo==profile（82401c30…一致）
- allowlist機構（意図的差分=kensho-env-audit-cron.sh 1件のみ許可）実装確認
- run324が17:19から稼働中（heartbeat継続、測位スクリプト staged）→ 最終成功指標は **9/10 16:00のhunter投入≤3件** で判定。次tick検証事項としてt_e971e85aにコメント済み。
- run323失敗履歴: `reclaimed stale_lock` 1件 → dispatcherの自動回収で復旧しており阻害なし。

## 検証記録ファイル確認（ルール③）
- t_c7d8460b Copperhead評価: `reports/revenue-proposals/2026-09-09-t_c7d8460b-copperhead-eval.md`（5.7KB）存在確認 ✅
  - worker commentで done_guard の「他ワーカーin-flight編集による条件(d)誤検出」をクリーンworktree再実行で回避した経緯が証跡付き。虚偽doneなし。→ QAがuntrackedレポートをcommit整理。

## 品質ゲート
- pytest: **530 passed, 4 skipped**（104秒。前回527→530、drift_checkテスト+3）
- git: コードdirty=N、ahead=0、push済み
- 幽霊assignee: なし（ready 3件すべて kensho-worker）
- ready滞留3件=上限30以内

## BOT検出リスク / 要注意事項
- **プロキシ1085（TankanNotes）が12:15からegress不通**（LISTENING但しCONNECT不可、WiFi再接続失敗=アダプタTankan_HR01無効『still ''』）。SAFETYスキップで自動的に応募停止（IP分離ルール遵守、自宅IPフォールバックなし）✅。**【要ユーザー対応】TankanNotesのUSBアダプタ物理確認/再接続**（ Software復旧不能、16回連続dead。ただし既知パターン・8/26以来再発）。
- knshow.com 18収集連続0件 = 上流変更の可能性 → t_27484abbで調査自動投入済み（センチネル設計どうおり）。
- chance.com 20収集連続0件 → 同上 t_5ed34bc3。

## 3軸評価
```json
{"evaluation":{"technical":{"score":8,"assessment":"v71センチネル+ガードは本番初実戦で3ソース検知・自動投入まで完走。drift checkはmd5照合+allowlist+サイレント契約まで実装。","evidence":"guard json blocked_at=16:18 / frontier再試行0件 / drift --json rc=0 checked=45 / pytest 530 passed"},"business_kpi":{"score":7,"assessment":"収集パイプラインの安全装置（重複応募防止・死にソース検知）は収益母数維持に直効。twscrape退役判断(248収集0件)はコスト削減余地。","evidence":"収集259件/tick維持、dead-source 3件自動可視化"},"cost_efficiency":{"score":6,"assessment":"workerが同一タスクで2回90iter予算枯渇（run319/321、計~4.5h相当）。実装済み機能の再検証ループにLLMを燃やす構造は wasteful。","evidence":"Iteration budget exhausted x2 / 機能自体は1207f6aで既に完了済み"}},"loop_health":{"score":75,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"t_c7d8460bのdone_guard誤検出回避（クリーンworktree再実行+証跡コメント）は正当。v70教訓のgit commit --only遵守も確認。"},"verdict":"pass","next_steps":["9/10 16:00 hunter投入<=3件の最終検証（t_e971e85a）","dead-source 3タスク(t_27484abb/35da58ce/5ed34bc3)のworker処理追跡","【要ユーザー対応】TankanNotes 1085 USBアダプタ物理確認"]}
```

## 申し送り（次tick/critic向け）
1. **t_51542f18クローズ済み**。検収は本レポートが最終判定。
2. **criticへ**: workerの「90iter予算枯渇2回」は構造問題。実装済みタスクの再検証ループ抑制策（完了条件到達で即complete、再検証はQAへ委譲）の教訓がタスクコメントに無い → プロンプト改善提案候補。
3. **9/10 16:00ゲート検証**: t_e971e85aの最終成功指標。次tickで当日作成kanban件数を `created_at` epoch比較で実測。
4. TankanNotes/1085は【要ユーザー対応】維持。soft復旧試行（restored=0が16回）は打ち切り。
