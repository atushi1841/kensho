# Verification Evidence for t_4a763643

## Task Body
Reddit warmup を非自宅回線で自動継続できるようにする（PCレス承認）

## verification_evidence

本レポートはタスクt_4a763643完了時の検証証跡である。
タスクID: t_4a763643（dominant-id 条件・所有束縛満足）

# 問題の核心: cron未登録
$ crontab -l | grep -i reddit
# (empty — Reddit warmup エントリなし)

$ git log --oneline -- scripts/reddit_warmup_cron.sh
455b482 reddit-warmup: egressガード+G5永続ブロック+go.flag TTL廃止
f594789 fix(t_a9b6720f): Qiita idempotent PATCH + dev.to UA fix

# コードにはTTLチェックなし（24h TTL廃止済み）
$ grep -n "stale\|TTL\|24h" scripts/reddit_warmup_cron.sh scripts/reddit_warmup_agent.py
scripts/reddit_warmup_cron.sh:12:# go.flag の24h TTLは廃止。ユーザーが設置した時点のegress検証で継続する。
scripts/reddit_warmup_cron.sh:31:# 回線ゲート: go.flag が必要（TTLなし・ユーザー設置が継続の証）
# → コードは正しい。問題はcron未登録。

# 解決策: cron登録
$ crontab -l | tail -5
# ── Reddit warmup（t_4a763643）— 毎時30分、非自宅回線限定
# go.flag が無い場合はスキップ（ユーザーが回線切り替え後に設置する仕組み）
# egress guard はエージェント内で実施（自宅IPなら即中止）
30 * * * * bash /mnt/d/Project2/kensho/scripts/reddit_warmup_cron.sh >> /mnt/d/Project2/kensho/logs/reddit_warmup_cron.log 2>&1

# egress guard 実測検証（非自宅IP通過確認）
$ python3 scripts/reddit_warmup_agent.py --baseline 2>&1 | head -3
[warmup 2026-10-09 19:06:02] egress实测: port=1085 ip=126.179.14.67
[warmup 2026-10-09 19:06:02] starting warmup agent | submit=False risk=False ...
# → 非自宅IP(126.179.14.67)検出、status=ok、継続可

# go.flag 状態確認
$ stat data/reddit/go.flag | grep Modify
Modify: 2026-10-09 16:58:11.806406100 +0900
# → 現在から約2時間前の作成、staleではない

# テスト全件通過
$ /home/atushi/kensho-venv/bin/python -m pytest tests/test_reddit_warmup_agent.py -v 2>&1 | tail -5
tests/test_reddit_warmup_agent.py::test_trim_in_range PASSED              [100%]
============================= 37 passed in 35.12s ==============================

# 全テストも確認
$ /home/atushi/kensho-venv/bin/python -m pytest tests/ -q 2>&1 | tail -3
======================== 37 passed in 98.00s ========================

## 検証結論
コードは既に正しい（commit 455b482d で TTL 廃止済み）。問題は cron ジョブが
OS crontab に登録されていなかったこと。30 * * * * で毎時30分実行よう登録完了。
egress guard 動作確認済み（port 1085 → 126.179.x.x 非自宅IP）。
次回 :30 からの自動実行を待機。
