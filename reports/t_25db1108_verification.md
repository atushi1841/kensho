# t_25db1108 検証レポート — kensho-dataset-weekly-update の週次失敗 恒久対策

- タスク: **t_25db1108**（【収益】kensho-dataset-weekly-update の恒久対策: 収集ステップの無リトライで週次更新が3/5回失敗）
- 実施: 2026-09-24 08:00〜08:20 JST / nightly-worker (job 5e8ec4984bba, profile kensho-sweeps)
- 対象ジョブ: c0e8e4d76933（毎週月曜 10:00 / no_agent / script=kensho-dataset-weekly.sh）
- 変更ファイル（2件・いずれもリポジトリ外の実行実体）
  1. `/home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-dataset-weekly.sh`（バックアップ: 同 `.bak-retry-20260924`）
  2. `/mnt/d/Project2/gumroad-automation/kensho_data_pipeline.py`（変更前の復元コピー: 同 `.bak-pre-t_25db1108`・構文OK）

## verification_evidence

対象タスク: t_25db1108（所有束縛: ファイル名 + 本見出し直下にタスクID）

### 0. 症状（before・実測）
job c0e8e4d76933 の `last_status=error`。失敗は 8/31 に2回、9/21 に1回で、成功は 9/07 のみ。
```
$ python3 -c "import json;d=json.load(open('/home/atushi/.hermes/profiles/kensho-sweeps/cron/jobs.json'));print([j['last_error'] for j in (d if isinstance(d,list) else d['jobs']) if j['id']=='c0e8e4d76933'])"
['Script exited with code 1\nstdout:\n[1] データ収集...\n  File .../httpx/_transports/default.py", line 118, in map_httpcore_exceptions\nhttpx.ConnectTimeout: timed out']
```
帰結: Gumroad商品の `zip` が `japan-hobby-dataset-20260907.zip` のまま2週間陳腐化（次回 9/28 まで黙って古いデータを配布）。

### 1. 真因の特定（実測）
api.apify.com は**公開DNSがAレコードを2件**返し、片方がこの回線から到達不能。
```
$ curl -sS -H 'accept: application/dns-json' 'https://cloudflare-dns.com/dns-query?name=api.apify.com&type=A'
{"Status":0,...,"AD":true,"Answer":[{"data":"34.198.8.69"},{"data":"100.30.24.153"}]}

$ getent hosts 100.30.24.153
100.30.24.153   ec2-100-30-24-153.compute-1.amazonaws.com

$ python3 -c "import socket,ssl
for ip in ['100.30.24.153','34.198.8.69']:
    try:
        s=socket.create_connection((ip,443),timeout=4); ctx=ssl.create_default_context()
        with ctx.wrap_socket(s,server_hostname='api.apify.com') as w: print(ip,'TLS OK',w.version())
    except Exception as e: print(ip,'FAIL',type(e).__name__)"
100.30.24.153 FAIL TimeoutError
34.198.8.69 TLS OK TLSv1.3
```
httpx/httpcore は**接続先アドレスの選択もフェイルオーバーも持たない**ため、リゾルバが到達不能側を先頭に返した窓では TCP connect が timeout(30s) し、**1リクエストの失敗で週次run全体が死ぬ**（1runで最大24リクエスト）。

### 2. 修正（実装）
- `kensho-dataset-weekly.sh`: step1 を最大3回リトライ（20/40s backoff）＋全出力を `logs/dataset_weekly_*.log` に永続化（従来は `tail -5` で捨てていた）＋全滅時は明示 `exit 1`。
- 併せて ZIP鮮度検証: `kensho_data_pipeline.py` は「データ収集できず」でも `exit 0` で return するため、実行開始以降に生成されたZIPでなければ失敗扱い（陳腐化ZIPを成功として配布させない）。
- `kensho_data_pipeline.py`: リクエスト単位のリトライ（`http_get`）＋失敗のたびに接続先候補をローテーション（`getaddrinfo` フック）＋connectタイムアウト 30s→6s。
- 検証フック `DATASET_PIPELINE_CMD / DATASET_RETRY_MAX / DATASET_RETRY_BACKOFF / DATASET_STOP_AFTER` は既定off（本番挙動は上記の改善のみ）。

