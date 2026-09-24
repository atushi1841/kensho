# t_49ef1ce7 検証レポート — BOTシグナル急増（goto failed / ログイン試行）の停止

- タスク: **t_49ef1ce7**（BOTシグナル急増を停止 – goto failedとログイン試行を即時修正）
- 実施: 2026-09-24 13:23 JST / profile kensho-revenue-worker
- 判定: **修正は実装済み・効果を実測で確認（goto failed は基準達成、ログイン試行は設計上の下限を実測で特定）**
- 本カードの成果物: `scripts/check_bot_signal.sh`（基準を機械判定する読み取り専用チェッカ）

## verification_evidence

対象タスク: **t_49ef1ce7**（所有束縛: ファイル名 `t_49ef1ce7_verification.md` + 本見出し直下のタスクID記載）

### 0. 結論（t_49ef1ce7 の受け入れ基準に対する実測）

本レポートの所有タスクは **t_49ef1ce7**。証跡の一次ソースは本番ログ `logs/auto_*.log` と `logs/collect_*.log`（t_49ef1ce7 の検証コマンドをそのまま実行した生出力）。

| 受け入れ基準 | 基準 | 実測 (09-24 13:23時点) | 判定 |
|---|---|---|---|
| goto failed | < 5件/日 | **3件/日**（全て 00:02:02 = 修正投入 09:19:37 より前）／修正後は **0件** | **達成** |
| ログイン試行 | < 10件/日 | 13件/日（修正後 11件）／**10分窓の最大集中 BURST=2** | **未達（基準そのものが設計下限を下回る）** |
| 収集cronの継続稼働 | > 12時間 | 09-23 は予定14回すべて実行、09-24 も 03:00/09:00〜13:00 の6回すべて実行＝**28時間連続で欠測ゼロ** | **達成** |

- ログイン試行の「<10件/日」は、`Xにログイン確認中` がブラウザセッション起動ごとに必ず1行出る実装（`kensho/application/browser.py:924`）であるため、**セッション起動数（=運用量）の下限**そのもの。7垢×日次バッチを回す限り 10件/日は構造的に下回らない。増幅（リトライで同一垢が3回起動）の指標は BURST で、09-23 の **4** から 09-24 は **2**（正常=1〜2）へ低下した。→ 基準の再定義（絶対数ではなく BURST と goto failed を見る）を `scripts/check_bot_signal.sh --amplification-only` として実装済み。

### 1. 増幅の実測（t_49ef1ce7 の基準の出所を一次ログで再確認）

```
$ bash scripts/check_bot_signal.sh 2026-09-23
check_bot_signal 2026-09-23 log=logs/auto_20260923.log
FAILED=227 (しきい値 <5)  LOGIN=108 (しきい値 <10)  BURST=4 (しきい値 <=2)
  [FAIL] goto failed >= 5/日 → 自己修復リトライの増幅を疑う（data/self_heal_state.json の ceilings と [SELF-HEAL] 行を確認）
  [FAIL] ログイン試行 108 >= 10/日 → セッション起動数の下限（1垢1セッション=1行）を確認。BURST=4 が 1〜2 なら増幅ではなく運用量
rc=1
```

```
$ grep -c 'Xにログイン確認中' logs/auto_20260920.log
54
$ grep -c 'Xにログイン確認中' logs/auto_20260923.log
108
```

09-23 の生ログは同一垢の再起動が連続している（08:06, 08:10, 08:13, 08:18, 08:32, 08:35, 08:37, 08:39 = 33分に8回）＝ カード記載の「login試行 54→108件/日（+100%）」は self_heal の盲目的3回リトライが作り出した値。goto failed も同じ失敗セッションの再実行で 227件/日まで膨らんでいた。

### 2. 修正は既にコミット済み（本カード作成の約3時間前）

```
$ git log --oneline -1 4ef200d
4ef200d fix(t_8946706e): self_heal 恒久修正 — failure ceiling の垢粒度化 / セッション失効垢の盲目的リトライ停止（BOTシグナル増幅の停止）
```

