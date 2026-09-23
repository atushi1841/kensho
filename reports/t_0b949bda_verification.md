# t_0b949bda 検証証跡: AIデータジャーナリズム基盤（傾向自動抽出・レポート/下書き生成）

- タスク: t_0b949bda（assignee: kensho-revenue-worker）
- 目的: 収集済み懸賞データから傾向を自動抽出し、決定的な週次レポート＋dev.to/Qiita 下書きを生成する基盤を t_0b949bda として構築する
- 検証方法: worker 自身が t_0b949bda の受け入れ条件に対して実コマンドを実行し、出力をそのまま貼付（以下の `$` 行はすべて実実行）

## 成果物（t_0b949bda）

| 種別 | パス |
|---|---|
| 分析エンジン | `scripts/kensho_data_journalism.py`（1084行・標準ライブラリのみ・読み取り専用） |
| 週次ランナー | `scripts/data_journalism_week.sh`（引数なし=本番、`--snapshot` 付き） |
| レポート雛形 | `reports/templates/data-journalism-report.md` |
| ブログ雛形 | `reports/templates/data-journalism-blog.md` |
| 第1弾レポート | `reports/journalism/2026W39.md` / `2026W39.json` |
| 投稿下書き | `reports/journalism/drafts/devto-2026W39.md` / `qiita-2026W39.md` |
| 運用フロー | `docs/data_journalism_flow.md`（AIチーム連携・cron・投稿手順） |
| 回帰テスト | `tests/test_data_journalism.py`（28件） |

## verification_evidence

### 1. t_0b949bda: 生成物の再現性（2回生成 → 統計ダイジェスト一致）

$ python3 diff_runs.py
run1: fingerprint=de967a99 bytes=10121
run2: fingerprint=de967a99 bytes=10121

diff paths: 0

same as canonical(set-normalized) after removing list order? True

（修正前は同一入力でも `80b1e241` と `bba53561` に割れていた。真因は set 反復順に依存した
「前週比の新規案件サンプル」で、キー降順固定に修正 → 上記の通り一致。詳細は本証跡末尾の回帰テスト。）

### 2. t_0b949bda: 主要数値の独立再計算（別実装でのクロスチェック）

$ python3 verify_t0b.py
(A) fingerprint run1=de967a99 run2=de967a99 match=True
(B) report body identical (mod generated_at)=True md_sha=5c78e937
    collected_today.json: rows=1178
    collected.json: rows=1190
    collected_20260923.json: rows=1178
(C) merged unique campaigns = 1202

$ python3 verify_t0b.py
    total_campaigns: report=112 independent=112 PASS
    total_entries: report=120 independent=120 PASS
    total_seats: report=2286 independent=2286 PASS
    route_X: report=110 independent=110 PASS
    dm_wins total=16 report_wins_total=16
RESULT: PASS

（独立再計算は snowflake ID から投稿時刻を復元し、3つの収集JSONを tweet_id キーで統合して
 週窓で絞る別実装。t_0b949bda のエンジン側集計値と案件数・応募数・当選枠・導線内訳がすべて一致。）

### 3. t_0b949bda: テスト

$ python3 -m pytest tests/test_data_journalism.py -q
collected 28 items
tests/test_data_journalism.py ............................               [100%]
============================== 28 passed in 7.32s ==============================

（新規追加: `test_wow_new_sample_is_deterministically_sorted` = 再現性の回帰テスト。
 既存の `test_build_sections_uses_real_numbers` は `min_df` 既定値の変更で空表を見ていたため
 `min_df=2` を明示する形に修正した。）

### 4. t_0b949bda: テンプレート整合性ゲート

$ bash scripts/data_journalism_week.sh --dry-run
[2026-09-23 23:52:23] data_journalism start (dry_run=1)
[2026-09-23 23:52:27] dry-run: template ok / generation skipped

### 5. t_0b949bda: 週次ランナー end-to-end（実データで第1弾を生成）

$ bash scripts/data_journalism_week.sh
[2026-09-23 23:45:04] data_journalism start (dry_run=0)
week       : 2026W39
campaigns  : 112
entries    : 120
seats      : 2,286
wins       : 4/16 突合
fingerprint: de967a99
[2026-09-23 23:45:08] data_journalism done (week=2026W39)

### 6. t_0b949bda: 定期実行の登録と gateway 前提の実測

$ hermes cron status
✗ Gateway is not running — cron jobs will NOT fire
  2 active job(s)
   Next run: 2026-09-17T09:00:00+09:00

（`kensho-data-journalism-weekly`（毎週月曜07:00・no_agent・deliver=local）を t_0b949bda で登録済み。
 ただし当プロファイルの gateway が停止しているため発火しない点を `docs/data_journalism_flow.md` に
 明示し、gateway 起動または gateway 稼働プロファイルへの登録という運用判断として残した。
 同 store の既存 `kensho-weekly-market-report` も Next run が過去日付のまま未発火であることを実測確認。）

## t_0b949bda 再現性の真因と修正

- 症状: t_0b949bda の生成器で、同一入力の2回生成でも統計ダイジェストが変化（`80b1e241` → `bba53561`）。
  レポート本文の「新規案件の例」の並びだけが入れ替わり、数値は同一だった。読者に「再現可能」と
  提示している以上これは破綻。
- 真因: `_wow_delta()` の `new_sample` が `list(new)[:5]`（set 反復順）で、順序がプロセスごとの
  ハッシュ乱数（PYTHONHASHSEED）に依存していた。
- 修正: `sorted(new, reverse=True)[:5]` に変更（キー降順＝決定的）。他の set 由来順序が無いことを確認
  （`accounts` は既に `sorted()`、集計は `Counter`/`sorted` のみ）。
- 回帰防止: `tests/test_data_journalism.py::test_wow_new_sample_is_deterministically_sorted` を追加。
- t_0b949bda の成果物はコミット 5c2f40b で push 済み。