### 3. 実測エビデンス
```
$ bash -n ~/.hermes/profiles/kensho-sweeps/scripts/kensho-dataset-weekly.sh && echo "SYNTAX OK"
SYNTAX OK

# T1: 全滅するスタブ → 2試行して exit 1（ログ永続化を確認）
$ DATASET_PIPELINE_CMD=false DATASET_RETRY_MAX=2 DATASET_RETRY_BACKOFF=1 bash <script>
[retry] データ収集 試行 1/2 ... / [retry] 1s 待機して再試行 / [retry] データ収集 失敗 (試行 2/2)
[ERROR] データ収集 が 2 回失敗。詳細ログ: /mnt/d/Project2/gumroad-automation/logs/dataset_weekly_20260924-080022.log
[T1] exit=1 elapsed=1s

# T2: 1回失敗→成功するスタブ → 2試行目で復帰し exit 0
$ DATASET_PIPELINE_CMD="bash /tmp/ds_stub_flaky.sh" DATASET_RETRY_BACKOFF=1 DATASET_STOP_AFTER=1 bash <script>
[retry] データ収集 成功 (試行 2/3) ... stub: attempt 2 OK (recovered)
[T2] exit=0 elapsed=1s

# T3: 収集が空でパイプラインが exit 0 したケース → 陳腐化ZIPを検出して exit 1（Gumroadへ未到達）
$ DATASET_PIPELINE_CMD=true DATASET_STOP_AFTER=3 bash <script>
[ERROR] 今回の実行でZIPが生成されていない（最新=japan-hobby-dataset-20260907.zip / 生成=2026-09-07 10:01:04）
[T3] exit=1 elapsed=0s

# T4(before): 修正前（リトライなし=当時の挙動）で実ネットワーク実行 → 3/3試行失敗
[T4] exit=1 elapsed=345s   # 08:00:28/08:01:49/08:04:05 の3試行すべて httpx.ConnectTimeout

# T5(after): 修正後（実ネットワーク・step1〜3） → 47秒で完走・新ZIP生成
$ DATASET_STOP_AFTER=3 bash <script>
[retry] データ収集 成功 (試行 1/3)
出力先: /mnt/d/Project2/gumroad-automation/datasets
Gumroad用ZIP: /mnt/d/Project2/gumroad-automation/japan-hobby-dataset-20260924.zip
[2] ZIP: japan-hobby-dataset-20260924.zip (486103B)
[3] bundle_info.json更新: japan-hobby-dataset-20260924.zip
[T5] exit=0 elapsed=47s

# T5ログ内で ConnectTimeout が実際に2回発生し、いずれもローテーションで復帰している
$ grep -E '\[http\]|\[OK\]' logs/dataset_weekly_20260924-081138.log
[http] api.apify.com 試行1/3 失敗 (ConnectTimeout) → 接続先候補を切替
[OK] tackleberry-japan-fishing-tackle-scraper: 100件 (run=2026-09-23T21:00:13)
[OK] kitamura-japan-used-camera-scraper: 100件 (run=2026-09-23T18:00:05)
[OK] jackroad-used-watch-scraper: 0件 / [OK] japan-used-instrument-market-scraper: 40件
[OK] komehyo-japan-brand-scraper: 100件
[http] api.apify.com 試行1/3 失敗 (ConnectTimeout) → 接続先候補を切替
[OK] iosys-japan-used-smartphone-scraper: 100件 (run=2026-09-23T18:00:07)

# ローテーション/リトライのユニット実測（httpx.get を2回失敗→3回目成功に差し替え）
$ python3 -c "... k.http_get(...) ..."
rotate rot=1 -> ['100.30.24.153','34.198.8.69'] / rot=0 -> ['34.198.8.69','100.30.24.153']
retry result: {'ok': True} calls= 3 rot= 2
non-retryable: OK (immediate raise)
```

| 指標 | before (T4) | after (T5) |
|------|-------------|------------|
| step1 の所要時間 | 345s（3試行全滅） | **47s（1試行で成功）** |
| exit code | 1 | **0** |
| ConnectTimeout 発生 | 致命（run全損） | **2回発生するも復帰** |
| 新ZIP | 生成されず（9/07のまま） | **japan-hobby-dataset-20260924.zip 486,103B** |

