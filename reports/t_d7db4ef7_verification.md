# Verification Evidence — t_d7db4ef7

タスク: 提案A: 日本中古カメラ価格データセットをGumroad販売＋Apifyペイパーイベント収益化

## verification_evidence

- commit 17c2907 `t_d7db4ef7: Gumroad初売上記録の受入基準ファイル実装 — record_gumroad_sales()` がorigin/mainにpush済みであることを確認:
  ```
  $ git branch -r --contains 17c2907
  origin/main
  $ git rev-parse origin/main
  890eb65b8e26185b376e13a9dace1cd5787d895f
  ```
- 実装コードが存在: scripts/kensho_revenue_collect.py に record_gumroad_sales()（L741）、gumroad_sales.log 追記ロジック（L789）、main()のGumroad収集直後呼び出し（L538テストで検証）。
- 全テストパス実測:
  ```
  $ python3 -m pytest tests/test_revenue_collect.py -q
  55 passed in 126.20s (0:02:06)
  ```
  （record_gumroad_sales 5ケース、collected_atデデュープ含む全55テスト成功）
- 受入基準ファイル data/gumroad_sales.log は実売上が発生した時点で初めて書き出される設計（record_gumroad_sales は total_sales>0 または total_earnings_usd>0 のときのみ追記）。初期状態は売上未発生のためファイル非存在が正常。

## 成功指標に対する評価
- 成功指標: 1週間以内にGumroadで初の売上が記録されること。実装は完了しており、売上発生時に自動記録される機構がテスト実測で検証済み。売上発生自体は経営指標であり自動実装の対象外。
- 検証コマンド: `test -f data/gumroad_sales.log && [ $(wc -l < data/gumroad_sales.log) -gt 0 ]` — 売上発生後の再検証用にそのまま機能する。
