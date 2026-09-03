# 収益化Worker実行記録 — Apify SEO監査スクリプト実装（t_ce1f9b36 / v13-A）

- 実行日時: 2026-09-04 06:46〜07:20 JST
- タスク: t_ce1f9b36「revenue-critic v13-A: Apify 1162 runs 3-day stagnation root cause analysis」
- 選択根拠: critic v13-C の優先順位付けで第1位。他候補は t_05d5f3da が12:00 JST以降必須（時間ブロック）、t_1d4c31a9 は RapidAPI provider billing が API 経由不可をQA実測済み（t_868caac2）→ 実装不能

## 1. 背景（エビデンス）

`data/revenue-daily.json` の実測:

| 日付 | total_runs | users30d | actors_ppe |
|------|-----------|----------|------------|
| 9/2 | 1125 | 21 | 25 |
| 9/3 | 1162 | 21 | 25 |
| 9/4 | **1162（増加ゼロ）** | 21 | 25 |

PPE課金は全25アクター適用済み（t_19bca94c でライブ検証PASS）だが流入が伸びていない。
→ ボトルネックは単価でなく**発見性（Store検索での露出）**と仮定し、監査ツールを実装。

## 2. 実装内容（Act）

| ファイル | 内容 |
|----------|------|
| `scripts/apify_seo_audit.py`（新規・806行） | Store SEO監査ツール（読み取り専用） |
| `tests/test_apify_seo_audit.py`（新規） | 20テスト（ネットワーク不使用・fixture/mock） |

監査ロジック（競合は `/v2/store?search=...&sortBy=popularity` の上位、自社除外）:
1. `short_description` — 説明文が競合中央値より短い
2. `missing_keywords` — 競合過半数に出現し自社全文（title/desc/readme/seo）に不在の語
3. `missing_categories` — 競合過半数が設定するカテゴリが自社に無い
4. `title_too_long` / `title_too_short` — 70字超 / 20字未満
5. `seo_title_missing` / `seo_description_missing` — detail APIで空判定
6. `thin_readme` — readmeSummary 200字未満
7. `discovery_gap` — 自社u30d=0 かつ競合中央値u30d≥1
8. `title_keyword_gap` — 競合タイトルに多く自社タイトルに無い語（サイト名等）

設計上の工夫（実測で2回やり直しして到達）:
- **マルチクエリ検索**: title語2→3、nameトークン、単語と「狭い→広い」順に最大4クエリ試行（1クエリだと `cross-shop` 等の連結語や狭い語で競合0件になった）
- **関連度フィルタ**: 自社title/nameと競合title/descの共有キーワード数で絞り、無関係な人気アクター（例: "watch"検索でYouTube系が上位）を除外。これでノイズ提案が180→110件に減少
- **stopword拡張**: 競合文の接続・修飾語（more/other/via/comprehensive等）を除外し「真似しても発見性が上がらない語」を提案しない
- **profile stale copyガード**: 実行パスが `/.hermes/profiles/` 配下なら exit 2（9/4教訓の再発防止）

## 3. 検証エビデンス（Verify）

### 3-1. テスト

```
python3 -m pytest tests/test_apify_seo_audit.py -q --no-cov
→ 20 passed in 2.12s
```

### 3-2. ライブ実行（Apify API実呼び出し、HTTP 200確認済み）

```
python3 scripts/apify_seo_audit.py --top 5
→ actors=58 findings=110
json: reports/apify-seo/apify-seo-audit-2026-09-04.json
csv:  reports/apify-seo/apify-seo-audit-2026-09-04.csv
```

内訳: `no_competitor_data 25 / missing_categories 23 / short_description 22 / missing_keywords 21 / title_keyword_gap 12 / discovery_gap 5 / seo_title_missing 1 / seo_description_missing 1`

### 3-3. 上位PPEアクターの監査結果（実測）

| アクター | 結果 |
|----------|------|
| japan-used-instrument-market-scraper | categories追加: AUTOMATION, DEVELOPER_TOOLS / title追加: digimart |
| japan-luxury-brand-market-scraper | description 286字以上へ拡張 |
| japan-used-camera-market-scraper | **指摘なし（競合5件と同等以上）** |
| japan-watch-market-scraper | **指摘なし** |
| japan-offmall-market-scraper | no_competitor_data（offmall検索に競合が存在しない） |

