// kensho_apify_console.js — Apify Console の画面内容を CDP 経由で読み取るドライバ
// 使い方: node kensho_apify_console.js <url> <outJsonPath> [--screenshot <pngPath>]
// Windows 側で実行する（WSL からは 127.0.0.1:9222 に到達できないため）。
// 生 WebSocket で CDP を叩く（puppeteer 非依存）。
const http = require('http');
const fs = require('fs');

const PORT = 9222;
const url = process.argv[2];
const outJson = process.argv[3] || 'C:\\temp\\apify_console_out.json';
const shotIdx = process.argv.indexOf('--screenshot');
const shotPath = shotIdx > 0 ? process.argv[shotIdx + 1] : null;

function httpJson(path) {
  return new Promise((resolve, reject) => {
    http.get('http://127.0.0.1:' + PORT + path, (res) => {
      let d = '';
      res.on('data', (c) => (d += c));
      res.on('end', () => {
        try { resolve(JSON.parse(d)); } catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const tabs = await httpJson('/json');
  const pages = tabs.filter((t) => t.type === 'page');
  if (!pages.length) { throw new Error('no page target'); }
  const page = pages[0];

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
      return 'EXC: ' + JSON.stringify(m.result.exceptionDetails).slice(0, 300);
    }
    return m.result && m.result.result && m.result.result.value;
  };

  await send('Page.enable');
  await send('Page.navigate', { url });
  await sleep(6000);

  // SPA の描画待ち（本文が空なら少し待つ）
  let text = '';
  for (let i = 0; i < 6; i++) {
    text = (await evalJs('document.body ? document.body.innerText : ""')) || '';
    if (text.trim().length > 40) break;
    await sleep(3000);
  }

  const finalUrl = await evalJs('location.href');
  const title = await evalJs('document.title');
  const info = {
    requested_url: url,
    final_url: finalUrl,
    title: title,
    logged_in: !/log ?[-_]?in|sign ?[-_]?in|sign ?[-_]?up|auth\.apify/i.test(
      String(finalUrl) + ' ' + String(title)
    ),
    body_len: text.length,
    body_text: text.slice(0, 20000),
    links: await evalJs(`JSON.stringify(Array.from(document.querySelectorAll('a')).map(a=>a.innerText.trim()).filter(Boolean).slice(0,80))`),
  };

  if (shotPath) {
    const m = await send('Page.captureScreenshot', { format: 'png' });
    const data = m.result && m.result.data;
    if (data) { fs.writeFileSync(shotPath, Buffer.from(data, 'base64')); info.screenshot = shotPath; }
  }

  fs.writeFileSync(outJson, JSON.stringify(info, null, 1));
  console.log('OK ' + outJson + ' final_url=' + info.final_url);
  ws.close();
}

main().catch((e) => { console.error('ERR ' + (e && e.message)); process.exit(1); });
