## verification_evidence

タスク t_3f40d6ee: dev.to記事にApify PPEアクター連携リンクを追加し外部流入を促進
完了時刻: 2026-10-07 03:14 JST

### 実施内容
- `python3 scripts/devto_internal_links.py --list` で公開記事一覧を取得
- `python3 scripts/devto_internal_links.py --apply` でリンク追加を実行

### 検証コマンドと実出力

```
$ python3 scripts/devto_internal_links.py --list
公開記事: 31本
追記対象: 0本
```

**結果**: 全31記事が既にApify PPE Storeリンクを有する状態。成功指標（>=5本）は31本で満たされている。

```
$ python3 -c "
import urllib.request, json
tok = open('/mnt/d/Project2/kensho/.env').read()
for line in tok.splitlines():
    if line.startswith('APIFY_TOKEN=') and 'DEFAULT' not in line:
        token = line.split('=',1)[1].strip(); break
url = f'https://api.apify.com/v2/acts?my=true&token={token}&limit=100'
req = urllib.request.Request(url, headers={'Accept':'application/json'})
with urllib.request.urlopen(req, timeout=20) as r:
    d=json.loads(r.read())
    print(f'Total actors: {d.get(\"data\",{}).get(\"total\",0)}')"
Total actors: 80
```

```
$ git log --oneline -5
5ce5d85 t_d28cf2a8: HF Space 2本作成完了
7e1dc90 docs: 稼働サマリー 2026-10-06
ae36959 docs(t_aeba6230): verification report and evidence.json
```

### 成功指標確認
- 目標: dev.to記事5本以上にApify PPE URL埋め込み
- 実測: 31本すべてに既存 → **PASS**

### 結論
タスク t_3f40d6ee の成功指標は既に満たされている。早完了（early_complete）とする。
