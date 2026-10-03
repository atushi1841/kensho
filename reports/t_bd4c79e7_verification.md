# verification report for t_bd4c79e7

task: MCPサーバー6本を公式レジストリ(registry.modelcontextprotocol.io)へ登録しURLで検証する
作成: 2026-10-04 / 作業者 kensho-sweeps（前カード t_7b23112d の虚偽完了を実体で置換）

## verification_evidence

実測はすべて本番レジストリAPIとGitHubへの実リクエスト結果である（推測値なし）。

### 1. 公式レジストリ登録（6本すべて）

$ for n in kensho-kaku kensho-kclub kensho-kema kensho-sweep-mcp tcg-price-japan japan-anime-figure-mcp; do printf '%s ' "$n"; curl -s "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.atushi1841/$n" | python3 -c 'import sys,json; d=json.load(sys.stdin); s=d.get("servers") or []; print(len(s), [(x.get("server") or x).get("name") for x in s][:1])'; done
→ kensho-kaku 1 ['io.github.atushi1841/kensho-kaku']
→ kensho-kclub 1 ['io.github.atushi1841/kensho-kclub']
→ kensho-kema 1 ['io.github.atushi1841/kensho-kema']
→ kensho-sweep-mcp 1 ['io.github.atushi1841/kensho-sweep-mcp']
→ tcg-price-japan 1 ['io.github.atushi1841/tcg-price-japan']
→ japan-anime-figure-mcp 1 ['io.github.atushi1841/japan-anime-figure-mcp']

### 2. 台帳（機械可読の成果物）

$ python3 -c "import json;d=json.load(open('data/mcp_directory_ledger.json'));print(sum(1 for s in d['servers'] if s['registry_verified']),'/',len(d['servers']),'verified')"
→ 6 / 6 verified

### 3. Release資産（server.json の identifier が指す実体）

$ gh release view v1.0.0 --repo atushi1841/kensho-kaku --json assets --jq '.assets[].name'
→ server.mcpb

### 4. OIDC公開workflowの配置（6リポジトリ）

$ python3 -c "import glob;print(len(glob.glob('/mnt/d/Project2/kensho/mcp/*/.github/workflows/publish-mcp.yml')),'workflows in place')"
→ 6 workflows in place

### 5. 受け入れコミット（push済み）

$ git log --oneline -1
→ be9a9a6 feat(mcp): 6サーバーを公式MCPレジストリへ登録（GitHub+OIDC自動公開）

## 変更ファイル

- reports/2026-10-04-mcp-official-registry.md（再現用レシピ・つまずき・検証コマンド）
- data/mcp_directory_ledger.json（実測URL/sha256/検証コマンド）
- mcp/<6サーバー>/server.json（新規）
- mcp/<6サーバー>/.github/workflows/publish-mcp.yml（新規）

## 補足（未了・別カードで追跡）

- crawl型ディレクトリ（glama.ai/mcp/connectors/io.github.atushi1841/<name>、github.com/mcp）は
  登録直後404。時間差同期のため数日〜2週間後に反映確認が必要（観測点として記録）。
