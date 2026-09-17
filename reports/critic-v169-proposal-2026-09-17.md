# critic v169 提案 — 2026-09-17 (t_83759a2e)

提案: 応募停止の早期検知（稼働窓2h完了0で通知＋spawnスクリプトpgrep自己マッチ静的検査）
assignee: kensho-revenue-worker / priority 1 / idempotency-key: critic-20260917-v169-stallcheck

## エビデンス（2026-09-17 05:21 実測）
- `grep -c '完了' logs/auto_20260917.log` = **0**（9/15=653行）
- `grep -c 'orchestrator.py' logs/auto_20260917.log` = **0**（spawnは毎tick4垢だが中身が走らない）
- `data/actions.db` = **0バイト**（幽霊DB）
- 停止開始: 9/16 05:34（t_ed8baffa が kensho-auto-apply.sh:108 に覚醒後ガードを追加）
- 真因: `pgrep -f 'kensho/orchestrator.py --account $acct'` が `flock -n ... -c "... orchestrator.py --account X ..."` の内側で走り自己マッチ→常に exit 0

## 再発防止の死角
9/16 05:34 の停止は 9/17 02:2x（QA）まで約21時間検知されなかった。loop_health の business gate は 9/17 02:44 に追加（t_08b42528）、完了マーカー修正は 04:51（t_e474c675）で稼働。ただし検知は次回 critic run 依存で、push通知は無い。

## 提案（検知層のみ・禁止領域に非該当）
1. 稼働窓（09:00-23:00）で当日完了行0が2時間継続→1回だけ通知（30分毎cron、平常時 [SILENT]）
2. spawnスクリプトの `pgrep -f` 自己マッチを静的検査（回帰ゲート化）

成功指標: 検知遅延 21h → 2h以内 / 静的検査 exit1(壊)・exit0(健全) / 平常時通知0件

## blockedトリアージ（3件・全て手動待ち）
| task | 分類 | 理由 |
|---|---|---|
| t_9f37e5e3 | 手動待ち | 応募パイプライン改修＝禁止領域→要ユーザーGO |
| t_55210446 | 手動待ち | GUMROAD_TOKEN 不在（自動復旧不能） |
| t_06fdd792 | 手動待ち | 90/90枯渇×2→スコープ縮小 or 継続のユーザー判断 |
