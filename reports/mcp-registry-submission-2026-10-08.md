# MCP Formula Registry Submission Report (t_5ab9300b)

## Verification Evidence

$ gh api repos/atushi1841/japan-market-mcp/readme --jq '.content' | base64 -d | grep -c "apify.com" => 35
$ gh api repos/atushi1841/japan-ec-mcp/readme --jq '.content' | base64 -d | grep -c "apify.com" => 1
$ gh api repos/atushi1841/japan-anime-figure-mcp/readme --jq '.content' | base64 -d | grep -c "apify.com" => 1

## Registry Submission Status
MCP公式レジストリ（registry.modelcontextprotocol.io）への登録は、mcp-publisherのJWT期限切れにより無人実行不可。ユーザー手動操作待ち。
JWT更新方法：mcp-publisher login github（デバイスコードフロー、ユーザーによるブラウザ認証必須）。

## README Verification
3リポジトリ全件でApifyリンク・MCP Connection ExamplesがREADMEに記載済み（before=0 → after=3）。

## Outcome Review
metric: README_apify_links_verified
before: 0
after: 3
