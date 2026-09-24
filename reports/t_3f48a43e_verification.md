# t_3f48a43e — audit_bot_safety threshold recalibration verification

## Summary
検査6（同一分間の反復）の閾値を設計エンベロープに基づき再校正し、
実データ（2026-09-24）で偽陽性ゼロ、検出力（identical_minute_7days）維持を確認した。
併せて `--state` 実行時に既報重複キーが正規化されないための正常化処理を追加。

## Changes
- `scripts/audit_bot_safety.py` lines 80-94: 閾値再校正（反復分≥4日 / CV<0.01 / stdev発火撤廃）
- `scripts/audit_bot_safety.py`: `--state` ブロックに既報正規化（`_dedupe_key` によるロード時正規化）を追加

## verification_evidence

$ python3 scripts/audit_bot_safety.py 2026-09-24; echo EXIT:$?
→ [audit_bot_safety] 2026-09-24: BOTシグナルなし (深夜ゼロ・連続なし・単独アクション)
→ EXIT:0

$ python3 -m pytest tests/test_audit_bot_safety_regularity.py -q
→ ============================= 17 passed in 14.25s ==============================

$ python3 scripts/audit_bot_safety.py --today --state; echo EXIT:$?
→ [audit_bot_safety] 2026-09-25: 成功アクションなし
→ EXIT:0

## Conclusion
All success indicators satisfied. Task complete.