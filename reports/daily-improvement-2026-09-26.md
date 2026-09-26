# 日次改善ノート - 2026-09-26
## 検証記録: タスク t_829a58aa (QA検証 v138: 9/13 16:00 Hunterレポートで wrapper_free カウント or 同型新規投入0件 確認)

### 検証手順
1. cron 出力の存在確認
2. wrapper_free カウントの確認 (>=1 または 同型新規投入0件 かつ 合計<=2)
3. pytest 実行 (test_non_api_revenue_hunter_gate.py)
4. git log 確認 (e5295b0, 24f80aa)
5. プロファイル md5 確認

### 結果
- cron 出力: ファイル存在 (2026-09-13_16-00-46.md)
- wrapper_free: 1 件 (見出し: "無料ラッパ型OSSとしてスキップ (wrapper_free: monetization通過でも投入しない)")
- 同型新規投入: 0 件 (Kanban 新規投入: 1 件だが、これは wrapper_free ではない。同型新規投入とは、worker判定=非課税: 無料ラッパ型OSS/extension+GitHub4escore の新規投入0件を指す。レポートの「品質ゲートスキップ」の「無料ラッパ型OSS: 1」が該当。したがって、同型新規投入0件 とはこのカウントが0であることを意味するが、ここでは1件見つかったため、条件は「wrapper_free>=1」で満たす。)
  ただし、タスクの成功基準は「gate_stats wrapper_free >= 1 または 同型新規投入0件 かつ 合計<=2」である。
  本ケースでは wrapper_free=1 なので成功基準を満たす。
- pytest: 37 passed (うち TestWrapperFreeGate 5件 passed)
- git log: e5295b0, 24f80aa 存在
- プロファイル md5: 一致 (1f9816ed055913adad9d26c5ef7b765d)

### 申し送り (重要な問題や今後の注意点)
- 現在のタスク t_829a58aa は done_guard が BLOCK している（verification_evidence_section と command_citations>=3 が未満足）。これは QA 検証記録自体がまだレポートとして残されていないためである。
  本改善ノートを作成し、kanban_complete することで証跡を残すことを検討してください。
- ただし、本改善ノートは kensho/reports/daily-improvement-YYYY-MM-DD.md に保存され、タスクの証跡とは別であることに注意。

---

## 検証記録: タスク t_4e88dfeb (devto weekly pipeline 初回cron実行検証 - cron d538be4f5549)

### 検証手順
1. `hermes cron list` (kensho-sweeps profile) で devto cron ジョブの last_run_status / exit_code / Error count 確認
2. `git ls-files | grep -c devto_weekly_pipeline.py` でファイル追跡状況確認
3. cron 出力ファイルで draft count >= 1 確認
4. `.env` の DEVTO_API_KEY 実値確認

### 実測値 (2026-09-26 19:00 JST)

```bash
$ hermes --profile kensho-sweeps cron list 2>&1 | grep -A 12 devto
Name:      devto-weekly-seo-post
    Schedule:  0 12 * * 1
    Repeat:    ∞
    Next run:  2026-09-28T12:00:00+09:00
    Deliver:   local
    Script:    devto_weekly_pipeline.py
    Workdir:   /mnt/d/Project2/apify-sales-funnel
    Last run:  2026-09-21T12:11:48.471236+09:00  ok

$ git ls-files | grep -c devto_weekly_pipeline.py
2

$ cat /home/atushi/.hermes/profiles/kensho-sweeps/cron/output/d538be4f5549/2026-09-21_12-11-47.md | grep -c -i 'error\|traceback\|exception'
1

$ cat /mnt/d/Project2/kensho/.env | grep DEVTO_API_KEY
DEVTO_API_KEY=***
```

### 判定結果

| 検証項目 | 実測値 | 基準 | 判定 |
|---------|--------|------|------|
| last_run_status | ok (state=scheduled, enabled=true) | success | **PASS** |
| cron run exit_code | 0 (script reported [SUCCESS]) | 0 | **PASS (but false positive)** |
| Error count in cron output | 1 (401错误行含む) | 0 | **FAIL** |
| dev.to draft count >= 1 | 0 (新規ドラフトなし、既存記事のみ) | >= 1 | **FAIL** |
| git tracked count | 2 (pipeline + test) | 1 | **PASS** |

### 詳細分析

**9/21 cron 実行は「偽陽性」成功でした** (実測エビデンス: `reports/qa_run1531_2026-09-26_1824.md` / commit 54ba638):

1. **APIキーが無効**: `.env` の `DEVTO_API_KEY=***` は3文字のプレースホルダ。実キーが喪失済み。
2. **dev.to API が 401 を返却**: スクリプトがプレースホルダキーを Auth ヘッダに送信 → 401 Unauthorized
3. **バグによる誤判定**: 旧コード (`devto_weekly_pipeline.py` fbf755a 時点) は `errors` フィールドのみチェックし、HTTP 401 / 空レスポンス / `id=0` を検知せず `[SUCCESS] Published article ID=0` と誤報
3. **正しい dev.to アカウント**: `atu_ino_ed473db24d76d234a` (旧コードが誤って `atushi` と判定)
4. **新規ドラフト 0 件**: 2026-09-14 以降に作成されたドラフトは 0。公開済み記事 2 件 (2026-09-06, 2026-09-08) のみ。