### 4. ロールバック
- shell: `cp kensho-dataset-weekly.sh.bak-retry-20260924 kensho-dataset-weekly.sh`
- pipeline: `cp kensho_data_pipeline.py.bak-pre-t_25db1108 kensho_data_pipeline.py`（復元コピーは構文OK・diffは本変更の追加分のみ）

### 5. 申し送り（次回候補）
1. 9/24の新ZIPはローカル生成のみ。**Gumroadへの実アップロード（step4-6）は次回 9/28 10:00 の定時実行に委譲**（公開設定変更は要ユーザー判断のため今回実行しない）。bundle_info.json は既に 20260924 を指している。
2. `mandarake-auction-scraper` / `surugaya-japan-hobby-prices` は「成功runなし」で毎回SKIP＝**8ソース中2ソースが欠測**（商品説明にはMandarakeを掲載）。別カードでApify側のrun復旧を要対応。
3. gumroad-automation ディレクトリは**バージョン管理外**（gitリポジトリでない）。今回バックアップはファイルコピーで代用した。恒久策としてリポジトリ配下へ移設を推奨。
4. `kensho_data_pipeline.py` に Apifyトークンがハードコードされている（L22）。認証情報は環境変数/.env 由来にすべき（値は本レポートに記載しない）。

## Reflexion（自己レビュー）
```json
{"self_review":{"what_was_done":"週次データセット更新の3/5回失敗を、シェル側リトライだけでなく到達不能Aレコードのローテーションまで含めて恒久修正し、before/after実測で示した","what_went_well":["T4で真因(Aレコード片方が到達不能)を実測特定し、推測で済ませなかった","before(345s/fail) → after(47s/exit0) の同一条件対比を取得","陳腐化ZIPの成功扱い(第2の潜在バグ)も同時に塞いだ"],"what_could_improve":["変更前バックアップを最初に取得すべきだった(pipelineは復元コピーで代用)","TLSプローブ方式を先に試して間欠性のため破棄した分の往復が発生した"],"mistakes_or_risks":["リゾルバ順序は環境依存のため将来Apifyがアドレスを変更すると再発し得る(ローテーションで緩和済)","step4-6(Gumroad実アップロード)は未検証のまま次回定時に委譲"],"learned":"httpx/httpcoreは接続先アドレスのフェイルオーバーを持たないため、複数Aレコードの公開ホストでは「1リクエストのタイムアウト=run全損」になる。connectタイムアウト短縮+候補ローテーション+リトライの3点セットが有効。","confidence":9,"verification_evidence":"T1-T3(スタブ実測) / T4(before 345s exit1) / T5(after 47s exit0・新ZIP 486103B・ConnectTimeout2回復帰)"}}
```

### 6. 追補（2026-09-24 08:50 JST / nightly-worker role kensho-revenue-worker・job 5e8ec4984bba）

実装済みだったが終端処理（kanban_complete）が未発行のまま run が落ちていたため、独立に再実測して引き継いだ（t_25db1108）。

```
$ printf '... attempt1 FAIL / attempt2 OK ...' > /tmp/ds_stub_recheck.sh; rm -f /tmp/ds_att
$ DATASET_PIPELINE_CMD="bash /tmp/ds_stub_recheck.sh" DATASET_RETRY_BACKOFF=1 DATASET_STOP_AFTER=1 bash /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-dataset-weekly.sh
[retry] データ収集 試行 1/3 2026-09-24 08:48:35 / [retry] データ収集 失敗 (試行 1/3) / [retry] 1s 待機して再試行
[retry] データ収集 成功 (試行 2/3) ログ: /mnt/d/Project2/gumroad-automation/logs/dataset_weekly_20260924-084835.log
stub: attempt 2 OK (recovered)
[T2-recheck] exit=0

$ grep -c "http]" /mnt/d/Project2/gumroad-automation/logs/dataset_weekly_20260924-081138.log
2
```

- 補足: `[retry] 成功 (試行 2/3)` の後に行が重複して見えるのは `run_with_retry` の `tail -3 "$RUN_LOG"` 出力であり、**パイプラインの二重実行ではない**（ログ内の試行回数は 1 回のみ）。
- 機械可読ハンドオフ: `reports/t_25db1108_evidence.json`（guard 条件(j) 合格を生成API自身が検証）。
