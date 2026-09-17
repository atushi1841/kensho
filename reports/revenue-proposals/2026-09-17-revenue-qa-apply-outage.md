# kensho-revenue-qa — 2026-09-17 02:2x 実行レポート（apply停止インシデント）

## 0. ループ健康度（script注入値 / 実測）
```json
{"score":100,"stagnation_streak":0,"priority":"normal","escalation_active":false,
 "state_file":"/home/atushi/.hermes/profiles/kensho-sweeps/data/loop_health_state.json",
 "last_run_ts":"2026-09-17T02:10:59+09:00"}
```
判定: **healthy（AIチームのボード運用としては健全）**。ただし後述のとおり、この指標は**応募パイプラインの死活を見ていない**（36時間停止中もscore=100のまま）。

## 1. 実測サマリ
| 項目 | 実測値 | コマンド |
|---|---|---|
| 9/16 完了行 | **0**（9/15=653） | `grep -c 完了 logs/auto_20260916.log` |
| 9/16 成功/エラー | 0 / 0 | `grep -c 成功\|エラー logs/auto_20260916.log` |
| 9/16 最終worker行 | **05:30:14** | `grep -E "^2026-09-16" logs/auto_20260916.log \| tail -3` |
| 9/17 worker行 | **0**（10tick、spawnは毎tick4垢） | `grep -c 処理待ち logs/auto_20260917.log` |
| audit.jsonl | 9/15=196行 → 9/16=**3行** | `grep -oE '"timestamp": "2026-09-1[567]' data/audit.jsonl \| sort \| uniq -c` |
| daily_counts | 9/16=4アクション | `cat data/daily_counts.json` |
| actions.db | 0バイト幽霊DB（mtime 9/16 12:47、生成コード0件） | `ls -la data/actions.db` |
| pytest | **688 passed / 5 skipped / 0 failed**（3:59） | `python3 -m pytest -q` |
| ボード | ready 0 / blocked 3 / running 0 / done 486 | sqlite 直叩き |
| 作業ツリー | コード未コミット: `mcp_hazard/server.py`(M) + `apify_shim.py`/`Dockerfile`/`requirements.txt`(??) = t_06fdd792（blocked）の作業中差分 | `git status --porcelain` |

## 2. 【要ユーザー対応・最重要】応募パイプラインが9/16 06:00以降停止（36時間）

**真因（再現済み）**: `~/.hermes/profiles/kensho-sweeps/scripts/kensho-auto-apply.sh:108` の「覚醒後ガード」
```bash
if pgrep -f 'kensho/orchestrator.py --account $acct' >/dev/null 2>&1; then exit 0; fi
```
は `flock -n … -c "… kensho/orchestrator.py --account atushi16 …"` の**内側**で走るため、`pgrep -f` が
自分自身のコマンドラインにマッチ → 常に exit 0 → 4垢すべて sleep 後に無言終了。

再現ログ（/tmp/qa_worker_test.log）:
```
[QA-TEST] guard1 skip
[QA-TEST] flock rc=0
```
（orchestrator本体は1行も実行されない。手動で `PYTHONPATH=/mnt/d/Project2/kensho … orchestrator.py --account atushi16` を実行すると正常に `処理待ちのバッチなし` を出し exit 0 ＝ コード側の異常ではない）

発生源: 案Bスタガー（t_ed8baffa）が 9/16 05:34 にガードを追加 →06:00から無音、16:03の現行版（7557B）に引き継がれ現在も停止。稼働版バックアップ `kensho-backups/kensho-auto-apply.sh.bak.t_ed8baffa.20260916053441`（5769B）には該当行が無い。

**推奨アクション（要GO・応募パイプライン改修のため自動実行せず）**
1. ガード行を削除、または実行行限定パターン（`pgrep -f "python .*kensho/orchestrator.py --account ${acct}$"`）へ変更。親ループ側の pgrep + `flock -n` が二重実行防止を担保済みなので削除で安全側。
2. 復旧確認: 子プロセスが `=== Kensho Orchestrator v4 ===` を出すこと＋翌日 `grep -c 完了 logs/auto_$(date +%Y%m%d).log` > 0。
3. ロールバック: バックアップから復元（`KENSO_STAGGER_MOD=0` では無効化できない＝ガードは別ブロック）。

## 3. 3軸評価
```json
{"evaluation":{
 "technical":{"score":6,"assessment":"workerの切り分け（応募停止が主因／計測欠落は副次）は実測で正しい。ただし真因は orchestrator_state ではなく spawnスクリプトのpgrep自己マッチで、報告の『get_pending_batches が空を返した真因』は誤誘導。run583-585が連続crashしcomplete/block未打刻（プロトコル違反2回）","evidence":"logs/auto_20260916.log 完了0行 / 9/17 worker行0 / 再現テスト guard1 skip"},
 "business_kpi":{"score":2,"assessment":"応募が36時間ゼロ。9/16の当選機会を丸ごと喪失（前日は完了653行）。数値上もaudit 196→3行","evidence":"audit.jsonl 196→3 / daily_counts 4件 / 完了行0"},
 "cost_efficiency":{"score":4,"assessment":"9/16以降、15分tick×4垢×約20時間=320回超のspawnが空回り（sleep後に無言exit）。計算資源とログのみ消費し成果ゼロ","evidence":"9/16 spawn行98回・catch上限到達25回、worker出力0"}},
 "loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},
 "self_review_quality":{"valid":false,"notes":"workerは自分が入れたガード起因の停止に気づけず、未検証のstate仮説を次アクションに据えた。さらにcrash×3で終端打刻なし"},
 "verdict":"fail",
 "next_steps":[
  "【要ユーザー対応】kensho-auto-apply.sh:108 の覚醒後ガード修正（削除or実行行限定パターン）で応募を即復旧",
  "loop_health.sh に business KPI ゲート（完了行0の日次検知）を追加し、パイプライン停止をscoreに反映",
  "actions.db 幽霊DBを廃し、集計源を gen_status_data.py（auto log 完了行）へ一本化"]}
```

## 4. その他の検出
- **幽霊カード t_a520bb76**（n8n workflow durability / assignee=None・作成者user）: assignee欠落でディスパッチャが永久スキップ（ready 4.3h放置）→ **kensho-worker に assign 済み**（復旧）。
- **t_55210446**（Gumroad商品ページ）: 真因は `GUMROAD_TOKEN` 不在（.env/環境変数どちらにも無し、実測）。ユーザー保有資格情報のため自動復旧不可 →【要ユーザー対応】維持。
- **t_06fdd792**（7th MCP hazard）: 90/90イテレーション枯渇×2でblocked。未コミットの `mcp_hazard/` 差分（BYOK apiKey + apify_shim）は同カードの作業中成果のため破棄せず温存。スコープ縮小 or 継続のユーザー判断待ち。
- 未追跡レポート4件（critic-observe-2026-09-17 / t_29167fa4×2 / t_9f37e5e3）: 追跡対象外だが証跡として残置。
- pytest恒久赤2件は **t_e94ea1ac で解消**（gate_skill_md_ratchet 59<=59、688 passed で全緑）。
