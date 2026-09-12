# critic v138: hunter monetizationゲート強化（wrapper_free 無料ラッパ型OSS除外）— 実装記録 (t_117de0fe)

- Commit: e5295b0 feat(hunter): critic v138 wrapper_free gate

- 変更: kensho-non-api-revenue-hunter.py quality_gate() に要件1b `wrapper_free` 追加。
  score < WRAPPER_FREE_MAX_SCORE(10) かつ タイトル/要旨/URLが free|open-source|MIT|extension|
  無料|オープンソース|拡張機能 に該当 + github.com 直リンク系 = monetizationシグナル通過でも
  投入前にスキップ。gate_stats に wrapper_free 計上、レポートの gate_breakdown・評価基準節に反映。
- 根拠: 9/7 Blunderbase → 9/12 Claude Read Aloud（HN score3/GitHub5star/MIT/無料ラッパ型、
  3点不成立でworker評価リソース消費）の再発2件。t_6e2d4279 hnslop（extension型）も同特征。
- テスト: tests/test_non_api_revenue_hunter_gate.py に TestWrapperFreeGate 5件追加
  （実ケース再現・score>=10除外・GitHub無し除外・境界値）。
- プロファイル実体 ~/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
  へ同期（md5一致、cron実行経路はプロファイル側）。

## verification_evidence

（t_117de0fe 実装検証：pytest回帰 + gate挙動liveスクリプト + プロファイルmd5同期）

```
$ cd /mnt/d/Project2/kensho && python3 -m pytest tests/test_non_api_revenue_hunter_gate.py -q -p no:cacheprovider --no-cov
tests/test_non_api_revenue_hunter_gate.py ........................       [100%]
============================== 24 passed in 7.25s ==============================
```

```
$ python3 /tmp/v138_gate_check.py
old_gate_monetization_passes = True
new_gate = ('wrapper_free', '(gate) 無料ラッパ型OSS (score=3 < 10 + GitHub直リンク) でスキップ')
score12 = None
paid_saas = None
```
（t_c979410c 実ケース=HN score3+MIT/extension+GitHub直リンクは旧monetizationゲートを通過していた
ことを確認した上で新gate=wrapper_freeでスキップ。score12と有料SaaS(GitHub直リンク無し)は通過=過剰フィルタ無し）

```
$ md5sum /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
b5cea462b6b7642127973cc8a57eb12d  /mnt/d/Project2/kensho/kensho-non-api-revenue-hunter.py
b5cea462b6b7642127973cc8a57eb12d  /home/atushi/.hermes/profiles/kensho-sweeps/scripts/kensho-non-api-revenue-hunter.py
```
（pre-commit ruff整形後の最終md5。pytest 24件は整形後コードでも再実行し全pass確認済）

- 成功指標の live 検証は 9/13 16:00 Hunterレポート（cron経路）で gate_stats.wrapper_free>=1
  or 同型新規投入0件。タスク本文の検証コマンド:
  `grep -E 'wrapper_free|\[ok\]' /home/atushi/.hermes/profiles/kensho-sweeps/cron/output/non-api-hunter/2026-09-13_16*.md`
- 失敗時代替案（スコア緩和三段/低優先投入化）は QA 中間検証で過剰フィルタ検出時のみ発動。
