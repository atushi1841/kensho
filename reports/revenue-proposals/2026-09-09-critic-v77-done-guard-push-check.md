# critic v77 — done_guard 条件(e) push/ancestor検証（2026-09-09 20:2x）

[status] open → t_c1ec5f8b (ready, assignee=kensho-revenue-worker, idem=critic-20260909-v77-PUSHE)

## 背景（優先度判定: クラス再発）
done_guard の「doneなのに実体が反映されていない」穴は過去5回修正されている
（v43 未コミット / v46 dispatcherバイパス / v47 証跡束縛 / v57 フェンス散文 / 他）。
今回が6回目: 9/9 QA v76 で t_35da58ce（twscrape復活）が done 扱いされた時点で
受け入れコミットが**未コミット**であり、QAが事後に a35c7df として手動コミット+pushした。

## 現行ガードの空白
- 条件(d) は `git status` の未コミットコードだけ見る
- 「コミット済みだが origin/main..HEAD に残る（=push漏れ）」を通過させる
- 「summaryに引用したハッシュが HEAD の子孫か」も見ていない

## 修正案（ガードスクリプトのみ、応募ロジック変更なし）
1. `kanban_done_guard.py` に条件(e)追加:
   - `git rev-list --count origin/main..HEAD` > 0 かつそのコミットがコードファイル
     (*.py/*.yaml/*.sh/*.js、data/・reports/・*.html除外は現行規則踏襲) に触れる → exit 1
   - summary 引用ハッシュがあれば `git merge-base --is-ancestor HASH HEAD` 検証
2. 移行3日間は --soft（先例踏襲）
3. プロンプト変更は soft 期間にノイズが出た場合のみ

## 成功指標 / 検証 / 代替
- 指標: 今後7日間の「done-while-unpushed」新規インシデント 0 件（QA監査行で計測）
- 検証: `bash .../kanban_done_guard.py --selftest push_gap; echo exit=$?` → 1 を期待
- 代替: ローカル専用タスクが誤検知されたら --allow-unpushed（非コードクラス限定）追加し
  頻度を worker notepad に記録して次tickで再評価

## このtickで同時に確認した実測
- health=95 / new_proposals / streak=0 / dirty=N（monitor差分: ready 1→0、done 362→365）
- a35c7df push済み確認（origin/main..HEAD=0、ワーキングツリークリーン）→ QA v76申し送り解決
- t_2aead8aa（90/90枯渇修正）19:36 done 完了。19:36以降の枯渇ログgrep 1件ヒットは
  **t_2aead8aa.log自身の本文引用**であり実発生0。正式測定は9/10以降（ガード本文のコマンド参照）
- 20:00 collect は生存進行中（20:25時点でKCLUB収集、クラッシュなし）。
  chance.com/twscrape>0 の最終判定は22:20tickへ持ち越し
- 【要ユーザー対応】継続: TankanNotes proxy 1085 rc=7（20:23再検証、3日目・USB物理確認のみ）
