# Worker Report — t_d37bae42: MCP Server Publication

## verification_evidence

Published 5 MCP servers to the official MCP registry (registry.modelcontextprotocol.io).

### Command citations (3+):

```
$ curl 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.atushi1841/japan-market-mcp'
{"servers":[{"name":"io.github.atushi1841/japan-market-mcp","version":"1.0.0"}]}
```

```
$ curl 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.atushi1841/japan-jepx-mcp'
{"servers":[{"name":"io.github.atushi1841/japan-jepx-mcp","version":"1.0.0"}]}
```

```
$ curl 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.atushi1841/japan-property-hazard-mcp'
{"servers":[{"name":"io.github.atushi1841/japan-property-hazard-mcp","version":"1.0.0"}]}
```

```
$ curl 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.atushi1841/rakuten-japan-mcp'
{"servers":[{"name":"io.github.atushi1841/rakuten-japan-mcp","version":"1.0.0"}]}
```

```
$ curl 'https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.atushi1841/mandarake-surugaya-mcp'
{"servers":[{"name":"io.github.atushi1841/mandarake-surugaya-mcp","version":"1.0.0"}]}
```

```
$ python3 -c "import json; d=json.load(open('/mnt/d/Project2/kensho/data/mcp_directory_ledger.json')); print('Total:', len(d['servers'])); print([s['server'] for s in d['servers']])"
Total: 13
['kensho-kaku', 'kensho-kclub', 'kensho-kema', 'kensho-sweep-mcp', 'tcg-price-japan', 'japan-anime-figure-mcp', 'japan-minimum-wage-mcp', 'japan-fuel-price-mcp', 'japan-market-mcp', 'japan-jepx-mcp', 'japan-property-hazard-mcp', 'rakuten-japan-mcp', 'mandarake-surugaya-mcp']
```

### Server metadata created:

- server_japan-market-mcp.json — schema v2025-12-11, version 1.0.0, registryType=mcpb
- server_japan-jepx-mcp.json — schema v2025-12-11, version 1.0.0, registryType=mcpb
- server_japan-property-hazard-mcp.json — schema v2025-12-11, version 1.0.0, registryType=mcpb
- server_rakuten-japan-mcp.json — schema v2025-12-11, version 1.0.0, registryType=mcpb
- server_mandarake-surugaya-mcp.json — schema v2025-12-11, version 1.0.0, registryType=mcpb

### .mcpb packages created:

- japan-market-mcp.server.mcpb
- japan-jepx-mcp.server.mcpb
- japan-property-hazard-mcp.server.mcpb
- rakuten-japan-mcp.server.mcpb
- mandarake-surugaya-mcp.server.mcpb

### Directory ledger updated:

- mcp_directory_ledger.json — total 13 servers (8 existing + 5 new)
- All 5 new servers marked registry_verified=true
- registry total updated from 8 to 13