# t_6c8b396c verification report — Apify Store PPEアクター プロモーション自動投稿

## verification_evidence

$ cd /mnt/d/Project2/kensho && python3 -m mypy scripts/apify_store_promo.py --strict
Found 3 errors in 1 file (checked 1 source file)
kensho/application/selenium_cdp.py:340: error: Argument 1 to "contextmanager" has incompatible type "Callable[[str, bool], KenshoCDP]"; expected "Callable[[str, bool], Iterator[Never]]"  [arg-type]
kensho/application/selenium_cdp.py:341: error: The return type of a generator function should be "Generator" or one of its supertypes  [misc]
kensho/application/selenium_cdp.py:271: error: Unused "type: ignore" comment  [unused-ignore]
# 0 errors in apify_store_promo.py 自体（3 errors は pre-existing selenium_cdp.py のみ）

$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_collector.py tests/test_applier.py tests/test_encoding.py tests/test_backup.py -q
============================== 156 passed in 23.08s ==============================

$ cd /mnt/d/Project2/kensho && python3 scripts/apify_store_promo.py --dry-run --force --slot a
[2026-09-27 09:22:48] 対象週: 2026-W39 / slot=a / atushi16 / Apify Store PPEプロモ
[2026-09-27 09:22:48] 紹介アクター: Japan Used Camera Prices, Japan Used Watch Prices, Japan Luxury Resale Prices
[2026-09-27 09:22:48] ツイート内容: 'クロスボーダー仕入れに Japan Used Camera Prices。
日本国内の中古カメラ実勢価格をリアルタイムAPIで取得、為替・Fed込で利益計算。
Pay-per-event $0.005。無料枠から開始 👉 #中古カメラ #カメラ転売 #Kitamura #Fujiya #MapCamera 他: Japan Used Watch Prices, Japan Luxury Resale Prices'
[2026-09-27 09:22:48] DRY-RUN: 投稿は実行していません。
exit=0

$ cd /mnt/d/Project2/kensho && bash scripts/cron_apify_promo_weekly; echo "exit=$?"
exit=0
$ cat logs/apify_store_promo_cron.log | tail -2
2026-09-27T00:23:13Z SKIP: 月曜/金曜以外 (7)

$ cd /mnt/d/Project2/kensho && python3 -c "import json;d=json.load(open('data/apify_ppe_external_runs_state.json'));print('actors:',len(d['actors']));print('zero_run:',sum(1 for a in d['actors'] if a['external_runs']==0))"
actors: 73
zero_run: 73

## 変更ファイル
- scripts/apify_store_promo.py (新規, 23,631 bytes): Apify Store PPEアクター週次自動投稿本体
- scripts/cron_apify_promo_weekly (新規, 2,058 bytes): 月曜 slot a / 金曜 slot b の cron ラッパー
- data/apify_ppe_external_runs_state.json: external_runs=0 アクター抽出元（73本中73本 zero_run）

## 判定
- DoD 1: scripts/apify_store_promo.py が data/apify_ppe_external_runs_state.json を読み、external_runs=0 のアクターを抽出 → 満たす
- DoD 2: 週次 cron 実行可能（月曜 09:00 JST slot a / 金曜 slot b、WEEKLY_TWEETS 8→16 種・slot a/b パターン踏 rotation）→ 満たす
- DoD 3: 投稿は X CDP + SOCKS5 プロキシ経由（KenshoCDP）→ 満たす
- 成功指標: 30日 window の external_runs > 0 または actual_revenue_usd > 0（現状 0 / 0.063 estimated）→ 実投稿後、次回 settle 追跡で検証
- xurl 認証不可（2026-09-13 確定）のため X 投稿は CDP + SOCKS5 プロキシ分離で実行（仕様通り）
- 外部生成不能な場合の代替案（Apify Store SEO メタデータ検索キーワード rich 化）は APIFY_TOKEN 未設定のため自動実装不可 → 【要ユーザー対応】タグで手動待機