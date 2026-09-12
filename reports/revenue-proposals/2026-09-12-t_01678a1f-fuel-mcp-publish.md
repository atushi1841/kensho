# t_01678a1f — 5th MCP「japan-fuel-price-mcp」公開完了 (2026-09-12)

## 結論
資源エネルギー庁 公式XLSX（給油所小売価格調査）をMCP化した **japan-fuel-price-mcp を Apify Store に公開**。
公開→ストア reachable→公開MCPエンドポイント経由で実データ取得まで全リンク実測。

- Actor: `RdCHlXHphoLsWnyhh` / name=japan-fuel-price-mcp
- isPublic = **True**（公開前 False）
- Store: https://apify.com/fruitful_quintessence/japan-fuel-price-mcp （HTTP 200）
- Standby MCP: https://fruitful-quintessence--japan-fuel-price-mcp.apify.actor/mcp

## 実施内容
コード・ビルド・PPE pricing は前回 run（#413/#414、90/90枯渇でblocked化）で既に push・build 済みだった。
今回 worker が対応したのは **公開の詰まり解除** の1点。

### 真因特定（詰まり=HTTP 403 cannot-publish-actor）
既知良好な japan-market-mcp（公開済み・600run）と全フィールド差分を取り、決定的な差を1つに絞った:
- market: `actorStandby = {isEnabled:true, tenancy:SINGLE_TENANT, ...}`
- fuel: `actorStandby = None` ← **MCP/Standby actor は standby設定が無いと公開を弾かれる**

（当初仮説の totalRuns=0・categories=MCP_SERVERS・README有無は、isPublic単独PUTでも403、
DEVELOPER_TOOLSでも403、marketもreadme=Noneで公開済み、なので却下）

### 修正
APIで actorStandby を market と同じ値で設定（HTTP 200）→ 即 isPublic=true PUT 成功。

```bash
curl -X PUT .../acts/RdCHlXHphoLsWnyhh \
  -d '{"actorStandby":{"isEnabled":true,"tenancy":"SINGLE_TENANT","maxRequestsPerActorRun":10,
       "desiredRequestsPerActorRun":3,"idleTimeoutSecs":300,"build":"latest","memoryMbytes":1024,
       "shouldPassActorInput":false,"disableStandbyFieldsOverride":false}}'
curl -X PUT .../acts/RdCHlXHphoLsWnyhh -d '{"isPublic":true}'
```

## 検証エビデンス（全て実測）
- ビルド: `K7qOLeEcVYEi081cR` SUCCEEDED（0.1.4、git dce8d3e）
- ストアページ: HTTP 200
- 公開 standby /mcp: 未認証=401（正常な保護）、Bearer=initialize握手成功
- MCP initialize: serverInfo=japan-fuel-price-mcp v3.4.7、session-id 発行
- tools/list: 5ツール = get_latest_fuel_price / get_fuel_price_history / cheapest_prefectures / national_fuel_trend / list_fuel_regions
- tools/call get_latest_fuel_price(東京, regular):
  `東京 (tokyo) — レギュラー 169.3 JPY/liter (survey 2026-09-07), 前回169.6, WoW -0.3, ガソリン税28.7円` ← 実データ返却
- PPE pricing 設定済み（apify-actor-start 0.00005 + 各ツール 0.001）
- git: fuel repo ワーキングツリー clean（コード差分は dce8d3e まで push 済み、master追従）

## 教訓（notepad 反映）
MCP/Standby actor を Apify API 経由で新規公開する際は、`isPublic=true` に先立って **`actorStandby`（isEnabled:true等）を必ず設定する**。未設定だと 403 cannot-publish-actor で、カテゴリ/README/run数では解消しない。market-mcp などの公開済み同型 actor と `actorStandby` フィールドを突きjust合わせるのが最短。

```json
{"self_review":{"what_was_done":"japan-fuel-price-mcpをApify Storeに公開。詰まり(403 cannot-publish-actor)の真因をmarket-mcpとの全フィールド差分でactorStandby未設定と特定し、API設定後isPublic=true成功。公開standby MCPでtools/list5件+tools/call実データ(東京レギュラー169.3円)まで実測。","what_well":[],"what_went_well":["推測せず既知良好actorとのフィールド差分で真因を1点に絞った","公開後の実データ応答まで検証しdone根拠とした"],"what_could_improve":["前runが90/90枯渇で詰まった箇所(公開)を、バーンアウト防止ルール通りgit/Board状態確認後に即着手できると判断した","初回実行でstandbyがTIMED-OUT(空input)になったがこれは想定内(MCPは入力不要)、publish可否とは無関係と即見切り"],"mistakes_or_risks":["空inputのstandby runを先に回してtotalRuns=0が原因か試したが的外れ(即却下、無駄1回)。先にフィールド差分を見るべきだった"],"learned":"MCP/Standby actorのApify公開はactorStandby設定が前提条件。未設定だと403 cannot-publish-actorでカテゴリ・README・run数では解消しない。","confidence":9,"verification_evidence":"build K7qOLeEcVYEi081cR SUCCEEDED / store HTTP200 / standby /mcp initialize成功+tools/list 5件+get_latest_fuel_price(東京)=169.3円(2026-09-07)実データ返却 / git clean dce8d3e"}}
```
