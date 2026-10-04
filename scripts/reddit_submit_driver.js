// reddit_submit_driver.js — Reddit コメント投稿の CDP ドライバ（Windows側で実行）
//
// 設計方針（2026-10-03 の調査結果より）:
//   - Reddit のコメント入力欄は Shadow DOM + Lexical で保護され、合成キー入力を受け付けない。
//     → UI を叩かず、**ログイン済みセッション内の fetch('/api/comment')** を使う。
//       ブラウザ内 fetch は cookie/CSRF/TLS/UA 指紋がすべて本物になる（これが最善手）。
//   - ただし「投稿だけして即閉じる」挙動は人間離れしているため、投稿前に
//     スレを実際に読む（段階スクロール＋滞在）を挟む。
//   - CDP は実 Chrome に接続する。navigator.webdriver は立たない。
//
// 使い方:
//   node reddit_submit_driver.js --cookie <header文字列ファイル> --url <スレURL>
//        --body <本文ファイル> --out <結果JSON> [--dry-run]
//   env: REDDIT_CDP_PORT (既定 9229)

const http = require('http');
const fs = require('fs');

const PORT = parseInt(process.env.REDDIT_CDP_PORT || '9229', 10);

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  return i > 0 ? process.argv[i + 1] : def;
}
const has = (name) => process.argv.includes('--' + name);

const cookieFile = arg('cookie');
const threadUrl = arg('url');
const bodyFile = arg('body');
const outFile = arg('out', 'C:\\temp\\reddit_submit_out.json');
const dryRun = has('dry-run');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// 人間のキー入力間隔に近い揺らぎ（平均80ms・σ30ms 相当）
const jitter = (mean, sigma) => Math.max(20, Math.abs(mean + (Math.random() - 0.5) * 2 * sigma));

