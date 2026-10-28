/* Phase 9.7 — public form + purchase walkthrough + response detail + inbox (TEST server/DB). */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { launchBrowser } = require(path.resolve(process.env.NORA_UI_DIR || '.', 'tools/browser-launch.cjs'));
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2];
const BOT_TOKEN = process.env.NORA_BALE_BOT_TOKEN; if (!BOT_TOKEN) throw new Error('bot token env missing');
const creds = fs.readFileSync(path.resolve(process.env.NORA_UI_DIR || '.', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { label: 'owner', user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { label: 'manager', user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
const FREE_FORM = process.env.FREE_FORM; const PURCHASE_FORM = process.env.PURCHASE_FORM_FULL; const REG_FORM = process.env.REG_FORM_FULL;
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const say = l => { log.push(l); fs.writeFileSync(path.join(OUT, 'public-checks.txt'), log.join('\n') + '\n'); };
async function launchWithRetry() { let last; for (let i = 0; i < 4; i++) { try { return await launchBrowser(); } catch (e) { last = e; await sleep(1500); } } throw last; }
async function context(mobile) {
  const browser = await launchWithRetry();
  const ctx = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, reducedMotion: 'reduce' } : { viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  ctx.close = async () => { await browser.close(); };
  return ctx;
}
const snap = (page, name) => page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: false });
const txt = (page, sel, n = 220) => page.evaluate(([s, k]) => { const el = document.querySelector(s); return el ? el.innerText.replace(/\s+/g, ' ').trim().slice(0, k) : null; }, [sel, n]);
const visible = (page, sel) => page.evaluate(s => { const el = document.querySelector(s); if (!el) return false; const r = el.getBoundingClientRect(); return !el.hidden && r.width > 0 && r.height > 0; }, sel);
async function step(name, fn) { try { await fn(); } catch (e) { say(`- ⚠️ step «${name}» failed: ${String(e.message).split('\n')[0].slice(0, 200)}`); } }
function initData(userId) {
  const fields = { auth_date: String(Math.floor(Date.now() / 1000)), query_id: 'p97-' + userId + '-' + Date.now(), user: JSON.stringify({ id: userId, first_name: 'آزمایش' }) };
  const check = Object.keys(fields).sort().map(k => `${k}=${fields[k]}`).join('\n');
  const secret = crypto.createHmac('sha256', 'WebAppData').update(BOT_TOKEN).digest();
  const hash = crypto.createHmac('sha256', secret).update(check).digest('hex');
  return new URLSearchParams({ ...fields, hash }).toString();
}
async function memberLogin(page, userId) {
  await page.goto(ORIGIN + '/events.html', { waitUntil: 'load', timeout: 60000 });
  const status = await page.evaluate(async data => { const r = await fetch('/api/auth/bale-mini-app', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ init_data: data }), credentials: 'same-origin' }); return r.status; }, initData(userId));
  if (status !== 200) throw new Error('member login failed ' + status);
}
async function staffLogin(page, who) {
  await page.goto(ORIGIN + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'load', timeout: 60000 });
  await page.waitForSelector('#lgStaffUsername', { timeout: 30000 });
  await page.fill('#lgStaffUsername', who.user); await page.fill('#lgStaffPassword', who.pass);
  await page.click('#lgStaffSubmit'); await sleep(3000);
  const go = await page.$('text=رفتن به پنل مدیریت'); if (go) { await page.evaluate(el => el.click(), go); await sleep(2500); }
}
const screenState = page => page.evaluate(() => {
  const s = document.querySelector('.screen.on'); const q = s ? s.querySelector('.q, .qtitle, h2, h3, label.lbl') : null;
  return { active: s ? s.id : null, q: q ? q.innerText.replace(/\s+/g, ' ').trim().slice(0, 90) : '', body: s ? s.innerText.replace(/\s+/g, ' ').trim().slice(0, 240) : '', next: (document.querySelector('#next') || { innerText: '' }).innerText.trim(), toast: (document.querySelector('#toast') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim().slice(0, 120), inputs: [...s ? s.querySelectorAll('input:not([type=hidden]), textarea, select') : []].map(e => e.type || e.tagName).join(','), choices: [...s ? s.querySelectorAll('.opt, [role=radio], .choice button, [data-opt], .chip') : []].map(e => e.innerText.trim()).slice(0, 6) };
});
async function fillCurrent(page, choiceText) {
  await page.evaluate(choice => {
    const s = document.querySelector('.screen.on'); if (!s) return;
    s.querySelectorAll('input:not([type=hidden]), textarea').forEach(e => {
      if (e.type === 'checkbox' || e.type === 'radio') { e.checked = true; e.dispatchEvent(new Event('change', { bubbles: true })); return; }
      const lbl = (s.innerText || '') + ' ' + (e.placeholder || '') + ' ' + (e.id || '') + ' ' + (e.inputMode || '');
      let v = 'آزمایش ۹.۷';
      if (e.type === 'tel' || /موبایل/.test(lbl)) v = '09120000097';
      if (/کد ملی/.test(lbl) && !/موبایل/.test(lbl)) v = '0012345678';
      if (/نام و نام خانوادگی/.test(lbl)) v = 'آزمایش ۹.۷ نورا';
      if (e.type === 'email') v = 'qa97@example.test';
      e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true }));
    });
    if (choice) { const btn = [...s.querySelectorAll('button, .opt, [role=radio], label')].find(b => b.innerText.trim() === choice); if (btn) btn.click(); }
  }, choiceText || null);
}
async function walk(page, formId, label, tag, { choice, maxSteps = 12, stopAt = null } = {}) {
  const api = []; page.on('response', r => { const u = r.url(); if (u.includes('/api/')) api.push(`${r.request().method()} ${u.replace(ORIGIN, '').split('?')[0].replace(formId, '{id}')} → ${r.status()}`); });
  const errors = []; page.on('pageerror', e => errors.push(String(e.message).slice(0, 100)));
  await page.goto(ORIGIN + '/form.html?fid=' + encodeURIComponent(formId), { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
  let st = await screenState(page);
  say(`- ${label} (${tag}) [${formId.slice(0, 8)}] start: active=${st.active}; CTA «${st.next}»; body «${st.body.slice(0, 200)}»`);
  await snap(page, `${tag}-${label}-01-${st.active}`);
  const seen = [st.active];
  for (let i = 1; i <= maxSteps; i++) {
    if (!(await visible(page, '#next'))) { say(`  #next not visible on ${st.active}; stop`); break; }
    await page.evaluate(() => document.querySelector('#next').click()); await sleep(1300);
    let cur = await screenState(page);
    if (cur.active === st.active) {
      await fillCurrent(page, choice); await sleep(400);
      await page.evaluate(() => document.querySelector('#next').click()); await sleep(1300);
      cur = await screenState(page);
      if (cur.active === st.active) { say(`  step ${i}: stuck on ${cur.active} after filling; toast «${cur.toast}»; inputs=${cur.inputs}; choices=${JSON.stringify(cur.choices)}`); await snap(page, `${tag}-${label}-${String(i + 1).padStart(2, '0')}-${cur.active}-stuck`); break; }
    }
    say(`  step ${i}: ${st.active} → ${cur.active}; q «${cur.q}»; inputs=${cur.inputs}; choices=${JSON.stringify(cur.choices)}; CTA «${cur.next}»; toast «${cur.toast}»; body «${cur.body.slice(0, 160)}»`);
    await snap(page, `${tag}-${label}-${String(i + 1).padStart(2, '0')}-${cur.active}`);
    seen.push(cur.active); st = cur;
    if (cur.active === 'u9') {
      const pay = await page.evaluate(() => ({ methods: [...document.querySelectorAll('#paymentMethodList [data-method]')].map(b => `${b.dataset.method}:${b.hidden ? 'hidden' : b.disabled ? 'disabled' : 'enabled'}${b.classList.contains('on') ? ':selected' : ''}`), note: (document.querySelector('#paymentStepNote') || { innerText: '' }).innerText.trim().slice(0, 160), total: (document.querySelector('#paymentTransferTotal') || { innerText: '' }).innerText.trim(), amount: (document.querySelector('#payAmount') || { innerText: '' }).innerText.trim(), card: (document.querySelector('#paymentBankCardStatus') || { innerText: '' }).innerText.trim().slice(0, 120), cardNo: (document.querySelector('#paymentBankCardNumber') || { innerText: '' }).innerText.trim().replace(/\d(?=\d{4})/g, '•'), coupon: document.querySelector('#couponRow') ? !document.querySelector('#couponRow').hidden : false, instr: (document.querySelector('#paymentInstructionsBox') || { innerText: '' }).innerText.trim().slice(0, 160) }));
      say(`  payment step: methods ${JSON.stringify(pay.methods)}; note «${pay.note}»; amount «${pay.amount}» total «${pay.total}»; card status «${pay.card}» (${pay.cardNo}); coupon row=${pay.coupon}; instructions «${pay.instr}»`);
      if (!pay.methods.some(m => m.includes(':selected'))) { await page.evaluate(() => { const b = [...document.querySelectorAll('#paymentMethodList [data-method]')].find(x => !x.disabled && !x.hidden); if (b) b.click(); }); await sleep(600); await snap(page, `${tag}-${label}-${String(i + 1).padStart(2, '0')}b-u9-selected`); say(`  after selecting method: CTA «${await txt(page, '#next', 40)}»; details «${await txt(page, '#paymentSelectionCard', 200)}»`); }
      if (stopAt === 'u9') break;
    }
    if (cur.active === 'u11') {
      say(`  receipt step: title «${await txt(page, '#receiptStepTitle', 80)}»; note «${await txt(page, '#receiptNote', 200)}»; upload control visible=${await visible(page, '#serverReceiptUpload')}; file input=${!!await page.$('#serverReceiptFile')}; review msg «${await txt(page, '#receiptReviewMessage', 160)}»; bale link visible=${await visible(page, '#receiptReviewBaleLink')}`);
      break;
    }
    if (cur.active === 'u12' || cur.active === 'u14' || cur.active === 'uUnavailable') break;
  }
  if (st.active === 'u12' || st.active === 'u14') say(`  end screen «${st.active}»: ${st.body.slice(0, 260)}`);
  const sum = {}; api.forEach(l => { sum[l] = (sum[l] || 0) + 1; });
  say(`  screens: ${seen.join(' → ')}; API: ${Object.entries(sum).map(([k, v]) => `${k}×${v}`).join('; ')}; JS errors: ${errors.length ? errors.join(' | ') : 'none'}`);
  return seen;
}

(async () => {
  for (const mobile of [false, true]) {
    const tag = mobile ? 'mobile' : 'desktop';
    say(`## guest / ${tag}`);
    /* free published form with a conditional question: pick «حضوری» → conditional question should be skipped */
    { const ctx = await context(mobile); const page = await ctx.newPage(); await step('free form حضوری', () => walk(page, FREE_FORM, 'free-hozoori', tag, { choice: 'حضوری' })); await ctx.close(); }
    if (!mobile) { const ctx = await context(mobile); const page = await ctx.newPage(); await step('free form آنلاین', () => walk(page, FREE_FORM, 'free-online', tag, { choice: 'آنلاین' })); await ctx.close(); }
    say('');
  }
  /* member purchase flow: 91012 (registered elsewhere, no purchase) up to the receipt step */
  for (const mobile of [false, true]) {
    const tag = mobile ? 'mobile' : 'desktop';
    say(`## member 91012 / ${tag}`);
    const ctx = await context(mobile); const page = await ctx.newPage();
    await step('member login', () => memberLogin(page, 91012));
    await step('purchase walk', () => walk(page, PURCHASE_FORM, 'purchase', tag, { stopAt: mobile ? 'u9' : null }));
    if (!mobile) await step('account after purchase attempt', async () => {
      await page.goto(ORIGIN + '/account.html#payments', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(3500);
      say(`- account.html#payments (91012): «${await txt(page, 'main, body', 360)}»`); await snap(page, 'desktop-member-account-payments');
    });
    say(''); await ctx.close();
  }
  /* owner: response detail row in builder + inbox as manager */
  {
    say('## owner / desktop — response detail'); const ctx = await context(false); const page = await ctx.newPage();
    await staffLogin(page, OWNER);
    await step('builder response detail', async () => {
      await page.goto(ORIGIN + '/builder.html', { waitUntil: 'load', timeout: 60000 }); await sleep(1500);
      await page.evaluate(() => document.querySelector('#syncServerForms').click());
      await page.waitForFunction(() => document.querySelectorAll('#formCards [data-form]').length > 0, { timeout: 25000 }); await sleep(1000);
      await page.evaluate(id => { const c = [...document.querySelectorAll('#formCards [data-form]')].find(c => c.dataset.form.startsWith(id)); (c.querySelector('[data-open]') || c).click(); }, FREE_FORM.slice(0, 8)); await sleep(1200);
      await page.click('#pSeg [data-tab="answers"]'); await sleep(2500);
      say(`- answers tab for [${FREE_FORM.slice(0, 8)}]: «${await txt(page, '#answersBox', 360)}»`); await snap(page, 'desktop-owner-r1-answers');
      const opened = await page.evaluate(() => { const r = document.querySelector('#answersBox [data-person]'); if (!r) return false; r.click(); return true; }); await sleep(2500);
      say(`  row opened=${opened}; active=${await page.evaluate(() => (document.querySelector('.screen.on') || {}).id)}; detail «${await txt(page, '#fUser', 420)}»`); await snap(page, 'desktop-owner-r2-response-detail');
      const del = await page.evaluate(() => !!document.querySelector('#fUser [data-delete-response], #fUser button.stop'));
      say(`  delete control present in detail=${del}`);
    });
    await ctx.close();
  }
  {
    say('## manager / desktop — shared inbox'); const ctx = await context(false); const page = await ctx.newPage();
    await staffLogin(page, MANAGER);
    await step('inbox', async () => {
      await page.goto(ORIGIN + '/admin.html#inbox', { waitUntil: 'load', timeout: 60000 }); await page.reload({ waitUntil: 'load', timeout: 60000 }); await sleep(4500);
      say(`- admin.html#inbox (manager): hash=${await page.evaluate(() => location.hash)}; body «${await txt(page, '#admBody', 420)}»`); await snap(page, 'desktop-manager-inbox');
      const first = await page.evaluate(() => { const r = document.querySelector('#admBody [data-task], #admBody [data-inbox-task], #admBody .admlirow button, #admBody article button'); if (!r) return null; r.click(); return r.innerText.trim().slice(0, 60); }); await sleep(2500);
      say(`  first task opened «${first}»; body now «${await txt(page, '#admBody', 420)}»`); await snap(page, 'desktop-manager-inbox-task');
    });
    await ctx.close();
  }
  say('DONE');
})().catch(e => { say('FATAL ' + e.stack); process.exit(1); });
