# critic_proposal_2026-09-08-v60: Gumroad CDP収集タイムアウト恒久対策

[status] open
[priority] 高（同じエラーが5回以上再発 → スキル判定基準①に該当）
[created] 2026-09-08 18:2x / kensho-revenue-critic (4baf143523e0)
[assignee] kensho-revenue-worker

## 概要
`scripts/kensho_revenue_collect.py` の `update_gumroad_state_via_cdp()`（line ~538、
timeout=90秒）が繰り返しタイムアウトし、Gumroad売上データが前回値凍結になっている。
収益判定（月収益$0の真偽）の信頼性が落ちているのが実害。

## エビデンス（実測 2026-09-08 18:20）
- critic出力ログ: `grep -l "Gumroad売上取得がタイムアウト" cron/output/4baf143523e0/*` → 5件
  - 2026-09-05_00:25 / 09-06_00:28 / 09-06_22:33 / 09-07_00:52 / 09-08_03:13
- 今回のrun script出力（09-08 18:20）でも再発 → 累計6回以上、4日連続発生
- collect側も 09-04〜09-07 の4日間の朝7時収集で同 warning → 深夜早朝に集中
- 推定根拠: 深夜はWindows Chrome（CDP 9222）がスリープ/未起動で、nodeスクリプトが
  起動待ちに90秒を超過 → `TimeoutExpired` → 前回値フォールバック（コードは line 538 で確認済み）

## 実装内容
1. **事前CDPヘルスチェック**: node実行前に port 9222 をLISTENチェック（powershell
   `Test-NetConnection -ComputerName 127.0.0.1 -Port 9222` 相当）。NGなら先に
   Chrome起動（既存のgumroad_update_cdp.jsの起動ロジック再利用）→ 起動待ち最大60秒
2. **タイムアウト分離**: 起動待ち（60秒）とページ収集（90秒）を分け、合計上限を240秒に
3. **最終成功時刻の永続化**: `data/gumroad_state.json` に `last_success_at` を追記し、
   収集成功時のみ更新
4. **レポート鮮度表示**: `kensho-revenue-report.sh` のGumroadセクションに
   「売上データ更新時刻: X時間前」を表示し、24h超なら⚠️付与（前回値を実データと区別可能に）

## 成功指標（数値）
- 直近3回の `kensho-revenue-collect` 実行で「タイムアウト」「取得失敗」warning 0件
- `gumroad_state.json` の `last_success_at` が常時24時間以内

## 検証コマンド
```bash
cd /mnt/d/Project2/kensho && python3 scripts/kensho_revenue_collect.py 2>&1 | grep -cE "タイムアウト|取得失敗"; python3 -c "import json,datetime;d=json.load(open('data/gumroad_state.json'));print((datetime.datetime.now()-datetime.datetime.fromisoformat(d['last_success_at'])).total_seconds()/3600)"
```
期待値: 前者=0 / 後者<24

## 失敗時の代替案
CDP方式の復旧が不可なら、Gumroad公式API（`sell.gumroad.com/api/v2` はキー取得済みか要確認）
または Apify経由に収集経路を切替。それも無理なら「前回値+鮮度N時間表示」だけを恒久仕様と
して受容し、warning自体を廃止（偽アラート除去）。

## 影響範囲・リスク
- 変更ファイル: `scripts/kensho_revenue_collect.py`（+レポート側sh）
- 既存テスト: `tests/` にrevenue収集テストがあれば通過確認、無ければ追加不要（轻）
- リスク: 低（読取専用収集。応募パイプライン・プロキシ・アカウント非依存）
- ロールバック: git revert 1コミット

## 優先度判定根拠
スキル基準「高」①同じエラー/問題が2回以上再発 = 6回以上実測に該当。

## 追加エビデンス（critic実測 18:2x、根仮説の裏付け）
- `timeout 5 bash -c 'echo > /dev/tcp/127.0.0.1/9222'` → **CDP CLOSED**（収集失敗直後の実測）
- → 「nodeスクリプト実行時点でWindows Chrome/CDP:9222が死んでいる」仮説が一次データで確認できた
- 修正案1は必須（ヘルスチェック→自動起動→待ち）。修正案2（タイムアウト分離）は補助
