// Gumroad売上データ収集スクリプト（本番版）
// CDP経由でGumroadダッシュボードの売上データを取得し、gumroad_state.jsonに保存する。
// Chrome自動起動対応（cron等からの一発実行用）。
// Cookie: D:\Project2\gumroad-automation\gumroad_cookies.json（約1ヶ月で再エクスポート必要）
// 出力: D:\Project2\kensho\data\gumroad_state.json
const http = require('http');
const fs = require('fs');
const { execFile } = require('child_process');

const CDP_PORT = parseInt(process.env.GUMROAD_CDP_PORT || '9333', 10);
const COOKIE_FILE = 'D:\\Project2\\gumroad-automation\\gumroad_cookies.json';
const STATE_FILE = 'D:\\Project2\\kensho\\data\\gumroad_state.json';
const CHROME_EXE = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
// ユニークプロファイルで起動する（固定プロファイルは既存Chromeにハンドオフされて
// CDP:9333が立たず、node側の起動待ちが90秒を超えてタイムアウトする根因の回避）
const CHROME_PROFILE = `C:\\temp\\gumroad-cdp-${CDP_PORT}-${process.pid}`;
const NAVIGATION_TIMEOUT = 15000;
const LAUNCH_TIMEOUT_MS = 45000; // ① 自動起動後の起動待ち上限（Python側の合計時限240sに収まる）
const CDP_HOSTS = ['127.0.0.1', '[::1]']; // ChromeはIPv4/IPv6どちらにbindしても接続できるよう両対応

