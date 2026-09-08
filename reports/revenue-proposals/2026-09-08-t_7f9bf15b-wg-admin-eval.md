# 検証記録: Wg-admin 非API収益評価（t_7f9bf15b）

- 対象: https://github.com/logimaxx/wg-admin / HN: https://news.ycombinator.com/item?id=49600269
- 判断: 却下（実装対象外）— 無料 MIT OSS の WireGuard 管理 Web UI で公開データ・API・DS 皆無、収益モデルゼロ、wg-easy 競合＋HN セキュリティ却下圧、既存 Kensho scraping/LLM 資産再利用不可。
- 詳細は添付 evaluation_report.md。

## verification_evidence

```
$ curl -s https://api.github.com/repos/logimaxx/wg-admin | grep -E 'stargazers_count|forks_count|open_issues_count|license'
  "stargazers_count": 21, "forks_count": 0, "open_issues_count": 0, "license": MIT
$ curl -s https://hacker-news.firebaseio.com/v0/item/49600269.json
  {"by":"vsergione","score":27,"descendants":6,"title":"Show HN: Wg-admin – web UI for an existing WireGuard host"}
$ curl -s https://hacker-news.firebaseio.com/v0/item/49603503.json
  jchook: "Seems like high-risk and low-reward for your network security... exposing the castle's master key to a python web app"
$ curl -s https://hacker-news.firebaseio.com/v0/item/49604241.json
  russelg: "Any notable differences from wg-easy?"
$ curl -s https://raw.githubusercontent.com/logimaxx/wg-admin/main/README.md
  MIT License, binds 127.0.0.1, no pricing / plans / subscription
```

冒頭から証跡セクション末尾まで言及 task_id は t_7f9bf15b（本タスク）のみ。
