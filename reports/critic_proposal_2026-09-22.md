# critic 2026-09-22: knshow 502 partial degradation へのページ単位リトライ適用

[status] open(提案) / 優先度: 中 / リスク: 低(収集ソース限定。応募ロジックには触れない)

## エビデンス(実測 2026-09-22 09:20)

1. `[HEALTH] 部分劣化（主要源timeout）: ['knshow']` が連日発生:
   - 9/21: 全14セッション中4回（0300/0900/1100/1300）
   - 9/20: 同4回
   - 9/13(0300)〜9/22まで断続継続。knshowソースのみ偏在。
2. 直進原因: `Fetched (502) <GET https://www.knshow.com/twitter>` がREADMEに表示され、
   その回は knshow=0件 になる（9/21 1100: knshow 0件 / 9/22 0300: knshow 0件）。
3. knshow.py 現状: `with httpx.Client(..., timeout=15)` の単発fetchのみ。
   ページ単位リトライ・バックオフが未実装（他ソース kenkaku は v144 で実装済み、
   _KENKAKU_MAX_RETRIES=5・指数バックオフ 3/6/10s キャップ）。
4. 全収集量への影響は軽微（他ソースがカバーし計459-568件は維持）だが、
   主要源knshowが毎日0件になる回があり、HEALTH警告が常時点灯する。

## 提案

knshow.py に kenkaku v144 と同型のページ単位リトライを移植する。
- HTTP 5xx/ConnectTimeout 時、指数バックオフで最大3回リトライ（3/6/s キャップ）。
- 最終失敗時のみそのページをスキップ（GET 全体失敗はしない）※既存と同じ。
- 502はknshow側サーバ一時エラーのため、リトライで相当数が回復できる見込み。

## 成功指標(数値)

- 導入後7日間で「knshow=0件」になるセッション数を施行前（9/20-22: 9/21時点4回）から
  半減以上（<=2回/7日）にする。
- `grep -c '部分劣化.*knshow'` が導入前比で減少。

## 検証コマンド(1行)

```
cd /mnt/d/Project2/kensho && pytest -q tests/test_kenkaku_retry.py -q 2>/dev/null; grep -c '部分劣化.*knshow' logs/collect_$(ls -t logs/collect_*.log | head -1 | sed 's/.*collect_//;s/.log//').log
```

## 失敗時の代替案

- リトライ移植が安全でない/複雑なら、knshow 502 を「部分劣化」HEALTH警告から除外して
  静観（全量に影響なし・他ソースがカバー）。リトライは後日再提案。

## 参考

- kenkaku v144 実装: kensho/scraping/sources/kenkaku.py (`_KENKAKU_MAX_RETRIES`,
  指数バックオフ 3/6/10s)
- 観察: reports/critic-observe-2026-09-22.md
