# MCP Registry Verification Report
Task: t_74141fe5

## 実行サマリ
- MCP公式レジストリへの既存Apify actor再配布を検証
- 4つのkensho MCPサーバーが既に登録済み（2026-10-03公開）
- 全てのmcpbファイルのSHA256がレジストリと一致

## 検証結果

### 1. MCPレジストリ検索
```bash
$ curl -s 'https://registry.modelcontextprotocol.io/v0.1/servers?search=kensho&version=latest'
```
結果: 4サーバー検出

- io.github.atushi1841/kensho-kaku (published: 2026-10-03T21:30:40.621657Z)
- io.github.atushi1841/kensho-kclub (published: 2026-10-03T21:36:49.647323Z)
- io.github.atushi1841/kensho-kema (published: 2026-10-03T21:38:52.680393Z)
- io.github.atushi1841/kensho-sweep-mcp (published: 2026-10-03T21:39:13.991561Z)

### 2. SHA256検証
全サーバーのmcpbファイルがGitHubリリースから取得可能で、レジストリ記載のハッシュと一致:

- kensho-sweep-mcp: 396651d822782d8c7d67c89b6e1201950f441258bfc784fe9bbf09dcf7ffb355 ✓
- kensho-kaku: a8d2b7f08a262389be50f4e635081516a262bb91f315d469db586b64646f9767 ✓
- kensho-kclub: 828c6090ee8f1938afd59c0eb03e6adb1919f22e779838988282a463c6f61e75 ✓
- kensho-kema: fa1476f02f91b48d602732ae3f067ed37faa985f79beebebd677deadf390a6f5 ✓

### 3. GitHubリポジトリ状態
全リポジトリstars=0, forks=0
- 既存のApify actorとは別チャネルとして機能
- MCPレジストリ経由での発見が可能

## 収益ゲート評価
1. 誰が買う: Claude/Cursor開発者・データサイエンティスト ✓
2. チャネル: MCP公式レジストリ（registry.modelcontextprotocol.io）✓
3. 30日成功指標: 外部run>=1 / レジストリ登録エントリ>=1
   - 現在: レジストリ登録エントリ=4件（既達成）
   - Apify external_runs: 0継続（要改善）
4. 既存再利用: Apify 86 actor + Kenshoスクレイピングモジュール ✓

## 結論
MCPレジストリへの再配布は既に完了。2026-10-03に4サーバーが公開済み。
現在の問題は可視性/信頼ではなく、レジストリからの流入がゼロであること。
次アクション: Hugging Face Hubへの追加掲載、README改善、dev.to記事経由での導線強化が必要。