→ **停滞の直接原因は「上位アクターのSEO欠陥」ではない**と実測で分かった。camera/watch は説明文・カテゴリ・SEO項目が競合水準に達しており、Store内の需要自体が小さい（u30d=1が5件だけ）ことが runs 停滞の主因と判断。次の打ち手は「既存アクターの微修正」より「検索ボリュームのある新規キーワード（surugaya/mercari/yahoo-auctions系）での公開本数増」側にある。

### 3-4. 回帰テスト

```
python3 -m pytest -q --no-cov（playwright/scrapling依存の5ファイルを除外）
→ 195 passed / 1 failed
```
失敗は `test_applier.py::test_dedupe_batch_items` の `ModuleNotFoundError: No module named 'scrapling'`（WSL環境に未導入の既存依存、私の変更とは無関係の既存事象）。新規2ファイル以外の変更ゼロ。

## 4. 自己レビュー（Reflexion）

```json
{
  "self_review": {
    "what_was_done": "scripts/apify_seo_audit.py を新規実装（自社公開58アクター×Apify Store人気順競合を比較し、short_description/missing_keywords/missing_categories/seo欠落/discovery_gap等8種の改善案をJSON+CSV diffで出力）。tests/test_apify_seo_audit.py 20件追加、ライブ実行で110件の改善案を実測取得",
    "what_went_well": [
      "マルチクエリ（狭い→広い4試行）+関連度フィルタで、初版の『上位5アクター全員 no_competitor_data』『無関係なYouTube系が競合化』という2つの実バグを実測で発見・修正できた",
      "ネットワーク不要のfixture/mockテストだけで20件カバーし、CI再現性を確保",
      "profile stale copyガードを組み込み、9/4の教訓をコードで恒久化"
    ],
    "what_could_improve": [
      "no_competitor_data が25件残っている — 非英語サイト名（suumo/goo-net系）はStore検索語が一致しないため、日本語サイト名のローマ字別名辞書を用意する",
      "競合のreadme本文は未取得（readmeSummaryのみ）。競合readme長まで比較すれば thin_readme 判定が正確になる",
      "実行に約5分（58アクター×最大4クエリ）。cron組み込み時は --limit で対象を絞る運用が必要"
    ],
    "mistakes_or_risks": [
      "初版の検索クエリ生成にハイフン連結語（cross-shop）がそのまま通り、実データで全滅した（テストで1件検出し修正）",
      "関連度フィルタ導入時に fixture の競合が自社と重複ゼロになり既存テストが1件落ちた — フィクスチャが『自社と無関係』だったことが原因で、テストデータの現実味不足が改善点",
      "リスク: このツールは提案を自動適用しない（読み取り専用）。適用は次バッチの別タスクで行うため、効果測定は9/5以降の実測待ち"
    ],
    "learned": "Apify Store検索は sortBy=popularity でもクエリ語が狭すぎると0件・広すぎると無関係な人気アクターが返る。因此『複数クエリ試行×自社とのキーワード重複度で絞る』の2段構えが必須。監査結果として『上位アクターは既に競合水準、停滞は需要側の問題』という否定命題を実測で示せたのが最大の収穫",
    "confidence": 8,
    "verification_evidence": "pytest tests/test_apify_seo_audit.py → 20 passed in 2.12s。ライブ実行 python3 scripts/apify_seo_audit.py --top 5 → 'actors=58 findings=110'（Store API HTTP 200、/tmp/store_test.json で total:95 応答確認済み）。出力JSON/CSV実在: reports/apify-seo/apify-seo-audit-2026-09-04.{json,csv}。回帰: 195 passed / 1 failed（scrapling未導入の既存環境依存、変更ファイルは新規2つのみ）"
  }
}
```

## 5. 次のアクション（申し送り）

- critic: 「camera/watch は競合水準に到達済み」→ 既存アクターのSEO微修正提案より、**検索ボリュームのある新規キーワード（surugaya/mercari/yahoo-auctions系）での公開本数増**へ振り向ける判断を推奨
- worker次バッチ: `missing_categories`（AUTOMATION/DEVELOPER_TOOLS/LEAD_GENERATION 追加）はApify設定APIで一括適用可能。ただし公開設定変更なのでユーザー承認推奨
- 監視: 9/5 00:20 の revenue-daily.json で total_runs が 1162 から動くか確認（動かなければ需要側対策へ完全転換）
