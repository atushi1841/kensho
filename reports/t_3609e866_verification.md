# t_3609e866 検証レポート — 自律稼働工場化: 本番安定性1週間モニタリング

- タスク: t_3609e866 (assignee kensho-qa / parent t_fa046d3a)
- 検証時刻: 2026-09-24 03:15〜04:00 JST
- 検証者: kensho-qa（コード変更なし・実測と記録のみ）
- 証跡: 本ファイル + `reports/t_3609e866_evidence.json`

## 結論（受け入れ条件の判定）

| # | 受け入れ条件 | 判定 | 実測根拠 |
|---|---|---|---|
| 1 | 1週間、重大なハングや同期エラーなくログが循環 | **未達 (FAIL)** | 同期エラー実在（github_sync push 成功0回）／HANG 7件（自動復帰は機能） |
| 2 | Telegram への（エラー）通知が不要な状態が続いている | **検証不能 (N/A)** | 通知経路が未配線（token/chat_id 空・`error` イベント呼び出し無し） |
| 3 | `docs/daily_reports/` が7日連続で push されている | **未達 (FAIL)** | 実在 2日分（09-22/09-23）= 2/7日、かつ自走 push 成功 0回 |

補足: 条件1の「ハング」側は watchdog が自動復帰させており機能している。未達の主因は
**同期（GitHub push）と watchdog 通知路の2経路が実質死んでいる**こと。

## 観測窓の実際（タイトルの「1週間」との差分）

- 遡及7日窓として使える最大窓: **2026-09-18 〜 2026-09-24**（日別ログが両系統揃う）
- self_heal の実装着弾は 09-22 以降（`self_heal failed` の発現が 09-22 から）。
  したがって「実装後の本番露出窓」は **09-22 00:00 〜 09-24 03:15 ≒ 51.3時間**（7日=168hの約31%）
- よって「1週間の安定性」は現時点で**構造的に証明不能**。本レポートは
  ①7日遡及窓での統合監視実測、②受入条件3の構造的未達、を確定させるに留める。

## 統合監視の実測（タスク内容1）

### self_heal（apply = `logs/auto_*.log` / collection = `logs/collect_*.log`）

- 7日窓の発動合計 **36件（apply 32件 + collection 4件）**、全件 `attempts=3`＝回復失敗（ユーザー可視の失敗）
  - apply: 09-22 に7件 / 09-23 に25件（09-18〜09-21 と 09-24 は0件）
  - collection: 09-23 の 17:00/18:00/19:00/20:00 に各1件。原因は
    `guarded_source() got an unexpected keyword argument 'proxy'`（引数不整合で収集全体が停止）
  - 09-23 21:00 および 09-24 03:00 の collection は 0件 → 当該不整合は解消済み（継続観測）
- 実装前（09-18〜09-21）は 0件。すなわち self_heal の発動は「新機能の稼働」と同義で、
  発動＝悪化ではないが、**回復できていない（attempts=3 で最終失敗）**点が本番品質の現在地。

### hang_watchdog（`logs/hang_watchdog.log`）

- 7日窓の HANG 検知 = **7件**（09-18 x3 / 09-19 x2 / 09-23 x2）、09-20・09-21・09-22・09-24 は **0件**
- 09-23 の2件（kudou 10:45, TankanNotes 14:35）は
  `HANG検知 → TERM → SIGKILL → RESTART: re-spawn発火（setsid flock）` まで完走＝**自動復帰が実働**
- 09-18/09-19 の5件は kill 止まり（re-spawn 実装前）。自律稼働化の主眼機能は
  09-23 の2件で初めて本番実証された。

### complete_watchdog（`logs/complete_watchdog_cron.log`）

- 実行 48回 / 候補 54件（complete-forgot 13・protocol-violation 41）/ 対象タスク 18件
- **誤検知 0件**: 候補18件のうち 17件は既に `done` 化（解消）、残1件 t_b64c35ea は
  claim 3回・reclaim 2回の作業痕跡付きで `ready` のまま（真陽性寄り＝未終端の実在）
- **重大欠陥: リマインドコメント送信が 54/54 = 100% 失敗**（`[err] comment failed: <task_id>`）。
  検出精度は良好だが、**配信路が死んでいるため運用効果はゼロ**。

### github_sync（`logs/github_sync_cron.log`）

- cron は設置済み（`55 23 * * * .../kensho_github_sync.sh`）
- 7日窓の生成 2件（09-22/09-23）に対し、**push 失敗 1件・`index.lock` 競合 1件**
  - `fatal: could not read Username for 'https://github.com': No such device or address`
  - `fatal: Unable to create '.../.git/index.lock': File exists.`
  - → cron 実行環境に資格情報が無く（非対話）、**同期自身の push は 0回成功**
- `docs/daily_reports/` の2コミットは origin/main には到達しているが、到達時刻は
  **同期実行（23:56）より後**＝他エージェントの push に便乗して運ばれたもの。
  「同期が push できている」証拠にはならない。
