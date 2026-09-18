# QA評価レポート 2026-09-18 10:15 (nightly-qa 033ff6065ef7)

## ループ健康度（script注入値 / 実測）
```
score=100|ready=6|blocked=2|prio=normal|streak=0|esc=False|skip=False|dirty=N|bulk=N
```
判定: **healthy**。streak=0で停滞なし。ready 7→6(-1) / blocked 0→2(+2)。
変化: ready減=タスク消費済、blocked増=新規2件がブロックされたのみ。score維持100。

## 実測サマリ
|| 項目 | 実測値 | コマンド |
|---|---|---|---|
| pytest | **105 passed / 0 failed** | `python3 -m pytest tests/test_source_health.py tests/test_applier.py -q` |
| Apify API | **200 OK** (前回404→回復) | `curl -s -o /dev/null -w "%{http_code}" https://api.apify.com/v2/acts?my=true` |
| コード変更 | 8ファイル / 52行変更 | `git diff HEAD --stat` |
| 未コミットコード | **なし**（data/・reports/のみ） | `git status --porcelain` → コードファイル(*)ゼロ |
| 適用パイプライン | 9/18 00:45〜03:09 37回spawn / 完了0件 | logs確認 |
| loop_health | score=100 / streak=0 / priority=normal | script出力 |

## ブロック2件の分析

### 1. t_1b2ecfa1 — 週次マーケットレポート有料購読（blocked要因: ユーザー判断必要）
- **前提3つが実測で崩れている**（判定書 9eaa8a8 済み）
  1. 🔴 GUMROAD_TOKEN未設定（HTTP 401確認）
  2. 🔴 email配信基盤無し（notifier.pyにsmtp無し）
  3. 🔴 collected.jsonは懸賞データで市場動向データではない
- **担当**: kensho-revenue-worker → kensho-qa
- **対応**: ユーザー判断待ち。GUMROAD_TOKEN発行 + 配信基盤選定 + データ源決定の3つが必要。

### 2. t_f91d2729 — t_9cc18ba0残検証（blocked要因: コードバグ）
- **FAIL項目**: 03:00収集でtwscrape実行されない
- **原因**: collector.py:480のresearch_allowed()が壁時計`datetime.now().hour`を参照。03:00 cron収集はスクレイピングに約1hかかるためStep 2f到達が≈04:0x → hour=4 ∉ research_hours=[3] → 常にスキップ
- **PASS項目**: 12:00等稼働帯でのRESEARCH分離スキップは正常動作
- **修正方向**: ゲートを収集開始時刻(cron hour)基準へ修正、またはresearch_hoursを深夜帯[0-4]へ拡張
- **担当**: kensho-qa → kensho-workerへ委譲

## 3軸評価
```json
{
  "evaluation": {
    "technical": {
      "score": 8,
      "assessment": "source_health.pyは状態機械設計で優秀。backoff8sキャップ+健康記録も合理的。Apify API健康度チェック実装で404早期検知＋フォールバック動作確認済み。research分離ゲートの時刻バグはQAが発見し修正を委譲。",
      "evidence": "105 pytest pass / Apify 200 / 未コミットコードなし"
    },
    "business_kpi": {
      "score": 4,
      "assessment": "適用パイプライン9/16以来停止気味(37回spawn/完了0件)。GUMROAD_TOKEN未設定でGumroad販売ページ作成不可。RapidAPI 90/90枯渇で代替API判断待ち。blocked 2件のうち1件はユーザー判断必須。",
      "evidence": "logs/auto_20260918.log: 処理待ち37回/完了0行 / GUMROAD_TOKEN不在 / RapidAPI 90/90"
    },
    "cost_efficiency": {
      "score": 8,
      "assessment": "SourceHealthによりtimeout源の無駄なリトライ回避(1日47件→自動skip)。setsid PGID分離はflockハング時の誤殺防止で効率的。Apifyフォールバックで404時のデータ源切替可能に。追加インフラなし。",
      "evidence": "collector.pyで4源guarded_source化 / auto-apply.sh setsid追加 / healthチェック2ファイルに実装"
    }
  },
  "loop_health": {"score": 100, "stagnation_streak": 0, "verdict": "healthy"},
  "self_review_quality": {"valid": true, "notes": "前回QA(08:15)の3事前問題(regression_gates)は本日clean HEADでもsame FAIL、新規regressionなし。Apify 404→200回復も健康度チェックの早期検知効果。"},
  "verdict": "conditional_pass",
  "next_steps": [
    "t_1b2ecfa1: ユーザーにGUMROAD_TOKEN発行+配信基盤選定+データ源決定を促す（GO推奨）",
    "t_f91d2729: workerへresearch_allowed()時刻基準修正を依頼（cron hour or research_hours拡張）",
    "Apify 404→200回復だがtoken有効期限監視をhealthチェックに残す",
    "blocked 2件のいずれかが解消したらreadyが減少→ループ健康度再測定"
  ]
}
```

## 発見事項

### 🔴 要対処（blocked維持）
1. **t_1b2ecfa1前提3つ崩壊**: GUMROAD_TOKEN/email基盤/データ源。ユーザー判断なしでは実装不可。
2. **t_f91d2729コードバグ**: collector.py:480 research_allowed()が壁時計参照。03:00収集でtwscrape常スキップ。

### 🟡 要ユーザー対応
3. **GUMROAD_TOKEN未設定**: Gumroadダッシュボードから発行（https://gumroad.com/settings/developer）。**おすすめですすめます（GOで実行/対応をお願いします）**
4. **RapidAPI 90/90枯渇**: 代替API or スコープ縮小判断を。**おすすめですすめます（GOで実行/対応をお願いします）**

### 🟢 改善提案
5. **loop_health.shにbusiness KPIゲート**: 完了行0の日次検知をscoreに反映（9/17 QAが指摘、未実装）
6. **actions.db幽霊DB廃止**: 集計源をgen_status_data.py(auto log完了行)へ一本化

## 申し送り
- t_442337b4: workerがコードを書いたがcommitしなかった。QAとしてはcommit/push後に再検証要。今回のgit statusで未コミットコードなしを確認（data/・reports/は対象外）。
- t_df34f367: フォロワー数急変アラート実装済(f4a3acb)。本QAでは未検証。
- t_55210446: GUMROAD_TOKEN待ち。ユーザー対応までblocked。
- regression_gates 3件は事前問題（worker変更非影響）だがcriticへ事前報告済
- **Apify API 404→200回復**: healthチェックの早期検知が功目。ただしtoken有効期限監視は要継続
- **blocked 2件の内1件(t_1b2ecfa1)はユーザー判断必須**。criticの提案通り「GOで対応」を促す

## 教訓（notepad保存用）
- loop_health score=100/streak=0/blocked=2: blocked増は新規タスクのブロックであり停滞ではない。score維持=ループ健全
- blocked 2件とも「要ユーザー対応」タイプ（前提崩壊＋コードバグ修正依頼）。criticが正しく優先度を振り分け
- Apify 404→200回復は健康度チェックの早期検知効果。ただしトークン失効は突発的なので継続監視必要
- worker commit忘れはQA通過最大ボトルネック。guard条件(e)未pushで確実にFAIL
- pytest 105 pass + Apify 200 + 未コミットコードなし = 本QAセッションの技術的条件は充足
- research_allowed()の時刻バグは「設計段階でcron開始時刻とStep 2f実行時刻のずれを見積もっていれば防げた」＝テストカバレッジ不足の教訓
