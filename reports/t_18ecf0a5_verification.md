# t_18ecf0a5 検証レポート — knshow 502部分劣化対策

## 概要
critic 2026-09-22 提案: knshow 一覧ページ/リダイレクト解決が単発 fetch(timeout=15) で
502 を通し、knshow=0 セッションを生んでいた。kenkaku v144 のページ単位指数バックオフ
リトライを移植して解決を狙う。成功指標: knshow=0 セッションを7日間で半減。

## 実装内容（commit 0a6b851, push済み）
- `kensho/scraping/sources/knshow.py`: `fetch_listing_with_retry` 新設
  （3アテンプト・base 3s→3,6→10sキャップ・HTTP5xx(502含む)/ネットワーク例外のみリトライ）
  ＋ `resolve_redirect` にネットワーク例外の指数バックオフリトライ追加。
- `kensho/scraping/collector.py`: knshow 一覧ページの単発 fetch を `fetch_listing_with_retry`
  に差し替え。
- `kensho/scraping/sources/__init__.py`: `fetch_listing_with_retry` を export。
- `tests/test_knshow_retry.py`: リトライ定数 / 502→200 / 全502打ち切り /
  非5xx即skip / ネットワーク例外→200 / リトライログ出力 / resolve_redirect 成功・
  再raise・初回成功 を mock で検証（network/sleep全mock、AGENTS.mdルール準拠）。

## 検証エビデンス（実測のみ）
1. テスト全件通過:
   ```
   $ python -m pytest tests/test_knshow_retry.py tests/test_kenkaku_retry.py tests/test_collector.py -q
   => 78 passed in 17.81s
   ```
2. 全 fetch 経路が3値タプル `(code, html, final_url)` を返すことを確認（common.fetch,
   scrapling_fetch, proxied_fetch）。fetch_listing_with_retry のシグネチャ
   `Callable[..., tuple[int,str,str]]` と整合。
3. _do_fetch（scrapling_fetch / proxied_fetch / fetch）が fetch_listing_with_retry に
   渡せることを collector.py L252-259 で確認。
4. push 反映:
   ```
   $ git push origin main
   => 4107349..0a6b851  main -> main
   ```

## 自己レビュー（Reflexion）
{"what_was_done":"knshow 502部分劣化対策(kns ページリトライ移植)を検証・コミット0a6b851・push済み。","what_went_well":["先行クラッシュランの未コミット実装を再利用し、テスト78件通過を実測で確認した","blockedタスクをunblock→claim→検証→コミット→pushまで完走した","リトライはHTTP5xx/ネットワーク例外のみ、404等は即skipで無限ループなしをテストで担保"],"what_could_improve":["7日間の実データでのknshow=0セッション半減はまだ未実測(時間経過待ち)","index.lockクラッシュ残骸の後始末に一手間かかった"],"mistakes_or_risks":["fetch_listing_with_retryは初期試行+リトライ2回=計3アテンプトで、最大待機時間(3+6)+各タイムアウト15s×3で最悪~60s/ページ。収集cronの時間枠に影響しないか今後の監視で要確認"],"learned":"先行runがクラッシュしても実装は残っている。unblock→claim→検証→コミットの順で再利用できる","confidence":9,"verification_evidence":"pytest 78 passed / git push 4107349..0a6b851 実測"}
