# Kensho コード改善提案（2026-09-01 / Ralph loop 静的解析・コードレビュー）

全テスト（249 passed / 4 skipped）をパスした状態を維持したまま、静的解析・コードレビュー
（data-flow-audit + requesting-code-review の観点）で特定した改善候補を列挙する。
優先度 = 重要度 × 今すぐ直す価値。コスト = 実装工数の相対目安。リスク = 導入時の副作用の大きさ。

※ 本タスクは「改善提案の生成」が主目的のため、コード変更は行っていない（変更不要の提案1件、
  他は要ユーザー判断/別タスクでの実装を想定）。変更する場合は必ず pytest 249件 + mypy strict を再実行する。

---

## 提案1（優先度: 高）: 壊れた遅延import — account_discovery の `--search` 機能が必ず失敗する

- ファイル: `kensho/scraping/account_discovery.py`
- 行: 84（`from kensho.tools.web_search import web_search`）
- 理由: `kensho/tools/` 以下に `web_search` モジュールが存在しない（実在: health_check, daily_pipeline_report, dedup_collected, hindsight_guard, migrate_keyword_flag, kensho_code, aider_launcher）。
  import が関数 `search_new_accounts()` の**内部**にある遅延importのため、`check_dms` 等の起動時は通るが、
  CLI `python -m kensho.scraping.account_discovery --search` や `discover_accounts(search=True)` を呼ぶと
  実行時に必ず `ModuleNotFoundError: No module named 'kensho.tools.web_search'` で落ちる。
  実データでも確認済み: `kensho/tools/` に web_search.py は不在。静的解析上も `web_search` の定義・呼び出しは
  このファイル内 (84, 100, 136行) のみで、外部に実装がない。
- 実装案:
  - 案A（推奨）: `search_new_accounts()` 冒頭に存在チェックを入れ、モジュールが無い場合は警告ログ＋空リストを返す
    ```python
    try:
        from kensho.tools.web_search import web_search
    except ImportError:
        print("[Discovery] kensho.tools.web_search が未実装のため Web検索をスキップ")
        return []
    ```
  - 案B: `kensho/tools/web_search.py` を本実装する（外部検索API依存が必要なら config にキー追加 → 新規依存になるため要検討）
  - 案C: 壊れた機能として `search=False` デフォルト維持＋CLI の `--search` を未実装警告に置換
- コスト: 低（案A: 数行）。リスク: 極低（失敗時フォールバックなので既存動作を壊さない）。
- 検証: `getattr`/try-import のみで list リテラル/df には触れない。

---

## 提案2（優先度: 中）: configキャッシュのTTL非一致性 — scorer が config.yaml 変更を反映しない

- ファイル: `kensho/scraping/scorer.py`
- 行: 18 (`_CONFIG_CACHE`), 21-33 (`_load_config`)
- 理由: `api_actions.py` (25-37行) は config を **30秒TTL** で再読込するが、`scorer._load_config()` は
  `_CONFIG_CACHE` を**一度読んだらプロセス生存中ずっと保持**する。長寿命の worker / 常駐コレクタでは、
  config.yaml の `prize_scoring`（jpy_patterns, priority_multipliers 等）を変更しても、
  プロセス再起動まで **変更が一切反映されない**。同じ "config キャッシュ" 概念がファイル間で
  セマンティクス衝突（TTLあり vs なし）している ── data-flow-audit の「同一概念の異なる命名/振る舞い」パターン。
- 実装案: api_actions.py と同様のタイムスタンプベースTTLを適用
  ```python
  _CONFIG_CACHE: dict[str, Any] | None = None
  _CONFIG_CACHE_AT: float = 0.0
  _CONFIG_TTL: float = 30.0
  def _load_config() -> dict[str, Any]:
      global _CONFIG_CACHE, _CONFIG_CACHE_AT
      now = time.time()
      if _CONFIG_CACHE is not None and now - _CONFIG_CACHE_AT < _CONFIG_TTL:
          return _CONFIG_CACHE
      ... # 従来の読込ロジック
      _CONFIG_CACHE_AT = now
      return _CONFIG_CACHE
  ```
- コスト: 低（+3行）。リスク: 低（TTL 追加で読込頻度が僅かに増えるのみ。テスト `test_collector` に影響なし）。
- 検証: mypy strict + pytest。任意で `test_scorer_config_ttl` を `test_collector.py` 相当に追加。

---

## 提案3（優先度: 中）: `_load_audit_done_set` が増大する audit.jsonl を毎セッション全件スキャン

- ファイル: `kensho/application/applier.py`
- 行: 158-214（`_load_audit_done_set`）、呼び出し元 834
- 理由: この関数は当日JST分の成功 RT/follow/like target を構築するため `data/audit.jsonl` を**先頭から全行読む**。
  実データ確認: audit.jsonl 現在 **10,955 行 / 約3.9MB**（追記専用・増加の一途）。各アカウントの応募セッション
  開始ごと（垢数×バッチ数）に毎回フルスキャンするため、ログが増えるほど **O(N) で劣化**する。
  さらに当日判定後も `len(ts)<10 or not ts.startswith("20")` 等で1行ずつ文字列処理する。
