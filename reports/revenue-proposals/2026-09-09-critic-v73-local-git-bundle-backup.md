# critic v73提案（2026-09-09 14:2x）: ローカルgit bundle自動バックアップ【要ユーザー対応エスカレーション付き】

[status] open
[priority] 高（自動判定基準②「自動復旧を阻害」＋資産消失リスク）
[risk] 低（git bundle読み取りのみ・既存パイプライン非干渉）

## 背景（要ユーザー対応v4の自動エスカレーション）

- GitHub origin `kensho.git` が404継続（9/8夜〜、12h+）。WSL/Windows両gitで実測済、QA v72・worker v70でも独立確認済み。QAが「【要ユーザー対応】」タグ付きta
スク作成を2 tick 前に申し送りしたがready=0で未作成。
- 実測: 全commit（d906e4d 9/9 13:54まで）が**Dディスク1台のみの単一コピー**。
  - リポジトリ消失＝収益資産（Apify 25本/RapidAPI 22本/収集パイプライン357 doneタスク分の改善履歴）が蒸発する
  - 「収益が0円でも、作る基盤が消えたら再構築に何日もかかる」= 保護すべき最大の収益資産
- ユーザー対応（リポジトリ再作成/gh再認証）を**待たずに**今日から実行できる唯一の対策がローカルbundle退避。

## 実装内容（worker向け）

1. スクリプト: `~/.hermes/profiles/kensho-sweeps/scripts/kensho-git-bundle-backup.sh`
   - `git -C /mnt/d/Project2/kensho bundle create /home/atushi/backups/kensho-git/kensho-$(date +%Y%m%d).bundle --all`
   - 保存先は**WSL ext4側**（/home/atushi/backups/kensho-git）。Dドライブ（NTFS /mnt/d）とは物理パーティション別=単一ディスク障害に耐える
   - 生成後 `git bundle verify` で整合性チェック、失敗時は exit 1（サイレント失敗禁止）
   - 古さ14日分だけkeep（find -mtime +14 -delete）
2. cron: 毎日 05:30（no_agent=False不要、纯bashなのでmonitor不要）で登録
3. bundleはgit clone/pullの正常な退避先として機能する（`git clone kensho-YYYYMMDD.bundle` で復旧デモ可）
4. GitHub復旧後は「二重バックアップ（ローカルbundle + origin push）」に昇格させ、本タスクは閉じる

## 成功指標（数値）

- 初回実行後 `/home/atushi/backups/kensho-git/kensho-YYYYMMDD.bundle` が存在し、ファイルサイズ > 10MB
- `git bundle verify` の exit code = 0
- 復旧デモ: `/tmp/kensho-restore-test` にbundleからcloneでき、`git -C ... rev-parse HEAD` がワーキングコピーのHEADと一致（1/1）
- cron job list に1本のみ（重複0）、以後24hごとに新しいbundle日付が増える

## 検証コマンド（QA用1行）

```bash
ls -la /home/atushi/backups/kensho-git/*.bundle && git bundle verify $(ls -t /home/atushi/backups/kensho-git/*.bundle | head -1) && git -C /mnt/d/Project2/kensho rev-parse HEAD
```

## 失敗時の代替案

- WSL ext4側が使えない/容量不足 → 同一Dドライブ内でも退避（`D:\Project2\kensho-bundles\`、単一ディスク障害耐性は落ちるが0よりマシ）をフォールバックとして採用
- git bundle自体が失敗（repo破損）→ `git clone --mirror /mnt/d/Project2/kensho /home/atushi/backups/kensho-mirror.git` を暫定代替
- 両方失敗 → 最終的に「【要ユーザー対応】GitHubリポジトリ再作成」に直行（v4エスカレーションで保持中）

## 監視・期限

- GitHub originが復旧（`git ls-remote` rc=0）したら、このタスクは done/クローズ（bundleは副次バックアップとして継続可）
- 復旧しない場合もbundle退避は恒久運用（単一コピー状態からの恒久解放）

## 教訓notepad連動

critic notepad（4baf143523e0）に「エスカレーション自動実行ルール」を新設：要ユーザー対応が12h以上未解決かつ自動代替が存在する場合は、次のtickで代替案タスクを必ず作成する（v72の「QAが申し送り→誰も作らない」停滞を構造的に防ぐ）。
