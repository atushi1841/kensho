import json
from server.server import _load

rows = _load()
print(f'Total rows: {len(rows)}')
print(f'First row keys: {list(rows[0].keys()) if rows else "none"}')