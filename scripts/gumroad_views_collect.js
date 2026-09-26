// scripts/gumroad_views_collect.js — t_3848cbde 商品ページviews日次収集（Gumroad Analytics CDP）
//
// gumroad_sales_collect.js（売上収集・port 9333）と分離した独立スクリプト。
// 既存売上パイプライン（t_ee5ca962等で稼働中の本番収集）には一切触れない。
//
// 使い方:
//   node.exe gumroad_views_collect.js <from=YYYY-MM-DD> <to=YYYY-MM-DD>
//
// 出力: stdout の `VIEWS_JSON:` 行に1行JSON。
//   {from, to, url, login_ok, views, sales, total, referrers: {source: views}, collected_at}
// 追記: data/gumroad_views_history.json へ {date: {...}} を日次マージ（既存上書き可）。
//
// 解析元: https://gumroad.com/dashboard/sales?from=X&to=X の統計カード
//   "Sales\n<N>\nViews\n<N>\nTotal\n$X" と Referrer 表（Twitter 経由views=販促効果）。
const http = require('http');
const fs = require('fs');
const { execFile } = require('child_process');

const CDP_PORT = parseInt(process.env.GUMROAD_VIEWS_CDP_PORT || '9335', 10);
const COOKIE_FILE = 'D:\\Project2\\gumroad-automation\\gumroad_cookies.json';
const STATE_FILE = 'D:\\Project2\\kensho\\data\\gumroad_views_history.json';
const CHROME_EXE = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const CHROME_PROFILE = `C:\\temp\\gumroad-views-${CDP_PORT}-${process.pid}`;
const NAVIGATION_TIMEOUT = 15000;
const LAUNCH_TIMEOUT_MS = 45000;

const FROM = process.argv[2];
const TO = process.argv[3] || FROM;
if (!/^\d{4}-\d{2}-\d{2}$/.test(String(FROM)) || !/^\d{4}-\d{2}-\d{2}$/.test(String(TO))) {
  console.error('usage: node gumroad_views_collect.js <YYYY-MM-DD> [YYYY-MM-DD]');
  process.exit(64);
}

function getJSON(host, path) {
  return new Promise((resolve, reject) => {
    http.get(`http://${host}:${CDP_PORT}${path}`, (res) => {
      let d = '';
      res.on('data', (c) => d += c);
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(new Error('JSON parse error: ' + d.slice(0, 200))); } });
    }).on('error', reject);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function connectCdp() {
  for (const host of ['127.0.0.1', '[::1]']) {
    try {
      const tabs = await getJSON(host, '/json');
      if (Array.isArray(tabs) && tabs.length > 0) {
        const page = tabs.find((t) => t.type === 'page' && t.url.startsWith('http')) || tabs.find((t) => t.type === 'page');
        if (page) return { host, page };
      }
    } catch (e) { /* 次のホスト */ }
  }
  return null;
}

async function ensureChrome() {
  let conn = await connectCdp();
  if (conn) return conn;
  console.log('Chrome起動: port=' + CDP_PORT);
  try {
    execFile(CHROME_EXE, [
      '--remote-debugging-port=' + CDP_PORT,
      '--user-data-dir=' + CHROME_PROFILE,
      '--no-first-run', '--no-default-browser-check',
      '--headless=new', '--disable-gpu', '--window-size=1280,900',
      'about:blank',
    // stdio:'ignore' — 親stdout継承で node 終了待ちが発生する（t_ee5ca962 実測）。
    ], { windowsHide: true, detached: true, stdio: 'ignore' }, () => {});
  } catch (e) {
    console.log('Chrome起動失敗: ' + e.message);
  }
  const deadline = Date.now() + LAUNCH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(2000);
    conn = await connectCdp();
    if (conn) return conn;
  }
  throw new Error('CDPに接続できません（port=' + CDP_PORT + '）');
}

