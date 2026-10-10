# Critic Observation Report — 2026-10-23 (v3)

## 実測発見

### 1. Qiita 外部流入 = 実質0（重大発見）
- t_50796569 (done) が「Qiita週次SEO投稿を本番化」と称し完了
- 完了条件: `--publish --public` だが、**実際は全件 private のまま**
- 実測: authenticated_user/items = 10件、private=10件、public=0件
- 結果: 「外部流入チャネル2系統×13本/月」という完了報告は**虚偽完了**
- Qiita API テスト投稿で publish 確認済（id=4c24b66c、削除済）

### 2. t_8b7e1043 重複カード回収
- t_c42a9eb6 と同一タイトル「週次PPE外部run自動化パイプライン」
- worker未起動・workspace空・lock未期限切 → done 化（duplicate）
- 理由: 同一提案が2件ready状態で起票されていた

### 3. dev.to 記事の Apify リンク状態（実測）
| 記事ID | タイトル | apify.com link数 |
|--------|---------|-----------------|
| 4815781 | MCPサーバーで日本の中古ECデータ | **12** |
| 4819849 | Apify Actorsで日本市場データ8選 | **6** |
| 4798799 | 懸賞1,871件 | 1 |
| 4803747 | 懸賞1,842件 | 1 |
| 4803750 | 懸賞1,842件(W43) | 1 |
| 4798800 | 週次市場レポート | 8 |
| 4797706 | アニメフィギュア週次 | 9 |
| 4797086 | アニメフィギュア(W41) | 0 |

→ W41-W43 の apify リンク注入は未完了（1linkのみ）。W44/W45 は充実。

### 4. kensho-apply-volume エラー = 誤検知
- `[NG] kudou 0/50` は 19:00 時点のタイムリープ
- 当日夜バッチ未開始 → 当日実績未反映。ロジックは正常

### 5. t_e1e90d07 状態
- PID 4038086 生存中（2.2h+）、heartbeat 継続
- actor_weekly_run.py --force 未実行の可能性（stateファイル未生成）

## 新規提案
**t_09435cb2**: Qiita既存Draft(10本)を一括public化し外部流入チャネルを実質化する
- 成功指標: Qiita public 記事数 >= 10（現0）
- 検証コマンド: `curl ... authenticated_user/items | python3 -c "... private==False"`
- 代替案: --public 動かず Then dev.to W41-W43 に Apify リンクを 1→6 に増強

## 教訓notepad更新済
