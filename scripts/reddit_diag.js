// reddit_diag.js — 403 の切り分け（読み取り専用。投稿しない）
// 出力: C:\temp\reddit_diag.json
const http = require('http');
const fs = require('fs');
const PORT = parseInt(process.env.REDDIT_CDP_PORT || '9229', 10);
const OUT = 'C:\\temp\\reddit_diag.json';
const SUB = process.argv[2] || 'japanlife';
const TID = process.argv[3] || '';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function httpJson(path) {
  return new Promise((resolve, reject) => {
    http.get('http://127.0.0.1:' + PORT + path, (res) => {
      let d = ''; res.on('data', (c) => (d += c));
      res.on('end', () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

async function main() {
  const tabs = await httpJson('/json');
  const page = tabs.filter((t) => t.type === 'page')[0];
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pending = {};
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending[m.id]) { pending[m.id](m); delete pending[m.id]; } };
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending[i] = res; ws.send(JSON.stringify({ id: i, method, params })); });
  await new Promise((r) => (ws.onopen = r));
  const ev = async (expr) => {
    const m = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    const r = m.result && m.result.result;
    return r ? r.value : null;
  };

  const out = {};

  // 1) セッションとアカウント状態
  out.me = await ev(`fetch('/api/v1/me',{credentials:'include'}).then(r=>r.json()).then(j=>JSON.stringify({
      name:j.name, comment_karma:j.comment_karma, link_karma:j.link_karma,
      is_suspended:j.is_suspended, is_spam:j.is_spam, verified:j.has_verified_email,
      created:j.created_utc, over_18:j.over_18, modhash_present: !!j.modhash, modhash_len:(j.modhash||'').length
    })).catch(e=>'ERR '+e)`);

  // 2) csrf の取得可否（document.cookie から読めるか）
  out.csrf = await ev(`(document.cookie.match(/csrf_token=([^;]+)/)||['',''])[1].length`);
  out.cookie_names = await ev(`document.cookie.split('; ').map(s=>s.split('=')[0]).join(',')`);

  // 3) その板での自分の立場（ban/mute/購読）
  out.sub_about = await ev(`fetch('/r/${SUB}/about.json',{credentials:'include'}).then(r=>r.json()).then(j=>{
      const d=j.data||{};
      return JSON.stringify({subreddit_type:d.subreddit_type, user_is_banned:d.user_is_banned,
        user_is_muted:d.user_is_muted, user_is_subscriber:d.user_is_subscriber,
        user_is_contributor:d.user_is_contributor, restrict_posting:d.restrict_posting,
        quarantine:d.quarantine, over18:d.over18, subscribers:d.subscribers});
    }).catch(e=>'ERR '+e)`);

  // 4) 対象スレが実在するか（読み取りのみ）
  if (TID) {
    out.thread = await ev(`fetch('/r/${SUB}/comments/${TID}.json?limit=1',{credentials:'include'}).then(async r=>{
        const t = await r.text();
        let j=null; try{j=JSON.parse(t);}catch(e){}
        if(!j) return 'HTTP '+r.status+' non-json '+t.slice(0,120);
        const p = j[0].data.children[0].data;
        return JSON.stringify({id:p.id, subreddit:p.subreddit, locked:p.locked, archived:p.archived,
          removed:p.removed, author_flair:!!p.author_flair_text, title:p.title.slice(0,60)});
      }).catch(e=>'ERR '+e)`);
  }

  // 5) 現在ページのURL（ナビゲーションが実際にどこへ着地したか）
  out.location = await ev('location.href');

  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log('DIAG_OK');
  ws.close();
}
main().catch((e) => { console.error('ERR ' + (e && e.message)); process.exit(1); });
