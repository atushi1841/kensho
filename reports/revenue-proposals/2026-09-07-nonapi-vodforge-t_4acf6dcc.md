# VODForge 非API収益評価 — 検証エビデンス (t_4acf6dcc)

対象: https://getvodforge.com / HN item 49590354 (score 37, コメント 12)
カテゴリ: アプリ/ツール（ネイティブデスクトップ OSS ツール）
判断: 却下（実装対象外）

## verification_evidence

$ curl -sL -A "Mozilla/5.0" -o /tmp/vodforge_root.html -w "HTTP %{http_code} size %{size_download}\n" https://getvodforge.com/
   → HTTP 200 size 33295 — ランディングはデスクトップダウンロード導線のみ、pricing なし

$ curl -sL -A "Mozilla/5.0" -o /tmp/vodforge_robots.txt -w "HTTP %{http_code}\n" https://getvodforge.com/robots.txt
   → HTTP 200 / User-agent: * Allow: / — Challenge でない

$ curl -sL -A "Mozilla/5.0" -o /tmp/vodforge_sitemap.xml -w "HTTP %{http_code}\n" https://getvodforge.com/sitemap.xml
   → HTTP 200 — sitemap は / /cloud/ /privacy/ /changelog/ /vs/* /youtube-to-mp4/ のみ

grep -oE '<loc>[^<]*</loc>' /tmp/vodforge_sitemap.xml
   → Web API・pricing・データエンドポイントの URL は存在しない

$ curl -sL -A "Mozilla/5.0" -o /tmp/hn.html -w "HTTP %{http_code}\n" https://news.ycombinator.com/item?id=49590354
   → HTTP 200 — score 37, コメント 12 件すべて技術Q&A（yt-dlp 内包 / MP3再エンコード提案 / ランダム遅延要望）

結論: 対象は MIT 無料のネイティブデスクトップ yt-dlp+ffmpeg ラッパー。収集対象データ・Web API・pricing 導線なし。
VODForge Cloud は「計画中の有料サービス」で未ローンチ（無料興味リストのみ）。自動化ワードは app 内蔵機能記述（誤検出）。
skill の却下パターン（ネイティブアプリ + MIT OSS で収集データ・有料化余地なし）に該当。実装タスクへの切り出しは行わない。
