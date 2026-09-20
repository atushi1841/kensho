#!/usr/bin/env python3
import re, glob
# Capture the "応募" / apply stats section from today's summary plus the full log breakdown
summary = open("/mnt/d/Project2/kensho/logs/summary/2026-09-20.md", encoding="utf-8").read()
for i, line in enumerate(summary.splitlines()):
    if any(k in line for k in ("応募", "apply", "成功", "失敗", "成功率", "## ")):
        print(i, "|", line[:130])
