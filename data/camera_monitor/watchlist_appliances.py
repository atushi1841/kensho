#!/usr/bin/env python3
"""Watchlist: used home appliances & digital products for margin monitoring.

Extends the camera watchlist pattern to game consoles, laptops, and premium
audio gear. matchTokens: every token must appear as an EXACT title token
(NFKC-lowered) in BOTH the Yahoo candidate and the SuRUGA reference.
"""

WATCHLIST = [
    # === Game Consoles ===
    {"model": "PlayStation 5 デジタル・エディション", "keyword": "PS5 デジタルエディション 本体",
     "surugaKeyword": "PS5 デジタルエディション", "matchTokens": ["playstation", "5", "digital"], "brand": "sony"},
    {"model": "PlayStation 5 ディスク・エディション", "keyword": "PS5 ディスクエディション 本体",
     "surugaKeyword": "PS5 ディスクエディション", "matchTokens": ["playstation", "5", "disc"], "brand": "sony"},
    {"model": "Nintendo Switch 有機EL", "keyword": "Nintendo Switch 有機EL モデル",
     "surugaKeyword": "Nintendo Switch 有機EL", "matchTokens": ["nintendo", "switch", "oled"], "brand": "nintendo"},
    {"model": "Nintendo Switch (通常版)", "keyword": "Nintendo Switch 本体",
     "surugaKeyword": "Nintendo Switch", "matchTokens": ["nintendo", "switch"], "brand": "nintendo"},
    {"model": "Steam Deck", "keyword": "Steam Deck 本体",
     "surugaKeyword": "Steam Deck", "matchTokens": ["steam", "deck"], "brand": "valve"},

    # === Laptops ===
    {"model": "MacBook Pro 14 M3 Pro", "keyword": "MacBook Pro 14 M3 Pro",
     "surugaKeyword": "MacBook Pro 14 M3 Pro", "matchTokens": ["macbook", "pro", "14", "m3"], "brand": "apple"},
    {"model": "MacBook Pro 16 M3 Max", "keyword": "MacBook Pro 16 M3 Max",
     "surugaKeyword": "MacBook Pro 16 M3 Max", "matchTokens": ["macbook", "pro", "16", "m3", "max"], "brand": "apple"},
    {"model": "MacBook Air 15 M2", "keyword": "MacBook Air 15 M2",
     "surugaKeyword": "MacBook Air 15 M2", "matchTokens": ["macbook", "air", "15", "m2"], "brand": "apple"},
    {"model": "Surface Pro 9", "keyword": "Surface Pro 9",
     "surugaKeyword": "Surface Pro 9", "matchTokens": ["surface", "pro", "9"], "brand": "microsoft"},

    # === Premium Audio ===
    {"model": "Sony WH-1000XM5", "keyword": "WH-1000XM5 ヘッドホン",
     "surugaKeyword": "WH-1000XM5", "matchTokens": ["wh", "1000xm5"], "brand": "sony"},
    {"model": "Sony WF-1000XM4", "keyword": "WF-1000XM4 イヤホン",
     "surugaKeyword": "WF-1000XM4", "matchTokens": ["wf", "1000xm4"], "brand": "sony"},
    {"model": "Apple AirPods Pro (2nd gen)", "keyword": "AirPods Pro 第2世代",
     "surugaKeyword": "AirPods Pro 第2世代", "matchTokens": ["airpods", "pro", "2"], "brand": "apple"},
]