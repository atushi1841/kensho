# t_e6968f4f verification report — Gumroad 販促 X 投稿 週1→週2 拡大

## verification_evidence

- `$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_gumroad_promo.py -q --no-cov` → 29 passed in 1.89s (slot a/b 差異・週2投稿・旧state互換・16種ローテーション 全検証)
- `$ cd /mnt/d/Project2/kensho && python3 scripts/gumroad_promo_weekly.py --slot b --dry-run` → 対象週: 2026-W39 / slot=b / DRY-RUN (新增8種 idx8「Stay ahead of the Japan hobby market」+ utm_campaign=w2026W39_b)
- `$ cd /mnt/d/Project2/kensho && python3 scripts/gumroad_promo_weekly.py --slot a --dry-run` → スキップ: 今週aスロットは投稿済み (week=2026-W39, tweet_id=2103645539585953932) — 旧state互換確認
- `$ (crontab -l; echo '...slot b...') | crontab -` → 金曜 08:40 `gumroad_promo_weekly_slot_b.sh` 追加 (月曜 slot a と4日間隔)
- `$ python3 -m mypy scripts/gumroad_promo_weekly.py --strict` → 0 new errors (pre-existing 13 errors 全部 gumroad_x_post.py 由来・本タスク変更なし)
- `$ python3 scripts/gumroad_promo_kpi.py` → twitter_views=0 参照経路正常 (views=None=当日データ未収集、KPI参照は前日比で判定)

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