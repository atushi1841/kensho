"""stdio エントリポイント — MCPBバンドル（ローカル実行）用。

Apify Standby（HTTP）ではなく、Claude Desktop / Cursor / Smithery の
ローカル配布（MCPB）として起動するときの入り口。

- transport は FastMCP 既定の stdio（stdout は JSON-RPC 専用、ログは stderr）
- データは同梱 data/accumulated.jsonl（読み取り専用）
- ネットワーク・APIキー不要
"""
from __future__ import annotations

import logging
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from server.server import server  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    server.run()  # FastMCP 既定 transport = stdio


if __name__ == "__main__":
    main()
