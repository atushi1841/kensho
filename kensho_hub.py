#!/usr/bin/env python3
"""
kensho_hub.py - 自分専用 懸賞ハブ（ブラウジングフィード）生成
============================================================
Kensho の収集データ(data/collected.json)から、見て楽しめる一覧HTMLを生成する。

特長
  * 締切順 / 当選人数の多い順 / 新しい順 で見られる
  * 「未応募のみ」フィルタで再応募を防げる（applied データ利用）
  * 締切が近いものを強調表示（今日 / あとN日）
  * ブラウザだけで完結する単一HTML（サーバ不要・ダブルクリックで開ける）

使い方
  python3 kensho_hub.py [collected.json のパス] [出力先 html のパス]
  省略時: data/collected.json -> data/kensho_hub.html
"""

import datetime
import html
import json
import os
import pathlib
import sys


def parse_deadline(s):
    """'2026-08-31' 等を date に。解釈不能なら None。"""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(s[:10], fmt).date()
        except ValueError:
            pass
    return None


def normalize(items, today=None):
    """raw 収集項目から hub 表示用 dict へ整形。"""
    today = today or datetime.date.today()
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        deadline = parse_deadline(it.get("deadline"))
        days = None
        status = ""
        if deadline:
            days = (deadline - today).days
            if days < 0:
                status = "expired"
            elif days == 0:
                status = "today"
            elif days <= 3:
                status = "soon"
            else:
                status = "ok"
        applied = it.get("applied") or {}
        applied_any = any(bool(v) for v in applied.values() if v)
        winner = None
        try:
            winner = int(float(it.get("winner_count") or 0))
        except (ValueError, TypeError):
            winner = 0
        src = it.get("source") or "その他"
        text = html.escape(it.get("tweet_text") or it.get("detail_url") or "")
        out.append({
            "title": html.escape((it.get("title") or "").strip() or "(タイトルなし)"),
            "text": text,
            "source": src,
            "url": it.get("detail_url") or "",
            "xurl": it.get("x_url") or "",
            "deadline": it.get("deadline") or "",
            "days": days,
            "status": status,
            "winner": winner,
            "applied": applied_any,
            "accounts": sorted(applied.keys()),
            "applied_map": {html.escape(str(k)): bool(v) for k, v in applied.items()},
        })
    return out


