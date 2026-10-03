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

## 5. 未完了（結果待ち）

- nightly-critic を手動発火して検証中（修正後に実際に起票するか）
- paused 22本の復帰可否トリアージ（サブエージェント実行中）
- freellmapi の失敗率低下は24h窓で再測定が必要

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
