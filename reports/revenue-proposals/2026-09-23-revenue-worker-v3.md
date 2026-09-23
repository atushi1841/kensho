# 収益ダッシュボードの鮮度・整合性の自動保証（revenue-worker v3 / 2026-09-23）

- 担当: nightly-worker（kensho-revenue-worker）cron job `5e8ec4984bba`
- 自垢タスク: ready/blocked **0件**（唯一の自垢カード t_0b949bda は dispatcher worker が稼働中 → 二重処理防止規律により不着手）
- 今回は「前回run（22:05）が残した申し送り」を履行し、**誤った申し送りを訂正**した

## 0. 前回申し送りの訂正（重要）

前回runは「ダッシュボード再生成を日次で回すcronジョブが存在しない」と記録したが、**これは誤り**。
実在した: `kensho-revenue-collect`（job `35a7cc70ff3d`・`5 7 * * *`・script `kensho_revenue_collect_daily.sh`・last_status=ok）。
同スクリプトは末尾で `scripts/kensho_revenue_dashboard.py` を実行しており、日次再生成は既に実装済み。

→ **新規cronジョブを作成しない**（同名ジョブの重複作成は9/14の事故と同型）。代わりに、実際に欠けていた2点のみ実装した。

## 1. 実装内容

| # | ファイル（プロファイル側） | 変更 | 理由 |
|---|---|---|---|
| 1 | `scripts/kensho-collect-only.sh`（毎時収集・native crontab `0 3,9-21 * * *`） | 収集完了直後に収益ダッシュボードを再生成する行を追加 | 再生成は日次7:05のみで、**日中の「本日収集実績」が最大24時間古い値**のまま表示されていた（値の自動集計化は済んだが鮮度が未解決） |
| 2 | `scripts/business-dashboard-count.sh` | `PROJECT_DIR` を環境変数で上書き可能に（既定は本番パス） | fixtureで ✅/❌ 両分岐を実測するため（後方互換） |
| 3 | `scripts/kensho-daily-health-check.sh`（no_agent・毎日8:15・`deliver=telegram`） | 収益ダッシュボード整合性チェックを追加（`DASH_CHECK` も上書き可）。**正常時は無出力＝通知ゼロ**、不一致時のみ📊ブロックを出力 | 整合性チェッカーは存在したがどこからも定期実行されておらず、ドリフトを誰も検知できなかった。既存のTelegram通知経路に相乗りし、新規ジョブを作らない |

`revenue-status.html` は毎時再生成される自動生成物になるため、作業ツリー上は常に ` M`（HTMLは done_guard 条件dの対象外＝コードファイルではない）。

## 2. 実測エビデンス

```
$ for f in kensho-collect-only.sh business-dashboard-count.sh kensho-daily-health-check.sh; do bash -n "$f" && echo "OK: $f"; done => OK: kensho-collect-only.sh / OK: business-dashboard-count.sh / OK: kensho-daily-health-check.sh
$ bash business-dashboard-count.sh => ✅ 一致: dashboard=478, live=478 / ✅ 一致: Apifyアクター dashboard=25, json=25 / EXIT=0
$ PROJECT_DIR=/tmp/dashcheck_fixture bash business-dashboard-count.sh（fixture: dashboard=999 vs live=3）=>
    ❌ 不一致: dashboard=999 vs live=3 → EXIT=1
    （同fixtureで dashboard=3 に修正して再実行）=> ✅ 一致: dashboard=3, live=3 → EXIT=0
$ bash kensho-daily-health-check.sh => 📊行 0件（正常時は無出力＝Telegram通知なし・EXIT=0）
$ DASH_CHECK=/tmp/ng_stub.sh bash kensho-daily-health-check.sh（不一致fixtureを指す）=> 📊 収益ダッシュボードの収集実績が実データと不一致（exit=1）+ 対処コマンド表示・EXIT=0
$ PROJECT_DIR=/mnt/d/Project2/kensho LOG_FILE=/tmp/dashregen_test.log bash /tmp/dashregen_block.sh（kensho-collect-only.shからverbatim抽出した挿入ブロック）=> ✓ revenue-status.html 生成完了 (22 entries) / EXIT=0
$ stat -c '%y %s' revenue-status.html => 2026-09-23 21:56:01 → 2026-09-23 22:56:00（再生成で更新されることを実測）
```

