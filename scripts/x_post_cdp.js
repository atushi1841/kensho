// x_post_cdp.js — X(Twitter) 投稿ドライバ（Windows Chrome CDP + CDP経由）
// Node.js を PowerShell 経由で実行して Windows Chrome に CDP接続。
// 使い方: node scripts/x_post_cdp.js <tweetBody.txt> <outJson> [--dry-run]
const http = require('http');
const fs = require('fs');
const { execFile } = require('child_process');

const CDP_PORT = parseInt(process.env.X_CDP_PORT || '9250', 10);
const COOKIE_FILE = process.env.X_SESSION_COOKIE || 'D:\\Project2\\kensho\\data\\x_session.json';
const CHROME_EXE = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const CHROME_PROFILE = `C:\\temp\\x-post-${CDP_PORT}-${process.pid}`;
const NAV_TIMEOUT = 20000;
const LAUNCH_TIMEOUT_MS = 45000;
const CDP_HOSTS = ['127.0.0.1', '[::1]'];

const tweetFile = process.argv[2];
const outFile = process.argv[3] || 'C:\\temp\\x_post_out.json';
const hasDryRun = process.argv.includes('--dry-run');

if (!tweetFile || !fs.existsSync(tweetFile)) {
  console.error('usage: node x_post_cdp.js <tweetBody.txt> <outJson> [--dry-run]');
  process.exit(64);
}
const bodyText = fs.readFileSync(tweetFile, 'utf-8').replace(/\r\n/g, '\n').trim();

function getJSON(host, path) {
  return new Promise((resolve, reject) => {
    http.get(`http://${host}:${CDP_PORT}${path}`, (res) => {
      let d = '';
      res.on('data', (c) => (d += c));
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function connectCdp() {
  for (const host of CDP_HOSTS) {
    try {
      const tabs = await getJSON(host, '/json');
      if (Array.isArray(tabs) && tabs.length > 0) {
        const page = tabs.find(t => t.type === 'page' && t.url.startsWith('http'));
        if (page) return { host, page };
      }
    } catch(e) { /* next */ }
  }
  return null;
}

async function ensureChrome() {
  let conn = await connectCdp();
  if (conn) return conn;
  console.log('Launching Chrome on port ' + CDP_PORT);
  try {
    execFile(CHROME_EXE, [
      '--remote-debugging-port=' + CDP_PORT,
      '--user-data-dir=' + CHROME_PROFILE,
      '--no-first-run', '--no-default-browser-check',
      '--headless=new', '--disable-gpu', '--window-size=1280,900',
      'about:blank',
    ], { windowsHide: true, detached: true, stdio: 'ignore' }, () => {});
  } catch (e) {
    console.log('Chrome launch failed: ' + e.message);
  }
  const deadline = Date.now() + LAUNCH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(2000);
    conn = await connectCdp();
    if (conn) return conn;
  }
  throw new Error('CDP unavailable after Chrome launch');
}

async function main() {
  const { page } = await ensureChrome();
  if (!page) { console.error('No tab found'); process.exit(2); }
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
        if (c.name === '__cf_bm') continue; // skip short-lived
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

  // Navigate to compose
  const composeUrl = 'https://x.com/compose/post';
  await send('Page.navigate', { url: composeUrl });
  await sleep(NAV_TIMEOUT);

  const currentUrl = await evalJs('location.href');
  const title = await evalJs('document.title');
  const isLoggedIn = !/log\s*in|sign\s*in/i.test(String(currentUrl) + ' ' + String(title));
  console.log('URL: ' + currentUrl + ' title: ' + title);

  if (!isLoggedIn) {
    const result = { status: 'not_logged_in', url: String(currentUrl), title: String(title), body_chars: bodyText.length };
    fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
    console.log('NOT_LOGGED_IN');
    try { ws.close(); } catch(e) {}
    process.exit(3);
  }

  if (hasDryRun) {
    const result = { dry_run: true, status: 'ok', url: String(currentUrl), title: String(title), body_chars: bodyText.length };
    fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
    console.log('DRY_RUN_OK');
    try { ws.close(); } catch(e) {}
    process.exit(0);
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
  console.log('Click: ' + clickResult);
  await sleep(1500);

  // Insert text
  const chars = bodyText.split('');
  for (const ch of chars) {
    try { await send('Input.insertText', { text: ch }); } catch(e) {}
    await sleep(5 + Math.random() * 15);
  }
  await sleep(1000);

  const textVerify = await evalJs(`
    (async () => {
      const ta = document.querySelector('[data-testid="tweetTextarea_0"]');
      return (ta && ta.value) ? ta.value.length : 0;
    })()
  `);
  console.log('Textarea chars: ' + textVerify);

  // Click tweet button
  const btnResult = await evalJs(`
    (async () => {
      const btn = document.querySelector('[data-testid="tweetButton"]') || document.querySelector('[data-testid="tweetButtonInline"]');
      if (!btn) return 'ERROR:no_button';
      btn.click();
      return 'clicked';
    })()
  `);
  console.log('Tweet button: ' + btnResult);

  // Wait for post
  await sleep(4000);
  const postUrl = await evalJs('location.href');
  const postTitle = await evalJs('document.title');
  console.log('After post URL: ' + postUrl + ' title: ' + postTitle);

  // Extract tweet ID
  let tweetId = null;
  const permalink = String(postUrl);
  const idMatch = permalink.match(/\/status\/(\d+)/);
  if (idMatch) tweetId = idMatch[1];
  console.log('Tweet ID from URL: ' + tweetId);

  // If not in URL, try to find on page or via profile
  if (!tweetId) {
    await sleep(2000);
    const verify = await evalJs(`
      (async () => {
        try {
          const links = Array.from(document.querySelectorAll('a[href^="/status/"]')).slice(0, 3);
          return JSON.stringify(links.map(l => l.href));
        } catch(e) { return 'ERR:' + e.message; }
      })()
    `);
    console.log('Links: ' + verify);
    try {
      const linkArr = JSON.parse(verify);
      if (Array.isArray(linkArr) && linkArr.length > 0) {
        const m = linkArr[0].match(/\/status\/(\d+)/);
        if (m) tweetId = m[1];
      }
    } catch(e) {}
  }

  const handle = await evalJs(`
    (async () => {
      const el = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
      if (!el) return null;
      const text = el.textContent || el.getAttribute('aria-label') || '';
      return text.match(/^@(\w+)/) ? text : null;
    })()
  `);

  const result = {
    status: 'posted',
    handle: handle || 'atushi16',
    body_chars: bodyText.length,
    composed_url: composeUrl,
    final_url: String(postUrl),
    final_title: String(postTitle),
    tweet_id: tweetId,
    permalink: tweetId ? `https://x.com/atushi16/status/${tweetId}` : null,
    cookie_injected: cookieCount,
  };

  fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
  console.log('POSTED status=' + result.status + ' tweet_id=' + tweetId + ' permalink=' + result.permalink);
  try { ws.close(); } catch(e) {}
  // Cleanup
  setTimeout(() => {
    try { fs.rmSync(CHROME_PROFILE, { recursive: true, force: true }); } catch(e) {}
  }, 3000);
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });
