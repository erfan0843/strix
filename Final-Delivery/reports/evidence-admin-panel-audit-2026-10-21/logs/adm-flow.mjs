// Manager decides a receipt in the real browser → history tab shows it; owner sees audit row. Also mobile shot.
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000'; const OUT = '/tmp/qa/adm/after'; fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const OWNER_PW = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const envText = fs.readFileSync('/tmp/nora-preview/env.sh', 'utf8');
const env = {}; for (const m of envText.matchAll(/^export ([A-Z_]+)=(.*)$/gm)) env[m[1]] = m[2].replace(/^'(.*)'$/, '$1');
const VP = process.env.VP === 'mobile' ? { width: 390, height: 844 } : { width: 1280, height: 800 };
const THEME = process.env.THEME || 'light'; const sz = VP.width === 390 ? 'mobile' : 'desktop';
let b;
async function login(user, pw) {
  b = await launchBrowser();
  const ctx = await b.newContext({ viewport: VP, serviceWorkers: 'block', locale: 'fa-IR' });
  await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, THEME);
  const p = await ctx.newPage(); p.on('pageerror', e => console.log('PAGEERROR', e.message));
  await p.goto(BASE + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await p.fill('#lgStaffUsername', user); await p.fill('#lgStaffPassword', pw); await p.click('#lgStaffSubmit'); await sleep(2500);
  if (await p.$('#lgContinue')) { await p.click('#lgContinue'); await p.waitForLoadState('domcontentloaded'); }
  await sleep(2500); return { ctx, p };
}
const shot = async (p, tag) => { await p.screenshot({ path: `${OUT}/${tag}-${sz}-${THEME}.png`, fullPage: true }); };
const txt = async (p) => p.evaluate(() => (document.querySelector('#admBody') || {}).innerText || '');
// manager
const MGR = JSON.parse(fs.readFileSync('/tmp/qa/adm/manager.json','utf8'));
if (process.env.SKIP_MANAGER) {} else {
const m = await login(MGR.user, MGR.pw);
await m.p.goto(BASE + '/admin.html#inbox', { waitUntil: 'domcontentloaded' }); await sleep(2500);
const cards = await m.p.$$('[data-workflow-card]'); console.log('manager pending cards', cards.length);
await shot(m.p, 'flow-manager-inbox-pending');
const target = await m.p.$('[data-workflow-reject]'); const tid = target && await target.getAttribute('data-workflow-reject');
if (tid) {
  await m.p.fill(`[data-workflow-reason="${tid}"]`, 'مبلغ با فرم نمی‌خواند (آزمون QA)');
  await m.p.click(`[data-workflow-reject="${tid}"]`); await sleep(2500);
  console.log('after reject, pending cards', (await m.p.$$('[data-workflow-card]')).length, '| toast:', await m.p.evaluate(() => (document.querySelector('#toast') || {}).textContent || ''));
  const approve = await m.p.$('[data-workflow-approve]'); if (approve) { await approve.click(); await sleep(2500); console.log('after approve, pending cards', (await m.p.$$('[data-workflow-card]')).length); }
  await m.p.click('[data-workflow-status="decided"]'); await sleep(2500);
  const h = await txt(m.p); console.log('history text:', h.replace(/\s+/g, ' ').slice(0, 500));
  await shot(m.p, 'flow-manager-inbox-history');
  // reload persistence
  await m.p.reload({ waitUntil: 'domcontentloaded' }); await sleep(2500); await m.p.click('[data-workflow-status="decided"]'); await sleep(2500);
  console.log('history after reload cards:', (await m.p.$$('[data-workflow-card]')).length);
}
await m.p.goto(BASE + '/admin.html#dash', { waitUntil: 'domcontentloaded' }); await sleep(2500); await shot(m.p, 'flow-manager-dash');
console.log('manager dash:', (await txt(m.p)).replace(/\s+/g, ' ').slice(0, 260));
await m.ctx.close(); await b.close(); }
// owner audit
const o = await login(env.NORA_OWNER_USERNAME, OWNER_PW);
await o.p.goto(BASE + '/admin.html#settings', { waitUntil: 'domcontentloaded' }); await sleep(2000);
await o.p.click('[data-setg="security"]'); await sleep(2500);
await o.p.click('[data-audit-action="workflow."]'); await sleep(2500);
console.log('owner audit (workflow):', (await o.p.$eval('[data-audit-panel]', e => e.innerText)).replace(/\s+/g, ' ').slice(0, 600));
await shot(o.p, 'flow-owner-audit');
await o.p.goto(BASE + '/admin.html#dash', { waitUntil: 'domcontentloaded' }); await sleep(2500); await shot(o.p, 'flow-owner-dash');
await o.p.goto(BASE + '/admin.html#users', { waitUntil: 'domcontentloaded' }); await sleep(2000);
await o.p.click('[data-server-role-module]'); await sleep(2500); await shot(o.p, 'flow-owner-accounts');
await o.ctx.close(); await b.close();
