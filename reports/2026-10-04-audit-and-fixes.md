# 2026-10-04 AIチーム・cron 全層点検 → 修正5件

ユーザー指示: 「AIチームやcronの点検をした方が良い。不必要なもの、効率、動いていないこと。
freellmapiを使って効率よくAIチームを動かすのが良い。お勧めでお願い。長時間仕事して良い。」

## 0. 結論

- 応募パイプラインと監視層は正常稼働。監視/応募/ダッシュボードは全て新鮮。
- 収益は事実として30日連続ゼロ（Apify external_runs=0 30/30日、Gumroad売上ゼロ30日）。
- **AIチームは「死んでいない」。本日10枚起票し、23:45起票のカードが今まさに実行中**。
- **ただし供給ループにデッドロックがあった**（「あなたが言わないと動かない」の真因）→ 修正済み。
- 初回スナップショットの「Criticが死んでいる」は誤診。原因は助言ロジックの逆転だった。

## 1. 修正した5件

### (1) loop_health の priority デッドロック → 修正【最重要】

`scripts/loop_health.sh` L662-668 の判定が `ready==0 AND running>0 → backlog_reduction` だった。
`backlog_reduction` は「新規提案禁止」を意味するため、**盤面が空（todoも0）でも提案禁止が続く**
永久ループに入っていた。todo 件数は同じ SQL で取得していたのに `_row[0]`（ready）しか読んでいなかった。

- 修正: `ready==0 AND todo==0 → new_proposals`（縮小すべきbacklogが実在しない時は供給を許可）
- 検証: `bash scripts/loop_health.sh` → `priority=new_proposals` / `advice.critic=propose_new`
- 分岐の単体確認: 空=propose / todo在り=reduce_backlog / ready在り=normal / blocked在り=triage 全て正
- 影響: Critic は 632回実行されていたが、この判定で毎回「提案するな」と言われていた

### (2) freellmapi: 死んだ上流キー4本を切り離し

`/api/keys` では `enabled=True status=healthy` と表示される第三者キーが、**モデル単位の実叩きでは
全て 401**（qwen3.8-27b も deepseek-v4-flash も）。これらのキーに ~2,150 の有効モデル登録が
ぶら下がっており、ルーティング毎に無駄な試行と遅延を生んでいた。

- 決定打の手順: `POST /api/models/<id>/test` で1件ずつ実叩きし、401 のキーだけを特定
  （"No enabled API key is available" は cooldown であり「死」ではない → 触らない）
- 対象: keyId 88(Lucidity composite)/92(NavyAI)/93(Routeway)/94(AINative) を disable
- 事前に `GET /api/keys` を丸ごとバックアップ: `data/freellmapi_keys_backup_20261004.json`
- 検証: `/v1/chat/completions`（model=auto）3回 → **3/3 成功**、直後のプロキシログに 401 が消えた
- 有効キー: 67/72

### (3) revenue-health-check の毎日の失敗

`check_external_runs()` の早期リターンに `total_days`/`zero_pct` が無く、データ欠損時に
`print_report` が KeyError で落ちていた（=**監視自身が盲目になる**型）。
早期リターンにキーを揃え、参照側も `.get` で防御。実行して exit 0、空データ経路も検証済み。

### (4) atushi16 の時間帯過集中（BOTシグナル）

安全監査が 4日連続で「1時間上限15超過」を検知（09/11/12時台に15〜17件）。
原因は `max:15 × 12バッチ = 容量180` に対し `daily_target:75` のため、**午前5バッチで目標を使い切り**
08〜13時に集中していたこと。

- 修正: `max 15 → 7`（12バッチ、容量84）。時刻は不変。1時間あたり最大14（通常7）で上限内
- 他3垢は不変（kudou 150 / zin 180 / Tankan 150）
- ランナー `orchestrator.py:114` が `batch.get("max")` を読むことを確認。テスト48件パス

### (5) X週次投稿の新経路（前ターンからの続き）

cron ラッパーが `KENSHO_PROMO_BROWSER=firefox` を固定していた（WSLでは必ず失敗）→ `win` に変更。
`post_with_windows_cdp()` を新設し、ドライバ `scripts/x_post_driver.js` を配線。
- 潰したバグ: `about:blank` を弾くCDP接続 / contenteditable に `.value`（常に0）/ dry-run が挿入前に止まる
- 検証: dry-run で `inserted_chars=206`（本文が実際に入ったことを確認）
- 未検証: 投稿ボタンのクリック以降のみ（次回実走 2026-10-05(月) 09:00 JST）

## 1.5 【追加】第2の真因: 注入側が判断フィールドを捨てていた

