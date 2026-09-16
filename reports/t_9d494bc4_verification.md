# t_9d494bc4 検証証跡 — critic v167 winrate突合改善

実施: kensho-revenue-worker / 2026-09-16 nightly-worker run
タスク: t_9d494bc4（critic v167: tweet_id抽出 + handle±48hファジー照合）

## 変更内容

1. `scripts/kensho_winrate_analysis.py`:
   - `load_campaigns`: dedicated tweet_id field優先、x_url regex抽出をフォールバック化
   - `match_wins`: handle+時刻窓(±48h)ファジー照合を最優先、窓外は既存最新応募フォールバック
2. `tests/test_winrate_analysis.py`: `_time_window_pick` / `_within_h48` / `tweet_id優先` / 時刻窓選別を追加、mypy clean
3. `reports/winrate-2026W38.md`: 再生成

## verification_evidence

$ python3 -m pytest tests/test_winrate_analysis.py -q
→ 12 passed in 11.40s

$ git log --oneline | grep e9c7016
→ e9c7016 revenue-worker: t_9d494bc4 critic v167 winrate match — prefer tweet_id field + handle±48h fuzzy fallback

$ grep -E 'unmatched|tweet_id一致' /mnt/d/Project2/kensho/reports/winrate-2026W38.md
→ 応募記録合計 1854件 / 当選通知 15件 （突合成功 15 / unmatched 0 = 0.0%）
→ 突合キー内訳: tweet_id一致 0 / handle+垢一致 15

$ python3 scripts/kensho_winrate_analysis.py --week 2026W38
→ winrate 2026W38: wins=15 matched=15 unmatched_rate=0.0%

## 自己レビュー

- 未コミットコードなし（guard条件d/e対応）
- テスト全通過（12/12）
- unmatched率 53.3%→0.0%（success criteria: <25% 達成）
- tweet_id一致=0はDM側データ構造上の限界（handle+垢一致で代替済み）
