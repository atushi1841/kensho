# t_1518457c verification evidence

## verification_evidence

**Task**: t_1518457c - Apify 81 actorへgithubUrl接続再実装

### 実施内容
Apify API read-back で version level gitRepoUrl の設定状況を確認し、欠落14件を修正。

### 検証コマンド
```bash
# API経由で全actor取得 + version-level gitRepoUrlチェック
python3 /tmp/apify_final_readback.py
```

### 実行結果
- total_actors: 81
- with_version_gitRepoUrl: **81/81**
- isSourceCodeHidden: True=0, False=81

### 修正内容
- mandarake-surugaya-mcp → https://github.com/atushi1841/mandarake-surugaya-mcp
- goo-net-car-scraper → https://github.com/atushi1841/goo-net-car-scraper
- tackleberry-scraper → https://github.com/atushi1841/tackleberry-scraper
- 残り11件 → https://github.com/atushi1841/kensho-actors

### 判定
完了条件「version level gitRepoUrl >= 80/81」**充足**（81/81）
isSourceCodeHidden監査も **False=81/81**（コード公開状態）