1時間後、手動発火した nightly-critic が **「ok」を返したのに新規カード0枚**、出力は9/18の定型ブロック
だったことから深掘りして発見。

- `kensho-revenue-report.sh` L29 が健康度JSONを
  `jq -r '.role_summary.critic // .'` で絞り込んでおり、**`priority` / `advice` を丸ごと破棄**していた
- critic のプロンプトは「script出力の `advice.critic` フィールドが行動方針を決定する」と明記
- ＝ **判断材料が届いていないので、毎時実行されていても何も提案しない**（632回実行して実質ゼロ）
- 注入実測（修正前）: キー15個（alert/score/running/... のみ）
- 注入実測（修正後）: `priority=new_proposals` / `advice={"action":"propose_new",...}` を追加

修正:
```bash
# 旧: priority/advice が消える
jq -r '.role_summary.critic // .'
# 新: role_summary を保ったまま priority と advice.critic を併せて注入
jq -r '. as $t | ($t.role_summary.critic // $t) as $r | {role_summary: $r, priority: $t.priority, advice: $t.advice.critic}'
```

`kensho-revenue-report.sh` はプロファイル内の実体ファイル（git管理外）。`loop_health.sh` は
repoへのsymlinkなので修正はコミット済み。

worker/qa のラッパーには同種の絞り込みは無し（jq/role_summary/advice の参照なし）。

## 2. 誤診の訂正（初回スナップショットとの差）

| 初回の見立て | 実測 |
|---|---|
| Critic が死んでいる（14日2枚） | 死んでいない。助言ロジックで**提案を禁じられていた** |
| 板が空（ready/todo 0） | 正常。dispatcher が数分で消費するため0に見える |
| 死んだプロジェクト残骸4本 | **全部実在**。I/O error は一過性（WSL /mnt/d 不通） |
| 22本のpausedジョブが放置 | 週次・月次は正常周期。統合済みは理由付き停止 |
| monitor がエージェントをスキップ | monitor=null。ゲートは存在しない |

## 3. 不要・要注意として残したもの

- **週次/月次ジョブの「長時間未実行」は正常**（例: 月曜ジョブが140h前 = 9/28(月) に実行済み）。
  26h閾値で機械的に「停止」と判定しないこと。
- **重複**: `kensho-apply-stall-check` が kensho-sweeps(`*/30`) と kensho-revenue-worker(`0,30 9-23`) の
  2プロファイルで同一スクリプト稼働 → 二重通知の可能性。**別プロファイルのため未変更**（要判断）。
- **tai-image-verify**: 「画像なし投稿3件を検出」で exit 1 → error 扱い。検出は正常動作なので
  exit code の意味づけの問題（別プロファイルのため未変更）。
- **3680件の custom モデル登録**: 死んだ鍵を指していた分は今回のキー無効化で切り離された。
  残り（keyId 6/37/39/89/90）は cooldown 状態で「死」ではない → 触らない。

## 4. 検証コマンド（実測ログ）

```
$ bash scripts/loop_health.sh | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['priority'],d['advice']['critic'])"
new_proposals {'action': 'propose_new', 'reason': 'ready=0かつtodo=0（盤面にworkが無い）→ 新規提案の起票を'}

$ curl -s -X POST -H "x-dashboard-token: $TOK" http://127.0.0.1:3002/api/models/945/test
{"success":false,...,"error":"Custom (OpenAI-compatible) API error 401: Invalid API key"}   # 無効化前
$ curl -s http://127.0.0.1:3002/v1/chat/completions -d '{"model":"auto",...}'   # 無効化後
3/3 成功（プロキシログに 401 なし）

$ python3 -m pytest tests -k "promo or store or x_post or orchestrator or batch" -q
59 passed / 48 passed（回帰なし）

$ python3 -c "import yaml;c=yaml.safe_load(open('config.yaml'))..."  # atushi16
12バッチ max=7 容量84 daily_target=75
```

## 5. 検証結果（Critic復活の実証）

修正の**効果を実測で確認**した（01:13〜01:15の連続イベント）:

| 時刻 | 出来事 |
|---|---|
| 01:13:03 | t_f1b09c25 起票（**assignee=null**）→ ready のまま滞留 |
| 01:15:17 | t_fb291adc 起票（同一タイトル・本文、**assignee=kensho-revenue-worker**、created_by=kensho-sweeps） |
| 01:15:56 | assigned(t_f1b09c25) / claimed(t_fb291adc) |
| 01:15:59 | spawned(t_fb291adc, pid=1269734) |
| 01:16:47 | heartbeat（**実行中**） |

起票内容: 「競争率スコア実装：収集時に低競争率懸賞を優先採択するバッチ配分ロジック」
（reports/research-20261003.md の実データ 68件応募→11件当選 16.2% を根拠に、低競争率の
地方共同企画を優先採択する提案＝**収益直結**）。