検証の限界（正直な記録）: `kensho-collect-only.sh` **全体の実走**は、21:00開始の収集がflockを保持したまま2時間継続中（22:58時点・KCLUBページ16を走査中）のため今回は実施できていない。挿入ブロックのverbatim実行と `bash -n` までを実測済み。次回 3:00 の収集ログ（`logs/collect_<日付>_0300*.log`）に `✓ revenue-status.html 生成完了` 行が出ることをもって実走確認とする。flockを意図的に迂回して並行収集を走らせることは collected.json の同時書き込みリスクがあるため行わない。

## 3. 検出した別件（申し送り・今回は不着手）

1. **21:00の収集が2時間継続**（`logs/collect_20260923_210002.log`・KCLUBのページ走査が17ページ超で長時間化）。flockにより後続の毎時収集がスキップされるため、長時間化が続くと収集スロットそのものが欠落する。`kensho/scraping/collector.py` は他タスク（t_96c94435）が未コミット変更を持つため、本セッションでは触っていない。criticで「1runの上限時間（例: 60分で打ち切り＋警告）」の提案を検討されたい。
2. `data/revenue-daily.json` の `collectors.collected_today=222` は**記録時点のスナップショット**（ライブ=478）。チェッカーは「ライブ値を正」として比較するため誤検知しないが、JSON側の値の意味はドキュメント化済み（チェッカー出力のℹ️行）。
3. 日次アカウント健全性チェックは `zin20120731=連続失敗6(要確認)` を検出（垢側の問題・禁止領域のため不着手。毎日8:15のTelegram通知で可視）。

## 5. 追記（同セッション内の追加実測）

- push確認: `cmd.exe /c "cd /d D:\Project2\kensho && git ls-remote origin main"` => `453c2485ef6fc82d8335e12dcfa158b2aec8270b refs/heads/main`（WSL側のls-remoteは443タイムアウトするが、push自体は `7b64380..453c248 main -> main` で成功済み）
- 21:00収集の長時間化は t_96c94435 の未コミット `kensho/scraping/collector.py` 変更（サーキットブレーカー/再試行）の影響を受けている可能性がある。同タスク完了コミット `f960c5e` の後に同条件で1runの所要時間を再測定し、閾値（例: 60分）を決めるのが妥当。
- 収集は 23:01 時点でも進行中（`logs/collect_20260923_210002.log` 12190B・KCLUB走査の継続）。停止ではなく低速であることはCPU時間とログ増加で確認済み（`$ cut -d' ' -f14,15 /proc/3275012/stat` => utime 4380 → 4428 と増加）。

## 6. 自己レビュー（Reflexion）

```json
{"self_review":{"what_was_done":"収益ダッシュボードの鮮度（毎時再生成）と整合性監視（日次8:15のTelegram watchdogへ統合）を実装し、前回runの誤った申し送り（存在しないcronジョブの作成提案）を実測で訂正した","what_went_well":["jobs.jsonを直接読み、申し送りを鵜呑みにせず事実確認して重複cron作成を未然に防止","✅/❌両分岐をfixtureで実測し、通知経路もstubで発火確認","新規cronを増やさず既存の監視・通知経路へ相乗りした（運用面の複雑化ゼロ）"],"what_could_improve":["kensho-collect-only.sh全体の実走検証がflock保持中でできず、ブロック単体実行に留まった","21:00収集の長時間化という別の異常は検出したが不着手（所有権の都合）"],"mistakes_or_risks":["毎時再生成によりrevenue-status.htmlが常時dirtyになる（HTMLはguard対象外・データ集計はライブ値が正）","並行収集を避けるためlockを迂回する検証は行わなかった"],"learned":"他runの申し送りは事実確認してから着手する。既存ジョブの有無はjobs.json直読みが最も確実（存在しない前提で新規作成すると重複事故になる）","confidence":9,"verification_evidence":"bash -n×3 OK / checker prod exit0(478=478) / fixture ❌exit1・✅exit0 / health-check正常時📊0件・stubで📊発火 / 挿入ブロックverbatim実行で生成完了・mtime更新"}}
```