// 統計カード + Referrer表を body text から抽出
function parseBody(bodyText) {
  const out = { views: null, sales: null, total: null, referrers: {} };
  const statRe = /Sales\n(\d+)\nViews\n(\d+)\nTotal\n\$([\d.,]+)/;
  const m = bodyText.match(statRe);
  if (m) {
    out.sales = parseInt(m[1], 10);
    out.views = parseInt(m[2], 10);
    out.total = m[3];
  }
  const refStart = bodyText.indexOf('Referrer\n');
  const refEnd = bodyText.indexOf('\nLocations');
  if (refStart >= 0 && refEnd > refStart) {
    const seg = bodyText.slice(refStart, refEnd);
    for (const line of seg.split('\n')) {
      if (!line.includes('\t')) continue;
      const cols = line.split('\t');
      if (cols.length < 2) continue;
      const src = cols[0].replace(/^[↓↑]\s*/, '').trim();
      const v = parseInt(cols[1], 10);
      if (src && src !== 'Source' && !Number.isNaN(v)) out.referrers[src] = v;
    }
  }
  return out;
}

async function main() {
  const { page } = await ensureChrome();
  if (!page) { console.error('ERROR: タブがありません'); process.exit(2); }
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
  await new Promise((r) => ws.onopen = r);

  const evalJs = async (expr) => {
    const m = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (m.result && m.result.exceptionDetails) return 'EXC: ' + JSON.stringify(m.result.exceptionDetails).slice(0, 200);
    return m.result && m.result.result && m.result.result.value;
  };

  // Cookie注入
  let cookieCount = 0;
  if (fs.existsSync(COOKIE_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(COOKIE_FILE, 'utf-8'));
    for (const c of cookies) {
      if (!c.name || !c.value) continue;
      try {
        await send('Network.setCookie', {
          name: c.name, value: c.value, domain: c.domain || '.gumroad.com',
          path: c.path || '/', secure: c.secure !== false,
          httpOnly: c.httpOnly === true, sameSite: c.sameSite || 'Lax',
          url: 'https://gumroad.com' + (c.path || '/'),
          ...(c.expirationDate ? { expires: c.expirationDate } : {}),
        });
        cookieCount++;
      } catch (e) { /* 個別失敗は無視 */ }
    }
  }
  console.log('Cookie注入: ' + cookieCount);

  await send('Page.enable');
  const target = `https://gumroad.com/dashboard/sales?from=${FROM}&to=${TO}`;
  await send('Page.navigate', { url: target });
  await new Promise((r) => setTimeout(r, NAVIGATION_TIMEOUT));
  const url = await evalJs('location.href');
  console.log('URL:', url);
  if (/\/login/i.test(String(url))) {
    console.log('VIEWS_JSON:' + JSON.stringify({ from: FROM, to: TO, url, login_ok: false, error: 'redirected to login' }));
    try { ws.send(JSON.stringify({ id: ++id, method: 'Browser.close', params: {} })); } catch (e) {}
    process.exit(3);
  }

  const bodyText = String(await evalJs('document.body ? document.body.innerText : ""'));
  const parsed = parseBody(bodyText);
  const loginOk = !/log ?in|sign ?in/i.test(bodyText.slice(0, 200));
  const result = {
    from: FROM, to: TO, url: String(url), login_ok: loginOk,
    views: parsed.views, sales: parsed.sales, total: parsed.total,
    referrers: parsed.referrers,
    collected_at: new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().replace('Z', ''),
  };
  if (parsed.views === null) result.parse_error = 'stat card not found: ' + bodyText.slice(0, 300).replace(/\n/g, ' | ');

  // 履歴へ日次マージ（キー=日付。完全日は上書き、部分日も同一キーで更新）
  try {
    let hist = {};
    if (fs.existsSync(STATE_FILE)) {
      try { hist = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8')); } catch (e) { hist = {}; }
    }
    hist[TO] = {
      views: result.views, sales: result.sales, total: result.total,
      referrers: result.referrers, login_ok: loginOk, collected_at: result.collected_at,
    };
    fs.writeFileSync(STATE_FILE, JSON.stringify(hist, null, 2), 'utf-8');
    result.history_saved = true;
  } catch (e) {
    result.history_saved = false;
    result.history_error = String(e && e.message || e).slice(0, 200);
  }

  console.log('VIEWS_JSON:' + JSON.stringify(result));
  try { ws.send(JSON.stringify({ id: ++id, method: 'Browser.close', params: {} })); } catch (e) {}
  try { ws.close(); } catch (e) {}
  for (let i = 0; i < 10; i++) {
    try { fs.rmSync(CHROME_PROFILE, { recursive: true, force: true }); } catch (e) {}
    if (!fs.existsSync(CHROME_PROFILE)) break;
    await sleep(500);
  }
  process.exit(result.views === null ? 5 : 0);
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });
