// gumroad_update_cdp.js — Gumroad 商品(agyhq)のファイル(ZIP)差し替え（CDP版 v2）
//
// 使い方（Windows側 node）:
//   node gumroad_update_cdp.js <zipPath(Windows形式)> [cookies.json]
//
// v2 (2026-10-04): sales_collect.js と同一の起動方式へ統一。
//   旧版(C:/temp のみ・正本なし)は 9222 固定プロファイル + Network.setCookies(domain指定) で、
//   cookie が有効でも /login へリダイレクトされ続けた（実測: sales_collect は同 cookie で成功）。
//   原因は (a) 固定プロファイルの残留状態 (b) setCookie の url 未指定。
//   → ユニークプロファイル + --headless=new + setCookie(url付き) に変更。
const http = require('http');
const fs = require('fs');
const { execFile } = require('child_process');

const CDP_PORT = parseInt(process.env.GUMROAD_UPDATE_CDP_PORT || '9444', 10);
const COOKIE_FILE = process.env.GUMROAD_COOKIE_FILE || 'D:\\Project2\\gumroad-automation\\gumroad_cookies.json';
const CHROME_EXE = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const CHROME_PROFILE = 'C:\\temp\\gumroad-cdp-update-' + CDP_PORT + '-' + process.pid;
const PRODUCT_URL = process.env.GUMROAD_PRODUCT_URL || 'https://gumroad.com/products/agyhq/edit/content';
const NAV_TIMEOUT = 15000;
const LAUNCH_TIMEOUT_MS = 45000;
const CDP_HOSTS = ['127.0.0.1', '[::1]'];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function getJSON(host, path) {
  return new Promise((resolve, reject) => {
    http.get('http://' + host + ':' + CDP_PORT + path, (res) => {
      let d = '';
      res.on('data', (c) => d += c);
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(new Error('JSON parse: ' + d.slice(0, 200))); } });
    }).on('error', reject);
  });
}

async function connectCdp() {
  for (const host of CDP_HOSTS) {
    try {
      const tabs = await getJSON(host, '/json');
      if (Array.isArray(tabs) && tabs.length > 0) {
        const page = tabs.find(t => t.type === 'page' && t.url.startsWith('http')) || tabs.find(t => t.type === 'page');
        if (page) return { host, page };
      }
    } catch (e) {}
  }
  return null;
}

async function ensureChrome() {
  let conn = await connectCdp();
  if (conn) return conn;
  console.log('Chrome起動: port=' + CDP_PORT + ' profile=' + CHROME_PROFILE);
  try {
    execFile(CHROME_EXE, [
      '--remote-debugging-port=' + CDP_PORT,
      '--user-data-dir=' + CHROME_PROFILE,
      '--no-first-run', '--no-default-browser-check',
      '--headless=new', '--disable-gpu', '--window-size=1280,900', 'about:blank',
    ], { windowsHide: true, detached: true, stdio: 'ignore' }, () => {});
  } catch (e) { console.log('Chrome起動失敗: ' + e.message); }
  const deadline = Date.now() + LAUNCH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(2000);
    conn = await connectCdp();
    if (conn) return conn;
  }
  throw new Error('Chrome CDPに接続できません（port=' + CDP_PORT + '）');
}