- 実装案:
  - 案A: ファイルを**末尾から逆読み**（`reversed(open(...))` 相当/ バイトオフセット seek）し、当日以前の
    タイムスタンプ行で打ち切る。当日は最新側に集中するため、対象行数が劇的に減る。
  - 案B: `status="success" and decision="allow" and account==アカウント` の行だけ先に集計し、当日の
    target セットに変換する。現ロジックを維持しつつ対象だけ絞る。
  - 案C（中長期）: audit の末尾に「当日インデックス」を別ファイルに保持、または `data/` に
    日次サマリ JSON を生成し、スキャン対象をその1ファイルに限定。
- コスト: 中（案A: seek/reversed 実装で +20行程度）。リスク: 中（読み込みロジック変更が重複防止の
  判定漏れを生むと再アクション＝BOT検出リスク）。**必ず pytest（特に test_applier の重複防止系）+ 実 deal で当日集合の一致を確認**。
- 検証: スキャン件数 vs 従来フルスキャンで、生成される rt_done/follow_done/like_done が同一であること。

---

## 提案4（優先度: 中）: `state.py` の `item["detail_url"]` 直接indexing → KeyError でマージ全体が破棄される

- ファイル: `kensho/application/state.py`
- 行: 77（`current_map = {item["detail_url"]: item for item in current_items}`）、85-86
- 理由: `save_collected_safe` は他プロセス（並列アカウント）の変更をマージする重要処理だが、`item["detail_url"]`
  を **.get() でなく直接 indexing** している。もし collected.json の既存エントリに `detail_url` が欠落した
  不正データが1件でも混入すると **KeyError → except (132行) がそれを握って print のみ** → マージ処理全体が
  スキップ → `data`（本プロセスが保持するメモリ版）がそのまま `safe_save_json` で上書き保存され、
  **他垢が書き込んだ `applied` 日付が失われる**（= 再応募/BOT検出リスク）。現状収集ソースは全員 detail_url を
  セットするが、外部ツール編集や過去データで欠落が絶対にないとは言い切れない。`.get()` で防御するだけで
  「1件の不正が全垢の状態を壊す」事態を防げる。
- 実装案:
  ```python
  current_map = {item.get("detail_url", i): item for i, item in enumerate(current_items)}
  ```
  （キー衝突を避けるため、detail_url 欠落時は index 文字列にフォールバック）
  - 同パターン `collector.py:385`（`{item["detail_url"]: item for item in existing_collected}`）にも同様の防御を推奨。
- コスト: 低（数行）。リスク: 低（.get 追加は正常系の振る舞いを変えない）。
- 検証: pytest（test_backup / test_applier の save merge 系）+ 不正データ注入のユニットテスト追加を推奨。

---

## 提案5（優先度: 高 = テスト品質）: 当選検出・通知・プロキシ監視系がカバレッジ0%

- ファイル: `kensho/scraping/dm_monitor.py`, `kensho/utils/notify.py`, `kensho/utils/dashboard.py`,
  `kensho/utils/check_proxies.py`, `kensho/application/follow_state_manager.py`（等）
- 理由（pytest 実行時のカバレッジ報告より）:
  - `dm_monitor.py` 155行 **0%** — 当選DM検出という「懸賞収益の回収」を担う最重要機能にテストなし。
    当選キーワード判定（`_WIN_KEYWORDS` 部分一致）の誤検知/見逃しを検証不能。
  - `notify.py` 60行 **0%** — 通知送信（Telegram）の event フィルタロジックを検証不能。
  - `dashboard.py` 175行 **0%**、`check_proxies.py` 142行 **0%** — 監視・診断系。
  - 全体で `TOTAL 6922行 / 5178未到達 (25%)`。収集・応募コア（collector 13%, scorer 13%）もまだ薄い。
  これらの関数は純粋ロジック（文字列・日付・キーワード判定）で Network 依存を mock しやすいため、
  ユニットテスト追加コストが低いわりに回帰防止価値が高い。
- 実装案: `tests/test_dm_monitor.py`, `tests/test_notify.py` を追加し、キーワード部分一致・URL正規化・
  eventフィルタを mock（urlopen, page を monkeypatch）で網羅。実行は tmp_path で。
- コスト: 中（2ファイル・各10-20テスト）。リスク: 低〜中（テスト追加のみ、プロダクションコード非変更で
  要件「既存機能を壊さない」を満たす）。
- 検証: `pytest tests/ -q` で 249+新規が全パス、mypy strict 0 error。

---

## 参考: 実データ確認メモ（改善項目の裏付け）

- `pytest tests/ -q` → **249 passed, 4 skipped**（exit 0）。現状の全テスト維持を確認済み。
- カバレッジ: 全体 25%到達（6922行中5178行未到達）。0%実ファイル: account_discovery, dm_monitor, check_proxies, dashboard, notify。
- `data/audit.jsonl`: 10,955行 / 約3.9MB（追記専用・増加継続）。
- `kensho/tools/` 配下に `web_search.py` は存在せず、提案1の import 先不在を確認。
- 変更領域は本ファイル（`kensho/IMPROVEMENTS.md`）のみで、`config.yaml` / `data/` は非変更。
