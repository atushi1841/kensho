#!/usr/bin/env python3
"""measure_agentic_standby_t_8646bcf9.py — one-shot re-measurement (kanban t_8646bcf9).

Root cause found: docs.apify.com/integrations/x402 "Supported Actors" — actors using
Standby mode are EXCLUDED from the agentic-payments (x402) whitelist. The 2 PPE MCP
actors had Standby enabled; fixed in t_8646bcf9 by PUT actorStandby.isEnabled=false
(pre-state saved in the worker workspace: standby_pre_<actorId>.json).

This script re-scans /v2/acts after Apify's whitelist refresh and logs whether
japan-market-mcp / mandarake-surugaya-mcp flipped to isWhiteListedForAgenticPayments=true.
Self-removes its crontab entry after running (t_e971e85a pattern).
"""

import datetime
import json
import subprocess
import urllib.request

SCRIPT = "measure_agentic_standby_t_8646bcf9.py"
TOKEN_LINE = "APIFY_TOKEN_DEFAULT="


def token():
    for line in open("/mnt/d/Project2/kensho/.env"):
        if line.strip().startswith(TOKEN_LINE):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no token")


def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token()}", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["data"]


def main():
    # /v2/acts does NOT carry the flag; /v2/store does (v87 evidence: 62/72 true).
    items = get("https://api.apify.com/v2/store?limit=1000&username=fruitful_quintessence")["items"]
    wl = sum(1 for i in items if i.get("isWhiteListedForAgenticPayments"))
    targets = {}
    for i in items:
        if i.get("name") in ("japan-market-mcp", "mandarake-surugaya-mcp"):
            targets[i["name"]] = {
                "whitelisted": i.get("isWhiteListedForAgenticPayments"),
                "standbyUrl": i.get("standbyUrl"),
            }
    print(
        datetime.datetime.now().isoformat(timespec="seconds"),
        f"wl={wl}/{len(items)}",
        json.dumps(targets, ensure_ascii=False),
    )


if __name__ == "__main__":
    main()
    cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    new = "\n".join(line for line in cron.splitlines() if SCRIPT not in line) + "\n"
    subprocess.run(["crontab", "-"], input=new, text=True)
    print("self-removed cron entry")