function httpJson(path) {
  return new Promise((resolve, reject) => {
    http.get('http://127.0.0.1:' + PORT + path, (res) => {
      let d = '';
      res.on('data', (c) => (d += c));
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

async function main() {
  const tabs = await httpJson('/json');
  let page = tabs.filter((t) => t.type === 'page')[0];
  if (!page) throw new Error('page target not found');

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = {};
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending[m.id]) { pending[m.id](m); delete pending[m.id]; }
  };
  const send = (method, params = {}) => new Promise((resolve) => {
    const mid = ++id;
    pending[mid] = resolve;
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  await new Promise((r) => (ws.onopen = r));

  const evalJs = async (expr) => {
    const m = await send('Runtime.evaluate', {
      expression: expr, returnByValue: true, awaitPromise: true,
    });
    if (m.result && m.result.exceptionDetails) {
      return { error: JSON.stringify(m.result.exceptionDetails).slice(0, 400) };
    }
    return { value: m.result && m.result.result && m.result.result.value };
  };

  const result = { dry_run: dryRun, steps: [] };

  // 1) cookie 注入（header 文字列 → Network.setCookie）
  await send('Network.enable');
  await send('Page.enable');
  if (cookieFile && fs.existsSync(cookieFile)) {
    const raw = fs.readFileSync(cookieFile, 'utf8').trim();
    let n = 0;
    for (const part of raw.split(';')) {
      const idx = part.indexOf('=');
      if (idx <= 0) continue;
      const name = part.slice(0, idx).trim();
      const value = part.slice(idx + 1).trim();
      if (!name || !value) continue;
      // secure/httpOnly を外してサーバーに拒否されない形で入れる（実測の知見）
      await send('Network.setCookie', { name, value, domain: '.reddit.com', path: '/' });
      n++;
    }
    result.cookies_injected = n;
  }

  // 2) スレへ移動
  await send('Page.navigate', { url: threadUrl });
  await sleep(4000 + Math.random() * 3000);

  // 3) ログイン確認（信頼するのは API レスポンスの name のみ）
  const me = await evalJs(
    "fetch('/api/me.json',{credentials:'include'}).then(r=>r.json()).then(j=>(j&&j.data&&j.data.name)||null)"
  );
  result.logged_in_as = me.value || null;
  result.steps.push('login_check:' + (me.value || 'guest'));
  if (!me.value) {
    fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
    console.log('NOT_LOGGED_IN');
    ws.close();
    return;
  }

  // 4) 読む（段階スクロール＋滞在。投稿だけして即離脱する挙動を避ける）
  const h = (await evalJs('document.body.scrollHeight')).value || 1000;
  const stepsN = 3 + Math.floor(Math.random() * 3);
  for (let i = 1; i <= stepsN; i++) {
    await send('Runtime.evaluate', { expression: `window.scrollTo({top:${Math.round((h * i) / stepsN)} })` });
    await sleep(1200 + Math.random() * 2600);
  }
  result.steps.push('read_scroll:' + stepsN);
  const title = (await evalJs('document.title')).value || '';
  result.thread_title = title;

  // 5) 本文の確定（改行を保持）
  let body = '';
  if (bodyFile && fs.existsSync(bodyFile)) {
    body = fs.readFileSync(bodyFile, 'utf8').replace(/\r\n/g, '\n').trim();
  }
  result.body_chars = body.length;

  if (dryRun) {
    result.steps.push('dry_run_stop_before_post');
    fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
    console.log('DRY_RUN_OK user=' + result.logged_in_as + ' chars=' + body.length);
    ws.close();
    return;
  }

  // 6) 投稿（ブラウザ内 fetch。cookie/CSRF はブラウザが自動付与）
  //    thing_id はスレURLの /comments/<id>/ から取る
  const m2 = threadUrl.match(/\/comments\/([a-z0-9]+)/i);
  const postId = m2 ? m2[1] : '';
  if (!postId) throw new Error('cannot extract post id from url');

  const expr = `(async () => {
    const csrf = (document.cookie.match(/csrf_token=([^;]+)/) || [])[1] || '';
    // 旧API(/api/comment)の uh は csrf ではなく /api/me.json の modhash（実測50桁）。
    // ここに csrf(32桁) を入れると 403 になる。
    const me = await fetch('/api/me.json', {credentials:'include'}).then(r=>r.json()).catch(()=>null);
    const uh = (me && me.data && me.data.modhash) || '';
    const p = new URLSearchParams();
    p.set('api_type', 'json');
    p.set('thing_id', 't3_${postId}');
    p.set('text', ${JSON.stringify(body)});
    p.set('r', (location.pathname.split('/')[2] || ''));
    if (uh) p.set('uh', uh);
    if (csrf) p.set('csrf_token', csrf);
    const r = await fetch('/api/comment?raw_json=1', {
      method: 'POST', credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Modhash': uh,
        'X-CSRF-Token': csrf,
      },
      body: p,
    });
    const t = await r.text();
    let j = null;
    try { j = JSON.parse(t); } catch (e) { j = { raw: t.slice(0, 300) }; }
    return JSON.stringify({ status: r.status, json: j, uh_len: uh.length, csrf_len: csrf.length });
  })()`;
  const r6 = await evalJs(expr);
  let parsed = null;
  try { parsed = JSON.parse(r6.value); } catch (e) { parsed = { parse_error: String(r6.value).slice(0, 300) }; }
  result.post_response = parsed;
  result.steps.push('post_status:' + (parsed && parsed.status));

  // 7) 投稿確認（スレの JSON を取り、自分のコメントが載っているか）
  await sleep(3000);
  const verify = await evalJs(
    `fetch('/r/' + (location.pathname.split('/')[2] || '') + '/comments/${postId}.json?limit=50', {credentials:'include'})
      .then(r=>r.json()).then(j=>{
        const listing=(j[1]&&j[1].data&&j[1].data.children)||[];
        const mine=listing.map(c=>c.data).filter(d=>d&&d.author===${JSON.stringify(result.logged_in_as)});
        return JSON.stringify({count: listing.length, mine: mine.slice(0,3).map(d=>({id:d.id, body:(d.body||'').slice(0,80)}))});
      })`
  );
  try { result.verify = JSON.parse(verify.value); } catch (e) { result.verify = { raw: String(verify.value).slice(0, 300) }; }

  fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
  console.log('POSTED status=' + (parsed && parsed.status) + ' user=' + result.logged_in_as);
  ws.close();
}

main().catch((e) => { console.error('ERR ' + (e && e.message)); process.exit(1); });
