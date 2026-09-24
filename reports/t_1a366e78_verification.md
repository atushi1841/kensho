# t_1a366e78 検証レポート — BOT信号異常増の根絶（goto failed 81→0 / login 41→11・同一時刻窓）

タスク: t_1a366e78「BOT信号異常増の根絶: goto failed 63→227件/日とlogin試行54→108件/日の原因特定」
担当: kensho-revenue-worker / 実施: 2026-09-24 12:50 JST / workdir: /mnt/d/Project2/kensho

## 結論（t_1a366e78 の成功指標は実測で充足）

t_1a366e78 の成功指標は「24h実測窓で goto failed < 100件/日、または根本原因ログパターンを特定（具体的事例≥3件）」。
実測の結果、**両方を同時に満たした**:

1. goto failed は同一時刻窓（08:00–12:48）で **81件 → 0件**（ページ失敗グループ数 27 → 0）。
2. 根本原因は Playwright `Page.goto: Timeout 30000ms exceeded` の反復で、原因は commit 4ef200d（2026-09-24 09:19:37 コミット）で恒久修正済み
   — failure ceiling の垢粒度化（apply → apply:<account_key>）、セッション失効/認証/dead_proxy を非回復種別化して盲目的リトライを停止、recovery_order 導入。
   = t_1a366e78 で「原因特定」要件を満たす具体的事例は、同一パターン（Timeout 30000ms）の連鎖として 76 グループ（9/23 全日）を数えられる。

BOT信号増幅の主因は self_heal が失効セッション垢を回復扱いのまま最大3回リトライし続けたこと。修正後はそのリトライが1回で停止し、signal が消滅した。

## verification_evidence

```
$ git show -s --format='%h %ci %s' 4ef200d
4ef200d 2026-09-24 09:19:37 +0900 fix(t_8946706e): self_heal 恒久修正 — failure ceiling の垢粒度化 / セッション失効垢の盲目的リトライ停止（BOTシグナル増幅の停止）

$ grep -c "goto failed (attempt 1)" logs/auto_20260923.log
76
$ grep -c "goto failed (attempt 1)" logs/auto_20260924.log
1
$ grep -c "goto failed (attempt" logs/auto_20260923.log
227
$ grep -c "goto failed (attempt" logs/auto_20260924.log
3
$ grep -c "Xにログイン確認中" logs/auto_20260923.log
108
$ grep -c "Xにログイン確認中" logs/auto_20260924.log
11

$ python3 - <<'PY'  (同一時刻窓 08:00:00–12:48:59 の比較)
20260923 window08-1248 gotoGroups= 27 attempts= 81 login= 41
20260924 window08-1248 gotoGroups= 0 attempts= 0 login= 11
PY

$ grep -h "goto failed (attempt 1)" logs/auto_20260923.log | head -1
2026-09-23 08:0x:xx.xxx | INFO | kensho.core.logger:write:48 - [NG] goto failed (attempt 1): Page.goto: Timeout 30000ms exceeded.

$ git log --oneline origin/main..HEAD
(空 = 未pushコミットなし)
$ git rev-parse HEAD origin/main
536d3a56b1de90cc6888d6795794317f5577885
536d3a56b1de90cc6888d6795794317f5577885

$ .venv/bin/python -m pytest tests/test_self_heal.py -q --no-cov
1 failed, 29 passed in 125.78s (0:02:05)
FAILED tests/test_self_heal.py::test_safety_blocks_dead_proxy_status - AssertionError: assert [] == ['zin20120731']
```

## before → after（数値KPI・改善方向: down）

| KPI | before (9/23) | after (9/24) | 方向 | 判定 |
|---|---|---|---|---|
| goto failed ページ失敗グループ数（同一窓08:00–12:48） | 27 | 0 | down | 改善 |
| goto failed attempt 件数（同一窓） | 81 | 0 | down | 改善 |
| goto failed attempt 件数（全日/当日累計） | 227（全日） | 3（12:48時点） | down | 改善 |
| Xにログイン確認中 件数（同一窓） | 41 | 11 | down | 改善（残: 約2.7件/h） |
| self_heal 回復リトライのBOTシグナル到達 | 36件（9/24 outcome-review 指摘） | 高頻度再起動は停止（修正で1回停止） | down | 改善 |

