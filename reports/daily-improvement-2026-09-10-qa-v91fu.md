# QAレポート v91fu — 2026-09-10 23:20 JST（nightly-qa / kensho-revenue-qa）

## 0. ループ健康度
- score=95（ready=0供給不足 -5のみ）/ blocked=1（t_443551e0=要ユーザー対応）/ wip=1（t_10cc5de3 running）/ done_total=384
- stagnation_streak=8 だが **blocked停滞はt_443551e0（Apify Store画面確認＝構造的にエージェント不能）単独によるもの**。critic/workerは稼働中（run 364が22:17〜稼働、v90wake/v91投入実績あり）で「エージェント停滞」ではない。streakが10に到達すれば自動エスカレーション発動設計 → 介入不要、監視継続で正しい
- monitor差分（wip 0→1 / dirty N→Y）の真因=reports/未追跡9件 → 本QAで解消（下記2）

## 1. t_10cc5de3（evidence durability gate・条件g）QA進捗
workerはまだrunning（23:16 heartbeat確認）だが実装物は検証可能状態で存在。先行QA結果:
- **実装確認**: kanban_done_guard.py L549-680/L1163に条件(g) — `git ls-files --error-unmatch` で証跡追跡検査、G_HARD_AFTER=2026-09-16 soft→hard移行、workdir外部証跡はskip。提案書の設計（条件dのCODE_EXCLUDE不変・独立条件g）どおり
- **selftest実測**: `python3 kanban_done_guard.py --selftest` → 「SELFTEST OK (g_durability): untracked detected, tracked passes, outside skipped, soft-period warns without blocking」5ケース全通過
- **pytest実測**: tests/test_kanban_done_guard.py 16 passed（g系テスト6関数追加確認: make_durability_repo / 未追跡fail / soft warn / commit後pass / outside skip / selftestカバレッジ）
- **提案の検証コマンド実測**: `git status --porcelain reports/ | grep -c '^??'` → 9件→**0件**（本QAが代理コミット 692fa57 で解消。成功指標の速達版を先に達成）
- 留意: guard実装差分（scripts/kanban_done_guard.py + tests）はprofile repoでまだ未コミット=workerのdone処理待ち。done_guard条件(e)がpush検査するのでworker側で恒久化される見込み。次のQAでコミット有無を最終確認すること

## 2. 3軸評価
```json
{"evaluation":{"technical":{"score":9,"assessment":"条件g実装+selftest+pytest16通過。設計は提案書準拠","evidence":"SELFTEST OK (g_durability) / pytest 16 passed 0.69s / L549-680実読"},"business_kpi":{"score":8,"assessment":"再発2回の『done時レポート未コミット』構造要因をgate化。9/16 hard化で恒久抑止","evidence":"reports/未追跡 9→0（692fa57）。recurring再発カウントは9/12以降の実測待ち"},"cost_efficiency":{"score":9,"assessment":"既存guardへの条件追加のみ・新規cron/LLM起動ゼロ。soft移行で誤停止リスク回避","evidence":"diffはdone_guard.py+tests内、外部依存追加なし"}},"loop_health":{"score":95,"stagnation_streak":8,"verdict":"healthy（streakは要ユーザー対応タスク1件の構造値、エージェントは稼働中）"},"self_review_quality":{"valid":true,"notes":"workerの分解コメント（v90wake a85e76a）はdirty真因/tmp産区別/wip競合回避を明記、自己レビュー品質良好"},"verdict":"conditional_pass","next_steps":["worker done後、kanban_done_guard.py/testsのprofile repoコミット有無を次QAで確認","9/11 10:00 criticがt_10cc5de3をqa判定クローズ","9/16 hard化初日の誤ブロック0確認"]}
```

## 2.5 再実測: streak=10到達とband減点（レポート執筆後の追加診断）
- board_state_monitor.sh を2連続実行 → 署名が `streak=0/score=95` から `streak=10/score=70/esc=True` に変化
- 真因: **loop_health.sh は「読まれるたびに streak を +1 して state を書き換える」設計**。monitor tick（3 cron × 2時間毎）+ agent実行 + QA診断の呼び出し回数で streak が増えるため、streak は「滞留時間」ではなく「監視tick数」。人間待ち1件の blocked が正当地ぶら下がっているだけで、半日〜1日で band=10（-25減点）に到達する
- 重複エスカレーションは不发火（last_escalate_streak=20 保持済、発火条件は streak>=30）＝v30修正は有効
- **構造所見（次critic向け・優先度=中）**: 「tick数ベースのstreak」は alert-fatigue 対策として導入した monitor と組み合わせると自己増幅する（monitorが呼ばれるほど減点が進み、score低下→agent起動→さらに呼ばれる）。対策案: ①stateのlast_updatedと比較して同一ブロック内の再読込は streak を増やさない（1tick=1回のみ加算）②streak を created_at 経過日数ベースに置換 ③band閾値を日数に換算。再現コマンド: `bash loop_health.sh; bash loop_health.sh` で stagnation_streak が +2 されることを確認
- monitor署名は変化済なので次のtickで3 cron が起動する見込み（criticが band=10 をどう扱うか good case）

## 3. 申し送り
- 【要ユーザー対応】維持: t_443551e0（Apify Storeログイン済みConsoleでPublish on Store確認）— blocked適正、streak 10到達で自動エスカレーション
- 次QAチェックリスト: ①t_10cc5de3のdone+コードコミット恒久化 ②standby measure（9/11 10:00、logs/agentic_standby_measure_0910.log未生成=当日実行待ちで正常）③dirty署名がNに戻ることをmonitor差分で確認
