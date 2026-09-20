#!/usr/bin/env bash
# Probe both scraper legs from this IP.
set -u
cd /mnt/d/Project2/yahoo-auctions-japan-scraper
echo "=== YAHOO probe (ILCE-7M4) ==="
timeout 90 /home/atushi/.hermes/hermes-agent/venv/bin/python3 - <<'PYEOF'
import asyncio, httpx
from research.research_locally import search_keyword
headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36','Accept-Language':'ja,en;q=0.9'}
async def r():
    async with httpx.AsyncClient(headers=headers,timeout=30,follow_redirects=True) as c:
        it=await search_keyword(c,'ILCE-7M4',1,5)
        print('YAHOO items:',len(it))
        for x in it[:3]: print('  ',x.get('title'),'| cur',x.get('currentPrice'),'| bn',x.get('buyNowPrice'))
asyncio.run(r())
PYEOF
echo "suruga probe rc=$?"
echo "=== SURUGA probe (ILCE-7M4) ==="
cd /mnt/d/Project2/suruga-scraper
timeout 100 /home/atushi/.hermes/hermes-agent/venv/bin/python3 src/__main__.py "ILCE-7M4" --pages 1 --in-stock --output _test_r7m4.json
echo "suruga rc=$?"
ls -la data/_test_r7m4.json 2>&1
