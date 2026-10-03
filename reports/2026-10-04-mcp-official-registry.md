# MCPサーバー6本の公式レジストリ登録（2026-10-04 完了）

## 結果

**6/6 が公式MCPレジストリ（registry.modelcontextprotocol.io）に登録された。** 全て version 1.0.0。

| サーバー | レジストリ名 | 検証コマンド |
|---|---|---|
| kensho-kaku | io.github.atushi1841/kensho-kaku | `curl 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.atushi1841/kensho-kaku'` |
| kensho-kclub | io.github.atushi1841/kensho-kclub | 同上（名前を差し替え） |
| kensho-kema | io.github.atushi1841/kensho-kema | 同上 |
| kensho-sweep-mcp | io.github.atushi1841/kensho-sweep-mcp | 同上 |
| tcg-price-japan | io.github.atushi1841/tcg-price-japan | 同上 |
| japan-anime-figure-mcp | io.github.atushi1841/japan-anime-figure-mcp | 同上 |

機械可読の台帳: `data/mcp_directory_ledger.json`（実測URL・sha256・検証コマンド入り）

## なぜ必要だったか

2026年の実務記事の一致した結論:「15箇所に個別投稿するのではなく、**GitHubリポジトリ**と**公式レジストリの
登録**の2資産が大半の仕事をし、crawl型ディレクトリ（glama.ai / github.com/mcp 等）はそこから自動で拾う」。
登録前の実測は **0件**（`search=kensho` → 0）で、需要側チャネルが丸ごと欠けていた。

## 実測した手順（再現用レシピ）

前提: Apifyと同じで、**PyPIへの公開は不要**。レジストリは `mcpb` 形式を正式サポートしており、
GitHub Release の直URL + sha256 で登録できる（schema 2025-12-11 の `Package.registryType` に `mcpb`、
`identifier` は「パッケージ名 **または直URL**」、`fileSha256` は「**MCPBでは必須**」）。

1. **GitHubリポジトリを作る**（今回6本作成済み。Windows側 `gh` は atushi1841 で認証済み）
   ```powershell
   gh repo create atushi1841/<name> --public --description '<desc>' --push --source .
   ```
   ※ 説明文に非ASCII（日本語等）を渡すとWindowsコンソール(CP932)で失敗する。**説明はASCIIで書く**。
2. **Release に .mcpb を添付**
   ```powershell
   gh release create v1.0.0 --repo atushi1841/<name> --title v1.0.0 --notes '...' 'D:\...\<name>\server.mcpb'
   ```
   アセットURLは `https://github.com/atushi1841/<name>/releases/download/v1.0.0/server.mcpb`
3. **`server.json` をリポジトリ直下に置く**
   ```json
   {
     "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
     "name": "io.github.atushi1841/<name>",
     "description": "100字以内（超えると422で拒否される）",
     "version": "1.0.0",
     "repository": {"url": "https://github.com/atushi1841/<name>", "source": "github"},
     "packages": [{"registryType": "mcpb",
       "identifier": "https://github.com/atushi1841/<name>/releases/download/v1.0.0/server.mcpb",
       "version": "1.0.0", "fileSha256": "<sha256>", "transport": {"type": "stdio"}}]
   }
   ```
   検証: `mcp-publisher validate server.json`（**本番レジストリに問い合わせる**ので実質E2E検証）
4. **GitHub Actions で OIDC 公開**（`login github` の対話OAuthは不要＝完全自動）
   `.github/workflows/publish-mcp.yml`:
   ```yaml
   permissions: {id-token: write, contents: read}
   steps:
     - curl -sL .../mcp-publisher_linux_amd64.tar.gz | tar xz
     - ./mcp-publisher login github-oidc
     - ./mcp-publisher publish
   ```
   名前空間は「GitHubでそのユーザーとしてログイン、**またはそのユーザーのリポジトリの Actions 内**」で
   所有確認されるため、`io.github.atushi1841/*` はこの経路で通る。

## つまずき（記録）

- `gh` の出力は CP932。Pythonから `subprocess` で読むときは `decode('cp932', errors='replace')` が必要。
- GitHub API は作成直後に 404 を返すことがある（キャッシュ）。`gh repo view` で確認するのが確実。
- レジストリ検索APIも時々シャードで空を返す（kensho-sweep-mcp が一瞬 ✗ になった）。**再試行で確定**させる。
- 一括push中に一時的な `dial tcp ... timeout` が発生し、3本のpushが落ちた。**リトライで解決**。

## 波及状況

`glama.ai/mcp/connectors/io.github.atushi1841/<name>` と `https://github.com/mcp` は登録直後は **404**。
これらはcrawl型で時間差同期のため、数日〜2週間で反映される見込み。反映の確認は次の観測点。

## 前カードの虚偽完了について

前カード `t_7b23112d` は「レポート作成＋Smithery公開済みの確認」で完了扱いになっていたが、実物検証では
GitHubリポジトリ0本・レジストリ0件だった（＝成果物なし）。本作業はその実体を後追いで実施したもの。
教訓: **カードの完了条件は検証可能な成果物のURLで書く。レポート作成は完了にしない。逃げ道条項は
「そのサイトが自動化を明示的に禁止している場合に限る」と狭く限定する。**

## verification_evidence

```
$ for n in kensho-kaku kensho-kclub kensho-kema kensho-sweep-mcp tcg-price-japan japan-anime-figure-mcp; do
    curl -s "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.atushi1841/$n" | head -c 120; echo; done
→ 6本すべてで servers 配列に該当エントリ（name=io.github.atushi1841/<n>, version=1.0.0）を確認

$ python3 -c "import json;d=json.load(open('data/mcp_directory_ledger.json'));print(sum(1 for s in d['servers'] if s['registry_verified']),'/',len(d['servers']))"
→ 6 / 6
```