- 検証中（09-24 04:00）に本検証者自身が `git push origin main` を試行したところ
  `Failed to connect to github.com port 443 after 134543 ms: Couldn't connect to server` で失敗。
  すなわち push 不成立の原因は**資格情報不在（cron環境）と接続不能（WSL側）の二重**であり、
  credential helper だけ直しても同期は復旧しない可能性が高い（同一時刻 03:43 には
  他エージェントの push が成功しており、接続は間欠的）。

### 稼働欠損（ネットワーク系 watchdog、参考）

- `logs/wifi_watchdog_*.log` の再接続失敗: **zin_AW6povo 132回**（09-19〜09-24 継続中）、
  chugakujuken_RM10JE_S 71回、kudou_RM10JE_B 9回（いずれも「SSID圏外 or 電源オフ」）
- 失敗が続く垢は HANG と相関（kudou は 09-18/09-19/09-23 に HANG）。IP分離用の
  USB-WiFi プロファイルが落ちている垢は**そもそも応募できていない**＝安定稼働の前提欠損。

## Telegram 通知（タスク受入条件2）の実測

- 7日窓のログに `telegram` の言及 **0行**、`logs/*/notifier.log` は**存在しない**
- `config.yaml` の `telegram:` は `token: ""` / `chat_id: ""`（未設定）
- さらに `send_notification()` の呼び出しは `dm_win` / `running` のみで、
  **`error` イベントの送信呼び出しはコード上に存在しない**
- 判定: 「エラー通知が不要な状態」ではなく「エラー通知の経路が未配線」。
  通知が 0件であることは健全性の証拠にならない（**N/A判定**）。

## BOT シグナルへの影響（最優先・強調）

- self_heal の回復手順は**ブラウザ再起動を伴う操作再実行**であり、失敗垢での
  リトライは同一アカウントのアクション痕跡を機械的に増やす。
  本窓の apply 最終失敗 32件は全件 `attempts=3`＝最大3回の再実行。
- 先行検証（別タスク t_66c14eb4）の実測では、この再実行系により
  **BOTシグナル相当の行動痕跡が 63 → 227 に増幅**している。
  つまり「ログが循環している」ことは BOT 安全性の改善を意味しない。
- 本レポートの結論として: **回復できない垢（WiFi圏外垢）でリトライを重ねる現挙動は
  BOT検出リスクの主要因**であり、attempts 上限/垢サーキットブレーカの
  実効化が最優先（過去の実測で failure ceiling は pipeline 単位キーのため毎時cronでは遮断不能と判明済み）。

## 未達項目と申し送り

1. **[最優先/BOT]** 失敗垢のリトライ増幅（attempts=3）に対する垢単位サーキットブレーカの実効化
2. **[同期]** `kensho_github_sync.sh` の push 認証（credential helper 不在）と `index.lock` 競合の解消
3. **[監視]** `kensho-complete-watchdog.sh --apply` のコメント送信 54/54 失敗の修復（検出しても届かない）
4. **[通知]** Telegram エラー通知の配線（token/chat_id 設定＋`error` イベント実装）または要件の再定義
5. **[稼働]** zin_AW6povo / chugakujuken_RM10JE_S の WiFi プロファイル復旧（該当垢は応募不能）
6. **[本タスク]** 7日窓の再監視は子タスクへ引き継ぎ（本タスクの受入条件は現時点で未達）

## 検証

$ pwd && date
/mnt/d/Project2/kensho
Thu Sep 24 03:15:54 JST 2026

$ ls -1 docs/daily_reports/
2026-09-22.md
2026-09-23.md

$ git log --format="%h %ci %s" -- docs/daily_reports/
06efacd 2026-09-23 23:56:16 +0900 docs: 稼働サマリー 2026-09-23 (auto)
15fb9d1 2026-09-22 13:20:41 +0900 docs: 稼働サマリー 2026-09-22 (auto)

$ git reflog show origin/main --date=iso | head -3
f8af58c refs/remotes/origin/main@{2026-09-24 03:43:43 +0900}: update by push
cdec6a4 refs/remotes/origin/main@{2026-09-24 03:04:30 +0900}: update by push
6bfcac9 refs/remotes/origin/main@{2026-09-24 02:59:40 +0900}: update by push
→ 09-23 23:56（同期実行時刻）に "update by push" が無い＝同期自身の push は不成立

$ git log --oneline origin/main..HEAD | wc -l
0
→ 未pushコミットは 0（daily_reports の2件は他エージェント push 便乗で到達済み）

$ git push origin main
fatal: unable to access 'https://github.com/atushi1841/kensho.git/': Failed to connect to github.com port 443 after 134543 ms: Couldn't connect to server
→ 検証時点(09-24 04:00)は WSL 側の接続自体が不能（cron側の資格情報エラーと別要因）

