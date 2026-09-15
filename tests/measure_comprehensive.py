#!/usr/bin/env python3
"""総合stealth性能測定 — 全5検出サイト × JS評価"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kensho.application.browser import close_browser, create_browser

SITES = [
    ("sannysoft", "https://bot.sannysoft.com/"),
    ("rebrowser", "https://bot-detector.rebrowser.net/"),
    ("browserscan", "https://browserscan.net/"),
]

MEASURE_JS = """
() => ({
    webdriver: typeof navigator.webdriver + '=' + navigator.webdriver,
    webgl: (() => {
        try {
            const c = document.createElement('canvas');
            const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
            if (!gl) return 'no_webgl';
            return gl.getParameter(gl.VENDOR) + '|' + gl.getParameter(gl.RENDERER);
        } catch(e) { return 'error:' + e.message; }
    })(),
    plugins: (() => {
        const p = navigator.plugins;
        return JSON.stringify({length: p.length, type: p.constructor.name, items: Array.from(p).map(x => x.name).slice(0,3)});
    })(),
    languages: JSON.stringify(navigator.languages),
    platform: navigator.platform,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigator.deviceMemory,
    pwInitScripts: typeof window.__pwInitScripts,
    userAgent: navigator.userAgent,
    screen: JSON.stringify({w: screen.width, h: screen.height, availW: screen.availWidth, availH: screen.availHeight, cd: screen.colorDepth, pd: screen.pixelDepth}),
    pixelRatio: window.devicePixelRatio,
})
"""

OUT = "/tmp/kensho-measure-final"
os.makedirs(OUT, exist_ok=True)

results = {}


class _LogProxy:
    def write(self, msg: str) -> None:
        print(msg)

    def flush(self) -> None:
        pass


for acct in ["atushi16", "kudou", "zin20120731", "TankanNotes"]:
    acct_results: dict = {}
    print(f"\n{'=' * 60}")
    print(f"[MEASURE] {acct}")
    print(f"{'=' * 60}")

    ipw, browser, ctx, page = create_browser(
        account_key=acct,
        headless=True,
        proxy="",
        log=_LogProxy(),
    )

    try:
        for name, url in SITES:
            print(f"\n  [{name}] ", end="", flush=True)
            try:
                page.goto(url, timeout=45000, wait_until="domcontentloaded")
                time.sleep(3)
                screenshot = f"{OUT}/{acct}-{name}.png"
                page.screenshot(path=screenshot, full_page=True)

                js_data = page.evaluate(MEASURE_JS)
                page_text = page.evaluate("() => document.body.innerText")

                acct_results[name] = {
                    "url": page.url,
                    "title": page.title(),
                    "js": js_data,
                    "text_preview": page_text[:800] if page_text else "",
                    "screenshot": screenshot,
                }
                print(f"OK ({page.title()[:40]})")
            except Exception as e:
                err = str(e)[:120]
                print(f"NG: {err}")
                acct_results[name] = {"error": err}

        results[acct] = acct_results
    finally:
        close_browser(ipw, browser)

# レポート
report = {"summary": {}, "details": results}

# 集計
KEYS = [
    "webdriver",
    "webgl",
    "plugins",
    "languages",
    "platform",
    "hardwareConcurrency",
    "deviceMemory",
    "pwInitScripts",
    "pixelRatio",
]
for acct, r in results.items():
    by_site = {}
    for site_name, data in r.items():
        if "js" in data:
            by_site[site_name] = {k: data["js"].get(k) for k in KEYS}
    report["summary"][acct] = by_site

with open(f"{OUT}/report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n{'=' * 60}")
print(f"レポート保存: {OUT}/report.json")
print(f"スクリーンショット: {OUT}/*.png")
print(f"{'=' * 60}")

# 簡易ターミナル表示
print("\n\n=== JS Fingerprint 測定結果（要約）===")
for acct, by_site in report["summary"].items():
    print(f"\n--- {acct} ---")
    for site_name, vals in by_site.items():
        print(f"  [{site_name}]")
        for k, v in vals.items():
            print(f"    {k}: {v}")