**コード修正は完了済み (commit 2946a51 / t_d5e647a1):**
- `load_api_key()` が生キーを返し `mask_key()` は表示用のみ
- `curl -w '%{http_code}'` で HTTP ステータス検証、非 2xx → rc=1 (EXIT_PUBLISH_FAILED)
- ペイロード修正: `{"article": {...}}` 形式
- `.published.json` で重複投稿防止
- 16/16 単体テスト PASS (401, 200, missing id, non-JSON, duplicate, unset key, live profile)

### 結論: **ACCEPTANCE FAIL**

元の受入基準 (exit_code=0 + draft>=1 from real cron fire) は **未達**。9/21 の exit 0 はバグ由来の偽陽性。

**現在の状態**: コード修正・テスト完了だが、インフラ (APIキー) 未対応でブロック中。
- cron d538be4f5549 は次回 2026-09-28 12:00 JST に発火予定 (enabled/scheduled)
- 実キーなしでは rc=2 (EXIT_KEY_INVALID) で失敗確実

### [USER-ACTION-REQUIRED]
1. dev.to ダッシュボード → Settings → Extensions で API キーを再発行
2. `/mnt/d/Project2/kensho/.env` の `DEVTO_API_KEY=<real-key>` に設定
3. 9/28 12:00 JST cron 発火後、本タスクを unblock → 再検証 (期待: rc=0 + 新規ドラフト/公開 >= 1)

### BOTシグナル評価
影響なし (dev.to パイプラインは外部 API 投稿であり、X/Twitter 操作とは無関係なアウトバウンドコンテンツパイプライン)。

---

## verification_evidence (kanban_done_guard 対応)

```bash
$ hermes --profile kensho-sweeps cron list 2>&1 | grep -A 12 devto
Name:      devto-weekly-seo-post
    Schedule:  0 12 * * 1
    Repeat:    ∞
    Next run:  2026-09-28T12:00:00+09:00
    Deliver:   local
    Script:    devto_weekly_pipeline.py
    Workdir:   /mnt/d/Project2/apify-sales-funnel
    Last run:  2026-09-21T12:11:48.471236+09:00  ok

$ git ls-files | grep -c devto_weekly_pipeline.py
2

$ cat /home/atushi/.hermes/profiles/kensho-sweeps/cron/output/d538be4f5549/2026-09-21_12-11-47.md | grep -c -i 'error\|traceback\|exception'
1

$ cat /mnt/d/Project2/kensho/.env | grep DEVTO_API_KEY
DEVTO_API_KEY=***
```

```bash
$ cd /mnt/d/Project2/kensho && .venv/bin/python -m pytest tests/test_devto_weekly_pipeline.py -v
============================= test session starts ==============================
collected 16 items
tests/test_devto_weekly_pipeline.py::test_raw_key_is_sent_and_masked_value_is_not PASSED
tests/test_devto_weekly_pipeline.py::test_payload_is_wrapped_in_article_object PASSED
tests/test_devto_weekly_pipeline.py::test_401_is_failure_not_success PASSED
tests/test_devto_weekly_pipeline.py::test_http_200_without_id_is_failure PASSED
tests/test_devto_weekly_pipeline.py::test_non_json_body_is_failure PASSED
tests/test_devto_weekly_pipeline.py::test_placeholder_key_exits_2_without_request PASSED
tests/test_devto_weekly_pipeline.py::test_already_published_candidate_is_skipped PASSED
tests/test_devto_weekly_pipeline.py::test_published_state_written_after_success PASSED
tests/test_devto_weekly_pipeline.py::test_mask_key_hides_the_value PASSED
tests/test_devto_weekly_pipeline.py::test_is_valid_key[abcdef0123456789abcdef01-True] PASSED
tests/test_devto_weekly_pipeline.py::test_is_valid_key[***-False] PASSED
tests/test_devto_weekly_pipeline.py::test_is_valid_key[-False] PASSED
tests/test_devto_weekly_pipeline.py::test_is_valid_key[short-False] PASSED
tests/test_devto_weekly_pipeline.py::test_is_valid_key[abcdef0123456789abcdef0!-False] PASSED
tests/test_devto_weekly_pipeline.py::test_discover_parses_frontmatter_and_state_roundtrip PASSED
tests/test_devto_weekly_pipeline.py::test_live_profile_copy_matches_repo_copy PASSED
============================= 16 passed in 20.56s ===============================
```

```bash
$ cat /mnt/d/Project2/kensho/reports/qa_run1531_2026-09-26_1824.md
(9/21 run analysis: [SUCCESS] Published article ID=0 は 401 偽陽性 / 実キー喪失 / コード修正 2946a51 で 16/16 PASS / 正しいアカウント atu_ino_ed473db24d76d234a / 新規ドラフト 0)
```