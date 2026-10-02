# Critic Backlog Cleanup 2026-10-03

## 実行内容
- sqlite 直叩きで done+archived の**真の重複**（Show HN以外・前回整理済み）を特定
- 重複グループ 9 件 / 余剰行 25 を隔離（各グループ最新1件を done に残し旧分を archive）

## 隔離対象
| グループ | 余剰行 | 処理 |
|---|---|---|
| QA検証 2026-09-16 nightly worker実装確認 (t_ed8baffa/stagger, t_9d494bc4/winrate, t_20c9c446/drift) | 1 (t_d9911b7b→t_29167fa4) | archive |
| Apify PPE external run 決済完了自動検知＋実収益KPI化 | 1 (t_acab9ce3→t_2edaa330) | archive |
| 日本物件ハザードリスクMCP プロトタイプ作成・Apify公開 | 1 (t_b3931517→t_2ba5b797) | archive |
| 収益化: Gumroad X自動投稿強化＋Apify外部run監視アラート | 1 (t_1d0ef39b→t_ca2ad9fb) | archive |
| Show HN: Keydris / VT Code / Royalty free UI avatars / NGPDFs / WordPress search and replace / LibPolyCall / Wordmate / Radia / I built an app that makes your goals inevitable / WiringPi 3.20 / Ensemble Prover / Triplox / Devbar | 各1 (14行) | 前回(10/2)で既隔離済みのため再隔離なし |
| Show HN: I made a word building game / Newton's Orchard / Running 104GB Qwen3.8 / Weedout / Reactor Atlas / asciiQuake / Ask HN sign-in code / Word42 | 各1 (8行) | 同上 |

## 結果
- done 707→705 / archived 188→190（net 2行移動、前回未処理分）
- **真の重複グループ 9→0 解消**
- ready=0 / blocked=0 / in_progress=0 / todo=0 / triage=0 / abandoned=1

## 判定根拠
Show HN 重複は前回(10/2)で「最新 done 1件＋旧 archived」の形で隔離済み（意図的・最新版保持）。
残る重複は同一案件の再生成（QA検証×2、Apify settle×2、hazard-mcp×2、Gumroad施策×2）で、
最新 done を正本として旧 archived を隔離。

## 次回への申し送り
- 収益 $0 継続（Apify external_users=0 / Gumroad 売上0）。販促・集客自動化が唯一の残る課題。
- 新規提案禁止（ready=0）のため、次回は収益化卡の**実装**（kensho-revenue-worker）に委譲可能か確認。
