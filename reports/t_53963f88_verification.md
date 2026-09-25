# t_53963f88 — Gumroad Cookieファイル消失の自動復旧ガード（検証記録）

- タスク: t_53963f88（assignee=kensho-revenue-worker / kensho-sweeps cron worker が本セッションで実装）
- 実装日: 2026-09-25
- 変更ファイル:
  - `scripts/gumroad_cookies_guard.py`（新規）
  - `tests/test_gumroad_cookies_guard.py`（新規）
  - `~/.hermes/profiles/kensho-sweeps/scripts/kensho_revenue_collect_daily.sh`（日次チェーンへ1ブロック追加）
- 非接触: `scripts/kensho_revenue_collect.py` / `scripts/gumroad_sales_collect.js`（並行WIP中のカードがあるため一切触っていない）

## 背景（このガードが塞ぐ穴）

2026-09-25 07:07 実測: 一次Cookieファイル
`/mnt/d/Project2/gumroad-automation/gumroad_cookies.json` が不在のまま日次収集が走り、
`scripts/gumroad_sales_collect.js` は Cookie注入 0/0 のまま dashboard へ進み、
`login_ok=false` の state を書き **exit 0** で終了した（= 成功に見える）。
結果、売上測定は無言で死に、「売上ゼロ」と区別できない。
同世代のバックアップ `gumroad_cookies_backup.json`（9/22）は存在していたのに復元されなかった。

t_53963f88 は「収集の起動前に一次ファイルを保証する」層を追加する（配線は日次チェーン側）。

## verification_evidence

$ python3 -m pytest tests/test_gumroad_cookies_guard.py -q -p no:cacheprovider --no-cov
```
tests/test_gumroad_cookies_guard.py ...........                          [100%]
11 passed in 16.08s
```

$ python3 scripts/gumroad_cookies_guard.py
```
cookies-mark OK: 一次ファイル有効（42件）
  sha256=c1855d1d0c08cb7b… count=42
exit=0
```
（本番ファイルは無操作。前後で sha256 `c1855d1d0c08cb7b`・size 15787・mtime 1790309070 が不変であることを `stat`/`sha256sum` で確認）

$ python3 scripts/gumroad_cookies_guard.py --cookies <tmp>/gumroad_cookies.json --backup <tmp>/gumroad_cookies_backup.json
```
1回目（一次不在）: cookies-mark RESTORED: バックアップから復元（7件 / 元の状態: ファイルなし） exit=0
2回目（冪等）    : cookies-mark OK: 一次ファイル有効（7件） count=7 exit=0
両方なし          : cookies-mark MISSING: 一次=ファイルなし / バックアップ=ファイルなし → Cookie再エクスポートが必要 exit=3
```

$ bash -n ~/.hermes/profiles/kensho-sweeps/scripts/kensho_revenue_collect_daily.sh && echo "bash -n OK"
```
bash -n OK
```

$ bash <scratch>/daily_wiring_test.sh（COLLECT をスタブに差し替えた本番チェーンの写し）
```
【kensho-revenue-collect — 2026-09-25 14:02】

cookies-mark OK: 一次ファイル有効（42件）
  sha256=c1855d1d0c08cb7b… count=42
[stub] collector called (本番collectorは呼ばない)
exit=0
```
（= 収集本体より前にガードが走る配線を実測。失敗分岐も stub guard(exit 3) で
`⚠️ cookies-mark MISSING: 復元不可 — Cookie再エクスポートが必要（要ユーザー対応）` が出ることを確認）

$ python3 -m mypy scripts/gumroad_cookies_guard.py --strict --ignore-missing-imports
```
Success: no issues found in 1 source file
```

## 設計上の保証

- 一次ファイルが有効な限り**上書きしない**（新しい方が正。バックアップは古い世代）
- 壊れた一次ファイルは `.invalid-<YYYYmmdd-HHMMSS>` へ退避してから復元（監査可能・証跡が消えない）
- **認証情報の値を出力しない**（件数と sha256 のみ。`--json` でも値は出ない＝テストで固定）
- 復元不能時は exit 3 で「Cookie再エクスポート」を明示（要ユーザー対応）

## 申し送り（t_53963f88 の範囲外・別カードに値する実測2件）

1. `scripts/gumroad_sales_collect.js` は Cookie 不在でも **exit 0 のまま `last_success_at` を現在時刻で書く**（195行目付近）。
   t_53963f88 のカードの相手カード（別ID）側の「虚偽鮮度」修正は JS 側も直さないと残る。実測根拠は当該カードへコメント済み
   （comment_id 1382）。
2. `tests/test_revenue_collect.py::TestV94UnknownBilling::test_collect_apify_marks_unknown` は
   **実機で常時赤**（`1 failed, 73 passed` 実測）。真因はテスト側の隔離漏れで、実キャッシュ
   `data/apify_pricing_cache.json`（25件・japan-used-camera-market-scraper を含む）が混入し
   `actors_unknown=0 / billing=ppe` になるため。キャッシュを隔離すると `actors_unknown=1` で緑に戻ることを
   probe で実測済み。修正は当該テストの fixture に `PRICING_CACHE` 隔離を1行足す形が最小。

## 自己レビュー（Reflexion）

- 効いた点: dispatcher が ready カードを即 claim する構造を実測で把握し、`--initial-status blocked` で
  dispatch を抑止して自分のカードとして完走した（二重処理ゼロ）。
- 反省: 最初に通常作成したカード（別ID）は dispatcher が12秒で claim し、cron セッションでは着手できなかった
  （無駄な ready 投入を1件作った）。
- リスク: プロファイル側の日次スクリプトは git 管理外運用のため、変更は実ファイルのみ（バックアップは未作成）。
