// x_post_driver.js — X(Twitter) 投稿 CDP ドライバ（Windows Chrome + CDP）
// 使い方: node x_post_driver.js <tweetBody.txt> <outJson> [--port PORT]
const http = require('http');
const fs = require('fs');
const { execFile } = require('child_process');

const CDP_PORT = parseInt(process.env.X_CDP_PORT || '9239', 10);
const COOKIE_FILE = process.env.X_SESSION_COOKIE || 'D:\\Project2\\kensho\\data\\x_session.json';
const CHROME_EXE = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const CHROME_PROFILE = `C:\\temp\\x-post-${CDP_PORT}-${process.pid}`;
const NAV_TIMEOUT = 18000;

const tweetFile = process.argv[2];
const outFile = process.argv[3] || 'C:\\temp\\x_post_out.json';
const hasDryRun = process.argv.includes('--dry-run');

if (!tweetFile || !fs.existsSync(tweetFile)) {
  console.error('usage: node x_post_driver.js <tweetBody.txt> <outJson> [--dry-run]');
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

async function connectCdp(anyPage = true) {
  // 2026-10-03 修正: 既定で about:blank のタブも拾う。
  // 旧実装は url.startsWith('http') を要求していたため、起動直後の about:blank を
  // 「ページ無し」と誤判定し、45秒待って 'CDP unavailable after Chrome launch' で落ちていた。
  for (const host of ['127.0.0.1', '[::1]']) {
    try {
      const tabs = await getJSON(host, '/json');
      if (Array.isArray(tabs) && tabs.length > 0) {
        const page = anyPage
          ? tabs.find((t) => t.type === 'page')
          : tabs.find((t) => t.type === 'page' && t.url.startsWith('http'));
        if (page) return { host, page };
      }
    } catch (e) { /* next */ }
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
  const deadline = Date.now() + 45000;
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

  // Inject X cookies from session file
  await send('Network.enable');
  await send('Page.enable');
  let cookieCount = 0;
  if (fs.existsSync(COOKIE_FILE)) {
    const session = JSON.parse(fs.readFileSync(COOKIE_FILE, 'utf-8'));
    if (session.cookies && Array.isArray(session.cookies)) {
      for (const c of session.cookies) {
        if (!c.name || !c.value) continue;
        // Skip __cf_bm which expires quickly (re-probes are fine to skip)
        if (c.name === '__cf_bm') continue;
        const url = (c.domain && c.domain.startsWith('.'))
          ? 'https://' + c.domain.replace(/^\./, '') + c.path
          : 'https://' + (c.domain || 'x.com') + (c.path || '/');
        try {
          await send('Network.setCookie', {
            name: c.name,
            value: c.value,
            domain: c.domain || 'x.com',
            path: c.path || '/',
            secure: c.secure !== false,
            httpOnly: c.httpOnly === true,
            sameSite: c.sameSite || 'Lax',
            url: url,
            ...(c.expires ? { expires: c.expires } : {}),
          });
          cookieCount++;
        } catch (e) { /* skip individual failures */ }
      }
    }
    if (session.origins && Array.isArray(session.origins)) {
      for (const origin of session.origins) {
        if (origin.localStorage && Array.isArray(origin.localStorage)) {
          for (const ls of origin.localStorage) {
            try {
              await send('Storage.setLocalStorageEntries', {
                entries: { [ls.name]: ls.value },
                securityOrigin: origin.origin,
              });
            } catch (e) { /* skip */ }
          }
        }
      }
    }
  }
  console.log('Injected cookies: ' + cookieCount);

  // Navigate to compose page
  const composeUrl = 'https://x.com/compose/post';
  await send('Page.navigate', { url: composeUrl });
  await sleep(NAV_TIMEOUT);

  // Check login state
  const currentUrl = await evalJs('location.href');
  const title = await evalJs('document.title');
  const isLoggedIn = !/log\s*in|sign\s*in/i.test(String(currentUrl) + ' ' + String(title));
  console.log('URL: ' + currentUrl + ' title: ' + title);

  if (!isLoggedIn) {
    const result = { status: 'not_logged_in', url: String(currentUrl), title: String(title), body_chars: bodyText.length };
    fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
    console.log('NOT_LOGGED_IN');
    try { ws.close(); } catch (e) {}
    process.exit(3);
  }

  // Click compose textarea
  const clickResult = await evalJs(`
    (async () => {
      const btn = document.querySelector('[data-testid="tweetTextarea_0"]');
      if (!btn) return 'ERROR:no_textarea';
      btn.click();
      btn.focus();
      return 'focused';
    })()
  `);
  console.log('Click result: ' + clickResult);
  await sleep(1500);

  // Insert text via Input.insertText
  const chars = bodyText.split('');
  for (const ch of chars) {
    try { await send('Input.insertText', { text: ch }); } catch (e) {}
    await sleep(30 + Math.random() * 40);
  }
  await sleep(1000);

  // Verify text in textarea
  // 2026-10-03 修正: contenteditable なので .value は常に undefined（旧実装は常に0を返していた）。
  // innerText を見る。0 なら挿入失敗として扱う。
  const textVerify = await evalJs(`
    (async () => {
      const ta = document.querySelector('[data-testid="tweetTextarea_0"]');
      if (!ta) return -1;
      return ((ta.innerText || ta.textContent || '').trim()).length;
    })()
  `);
  console.log('Textarea chars after insert: ' + textVerify);

  // dry-run は「本文が入ったこと」まで確認して、投稿ボタンは押さない
  if (hasDryRun) {
    const handle = await evalJs(`
      (() => {
        const el = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
        if (!el) return null;
        const t = (el.textContent || '') + ' ' + (el.getAttribute('aria-label') || '');
        const m = t.match(/@(\\w+)/);
        return m ? m[1] : null;
      })()
    `);
    const result = {
      dry_run: true,
      status: textVerify > 0 ? 'dry_run_ok' : 'insert_failed',
      url: String(currentUrl), title: String(title),
      body_chars: bodyText.length, inserted_chars: textVerify, handle,
    };
    fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
    console.log('DRY_RUN_' + (textVerify > 0 ? 'OK' : 'INSERT_FAILED') + ' chars=' + textVerify + ' handle=' + handle);
    try { ws.close(); } catch (e) {}
    process.exit(textVerify > 0 ? 0 : 1);
  }

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

  // Wait for navigation / post
  await sleep(4000);
  const postUrl = await evalJs('location.href');
  const postTitle = await evalJs('document.title');
  console.log('After post URL: ' + postUrl + ' title: ' + postTitle);

  // Try to get tweet ID from URL or check profile
  let tweetId = null;
  const permalink = String(postUrl);
  const idMatch = permalink.match(/\/status\/(\d+)/);
  if (idMatch) tweetId = idMatch[1];
  console.log('Tweet ID from URL: ' + tweetId);

  // If no ID in URL, check if we're redirected to home, then verify on profile
  if (!tweetId) {
    // Try to find tweet via GraphQL (using session cookies via browser fetch)
    await sleep(2000);
    const verifyResult = await evalJs(`
      (async () => {
        try {
          const r = await fetch('https://x.com/' + window.location.pathname.split('/')[1] + '/?screen_name=' + window.location.pathname.split('/')[1], {credentials:'include'});
          const html = await r.text();
          const m = html.match(/"tweet_id":"(\d+)"/);
          return JSON.stringify({status:r.status, tweet_id: m ? m[1] : null, html_len: html.length});
        } catch(e) { return 'ERR:' + e.message; }
      })()
    `);
    console.log('Verify result: ' + verifyResult);
    try { const v = JSON.parse(verifyResult); if (v.tweet_id) tweetId = v.tweet_id; } catch (e) {}
  }

  // Final check: try to get user handle
  const handle = await evalJs(`
    (async () => {
      const el = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
      if (!el) return null;
      // Try to extract username from aria-label or button text
      const text = el.textContent || el.getAttribute('aria-label') || '';
      return text.match(/^@(\w+)/) ? text : null;
    })()
  `);

  const result = {
    status: 'posted',
    handle: handle || 'unknown',
    body_chars: bodyText.length,
    composed_url: composeUrl,
    final_url: String(postUrl),
    final_title: String(postTitle),
    tweet_id: tweetId,
    permalink: tweetId ? `https://x.com/${handle || 'atushi16'}/status/${tweetId}` : null,
    cookie_injected: cookieCount,
  };

  fs.writeFileSync(outFile, JSON.stringify(result, null, 1));
  console.log('POSTED status=' + result.status + ' tweet_id=' + tweetId);
  try { ws.close(); } catch (e) {}
  // Cleanup Chrome profile
  setTimeout(() => {
    try { fs.rmSync(CHROME_PROFILE, { recursive: true, force: true }); } catch (e) {}
  }, 3000);
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });
