// Mobile + dark after-shots of key pages (owner & manager), one browser per role.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000'; const OUT = '/tmp/qa/adm/after';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const OWNER_PW = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const envText = fs.readFileSync('/tmp/nora-preview/env.sh', 'utf8');
const env = {}; for (const m of envText.matchAll(/^export ([A-Z_]+)=(.*)$/gm)) env[m[1]] = m[2].replace(/^'(.*)'$/, '$1');
const MGR = JSON.parse(fs.readFileSync('/tmp/qa/adm/manager.json','utf8'));
const ROLE = process.env.ROLE || 'owner'; const VP = process.env.VP === 'mobile' ? { width: 390, height: 844 } : { width: 1280, height: 800 };
const THEME = process.env.THEME || 'light'; const sz = VP.width === 390 ? 'mobile' : 'desktop';
const b = await launchBrowser(); const ctx = await b.newContext({ viewport: VP, serviceWorkers: 'block', locale: 'fa-IR' });
await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, THEME);
const p = await ctx.newPage(); p.on('pageerror', e => console.log('PAGEERROR', e.message));
await p.goto(BASE + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'domcontentloaded' }); await sleep(1200);
await p.fill('#lgStaffUsername', ROLE === 'owner' ? env.NORA_OWNER_USERNAME : MGR.user); await p.fill('#lgStaffPassword', ROLE === 'owner' ? OWNER_PW : MGR.pw); await p.click('#lgStaffSubmit'); await sleep(2500);
if (await p.$('#lgContinue')) { await p.click('#lgContinue'); await p.waitForLoadState('domcontentloaded'); }
await sleep(2500);
const shot = async (tag) => { const ox = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth); await p.screenshot({ path: `${OUT}/${ROLE}-${tag}-${sz}-${THEME}.png`, fullPage: true }); console.log(tag, 'ox=', ox); };
await shot('dash');
await p.goto(BASE + '/admin.html#inbox', { waitUntil: 'domcontentloaded' }); await sleep(2500); await shot('inbox');
await p.click('[data-workflow-status="decided"]'); await sleep(2500); await shot('inbox-history');
if (ROLE === 'owner') {
  await p.goto(BASE + '/admin.html#users', { waitUntil: 'domcontentloaded' }); await sleep(1800);
  const mod = await p.$('[data-server-role-module]'); if (mod) { await mod.click(); await sleep(2500); await shot('accounts'); }
  await p.goto(BASE + '/admin.html#settings', { waitUntil: 'domcontentloaded' }); await sleep(1800);
  await p.click('[data-setg="security"]'); await sleep(2500); await shot('audit');
} else {
  await p.goto(BASE + '/admin.html#settings', { waitUntil: 'domcontentloaded' }); await sleep(1800); await shot('settings-locked');
}
await b.close();
