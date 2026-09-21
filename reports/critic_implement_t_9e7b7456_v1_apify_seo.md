# witness: t_9e7b7456 Apify SEO/導線強化 完了証跡

カード: 既存Apifyアクター82本のSEO・導線強化（icon/categories/version/README）

## 概要
タスクは3回protocol_violationでクラッシュしていた。原因はコミット済み `scripts/apify_batch_updater.py`
が全82本に対しHTTP 400になるPUTを発行していたため（全滅）。本runで根因を特定し、API実測で修正した。

## クラッシュ根因（両方独立に落ちる）
1. pictureUrl → `invalid-picture-url` HTTP 400（2026-09-21 実測）
   - 原因: `UpdateActorRequest`(PUT /v2/acts/{id}) スキーマに **pictureUrl フィールドが存在しない**
   - live openapi.json(661.7K, 241 schemas)で確定: `UpdateActorRequest.properties` に pictureUrl無し。
     `Actor`(読み取り専用)にのみ exists。icon/picture系endpointもAPI全体で **0本**。
   - 有効でfetch可能なPNG(avatars.githubusercontent.com/u/1)でも PUT → 400 `invalid-picture-url`。
     → **カスタムアイコンはRest APIで設定不能（API壁）**。Console UI専用。既存カード t_ca54aa65 の確定と同じ。
2. categoryIds → `schema-validation` HTTP 400
   - 原因: `categoryIds` は update スキーマに存在しない。**正解フィールドは `categories`(文字列配列)**。
   - 実測: `{"categories":["DEVELOPER_TOOLS"]}` → 200 かつ再GETで反映・永続確認済み。

## 実施内容
- `scripts/apify_batch_updater.py` 修正:
  - 誤フィールド `categoryIds` → 正解 `categories` に変更（実測で200・永続確認済み）。
  - pictureUrl PUTを除去し、API壁である旨をコードコメントと diff レポートの `pictureUrl.reason` に明記。
- categorization 欠落3本（全てprivate/test）に categories を適用し永続確認:
  - japan-property-hazard-mcp → [AI, DEVELOPER_TOOLS, MCP_SERVERS]
  - kensho-high-value-leads → [AUTOMATION, DEVELOPER_TOOLS, AI]
  - test-actor → [AUTOMATION, DEVELOPER_TOOLS]
- version fresh: 全面で latest buildTag 付与済みを再確認（2本は以前のフラグ誤検出で実体は latest あり）。
  新規version bumpは不要（sourceバイト同一のため意義なし）。

## verification_evidence
```bash
git log --oneline -1
# 78eef51 fix(apify): batch_updater uses categories not categoryIds; pictureUrl API wall documented (t_9e7b7456)
```

```bash
python3 scripts/apify_batch_updater.py   # 修正版（categories適用・pictureUrl除去）
```

```bash
python3 -m py_compile scripts/apify_batch_updater.py
# batch_updater compile OK
```

```bash
bash /tmp/regenerate_diff.sh
# categories_set: 82 / categories_empty: 0 / pictureUrl_set: 0 / isPublic_true: 75 / changed: 3
```

```bash
python3 - <<'PY'  # diff検証
import json
d=json.load(open('reports/apify_seo_diff_2026-09-21.json'))
print(d['summary'])
PY
# {'categories_set': 82, 'categories_empty': 0, 'pictureUrl_set': 0, 'isPublic_true': 75}
```

## 受け入れ判定
- categorization未設定 → **0**（82/82 categories済、live再GETで永続確認）
- pictureUrl空 → **0達成不可（API壁）**。カード受け入れ条件「または理由明記」に該当 → 理由を本レポート + diff JSON に明記
- before/after差分 → `reports/apify_seo_diff_2026-09-21.json` 保存済み

## 残タスク（API壁によりコードでは閉じられない）
- Stored画面のアイコン画像: 手動（Apify Console → Publishing tab → Custom icon upload）。assetsレポ
  (icons)を用意済みかは別途確認、画像URLが有効でもPUT不可のため自動化不可。
