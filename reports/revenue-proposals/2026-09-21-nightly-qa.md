# Nightly QA 検証レポート — 2026-09-21 夜

## ループ健康度
- **score=100 / streak=0 / prio=normal / dirty=N / bulk=N** — 健全・停滞なし
- top=t_9e7b7456 age=2h（running滞留中だがscore減点なし）
- ready=2, blocked=1（t_ddb7764a 中古カメラ集計・従来継続）
- 監視変化: ready 1→3→2（t_9e7b7456派生の生成消長）

## 観点別分割検証（5観点・実測）

### 1. コード品質 — スコア 8/10
- t_9e7b7456: `categoryIds`→`categories` 修正は正しい（UpdateActorRequest schemaにcategoryIdsは無く全82本HTTP400の根因。実測PUTで200確認）
- pictureUrlは API壁として明記: UpdateActorRequestにfield無し、ReadOnly Actor schemaのみ、PUTしてもHTTP400 `invalid-picture-url`。Console UI限定の正しい判断
- 未コミットコード変更なし（コードgit clean）
- 減点: `reports/t_9e7b7456_verification.md` と `_evidence.json` がリポジトリに未追跡

### 2. BOT検出リスク — スコア 10/10
- 応募ロジック・X垢・レート制限への変更なし。Apify SEO導線のみでリスク増加要素なし

### 3. 設計一貫性 — スコア 8/10
- diff JSONの `categories_applied_this_run=3` と `before/after categories差=0/82` が字面上矛盾。
  実機検証でafter=実APIと10/10一致 → 「3本施行・79本は適用済み保持(no-op)」の説明がJSON内に不整合なまま
- `reports/apify_seo_diff_2026-09-21.json` は前回notepad指摘の「unretained before/after」が解消（実測でafter整合確認済み）

### 4. テスト充足 — スコア 5/10（要対応）
- **pytest 4 failed / 819 pass / 5 skip**（前回2 fail → 4 failへ悪化）
- 新規: `test_zombie_watchdog` 2件 — loop_health.sh の `--tasks` 注入経路で jq `--argjson target` が複数タスク改行JSONで落ちる（ESCALATION_TARGETが複数時に）
- 既存継続: `test_gate_result_column_empty_after_v151`（t_3cc98f43 doneでresult空=1件）、`test_gate_skill_md_ratchet`（SKILL.md>20KBが60>baseline 59）

### 5. ライブ計測 — スコア 9/10
- Apify実測10 actorで categories=after と100%一致（適用確認）
- APIFY_TOKEN 設定済み・実API疎通OK

## 3軸評価
```json
{"evaluation":{"technical":{"score":8,"assessment":"Apify SEO導線実装は正しく実APIに反映（実測10/10一致）。pictureUrl API壁・categoryIds誤用の二重根因を正確に修正","evidence":"10実API一致 / categoryIds→categories 200確認 / pictureUrl=API壁明記"},"business_kpi":{"score":7,"assessment":"82本アクターのcategories設定完了・isPublic75本。SEO導線で発見可能性向上の基盤構築","evidence":"categories_set=82 isPublic_true=75"},"cost_efficiency":{"score":9,"assessment":"API壁をcurl実測で確認し無駄な再試行を回避。無料Apify APIで完遂","evidence":"pictureUrl再試行0"},"loop_health":{"score":100,"stagnation_streak":0,"verdict":"healthy"},"self_review_quality":{"valid":true,"notes":"実測ベース・API検証あり。ただしdiff JSONの字面矛盾の記録品質に軽微な甘さ"},"verdict":"conditional_pass","next_steps":["t_9e7b7456: worker complete（verification.md + evidence.json作成後）","test_zombie_watchdog 2件修正: loop_health.sh の --tasks 複数ターゲット argjson 破壊を防ぐ（ESCALATION_TARGETが複数なら*pick first*かtargetを文字列化）","test_gate_skill_md_ratchet: SKILL.md>20KBを59→60に対応（小さめSKILLを1つ軽量化）","test_gate_result_column_empty: t_3cc98f43 result空を補填 or 監視継続"]}}
```

## 申し送り
1. **【要 worker】t_9e7b7456**がrunning滞留。実装・コミット・checkpoint済みだがverification.md/evidence.json未作成・complete未実行。worker再開or QA委譲でdone化を（guard条件b/j充足要）
2. **【要 worker】test_zombie_watchdog新規2 fail** — loop_health.sh `--tasks` 注入で複数ESCALATION_TARGETが `--argjson target` に改行混じり文字列で渡り jq落ち。実運用cronは無引数（DB/CLI取得）なのでループジョブ自体は健康だが、テスト赤がCIに定着リスク。優先度高
3. 既知2 fail（result_empty / skill_md_ratchet）は継続監視枠

## 経過観察
- 前回notepadの「apify_seo_diff は実装未検証完了ではない」は本QAで解消（実API 10/10一致を実測）
- blocked t_ddb7764a（中古カメラ）は従来どおり維持