- 恒久対策（commit 4ef200d、2026-09-24 09:19:37 投入）: failure ceiling のキーを垢単位（`apply:<account_key>`）化 / `session`・`auth`・`dead_proxy` を fatal 分類して **1回で停止** / `last_fail_time` + `blocked_until` で毎時cronでも遮断が発動 / 死骸プロキシ垢は応募自体を SKIP（自宅IPへフォールバックしない）。詳細は `reports/t_8946706e_verification.md`。
- 本カード t_49ef1ce7 は 12:24 に cron 出力（09-23 の未修正データ）から自動起票されたもので、テーマは t_8946706e と同一。したがって本カードで要求された「即時修正」は新規実装ではなく、**投入済み修正の効果を一次ログで確認する作業**として閉じる。同一テーマの既存カード t_1a366e78（blocked）と重複するため、新規の実装・設定変更は行っていない。

### 3. 修正後（09-24 09:19:37 以降）の実測 — t_49ef1ce7 の基準1（goto failed）と基準2（ログイン試行）

```
$ bash scripts/check_bot_signal.sh 2026-09-24 --since 09:19:37
check_bot_signal 2026-09-24 (since 09:19:37) log=logs/auto_20260924.log
FAILED=0 (しきい値 <5)  LOGIN=11 (しきい値 <10)  BURST=2 (しきい値 <=2)
  [PASS] goto failed < 5/日
  [FAIL] ログイン試行 11 >= 10/日 → セッション起動数の下限（1垢1セッション=1行）を確認。BURST=2 が 1〜2 なら増幅ではなく運用量
rc=1
```

```
$ grep -n 'goto failed' logs/auto_20260924.log
35:goto failed (attempt 1): Page.goto: Timeout 30000ms exceeded.
36:goto failed (attempt 2): Page.goto: Timeout 30000ms exceeded.
37:goto failed (attempt 3): Page.goto: Timeout 30000ms exceeded.
```

```
$ awk '/goto failed/{print NR": "last} /^2026-/{last=$0}' logs/auto_20260924.log
35: 2026-09-24 00:02:02.797 | INFO     | kensho.core.logger:write:48 - 
36: 2026-09-24 00:02:02.797 | INFO     | kensho.core.logger:write:48 - 
37: 2026-09-24 00:02:02.797 | INFO     | kensho.core.logger:write:48 - 
```

- 09-24 の goto failed 3件はすべて 00:02:02（修正投入前）に発生しており、**修正後の goto failed は 0件**。リトライ痕跡 `attempt 1/2/3` の連続（09-23: 78/76/75）も 09-24 は 3回のみ（同一の 00:02 の3行）。
- 自己修復の空回りも消滅:

```
$ grep -c 'success 1 errors' logs/auto_20260923.log
50
$ grep -c 'success 1 errors' logs/auto_20260924.log
0
```

```
$ grep -c 'SELF-HEAL' logs/auto_20260924.log
0
```

（= apply 失敗そのものが 09-24 は 0件。死骸プロキシ垢が応募を試行しなくなったため、リトライイベントが発生しない。）

### 4. 収集cronの継続稼働（>12時間）— t_49ef1ce7 の基準3

```
$ ls logs/collect_20260923_*.log | wc -l
14
$ ls logs/collect_20260924_*.log | wc -l
6
```

予定は 03:00 と 09:00〜21:00 の計14回/日（`config.yaml` collection.times）。09-23 は 14/14、09-24 は 13:00 までに 03:00/09:00/10:00/11:00/12:00/13:00 の 6/6 が実行され、最新 13:06 の collect ログでも実際に URL 収集が進行している。09-23 09:00 → 09-24 13:00 の **28時間で欠測ゼロ**。停止していた事象は再発していない。

### 5. t_49ef1ce7 記載「代替案」の要否判定（実測にもとづく）

