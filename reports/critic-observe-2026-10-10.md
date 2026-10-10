# Critic 観察レポート 2026-10-10（Glamaインデックス追跡）

## 盤面状態（sqlite 実測）
- ready=0 / todo=2 / running=1 / blocked=0 / done=20 / archived=20
- priority=backlog_reduction（loop_health.sh 判定）
- running: t_25832581（Glama登録、worker、heartbeat 1791624858、claim_expires 1791625758＝残り約17分、生存中）
- todo: t_cdb54a4f（Glamaカバレッジ拡大、worker、親=t_25832581）、t_dea751b5（HTTP 200検証、QA、親=t_25832581）
- 3カードとも **同じ scratch workspace**（/t_cdb54a4f）を参照 → WIP共有注意

## Glama インデックス状態（API/HTTP 実測・18:5x JST）
- `https://glama.ai/mcp/servers?query=author:atushi1841` の JSON-LD `itemListElement` から抽出した登録済みslug = **5本**:
  japan-minimum-wage-mcp / mandarake-surugaya-mcp / japan-fuel-price-mcp / rakuten-japan-mcp / japan-market-mcp
- GitHub 上の glama.json 存在確認（`api.github.com/.../contents/glama.json`）= **10件すべて 200**:
  kensho-sweep-mcp / japan-anime-figure-mcp / japan-jepx-mcp / japan-property-hazard-mcp / japan-food-delivery-mcp / japan-ec-mcp / kensho-kema / kensho-kclub / kensho-kaku / japan-market-data
- **差分=5本**。push完了（10:47 JST、11件追加）から **8時間以上** 経過しているにもかかわらず Glama クローラーが反映されていない。
- ダミースlug（nonexistent-slug-xyz-12345 等）も含め全slugが HTTP 200 を返すため、**HTTP 200 チェック単体では登録の有無を判別できない**（Glama は未登録slugでも200＋専用タイトルを返す）。→ t_dea751b5 の完了条件「All slugs return HTTP 200」は**偽doneの温床**。完了条件は JSON-LD での掲載確認に変更必要。

## 教訓
1. **Glama 自動インデックスのレイテンシは 8h+**。glama.json push 後は最低24h経過を待つか、再チェックは翌日とする。即時完了条件にできない。
2. **Glama の URL チェックは 200 判別不可**。登録の真伪は `?query=author:atushi1841` の JSON-LD `itemListElement` で `url` フィルタする必要がある。
3. **t_dea751b5（HTTP 200検証）の完了条件が不適切** → QA カードとして再定義必要（JSON-LD 掲載数 >=12 に変更）。

## X TOS 変更（2026-10-09 有効）— 未対応の高リスク
前回調査（job 0a52174180bd）で検出: 「公開インターフェースを通じない自動化アクセスは禁止／スクレイピングは書面許可なし禁止」。
Kensho の現行ブラウザ自動化（CDP＋プロキシ分離）がこの規約に該当する可能性が**極めて高い**。
→ 【要ユーザー対応】。自動化で解決できない（Xの規約解釈・例外申請は人間の判断）。提案ではなくユーザー判断事项。
