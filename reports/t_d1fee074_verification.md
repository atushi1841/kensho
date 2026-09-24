# t_d1fee074 — 再検証: 自律履歴の本番安定性確認

## 検証日時
2026-09-25 03:59 JST

## 親タスク完了時刻
- t_37e25225: 2026-09-25 03:44 JST (完了)
- t_5dff275b: 2026-09-25 03:44 JST (完了)
- t_adc65737: 2026-09-25 03:44 JST (完了)

## 検証結果サマリ

### 受け入れ条件

| 条件 | 判定 | 実測根拠 |
|------|------|----------|
| 1. アカウント単位のサーキットブレーカー (attempts=3 抑制) | **PASS** | 事前窓 09-18..09-24: attempts=3 ライン 64件→事後窓 09-24 09:19..09-25 03:40: 0件。最大 CEILING 連続失敗 3→2。 |
| 2. ネットワーク圏外スキップ (network_outage_skip 実発火) | **FAIL** (構造的到達不能) | applier.py:885-903 は applier.py:855-871 と同一入力の到達不能コード。圏外垢 zin20120731 は orchestrator で「処理待ちのバッチなし」となり applier 起動されず。実発火ログ 0件。 |
| 3. before/after 数値比較 | **PASS** | 事前 7日窓 (09-18..09-24): self_heal 発動 32件、全件 attempts=3。事後 18.7h窓 (09-24 09:19..09-25 03:40): attempts=3 ライン 0件、最大 ceiling 2回、goto failed 7件。 |
| 4. BOT制約値 unchanged | **PASS** | rate_limits / max_attempts の緩和 0件。構成不変。 |

### 7日連続 push 条件
- **結果:** 未達 (FAIL)
- 事前 7日窓 (09-18..09-24): `docs/daily_reports/` push 3日分 (09-22, 09-23, 09-24) = 3/7日
- origin/main への push は cron 環境の credential 不在により 0回成功。他エージェントの便乗 push あり。
- 2026-09-25 現在、7日連続 push の証跡はない。

### complete_watchdog コメント送信
- **結果:** 0件の失敗 (100% 成功)
- 修正後 (2026-09-24 05:00以降) 観測ラン数 5件、 `comment failed` 0件。
- DB task_comments id=1133 に t_adc65737 コメント 1件存在。重複リマインド 0件。

### retry attempts=3 抑制
- 事前窓 (09-18..09-24 09:19): attempts=3 ライン 64件 (self_heal 回復失敗)
- 事後窓即時 (09-24 09:19..09-25 03:40): attempts=3 ライン 0件
- 最大連続失敗 (CEILING): 事前 3回→事後 2回 (上限値低減)
- 推奨: 垢単位サーキットブレーカーの継続運用

## 検証コマンド
```
$ bash ~/.hermes/profiles/kensho-sweeps/scripts/kanban_done_guard.py t_d1fee074 --workdir /mnt/d/Project2/kensho --task
$ git log --format="%h %ci %s" -- docs/daily_reports/
$ python3 -m pytest tests/test_self_heal.py -q --no-cov
$ grep -c "comment failed" logs/complete_watchdog_cron.log
$ python3 /home/atushi/.hermes/profiles/kensho-qa/cache/scratch/scan_days.py
```

## 主要ファイル
- `reports/t_d1fee074_evidence.json` — 機械読み取り可能な証跡
- `scripts/scan_days.py`, `scripts/analyze_ceiling.py` — 解析スクリプト

## 申し送り (Follow-ups)
1. **7日連続 push 条件:** 48h 経過後の再監視を child カード t_?????? へ委譲
2. **ネットワーク圏外スキップ:** 到達不能コードの除去または明記（既存の FAIL 状態を受け入れ、将来のリファクタで対応）
3. **zin_AW6povo / chugakujuken_RM10JE_S WiFi 復旧:** 物理的なプロファイル復旧が必要（応募不可垢）