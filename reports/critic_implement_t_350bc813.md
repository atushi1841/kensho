# t_350bc813 — KENKAKU/KENS-EVERY ConnectTimeoutリカバリ強化（early_complete確認）

該当修正は既に commit `59bc5ce` でマージ済み。タスク受理条件の再検証を実施、コミットハッシュ・テスト合格を確認したため early_complete とした。

## verification_evidence
$ git log --oneline -5
59bc5ce fix(collect): t_350bc813 KENKAKU/KENS-EVERY ConnectTimeoutリカバリ強化
e076030 feat(compaction): team memory compact script (Anthropic compaction pattern)
f794699 docs(status): t_d2b1ba39 verification evidence
e606bbe fix(status): t_d2b1ba39 直近実行の成功率偽陽性修正（benign行でwarn化→実エラー基準へ）
d3ea842 docs: t_c76075ca - report dominant-id ownership fix (t_c76075ca>t_455add05) for done guard

$ git show 59bc5ce --stat
kensho/scraping/sources/kenkaku.py         |  12 ++--
kensho/scraping/sources/kensho_everyday.py |   6 +-
tests/test_kenkaku_retry.py                |  56 +++++++--------
tests/test_kensho_everyday_retry.py        | 106 +++++++++++++++++++++++++++++
4 files changed, 146 insertions(+), 34 deletions(-)

$ python -m pytest tests/test_kenkaku_retry.py tests/test_kensho_everyday_retry.py -q
============================= 14 passed in 30.30s ==============================

受理条件対応確認:
1. KENKAKU: _KENKAKU_MAX_RETRIES 3→5、_KENKAKU_RETRY_BACKOFF 2.0→3.0 + 上限10sキャップ（3,6,10,10,10）— 指数バックオフ導入で完全drop回避。
2. KENS-EVERY RSS: 裸の fetch() → common._fetch_with_retry(source="kensho-everyday", timeout=30) に変更。ConnectTimeoutで指数バックオフリトライ + source_health継続監視で完全drop回避。
3. 応募ロジック・プロキシ・BOT設定は非変更（変更ファイルは収集ソース2ファイルとテストのみ）。

作業ツリーは collect 関連のソース変更なし（uncommitted は data/status 等の実行時データのみ）。
