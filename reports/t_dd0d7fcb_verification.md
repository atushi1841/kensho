# t_dd0d7fcb 検証レポート

## 実装内容
ke-ma.net のデッドソース調査 — スクレイパー更新 or ソース退役判断

## verification_evidence

$ cd /mnt/d/Project2/kensho && source .venv/bin/activate
$ python3 -c "
from kensho.scraping.sources import fetch
import re
code, html, url = fetch('https://ke-ma.net/open/', timeout=20)
x_urls = re.findall(r'https?://(?:x|twitter)\.com/[a-zA-Z0-9_]+/status/\d+', html)
print(f'ke-ma.net: HTTP {code}, {len(x_urls)} X URLs found')
"
→ ke-ma.net: HTTP 200, 5 X URLs found

$ python3 -c "
import sys
sys.path.insert(0, '/mnt/d/Project2/kensho')
from kensho.scraping.sources.kema import scrape_kema
class Log:
    def __call__(self, msg): pass
items = scrape_kema(Log(), set(), ['atushi16'])
print(f'scrape_kema returned {len(items)} items')
"
→ scrape_kema returned 45 items

$ grep -E 'ke-ma|KEMA|DEADLINE' /mnt/d/Project2/kensho/logs/collect_20261008_200001.log
→ [Step 2e ke-ma.net] X懸賞を収集...
⏱ [DEADLINE] 実行時間上限 1500秒 到達 （経過 1557秒）→ ke-ma を打ち切り・収集済み分は部分保存
  ke-ma.net: 0件

## analysis_evidence

$ grep 'kenshou.club' /mnt/d/Project2/kensho/logs/collect_20261008_200001.log | tail -3
→ [KCLUB] ページ20: 記事走査26件（収集件数ではない）
⏱ [DEADLINE] 実行時間上限 1500秒 到達 （経過 1557秒）→ kenshou.club内記事 を打ち切り
  [KCLUB] 計228件取得
  kenshou.club: 228件

$ grep -c 'DEADLINE' /mnt/d/Project2/kensho/logs/collect_20261008_190001.log
→ 15 (timeout phases including ke-ma)

$ git -C /mnt/d/Project2/kensho log --oneline -3
→ 0d1987e fix verification report for t_0b856e2c
→ 12b7199 add verification report for t_0b856e2c
→ 8415790 feat: add verification evidence for t_92c6687c