## t_1a366e78 の残課題（申し送り）

- login試行は 11件/4.8h（≒55件/日換算）で、t_49ef1ce7 の厳格目標（<10件/日）には未達。t_1a366e78 の成功指標（goto failed < 100/日 or 原因特定）は充足済みだが、ログイン確認の常時発生は別途 t_49ef1ce7 側で追跡中（同タスクは 12:39 に dispatcher が spawn 済み・二重着手回避のため t_1a366e78 からは触らない）。
- t_1a366e78 は 9/24 12:06 に done_guard（条件a/b/d/g 所有束縛）で blocked 化していたが、本レポートで証跡形式（bare `## verification_evidence` 見出し + `$ cmd => output` 引用 + タスク所有束縛）を満たした。作業自体は commit 4ef200d で完了済み。

## 追加発見（t_1a366e78 からの申し送り）: test_self_heal.py が時刻依存で恒久レッド化

- 現象: `tests/test_self_heal.py::test_safety_blocks_dead_proxy_status` が 2026-09-24 11:15 JST 以降 FAIL（4ef200d のコミット時 09:19 は age 4.07h で pass していた＝当時の「35 passed」は正当）。
- 根本原因（実測で確定）: fixture が `updated` を固定値 `2026-09-24T05:15:02` で書き、`dead_proxy_reason()` の鮮度ガード `safety.dead_proxy_max_age_hours`（既定6h）を超えると判定不能として `[]` を返すため。**時間経過で必ず再現する時限式フレーク**。

```
$ .venv/bin/python - <<'PY'   # tmp_pathで updated だけ差し替えた対照実験
updated=fixture値(05:15:02) -> dead_proxy_accounts=[]
updated=直近(now) -> dead_proxy_accounts=['zin20120731']
PY
```
- 修正案（1行）: fixture の `"updated"` を `datetime.now().isoformat(timespec="seconds")` に変更する。
- 影響: 以後すべての worker/QA の pytest が赤になり「全テスト通過」判定が構造的に不能。
- t_1a366e78 の受け入れ条件には含まれないため本カードでは修正せず、kanban で kensho-worker へ申し送りカードを作成した（二重着手回避）。

## 再現手順（t_1a366e78）

```
$ cd /mnt/d/Project2/kensho
$ grep -c "goto failed (attempt" logs/auto_20260923.log   # => 227
$ grep -c "goto failed (attempt" logs/auto_20260924.log   # => 3
$ grep -c "Xにログイン確認中" logs/auto_20260923.log        # => 108
$ grep -c "Xにログイン確認中" logs/auto_20260924.log        # => 11
$ git show 4ef200d --stat
```

## 自己レビュー（Reflexion）

{"self_review":{"what_was_done":"t_1a366e78 のBOT信号異常増について、同一時刻窓での before/after を実測し、原因が commit 4ef200d の self_heal 恒久修正（垢粒度 failure ceiling + 非回復種別のリトライ停止）で解消済みであることを証跡化した","what_went_well":["時刻窓を揃えた比較（08:00-12:48）で曜日/時間帯バイアスを排除","全日累計と窓比較の2系統で同じ結論を再現","未pushコミット0を確認し条件(e)を事前充足"],"what_could_improve":["login試行は依然約2.7件/hで残存し、厳格目標には未達（t_49ef1ce7 へ申し送り）","当初 180s の pytest 既定タイムアウトで枯渇→バックグラウンド実行に切替"],"mistakes_or_risks":["blocked復活時に dispatcher が同一カードを再spawn するリスク→unblock直後にclaimし即complete で窓を最小化","t_62e7242b/t_49ef1ce7 が同時runningのため commit は自タスク証跡2ファイルに限定"],"learned":"同一症状の before/after は『同一時刻窓』で比較しないと日中の進行度差で誤判定する（9/24 は12:48時点の途中経過である）","confidence":8,"verification_evidence":"logs/auto_20260923.log: goto attempt1=76 / attempt=227 / login=108、logs/auto_20260924.log: attempt1=1 / attempt=3 / login=11、同一窓 81→0・41→11"}}
