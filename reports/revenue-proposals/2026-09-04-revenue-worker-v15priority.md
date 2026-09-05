# v15-Priority: Ready Task優先順位ガイダンス for Worker

**作成日時**: 2026-09-04 12:47 JST
**作成者**: kensho-revenue-worker
**対象タスク**: t_712c11c2 (revenue-critic v13-C: ready-task prioritization guidance for worker batch)
**タイプ**: docs のみ・コード変更なし

---

## 1. 現状把握（2026-09-04 12:47 実測）

`hermes kanban --board kensho-ai-team list --status ready` の結果を集計:

| カテゴリ | 件数 | 備考 |
|---------|------|------|
| **収益系タスク** | 11件 | v11/v12/v13/v14/v15/v16 + MCP関連 + 新規API |
| **HN案件系** | 41件 | `t_880da339`で90件→53件に整理済だが重複多 |
| **合計** | 53件 | 8/31以前タスク含む |

### 収益系11件の内訳

| 優先度 | タスクID | タイトル | 実装可能性 | コスト |
|--------|----------|----------|----------|------|
| **高** | t_86e83e24 | dmm-scraper publish（daily limit待ち） | 18:00以降 | 30分 |
| **高** | t_4de26f84 | Apify top5 PPE pricing live test | 即時可 | 1-2h |
| **高** | t_05d5f3da | Apify publish retry after 429 reset | 18:00以降 | 30分 |
| **高** | t_1d4c31a9 | RapidAPI private 2 APIs monetization (API-direct) | CDP手動確認要 | 1h |
| **中** | t_792918af | v14-B New demand-side actors publish | 3アクター作成+publish | 3-4h ⚠️1セッション超 |
| **中** | t_90fce3df | v15-A description 110 bulk templating | 即時可 | 2h |
| **中** | t_60f5b5de | v11-A RapidAPI paid plan via CDP | CDP必要 | 1.5h |
| **中** | t_ca5eb971 | v12-B RapidAPI top3 FREEMIUM to PAID A/B | CDP必要 | 2h |
| **中** | t_a4b1f89e | 既存ApifyアクターのMCPサーバー化 | 即時可 | 3-4h ⚠️高コスト |
| **中** | t_bdcf32a7 | 日本語帳票・PDFデータ抽出API需要調査 | リサーチのみ | 30分 |
| **低** | t_3409ff7c | v12-C Gumroad agyhq Bing index daily check | cron設定のみ | 30分 |
| **低** | t_21a7df50 | v16-A Apify SEO batch 効果測定 | 9/5以降計測 | 1h |
| **低** | t_d9ec7541 | v16-B Gumroad agyhq external traffic test | 9/5以降実施 | 1.5h |
| **低** | t_712c11c2 | v13-C ready-task prioritization（本件） | docsのみ | 15分 |

---

## 2. ワーカー推奨優先順位（エビデンスベース）

### 🥇 Tier 1（即時実装可・低コスト・高効果）

| # | タスク | 根拠 | 想定時間 |
|---|--------|------|---------|
| 1 | **t_4de26f84** (v11-B) | Apify top5 PPE pricing live test — t_79c58629 (PPE/collection accuracy)実装済→次ステップとして**収益効果を実測で確定**できる。今すぐ検証可能（9/3 12:00以降のrun countが必要）。 | 1-2h |
| 2 | **t_90fce3df** (v15-A) | description 110 bulk templating — t_15af8300 (v14-C)で時間かかっている作業を効率化。**インフラ整備タスク**で実装後は以降のSEO batchが楽になる。 | 2h |
| 3 | **t_05d5f3da** (v11-C) | Apify publish retry after 429 reset — **9/4 18:00以降のdaily limit解消**で実行可能。t_86e83e24と統合可（同じdaily limit枠）。 | 30分 |

### 🥈 Tier 2（CDP手動確認が要る・またはコスト中）

| # | タスク | 根拠 | 想定時間 |
|---|--------|------|---------|
| 4 | t_60f5b5de (v11-A) | RapidAPI paid plan via CDP — v14-A (t_698fc46c) でAPI-directはblocked判明済→**CDP経由が現実解**。 | 1.5h |
| 5 | t_1d4c31a9 (v13-B) | RapidAPI private 2 APIs monetization — v14-Aの続き。手動cookie必要ならスキップ。 | 1h or skip |
| 6 | t_ca5eb971 (v12-B) | RapidAPI top3 FREEMIUM to PAID A/B test — 重要だが**RapidAPIの公開API仕様変更に依存**するため変動リスクあり。 | 2h |
| 7 | t_bdcf32a7 | 日本語帳票・PDF API需要調査 — リサーチのみなので他タスクの合間に。 | 30分 |

