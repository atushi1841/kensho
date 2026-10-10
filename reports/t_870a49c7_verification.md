# t_870a49c7 verification — mcp.json metadata for 10 unlisted MCP repos

## verification_evidence

t_870a49c7 の完了条件「unlisted_repos.txt の全repoに mcp.json or READMEメタデータ付与・GitHub push済み」の実測証跡。t_870a49c7 着手時点では mcp.json 保有 0/10、READMEに modelcontextprotocol 言及ありは 3/10 のみだった。

$ gh api "repos/atushi1841/kensho-kaku/contents/mcp.json" --jq .content | base64 -d | head -4
{
  "name": "io.github.atushi1841/kensho-kaku",
  "description": "Japan X/Twitter sweepstakes data from ken-kaku.com. 3 tools: search, history, prize movers.",
  "version": "1.0.0",

$ CNT=0; for r in japan-anime-figure-mcp japan-ec-mcp japan-food-delivery-mcp japan-jepx-mcp japan-market-data japan-property-hazard-mcp kensho-kaku kensho-kclub kensho-kema kensho-sweep-mcp; do n=$(gh api "repos/atushi1841/$r/contents/mcp.json" --jq .content | base64 -d | python3 -c "import json,sys;d=json.load(sys.stdin);assert d['name'] and d['description'] and d['author'] and 'modelcontextprotocol' in d;print('OK')"); [ "$n" = OK ] && CNT=$((CNT+1)); done; echo "TOTAL_OK=$CNT/10"
TOTAL_OK=10/10

$ gh api "repos/atushi1841/japan-ec-mcp/contents/mcp.json" --jq .content | base64 -d | python3 -c "import json,sys;d=json.load(sys.stdin);assert d['name'] and d['description'] and d['author'] and 'modelcontextprotocol' in d;print('japan-ec-mcp OK')"
japan-ec-mcp OK

## 実施内容

unlisted_repos.txt（t_cfaf93c0成果物、10本）の各repoへ GitHub Contents API（`gh api --method PUT repos/atushi1841/<repo>/contents/mcp.json`）で最小 mcp.json（name/description/url/author/version/modelcontextprotocol）を直接push。コミットハッシュは metadata_added.log に記録。

| repo | commit |
|------|--------|
| japan-anime-figure-mcp | a7cf2992 |
| japan-ec-mcp | 21fe8a9d |
| japan-food-delivery-mcp | 83b933e8 |
| japan-jepx-mcp | 1b6508a1 |
| japan-market-data | d625c600 |
| japan-property-hazard-mcp | e9f752cd |
| kensho-kaku | 12a8ce0a |
| kensho-kclub | 8a041ac9 |
| kensho-kema | f8707849 |
| kensho-sweep-mcp | dfbf542d |

## Outcome

mcp.json保有: before=0/10 → after=10/10（read-back実測）。japan-market-data は初回PUTがGitHub API i/o timeoutで失敗→1回リトライで成功（d625c600）。

## t_870a49c7 完了条件との対応

1. 全repoに mcp.json 存在+必須フィールド → TOTAL_OK=10/10 実測 ✓
2. push済み → 各repoのGitHub default branch上にコミットハッシュ実在（Contents APIレスポンスのcommit sha）✓
