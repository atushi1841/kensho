// x_post_test.js — Minimal CDP test to verify Chrome connectivity from Windows side
const http = require('http');
const fs = require('fs');

const PORT = 9252;
const COOKIE_FILE = 'D:\\Project2\\kensho\\data\\x_session.json';

function getJSON(path) {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${PORT}${path}`, (res) => {
      let d = '';
      res.on('data', (c) => (d += c));
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const tabs = await getJSON('/json');
  console.log('Tabs:', tabs.length);
  const page = tabs.find(t => t.type === 'page');
  if (!page) { console.log('No page tab'); process.exit(2); }
  console.log('Page:', page.url);
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
  console.log('WS connected');

  const evalJs = async (expr) => {
    const m = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (m.result && m.result.exceptionDetails) return 'EXC: ' + JSON.stringify(m.result.exceptionDetails).slice(0, 300);
    return m.result && m.result.result && m.result.result.value;
  };

  // Inject cookies
  await send('Network.enable');
  await send('Page.enable');
  let cookieCount = 0;
  if (fs.existsSync(COOKIE_FILE)) {
    const session = JSON.parse(fs.readFileSync(COOKIE_FILE, 'utf-8'));
    if (session.cookies && Array.isArray(session.cookies)) {
      for (const c of session.cookies) {
        if (!c.name || !c.value) continue;
        if (c.name === '__cf_bm') continue;
        const domain = c.domain || 'x.com';
        const url = (c.domain && c.domain.startsWith('.'))
          ? 'https://' + c.domain.replace(/^\./, '') + (c.path || '/')
          : 'https://' + domain + (c.path || '/');
        try {
          await send('Network.setCookie', {
            name: c.name, value: c.value,
            domain: domain, path: c.path || '/',
            secure: c.secure !== false,
            httpOnly: c.httpOnly === true,
            sameSite: c.sameSite || 'Lax',
            url: url,
            ...(c.expires ? { expires: c.expires } : {}),
          });
          cookieCount++;
        } catch(e) { /* skip */ }
      }
    }
    if (session.origins && Array.isArray(session.origins)) {
      for (const origin of session.origins) {
        if (origin.localStorage) {
          for (const ls of origin.localStorage) {
            try {
              await send('Storage.setLocalStorageEntries', {
                entries: { [ls.name]: ls.value },
                securityOrigin: origin.origin,
              });
            } catch(e) { /* skip */ }
          }
        }
      }
    }
  }
  console.log('Cookies injected: ' + cookieCount);

  // Navigate to compose page
  const url = 'https://x.com/compose/post';
  await send('Page.navigate', { url });
  await sleep(15000);

  const currentUrl = await evalJs('location.href');
  const title = await evalJs('document.title');
  console.log('URL:', currentUrl);
  console.log('Title:', title);
  const isLoggedIn = !/log\s*in|sign\s*in/i.test(String(currentUrl) + ' ' + String(title));
  console.log('Logged in:', isLoggedIn);

  if (!isLoggedIn) {
    console.log('NOT_LOGGED_IN - cannot post');
    try { ws.close(); } catch(e) {}
    process.exit(3);
  }

  // Click textarea
  const clickResult = await evalJs(`
    (async () => {
      const btn = document.querySelector('[data-testid="tweetTextarea_0"]');
      if (!btn) return 'ERROR:no_textarea';
      btn.click(); btn.focus();
      return 'focused';
    })()
  `);
  console.log('Click:', clickResult);
  await sleep(1500);

  // Insert text
  const bodyText = `日本オークション市場の価格モニタリング、今週も更新。
Mandarake Auction で仕入れ判断・在庫評価を自動化。
初期費用ゼロで開始 https://apify.com/fruitful_quintessence/mandarake-auction-scraper #まんだらけ #オークション
📊 週次分析（無料サンプル）: https://atushi5.gumroad.com/l/kutuxe`;

  const chars = bodyText.split('');
  for (const ch of chars) {
    try { await send('Input.insertText', { text: ch }); } catch(e) {}
    await sleep(5 + Math.random() * 15);
  }
  await sleep(1500);

  const textVerify = await evalJs(`
    (async () => {
      const ta = document.querySelector('[data-testid="tweetTextarea_0"]');
      return (ta && ta.value) ? ta.value.length : 0;
    })()
  `);
  console.log('Textarea chars:', textVerify);

  // Click tweet button
  const btnResult = await evalJs(`
    (async () => {
      const btn = document.querySelector('[data-testid="tweetButton"]') || document.querySelector('[data-testid="tweetButtonInline"]');
      if (!btn) return 'ERROR:no_button';
      btn.click();
      return 'clicked';
    })()
  `);
  console.log('Tweet button:', btnResult);

  // Wait for navigation
  await sleep(5000);
  const postUrl = await evalJs('location.href');
  const postTitle = await evalJs('document.title');
  console.log('After post URL:', postUrl);
  console.log('After post title:', postTitle);

  // Extract tweet ID
  let tweetId = null;
  const idMatch = String(postUrl).match(/\/status\/(\d+)/);
  if (idMatch) tweetId = idMatch[1];
  console.log('Tweet ID:', tweetId);

  // Get handle
  const handle = await evalJs(`
    (async () => {
      const el = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
      if (!el) return null;
      const text = el.textContent || el.getAttribute('aria-label') || '';
      const m = text.match(/^@(\w+)/);
      return m ? '@' + m[1] : null;
    })()
  `);
  console.log('Handle:', handle);

  const result = {
    status: 'posted',
    handle: handle || 'atushi16',
    final_url: String(postUrl),
    tweet_id: tweetId,
    permalink: tweetId ? `https://x.com/atushi16/status/${tweetId}` : null,
  };
  console.log('RESULT:', JSON.stringify(result, null, 2));
  try { ws.close(); } catch(e) {}
  process.exit(0);
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });