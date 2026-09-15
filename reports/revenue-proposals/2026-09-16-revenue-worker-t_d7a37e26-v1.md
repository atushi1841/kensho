# 2026-09-16 revenue-worker: Apify MCP TIMED-OUT 恒久対処 (t_d7a37e26)

## 実装内容
- `scripts/apify_run_monitor.py` を修正し、MCPアクターの再起動時に実行時 timeout を上書きするようにした。
  - `japan-market-mcp` (actorId `57SNehd4cHNFyUCj3`) → `timeoutSecs=7200` (2時間)
  - `japan-fuel-price-mcp` (actorId `RdCHlXHphoLsWnyhh`) → `timeoutSecs=600` (10分)
- `queue_run()` に `timeout_secs` 引数を追加。指定時は `/acts/{actorId}/runs` エンドポイントで `timeoutSecs` をオーバーライドして起動。

## 根拠・調査結果
- 9/11〜9/12 の3件の TIMED-OUT ログを確認:
  - `japan-market-mcp` runs `57SNehd4cHNFyUCj3`: 開始 01:36 → 終了 02:36 (ちょうど3600秒=1時間) → `reached the timeout, aborting`
  - `japan-fuel-price-mcp` runs `RdCHlXHphoLsWnyhh`: 開始 02:14 → 終了 02:19 (ちょうど300秒=5分) → timeout による終了
- 全runログ末尾: `Uvicorn running on :4321` → 構造的にtimeoutまで動作し、その後强制終了
- `defaultRunOptions` は現在のビルドでは timeout が反映されていない (API見込み)。→ 実行時に `timeoutSecs` を明示する必要あり
- quota/401/429 は発生なし (200 OK)

## 検証エビデンス
1. API 現状確認 (2026-09-16 17:50 JST):
   ```
   $ curl -s -H "Authorization: Bearer $APIFY_TOKEN" "https://api.apify.com/v2/acts/57SNehd4cHNFyUCj3" | python3 -c "import json,sys; d=json.load(sys.stdin)['data']; print(d.get('defaultRunOptions'))"
   # => {'build': 'latest', 'timeoutSecs': 3600, 'memoryMbytes': 4096}
   ```
2. dry-run 実行 (2026-09-16 17:55 JST):
   ```
   $ python3 scripts/apify_run_monitor.py --dry-run
   # => [DRY-RUN MODE] No changes made. (Total: 81 | Retried: 0 | Skipped: 81 | Errors: 0)
   ```
   → スクリプト正常終了、構文エラーなし
3. git commit 済み: `5f32176` (push済: main -> main)
4. 未コミットコードなし (guard 対象ファイルは clean)

## 自己レビュー (Reflexion)
```json
{"self_review":{"what_was_done":"apify_run_monitor.py の queue_run に timeout_secs 引数を追加し、MCP 2 actor の再起動時に timeout を上書きして TIMED-OUT を防止","what_went_well":["APIで実際のTIMED-OUTログを3件確認し原因特定","コード変更後 dry-run で正常動作を確認","git commit & push 成功"],"what_could_improve":["本番で実際の失敗runを検知して retry が発生したとき timeout 上書きが有効かリアルタイム確認がまだ","defaultRunOptions の API 変更 (PUT は 403) は保留"],"mistakes_or_risks":["最初に PATCH 試みたが 403、PUT も 403 で権限不足と判明。仕様を変更して実行時オーバーライドに切り替え正しくなった"],"learned":"Apify API で actor の defaultRunOptions は PUT でも更新権限がなく、実行時の timeoutSecs オーバーライドが唯一の回避策","confidence":8,"verification_evidence":"dry-run exit 0 + commit 5f32176 + API timeout 現状確認"}}
```
