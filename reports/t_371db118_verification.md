# verification_evidence

## 実装内容
scripts/kensho_revenue_dashboard.py の render() に実績収益セクションを追加し、以下の KPI を表示:
- **実績収益（決済完了分・Apify）**: apify_verified_revenue_usd（通貨 USD）— $2.07
- **決済状況**: apify_settle_status — completed
- **課金item数**: apify_verified_charged_items — 414
- **外部run数**: apify_ppe_external_runs.summary.total_triggered — 7

## 7日トレンド表に Apify実収益(USD) 列を追加
- apify_actual_revenue_usd が数値なら $X.XX、None なら "—" を表示
- フォールバック: actual が None なら verified を使用、両方 None なら "—"

## 検証コマンドと結果
```bash
$ python3 scripts/kensho_revenue_dashboard.py
✓ revenue-status.html 生成完了 (25 entries)
  出力: /mnt/d/Project2/kensho/revenue-status.html
```

```bash
$ grep -n '2.07' revenue-status.html
40:<div class="stat-card"><div class="stat-val" style="color:#3fb950">$2.07</div><div class="stat-label">実績収益（通貨 USD）</div></div>
111:<tr><td>2026-09-20</td>...<td>$2.07</td></tr>
```

```bash
$ grep '実績収益' revenue-status.html
<div class="card-title">実績収益（決済完了分・Apify）</div>
<div class="stat-card"><div class="stat-val" style="color:#3fb950">$2.07</div><div class="stat-label">実績収益（通貨 USD）</div></div>
<p class="sub" style="margin-top:8px">実績収益=apify_verified_revenue_usd（決済確定済み）。月間収益見込みとは別指標（推定値と実績の混同防止）。</p>
```

## 成功指標確認
- revenue-status.html に "2.07" が実績収益として記載されている ✓
- 月間収益見込みカードは $0 のまま（推定値と実績の混同防止）✓
- mypy strict 0 error ✓
- pytest 66 passed ✓