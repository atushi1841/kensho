// x_post_v2.js — X(Twitter) 投稿 V2: Draft.js + proper editor interaction
const http = require('http');
const fs = require('fs');

const PORT = 9252;
const COOKIE_FILE = 'D:\\Project2\\kensho\\data\\x_session.json';
const OUT_FILE = 'D:\\temp\\x_post_out_v2.json';
const SCREENSHOT_FILE = 'D:\\temp\\x_post_screenshot_v2.png';

const bodyText = `日本オークション市場の価格モニタリング、今週も更新。
Mandarake Auction で仕入れ判断・在庫評価を自動化。
初期費用ゼロで開始 https://apify.com/fruitful_quintessence/mandarake-auction-scraper #まんだらけ #オークション
📊 週次分析（無料サンプル）: https://atushi5.gumroad.com/l/kutuxe`;

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
  const page = tabs.find(t => t.type === 'page');
  if (!page) { console.log('No page'); process.exit(2); }
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

  // Navigate to compose
  await send('Page.navigate', { url: 'https://x.com/compose/post' });
  await sleep(12000);
  
  const currentUrl = await evalJs('location.href');
  const title = await evalJs('document.title');
  console.log('URL:', currentUrl);
  console.log('Title:', title);
  
  // Wait for page load
  await sleep(3000);

  // Get editor state
  const editorState = await evalJs(`
    (async () => {
      const ta = document.querySelector('[data-testid="tweetTextarea_0"]');
      if (!ta) return { error: 'no_editor' };
      
      // Check if Draft.js
      const editorKey = ta.getAttribute('data-editor');
      const editorState = window.__CURRENT_EDITOR_STATE__ || null;
      
      // Try to get text content
      const textContent = ta.innerText || ta.textContent || '';
      
      // Check tweet button state
      const btn = document.querySelector('[data-testid="tweetButton"]') || 
                  document.querySelector('[data-testid="tweetButtonInline"]');
      const btnDisabled = btn ? btn.disabled : true;
      
      // Try Draft.js API
      let draftContent = null;
      try {
        const Draft = window.Draft;
        if (Draft && ta._wrapperNode) {
          const instance = ta._wrapperNode._instance;
          if (instance && instance.editorState) {
            draftContent = instance.editorState.getCurrentContent().getPlainText();
          }
        }
      } catch(e) {}
      
      return {
        found: true,
        editorKey: editorKey,
        textLen: textContent.length,
        textPreview: textContent.slice(0, 50),
        btnDisabled: btnDisabled,
        btnExists: !!btn,
        draftContent: draftContent,
        innerHTML: (ta.innerHTML || '').slice(0, 200),
      };
    })()
  `);
  console.log('Editor state:', JSON.stringify(editorState, null, 2));

  // Try different text insertion methods
  const insertResult = await evalJs(`
    (async () => {
      const ta = document.querySelector('[data-testid="tweetTextarea_0"]');
      if (!ta) return { error: 'no_ta' };
      
      // Method 1: Dispatch input event after setting textContent
      ta.innerText = ''' + bodyText.replace(/'/g, "\\'") + ''';
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      ta.dispatchEvent(new Event('change', { bubbles: true }));
      
      // Method 2: Also try DOMDelta injection for Draft.js
      try {
        if (ta._wrapperNode && ta._wrapperNode._instance) {
          const instance = ta._wrapperNode._instance;
          const editorState = instance.editorState;
          const contentState = editorState.getCurrentContent();
          const selectionState = editorState.getSelection();
          
          // Insert text at current selection
          const newContent = contentState.replaceText(
            selectionState,
            ''' + bodyText.replace(/'/g, "\\'") + ''',
            'insert-char'
          );
          const newEditorState = window.__CURRENT_EDITOR_STATE__ || 
            (window.Draft ? window.Draft.EditorState.createWithContent(newContent) : null);
          
          if (newEditorState) {
            instance.props.onChange(newEditorState);
          }
        }
      } catch(e) {}
      
      // Method 3: Simulate keyboard events character by character
      // This triggers the actual input handler
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      nativeInputValueSetter.call(ta, ''' + bodyText.replace(/'/g, "\\'") + ''');
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      
      // Also set data attribute if exists
      if (ta.dataset && ta.dataset.testid) {
        ta.setAttribute('data-value', ''' + bodyText.replace(/'/g, "\\'") + ''');
      }
      
      const afterText = ta.innerText || ta.textContent || '';
      return {
        inserted: afterText.length,
        preview: afterText.slice(0, 80),
        innerHTMLLen: (ta.innerHTML || '').length,
      };
    })()
  `);
  console.log('Insert result:', JSON.stringify(insertResult));

  await sleep(1500);
  
  // Verify text
  const verify = await evalJs(`
    (async () => {
      const ta = document.querySelector('[data-testid="tweetTextarea_0"]');
      if (!ta) return { error: 'no_ta' };
      return {
        textLen: (ta.innerText || ta.textContent || '').length,
        valueLen: (ta.value || '').length,
        innerHTMLLen: (ta.innerHTML || '').length,
        class: ta.className,
        hasDraft: !!ta._wrapperNode,
      };
    })()
  `);
  console.log('Verify:', JSON.stringify(verify));

  // Try to click tweet button
  const btnResult = await evalJs(`
    (async () => {
      const btn = document.querySelector('[data-testid="tweetButton"]') || 
                  document.querySelector('[data-testid="tweetButtonInline"]');
      if (!btn) return { error: 'no_button' };
      
      console.log('Button disabled:', btn.disabled);
      console.log('Button class:', btn.className);
      console.log('Button aria-disabled:', btn.getAttribute('aria-disabled'));
      
      // If disabled, try to enable it
      if (btn.disabled) {
        btn.disabled = false;
        btn.removeAttribute('aria-disabled');
        console.log('Enabled button');
      }
      
      btn.click();
      return 'clicked';
    })()
  `);
  console.log('Btn result:', btnResult);

  // Wait for post
  await sleep(6000);
  
  const postUrl = await evalJs('location.href');
  const postTitle = await evalJs('document.title');
  console.log('After post URL:', postUrl);
  console.log('After post title:', postTitle);

  // Take screenshot
  try {
    const shotResult = await send('Page.captureScreenshot', { format: 'png' });
    if (shotResult.result && shotResult.result.data) {
      const buf = Buffer.from(shotResult.result.data, 'base64');
      fs.writeFileSync(SCREENSHOT_FILE, buf);
      console.log('Screenshot saved: ' + SCREENSHOT_FILE);
    }
  } catch(e) { console.log('Screenshot failed:', e.message); }

  // Extract tweet ID
  let tweetId = null;
  const idMatch = String(postUrl).match(/\/status\/(\d+)/);
  if (idMatch) tweetId = idMatch[1];
  console.log('Tweet ID:', tweetId);

  // Check for tweet links
  if (!tweetId) {
    await sleep(2000);
    const links = await evalJs(`
      (async () => {
        const allLinks = Array.from(document.querySelectorAll('a[href]'));
        const statusLinks = allLinks.filter(l => l.href.includes('/status/')).slice(0, 5);
        return JSON.stringify(statusLinks.map(l => l.href));
      })()
    `);
    console.log('Status links:', links);
    try {
      const arr = JSON.parse(links);
      if (Array.isArray(arr) && arr.length > 0) {
        const m = arr[0].match(/\/status\/(\d+)/);
        if (m) tweetId = m[1];
      }
    } catch(e) {}
  }

  // Get handle
  const handle = await evalJs(`
    (async () => {
      const el = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
      if (!el) return null;
      return el.textContent.trim() || el.getAttribute('aria-label') || null;
    })()
  `);
  console.log('Handle:', handle);

  const result = {
    status: tweetId ? 'posted' : 'post_failed',
    handle: handle || 'atushi16',
    body_chars: bodyText.length,
    final_url: String(postUrl),
    tweet_id: tweetId,
    permalink: tweetId ? `https://x.com/atushi16/status/${tweetId}` : null,
    cookie_count: cookieCount,
    screenshot: SCREENSHOT_FILE,
    verify: JSON.stringify(verify),
    insert_result: JSON.stringify(insertResult),
  };
  
  fs.writeFileSync(OUT_FILE, JSON.stringify(result, null, 2));
  console.log('RESULT:', JSON.stringify(result, null, 2));
  
  try { ws.close(); } catch(e) {}
  process.exit(0);
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });