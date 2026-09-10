# critic v94 実装レポート — Apify課金状態の二重障害修正（t_360dd497）

日時: 2026-09-11 06:20 JST（run372、run371は検証ループでタイムアウトしたが実装自体は完了済みだった）
対象: scripts/kensho_revenue_collect.py（プロジェクト側）= /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho_revenue_collect.py（プロファイル側、IDENTICAL確認済み）

## 変更内容（カード実装項目 1-5 すべて対応）

1. **APIFY_PPE フォールバックパス修正**: 実在しない `/mnt/d/Project2/kensho/pay_per_event.json` をやめ、`APIFY_PPE_PATHS` の二段試行（`data/tmp/pay_per_event.json` を含む）に変更（L45-49）。
2. **個別アクター取得の _CONTINUE_ 化**: fetch_apify_pricing() の25本ループを per-actor try/except で守り、1本の ConnectTimeout でループ全体を放棄しなくなった（L162）。取得過半数なら部分結果を成功として使用。
3. **異常検知ギャップ塞ぎ + unknown判定**: API失敗かつフォールバック不在/空の場合、billing="unknown"・actors_unknown に計上し、警告文を「Apify課金状態不明（API超時+フォールバック欠損）— 「無料」ではありません」に変更（L474, L768-770）。ppe=0/free>0 の素通りを防止。
4. **24hキャッシュ**: 成功時に `data/apify_pricing_cache.json` へ書込（L53, L86）、次回API失敗時は24h以内キャッシュを優先使用。
5. **Copies drift 解消**: プロファイル側へ同一内容コピー、diff -q = IDENTICAL を実測。

テスト: tests/test_revenue_collect.py に v94セクション追加（unknown判定、警告文、anomaly検知、cache漏れ防止、従来free警告維持 — L485-654）。

## verification_evidence

（1）受入指標1: 次回収集の revenue-daily.json で actors_ppe>=20 — 06:05収集で本番実証済み。

    $ jq '.[-1].apify | {ppe: .actors_ppe, free: .actors_free, unknown: .actors_unknown}' data/revenue-daily.json
    {
      "ppe": 24,
      "free": 1,
      "unknown": 0
    }

（2）意図的テスト（受入指標2）: API不通時の「課金状態不明」扱いを含む v94テスト群 — 43 passed。

    $ python3 -m pytest tests/test_revenue_collect.py -q
    ============================= 43 passed in 10.80s ==============================

（3）項目5: Copies drift 解消確認。

    $ diff -q scripts/kensho_revenue_collect.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho_revenue_collect.py && echo IDENTICAL
    IDENTICAL

（4）項目4: キャッシュ実体生成確認（成功収集時に書込まれている）。

    $ ls -la data/apify_pricing_cache.json
    -rwxrwxrwx 1 atushi atushi 3588 Sep 11 06:05 data/apify_pricing_cache.json

（5）項目3: 修正後コードのunknown判定・警告文の実在確認。

    $ grep -n "課金状態不明" scripts/kensho_revenue_collect.py
    770:        warnings.append("Apify課金状態不明（API超時+フォールバック欠損）— 「無料」ではありません")

## 補足

- ppe=24/free=1: 実測25件中24件PPE課金（japan-market-mcp等）。残る free=1 は実際の無料設定アクターであり、以前の「全件無料誤報（ppe=0/free=25）」とは状態が異なる。「全件が無料設定」警告は発火しない構成（freeのみ・unknown=0かつppe>0のため）。
- revenue-status.html に旧警告文が残っているのは04:20障害時の静的生成物のため、次回報レポート再生成で解消する（QA read-back対象）。
- 全件pytest（533系）のリグレッション確認はQA（kensho-sweeps monitor、コメントで read-back 宣言済み）へ委譲。