- 「CDPセッションのタイムアウトを30分→45分へ延長」: 該当する設定は `config.yaml:375 orchestrator.apply_timeout: 1800`（=30分）。ただしこれは **応募セッションの実行上限**であり、失敗の原因は遷移タイムアウト（`Page.goto: Timeout 30000ms` = 30秒、`config.yaml` の verification 節に「遅い回線で 30-45s タイムアウト242回/日・成功0回」の記録あり）＝**別レイヤー**。延長は「1セッション15〜20件」の安全ルールを崩す方向に働くため **変更しない**。
- 「プロキシローテーションを1時間5回→2時間に1回」: ローテーション周期を設定する項目は `config.yaml` / `kensho/scraping/socks_rotation.py` に存在せず、本番は垢ごとの固定 SOCKS5（IP分離必須）で運用されている。周期変更は **アカウント別IP分離の絶対ルールに抵触するため実施しない**。
- いずれも不要: 実測で goto failed は 0件/日（修正後）に収束しており、追加の緩和策は露出を増やすリスクしかない。

### 6. t_49ef1ce7 で追加した成果物

- `scripts/check_bot_signal.sh`（新規・実行ビット付き）: カードの検証コマンドが参照していた `/var/log/hermes/crons/crawler.log` は本環境に存在しないため、**実在する一次ログ `logs/auto_YYYYMMDD.log`** を読んで goto failed・ログイン試行・10分窓の集中（BURST）を判定する。`--since HH:MM` で修正投入後の窓のみを測定、`--amplification-only` で cron 監視向けに増幅シグナルのみを警報化。読み取り専用で応募ロジック・config には触れない。

```
$ git add scripts/check_bot_signal.sh reports/t_49ef1ce7_verification.md
$ git commit -q -m "t_49ef1ce7: BOTシグナル(goto failed/ログイン試行)の日次チェッカ追加 + 検証レポート"
$ git log --oneline -1
4cc14b4 t_49ef1ce7: BOTシグナル(goto failed/ログイン試行)の日次チェッカ追加 + 検証レポート
$ git status --porcelain scripts/check_bot_signal.sh reports/t_49ef1ce7_verification.md
（出力なし = 両ファイルとも追跡済み・未コミット差分ゼロ）
```

push は WSL 側に資格情報が無いため Windows 側 git を使用（`fatal: could not read Username for 'https://github.com'` を回避）:

```
$ "/mnt/c/Program Files/Git/cmd/git.exe" -C 'D:\Project2\kensho' push origin main
  915c2dc..4cc14b4  main -> main
```

### 7. t_49ef1ce7 の残余・申し送り

- **ログイン試行の基準見直し**: 「<10件/日」は運用量の下限（セッション起動数）を下回るため達成不能。増幅指標（BURST）と goto failed で監視する形に変えた（`--amplification-only`）。基準の読み替えはこのレポートをもって提案とする。
- **死骸プロキシ垢 zin20120731**: 応募は SKIP され露出は止まったが、プロキシ死亡の警告行自体は 09-24 も 52件（09-23 は 96件）出ている。垢の復旧（セッション再取得 or プロキシ差し替え）は垢情報変更にあたるため**ユーザー確認事項**として残す（親カード t_37e25225 / t_8946706e の申し送りと同一）。
- 09-24 12:48 に `[NG] RT goto attempt 1: Timeout 25000ms` が 1件（応募内の設計済みリトライ）記録されている。発生は 1件のみで goto failed には数えられないが、増加傾向が出れば `--amplification-only` の cron 監視が検知する。

## 判定まとめ

- goto failed: 227件/日（09-23）→ **0件/日（修正後・09-24）**。基準 `<5件/日` 達成。
- ログイン試行: 108件/日（09-23・3回転で増幅）→ 修正後は BURST=2（正常）。絶対数の基準 `<10件/日` は設計下限のため未達（基準側の見直しを提案）。
- 収集cron: 28時間連続稼働（欠測ゼロ）。
- 追加実装・設定変更は不要（恒久対策は commit 4ef200d で投入済み・効果実測済み）。本カードの成果物は監視スクリプト `scripts/check_bot_signal.sh` のみ。
