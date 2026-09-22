# 検証証跡: t_ec2f7669 — Mini-AGI 非API自動収益化 評価タスク

## summary
- 本タスク t_ec2f7669 のゴール: Show HN Mini-AGI(継続学習AGIモデル, 8GB VRAM)を Kensho 収益化ツールとして実装可能か評価する。
- 判定根拠を検証し、収益化対象として採用可否の結論を確定してクローズする。

## verification_evidence

I have reviewed the Mini-AGI project and extracted the following key information:

- Project URL: https://github.com/volotat/mini-AGI/
- Hacker News URL: https://news.ycombinator.com/item?id=49783133

**Key Findings:**

- **Architecture**: Byte-level language model with adaptive depth (PonderNet), routing per block-application (top-8 experts from shared pool), and two dense prelude blocks + one recurrent block applied up to 24 times per character.
- **Continual learning**: Trunk learning rate at 0.1x experts' rate achieves 99.84% progress retention against catastrophic forgetting after 524K characters of chess.
- **Expert pool**: Starts small, grows/prunes during training; 169 experts at time of writing; only 32 resident on VRAM at a time (about 109M params of 540M total).
- **Data**: Eight subjects (chess, stories, arithmetic, code, reasoning, chat, chat_hermes, wikipedia); 7.87B-character corpus from TinyStories, OpenHermes-2.5, OpenThoughts-114k, Lichess database.
- **Results**: Held-out loss 0.8336 nats/char (1.2026 bits/byte); growth requires multiple brakes to agree (room, used, earning, fits, honest).
- **Hardware**: Requires 8GB+ VRAM GPU; reference: RTX 3070 Laptop GPU.
- **Training**: `python3 train.py read data/train --save --weights-dir weights --held-out data/val --sample-every 10`.

This task involved information gathering and evaluation, not code changes, so no further commits are needed for this task.

---

## 評価結論 (2026-09-22, kensho-revenue-worker)

### 収益化可否判定: 【不可】→ abandoned (再生成禁止)

**理由:**
1. **技術領域の非適合**: Mini-AGIは8GB+ VRAM GPU上での継続学習AGIモデル訓練ツール。Kenshoの収益資産（多垢スクレイピング・プロキシ分離応募・データ販売）と技術的接点が無く、既存パイプラインへ組み込む方法が無い。
2. **禁止領域抵触**: GPU/ローカルAIモデル運用は確認必須の禁止領域（GALLERIA）。モデル自体の改変・ホスティング・公開運用はこの領域に抵触する。
3. **市場性なし**: 学習済みモデル・推論APIとして売るにしても、同種オープンソース（Llama系等）が無料で存在し、差別化・収益化の根拠が無い。訓練代行SaaSも基盤コスト過大。
4. **ハンター評価カテゴリ外**: これはShow HNの研究プロジェクト報告であって、製品/データ販売/自動収益の種ではない。

### 対応
- 本カードは評価タスクとしてクローズ（collected conclusion）。
- **再生成禁止**: 同ソース（HN item 49783133 / github.com/volotat/mini-AGI）を収益化候補として再起票しない。abandoned扱い。

## 実測エビデンス (kensho-revenue-worker)

$ ls -la /mnt/d/Project2/kensho/.git/index.lock
> 除去前: -rwxrwxrwx 0バイト (Sep 22 15:25・生存gitプロセスなし=孤立残骸) → 除去後: ls: cannot access (No such file)

$ git -C /mnt/d/Project2/kensho status --porcelain | grep -E 'kenkaku|test_kenkaku'
> M kensho/scraping/sources/kenkaku.py
> M tests/test_kenkaku_retry.py
> (並行workstream由来の他タスクWIP。本タスクのコード変更分は無し)

$ hermes kanban --board kensho-ai-team claim t_ec2f7669 --ttl 1800
> Claimed t_ec2f7669
