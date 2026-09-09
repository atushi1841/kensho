# QA v77 検証レポート — 2026-09-09 21:45（kensho-revenue-qa / job 033ff6065ef7）

## 0. ループ健康度
- score=95 / streak=0 / blocked=0 / ready=0 / in_progress=1→0 / priority=new_proposals
- monitor差分: wip 2→1→0、done 363→365、dirty=Y→N。正常状態。skip_fast=false。

## 1. 前回からのdelta検証（v76→v77）

### ① twscrape復活のライブ最終確認 ✅（最重要）
- v76でQAコミットした a35c7df（cookies注入）に対し、**20:00/21:00の収集は依然 twscrape=0件**だった
- 真因: **kensho-venv の twscrape が 0.19.1 のまま**（`XClIdGenStore.get()` が `cookies` kwarg非対応 → TypeError → except節で「XClientTxId生成不能」と誤出力）。cron実行pythonは `/home/atushi/kensho-venv/bin/python`（kensho-collect-only.sh）
- QA直接対応: venvへ `pip install -U 'twscrape>=0.20.1'` → 0.20.1 導入
- 検証1（venv直接スモーク）: GEN OK → SEARCH OK count: 21（実懸賞ツイート取得）
- 検証2（本番パイプライン）: `kensho-collect-only.sh` 手動実行 → **twscrape 104件**、collected.json保存（計213件）
- → dead_source_sentinel の「248収集連続0件」カウントはこれで停止・復活確定

### ② パターン教訓: 「依存宣言≠venv実適用」
a35c7df は pyproject.toml に `twscrape>=0.20.1` を宣言したが、**実行venvへのインストールは別途必要**。pyproject宣言だけだとコミット=完了と誤認しやすい。
再発パターン: df1f851でもpatchright宣言済みだが venv実態は 1.61.1（pin=1.62.3）で同じギャップが既に出ていた。

### ③ patchright venv drift検出・修正 ✅
- `pytest`（venv実行）で `test_patchright_installed_and_pinned` FAIL: venv=1.61.1 ≠ pin=1.62.3
- 修正: venvへ `patchright==1.62.3` 導入 → **pytest 533 passed / 4 skipped 全通過**
- browser.pyのデフォルトは標準playwright Firefox（chromium-stealthはopt-in）なので応募稼働には無影響だったが、pin検証テストが常時FAIL状態だった

### ④ dead-source 3/3 収束確認（v76の続き）
- knshow: 21:28実行も0件（上流CF 502継続。keep判定はv76通り妥当）
- chance.com: 1f0485e適用済み。21:28=0件だが新規なしの正常挙動（20:00=30件で動作実証済）
- twscrape: 上記①で復活

## 2. 3軸評価
```json
{"evaluation":{
 "technical":{"score":9,"assessment":"twscrape復活が本番収集で104件として実証。venv drift 2件（twscrape/patchright）を検出・修正。pytest 533全通過。","evidence":"collect_20260909_212840.log: twscrape 104件 / pytest 533 passed, 4 skipped"},
 "business_kpi":{"score":7,"assessment":"収集源が8系統→実効9系統に回復し1回あたり+100件規模の供給増。knshow上流障害は依然残但し代替源で吸収（計213件/tick）。","evidence":"21:28 tick 計213件（twscrape 104を含む）vs 21:00 tick 計128件"},
 "cost_efficiency":{"score":8,"assessment":"monitor gateにより無変化tickのLLM起動ゼロを維持。venv修正はpip 1コマンドで追加コスト無。","evidence":"monitor diff: score85→95変化時のみ起動、skip=False"}
},
"loop_health":{"score":95,"stagnation_streak":0,"verdict":"healthy"},
"self_review_quality":{"valid":true,"notes":"v76QAのdone_guard教訓（コミット検証）は機能したが、依存の『実適用』検証（venv pip check）まで到達していなかった。done検証に実行環境同期チェックを追加すべき"},
"verdict":"pass",
"next_steps":[
 "critic提案: done_guardに『pyproject宣言依存のvenv実バージョン一致チェック』を追加（uv pip check相当をQAゲート化）",
 "watch: 22:00/翌9:00の定期収集でtwscrape>0が自動継続することを確認（次回QA tick）",
 "TankanNotes 1085【要ユーザー対応】は継続（USB物理確認のみユーザー側）"
]}
```

## 3. 申し送り
- 【要ユーザー対応】TankanNotes プロキシ :1085 3日目不動（rc=7）。USB物理確認のみ可能。
- criticへ: venv/宣言の漂移が2件連続発生（twscrape→patchright）。CIゲート化の提案価値「高」（自動復旧阻害タイプ: テストが正しく実環境を反映しない）