→ **修正前に「14日で2枚」だったCriticが、修正直後に収益直結の提案を出し、
dispatcherが40秒で拾って実行が始まった。** 供給ループは復活した。

### 残った小さな欠陥（記録のみ）
- 01:13の起票だけ assignee が空で、dispatcher に拾われず滞留した（同一内容を2分後に
  作り直しており、エージェントは自力で回復した）。**assignee無しカードは永久に拾われない**
  という仕様は罠なので、`ai-team-improvement` スキルに記録。
- t_f1b09c25 を私が assign した後の status が `done` になったが、completed イベントが無い
  （同一内容の実行カードが別にあるため実害なし）。イベント無しの status 変更は要観察。

## 6. paused 22本のトリアージ結果（サブエージェント委譲→親が検証）

| 区分 | 件数 | 内容 |
|---|---|---|
| 不要（重複） | 4 | kensho-weekly-stealth-check / optimize-storage-monthly / kensho-apply-stall-check / kensho-data-journalism-weekly → いずれも enabled な同名 twin が稼働中 |
| 不要（統合済み・意図的停止） | 3 | kensho-dataset-weekly-update, kensho-revenue-collect（revenue-health-check.pyへ統合）, kensho-auto-fallback-watchdog（freellmapi単独運用のため停止と理由明記） |
| 不要（スクリプト消滅） | 1 | kensho-winrate-weekly（再設定が必要） |
| 不明→保留 | 12 | price-alert-daily / suruga-price-tracker / hotpepper-sales-observe / daily-model-stick×2 / reddit-sabotenJAL-weekly / apify-run-monitor / Japan Fuel APIメトリクス（期間限定） / kensho-research-agent ほか |
| 復帰推奨（サブエージェント判定） | 5 | gateway-memory-watchdog / line-openchat-collect / car-price-alert-daily / car-price-alert-daily-check / yahoo-resale-research-daily |

### ⚠️ 「復帰推奨」5本は復帰させた後、**親が取り消した**

サブエージェントは「last_error が一過性 I/O だから復帰」と判定したが、親が検証したところ不十分だった:

- **全ての最終実行が 2026-08-19**（6週間前）。`next_run_at` も 8/19-20 のまま固まっていた
- 対象プロジェクトの実体が**いずれも8月中旬から休眠**:
  car-price-alert=8/12、japan-car-price-alert=8/17、yahoo-auctions-japan-scraper=8/17、akiko-line=8/16
- 停止時期が **2026-08-14 の「転売・取引自動化は構造的却下」の直後**と一致
- gateway-memory-watchdog は **RSS 2GB超でHermes Gatewayを強制再起動する副作用**持ち

→ 5本とも `pause` で元に戻した（enabled=false / state=paused を確認）。

教訓: **「一過性エラーだから復帰」は復帰の根拠にならない。最終実行日・対象プロジェクトの鮮度・副作用
の3点を見る。** 判定できないものは復帰させず、ユーザー判断待ちとして提示する。
（`cron-job-workflow` スキルに記録）

### ユーザー判断が必要なもの（復帰候補・未実行）
1. `apify-run-monitor` — Apifyの実行監視。script実在。収益導線に関わるので復帰価値はあるが停止理由不明
2. `suruga-price-tracker` / `price-alert-daily` — 価格監視。駿河屋は Apify actor の対象データ源
3. `daily-model-stick` ×2 — 日次モデル固定（freellmapi単独運用になったので不要の可能性）
4. `gateway-memory-watchdog` — 復帰するなら閾値と再起動方針の再設計が必要（いまは無効のまま）

## 7. 完了状況

- ✅ nightly-critic の修正検証 → 起票→40秒でdispatch→実行中を実測（§5）
- ✅ paused 22本のトリアージ → 判定＋親の検証で「復帰推奨5本」を取り消し（§6）
- ⏳ freellmapi の失敗率低下は24h窓での再測定待ち（無効化直後の1時間は401ゼロを確認済み）

## verification_evidence

```
$ timeout 180 bash scripts/loop_health.sh > /tmp/lh2.json; echo exit=$?
exit=0
$ python3 -c "import json;d=json.load(open('/tmp/lh2.json'));print(d['priority'],d['counts'])"
new_proposals {'running': 1, 'blocked': 0}
$ timeout 400 python3 -m pytest tests -k "orchestrator or config or batch or rate_limit" -q
48 passed, 1314 deselected
$ curl -s -m 10 -H "x-dashboard-token: $TOK" http://127.0.0.1:3002/api/keys
enabled: 67 / 72
```
