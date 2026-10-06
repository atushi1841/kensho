# t_2d49610b — japan-ec-mcp README改善完了証跡

タスクID: t_2d49610b
タイトル: japan-ec-mcp READMEにApify詳細URL+MCP接続例を追記し外部流入改善
担当: kensho-revenue-worker
実施日時: 2026-10-06 JST

## verification_evidence

t_2d49610b の完了条件に対する実測検証。

### 成功指標 (1/2): curl README | grep -c apify.com >= 4

```
$ curl -s https://raw.githubusercontent.com/atushi1841/japan-ec-mcp/main/README.md | grep -c "apify.com"
14
```

- t_2d49610b 目標: >= 4
- 実測: 14 → **達成** (3.5倍)
- リンク内訳: mercari/yahoo/surugaya/kakaku/rakuten(5) + mandarake/kitamura/jackroad/komehyo/tackleberry(5) + japan-market-mcp/japan-anime-figure-price-data/japan-anime-figure-demand-features(3) + 収益化経路文脈(1)

### 成功指標 (2/2): README に "## MCP 接続例" セクションが存在する

```
$ curl -s https://raw.githubusercontent.com/atushi1841/japan-ec-mcp/main/README.md | grep -E "^## " 
## Tools（MCP ツール一覧）
## MCP 接続例
## Related Apify Actors
## Quickstart
## MCP 公開レジストリ登録状況
## 収益ゲート（この README の役割）
## License
```

- t_2d49610b 目標: "## MCP 接続例" セクションの存在
- 実測: 存在 → **達成**
- セクション内 4 pattern: stdio (Claude Desktop) / HTTP mode / Python import / n8n-Apify Workflow

### 差分確認

```
$ git -C /tmp/jecmcp log --oneline -1
824e25d docs(t_2d49610b): READMEにApify詳細URL+MCP接続例を追記し外部流入改善

$ git -C /tmp/jecmcp show --stat HEAD
824e25d docs(t_2d49610b): READMEにApify詳細URL+MCP接続例を追記し外部流入改善
 README.md | 165 +++++++++++++++++++++++++++++++++++++++---
 1 file changed, 165 insertions(+), 13 deletions(-)
```

- 変更ファイル: japan-ec-mcp/README.md 1ファイルのみ（スコープ最小）
- 変更量: 927B → 6885B（約 7.4倍）
- Commit hash: 824e25d
- Push: `git push` 成功 (`8456bf6..824e25d main -> main`)

### GitHub HTTP 確認

```
$ curl -s -o /dev/null -w "%{http_code}\n" https://github.com/atushi1841/japan-ec-mcp
200

$ curl -s https://api.github.com/repos/atushi1841/japan-ec-mcp | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('default_branch'),d.get('size'),d.get('pushed_at'))"
main 2 2026-10-06T10:14:xx+00:00
```

- リポジトリ HTTP: 200
- 変更反映済み

### 収益ゲート充足チェック

| 項目 | 内容 | 実測 |
|---|---|---|
| 誰が買う | MCPクライアント利用者（Claude/Cursor/VS Code + 日本市場データ） | README明記済 |
| どのチャネルで届くか | GitHub README → Smithery / mcp.so（要ユーザー対応）→ Apify 86本 | 3段階明記済 |
| 30日で何を測れるか | READMEにapify.com>=4 / Smithery api 200 | apify=14 / Smithery=未登録継続 |
| 既存何を再利用 | 既存README + Apify actors + smithery.yamlテンプレ | 全て利用 |

---

## Reflexion

**実施した作業**: t_2d49610b に対する実装・検証・push・証跡作成

**良かったこと**:
- README単体で完結するスコープ（1ファイルのみ）
- 既存の Apify actor 名 + smithery.yaml パターンを再利用
- 外部流入チャネルを「GitHub → Smithery → Apify」の3段に明示

**改善点**:
- Smithery API で自動登録できないためユーザー手動待ち（構造的・不可避）

**Learned**: Apify actors の公開スナップショット（data/apify_actors_detail_snapshot.json）は description フィールドが空で URL のみ有用。次回は URL 生成は名前から決定論的にできる。

**Confidence**: 10

**Verification evidence**: 上記 curl 実測 + commit 824e25d + push 完了ログ
