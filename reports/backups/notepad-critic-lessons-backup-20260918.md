2026-09-17: KENKAKU平均 16.1件 / ConnectTimeout 8件 / apply成功率 100.0%
2026-09-18(v186-夜):
- 【要ユーザー対応】(高・継続) zin20120731 proxy:1084 egress死(9/18朝〜夜)。watchdog再起動+再アソシとも効かず「Adapter zin_AW6povo has no non-APIPA IPv4」=povo端末側。端末再起動/機内モード切替を推奨。ログイン失敗継続。
- (中) t_1593ad00(メモリcompaction)がassignee=Noneでready滞留→dispatcher永久スキップ。kensho-workerに補完割当(9/18夜)。ユーザー作成カードのassignee未設定は要注意。
- ボード=score100/ready3(t_455add05/t_d2b1ba39/t_1593ad00)/running1(t_c76075ca)/blocked0/streak0で健全。新規提案なし(既存バックログが問題を網羅)。
