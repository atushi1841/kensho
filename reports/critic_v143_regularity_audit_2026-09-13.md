# critic v143 — 日跨ぎ規則性監査の追加（2026-09-13 16:2x JST）

Origin: nightly-critic 4baf143523e0 / monitor change detected (blocked 0→1)。
カード: t_32c2723a (ready, kensho-revenue-worker, idempotency-key critic-20260913-v143-REGJIT)

## 実測エビデンス（audit.jsonl 16,240行・window 9/6〜9/12・JST）

|垢|初動時刻 stdev|日次件数 mean|CV|判定|
|---|---|---|---|---|
|atushi16|13.9分|104|0.10|正規性あり（監査対象）|
|zin20120731|17.3分|97|0.23|境界（件数CVはOK・時刻が狭い）|
|kudou|44.6分|85|0.42|OK|
|chugakujuken|74.4分|100|0.22|OK|
|TankanNotes|161.3分|63|0.55|OK|

研究裏付け: research-20260913.md（3ソース一致・信頼度高）— X検出は「量より規則性」、
推奨ジッタ ±8〜22分。2000垢red-team分析で時間正規性が主要シグナル。

## 重要発見（スコープ修正の根拠）

`config.yaml:303 batch_jitter_minutes: 15` でバッチ時刻ジッタは**既実装**。
atushi16 の初動stdev13.9分は ±15分ジッタと整合 → 「ジッタ未実装」ではない。
問題なのは**監査が5項目（深夜・間隔秒・多重・過フォロー・hourly）だけで、
日跨ぎの時刻/件数分布の正規性を一切見ていない**こと＝blind spot。
よってv143は「可視化（監査項目6）」に限定し、応募ロジック・jitter値変更はスコープ外
（変更はパイプライン改修ゲート=ユーザーGO対象）。検出された垢の対策は別カードでGO提案。

## ゲート状況（同時確認）

- t_cafe0cdd (v142 scrapling): blocked=ユーザーGO(a/b/c)待ち → 16:2xに【要ユーザー対応】コメント付与。A/B・QA独立再実測ともPASS済みで、ユーザーの1行コメントのみで前進可能。park監視 9/14 14:31。
- t_829a58aa (v138 hunter計上QA, scheduled): 先行確認 — `non-api-hunter/2026-09-13_16-00-46.md` に「無料ラッパ型OSS: 1」= wrapper_freeゲート発動を実測確認。QA側で自動クローズ見込み。
- knshowオリジン502: 16:22 critic再確認でも top/twitter とも HTTP 502（4時点連続）。明日も502なら源別フェイルオーバーをv144提案化。

## 成功指標・検証（カード本文と同一）

- `python3 scripts/audit_bot_safety.py 2026-09-12` → exit 1 + 「正規性」出力（atushi16/zin検出）
- 検証コマンド: `cd /mnt/d/Project2/kensho && python3 scripts/audit_bot_safety.py 2026-09-12 | grep -c 正規性` → 1以上
- 代替案: 30日で誤検知が週2回超なら scripts/audit_regularity.py 単体へ格下げ
