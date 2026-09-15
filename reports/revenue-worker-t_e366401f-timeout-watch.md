# revenue-worker t_e366401f — timeout監視定例化 実装報告（2026-09-15）

## 実施内容
ソース別Timeout日次集計スクリプト `kensho-timeout-watch.sh` を新設し、
WSL crontab で1日1回（07:55 JST）自動実行化する監視を定例化した。

- スクリプト: `/home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-timeout-watch.sh`
- 台帳: `/mnt/d/Project2/kensho/logs/timeout_watch.tsv`（日付ごとにupsert、再実行でドリフトした最新値を残す）
- cronログ: `/mnt/d/Project2/kensho/logs/timeout_watch_cron.log`
- crontab行: `55 7 * * * bash .../kensho-timeout-watch.sh >> logs/timeout_watch_cron.log 2>&1`
- 起票条件: 閾値（既定20件/day、`TIMEOUT_WATCH_THRESHOLD`でoverride可）超が**2日連続**成立で
  `--assignee kensho-critic --priority 10` のエスカレーションカードを `hermes kanban create` で起票。
  idempotency-key=`timeout-watch-YYYYMMDD` ＋ 未クローズtimeout-watch-*カードがある間は重複起票しない。
- パイプライン非改修・読み取り専用（応募ロジック・config・kenkaku.pyに一切触れない）。
- 失敗時代替案（cron新設が重なる場合）は不要と判断：既存cron帯（03,9-21時の収集／07:05 collect／
  07:15 revenue）と衝突しない55分配置、Hermes cronではなくnative crontabなのでgateway起動に依存しない。

## v144(t_902d09ac) GO待ち期間の位置づけ
run458/460/462で3回手動grepした集計をスクリプトに正式化。v144 GO適用後もそのまま監視継続でき、
源別内訳（KENKAKU/KCLUB/KEMA/CPMK）が台帳に積まれるため横断再発（9/14=47件スパイク）の検知が即時になる。

## 検証手順（実測）
- DRY-RUN+state overrideで4パス検証: ①閾値未満→not triggered ②前日欠測→not triggered
  ③閾値10に落として2日連続超過→DRY-RUN would create critic card（起票文言確認）④本番実行rc=0
- 件数はrun462手動grep（KENKAKU11/KCLUB14/KEMA13/CPMK9=47）と一致

## verification_evidence
t_e366401f 受理条件「1日1回ソース別Timeout集計が自動出力／20件/day超2日連続でcriticカード起票」の実測。

$ bash /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-timeout-watch.sh
[2026-09-14] timeout by source: KENKAKU=11 KCLUB=14 KEMA=13 CPMK=9 total=47 (threshold 20/day)
$ cat /mnt/d/Project2/kensho/logs/timeout_watch.tsv
2026-09-14	47	11	14	13	9
$ crontab -l | grep -c timeout-watch
1
$ TIMEOUT_WATCH_DRY=1 TIMEOUT_WATCH_STATE=/tmp/tw_test.tsv TIMEOUT_WATCH_DATE=2026-09-15 TIMEOUT_WATCH_THRESHOLD=10 bash /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/kensho-timeout-watch.sh
[2026-09-15] DRY-RUN would create critic card: timeout-watch: >10/day x2 days (2026-09-14=47, 2026-09-15=18) critic escalation
$ grep -hoE '\[(KENKAKU|KCLUB|KEMA|CPMK)\].*(Timeout|timeout)' /mnt/d/Project2/kensho/logs/collect_20260914_*.log | cut -d']' -f1 | sort | uniq -c
      9 [CPMK
     14 [KCLUB
     13 [KEMA
     11 [KENKAKU
