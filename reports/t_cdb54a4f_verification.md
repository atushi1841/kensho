# t_cdb54a4f Glama掲載カバレッジ拡大 — 検証記録 (2026-10-10)

## verification_evidence

$ curl -s 'https://glama.ai/mcp/servers?query=author%3Aatushi1841' | grep -oE 'href="/mcp/servers/[^"]+"' | sort -u | wc -l
5

$ gh api repos/atushi1841/kensho-kaku/contents/Dockerfile --jq '.sha[0:8]'
1c790e6e

$ printf '{"jsonrpc":"2.0","id":1,...initialize...}\n' | timeout 45 docker run -i --rm glama-test-kaku | grep jsonrpc | python3 -c "...tools/list..."
INIT: {'name': 'kensho-kaku', 'version': '4.1.0'}
TOOLS: ['current_sweep', 'sweep_history', 'top_prize_movers']

$ docker build -q -t glama-test-kaku .
sha256:2b486094c0b8c625bb068ff85e5a5d20094e4819f5c955ac0049f24464b78f32

$ curl -s "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.atushi1841" | python3 -c "...count..."
count= 10

## 実施内容
1. 原因分析: Glama methodology 1.3「AI推定Dockerfileのビルド失敗 → 検索結果から非表示」が未掲載の直接原因と特定。掲載5本は全て Dockerfile+.actor あり、未掲載7本（kensho-kaku/kclub/kema/sweep-mcp/tcg-price-japan/japan-anime-figure-mcp/japan-ec-mcp）は Dockerfile 無し。
2. 実装: 7本へ Dockerfile を追加 push（run2024: kaku=e228898, ec=2c57132 他5本。run2030が同一内容で再push、blob sha一致=競合なし）。tcg-price-japan へ glama.json maintainer claim 追加。
3. ローカル検証: docker build 成功 + MCP introspection（initialize/tools/list）で3ツール緑 = Glamaサンドボックスのビルド成功条件を満たす実証。
4. 公式MCPレジストリには io.github.atushi1841/* 10本 active 登録済（Glamaは公式レジストリのsuperset、methodology 3）。

## 現状と完了条件判定
- 完了条件「掲載12以上」は **未達（5のまま）**。push後~10分時点では再スキャン未反映。
- run2030は「手動OAuth submission必須」と結論し needs_input で block-loop検知（recurrences=2）→ カードは triage。
- 反証: methodology 3「Glama ingests and re-publishes everything in the official registry」より、公式レジストリ登録済10本は自動流入の余地あり。24h経過後の再クエリで判定すべき。

## 24h後の再検証コマンド
$ curl -s 'https://glama.ai/mcp/servers?query=author%3Aatushi1841' | grep -oE 'href="/mcp/servers/[^"]+"' | sort -u | wc -l  # => 12以上なら成功
