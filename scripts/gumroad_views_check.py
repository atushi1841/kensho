#!/usr/bin/env python3
"""
Gumroad商品ページのviewsをスクレイピングで取得
公開ページからviews数を抽出
"""
import sys
import re
import requests
from bs4 import BeautifulSoup
import os

# URLは環境変数または引数で指定可能にする
GUMROAD_URL = os.environ.get('GUMROAD_URL', "https://atushi5.gumroad.com/l/agyhq")

def get_views() -> int:
    """Gumroad商品ページからviews数を取得"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(GUMROAD_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Gumroadのviews要素を探す（複数パターン対応）
        # パターン1: data-views属性
        for elem in soup.find_all(attrs={"data-views": True}):
            views = elem.get('data-views')
            if views and views.isdigit():
                return int(views)
        
        # パターン2: テキスト内の "X views" 形式
        text = soup.get_text()
        match = re.search(r'(\d[\d,]*)\s*views?', text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(',', ''))
        
        # パターン3: metaタグ
        meta = soup.find('meta', property='og:description')
        if meta and meta.get('content'):
            match = re.search(r'(\d[\d,]*)\s*views?', meta['content'], re.IGNORECASE)
            if match:
                return int(match.group(1).replace(',', ''))
        
        return -1  # 取得失敗
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return -1

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=30, help='期間（日数）- 現在は現在値のみ取得')
    parser.add_argument('--url', type=str, help='Gumroad商品URL（省略時は環境変数GUMROAD_URL）')
    args = parser.parse_args()
    
    if args.url:
        os.environ['GUMROAD_URL'] = args.url
    
    views = get_views()
    if views >= 0:
        print(f"Gumroad views: {views}")
        sys.exit(0)
    else:
        print("Failed to fetch views (URL may not be published yet)", file=sys.stderr)
        sys.exit(1)