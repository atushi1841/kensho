# t_7d5d5ed1 verification

## verification_evidence
$ git -C /mnt/d/Project2/kensho log -1 --oneline
50255bf manifest repositoryUrl/homepageUrl 追加 (t_7d5d5ed1 step1)
$ python3 -c "import json; d=json.load(open('/mnt/d/Project2/kensho/mcp/kensho-kema/manifest.json')); print('repositoryUrl',d.get('repositoryUrl')); print('homepageUrl',d.get('homepageUrl'))"
repositoryUrl https://github.com/atushi1841/kensho
homepageUrl https://github.com/atushi1841/kensho
$ ls -l /mnt/d/Project2/kensho/mcp/kensho-kema/server.mcpb
-rwxrwxrwx 1 atushi atushi 128512 Oct  4 06:52 /mnt/d/Project2/kensho/mcp/kensho-kema/server.mcpb
$ curl -s https://api.smithery.ai/servers/atushi1841/kensho-kema | python3 -c "import json,sys; d=json.load(sys.stdin); print('description:', repr(d.get('description')))"
description: ''
$ git -C /mnt/d/Project2/kensho diff --name-only HEAD~1
mcp/kensho-kaku/manifest.json
mcp/kensho-kclub/manifest.json
mcp/kensho-kema/manifest.json
mcp/kensho-sweep-mcp/manifest.json
mcp/tcg-price-japan/manifest.json
