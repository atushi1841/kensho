# nightly-qa v67 検証レポート（2026-09-09 05:1x JST）

対象: t_b1bb39d0「critic v67: cpmeikan stale deadline-empty purge (snowflake 14d)」
worker実装: c126bbd（+docs 9e9c8ff）/ 提案: 9841a69
トリガー: monitor差分 done 352→353

## 0. ループ健康度
- score=95 / streak=0 / priority=new_proposals / skip_fast=false / blocked=0 / ready=0 / wip=0 / done=353
- 判定: **healthy**（唯一の減点是「ready=0 供給不足 -5」＝criticは1件提案可の状態）

## 1. QA独立検証（実測5点）

| # | 項目 | 結果 | 実測値 |
|---|------|------|--------|
| 1 | コード差分が意図どおり | PASS | collector.py +34行のみ（`_snowflake_ts_ms` / `_is_stale_empty_deadline` / merge purge二段化）。applier・応募ロジック無変更。閾値は`_STALE_TWEET_DAYS`定数化（代替案どおり21dへ緩和可能） |
| 2 | pytest | PASS | **490 passed / 4 skipped**（52.5s）。worker報告は489/5で、私の実測は490/4。**新規追加5テストは全件成功、回帰ゼロ**。差分は集計時点のskipped変動と推定（失敗0であることは両者一致） |
| 3 | 実データシミュレーション（実関数 import して再現） | PASS | 602 → 545（57件除去、**kept ratio 90.5% = ±20%帯内**）。除去57件は全て deadline空。手元再計算 stale_gt14d=**57** とworker/operatorベースラインと完全一致 |
| 4 | git hygiene | PASS | dirty code files（py/yaml/sh/js）**0件**。ruffモジュールは本環境に未導入（`No module named ruff`）だがpre-commit hook通過済み＝worker報告と矛盾なし |
| 5 | mypy 新規導入エラー | PASS（既存は据え置き） | 現状7 errors / 旧コード（c126bbd^）でも7 errors。**新規0件**。新規行342/526/549は既存行の位移動（+32行オフセット）で、内容・件数とも変化なし |

### 検証コマンドの欠陥を worker が自己申告・修正していた（好材料）
提案body記載のQA 1行コマンドは `(time.time()*1000-...)<<22` で **TypeError（floatに`<<`）**。
私が素で踏んだ（実測で失敗確認）→ worker報告「注意点」に正しいint化版が記載されており、その修正版で検証完了。
→ **プロセス改善の教訓**: 提案の検証コマンドはcritic自身が1回実行してから提案に載せるべき（未実行のコマンドは検証不能＝Verifiability Constraint違反）。

## 2. 成功指標の判定

| 指標 | 判定 | 根拠 |
|------|------|------|
| ①2 tick連続 stale_gt14d=0 | **PENDING** | 現時点 collected.json は stale=57 残存（収集tick未実行、workerも明記）。**9/9 09:00収集後が初測定**。判定は次回QAへ申し送り |
| ②総件数 602±20% で安定 | PASS（先行） | 545 = 90.5%。過剰削除なし |
| ③実装後24h deadline空への新規 applied=0 | PASS（暫定） | v67 commit 05:03以降の applied レコード **0件**（collected.json内 applied dictを全件パース）。なお提案エビデンスの「9/8以降3件」は実在し、**3件全て stale（14日超）＝今回パージ対象**と確認。9/8 10:34 kudou / 10:52 chugakujuken / 11:00 zin20120731 |

## 3. ⚠ 重要所見：パージでは非空率70%目標に届かない（構造計算）
```
post-purge cpmeikan: 33件 / deadline非空 7件 → 21.2%（target ≥70%）
```
- パージは「古い空」57件を消すだけで、**残る26件は生成14日未満の新規空**（構造的に毎収集で再増殖する）。
- つまり backfill の `非空率 ≥70%` CHECK は v67後も**FAILし続ける**（7.8% → 21.2% に改善はするが未達）。
- v67の狙い（滞留除去・applierの旧キャンペーン再スキャン防止）は達成されるが、
  **v61系の「非空率70%」というKPIは cpmeikan のサイト構造上、収集層では到達不能**（提案v67自身のエビデンス2が「正規表現改善は不可能」と実証済み）。
