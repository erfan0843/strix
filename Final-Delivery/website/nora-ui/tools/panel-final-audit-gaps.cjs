/* Follow-up to panel-final-audit.cjs: the preview DB had no article and no site person, so the
   article editor / person editor steps were never reached. This script seeds ONE draft article and
   ONE teacher row through the real owner APIs (test DB only), then re-walks those editors (desktop +
   mobile), lists icon-only buttons without an accessible name, and checks the preloaded fonts. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { launchBrowser } = require('./browser-launch.cjs');
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2] || path.join(process.cwd(), 'final-audit');
const creds = fs.readFileSync(path.join(__dirname, '..', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = { origin: ORIGIN, at: new Date().toISOString(), steps: [] };
const flush = () => fs.writeFileSync(path.join(OUT, 'final-audit-gaps-results.json'), JSON.stringify(out, null, 2));
let consoleBuf = [], failBuf = [];
async function staffLogin(page, who) {
  await page.goto(ORIGIN + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'load', timeout: 60000 });
  await page.evaluate(() => { try { localStorage.removeItem('nora-admin'); } catch (e) { /* ignore */ } });
  await page.waitForSelector('#lgStaffUsername', { timeout: 30000 });
  await page.fill('#lgStaffUsername', who.user); await page.fill('#lgStaffPassword', who.pass); await page.click('#lgStaffSubmit');
  await sleep(3000);
  const go = await page.$('text=رفتن به پنل مدیریت'); if (go) { await page.evaluate(el => el.click(), go); await sleep(3000); }
  if (!/admin\.html/.test(page.url())) throw new Error('login failed: ' + page.url());
  await page.waitForLoadState('load'); await sleep(1200);
}
const click = async (page, selector, wait = 1200) => { const ok = await page.evaluate(s => { const el = document.querySelector(s); if (el) { el.click(); return true; } return false; }, selector); await sleep(wait); return ok; };
async function snap(page, name, extra = {}) {
  await sleep(1500);
  const info = await page.evaluate(() => {
    const body = document.querySelector('#admBody') || document.body; const text = body.innerText || '';
    const anomalies = []; for (const re of [/\bundefined\b/, /\bNaN\b/, /\[object /, /لورم/, /data\.js/]) { const m = text.match(re); if (m) anomalies.push(m[0]); }
    return { hash: location.hash, textLen: text.length, anomalies, overflow: document.documentElement.scrollWidth > window.innerWidth + 1, hist: !!document.querySelector('[data-ch-pane="hist"]'), editor: !!document.querySelector('#peEditor, [data-ct-editor], [data-ct-form]') };
  });
  const file = `gaps-${String(out.steps.length + 1).padStart(2, '0')}-${name}.png`;
  await page.screenshot({ path: path.join(OUT, file) });
  const step = { name, file, ...info, consoleErrors: consoleBuf.splice(0).filter(c => !/401|preload/.test(c.text)), failed: failBuf.splice(0).filter(f => !(f.status === 401 && /\/me$/.test(f.url))), ...extra };
  out.steps.push(step); flush(); return step;
}
(async () => {
  const browser = await launchBrowser();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  page.on('dialog', d => d.accept());
  page.on('console', m => { if (m.type() === 'error') consoleBuf.push({ type: m.type(), text: m.text().slice(0, 300) }); });
  page.on('pageerror', e => consoleBuf.push({ type: 'pageerror', text: String(e && e.message || e).slice(0, 300) }));
  page.on('response', r => { if (r.status() >= 400) failBuf.push({ status: r.status(), url: r.url().replace(ORIGIN, '') }); });
  try {
    await staffLogin(page, OWNER);
    /* seed through the real APIs (owner cookie + CSRF double-submit) */
    const seeded = await page.evaluate(async () => {
      const csrf = (document.cookie.match(/(?:^|; )nora_csrf=([^;]+)/) || [])[1] || '';
      const H = { 'Content-Type': 'application/json', 'X-CSRF-Token': decodeURIComponent(csrf) };
      const result = {};
      const list = await (await fetch('/api/admin/content/articles?limit=1')).json();
      result.articlesBefore = (list.items || list.rows || []).length;
      if (!result.articlesBefore) {
        const r = await fetch('/api/admin/content/articles', { method: 'POST', headers: H, body: JSON.stringify({ record: { t: 'مطلب آزمایشی ممیزی نهایی', cat: 'آموزش', lead: 'لید آزمایشی', body: 'بند اول\n\nبند دوم', at: '2026-10-20', tags: ['audit'] }, expected_version: list.version || 0 }) });
        result.articleCreate = r.status; result.articleBody = (await r.text()).slice(0, 200);
      }
      const sc = await (await fetch('/api/owner/site-content')).json();
      result.peopleBefore = ((sc.content || {}).people || []).length; result.scVersion = sc.version;
      if (!result.peopleBefore) {
        const r = await fetch('/api/owner/site-content', { method: 'PATCH', headers: H, body: JSON.stringify({ content: { people: [{ id: 'pp-audit-teacher', n: 'مدرس آزمایشی ممیزی', kind: 'teacher', r: 'مدرس نجوم', role2: '', bio: 'زندگی‌نامهٔ آزمایشی', quote: '', where: 'رصدخانه', yrs: '۵', courses: '۳', rate: '', tag: 'نجوم', exp: ['رصد'], links: [], photo: '', g: '', form: '', formTxt: '' }] }, expected_version: sc.version }) });
        result.personCreate = r.status; result.personBody = (await r.text()).slice(0, 200);
      }
      return result;
    });
    out.seeded = seeded; flush();
    for (const mobile of [false, true]) {
      if (mobile) await page.setViewportSize({ width: 390, height: 844 });
      const tag = mobile ? 'm' : 'd';
      await page.goto('about:blank'); await page.goto(ORIGIN + '/admin.html#events', { waitUntil: 'load' }); await sleep(2500);
      await click(page, '[data-ct-kind="articles"]'); await snap(page, tag + '-articles-list', { mobile });
      await click(page, '[data-ct-edit]'); await snap(page, tag + '-article-editor', { mobile });
      await click(page, '[data-ch-pane="hist"]'); await snap(page, tag + '-article-history', { mobile });
      await click(page, '[data-ct-cancel]', 600);
      await page.goto('about:blank'); await page.goto(ORIGIN + '/admin.html#settings', { waitUntil: 'load' }); await sleep(2500);
      await click(page, '[data-setg="people"]'); await snap(page, tag + '-people-list', { mobile });
      await click(page, '[data-pe-edit]'); await snap(page, tag + '-person-editor', { mobile });
      await click(page, '[data-ch-pane="hist"]'); await snap(page, tag + '-person-history', { mobile });
      await click(page, '[data-pe-cancel]', 600);
    }
    /* hub cards of the users section: shared inbox, attendance, certificates, club mirror, server accounts */
    for (const mobile of [false, true]) {
      await page.setViewportSize(mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 });
      const tag = mobile ? 'm' : 'd';
      const open = async (selector, name, inner) => {
        await page.goto('about:blank'); await page.goto(ORIGIN + '/admin.html#users', { waitUntil: 'load' }); await sleep(2500);
        await page.evaluate(() => { try { const st = JSON.parse(localStorage.getItem('nora-admin') || '{}'); st.uV = ''; st.uHub = 'users'; localStorage.setItem('nora-admin', JSON.stringify(st)); } catch (e) { /* ignore */ } });
        await page.goto('about:blank'); await page.goto(ORIGIN + '/admin.html#users', { waitUntil: 'load' }); await sleep(2500);
        const ok = await click(page, selector); await snap(page, `${tag}-${name}`, { mobile, clicked: ok });
        if (inner) for (const [sel, nm] of inner) { const ok2 = await click(page, sel); await snap(page, `${tag}-${nm}`, { mobile, clicked: ok2 }); }
      };
      await open('[data-open-workflow-inbox]', 'shared-inbox', [['[data-workflow-kind="receipt_review"]', 'shared-inbox-receipts'], ['[data-workflow-kind="profile_review"]', 'shared-inbox-profiles']]);
      await open('[data-open-attendance]', 'attendance', [['[data-att-form]', 'attendance-people']]);
      await open('[data-open-cert]', 'certificates', [['[data-cert-open]', 'certificate-detail']]);
      await open('[data-open-club]', 'club', [['[data-club-member]', 'club-member']]);
      if (!mobile) await open('[data-server-role-module]', 'server-accounts');
    }
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('about:blank'); await page.goto(ORIGIN + '/admin.html#dash', { waitUntil: 'load' }); await sleep(4000);
    out.dashButtons = await page.evaluate(() => [...document.querySelectorAll('button')].filter(b => !b.textContent.trim() && !b.getAttribute('aria-label') && !b.title).map(b => b.outerHTML.slice(0, 160)));
    await click(page, '[data-dashx-map]', 1500);
    out.mapButtons = await page.evaluate(() => [...document.querySelectorAll('button')].filter(b => !b.textContent.trim() && !b.getAttribute('aria-label') && !b.title).map(b => b.outerHTML.slice(0, 160)));
    out.fonts = await page.evaluate(async () => { await document.fonts.ready; return { body: getComputedStyle(document.body).fontFamily, vazir: document.fonts.check('16px Vazirmatn'), estedad: document.fonts.check('16px Estedad'), loaded: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight) }; });
    flush();
  } catch (error) { out.fatal = String(error && error.stack || error).slice(0, 1200); flush(); } finally { await browser.close(); }
})();
