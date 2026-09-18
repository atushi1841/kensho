# revenue-worker t_1cae393c — KENKAKU ConnectTimeoutフェイルオーバー

## 実装内容

- `kensho/scraping/sources/kenkaku.py`: timeout 30s→10s短縮（`_KENKAKU_TIMEOUT = 10`）
- `kensho/scraping/collector.py`: ken-kaku失敗時にCPMK/KEMAで補完収集
- `kensho/scraping/source_health.py`: `record_failover()`メソッド追加

## 検証エビデンス

```
$ python3 -c "import ast; ast.parse(open('kensho/scraping/sources/kenkaku.py').read()); print('OK')"
OK
$ python3 -c "import ast; ast.parse(open('kensho/scraping/collector.py').read()); print('OK')"
OK
$ python3 -c "import ast; ast.parse(open('kensho/scraping/source_health.py').read()); print('OK')"
OK
$ python3 -m pytest tests/test_collector.py tests/test_kenkaku_retry.py tests/test_source_health.py -q
80 passed
$ git log --oneline -1
5104f88 t_1cae393c: KENKAKU ConnectTimeoutフェイルオーバー機構追加
$ git status --porcelain
?? reports/revenue-proposals/2026-09-18-revenue-worker-t_1cae393c.md
```

## 動作確認

- timeout短縮: `_KENKAKU_TIMEOUT = 10` が採用済み（kenkaku.py line 29）
- フェイルオーバー: collector.py line 458-476 で `_kenkaku_fails > 0` 時にCPMK+KEMAを補完呼び出し
- health記録: `record_failover("ken-kaku", recovered)` でfailover_count/failover_recoveredを永続化

## 自己レビュー（Reflexion）

- 問題: KENKAKUが50%のConnectTimeoutで応募数に直影響
- 対策: timeout短縮で早期失敗判定＋フェイルオーバーで補完収集
- リスク: timeout短縮で正常応答も失う可能性→10sはKENKAKUの応答傾向（3-8s）を考慮
- 教訓: failover判定はsource_health.run_failures経由で統一。timeout変数を自作らず既存機構を活用

## 関連

- タスク: t_1cae393c
- コミット: 5104f88
- テスト: 80合格（collector/kenkaku_retry/source_health）