- → criticへの申し送り: **KPIの再定義が必要案**。「cpmeikan の deadline空のうち stale=0件」＋「応募対象は生成14日以内のみ」という**層別指標**に置き換えるか、生成14日未満の空アイテムに対する**ツイート本文からの期限抽出（詳細取得）**を新規提案化するか。数値目標が達成不能なまま残ると、毎朝 CHECK FAIL がノイズになり alert fatigue を再生産する。

## 4. carryover の進捗（前回notepad由来）
- [VERIFY-0445] backfill 初発火: **完了** — `logs/backfill_deadlines_20260909_034501.log`（rc=0、crontab `45 3,9-21 * * *` 登録確認）。krontab上のtypoではなく実登録済みを確認
- [VERIFY-9AM] 440e7db4a35c / b381e7117f9d: **ピン留め確認済み（05:1x時点）**。両者 `provider=bai / model=qwen3.8-flash`（jobs.json 59件中）。9/8 09:30の `drift_skip` エラーはピン前のもので、`check-cron-provider-drift.sh` は rc=0・出力0行（drift 0件）。**発火そのものは09:00/09:30待ち**
- [NOTE] watchdog unknown-arg:tai: 追跡不要（worker教訓どおり過渡的dev引数、消滅確認）

## 5. 3軸評価
```json
{"evaluation":{
"technical":{"score":9,"assessment":"snowflake復元は正確、非数値/欠落はNoneで安全側フォールバック、閾値定数化で緩和可能。既存_is_expiredと直列ORで責任分離も明確。","evidence":"実関数をimportして実データ適用: 602->545、除去57件のうちdeadline空57（deadlineありの誤削除0）。新規テスト5件含め490 passed/4 skipped。mypy新規0件（旧7=新7）。"},
"business_kpi":{"score":7,"assessment":"滞留除去と誤応募防止は確実に効くが、上位KPI（非空率70%）は構造的に未達のまま。目標設定と対策レイヤーの不一致が残る。","evidence":"post-purge cpmeikan非空率 21.2%（7/33）vs target 70%。9/8以降のdeadline空への誤applied 3件は全てstale=今回のパージ対象。v67 commit以降の誤applied 0件。"},
"cost_efficiency":{"score":9,"assessment":"収集時のO(n)フィルタ追加のみで、API呼び出し・ネットワーク・LLM起動コストゼロ。cron既存枠内で完結。","evidence":"diff +34行/-1、新規ネットワークI/Oなし。収集は既存0 3,9-21窓、backfillは03:00収集の45分後窓に格納済み。"}}
,"loop_health":{"score":95,"stagnation_streak":0,"verdict":"healthy"}
,"self_review_quality":{"valid":true,"notes":"workerは検証不能な検証コマンド（float<<22）を自分で見つけて修正版を明記し、未コミットデータでのシミュレーション値とベースラインの一致まで報告。自己レビューは実効的。"}
,"verdict":"pass"
,"next_steps":["09:00収集後にstale_gt14d=0を初測定（成功指標①は2 tick連続必要）","非空率70% KPIの層別再定義をcriticが検討（達成不能目標の放置はalert fatigue）","09:00/09:30 tickで440e7db4a35c/b381e7117f9dのlast_run_at更新を確認してdrift-fix最終ゲージ完了"]}
```

## 6. 申し送り（次回QA / critic向け）
1. **stale_gt14d 初測定は 09:10 QA の役目**（09:00収集後）。再現コマンドはint化版を使うこと。09:10では09:30tick（440e7db4a35c）は未発火なので**最終ゲージは11:10 QA**。
2. **非空率 KPI の扱い**はcritic判断。少なくとも「CHECK FAIL but by-design」をログに区別出力しないと、毎朝7.8%→21.2%のFAILが偽アラートになる。
3. ready=0（供給不足）が継続。criticは1件提案可だが、上記KPI再定義が自然な候補。
