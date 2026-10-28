/* Final panel audit crawl against the local preview (TEST DB only; synthetic accounts from
   tools/phase9-preview-seed.py). For owner (desktop + mobile) and manager (desktop) it walks every
   panel section and sub-tab, and records per step: console errors / page errors, failed HTTP
   responses (≥400, except the expected guest/staff identity probes), rendered-text anomalies
   (undefined/NaN/[object/null/لورم), horizontal overflow on mobile, and a screenshot. Afterwards it
   checks every in-page link (same-origin GET) and the asset pins of admin.html.
   Usage:
     NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_QA_ORIGIN=http://127.0.0.1:8000 \
     node tools/panel-final-audit.cjs <out dir> */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'final-audit');
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!OWNER.pass || !MANAGER.pass) throw new Error('credentials file not parsed');
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const EXPECTED_4XX = [/\/api\/auth\/me$/, /\/api\/account\/me$/, /\/api\/owner\/me$/, /\/sitemap\.xml$/];
const steps = [];
const links = new Map();
let consoleBuf = [], failBuf = [];
const flush = () => fs.writeFileSync(path.join(OUT, 'final-audit-results.json'), JSON.stringify({ origin: ORIGIN, at: new Date().toISOString(), steps, links: [...links.entries()].map(([href, v]) => ({ href, ...v })) }, null, 2));

async function launchWithRetry() { let last; for (let i = 0; i < 4; i++) { try { return await launchBrowser(); } catch (e) { last = e; await sleep(1500); } } throw last; }
async function staffLogin(page, who) {
  await page.goto(ORIGIN + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'load', timeout: 60000 });
  await page.evaluate(() => { try { localStorage.removeItem('nora-admin'); } catch (e) { /* ignore */ } });
  await page.waitForSelector('#lgStaffUsername', { timeout: 30000 });
  await page.fill('#lgStaffUsername', who.user);
  await page.fill('#lgStaffPassword', who.pass);
  await page.click('#lgStaffSubmit');
  await sleep(3000);
  const go = await page.$('text=رفتن به پنل مدیریت');
  if (go) { await page.evaluate(el => el.click(), go); await sleep(3000); }
  if (!/admin\.html/.test(page.url())) throw new Error('staff login did not reach the panel: ' + page.url());
  await page.waitForLoadState('load'); await sleep(1200);
}
const clickAll = async (page, selector, wait = 300) => page.evaluate(({ selector }) => { const el = document.querySelector(selector); if (el) { el.click(); return true; } return false; }, { selector }).then(async ok => { await sleep(wait); return ok; });

