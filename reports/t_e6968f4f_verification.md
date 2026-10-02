# t_e6968f4f verification report — Gumroad 販促 X 投稿 週1→週2 拡大

## verification_evidence

$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_gumroad_promo.py -q --no-cov
============================== 29 passed in 1.89s ==============================

$ cd /mnt/d/Project2/kensho && python3 scripts/gumroad_promo_weekly.py --slot b --dry-run
対象週: 2026-W39 / slot=b / atushi16 / 週次販促投稿
ツイート内容: 'Stay ahead of the Japan hobby market. Free sample: https://atushi5.gumroad.com/l/kutuxe?utm_source=tw&utm_medium=s&utm_campaign=w2026W39_b Deep dive: https://atushi5.gumroad.com/l/qdyyyi?utm_source=tw&utm_medium=s&utm_campaign=w2026W39_b #priceguide'
DRY-RUN: 投稿は実行していません。

$ cd /mnt/d/Project2/kensho && python3 scripts/gumroad_promo_weekly.py --slot a --dry-run
スキップ: 今週aスロットは投稿済み (week=2026-W39, tweet_id=2103645539585953932)

$ crontab -l | grep -i gumroad
40 8 * * 1 /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_promo_weekly.sh > /dev/null 2>&1
40 8 * * 5 /home/atushi/.hermes/profiles/kensho-revenue-worker/scripts/gumroad_promo_weekly_slot_b.sh > /dev/null 2>&1

$ cd /mnt/d/Project2/kensho && git log --oneline -1
f426bee feat(gumroad): X販促投稿 週1→週2拡大 (t_e6968f4f) — WEEKLY_TWEETS 8→16種、slot a/b、金曜cron追加、state構造化

## 変更ファイル
- scripts/gumroad_promo_weekly.py: WEEKLY_TWEETS 8→16種、SLOTS/pick_text(slot)/_slot_index 追加、state 年構造化
- tests/test_gumroad_promo.py: 10→29 テスト (slot a/b 差異・旧state互換・週2投稿・16種)
- scripts/gumroad_promo_weekly_slot_b.sh (新規): 金曜 08:40 slot b 実行ラッパー
- crontab: 金曜 08:40 slot b エントリ追加
- data/gumroad_promo_weekly_state.json: 旧平構造 → {week: {slot: ...}} に移行

## 判定
- 月間 X 投稿数 4→8/月 (週1→週2)
- twitter_views 参照経路は t_b8ec048a の utm 計測をそのまま継承 (campaign=w{week}_{slot} で区別)
- 旧 t_3848cbde state は slot=a として互換 (W39 実投稿は再実行されない)
- BOT 検知回避: 月曜↔金曜 4日間隔 + 週×スロットで独立文言