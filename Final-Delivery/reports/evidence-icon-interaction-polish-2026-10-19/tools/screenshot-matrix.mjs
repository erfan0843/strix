// Screenshot matrix for the icon/interaction polish phase.
// Usage: TAG=before|after FORM_ID=... node _shots.mjs  → /tmp/qa/icons/<TAG>/<page>-<w>x<h>-<theme>.png
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000';
const TAG = process.env.TAG || 'before';
const FORM = process.env.FORM_ID || '';
const OUT = `/tmp/qa/icons/${TAG}`; fs.mkdirSync(OUT, { recursive: true });
const VPS = [[360, 800], [390, 844], [768, 1024], [1280, 800], [1440, 900]];
const DARK_VPS = [[390, 844], [1280, 800]];
const PAGES = [
  ['home', '/home.html'], ['events', '/events.html'], ['event', '/event.html?id=qa-ev-1'],
  ['post', '/post.html?id=np-qa-1'], ['person', '/person.html?id=qa-p1'], ['partner', '/partner.html?id=qa-partner-1'],
  ['login', '/login.html'], ['account', '/account.html'], ['form', '/form.html?fid=' + FORM],
  ['support', '/support.html'], ['404', '/no-such-page-qa.html'], ['offline', '/offline.html'],
  ['create', '/create.html'], ['builder', '/builder.html'], ['admin', '/admin.html'],
  ['final-page-review', '/final-page-review.html'], ['loading-preview', '/loading-preview.html'],
  ['nora-pay-preview', '/nora-pay-preview.html'], ['index', '/index.html'],
];
const ONLY = process.env.ONLY ? process.env.ONLY.split(',') : null;
// owner session for admin/create/builder
let cookies = [];
try {
  const pw = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
  const r = await fetch(BASE + '/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: BASE }, body: JSON.stringify({ username: 'preview-owner', password: pw }) });
  const sc = r.headers.getSetCookie ? r.headers.getSetCookie() : [];
  cookies = sc.map(s => { const [kv] = s.split(';'); const i = kv.indexOf('='); return { name: kv.slice(0, i).trim(), value: kv.slice(i + 1).trim(), domain: '127.0.0.1', path: '/' }; });
  console.log('owner login', r.status, 'cookies', cookies.map(c => c.name).join(','));
} catch (e) { console.log('owner login failed', e.message); }
const results = [];
for (const [name, path] of PAGES) {
  if (ONLY && !ONLY.includes(name)) continue;
  const combos = [...VPS.map(v => [v, 'light']), ...DARK_VPS.map(v => [v, 'dark'])];
  for (const [[w, h], theme] of combos) {
    let b=null; for (let i=0;i<3&&!b;i++){ try{ b=await launchBrowser(); }catch(e){ console.log('launch retry',i,e.message.slice(0,60)); await new Promise(r=>setTimeout(r,1500)); } } if(!b){ results.push({page:name,vp:`${w}x${h}`,theme,error:'launch failed'}); continue; }
    try {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, serviceWorkers: 'block', locale: 'fa-IR' });
      if (cookies.length && /admin|create|builder/.test(name)) await ctx.addCookies(cookies);
      await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, theme);
      const p = await ctx.newPage();
      const errs = [];
      p.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
      p.on('console', m => { if (m.type() === 'error' && !/401|403|404|favicon|Failed to load resource/.test(m.text())) errs.push(m.text().slice(0, 120)); });
      await p.goto(BASE + path, { waitUntil: 'domcontentloaded' });
      await p.waitForTimeout(1400);
      const file = `${OUT}/${name}-${w}x${h}-${theme}.png`;
      await p.screenshot({ path: file, fullPage: false });
      // metrics: broken <use> refs, tiny interactive targets, overflow
      const m = await p.evaluate(() => {
        const uses = [...document.querySelectorAll('use')];
        const broken = uses.filter(u => { const h = u.getAttribute('href') || u.getAttribute('xlink:href') || ''; return h.startsWith('#') && !document.getElementById(h.slice(1)); }).map(u => u.getAttribute('href'));
        const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
        const ctrls = [...document.querySelectorAll('button,a[href],[role=button],input[type=checkbox],input[type=radio]')].filter(vis);
        const small = ctrls.filter(el => { const r = el.getBoundingClientRect(); return r.width < 24 || r.height < 24; }).map(el => (el.id ? '#' + el.id : el.className.toString().slice(0, 30)) + ' ' + Math.round(el.getBoundingClientRect().width) + 'x' + Math.round(el.getBoundingClientRect().height));
        const iconOnly = ctrls.filter(el => el.querySelector('svg') && !el.textContent.trim() && !el.getAttribute('aria-label') && !el.getAttribute('title') && !el.getAttribute('aria-labelledby')).map(el => el.id ? '#' + el.id : el.className.toString().slice(0, 40));
        const emoji = [...document.querySelectorAll('button,a[href]')].filter(vis).filter(el => /[\u2300-\u23FF\u2600-\u27BF\u{1F300}-\u{1FAFF}]/u.test(el.textContent)).map(el => el.textContent.trim().slice(0, 20));
        return { broken: [...new Set(broken)], small: small.slice(0, 12), smallCount: small.length, iconOnly: [...new Set(iconOnly)], emoji: [...new Set(emoji)].slice(0, 8), overflowX: document.documentElement.scrollWidth > innerWidth + 1, ctrls: ctrls.length };
      });
      results.push({ page: name, vp: `${w}x${h}`, theme, ...m, errs }); fs.appendFileSync(`${OUT}/metrics.jsonl`, JSON.stringify(results[results.length-1])+'\n');
      console.log(`${name} ${w}x${h} ${theme}: ctrls=${m.ctrls} broken=${m.broken.length} small=${m.smallCount} iconOnlyNoName=${m.iconOnly.length} emoji=${m.emoji.length} overflowX=${m.overflowX} errs=${errs.length}`);
    } catch (e) { console.log(`${name} ${w}x${h} ${theme}: ERROR ${e.message.slice(0, 120)}`); results.push({ page: name, vp: `${w}x${h}`, theme, error: e.message.slice(0, 200) }); }
    finally { await b.close(); }
  }
}
fs.writeFileSync(`${OUT}/metrics.json`, JSON.stringify(results, null, 1));
console.log('done', results.length, 'shots →', OUT);