$ cat -n logs/github_sync_cron.log
     1	[warn] git 操作失敗 (128): fatal: Unable to create '/mnt/d/Project2/kensho/.git/index.lock': File exists.
     9	[gen] /mnt/d/Project2/kensho/docs/daily_reports/2026-09-22.md (1740 文字)
    10	[warn] push 失敗 (128): fatal: could not read Username for 'https://github.com': No such device or address
    12	コミットはローカルに残留
    13	[gen] /mnt/d/Project2/kensho/docs/daily_reports/2026-09-23.md (1717 文字)

$ python3 /tmp/t3609_logs.py  (統合監視サマリ)
runs=48 flagged_entries=54 comment_failed=54
  kinds: complete-forgot=13 protocol-violation=41
  comment failure rate = 54/54 (100%)
  bytes=644 gen=2 push_fail=1 local_residual=1 index_lock_fail=1
  telegram 言及行数=0 / logs/*/notifier.log 存在: なし

$ python3 /tmp/t3609_wd.py  (watchdog 誤検知解析 / kanban.db 照合)
runs=48 entries=54 comment_failed=54
-- flagged task state (kanban.db truth) --
  t_0dc05be4 status=done   kinds=protocol-violation RESOLVED
  t_5e16a983 status=done   kinds=protocol-violation RESOLVED
  t_b64c35ea status=ready  kinds=complete-forgot
  ...
flagged-as-not-done-while-running=0
→ 17/18件は done 化で解消、残1件は作業痕跡付き ready（誤検知 0件）

$ python3 /tmp/t3609_sh.py  (self_heal 厳密計数)
  window合計 apply発動=32
  apply N success N errors (x32 / 全件 attempts=3)
$ grep -c "self_heal failed" logs/collect_20260923_170001.log logs/collect_20260923_180002.log logs/collect_20260923_190001.log logs/collect_20260923_200001.log logs/collect_20260923_210002.log logs/collect_20260924_030001.log
logs/collect_20260923_170001.log:2
logs/collect_20260923_180002.log:2
logs/collect_20260923_190001.log:2
logs/collect_20260923_200001.log:2
logs/collect_20260923_210002.log:0
logs/collect_20260924_030001.log:0
→ collection 4件（1件=2行）／21:00 以降は 0件

$ python3 /tmp/t3609_wifi.py  (hang_watchdog 7日詳細)
  2026-09-18: events=12 HANG=3 kill=6 restart=0
  2026-09-19: events=8 HANG=2 kill=4 restart=0
  2026-09-20: events=0 HANG=0 kill=0 restart=0
  2026-09-21: events=0 HANG=0 kill=0 restart=0
  2026-09-22: events=0 HANG=0 kill=0 restart=0
  2026-09-23: events=9 HANG=2 kill=3 restart=2
  最終エントリ: [2026-09-23 14:35:16] RESTART: acct=TankanNotes re-spawn発火（setsid flock, pid=2157464）

$ python3 /tmp/t3609_ap.py  (WiFi 再接続失敗)
  zin_AW6povo              失敗= 132  期間=2026-09-19..2026-09-24
  chugakujuken_RM10JE_S    失敗=  71  期間=2026-09-18..2026-09-23
  kudou_RM10JE_B           失敗=   9  期間=2026-09-18..2026-09-23

$ crontab -l | grep -nE "watchdog|github_sync"
35:*/5 * * * * .../kensho-hang-watchdog.sh >> /mnt/d/Project2/kensho/logs/hang_watchdog.log 2>&1
42:*/30 * * * * .../kensho-complete-watchdog.sh --apply >> /mnt/d/Project2/kensho/logs/complete_watchdog_cron.log 2>&1
54:55 23 * * * /mnt/d/Project2/kensho/scripts/kensho_github_sync.sh >> .../logs/github_sync_cron.log 2>&1

$ grep -n "^telegram:" -A 3 config.yaml
482:telegram:
484:  token: ""                      # BotFatherから取得（例: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"）
485:  chat_id: ""                    # 通知先チャットID（@userinfobot等で確認）

## 再現手順

解析スクリプト（本検証で使用、リポジトリ外 `/tmp` に作成）:
`/tmp/t3609_logs.py` / `/tmp/t3609_wd.py` / `/tmp/t3609_sh.py` / `/tmp/t3609_wifi.py` / `/tmp/t3609_ap.py`

```bash
cd /mnt/d/Project2/kensho
python3 /tmp/t3609_logs.py     # 統合監視サマリ（7日窓）
python3 /tmp/t3609_wd.py       # complete_watchdog 誤検知 + kanban.db 照合
python3 /tmp/t3609_sh.py       # self_heal 発動の厳密計数
python3 /tmp/t3609_wifi.py     # wifi_watchdog 継続性 + HANG 詳細
python3 /tmp/t3609_ap.py       # アカウント別 WiFi 再接続失敗
# done_guard（本レポートの構造検証）
bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_3609e866 \
  --workdir /mnt/d/Project2/kensho --task
```
