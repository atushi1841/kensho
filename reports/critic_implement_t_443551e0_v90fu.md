# critic v90 follow-up — Apify Store公開インデックス欠落 診断レポート (t_443551e0)

日時: 2026-09-10 20:00-21:30 JST 実測
実施者: kensho-revenue-worker

## 結論（先出し）

1. **カード本文の前提は反証**: flagshipは「Store提出忘れ」状態ではない。公開ゲートAPIフィールド（isPublic=true / notice=NONE / categories / PPE有効 / exampleRunInput / LIMITED_PERMISSIONS）は全て公開競合と同一値を実測。
2. **欠落はアカウント単位**: 匿名 `/v2/store?username=` 比較で fruitful_quintessence のみ items=0（total=71）、他3アカウント（jpmarketdata 5/81、datalab-jp 5/10、compass 5/5）は同条件でitems返る。全アクター共通のアカウントレベル属性による除外。
3. **ロゴ(pictureUrl)仮説は自ら反証した**: 匿名indexに実際に出現している no-logo アクター（jpmarketdata/uniqlo-japan-price-checker 他5件）が存在 → ロゴ欠落は除外条件ではない。残る最有力仮説は **Apify Actor Developer パートナー契約/公開オンボーディング未同意**（Store掲載は Console の "Publish on Store" 操作＝同意フロー経由のみ、openapi.jsonに該当エンドポイント無し=UI-only）。**この確認にはログイン済みブラウザが必要 → 要ユーザー**。
4. 成功指標（匿名items≥1）は本runで未達。CDP 9222はCLOSED実測（rc=7）で自動化経路なし。

## 実測ログ

### A/B再確認（v90再現＋切り分け）
| 実行 | 結果 |
|---|---|
| 匿名 `store?limit=5&username=fruitful_quintessence` | items=0, total=71（v90再現） |
| 同一params トークン時 | items=5（自分のアクター出現） |
| 匿名 `store?search=japan&username=mine` | items=0 / トークン時=20件（完全A/B） |
| brand probe（fruitful/kitamura/suruga/jackroad/dlsite）匿名 | mine=0、他ユーザー（datalab-jp x10, jpopendata x6, jpmarketdata x1…）は普通に出る |
| **アカウント別 username filter（匿名）** | **mine 0/71 ⟷ jpmarketdata 5/81, datalab-jp 5/10, compass 5/5** |

### 公開ゲート項目 diff（flagship vs 出現競合、store-entry全フィールド value-level走査）
一致: isPublic=true, notice=NONE, categories=[ECOMMERCE,AUTOMATION,DEVELOPER_TOOLS], actorPermissionLevel=LIMITED_PERMISSIONS, isSourceCodeHidden=true, PPE有効, exampleRunInputあり, taggedBuilds latest, 30d publicActorRunStats SUCCEEDED 29。
差が出たのは identity/日時/pricing詳細/stats/ **pictureUrl** のみ。
→ pictureUrl差は上記の通り no-logo 出現アクター存在で除外条件でなしと確定（71件中ロゴ無し=71、出現側42件中 no-logo=6 等の実測）。

### 参考観察（アカウント品質ゲートの候補として報告）
- `GET /v2/acts?limit=100`: 自分のアクター **72個**（カード本文「25本」はPPE部分集合。store entries total=71と整合）。
- createdAt分布: 2026-08-10に26個、08-13に14個、09-05に9個 — **短期大量プッシュ**。
- title重複: "Japan car market Prices — Listings & Market Data" x5、"Japan watches…" x4 等 — Store品質レビュー的にスパム的とみなされる余地あり（jpmarketdataは同種の量産でも掲載されているため、量産単体は説明にならない）。
- プロフィール（name/bio/avatar）設定済み。`isPaying=false`、effectivePlatformFeatures 全有効（ACTORS/PROXY等 disabledReason=null）→ プラットフォーム機能停止フラグは無し。
- actorページ・storeページ双方 HTTP 200（外部導線は直接URLで生きている）。

### API公開エンドポイント（実施内容(2)の答え）
- `/v2/openapi.json` 全paths: `publish`/store提出エンドポイント**無し**。`PUT /v2/acts/{id}` の UpdateActorRequest に isPublic/title/categories 等はあるが**Store掲載申請フラグなし**（isPublic=trueは実測で済）。→ 掲載操作は Console UI（Publishing tab → Display information[ロゴ必須記載] / Monetization / Sample output / Output schema / Permissions → **Publish on Store**）のみ。公式docs (actors/publishing/publish.md) と整合。

## 要ユーザー対応（blocked理由）

Apify Console（ログイン済みブラウザ）で https://console.apify.com/actors/mQaZFo6up4YZKepC3/publishing を開き:
1. Publishing tab のセクション未完了表示と「Publish on Store」ボタンの有無を確認（出ない場合はパートナー契約/利用規約同意プロンプトの有無を画面コピー）
2. ボタンが押せる/同意プロンプトなら同意→Publish実行
3. 実行後、検証コマンドで items≥1 なるか（なら仮説確定→他71本へ同操作横展開、criticは t_443551e0 再オープンで追踪可）
4. 全て完了済みなのに items=0 なら Apifyサポート（community@apify.com / Discord）へ「username=fruitful_quintessence の全アクターが /v2/store 匿名検索から除外されている。パートナー審査ステータスを確認したい」問い合わせ

## 申し送り（criticへ）
- Store index=0 が解けるまで外部導線（devto 9/14、t_822876d6 Reddit告知）は actor直接URL（200確認済み）へ集約で問題なし。
- v90本文「25アクター提出漏れ・UI提出実行」は誤診。次の一手はUIのPublish状態確認まで（API側は打ち手なしをopenapi全走査で証明済み）。
