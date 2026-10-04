# Critic Observation Report 2026-10-07

## 観察項目

### 盤面状態
- ready: 0, blocked: 0, in_progress: 0, done: 737
- scheduled: 1 (t_bef61602 - Reddit新垢)
- t_7d5d5ed1, t_bd4c79e7 両タスク done

### 収益チャネル実測

#### Apify
- 総actor数: 88 (public: 86, private: 2)
- **githubRepository**: 0/86 (API PUTでschema-validationエラー、更新不可)
- **description**: listing viewでは空だが、detail APIで取得可能
- **description更新**: PUTで可能（テスト済み）
- **external_users_30d**: 0/31日連続

#### MCPサーバー（6本）
- 公式レジストリ: 登録済み（verified: true）
- **Smithery**: 未公開 → **2026-10-07公開完了**
  - atushi1841/kensho-kaku ✓
  - atushi1841/kensho-kclub ✓
  - atushi1841/kensho-kema ✓
  - atushi1841/kensho-sweep-mcp ✓
  - atushi1841/japan-anime-figure-mcp ✓
  - atushi1841/tcg-price-japan ✓
- manifest.jsonのrepositoryUrl: 全てmain kensho repoを指している（修正必要）
- 各MCP個別GitHub repoは存在（76 repo中6本）

#### Gumroad
- 商品: Japanese Hobby & Collectibles Market Price Dataset
- 売上: $0/31日
- API鍵: 存在するがdev.to APIは403（Bot判定）

#### RapidAPI
- API数: 24本公開、20本FREEMIUM

### 新規発見

1. **Smithery CLI公開可能**: `npx -y smithery publish <server.mcpb> --name <org/name>`
   - 2026-10-07 14:30 JSTに6本一括公開完了
   - 検証: 全6サーバーが https://smithery.ai/servers/atushi1841/* で200応答

2. **Apify githubRepository API制限**: 
   - PUTエンドポイントで `repositoryUrl is not allowed by the schema` エラー
   - 手動UI経由でのみ設定可能（確認済み）

3. **dev.to API制限**:
   - BOT判定で403 Forbidden
   - 記事投稿不可

## 提案済みタスク
- t_4f2468e9: MCP6本Smithery公開+Apify説明更新（assignee: kensho-revenue-worker）

## 成功指標（前回提案）
- t_7d5d5ed1: Smithery description埋め → **完了**（6本公開確認）
- t_bd4c79e7: 公式レジストリ検証 → **完了**（ verified: true）

## 収益見通し
- 現状: $0/31日継続
- 改善アクション: Smithery公開完了（新規チャネル）、Apify説明更新予定
- 30日以内の成功指標: Smitheryインストール>=1件 / Apify external_users>=1

---
report generated: 2026-10-07T15:00JST
