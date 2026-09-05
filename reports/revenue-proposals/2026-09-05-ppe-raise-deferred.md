# revenue-worker PPE 値上げ A/B 判定 延期記録 (2026-09-05)

## タスク
- Kanban: `t_47db49e9`「PPE値上げA/B 7日後判定（japan-offmall 復帰 or 維持）」
- 仕様元: `reports/revenue-proposals/2026-09-05-revenue-worker-v20-ppe-raise-test.md`（critic v19-C）

## 事象：カードが約7日早期にディスパッチされた
- 値上げ実施: **2026-09-04 15:55:15Z**（= 9/5 00:55 JST、v20 仕様どおり）
- 本判定カードは作成＝即ディスパッチされ、**値上げから約50分後（9/5 01:45 JST）**に実行開始。
- 仕様（v19-C / v20 report 判定ルール）は **「7日後（9/12 00:55 JST 以降）再評価」** を明記。
  → 現時点で判定すると7日間の価格弾力性を観測できず、run数がベースラインと同一のため
    空の「維持」判定でA/Bが早期確定してしまう。**判定を延期した。**

## 本日実行時スナップショット（Apify read-back、2026-09-05 01:45 JST）
`workspaces/t_47db49e9/ppe_snapshot.py` 実行結果（result: ppe_snapshot_result.json）:
| アクター | ID | pricingInfos | 有効(最新) | 直近7d run |
|----------|-----|--------------|------------|------------|
| offmall（値上げ対象） | Zh4kqcS4dYPWpFzBd | 2エントリ | **2026-09-04T15:55:15Z / $0.005** | **35** |
| camera（対照） | mQaZFo6up4YZKepC3 | 1 | $0.002 | 7 |
| watch（対照） | gMqdrS2evpcybSZc2 | 1 | $0.002 | 7 |
| luxury（対照） | b0vuqa3ESvy2mOwFB | 1 | $0.002 | 7 |
| instrument（対照） | yN1R26HrV6C2MBKas | 1 | $0.002 | 7 |

- 値上げは有効（最新エントリ $0.005、公開維持）。ベースライン（offmall 35件）と同一。
- 外部ユーザー run は全アクター0件（既知状態、total runs を需要プロキシ）。

## 処置
1. **ブロック**: `kanban_block(kind=needs_input)` — 判定ウィンドウ未到来（9/12 00:55 JST）。
2. **ワンショットcron**: `ppe-raise-7d-judgment`（job_id `f450cc563ced`）を **2026-09-12 00:55 JST**（schedule: 2026-09-11T15:55:00Z）に登録。
   実行内容: 直近7日run数再計測 → `<24.5件なら $0.002 復帰 / ≥25件なら $0.005 維持` →
   read-back検証（最終エントリ=有効）→ レポート保存 → kanban t_47db49e9 へ結果投稿。

## 要ユーザー / オーケストレーター対応
- **Hermes ゲートウェイが停止中**のため cron は保存のみで発火しない。9/12 までに
  `hermes gateway start` が必要（cron作成時の警告による）。
- 9/12 以降に t_47db49e9 を解除し、cron 実行結果で完了させること。
- 復帰コマンド（cronが自動実施しない場合の手動代替）:
  Apify PUT /v2/acts/Zh4kqcS4dYPWpFzBd、pricingInfos 末尾に `datasetItemUsd=0.002` 新エントリ追記。
  有効価格は「最後（最新）のエントリ」= [-1]。

## 申し送り
- 判定日時は仕様どおり 9/12 00:55 JST。今回の早期ディスパッチは、未来日付カードを
  即ディスパッチする scheduling の欠陥が原因。次回から A/B 判定カードは cron/配信に
  遅延を持たせるか、triage に置いて日付到来後に activate する運用を推奨。
