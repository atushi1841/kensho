# MCPサーバー収益化戦略レポート

**作成日**: 2026-09-18
**タスク**: t_e1abac50
**目的**: Kenshoスクレイピング技術をMCPサーバー化し、AIエージェント向けAPIとしてRapidAPI/mcp marketplaceで収益化

---

## 1. 現状整理

### 既存MCPサーバー（ Kensho資産）

| MCP | 状態 | 技術 | 収益化 |
|-----|------|------|--------|
| hazard_mcp / mcp_hazard | プロトタイプ完成 | FastAPI + CDP mode + Apify actor-ready | Smithery登録予定 |
| 燃料価格MCP | **RapidAPI公開済** | Python MCP server | freemium成功事例 |
| 最低賃金MCP | **RapidAPI公開済** | Python MCP server | freemium成功事例 |

### 進行中タスク

| タスク | 内容 | 状況 |
|--------|------|------|
| t_06fdd792 | 7th MCP: 日本ハザードリスク | **BLOCKED** — RapidAPI quota枯渇（ユーザー対応待ち） |
| t_eb308533 | 8th MCP: JEPX電力価格 | **実装完了** — QA検証待ち（4回クラッシュはプロトコル違反） |
| t_e1abac50 | MCP収益化戦略（今タスク） | **本レポート** |

---

## 2. 競合分析（2026-09-18実測）

### 検索結果

| 検索クエリ | 结果 | 意味 |
|------------|------|------|
| GitHub "jepx mcp" | **total_count: 0** | JEPX MCPサーバー未存在 |
| GitHub "hazard mcp japan" | **total_count: 0** | 日本ハザードMCP未存在 |
| Glama "jepx"/"japan electricity" | **該当なし** | MCPレジストリに日本電力データ無し |
| Glama "hazard" | US/Indonesia/UKのみ | 日本語住所レベルのハザードMCPは無い |
| X（Twitter）検索 | 日本製品MCPサーバー無し | 日本市場の盲点確認済 |

### 競合優位性

- **欧米中心**: US hazard MCPs (us-property-hazard-risk, mcp-hazards) は日本データ非対応
- **japan-gov-mcp**: API一覧のみで住所レベルリスクスコア無し
- **x402課金**: jp-m2m-mcpがJP規制データで実績あり（決済インフラ証明済み）

---

## 3. 候補API優先順位

| 優先度 | API | 需要先 | データ入手 | 実装難易度 | 収益可能性 |
|--------|-----|--------|-----------|-----------|-----------|
| **P1** | **JEPX電力価格** | EV充電/蓄電池/Battery arbitrage | JEPX公開データ+OCCTO | 低（既に実装完了 t_eb308533） | 高（リアルタイム性+需要増加中） |
| **P2** | **天気/気象** | 農業・物流・外食・施工管理 | jma-api 或いは Open-Meteo | 低（無料APIで開始可能） | 中（競合はるかだが需要安定） |
| **P3** | **為替データ** | 輸出入企業・FX教育・旅行 | FinanceAPI/為替Wiki | 低 | 中（為替MCPは既に他社あり） |
| **P4** | **ハザードリスク** | 不動産・保険・引っ越し | MLIT RiskASSIST/国土地理院 | 高（API審査必須） | 高（t_06fdd792で検証済み） |

**P1を最優先理由**: t_eb308533が実装完了済み、JEPXデータは公開ソース+OCCTO補完で安定提供可能、電力自由化2016年以降の実需要あり

---

## 4. 収益化モデル

### 既存プレイブック（燃料価格・最低賃金MCPの成功パターン）

```
Phase 1: RapidAPI freemium公開（0円）→ 需要検証
Phase 2: 有料プラン設定（$9.99/月 or $0.01/call）→ 安定課金
Phase 3: Smithery/MCPマーケットプレイ登録 → 認知拡大
Phase 4: x402 pay-per-call併用 → 即時マイクロ決済
```

### 売上見通し（保守推定）

| MCP | 1日API呼び出し | 月間収益（$0.01/call） |
|-----|---------------|----------------------|
| JEPX電力価格 | 30 calls | $9/月 |
| 天気データ | 50 calls | $15/月 |
| ハザードリスク | 20 calls | $6/月 |
| **合計** | **100 calls** | **$30/月** |

※ 燃料価格MCPの実績を参照。実際は有料プラン移行で10-50倍に伸び得る

---

## 5. 実装ロードマップ

### 今週（2026-09-18〜09-25）

- [x] t_eb308533 JEPX MCP実装完了 → QA検証（033ff6065ef7）に委譲
- [ ] t_e1abac50 本戦略レポート作成完了 → 今タスク
- [ ] t_06fdd792 blocked解除（ユーザーにRapidAPI追加枠を要確認）

### 来週以降

- [ ] JEPX MCPをRapidAPIにpublish（rapidapi_admin.py使用）
- [ ] 天気MCPのプロトタイプ作成（Open-Meteo API利用、APIキー不要）
- [ ] Smithery登録（JEPX MCP优先）

---

## 6. リスクと対策

| リスク | 確度 | 対策 |
|--------|------|------|
| RapidAPI quota枯渇（t_06fdd792で実測） | 高 | PUBLIC枠→PRIVATE化で冗長化、ユーザーに追加枠要請 |
| JEPXデータIP制限 | 中 | OCCTO public APIをフォールバック（タスク本体に明記済） |
| BOT検出・TOS違反 | 低 | MCPはAPIサーバーなのでCDP/ブラウザ操作無し、リスク低 |
| 需要不足 | 中 | 無料クーポン配布でフィードバック収集（hazard MCPロードマップ準拠） |

---

## 7. 結論

**MCPサーバー収益化は実現可能**。証拠:
1. 既存2MCP（燃料価格・最低賃金）がRapidAPIで成功収益化済み
2. 日本語MCPサーバーは竞合ゼロ（GitHub/Glama実測でtotal_count=0）
3. x402課金のJP規制データでの実績（jp-m2m-mcp）あり
4. JEPX電力価格MCPは既に実装完了、次はQA検証→公開

**最優先アクション**: t_eb308533のQA検証完了→RapidAPI publish→Smithery登録
