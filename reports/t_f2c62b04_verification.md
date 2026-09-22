# t_f2c62b04 KENKAKU ConnectTimeout 源別偏重対策 — 検証証跡

## objective
ken-kaku.com 収集のみに ConnectTimeout が7件/day 偏重（KCLUB/KEMA/CPMKは0件）。
collect側の KENKAKU リトライ/タイムアウト設定を他源と同等に調整し、設計不均衡を解消する。

## 根因特定
t_1cae393c が fail-fast 目的で KENKAKU timeout を 30s→10s に短縮していた。それにより
ken-kaku.com の遅延TCP受付（>10s かつ <30s）の接続が ConnectTimeout として即断されるため
KENKAKU 単独でタイムアウトが発生。他源は timeout=30 のため偏重が出ていた。

## 変更
- `kensho/scraping/sources/kenkaku.py`: `_KENKAKU_TIMEOUT` 10s→30s に復元（他源と同じ値）
- `tests/test_kenkaku_retry.py`: 回帰ガード追加 `test_timeout_matches_other_sources`

## verification_evidence
- t_f2c62b04: `grep -n "timeout" kensho/scraping/sources/common.py` → `timeout: int = 30`（他源デフォルトは30s）
- t_f2c62b04: `grep -n "timeout=30" kensho/scraping/sources/kema.py kensho/scraping/sources/cpmeikan.py kensho/scraping/sources/kenshouclub.py kensho/scraping/sources/kensho_everyday.py` → KEMA/CPMK/KCLUB/KENS-EVERY 全て timeout=30
- t_f2c62b04: `git show -s --format=%B 5104f88` → "kenkaku.py: timeout 30s→10s短縮"（偏重の発生源を確認）
- t_f2c62b04: `git show 5104f88~1:kensho/scraping/sources/kenkaku.py` → 短縮前は30s
- t_f2c62b04: `grep -n "_KENKAKU_TIMEOUT" kensho/scraping/sources/kenkaku.py` → `_KENKAKU_TIMEOUT: int = 30`（30sへ復元確認）
- t_f2c62b04: `grep -n "test_timeout_matches_other_sources" tests/test_kenkaku_retry.py` → `assert kenkaku._KENKAKU_TIMEOUT == 30`
- t_f2c62b04: `python -m pytest tests/test_kenkaku_retry.py -q` → `13 passed in 28.08s`

## 残課題（QA委譲：3日間数値検証）
成功指標「実行後3日間のConnectTimeout合計が平均3件/day以下」は観察期間が要るため本runでは
判定不可。QAが日次ログで推移を監視する。
- `grep -c ConnectTimeout /mnt/d/Project2/kensho/data/*.log 2>/dev/null` で日次件数推移確認
- `tail -50 /mnt/d/Project2/kensho/data/collect_*.log | grep -i "timeout"` で源別内訳確認
