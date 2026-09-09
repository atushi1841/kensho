# QA v79 検証レポート — 2026-09-09 23:59（kensho-revenue-qa / t_fef285a1）

対象: kanban_done_guard.py 条件(e)（v77実装 / sweeps@36521c0、parent t_c1ec5f8b）の独立QA。
プローブ類はワークスペース `~/.hermes/kanban/boards/kensho-ai-team/workspaces/t_fef285a1/` に実物残置（probe_regex.py / probe_e2e.py / probe_hard.py / audit_7d.py）。すべて読み取り専用＋一時DB/一時repoで実行、本番repo・本番DBは未変更。

## Scope 1 — CITED_HASH_RE フォーマット探測 ✅（24 probes、worker未カバー分を含む）

| 入力形式 | 結果 | 判定 |
|---|---|---|
| `commit:#HASH` / `commit=HASH` / `commit-hash` / `commit# HASH` / バッククォート | 捕獲 | OK（区切りクラス `[\s#:=\-]*`） |
| `commit@HASH` | 非捕獲 | 意図通り（@は区切りクラス外） |
| 全角コロン `commit：HASH`・全角イコール・カタカナ `コミット：HASH` | 非捕獲 | **潜在盲点**（下記申し送り1） |
| cron系ID（12hex 文脈なし / `commit a85cf2d361cf`） | 前者非捕獲・後者捕獲 | キーワード锚方式の想定挙動 |
| task ID（`t_fef285a1` 単独 / `commit t_88b6d325`） | 非捕獲 | OK（誤認なし） |
| 完全英字hex語 `defaced` | raw捕獲→digit規則で除外 | OK |
| 6hex（短すぎ）非捕獲 / 7hex・40hex・大文字 捕獲 | 境界正常 | OK |

E_HARD_AFTER=2026-09-13 / 現 `_e_is_hard()=False`（soft期間稼働中）を確認。

## Scope 2 — soft期間WARNING挙動 + hard化シミュレーション + 7日監査 ✅

合成repo（origin/main..HEAD=1 の未pushコードコミット3e2a7b7）＋合成タスクDBで**実guard CLI**を実行：
- `--json`: exit 0 / pass=true / `e_status:"fail"` / `e_soft:true` / `e_hard:false` ✅
- プレーン出力: `WARNING: 条件(e)未達だが移行soft期間のためpass扱い（hard化 2026-09-13 以降 exit 1 でブロック）` 表示・exit 0 ✅（ただしstdout出力。stderrではない→申し送り2）
- **hard化シミュレーション**（E_HARD_AFTERを過去にmonkeypatch）: 同一ケースで `e条件=False / pass=False` → 2026-09-13以降 exit 1 でブロックされることを実証 ✅
- 退路: `--allow-unpushed` 有効時はhardforcedでも pass=True ✅
- `--selftest`: SELFTEST OK（exit 1=検出動作のため正常） / `pytest tests/test_kanban_done_guard.py`: **10 passed** ✅

**done-vs-HEAD 7日監査**（v77成功指標、board DB read-only、348 done件/引用hash 8件検査）:
- インシデント6件（t_15af8300=09-04、t_8a9079c9/t_4bd48e99=09-05、t_1e5f1e47/t_4acf6dcc/t_226bb0d8=09-07）— **全件がguard導入（09-09 21:14）より前**
- **guard導入後（新規）インシデント = 0件 / 目標0件 達成** ✅
- 詳細: 引用された4hashは現在もorigin/main非祖先だが、同等コミットがrebase書き換え済みとして存在（83c6fa5→4a722bd / 932af8b→c38e58e / 35ee53a→c52961d / a4dbd7a→1c76b10）→ 実体は「done時未push」ではなく「rebaseによる引用hash失効」クラス。code喪失なし。

## Scope 3 — --allow-unpushed 退路 ✅（使用頻度記録つき）

- 前方一致救済: 7文字prefix `3e2a7b7` で救済されることをCLI実走で確認 ✅
- 完全hash指定も救済 ✅ / 誤hash（`deadbeef`）は救済なし（SOFT表示のまま）✅ — 無条件バイパス不可
- **使用頻度: 0回**（board logs / cron 出力をgrep、実運用での指定事例ゼロ。ヒットは全てguardソース・本次QAプローブ内）→ 次のcritic tickへ: 退路が不要なら削除候補、必要なら正当用途の明文化を。

## 3軸評価
```json
{"evaluation":{
 "technical":{"score":9,"assessment":"条件(e)の検出・soft/hard切替・退路・ハッシュancestryが設計通り。24フォーマット探測で誤認ゼロ・想定外誤認なし、hard化シミュで9-13以降のブロックを実証。","evidence":"probe_regex/probe_e2e/probe_hard 実走ログ、pytest 10 passed、selftest OK"},
 "business_kpi":{"score":8,"assessment":"done-while-unpushed新規0件（導入後）でv77成功指標を初回監査で達成。過去6件はrebase失効クラスでcode喪失なし。","evidence":"audit_7d.py: 348 done中 incidents=6 全件guard導入前"},
 "cost_efficiency":{"score":9,"assessment":"監査はread-only SQLite+git ancestryのみでLLM追加コストなし。guard自体はdone判定に既存git呼ぶだけ。","evidence":"audit_7d.py 実行 <1s、guard CLI評価 ~0.3s/case"}
},
"loop_health":{"score":95,"stagnation_streak":0,"verdict":"healthy"},
"self_review_quality":{"valid":true,"notes":"worker自己申告（10 passed・selftest exit 1・ghost fail/real pass）は全て独立再実走で裏取り済み。stdout/stderrの食い違いはカード文言と実装の差として正直に記録。"},
"verdict":"pass",
"next_steps":[
 "critic提案(優先度中): CITED_HASH_RE区切りクラスに全角コロン/全角イコール/\\uff1a\\uff1d@を追加（日本語作業者のIME起因サイレント非検出の防止）。テスト込みで。",
 "critic提案(低): soft期間WARNINGの出力先をstderr併記を検討（今のstdout-onlyは--no-agent配信には好都合なので仕様として明文化でも可）。",
 "board hygiene: kensho mainに他タスク由来のuntrackedコード（scripts/dm_probe.py, scripts/dm_scan.py）残置（check_dep_drift.pyはt_7b040302側で03f6daeとしてコミット済みに変更確認）。dm_probe/dm_scanのowner worker次回tickでcommit or移動のこと。",
 "2026-09-13 hard化当日: 既存workflowが(e)で mass-block されないか1回監査（soft WARNING件数の前日計測を推奨）。"
]}
```

## 申し送り
1. **全角区切り非対応**: `commit：HASH`（全角コロン）等がCITED_HASH_REに捕捉されない。workerが日本語IMEで引用するとハッシュ検査がサイレントに素通りする。critic修正提案は上記next_steps。
2. WARNINGはstdout（stderrではない）。非ブロッキング＋可視化の意図は達成済み。
3. --allow-unpushed 使用0回。hard化後も実需要がなければ削除候補。
4. コードは一切変更していない（QA役割遵守）。本番repo・本番DBはread-onlyアクセスのみ。
5. 本レポート自体のコミット: fc2d65d（初回5f3cb9f→Typo修正amend）。origin/main未push（本セッションにGitHub認証なし。pushは運用側にて）。
