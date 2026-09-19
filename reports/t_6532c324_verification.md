# t_6532c324 verification — applier.py log.write型不一致 root cause

- 日付: 2026-09-19
- 担当: kensho-revenue-worker
- タスク: t_6532c324（【提案】applier.py log.write型不一致の根本原因解明+適用可能パッチ草案。適用はユーザーGO待ち・禁止領域）
- 成功指標: reports/applier_logwrite_fix.md が存在し root cause + 最小パッチdiff を記載 / kensho/application/ の変更0ファイル

## verification_evidence

$ git status --porcelain kensho/application/
（実行結果: 空出力 = kensho/application/** 未変更・禁止領域クリーン）

$ ls reports/applier_logwrite_fix.md
reports/applier_logwrite_fix.md

$ git -C /mnt/d/Project2/kensho log --oneline -1
ec3e396 docs(evidence): t_ef9e899f loop_health role_summary context curation verification evidence

$ grep -n "_multi_response_record(tweet_id, account_key, cfg, out)" /mnt/d/Project2/kensho/kensho/application/applier.py
2257:  _multi_response_record(tweet_id, account_key, cfg, out)

$ sed -n '446,508p' /mnt/d/Project2/kensho/kensho/application/applier.py
446:def _multi_response_record(tweet_id, account_key, cfg, log: Any, state_path: Path | None = None):
507:                    if log is not None:
508:                        log.write(msg)

$ grep -n "def out(msg" /mnt/d/Project2/kensho/kensho/application/applier.py
814:    def out(msg: str) -> None:

確定した進捗（root cause）:
- apply_for_account (applier.py:681) 内のローカル関数 out (L814) を、_multi_response_record(L446) の
  log 引数(最後に log.write(L508) を要求)へ誤って渡しているのが applier.py:2257。
- out は関数オブジェクト → .write を持たず AttributeError: 'function' object has no attribute 'write'。
- この例外は apply ループの例外ハンドラ (L2418→L2425 out(...[NG]...write (url=...))) で捕捉され、
  [NG] として error 誤集計。2026-09-18 追加機能「複数同時刻応答検知」の新設呼び出しが発端。
- 最小パッチ: applier.py:2257 の第4引数を out → log の1行変更。類縁経路は grep で全て正確と確認済み。
- 適用はユーザーGO待ち。kensho/application/ は未変更。
