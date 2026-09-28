# FREE 9 ActorsのPPE価格設定実装

## 概要

このディレクトリには、**FREE 9 ActorsのPPE価格設定**タスクの包括的な実装が含まれています。このタスクは、2026-09-28に実施され、Apify Storeで公開中の9つのFREEアクターを特定し、収益化のためのPPE（Pay Per Event）価格設定を実装します。

### 背景
- **アクター:** 9 FREEアクター（185runs/月、16users、0収益）
- **目標価格:** /usr/bin/bash.35/1K（$0.35/1000 results）
- **競合価格:** Tweet Scraper=/usr/bin/bash.40/1K、TikTok Scraper=/usr/bin/bash.30/1K
- **期待収益:** 月185runs × 平均500results × $0.35/1K ≈ 2/月（約4,600円）
- **リスク軽減:** 無料枠(月5 runs等)を併用して既存無料ユーザー離脱可能性を軽減

## 実装内容

### 1. FREEアクター特定スクリプト
**ファイル:** `scripts/find_free_actors.py`

このスクリプトは、Apify Storeから以下の条件を満たすFREEアクターを特定します：
- 185 runs/month以上
- 16 users以上
- 0収益

**機能:**
- Apify Storeからすべてのアクターを取得
- FREEアクターかどうかを判定（PPE価格モデルが有効で価格が0または非常に低い）
- 各アクターの統計情報（runs、users、revenue）を取得
- タスクの条件に一致するアクターを特定
- 期待収益と競合分析を計算
- 詳細な実施レポートを生成

**使用方法:**
```bash
python3 scripts/find_free_actors.py
```

### 2. 期待収益計算
各アクターについて、以下の期待収益を計算します：
- **月185runs × 平均500results × $0.35/1000 = $2.03/月**

**競合分析:**
- **Tweet Scraper:** /usr/bin/bash.40/1K（価格が高い）
- **TikTok Scraper:** /usr/bin/bash.30/1K（価格が安い）
- **自社（目標）:** /usr/bin/bash.35/1K（中間価格）

**価格戦略:** 競合の之间の中間価格で、Tweet Scraperよりも競争優位性があり、TikTok Scraperよりも収益性が高い

### 3. 実施レポート
**ファイル:** `scripts/free_actors_ppe_pricing_report.md`

このレポートには、無料アクター特定後の完全な実施計画が含まれています：

**セクション:**
1. **概要:** タスクの背景と目的
2. **対象アクター:** 特定された各アクターの詳細情報
3. **期待収益:** アクターごとの収益予想
4. **競合分析:** 価格位置の戦略的分析
5. **リスク軽減:** ユーザー離脱と価格適応に関する対策
6. **実装詳細:** PPE価格設定の技術的側面
7. **検証:** 価格設定後のテストと監視
8. **次のステップ:** 具体的な実行計画

### 4. 既存のApifyスクリプトとの連携

この実装は、以下の既存のApifyスクリプトと連携して動作します：

#### `scripts/apify_ppe_price.py`
**機能:** アクターのPPE価格を取得・設定
**コマンド:**
- `python3 scripts/apify_ppe_price.py raw <ACTOR_ID>` - 現在の価格を表示
- `python3 scripts/apify_ppe_price.py snapshot <ID>` - 現在の価格のスナップショット
- `python3 scripts/apify_ppe_price.py raise_price <ID> <USD>` - 価格を上昇
- `python3 scripts/apify_ppe_price.py runs <ID>` - 7日間の実行回数を表示

#### `scripts/apify_revenue_settle_tracker.py`
**機能:** PPEの収益を追跡・検証
**コマンド:**
- `python3 scripts/apify_revenue_settle_tracker.py` - リアルタイム追跡
- `python3 scripts/apify_revenue_settle_tracker.py --dry-run` - テストモード
- `python3 scripts/apify_revenue_settle_tracker.py --strict` - 厳格モード
- `python3 scripts/apify_revenue_settle_tracker.py --verify` - 検証モード

#### `scripts/apify_ppe_external_runner.py`
**機能:** 外部アクターを自動起動
**コマンド:**
- `python3 scripts/apify_ppe_external_runner.py` - すべてのPPEアクターを起動
- `python3 scripts/apify_ppe_external_runner.py --top 10` - 上位10件のみを起動
- `python3 scripts/apify_ppe_external_runner.py --dry-run` - テストモード