async function inspect(page, tag, name, { mobile = false } = {}) {
  await sleep(1800);
  const info = await page.evaluate(() => {
    const body = document.querySelector('#admBody') || document.body;
    const text = body.innerText || '';
    const anomalies = [];
    for (const re of [/\bundefined\b/, /\bNaN\b/, /\[object /, /(^|\s)null(\s|$)/, /لورم/, /data\.js/]) { const m = text.match(re); if (m) anomalies.push(m[0]); }
    const hrefs = [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).filter(h => h && !h.startsWith('mailto:') && !h.startsWith('tel:'));
    const overflow = document.documentElement.scrollWidth > window.innerWidth + 1;
    const emptyButtons = [...body.querySelectorAll('button')].filter(b => !b.textContent.trim() && !b.getAttribute('aria-label') && !b.title).length;
    const imgsBroken = [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.getAttribute('src')).map(i => i.getAttribute('src')).slice(0, 5);
    return { title: (document.querySelector('.admbar .head, #admBar b, header b')?.textContent || '').trim().slice(0, 60), textLen: text.length, anomalies, hrefs, overflow, emptyButtons, imgsBroken, hash: location.hash };
  });
  for (const h of info.hrefs) if (!links.has(h)) links.set(h, { seenAt: `${tag}:${name}` });
  const consoleErrors = consoleBuf.splice(0), failed = failBuf.splice(0);
  const unexpectedFailed = failed.filter(f => !(f.status === 401 && EXPECTED_4XX.some(re => re.test(f.url))) && !(f.status === 503 && /sitemap/.test(f.url)));
  const unexpectedConsole = consoleErrors.filter(c => !(/401|Unauthorized/.test(c.text) && EXPECTED_4XX.some(re => re.test(c.text))) && !/sitemap/.test(c.text));
  const file = `${tag}-${String(steps.length + 1).padStart(2, '0')}-${name}.png`;
  await page.screenshot({ path: path.join(OUT, file), fullPage: false });
  const step = { tag, name, file, hash: info.hash, textLen: info.textLen, anomalies: info.anomalies, overflow: mobile ? info.overflow : undefined, emptyButtons: info.emptyButtons, imgsBroken: info.imgsBroken, consoleErrors: unexpectedConsole, failed: unexpectedFailed, expectedProbes: failed.length - unexpectedFailed.length };
  steps.push(step); flush();
  return step;
}

async function crawl(page, who, tag, mobile) {
  const nav = async sec => { await page.evaluate(sec => { const b = document.querySelector(`#admNav [data-sec="${sec}"]`) || document.querySelector(`[data-sec="${sec}"]`); if (b) b.click(); }, sec); await sleep(1500); };
  const sub = async (selector, name, extra) => { const ok = await clickAll(page, selector, 1200); const s = await inspect(page, tag, name, { mobile }); s.clicked = ok; if (extra) Object.assign(s, extra); return s; };

  await staffLogin(page, who);
  await inspect(page, tag, 'dash', { mobile });
  await sub('[data-dashx-map], [data-panel-map]', 'dash-map');
  /* events & content */
  await nav('events'); await inspect(page, tag, 'events-list', { mobile });
  await sub('[data-ct-kind="articles"]', 'articles-list');
  await sub('[data-ct-edit]', 'article-editor');
  await sub('[data-ch-pane="hist"]', 'article-history');
  await clickAll(page, '[data-ct-cancel]', 800);
  await sub('[data-ct-kind="events"]', 'events-list-again');
  await sub('[data-ct-edit]', 'event-editor');
  await sub('[data-ch-pane="hist"]', 'event-history');
  await clickAll(page, '[data-ct-cancel]', 800);
  await sub('[data-ct-new]', 'event-new');
  await clickAll(page, '[data-ct-cancel]', 800);
  if (!mobile) {
    await sub('[data-ct-interaction]', 'event-tool');
    const tabs = await page.evaluate(() => [...document.querySelectorAll('[data-ei-tab]')].map(el => el.dataset.eiTab));
    for (const t of tabs) await sub(`[data-ei-tab="${t}"]`, `event-tool-${t}`);
    await clickAll(page, '[data-ei-close], [data-ei-back]', 800);
    await sub('[data-ei-open-all]', 'events-open-questions');
    await clickAll(page, '[data-ei-close], [data-ei-back], [data-cm-close]', 800);
  }
  /* users */
  await nav('users'); await inspect(page, tag, 'users-list', { mobile });
  await sub('[data-user-open]', 'user-file');
  const ufTabs = await page.evaluate(() => [...document.querySelectorAll('[data-ufl-tab], [data-uf-tab]')].map(el => el.dataset.uflTab || el.dataset.ufTab));
  for (const t of ufTabs.slice(0, 8)) await sub(`[data-ufl-tab="${t}"], [data-uf-tab="${t}"]`, `user-file-${t}`);
  await clickAll(page, '[data-uback]', 800);
  await sub('[data-users-status="blocked"], [data-utool="blocked"]', 'users-blocked-filter');
  await clickAll(page, '[data-uback]', 800);
  await nav('users');
  const tiles = await page.evaluate(() => [...document.querySelectorAll('[data-uv]')].map(el => el.dataset.uv));
  for (const t of tiles) {
    await sub(`[data-uv="${t}"]`, `users-${t}`);
    if (t === 'tools') {
      const tools = await page.evaluate(() => [...document.querySelectorAll('[data-utool]')].map(el => el.dataset.utool));
      for (const u of tools) await sub(`[data-utool="${u}"]`, `tools-${u}`);
    }
    if (t === 'shared-inbox') {
      const kinds = await page.evaluate(() => [...document.querySelectorAll('[data-workflow-kind]')].map(el => el.dataset.workflowKind));
      for (const k of kinds.slice(0, 4)) await sub(`[data-workflow-kind="${k}"]`, `inbox-${k}`);
    }
    await clickAll(page, '[data-uback]', 600);
    await nav('users');
  }
  await sub('[data-user-hub="reports"]', 'reports-hub');
  await sub('[data-server-report-period="7d"]', 'reports-7d');
  await sub('[data-server-outbox-kind="event_reminder"]', 'reports-outbox-reminders');
  await sub('[data-server-outbox-state="failed"]', 'reports-outbox-failed');
  /* forms */
  await nav('forms'); await inspect(page, tag, 'forms', { mobile });
  /* settings */
  await nav('settings'); await inspect(page, tag, 'settings', { mobile });
  const groups = await page.evaluate(() => [...document.querySelectorAll('[data-setg]')].map(el => el.dataset.setg));
  for (const g of groups) {
    await sub(`[data-setg="${g}"]`, `settings-${g}`);
    if (g === 'services') { const svc = await page.evaluate(() => [...document.querySelectorAll('[data-svc-tab]')].map(el => el.dataset.svcTab)); for (const s of svc) await sub(`[data-svc-tab="${s}"]`, `settings-service-${s}`); }
    if (g === 'people') { await sub('[data-pe-edit]', 'person-editor'); await sub('[data-ch-pane="hist"]', 'person-history'); await clickAll(page, '[data-pe-cancel], [data-pe-back]', 600); }
    if (g === 'publishing') { const pp = await page.evaluate(() => [...document.querySelectorAll('[data-pptab]')].map(el => el.dataset.pptab)); for (const p of pp) await sub(`[data-pptab="${p}"]`, `publishing-${p}`); }
  }
  /* direct hashes that the design used */
  for (const h of ['#reports', '#money', '#club', '#cert', '#newev', '#posts', '#nonexistent-section']) {
    await page.goto('about:blank'); await page.goto(ORIGIN + '/admin.html' + h, { waitUntil: 'load', timeout: 60000 });
    await inspect(page, tag, 'hash-' + h.slice(1), { mobile });
  }
}

(async () => {
  const browser = await launchWithRetry();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  page.on('dialog', d => d.dismiss());
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') consoleBuf.push({ type: m.type(), text: m.text().slice(0, 300) }); });
  page.on('pageerror', e => consoleBuf.push({ type: 'pageerror', text: String(e && e.message || e).slice(0, 300) }));
  page.on('response', r => { if (r.status() >= 400) failBuf.push({ status: r.status(), url: r.url().replace(ORIGIN, '') }); });
  page.on('requestfailed', r => failBuf.push({ status: 0, url: r.url().replace(ORIGIN, ''), reason: r.failure() && r.failure().errorText }));
  try {
    await crawl(page, OWNER, 'owner-d', false);
    await ctx.clearCookies();
    await crawl(page, MANAGER, 'manager-d', false);
    await ctx.clearCookies();
    await page.setViewportSize({ width: 390, height: 844 });
    await crawl(page, OWNER, 'owner-m', true);
    /* link check (same origin, GET) + asset pins */
    await ctx.clearCookies(); await staffLogin(page, OWNER);
    const hrefs = [...links.keys()];
    const results = await page.evaluate(async hrefs => {
      const out = {};
      for (const h of hrefs) {
        if (/^https?:\/\//.test(h) && !h.startsWith(location.origin)) { out[h] = { status: 'external' }; continue; }
        if (h.startsWith('#')) { out[h] = { status: 'hash' }; continue; }
        try { const r = await fetch(h, { method: 'GET', credentials: 'same-origin', cache: 'no-store' }); out[h] = { status: r.status }; } catch (e) { out[h] = { status: 'error', error: String(e).slice(0, 80) }; }
      }
      return out;
    }, hrefs);
    for (const [h, r] of Object.entries(results)) Object.assign(links.get(h), r);
    const pins = await page.evaluate(async () => {
      const html = await (await fetch('/admin.html', { cache: 'no-store' })).text();
      const assets = [...html.matchAll(/(?:src|href)="([^"]+\.(?:js|css)\?v=\d+)"/g)].map(m => m[1]);
      const out = [];
      for (const a of assets) { const r = await fetch(a, { cache: 'no-store' }); out.push({ asset: a, status: r.status, type: r.headers.get('content-type') }); }
      const loaded = performance.getEntriesByType('resource').filter(e => /\.(js|css)\?v=/.test(e.name)).map(e => e.name.replace(location.origin, ''));
      return { assets: out, loaded };
    });
    steps.push({ tag: 'pins', name: 'admin.html asset pins', pins });
    flush();
  } catch (error) {
    steps.push({ tag: 'fatal', name: String(error && error.message || error), stack: String(error && error.stack || '').slice(0, 1200) });
    try { await page.screenshot({ path: path.join(OUT, 'fatal.png') }); } catch (e) { /* ignore */ }
    flush();
  } finally { await browser.close(); }
})();
