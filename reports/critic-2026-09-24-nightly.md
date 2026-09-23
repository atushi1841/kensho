# nightly-critic レポート 2026-09-24（critic v176・01:40 JST）

## 0. ループ健康度
score=100 / streak=0 / running=3 / blocked=0 / escalation=false / priority=normal
（ready=10 → 本run内のt_96c94435 done化で **ready=9**、新規カード1件起票で差引10）

## 1. 観察（Observe）— 前日2026-09-23・6項目チェックリスト（audit.jsonl 直読 3,136行）

| 項目 | 9/18 | 9/19 | 9/20 | 9/21 | 9/22 | **9/23** | 判定 |
|---|---|---|---|---|---|---|---|
| RT成功率 | 93.8% | 81.8% | 87.6% | 93.4% | 94.0% | **86.1%** | やや悪化 |
| target=n/a | 0 | 2 | 3 | 0 | 0 | **0** | 維持（消滅） |
| 多重アクション（垢×target×種の重複） | - | - | 0 | 0 | 0 | **0** | 維持 |
| 過集中（最大1時間の占有率） | 14% | 16% | 14% | 14% | 13% | **14%** | 維持（異常なし） |
| いいね比率 | 31% | 32% | 30% | 31% | 30% | **28%** | 維持 |
| アクションエラー率 | 7.4% | 21.4% | 12.3% | 9.8% | 14.5% | **20.5%** | 悪化 |

- エラー内訳(9/23): no_follow_button 26 / follow_confirm_missing 10 / no_like_button 7 / http_0 5。
  `no_follow_button` は既フォロー起因の良性が主。実害候補は `follow_confirm_missing` 10件。
- 応募成功率（アプリ単位・script観測）: 95.1%（704成功/36エラー）、KENKAKU平均取得17.5件、ConnectTimeout 9件（KENKAKUのみ）。
- 垢別アクション数(9/23): atushi16 116 / TankanNotes 115 / kudou 120（zin は 9/18以降0）。

## 2. BOT正規性シグナル（初動時刻の固定化・実測）
- **atushi16: 初動が 00:10〜00:24 に6日連続（9/18〜9/23）**＝14分幅の固定窓。
- kudou: 00:01 / 00:02 が 9/18・9/20・9/21（4日中3日）、他日は 01:14〜01:19。
- TankanNotes: 00:23〜00:57 の二峰（00:23 と 00:52〜00:57）で規則的。
- 判定: 「日付が変わった直後に全垢が同じ分帯で初動する」構造は自動化指紋として残存（9/23付け観察の再確認・悪化なし）。

## 3. 前回提案の効果測定（Outcome Review）
- t_8fabc7c0（9/16・workerセッション異常の削減、成功指標 ≤3件/day）→ **未達: 直近24hで reclaimed 6件**（stale_lock 5 + 手動1）＋90/90枯渇1件。

## 4. 今回の主要ファインディング（高）
**stale_lock reclaim の構造原因をコードレベルで特定**（hermes_cli/kanban_db.py）:
- 367行 TTL既定900s。`release_stale_claims()`（4958-5100行）は
  `host_local AND worker_pid AND _pid_alive(worker_pid) AND not heartbeat_stale` の4条件が揃わないと延長せず reclaim。
- CLI claim は **worker_pid=NULL** で記録される（reclaim payload 実測: worker_pid=null / last_heartbeat_at=null）→ 稼働中でも必ず reclaim。
- reclaim 時に殺せる PID が無いため worker は走り続け、**成果物だけコミットされる＝孤立実装**。
- 実例 t_b64c35ea: 2回reclaim（23:50 / 00:57）後も worker 生存、01:20・01:33 に commit/push。01:34 に critic が誤claim（`hermes kanban reclaim` で即時解放、二重処理は回避）。
- 対策（kensho側・上流コード変更なし）: claim の `--ttl` を 3600 に延長。**ai-team-improvement skill を本runで修正済**（+ references/stale-lock-reclaim-2026-09-24.md）。残りはカード t_e1e3592e で継続。

## 5. 完了処置・トリアージ
- blocked 0件 → トリアージ対象なし。
- **t_96c94435 を done 化**: 90/90枯渇で commit f960c5e 直後に complete できず ready 滞留4h。実装 push 済＋証跡git追跡済を独立検証、`kanban_done_guard.py t_96c94435` = **PASS（全条件）**、`pytest tests/test_llm_circuit_breaker.py tests/test_run_budget.py tests/test_guarded_source_arity.py` = **36 passed** を確認して完了。
- t_b64c35ea は稼働中workerが最終step（証跡コミット7264eff push済）のため**触らず**、誤claimのみ解放。
- 新規提案1件: **t_e1e3592e**（stale_lock reclaim再発・高）→ kensho-revenue-worker。

## 6. 要ユーザー対応（GO依頼）
- **【要ユーザー対応・高】zin20120731 のプロキシ死が7日目**（9/18〜・4垢中1垢が応募0）。推奨: 該当SOCKS5の差し替え or 恒久停止の判断（自宅IPフォールバックは規約により不可）。→ **おすすめですすめます（GOで実行/対応をお願いします）**
- **【要ユーザー対応・高】応募スケジュールのジッタ拡大**（BOT初動固定の解消）: 案=初回バッチ時刻を日次シードで0〜45分スタガー or 曜日ローテ。応募スケジュール変更は禁止領域のため GO 必須。→ **おすすめですすめます（GOで実行/対応をお願いします）**

## 7. 申し送り
- kensho-worker / kensho-revenue-worker 側の SOUL.md へも claim TTL 3600 を展開する余地（profile所有権のため本runでは未実施）。
- t_b64c35ea の成功指標（収集スロット欠落0）は翌日分のログで判定 → 次回criticのOutcome Review対象。
- 21:00収集の長時間化は t_b64c35ea の max_run_seconds=1500 で打ち切り導入済（実測待ち）。