def build_html(items, generated_at):
    data = json.dumps(items, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>自分の懸賞ハブ</title>
<style>
:root{{--bg:#0f1115;--card:#171a21;--line:#262b36;--fg:#e6e8ee;--mut:#8b93a5;--acc:#ffd54a;--ok:#3ddc84;--hi:#ff6b6b;}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:'Hiragino Kaku Gothic ProN','Yu Gothic UI',Meiryo,sans-serif;background:var(--bg);color:var(--fg)}}
header{{position:sticky;top:0;z-index:10;background:rgba(15,17,21,.95);border-bottom:1px solid var(--line);padding:12px 18px}}
h1{{font-size:18px;margin:0 0 10px;font-weight:700}}
h1 small{{color:var(--mut);font-weight:400;font-size:12px}}
.controls{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
input,select,button{{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:13px}}
input::placeholder{{color:var(--mut)}}
label{{font-size:12px;color:var(--mut);display:inline-flex;align-items:center;gap:5px}}
.count{{margin-left:auto;color:var(--mut);font-size:12px}}
main{{padding:16px 18px;max-width:1000px;margin:0 auto}}
.grid{{display:grid;grid-template-columns:1fr;gap:10px}}
@media(min-width:720px){{.grid{{grid-template-columns:1fr 1fr}}}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 15px;display:flex;flex-direction:column;gap:8px}}
.card.applied{{opacity:.42;filter:grayscale(1)}}
.top{{display:flex;align-items:flex-start;gap:8px;flex-wrap:wrap}}
.tag{{font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);color:var(--fg);white-space:nowrap}}
.tag.src{{background:#202a3f;border-color:#2c3a55}}
.tag.dead{{font-weight:700}}
.tag.dead.soon,.tag.dead.today{{background:#3a1a1a;border-color:#7a2b2b;color:var(--hi)}}
.tag.dead.expired{{background:#23252b;color:var(--mut);text-decoration:line-through}}
.tag.win{{color:#ffd54a}}
.tag.applied-flag{{color:#8b93a5}}
h2{{font-size:14px;margin:0;line-height:1.5;font-weight:600}}
.badges{{display:flex;gap:5px;flex-wrap:wrap}}
.text{{font-size:12.5px;color:#c4c9d4;white-space:pre-wrap;word-break:break-word;max-height:4.2em;overflow:hidden;line-height:1.5;position:relative}}
.text.expand{{max-height:none}}
.doc{{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--mut);margin-top:2px}}
.doc a{{color:#7fb0ff;text-decoration:none}}
.exp{{border:none;background:none;color:var(--acc);font-size:11px;cursor:pointer;padding:0}}
.empty{{color:var(--mut);text-align:center;padding:40px 0}}
</style>
</head>
<body>
<header>
  <h1>🎯 自分の懸賞ハブ <small>{generated_at} 生成 / 全 {len(items)} 件</small></h1>
  <div class="controls">
    <input id="q" type="search" placeholder="キーワード検索…" style="min-width:180px">
    <select id="src">
      <option value="">全ソース</option>
    </select>
    <select id="sort">
      <option value="deadline">締切が近い順</option>
      <option value="winner">当選人数が多い順(狙い目)</option>
      <option value="newer">新しい順</option>
    </select>
    <label><input type="checkbox" id="onlyopen" checked> 未応募のみ</label>
    <label><input type="checkbox" id="hasdl" checked> 締切ありのみ</label>
    <label><input type="checkbox" id="hideexp"> 締切切れを隠す</label>
    <span class="count" id="count"></span>
  </div>
</header>
<main><div class="grid" id="grid"></div><div class="empty" id="empty" style="display:none">該当する懸賞がありません</div></main>
<script>
const DATA = {data};
const FMT = n => n==null||isNaN(n)?'?':(n>=0?('あと'+(n===0?'今日!':n+'日')):'締切切れ');
const bad = (it, exp=e=>e) => {{
  const b=[];
  b.push(`<span class="tag src">${{it.source}}</span>`);
  if(it.days!=null) b.push(`<span class="tag dead ${{it.status}}">締切 ${{it.deadline}}（${{FMT(it.days)}}）</span>`);
  else b.push(`<span class="tag dead">締切なし</span>`);
  if(it.winner>0) b.push(`<span class="tag win">🎁 ${{it.winner}}名</span>`);
  if(it.applied) b.push(`<span class="tag applied-flag">✓応募済</span>`);
  return b.join('');
}};
const accBad = it => {{
  if(!it.applied) return '';
  const done=it.accounts.filter(a=>it.applied_map[a]);
  return `<span class="doc">応募済み: ${{done.join(', ')}}</span>`;
}};
function render(){{
  const q=document.getElementById('q').value.trim().toLowerCase();
  const src=document.getElementById('src').value;
  const sort=document.getElementById('sort').value;
  const onlyopen=document.getElementById('onlyopen').checked;
  const hasdl=document.getElementById('hasdl').checked;
  const hideexp=document.getElementById('hideexp').checked;
  let list=DATA.filter(it=>{{
    if(q && !(it.text+' '+it.title+' '+it.source).toLowerCase().includes(q)) return false;
    if(src && it.source!==src) return false;
    if(onlyopen && it.applied) return false;
    if(hasdl && it.days==null) return false;
    if(hideexp && it.status==='expired') return false;
    return true;
  }});
  if(sort==='winner') list=list.sort((a,b)=>b.winner-a.winner || (a.days??999)-(b.days??999));
  else if(sort==='newer') list=list.sort((a,b)=>(b.deadline||'').localeCompare(a.deadline||''));
  else list=list.sort((a,b)=>(a.days==null?999:a.days)-(b.days==null?999:b.days));
  const grid=document.getElementById('grid');
  grid.innerHTML=list.map((it,i)=>`
    <div class="card ${{it.applied?'applied':''}}">
      <div class="top"><h2>${{it.title||'(無題)'}}</h2></div>
      <div class="badges">${{bad(it)}}</div>
      <div class="text" id="t${{i}}">${{it.text}}</div>
      <button class="exp" onclick="toggle(${{i}})">…続きを表示</button>
      <div class="doc">
        ${{it.url?`<a href="${{it.url}}" target="_blank">詳細</a>`:''}}
        ${{it.xurl?`<a href="${{it.xurl}}" target="_blank">Xで見る</a>`:''}}
      </div>
      ${{accBad(it)}}
    </div>`).join('');
  document.getElementById('empty').style.display=list.length?'none':'block';
  document.getElementById('count').textContent=list.length+' 件 / '+DATA.length;
}}
function toggle(i){{
  const el=document.getElementById('t'+i);
  el.classList.toggle('expand');
  el.nextElementSibling.textContent=el.classList.contains('expand')?'閉じる':'…続きを表示';
}}
// ソース選択肢をデータから用意
const srcs=[...new Set(DATA.map(x=>x.source))].sort();
const sel=document.getElementById('src');
srcs.forEach(s=>{{const o=document.createElement('option');o.value=s;o.textContent=s;sel.appendChild(o);}});
['q','src','sort','onlyopen','hasdl','hideexp'].forEach(id=>document.getElementById(id).addEventListener('input',render));
render();
</script>
</body>
</html>
"""


def main():
    here = pathlib.Path(__file__).resolve().parent
    src_path = sys.argv[1] if len(sys.argv) > 1 else str(here / "data" / "collected.json")
    out_path = sys.argv[2] if len(sys.argv) > 2 else str(here / "data" / "kensho_hub.html")
    with open(src_path, encoding="utf-8") as f:
        raw = json.load(f)
    # collected.json は "collected" 配列を持つ。無ければそのまま配列とみなす
    items = raw.get("collected") if isinstance(raw, dict) else raw
    today = datetime.date.today()
    data = normalize(items, today)
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html_out = build_html(data, generated_at)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"OK: {len(data)} 件 → {out_path}")


if __name__ == "__main__":
    main()
