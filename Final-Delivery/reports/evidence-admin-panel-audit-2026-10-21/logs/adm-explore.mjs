// Exploration of the admin panel on the test server: owner + manager; dumps text and screenshots per section.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000'; const OUT = process.env.OUT || '/tmp/qa/adm/explore'; fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const OWNER_PW = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const envText = fs.readFileSync('/tmp/nora-preview/env.sh', 'utf8');
const env = {}; for (const m of envText.matchAll(/^export ([A-Z_]+)=(.*)$/gm)) env[m[1]] = m[2].replace(/^'(.*)'$/, '$1');
const ROLE = process.env.ROLE || 'owner';
const USER = ROLE === 'owner' ? env.NORA_OWNER_USERNAME : process.env.MGR_USER;
const PW = ROLE === 'owner' ? OWNER_PW : process.env.MGR_PW;
const vp = process.env.VP === 'mobile' ? { width: 390, height: 844 } : { width: 1280, height: 800 };
const b = await launchBrowser();
const ctx = await b.newContext({ viewport: vp, serviceWorkers: 'block', locale: 'fa-IR' });
await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, process.env.THEME || 'light');
const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
const cons = []; p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') cons.push(m.type() + ': ' + m.text().slice(0, 160)); });
await p.goto(BASE + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'domcontentloaded' }); await sleep(1200);
await p.fill('#lgStaffUsername', USER); await p.fill('#lgStaffPassword', PW); await p.click('#lgStaffSubmit');
await sleep(2500);
console.log('after login url', p.url(), 'status', await p.evaluate(() => (document.querySelector('#lgStatus') || {}).textContent || ''));
if (await p.$('#lgContinue')) { await p.click('#lgContinue'); await p.waitForLoadState('domcontentloaded'); }
await sleep(2500);
const dump = async (tag) => {
  const t = await p.evaluate(() => ({ url: location.href, bar: (document.querySelector('#admBar') || {}).innerText || '', nav: [...document.querySelectorAll('#admNav a,#admNav button')].map(a => a.textContent.trim().replace(/\s+/g, ' ') + '|' + (a.dataset.sec || a.getAttribute('href') || '')), tabs: [...document.querySelectorAll('#admTabs a')].map(a => a.textContent.trim().replace(/\s+/g, ' ')), body: (document.querySelector('#admBody') || {}).innerText || '', ox: document.documentElement.scrollWidth > innerWidth, docH: document.documentElement.scrollHeight }));
  fs.writeFileSync(`${OUT}/${ROLE}-${tag}.txt`, JSON.stringify(t, null, 1));
  await p.screenshot({ path: `${OUT}/${ROLE}-${tag}.png`, fullPage: true });
  console.log(tag, 'url=', t.url.replace(BASE, ''), 'nav=', t.nav.join(' , '), 'ox=', t.ox, 'docH=', t.docH, 'body=', t.body.replace(/\s+/g, ' ').slice(0, 300));
};
await dump('dash');
for (const sec of ['events', 'users', 'forms', 'cert', 'settings']) {
  await p.goto(BASE + '/admin.html#' + sec, { waitUntil: 'domcontentloaded' }); await sleep(2200); await dump(sec);
}
// settings tabs
for (const g of ['services', 'deploy', 'data', 'security', 'publishing', 'bots', 'performance']) {
  const el = await p.$(`[data-setg="${g}"]`); if (!el) { console.log('no setg', g); continue; }
  await el.click(); await sleep(2200); await dump('settings-' + g);
}
// users subviews
await p.goto(BASE + '/admin.html#users', { waitUntil: 'domcontentloaded' }); await sleep(2000);
for (const sel of ['[data-open-workflow-inbox]', '[data-user-hub="reports"]', '[data-server-role-module]']) {
  const el = await p.$(sel); if (!el) { console.log('no', sel); continue; }
  await el.click(); await sleep(2500); await dump('users-' + sel.replace(/[^a-z]/g, ''));
  await p.goto(BASE + '/admin.html#users', { waitUntil: 'domcontentloaded' }); await sleep(1800);
}
// user hub tabs
const hubTabs = await p.$$eval('[data-user-hub],[data-uv],[data-utool]', els => els.map(e => e.outerHTML.slice(0, 120)));
console.log('hub controls', hubTabs.join('\n'));
console.log('pageerrors', errs); console.log('console', cons.slice(0, 20));
await b.close();
