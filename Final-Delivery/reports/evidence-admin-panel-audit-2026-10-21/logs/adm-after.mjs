// After-fix browser verification on the test server (owner + manager), desktop + mobile, light/dark.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000'; const OUT = process.env.OUT || '/tmp/qa/adm/after'; fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const OWNER_PW = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const envText = fs.readFileSync('/tmp/nora-preview/env.sh', 'utf8');
const env = {}; for (const m of envText.matchAll(/^export ([A-Z_]+)=(.*)$/gm)) env[m[1]] = m[2].replace(/^'(.*)'$/, '$1');
const ROLE = process.env.ROLE || 'owner';
const USER = ROLE === 'owner' ? env.NORA_OWNER_USERNAME : process.env.MGR_USER;
const PW = ROLE === 'owner' ? OWNER_PW : process.env.MGR_PW;
const VP = process.env.VP === 'mobile' ? { width: 390, height: 844 } : { width: 1280, height: 800 };
const THEME = process.env.THEME || 'light';
const b = await launchBrowser();
const ctx = await b.newContext({ viewport: VP, serviceWorkers: 'block', locale: 'fa-IR' });
await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, THEME);
const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
const dialogs = []; p.on('dialog', async d => { dialogs.push(d.message()); await d.dismiss(); });
await p.goto(BASE + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'domcontentloaded' }); await sleep(1200);
await p.fill('#lgStaffUsername', USER); await p.fill('#lgStaffPassword', PW); await p.click('#lgStaffSubmit'); await sleep(2500);
if (await p.$('#lgContinue')) { await p.click('#lgContinue'); await p.waitForLoadState('domcontentloaded'); }
await sleep(2500);
const tagName = `${ROLE}-${VP.width === 390 ? 'mobile' : 'desktop'}-${THEME}`;
const dump = async (tag, full = true) => {
  const t = await p.evaluate(() => ({ url: location.href, bar: (document.querySelector('#admBar') || {}).innerText || '',
    tabsVisible: (() => { const e = document.querySelector('#admTabs'); return !!e && getComputedStyle(e).display !== 'none'; })(),
    body: (document.querySelector('#admBody') || {}).innerText || '', ox: document.documentElement.scrollWidth > innerWidth }));
  fs.writeFileSync(`${OUT}/${tagName}-${tag}.txt`, JSON.stringify(t, null, 1));
  await p.screenshot({ path: `${OUT}/${tagName}-${tag}.png`, fullPage: full });
  console.log(tag, '| tabsVisible=', t.tabsVisible, 'ox=', t.ox, '| bar=', t.bar.replace(/\s+/g, ' ').slice(0, 90), '| body=', t.body.replace(/\s+/g, ' ').slice(0, 220));
};
await dump('dash');
// inbox + history
await p.goto(BASE + '/admin.html#inbox', { waitUntil: 'domcontentloaded' }); await sleep(2500); await dump('inbox-pending');
const hist = await p.$('[data-workflow-status="decided"]'); if (hist) { await hist.click(); await sleep(2500); await dump('inbox-history'); }
if (ROLE === 'owner') {
  await p.goto(BASE + '/admin.html#users', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const mod = await p.$('[data-server-role-module]'); if (mod) { await mod.click(); await sleep(2500); await dump('accounts');
    await p.fill('#serverRoleQuery', 'qa'); await p.click('[data-role-search]'); await sleep(2000); await dump('accounts-search');
    await p.click('[data-role-filter="manager"]'); await sleep(2000); await dump('accounts-filter-manager');
    // confirm dialog on credential removal: dismissed by handler → no request
    const rm = await p.$('[data-remove-manager-credentials]'); if (rm) { await p.evaluate(() => document.querySelector('[data-remove-manager-credentials]').click()); await sleep(800); console.log('confirm dialogs:', dialogs, '| still enabled:', !!(await p.$('[data-remove-manager-credentials]'))); }
  }
  await p.goto(BASE + '/admin.html#settings', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  console.log('setg tabs:', await p.$$eval('[data-setg]', els => els.map(e => e.dataset.setg)));
  for (const g of ['security', 'performance']) { const el = await p.$(`[data-setg="${g}"]`); if (el) { await el.click(); await sleep(2500); await dump('settings-' + g); } }
  await p.goto(BASE + '/admin.html#bots', { waitUntil: 'domcontentloaded' }); await sleep(1500); console.log('#bots →', await p.$eval('[data-setg].on,[data-setg][aria-selected="true"]', e => e.dataset.setg).catch(() => 'n/a'));
  await p.goto(BASE + '/builder.html', { waitUntil: 'domcontentloaded' }); await sleep(1500);
  const k = await p.$('[data-go="fKartabl"]'); if (k) { await k.click(); await sleep(800); await dump('builder-kartabl', false); }
} else {
  await p.goto(BASE + '/admin.html#settings', { waitUntil: 'domcontentloaded' }); await sleep(1500); await dump('settings-locked');
  const r = await fetch(BASE + '/api/owner/audit?limit=5&offset=0', { headers: { Cookie: (await ctx.cookies()).map(c => c.name + '=' + c.value).join('; ') } });
  console.log('manager GET /api/owner/audit →', r.status);
}
console.log('pageerrors', errs);
await b.close();
