# t_c189d8d8 検証レポート — BOT検出リスク低減のためのセッション行動パターン改善

Task: t_c189d8d8
Assessor: kensho-worker
Date: 2026-09-18
Status: 3提案すべてコミット済み・コード実測確認（early_complete）

## 検証対象

t_c189d8d8 の3提案を HEAD ブランチ履歴内で確認した。

1. 提案1 セッション内行動異常検知: 連続RT/いいね5回で強制終了（applier.py）
2. 提案2 FLOCKハング対策: setsid + kill -TERM -PGID（kensho-auto-apply.sh / kensho-hang-watchdog.sh）
3. 提案3 死んだプロキシをステータスHTMLで原因明記（gen_status_data.py / gen_status_html.py）

## verification_evidence

採用コミットの祖先性（HEAD 履歴内かを成立証明）:

```
$ git merge-base --is-ancestor 7e31a4f HEAD && echo 7e31a4f YES
7e31a4f YES
$ git merge-base --is-ancestor cb829b6 HEAD && echo cb829b6 YES
cb829b6 YES
$ git merge-base --is-ancestor 06bf8be HEAD && echo 06bf8be YES
06bf8be YES
```

提案1のコード反映（applier.py 内の異常検知カウンタ/abortフラグ/configキー）:

```
$ grep -n "anomaly\|consecutive_rt_like\|_anomaly_abort" kensho/application/applier.py
793: consecutive_rt_like: int = 0
795: _anomaly_abort: bool = False
849: anomaly_max_rt_like: int = int(anomaly_cfg.get("anomaly_max_consecutive_rt_like", 5))
1989: consecutive_rt_like += 1
1990: if consecutive_rt_like >= anomaly_max_rt_like:
1995: _anomaly_abort = True
```

提案2のコード反映（setsid flock + watchdog PGID TERM→KILL昇格）:

```
$ grep -n "setsid" kensho-auto-apply.sh; grep -n "PGID\|SIGKILL" scripts/kensho-hang-watchdog.sh
118: setsid flock -n "$LOCK_DIR/$acct.lock" -c "
58-61: PGID特定（setsid ⇒ orchestrator.py の PGID == flock.pid）
69: kill -TERM -- "-$PG"
80: kill -KILL -- "-$PG"
```

提案3のコード反映（status HTML の dead_proxy 原因バッジ）:

```
$ grep -n "dead_proxy" scripts/gen_status_data.py scripts/gen_status_html.py
scripts/gen_status_data.py:619: # 死骸は status:dead_proxy で示す
scripts/gen_status_data.py:707: # status/<acct>.json を垢別に書き出し
scripts/gen_status_html.py:338: if pstatus == "dead_proxy":
scripts/gen_status_html.py:339: state_badge = '<span class="badge bg-red">status:dead_proxy</span>'
```

テスト実測:

```
$ python -m pytest tests/test_applier.py -q
============================= 89 passed in 17.56s ==============================
```

## 監視指標に関する申し送り

「30日間BOT警告/凍結ゼロ」「異常検知発生率 < 5%」は短期計測の外（実運用データが必要）のため、本レポートでは実測対象外。QA側で運用ログの監視指標として継続確認する。

## 作業ツリー残留

本タスク不関与の他ワーカー由来ファイル（data/status/*.json, reports/*.md）のみ。コード未コミットなし。
