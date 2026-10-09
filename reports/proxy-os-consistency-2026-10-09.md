# プロキシOS整合性確認 — 実測報告 (2026-10-09)

## 実測結果

### プロキシホストOS
| 項目 | 値 |
|------|-----|
| ホスト | 172.26.80.1 (WSL Linux N100) |
| OS | Ubuntu 24.04.4 LTS (Noble Numbat) |
| カーネル | 6.6.87.2-microsoft-standard-WSL2 |
| TCP パラメータ | port_range=32768-60999, somaxconn=4096, cubic |

### 各垢プロキシ状態
| 垢 | ポート | proxy_state | TCP疎通 | 備考 |
|----|-------|-------------|--------|------|
| atushi16 | 1081 | listen (JSON) | **CLOSED** | 自宅有線LAN |
| kudou | 1082 | 停止 (JSON) | **CLOSED** | POVOスマホ、adapter切断 |
| zin20120731 | 1084 | 停止 (JSON) | **CLOSED** | Aterm MR05LN、adapter切断 |
| TankanNotes | 1085 | listen (JSON) | **CLOSED** | 有線LAN直結 |
| toushiwatch | 1087 | 停止 (JSON) | **CLOSED** | RM10JE_S、adapter切断 |

**全ポート CLOSED（プロキシ未起動中）**

### ブラウザ詰称OS（SeleniumBase CDP）
| 項目 | 値 |
|------|-----|
| platform | Win32 |
| platformVersion | （Windows） |
| CPUアーキテクチャ | x86_64 |

## 判定

### OS不一致は構造的・本質的
- プロキシホスト = Ubuntu 24.04 (Linux)
- ブラウザ詰称OS = Windows (Win32)
- これは **設定ミスではなくアーキテクチャ上的必然**（SOCKS5プロキシはWSL/Linuxホストで動く、ブラウザはWindows経由のCDPで操作）

### 影響評価
- **現状で応募成功率100%**（タスク本文記載）→ BOT検知による応募停止は起きていない
- TLS TCPフィンガープリントの不一致は **カーネル層** の値だが、X/Twitter側の検知阈値は未確認
- external_runs=0 / Gumroad売上0 の **直接的な原因ではない**（原因は可視性・信頼・集客）

### 結論
- プロキシOS整合性の是正は **現状では非現実的**（Linuxホスト上的SOCKS5 + Windowsブラウザ詰称の構造）
- 代わりに有効なのは「**ブラウザ詰称OSをLinuxに変更する**」か「**プロキシをWindowsホストに移設する**」の2択
- どちらも **高リスク・高コスト**（プロキシ再構築 or ブラウザ設定変更）であり、
  応募成功率100%の現状を崩すリスクがあるため **現时不推奨**

## 収益接続
この調査は収益基盤の理解を深めたが、**直接的な収益upには繋がらない**。
external_runs=0の真因は「可視性・信頼・集客」にあり、proxy OS整合性ではない。
→ 本調査は **クローズ**。criticへの提案例外。