function getJSON(host, path) {
  return new Promise((resolve, reject) => {
    http.get(`http://${host}:${CDP_PORT}${path}`, (res) => {
      let d = '';
      res.on('data', (c) => d += c);
      res.on('end', () => {
        try { resolve(JSON.parse(d)); }
        catch(e) { reject(new Error('JSON parse error: ' + d.slice(0,200))); }
      });
    }).on('error', reject);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 対象CDPポートに接続でき、pageタブを返せるか（IPv4/IPv6両方を試す）
async function connectCdp() {
  for (const host of CDP_HOSTS) {
    try {
      const tabs = await getJSON(host, '/json');
      if (Array.isArray(tabs) && tabs.length > 0) {
        const page = tabs.find(t => t.type === 'page' && t.url.startsWith('http')) || tabs.find(t => t.type === 'page');
        if (page) return { host, page };
      }
    } catch(e) { /* そのホストではまだ接続不可 */ }
  }
  return null;
}

// ① 事前CDPチェック → 無ければChrome自動起動 → 起動待ち（最大45秒）
async function ensureChrome() {
  let conn = await connectCdp();
  if (conn) return conn;
  console.log('Chrome起動: port=' + CDP_PORT + ' profile=' + CHROME_PROFILE);
  try {
    execFile(CHROME_EXE, [
      '--remote-debugging-port=' + CDP_PORT,
      '--user-data-dir=' + CHROME_PROFILE,
      '--no-first-run',
      '--no-default-browser-check',
      '--headless=new',
      '--disable-gpu',
      '--window-size=1280,900',
      'about:blank',
    // stdio:'ignore' — Chrome に親の stdout/stderr パイプを継承させない。
    // 継承すると node 終了後も Python の subprocess(capture_output=True) が EOF を待ち、
    // 240s timeout に化ける（実測 2026-09-25 / t_ee5ca962）。
    ], { windowsHide: true, detached: true, stdio: 'ignore' }, () => {});
  } catch(e) {
    console.log('Chrome起動失敗: ' + e.message);
  }
  const deadline = Date.now() + LAUNCH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    await sleep(2000);
    conn = await connectCdp();
    if (conn) return conn;
  }
  throw new Error('Chrome CDPに接続できません（port=' + CDP_PORT + '）');
}

async function main() {
  // 1. Chrome CDP接続（事前チェック→自動起動→起動待ちはensureChrome内で実施）
  const { host, page } = await ensureChrome();
  if (!page) { console.log('ERROR: タブがありません'); process.exit(2); }

  // 2. WebSocket接続
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

  // 3. Cookie注入
  let cookieCount = 0;
  if (fs.existsSync(COOKIE_FILE)) {
    const cookies = JSON.parse(fs.readFileSync(COOKIE_FILE, 'utf-8'));
    for (const c of cookies) {
      if (!c.name || !c.value) continue;
      try {
        const params = {
          name: c.name,
          value: c.value,
          domain: c.domain || '.gumroad.com',
          path: c.path || '/',
          secure: c.secure !== false,
          httpOnly: c.httpOnly === true,
          sameSite: c.sameSite || 'Lax',
          url: 'https://gumroad.com' + (c.path || '/'),
        };
        if (c.expirationDate) params.expires = c.expirationDate;
        await send('Network.setCookie', params);
        cookieCount++;
      } catch(e) { /* 個別失敗は無視 */ }
    }
    console.log('Cookie注入: ' + cookieCount + '/' + cookies.length);
  } else {
    console.log('Cookieファイルなし: ' + COOKIE_FILE);
  }

  // 4. ダッシュボードへ移動
  await send('Page.enable');
  await send('Page.navigate', { url: 'https://gumroad.com/dashboard' });
  await new Promise((r) => setTimeout(r, NAVIGATION_TIMEOUT));
  const url = await evalJs('location.href');
  console.log('Dashboard URL:', url);

  // 5. 売上データ抽出
  const bodyText = await evalJs('document.body ? document.body.innerText : ""');
  let rev = {};
  if (typeof bodyText === 'string') {
    const moneyRe = /\$(\d+(?:\.\d{2})?)/g;
    const balanceIdx = bodyText.indexOf('Balance');
    const totalIdx = bodyText.indexOf('Total earnings');
    rev = {
      balance: null,
      last_7_days: null,
      last_28_days: null,
      total_earnings: null,
      has_login: !/log ?in|sign ?in/i.test(bodyText.slice(0, 200)),
    };
    if (balanceIdx >= 0) {
      const seg = bodyText.slice(balanceIdx, Math.min(balanceIdx + 150, bodyText.length));
      const segMatches = [...seg.matchAll(moneyRe)].map(x => x[1]);
      if (segMatches.length >= 1) rev.balance = segMatches[0];
      if (segMatches.length >= 2) rev.last_7_days = segMatches[1];
      if (segMatches.length >= 3) rev.last_28_days = segMatches[2];
    }
    if (totalIdx >= 0) {
      const seg = bodyText.slice(totalIdx, Math.min(totalIdx + 80, bodyText.length));
      const segMatches = [...seg.matchAll(moneyRe)].map(x => x[1]);
      if (segMatches.length >= 1) rev.total_earnings = segMatches[0];
    }
  } else {
    rev = { raw: String(bodyText).slice(0, 300) };
  }
  console.log('売上データ:', JSON.stringify(rev));

  // 6. Salesページ（Analytics）でも確認
  let salesText = null;
  try {
    await send('Page.navigate', { url: 'https://gumroad.com/dashboard/sales' });
    await new Promise((r) => setTimeout(r, NAVIGATION_TIMEOUT));
    salesText = await evalJs('document.body ? document.body.innerText.slice(0, 3000) : ""');
  } catch(e) { /* 失敗しても続行 */ }

  // 7. gumroad_state.json に保存
  const collectedAt = new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().replace('Z', '');
  const state = {
    state_exists: true,
    sales: 0,
    revenue: 0,
    total_sales: 0,
    total_revenue: rev.total_earnings !== null ? parseFloat(rev.total_earnings) : 0,
    balance_usd: rev.balance !== null ? parseFloat(rev.balance) : null,
    last_7_days_usd: rev.last_7_days !== null ? parseFloat(rev.last_7_days) : null,
    last_28_days_usd: rev.last_28_days !== null ? parseFloat(rev.last_28_days) : null,
    total_earnings_usd: rev.total_earnings !== null ? parseFloat(rev.total_earnings) : null,
    currency: 'USD',
    // 日本時間（JST, UTC+9）のISO 8601表記で保存（他スクリプトのcollected_atと表記統一）
    collected_at: collectedAt,
    last_success_at: collectedAt,
    dashboard_url: url,
    login_ok: rev.has_login !== false,
    sales_page_ok: salesText !== null && salesText.includes('Total'),
  };
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), 'utf-8');
  console.log('保存:', STATE_FILE);
  console.log(JSON.stringify(state, null, 2));

  // 起動したChromeを閉じ、ユニークプロファイルを後始末（ベストエフォート）
  // NOTE (t_ee5ca962): 旧実装は ws.close() → await send('Browser.close') の順で、
  // ①WSを閉じてから応答を待つため await が永久に解決しない ②起動Chrome(detached・unref無し)が
  // イベントループを生かし続ける、の二重で node が自力終了せず毎回240sで打ち切られていた
  // （日次レポートに虚偽の timeout-mark、C:\temp\gumroad-cdp-* も後始末されず蓄積）。
  // → Browser.close は「送信のみ」(応答待ちなし) とし、後始末後に process.exit(0) で明示終了する。
  try { ws.send(JSON.stringify({ id: ++id, method: 'Browser.close', params: {} })); } catch(e) {}
  try { ws.close(); } catch(e) {}
  // プロファイル後始末: WindowsはChromeのファイルハンドル解放に数秒かかる。
  // force:true 1回では EBUSY で消え残る（実測 2026-09-25: 13:11 run が dir を残留/累積30件）ため
  // 最大5秒までリトライし、消えた時点で抜ける（本体の時限240sには十分収まる）。
  for (let i = 0; i < 10; i++) {
    try { fs.rmSync(CHROME_PROFILE, { recursive: true, force: true }); } catch(e) {}
    if (!fs.existsSync(CHROME_PROFILE)) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  console.log('完了');
  process.exit(0);
}

main().catch((e) => { console.error('FATAL:', e.message); process.exit(1); });
