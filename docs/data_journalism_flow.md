# AIデータジャーナリズム運用フロー (t_0b949bda)

収集済みデータだけを入力にした「決定的な分析レポート」を週次で生成し、
dev.to / Qiita へ投稿できる下書きまでを機械的に用意するための運用手順。

## 1. パイプライン

```
[毎時 cron / kensho-sweeps]
  kensho_collect.py  →  data/collected_today.json, data/collected.json
                                  │
                                  ▼
[週次 / data_journalism_week.sh]
  scripts/kensho_data_journalism.py  ──┬─→ reports/journalism/<WEEK>.md      レポート本体
                                        ├─→ reports/journalism/<WEEK>.json    統計JSON（下流の唯一の入力）
                                        └─→ reports/journalism/drafts/*.md    dev.to / Qiita 下書き
                                  │
                                  ▼
[独立検証 / kensho-qa]
  決定性・数値の独立再計算・テンプレ整合・pytest
                                  │
                                  ▼
[公開判断 / 人間]
  下書きレビュー → published:false / private:true を公開へ
```

入力は **収集JSONと当選DMのみ**（`data/collected_today.json` / `data/collected.json` /
`data/collected_history/*.json` / `data/dm_wins.json`）。応募・収集ロジックには一切触れない（読み取り専用）。

## 2. 役割分担

| 担当 | プロファイル | 責務 |
|---|---|---|
| 生成・保守 | `kensho-revenue-worker` | 生成器・テンプレート・下書きの実装、週次の生成実行 |
| 独立検証 | `kensho-qa`（収益系は `kensho-revenue-qa`） | 決定性・数値の再現・証跡の done_guard 準拠を検証 |
| 監視・改善提案 | `kensho-critic` | 分類規則（キーワード/カテゴリ）の妥当性、指標の穴を指摘 |
| 公開判断 | 人間 | 下書きの中身の最終判断（機械は公開しない） |

AIチームは「レポートを書く」のではなく「同じ入力から同じ数値が出る生成器を保守する」。
記事本文の数値はすべて統計JSON由来で、手作業の加筆は行わない（数値訂正は分類ロジックを直して再生成する）。

## 3. 実行手順

```bash
# 1) 生成（引数なし=本番。--snapshot 付きで履歴を1件増やし次回の前週比の母集団を作る）
bash scripts/data_journalism_week.sh                 # 今週分
bash scripts/data_journalism_week.sh --week 2026W39  # 週を指定して再生成
bash scripts/data_journalism_week.sh --dry-run       # テンプレ整合性チェックのみ

# 2) 生成器の直接実行（cron からは上記wrapper経由）
python3 scripts/kensho_data_journalism.py --week 2026W39
python3 scripts/kensho_data_journalism.py --check-template

# 3) テスト
python3 -m pytest tests/test_data_journalism.py -q
```

## 4. 週次の生成体制（cron）

| 項目 | 値 |
|---|---|
| wrapper（実体） | `/mnt/d/Project2/kensho/scripts/data_journalism_week.sh` |
| wrapper（プロファイル側） | `~/.hermes/profiles/kensho-revenue-worker/scripts/data_journalism_week.sh` |
| ジョブID | `4e566e2d069e`（`kensho-data-journalism-weekly`） |
| 実行モード | `no_agent`（スクリプトの stdout をそのまま保存。引数なし=`--snapshot` 付き本番実行） |
| スケジュール | 毎週月曜 07:00（`0 7 * * 1` / next run 2026-09-28 07:00 JST） |
| 配信先 | `local`（保存のみ。レポートは `reports/journalism/` を見る運用） |
| 実行ログ | `logs/data_journalism_<YYYYMMDD>.log` |

**gateway 前提（重要）**: Hermes の cron は「そのプロファイルで gateway が動いている」場合のみ発火する。
`kensho-revenue-worker` の gateway は stopped のため、この store のジョブは現状発火しない
（実測で `hermes cron status` が `Gateway is not running — cron jobs will NOT fire` を返し、
同じ store の既存 `kensho-weekly-market-report` も Next run が過去日付のまま停止している）。
発火させる運用にする場合の選択肢:

1. `hermes gateway run`（または `hermes gateway install`）で当該プロファイルの gateway を起動する
2. gateway が稼働している別プロファイル（例: `kensho-sweeps`）側に同一 wrapper を登録する

いずれも運用判断（プロファイル横断の変更）なので、本タスクでは wrapper と登録手順までを用意し、
実際の scheduler 登録先は未確定のまま明示している。

## 5. QA が再現すべき検証ゲート

1. **決定性**: 2回生成して統計 JSON の `fingerprint` が一致し、レポート本文が `generated_at` 行以外ビット同一であること
2. **数値の独立再計算**: 収集 JSON から週内案件数 / 応募数 / 当選枠合計 / 導線内訳を別実装で再計算し一致すること
3. **テスト**: `python3 -m pytest tests/test_data_journalism.py -q` が全件パス
4. **テンプレ整合**: `--check-template` が OK（プレースホルダ欠落なし）
5. **証跡**: `reports/t_0b949bda_verification.md` が `## verification_evidence` 見出しと実コマンド出力引用を持ち、git 追跡されている

## 6. ブログ投稿フロー（dev.to / Qiita）

1. `reports/journalism/drafts/devto-<WEEK>.md` / `qiita-<WEEK>.md` を開く（front matter は `published: false` / `private: true` 固定で出力される）
2. 記事中の数値を `reports/journalism/<WEEK>.json` と突合する（記事の数値はすべて JSON から描画されている）
3. 人手で読み物としての品質を確認 → 公開フラグを立てて投稿
4. 記事末尾の統計ハッシュ（`fingerprint` 先頭16桁）を残す＝読者が同じコマンドで再現できる

再現コマンドは記事内に自動埋め込みされる:

```bash
python3 scripts/kensho_data_journalism.py --week 2026W39
```

## 7. 再現性の落とし穴（実測で踏んだ）

Python の `set` 反復順はプロセスごとのハッシュ乱数（PYTHONHASHSEED）に依存する。
前週比の「新規案件の例」を `list(new)[:5]` で作っていたため、**同一入力でも fingerprint が実行ごとに変わっていた**
（実測: 同条件2回で `80b1e241` / `bba53561`、レポート本文の数値は同一なのに統計ダイジェストだけが揺れる）。
キー降順の固定サンプルに修正し、回帰テスト
`tests/test_data_journalism.py::test_wow_new_sample_is_deterministically_sorted` で再発を止めている。

同種の事故を避けるため、出力（Markdown・JSON）に set 出来の順序を持ち込まないこと。
`Counter`/`sorted()` 由来の順序のみを使う。

## 8. 出力の読み方（セクション対応）

| セクション | 元データ | 意味 |
|---|---|---|
| 1. サマリ | 集計ヘッダ | 案件数・応募数・枠合計・欠損率 |
| 2. キーワード | `tweet_text` の語 | 出現案件数(DF) × 応募率リフト。負のリフト=自動化の穴 |
| 3. カテゴリ | `prize_score.items` + 本文 | 賞品カテゴリ別の供給と応募の偏り |
| 4. 当選枠 | `winner_count` | 枠レンジ別の構造（1名帯=回数勝負、大量枠=期待値） |
| 5. 締切 | `deadline` | 逼迫度。未記載率は収集品質の指標 |
| 6. 導線 | `導線` | X完結=自動化可、LINE/外部フォーム=実質的な参入障壁 |
| 7. 収集源 | `source` | 供給量の偏り（1源依存のリスク） |
| 8. 当選 | `dm_wins.json` × 収集案件 | 突合できた当選のみ。未突合は収集前案件/X外経路 |
| 9. 前週比 | `data/collected_history/` | 供給量の変化（集合差分） |
| 10. アカウント | `applied` | アカウント別カバレッジ＝機会損失の所在 |
| 11. 機会損失 | 未応募 × 推定価値 | 応募が刺さっていない高価値案件トップ10 |
