#!/usr/bin/env python3
"""Dump agent.log lines inside a time window for one profile (diagnosis helper)."""
from __future__ import annotations

import datetime
import re
import sys

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2}):(\d{2})")


def main() -> int:
    path = sys.argv[1]
    day = sys.argv[2]
    hhmm_from = sys.argv[3]
    hhmm_to = sys.argv[4]
    needles = sys.argv[5:]

    def ts(hh, mm):
        return datetime.datetime.strptime(f"{day} {hh}:{mm}", "%Y-%m-%d %H:%M").timestamp()

    lo = ts(*hhmm_from.split(":"))
    hi = ts(*hhmm_to.split(":"))
    n = 0
    with open(path, "rt", errors="replace") as fh:
        for line in fh:
            m = TS_RE.match(line)
            if not m:
                continue
            t = datetime.datetime(
                int(m.group(1)[:4]), int(m.group(1)[5:7]), int(m.group(1)[8:10]),
                int(m.group(2)), int(m.group(3)), int(m.group(4)),
            ).timestamp()
            if not (lo <= t <= hi):
                continue
            if needles and not any(x in line for x in needles):
                continue
            n += 1
            print(line.rstrip()[:300])
    print(f"--- {n} lines", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