async function main() {
  const zipPath = process.argv[2];
  const cookiePath = process.argv[3] || COOKIE_FILE;
  const VERIFY_ONLY = process.env.GUMROAD_VERIFY_ONLY === '1' || process.argv.includes('--verify');
  if (!VERIFY_ONLY) {
    if (!zipPath || !fs.existsSync(zipPath)) { console.log('[ERR] ZIP指定なし or 存在せず: ' + zipPath); process.exit(1); }
    console.log('[ZIP]', zipPath, Math.floor(fs.statSync(zipPath).size / 1024) + 'KB');
  }

  const { page } = await ensureChrome();
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = {};
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending[m.id]) { pending[m.id](m); delete pending[m.id]; } };
  const send = (method, params = {}) => new Promise((resolve) => { const mid = ++id; pending[mid] = resolve; ws.send(JSON.stringify({ id: mid, method, params })); });
  await new Promise((r) => ws.onopen = r);
  const evalJs = async (expr) => {
    const m = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (m.result && m.result.exceptionDetails) return 'EXC: ' + JSON.stringify(m.result.exceptionDetails).slice(0, 200);
    return m.result && m.result.result && m.result.result.value;
  };

  await send('Page.enable');
  await send('Network.enable');

  if (fs.existsSync(cookiePath)) {
    const raw = JSON.parse(fs.readFileSync(cookiePath, 'utf-8'));
    const cks = Array.isArray(raw) ? raw : (raw.cookies || []);
    let n = 0;
    for (const c of cks) {
      if (!c.name || !c.value) continue;
      try {
        const params = {
          name: c.name, value: c.value,
          domain: c.domain || '.gumroad.com', path: c.path || '/',
          secure: c.secure !== false, httpOnly: c.httpOnly === true,
          sameSite: c.sameSite || 'Lax',
          url: 'https://gumroad.com' + (c.path || '/'),
        };
        if (c.expirationDate) params.expires = c.expirationDate;
        await send('Network.setCookie', params);
        n++;
      } catch (e) {}
    }
    console.log('[COOKIES]', n + '/' + cks.length, 'from', cookiePath);
  } else { console.log('[COOKIES] file not found:', cookiePath); }

  await send('Page.navigate', { url: PRODUCT_URL });
  for (let i = 0; i < 20; i++) { await sleep(1500); const st = await evalJs('document.readyState'); if (st === 'complete') break; }
  await sleep(4000);
  const info = await evalJs('location.href + " | " + document.title');
  console.log('[PAGE]', info);
  if (/\/login|\/sign_in|\/signin/i.test(String(info))) {
    console.log('[ERR] セッション失効。cookieの再取得が必要');
    try { ws.close(); } catch (e) {}
    process.exit(2);
  }

  const doc = await send('DOM.getDocument');
  const node = await send('DOM.querySelector', { nodeId: doc.result.root.nodeId, selector: "input[type='file']" });
  if (!node.result || !node.result.nodeId) {
    console.log('[ERR] file input不在');
    try { ws.close(); } catch (e) {}
    process.exit(3);
  }
  if (VERIFY_ONLY) {
    const cur = await evalJs("(() => { const t=document.body?document.body.innerText:''; const m=t.match(/[\\w.-]+\\.zip|[\\d.]+\\s?(KB|MB|kB)/gi)||[]; const f=document.querySelector(\"input[type='file']\"); const fn=f&&f.files&&f.files[0]?f.files[0].name+'|'+f.files[0].size:''; return 'hits='+m.slice(0,8).join(',')+' input='+fn+' textlen='+t.length; })()");
    console.log('[VERIFY]', cur);
    try { ws.send(JSON.stringify({ id: ++id, method: 'Browser.close', params: {} })); } catch (e) {}
    try { ws.close(); } catch (e) {}
    for (let i = 0; i < 10; i++) { try { fs.rmSync(CHROME_PROFILE, { recursive: true, force: true }); } catch (e) {} if (!fs.existsSync(CHROME_PROFILE)) break; await sleep(500); }
    process.exit(0);
  }
  await send('DOM.setFileInputFiles', { files: [zipPath], nodeId: node.result.nodeId });
  console.log('[SET FILES] 完了、アップロード待ち...');
  await sleep(25000);

  const saveBtn = await evalJs("(() => { const btns = [...document.querySelectorAll('button, input[type=submit]')]; const b = btns.find((x) => /^(save|update|publish)/i.test((x.textContent || x.value || '').trim())); if (b) { b.click(); return 'clicked: ' + (b.textContent || b.value).trim(); } return 'no save button (auto-save?)'; })()");
  console.log('[SAVE]', saveBtn);
  await sleep(8000);
  console.log('[AFTER]', await evalJs('location.href + " | " + document.title'));

  try { ws.send(JSON.stringify({ id: ++id, method: 'Browser.close', params: {} })); } catch (e) {}
  try { ws.close(); } catch (e) {}
  for (let i = 0; i < 10; i++) { try { fs.rmSync(CHROME_PROFILE, { recursive: true, force: true }); } catch (e) {} if (!fs.existsSync(CHROME_PROFILE)) break; await sleep(500); }
  console.log('完了');
  process.exit(0);
}
main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });
