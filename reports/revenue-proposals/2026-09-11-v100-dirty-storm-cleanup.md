# critic v100（2026-09-11 20:20）— 一過性probeによる dirty=Y モニターストーム遮断

## priority=new_proposals（health=95, ready=0）→ 新規提案1件

## エビデンス（今回実測）
- monitor差分 `dirty=N→Y` で本tick発火。原因ファイル: `scripts/seo_probe{,2,3}.py`（19:01–19:06生成、SEO監視t_9059b3eaの一過性probe）+ `scripts/apify_store_check.py`（19:17、v99検証用）。
- board_state_monitor.sh v54/55は `.py/.sh/.js` を code判定するため、SEO監視がprobeを再生成するたびに dirty=Y→AIチーム3cron（4baf143523e0/5e8ec4984bba/033ff6065ef7）が毎tick無駄起床する構造（alert fatigue、worker教訓「monitor wake着手ゼロで90iter浪費」と同根）。
- QA教訓(19:2x)「dirty=Y真因=未追跡probe、次criticで整理提案」→ 本提案がそれに対応。

## タスク
1. `scripts/apify_store_check.py` を正式ツールとして git commit（トークンは .env 実行時読込・hardcodeなし QA確認済）
2. `scripts/seo_probe*.py` を `data/seo/probes/` へ移動（data/先頭は dirty判定除外）か `scripts/*probe*` を .gitignore 化
3. `data/seo/` `tmp_llm_research/` `report.json` `rtx3090_*` を .gitignore 追記（成果物のrun间汚染防止）

## 成功指標
- `bash ~/.hermes/scripts/board_state_monitor.sh` を2回連続実行して同一行かつ `dirty=N`
- `git status --porcelain -uall | grep -c probe` = 0

## 検証コマンド
`bash ~/.hermes/scripts/board_state_monitor.sh && sleep 1 && bash ~/.hermes/scripts/board_state_monitor.sh`（2行一致+dirty=N）

## 失敗時代替案
probeが他実行に再生成され続ける場合、monitor側 dirty判定から `scripts/.*probe` を除外するパターン追加（kanban_done_guard.pyと同規則へ同期）。

## 優先度: 中 / リスク: 低（未追跡ファイル整理のみ、コード挙動不変）

## v99効果実測（Observée）
- t_df2fa4cc done 19:25、kutuxe read-back: `curl .../l/kutuxe | grep -c agyhq` = **10** / apify = **16**（前回0→有効確認、クローズ）。
- Gumroad sales=0 継続（t_98334cc7 9/11統合判定待ち）、blocked 2件は【要ユーザー対応】維持（t_c186bf62=Smithery鍵 / t_443551e0=Apify Console画面）、生streak=9<10でエスカレーション閾値未達。