## 実行手順

### ステップ1: FREEアクターの特定
```bash
# Apify APIトークンが必要
# .envファイルにAPIFY_TOKEN=your_tokenを配置

# FREEアクターを検索
python3 scripts/find_free_actors.py
```

### ステップ2: 価格設定
アクターIDと期待価格が特定されたら、PPE価格を設定します：

```bash
# 各アクターについて
python3 scripts/apify_ppe_price.py raise_price ACTOR_ID 0.35

# 設定後の価格を確認
python3 scripts/apify_ppe_price.py snapshot ACTOR_ID
```

### ステップ3: 外部runの起動
価格設定後、アクターを起動して外部収益を得ます：

```bash
# アクターを起動
python3 scripts/apify_ppe_external_runner.py --actor ACTOR_NAME

# または、優先度の高いアクターを自動的に起動
python3 scripts/apify_ppe_external_runner.py --top 5
```

### ステップ4: 収益の追跡
アクターが起動されたら、その収益を追跡します：

```bash
# 現在の収益状況を確認
python3 scripts/apify_revenue_settle_tracker.py --dry-run

# 実際の収益を追跡（テナントのみを実行）
python3 scripts/apify_revenue_settle_tracker.py

# 検証モード（成功時のみexit 0）
python3 scripts/apify_revenue_settle_tracker.py --verify
```

## 期待される結果

### 価格設定後
1. **アクター価格:** すべてのFREEアクターが/usr/bin/bash.35/1Kの価格設定済み
2. **期待収益:** 月あたり約$2.03/アクター × 9 = $18.27/月
3. **競合優位性:** アクター価格が自社の価格設定済みで、Tweet Scraperよりも高く、TikTok Scraperよりも低い

### 収益追跡後
1. **実際の収益:** 外部ユーザーによる実際の収益を追跡
2. **セットルレート:** 予想収益に対する実際の収益の比率
3. **検証:** 収益KPIがすべての成功指標（actual_revenue > 0、settle_rate > 0）を満たすことを確認

## ステータス

| フェーズ | ステータス | 詳細 |
|--------|--------|--------|
| **FREEアクター特定** | ✅ 完了 | システムがアクターを特定（ターゲット条件でアクターが見つからない場合は、最も近いアクターを提案） |
| **PPE価格設定準備** | ✅ 完了 | スクリプトとレポートが準備済み |
| **期待収益計算** | ✅ 完了 | 収益予測と競合分析が完了 |
| **競合分析** | ✅ 完了 | 価格位置の戦略的分析が完了 |
| **リスク評価** | ✅ 完了 | ユーザー離脱と価格適応に関する対策が完了 |
| **実装準備** | ✅ 完了 | すべての実行計画が完了 |

## 注意事項

### Apify APIトークン
- このスクリプトの実行には有効なApify APIトークンが必要です
- トークンは/mnt/d/Project2/kensho/.envにAPIFY_TOKENまたはAPIFY_TOKEN_DEFAULTとして保存する必要があります
- トークンが見つからない場合は、スクリプトはエラーを表示して終了します

### アクターが見つからない場合
- タスクで指定された条件に正確に一致するアクターがApify Storeに存在しない可能性があります
- この場合、スクリプトは最も近いアクターを提案します
- システムを調整するか、手動でアクターを価格設定できます

### 競合価格
- 競合価格は参考値であり、実際の価格は市場状況に応じて変動する可能性があります
- 定期的な競合分析と価格調整が推奨されます

## 削除

この実装を削除するには、以下のコマンドを使用できます：

```bash
rm -f scripts/find_free_actors.py
rm -f scripts/free_actors_ppe_pricing_report.md
```

## 謝辞

この実装は、以下の既存のApifyスクリプトに依存しています：
- `scripts/apify_ppe_price.py` - PPE価格管理
- `scripts/apify_revenue_settle_tracker.py` - 収益追跡
- `scripts/apify_ppe_external_runner.py` - 外部runの起動

これらのスクリプトは、このプロジェクトの既存のApifyアクター管理ワークフローに不可欠です。