### 🥉 Tier 3（高コスト・または条件待ち）

| # | タスク | 根拠 | 想定時間 |
|---|--------|------|---------|
| 8 | t_792918af (v14-B) | New demand-side actors — 3アクター作成+publish = **90-120分超・1セッションで完了困難**。分割実装か次回バッチに委ねる。 | 3-4h ⚠️ |
| 9 | t_a4b1f89e | 既存ApifyアクターのMCPサーバー化 — 高コスト・効果未確定・**v14-CのSEO効果測定（t_21a7df50）を先**に評価すべき。 | 3-4h ⚠️ |
| 10 | t_3409ff7c (v12-C) | Gumroad agyhq Bing index daily check — cron設定のみだが**実装価値は Bing index 確認**自体。 | 30分 |

### ⏸️ Wait（時間待ち）

| # | タスク | 待機条件 | 次回再評価 |
|---|--------|---------|----------|
| W1 | t_86e83e24 (dmm-scraper) | 9/4 18:00以降 | 18:05バッチから処理可 |

### 📅 Future（9/5以降）

| # | タスク | 実施時期 |
|---|--------|---------|
| F1 | t_21a7df50 (v16-A) | 9/5 24h / 9/6 72h / 9/7 168h 計測 |
| F2 | t_d9ec7541 (v16-B) | 9/5以降実施 |

---

## 3. ワーカーバッチ戦略（推奨パターン）

### パターンA: 1バッチ=1高効果タスク（推奨・デフォルト）

```
1セッション = 1 Tier 1タスクを「実装→検証→報告」まで完了
所要: 1-2時間/タスク
1日2-3セッション稼働（atushi16/kudou/chugaku/Tankanのdaily limit範囲外）
```

### パターンB: HN系タスクの一括処理（HN重複対策）

HN案件41件は**重複整理（t_2d2928e0修正済）が完了**しているが、HNの性質上「個別実装コスト=実装価値」を超えない。**5件に1件だけ実装**または**全件skip**を推奨:
- 理由: HNの個別実装は収益化に直結しない・テンプレ的実装になりがち
- 代替: 既に done 化された20+件の分析から「収益化に効くパターン」を抽出するリサーチタスクに置換

### パターンC: 計測待機タスク（v16-A等）

cron 9/5 4:00（kensho-revenue-collect）実行後のデータを待ってから実施。**1日1回確認+記録**で足りる。

---

## 4. 今セッション（即時実行）の推奨

| 時刻 | タスク | 根拠 |
|------|--------|------|
| **12:47-13:47** | t_712c11c2 (本件) → 完了 → 次に t_4de26f84 (v11-B) | 即時実装可・PPE効果実測 |

次のワーカー実行では以下を推奨:
1. **t_4de26f84** (Tier 1最優先)
2. **t_90fce3df** (Tier 1・v15-A)
3. **t_86e83e24 + t_05d5f3da** (18:00以降まとめて)

---

## 5. 申し送り（次回critic/workerへ）

- **HN案件41件の処理方針**: 5件/日ペースの「選択実装」または「リサーチ統合」を推奨。全部実装は非効率。
- **Tier 3の高コストタスク（v14-B, MCP）**: 分割実装またはROI再評価が必要。
- **Tier 2のCDP依存タスク**: ユーザー手動（cookie）が絡むため、自動化worker単独では完了困難。**ユーザー対応タグ**付け検討。
- **9/5以降の計測タスク**: cron収集後のデータで実測→優先度再評価。

---

## 6. 完了条件

- [x] readyタスクの網羅的把握（53件・収益系11件・HN系41件）
- [x] 5軸（実装コスト/収益インパクト/即時性/リスク/依存関係）で優先順位決定
- [x] ワーカーが次回すぐ参照できる形式で構造化
- [x] 申し送り（次回critic/workerへの引き継ぎ）明記

---

**Result**: 優先順位ガイド完了。次回workerはTier 1の t_4de26f84 から着手推奨。HN案件は方針要相談。
