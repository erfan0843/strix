/* Phase 9.7 — form builder AUDIT (test server + test DB). Owner / manager / guest, desktop + mobile.
   Real staff login, real builder.html + create.html + form.html; findings from the DOM and from the real HTTP
   responses the pages make. Nothing from the credentials file is printed. No application code is changed. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { launchBrowser } = require(path.resolve(process.env.NORA_UI_DIR || '.', 'tools/browser-launch.cjs'));
const ORIGIN = process.env.NORA_QA_ORIGIN || 'http://127.0.0.1:8000';
const OUT = process.argv[2];
const creds = fs.readFileSync(path.resolve(process.env.NORA_UI_DIR || '.', 'PREVIEW-LOGIN.local.md'), 'utf8');
const pick = re => (creds.match(re) || [])[1];
const OWNER = { label: 'owner', user: pick(/مالک: `([^`]+)`/), pass: pick(/مالک: `[^`]+` \/ `([^`]+)`/) };
const MANAGER = { label: 'manager', user: pick(/مدیر: `([^`]+)`/), pass: pick(/مدیر: `[^`]+` \/ `([^`]+)`/) };
if (!OWNER.pass || !MANAGER.pass) throw new Error('credentials file not parsed');
const REG_FORM = process.env.REG_FORM || '43bf0182';
const PURCHASE_FORM = process.env.PURCHASE_FORM || 'e19a45ff';
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const say = l => { log.push(l); fs.writeFileSync(path.join(OUT, 'audit-checks.txt'), log.join('\n') + '\n'); };
const state = { newFormId: null };
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
async function staffLogin(page, who) {
  await page.goto(ORIGIN + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'load', timeout: 60000 });
  await page.waitForSelector('#lgStaffUsername', { timeout: 30000 });
  await page.fill('#lgStaffUsername', who.user); await page.fill('#lgStaffPassword', who.pass);
  await page.click('#lgStaffSubmit'); await sleep(3000);
  const go = await page.$('text=رفتن به پنل مدیریت'); if (go) { await page.evaluate(el => el.click(), go); await sleep(2500); }
  if (!/admin\.html/.test(page.url())) throw new Error('staff login did not reach the panel: ' + page.url());
}
function trackApi(page, bucket) {
  page.on('response', r => { const u = r.url(); if (u.includes('/api/')) bucket.push(`${r.request().method()} ${u.replace(ORIGIN, '').split('?')[0]} → ${r.status()}`); });
}

async function builderPass(page, who, tag) {
  const api = []; trackApi(page, api);
  await page.goto(ORIGIN + '/builder.html', { waitUntil: 'load', timeout: 60000 }); await sleep(1500);
  const autoCards = await page.evaluate(() => document.querySelectorAll('#formCards [data-form]').length);
  say(`- builder.html (${tag}/${who}) on load: ${autoCards} cards before pressing «گرفتن فرم‌های سرور» (button visible=${await visible(page, '#syncServerForms')}); message «${await txt(page, '#serverFormsMessageText', 160)}»`);
  await snap(page, `${tag}-${who}-b0-list-onload`);
  await page.evaluate(() => { const b = document.querySelector('#syncServerForms'); if (b) b.click(); });
  await page.waitForFunction(() => document.querySelectorAll('#formCards [data-form]').length > 0, { timeout: 25000 }).catch(() => {});
  await sleep(1500);
  const cards = await page.evaluate(() => [...document.querySelectorAll('#formCards [data-form]')].map(c => ({ id: c.dataset.form, text: c.innerText.replace(/\s+/g, ' ').trim().slice(0, 90) })));
  say(`- builder.html (${tag}/${who}): ${cards.length} form cards from server; message «${await txt(page, '#serverFormsMessageText', 160)}»; chips «${await txt(page, '#listChips', 120)}»`);
  say(`  first cards: ${cards.slice(0, 4).map(c => `[${c.id.slice(0, 8)}] ${c.text}`).join(' | ')}`);
  say(`  nav visible: financeNav=${await visible(page, '#financeNav')}, kartabl=${await visible(page, '[data-go="fKartabl"]')}, team=${await visible(page, '[data-go="fTeam"]')}`);
  await snap(page, `${tag}-${who}-b1-list`);
  const target = cards.find(c => c.id.startsWith(REG_FORM)) || cards[0];
  if (!target) { say('  ⚠️ no server form card to open'); return; }
  await page.evaluate(id => { const c = document.querySelector(`#formCards [data-form="${id}"]`); const b = c.querySelector('[data-open]') || c; b.click(); }, target.id);
  await sleep(1500);
  say(`  opened [${target.id.slice(0, 8)}]: active=${await page.evaluate(() => (document.querySelector('.screen.on') || {}).id)}, status «${await txt(page, '#pStatus', 60)}», sub «${await txt(page, '#pSub', 120)}», link «${await txt(page, '#pLink', 120)}»`);
  say(`  stats tab: «${await txt(page, '#statsBox', 260)}»`);
  await snap(page, `${tag}-${who}-b2-panel-stats`);
  for (const t of ['info', 'changes', 'answers']) {
    await page.click(`#pSeg [data-tab="${t}"]`); await sleep(2500);
    const box = { info: '#infoBox', changes: '#changesBox', answers: '#answersBox' }[t];
    say(`  tab ${t}: «${await txt(page, box, 300)}»`);
    await snap(page, `${tag}-${who}-b3-tab-${t}`);
  }
  for (const sec of ['fReports', 'fSettings', 'fKartabl', 'fMine', 'fTeam', 'fAttend', 'fMoney']) {
    const ok = await page.evaluate(s => { const b = document.querySelector(`[data-go="${s}"]`); if (!b || b.hidden) return false; b.click(); return true; }, sec);
    if (!ok) { say(`  section ${sec}: nav button hidden/absent`); continue; }
    await sleep(1500);
    say(`  section ${sec}: active=${await page.evaluate(() => (document.querySelector('.screen.on') || {}).id)}; «${await txt(page, '#' + sec, 260)}»`);
    await snap(page, `${tag}-${who}-b4-${sec}`);
  }
  const apiSummary = {}; api.forEach(l => { apiSummary[l] = (apiSummary[l] || 0) + 1; });
  say(`  API calls from builder.html: ${Object.entries(apiSummary).map(([k, v]) => `${k}×${v}`).join('; ')}`);
}

async function createPass(page, tag) {
  const api = []; trackApi(page, api);
  await page.goto(ORIGIN + '/create.html', { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
  say(`- create.html (${tag}/owner) step1: capability status «${await txt(page, '#formCapabilityStatus', 160)}»; owner api «${await txt(page, '#ownerApiState', 80)} / ${await txt(page, '#ownerApiMessage', 160)}»`);
  const tiles = await page.evaluate(() => [...document.querySelectorAll('[data-model]')].map(t => t.innerText.replace(/\s+/g, ' ').trim().slice(0, 70)));
  say(`  model tiles (${tiles.length}): ${tiles.join(' | ')}`);
  await snap(page, `${tag}-owner-c1-step1`);
  await page.click('[data-model="registration"]'); await sleep(400);
  await page.fill('#fTitle', '[QA ۹.۷] فرم ممیزی فرم‌ساز'); await page.dispatchEvent('#fTitle', 'input'); await sleep(400);
  say(`  model summary: «${await txt(page, '#modelCapabilitySummary', 200)}»; slug view «${await txt(page, '#slugView', 100)}»`);
  await page.click('#btnNext'); await sleep(800);
  say(`  step2 active=${await page.evaluate(() => (document.querySelector('.screen.on') || {}).id)}; hint «${await txt(page, '#stepHint', 120)}»`);
  await snap(page, `${tag}-owner-c2-fields-empty`);
  await page.click('[data-quick="basic"]'); await sleep(600);
  await page.click('#addTop'); await sleep(800);
  const cat = await page.evaluate(() => { const items = [...document.querySelectorAll('#catList [data-add]')]; return { total: items.length, disabled: items.filter(i => i.disabled).map(i => i.dataset.add), limited: items.filter(i => i.querySelector('.cap-tag.limited')).map(i => i.dataset.add) }; });
  say(`  catalog: ${cat.total} items; disabled (server unavailable): ${cat.disabled.join(',')}; limited: ${cat.limited.join(',')}`);
  await snap(page, `${tag}-owner-c3-catalog`);
  await page.click('#catList [data-add="choice"]'); await sleep(800);
  say(`  field editor opened=${await visible(page, '#shField')}; type «${await txt(page, '#fdType', 60)}»; struct «${await txt(page, '#fdStruct', 120)}»; verify box visible=${await visible(page, '#fdVerifyBox')}; cond box visible=${await visible(page, '#fdCondBox')}`);
  await page.fill('#fdTitle', 'نحوهٔ حضور'); await page.dispatchEvent('#fdTitle', 'input');
  const optCount = await page.evaluate(() => document.querySelectorAll('#fdOptions [data-optl]').length);
  for (let i = optCount; i < 2; i++) { await page.click('#fdAddOption'); await sleep(200); }
  await page.fill('#fdOptions [data-optl="0"]', 'حضوری'); await page.dispatchEvent('#fdOptions [data-optl="0"]', 'input');
  await page.fill('#fdOptions [data-optl="1"]', 'آنلاین'); await page.dispatchEvent('#fdOptions [data-optl="1"]', 'input');
  await page.evaluate(() => { const r = document.querySelector('#fdReq'); if (r && !r.classList.contains('on')) r.click(); });
  await snap(page, `${tag}-owner-c4-field-editor`);
  await page.evaluate(() => { const c = document.querySelector('#shField [data-close]'); if (c) c.click(); }); await sleep(600);
  await page.click('#addTop'); await sleep(500); await page.click('#catList [data-add="text"]'); await sleep(700);
  await page.fill('#fdTitle', 'لینک حضور آنلاین را کجا بفرستیم؟'); await page.dispatchEvent('#fdTitle', 'input');
  await page.click('#fdAddCondition'); await sleep(400);
  const condState = await page.evaluate(() => {
    const f = document.querySelector('#fdCondField'), o = document.querySelector('#fdCondOp'), v = document.querySelector('#fdCondVal');
    const opts = f ? [...f.options].map(x => x.text) : [];
    if (f) { const idx = [...f.options].findIndex(x => /حضور/.test(x.text)); if (idx >= 0) { f.selectedIndex = idx; f.dispatchEvent(new Event('change', { bubbles: true })); } }
    return { fields: opts, ops: o ? [...o.options].map(x => x.text) : [], valTag: v ? v.tagName : null };
  });
  await sleep(300);
  await page.evaluate(() => { const v = document.querySelector('#fdCondVal'); if (v && v.tagName === 'SELECT') { const idx = [...v.options].findIndex(x => /آنلاین/.test(x.text)); if (idx >= 0) { v.selectedIndex = idx; v.dispatchEvent(new Event('change', { bubbles: true })); } } else if (v) { v.value = 'آنلاین'; v.dispatchEvent(new Event('input', { bubbles: true })); } });
  await sleep(300);
  say(`  condition editor: source fields ${JSON.stringify(condState.fields)}; operators ${condState.ops.length}; value control ${condState.valTag}; hint «${await txt(page, '#fdCondHint', 160)}»; rules «${await txt(page, '#fdCondRules', 160)}»`);
  await snap(page, `${tag}-owner-c5-condition`);
  await page.evaluate(() => { const c = document.querySelector('#shField [data-close]'); if (c) c.click(); }); await sleep(600);
  const blocks = await page.evaluate(() => [...document.querySelectorAll('#fieldList .block')].map(b => b.querySelector('.qline').innerText.trim() + (b.querySelector('.tag.brand') ? ' [شرطی]' : '')));
  say(`  canvas fields (${blocks.length}): ${blocks.join(' | ')}`);
  await page.evaluate(() => { const b = document.querySelectorAll('#fieldList [data-down]')[0]; if (b) b.click(); }); await sleep(400);
  say(`  reorder via button: status «${await txt(page, '#fieldReorderStatus', 120)}»; help «${await txt(page, '#fieldReorderHelp', 120)}»; drag handles=${await page.evaluate(() => document.querySelectorAll('[data-drag-handle][draggable="true"]').length)}`);
  await snap(page, `${tag}-owner-c6-canvas`);
  await step('s2 more-panel settings', async () => {
    await page.fill('#cap', '50'); await page.dispatchEvent('#cap', 'input'); await page.dispatchEvent('#cap', 'change');
    say(`  s2 more-panel: cap set; schedule inputs present start=${!!await page.$('#pkStart')} end=${!!await page.$('#pkEnd')}; limitMode help «${await txt(page, '#limitModeHelp', 160)}»; ticketing switch=${!!await page.$('#ticketingEnabled')}`);
    await page.evaluate(() => window.scrollTo(0, 400)); await snap(page, `${tag}-owner-c6b-more-panel`);
  });
  await page.click('#btnNext'); await sleep(900);
  const fin = await page.evaluate(() => ({ canMoney: (typeof CAN_MONEY !== 'undefined') ? CAN_MONEY : 'n/a', financeOwner: !!(window.NORA_UI && NORA_UI.financeOwner && NORA_UI.financeOwner()), adminSession: !!localStorage.getItem('nora-admin-session'), people: ((window.NORA || {}).ADMIN || {}).people ? 'present' : 'absent', finCardHidden: document.querySelector('#finItemsCard').hidden, couponHidden: document.querySelector('#finCouponCard').hidden, methodsHidden: document.querySelector('#formPaymentMethodsCard').hidden, receiptCardHidden: document.querySelector('#receiptReviewCard') ? document.querySelector('#receiptReviewCard').hidden : 'n/a' }));
  say(`  s3 finance access as OWNER: CAN_MONEY=${fin.canMoney} (NORA_UI.financeOwner()=${fin.financeOwner}, localStorage nora-admin-session=${fin.adminSession}, NORA.ADMIN.people=${fin.people}); hidden: finItems=${fin.finCardHidden}, coupon=${fin.couponHidden}, customMethods=${fin.methodsHidden}, receiptCard=${fin.receiptCardHidden}`);
  say(`  step3 active=${await page.evaluate(() => (document.querySelector('.screen.on') || {}).id)}; finance notice «${await txt(page, '#financeOwnerNotice', 160)}»; payment status «${await txt(page, '#createPaymentStatus', 200)}»`);
  await snap(page, `${tag}-owner-c7-settings`);
  await step('settings values', async () => {
    await page.evaluate(() => { const g = document.querySelector('#guestsOn'); if (g && !g.classList.contains('on')) g.click(); });
    await sleep(300);
    await page.fill('#maxPer', '3').catch(() => {}); await page.dispatchEvent('#maxPer', 'input').catch(() => {});
    say(`  schedule inputs present: start=${await visible(page, '#pkStart')}, end=${await visible(page, '#pkEnd')}; limitMode «${await txt(page, '#limitModeHelp', 160)}»`);
    say(`  companions: compFields «${await txt(page, '#compFields', 120)}»; ticketing switch visible=${await visible(page, '#ticketingEnabled')}`);
  });
  await step('finance item', async () => {
    if (fin.finCardHidden) { say('  finance item: skipped — finance cards hidden for the real owner session (see CAN_MONEY)'); await page.evaluate(() => { const s = document.querySelector('#receiptReviewRequired'); if (s && !s.classList.contains('on')) s.click(); }); await sleep(400); say(`  receipt switch toggled anyway: card «${await txt(page, '#receiptReviewCard', 260)}»; payment status «${await txt(page, '#createPaymentStatus', 200)}»`); return; }
    await page.click('#addFin'); await sleep(400);
    await page.fill('#finList [data-fl="0"]', 'هزینهٔ شرکت'); await page.dispatchEvent('#finList [data-fl="0"]', 'input');
    await page.fill('#finList [data-fp="0"]', '1500000'); await page.dispatchEvent('#finList [data-fp="0"]', 'input'); await page.dispatchEvent('#finList [data-fp="0"]', 'change');
    await sleep(300);
    await page.fill('#dc', 'QA97'); await page.dispatchEvent('#dc', 'input'); await page.fill('#dp', '10'); await page.dispatchEvent('#dp', 'input');
    await page.evaluate(() => { const s = document.querySelector('#receiptReviewRequired'); if (s && !s.classList.contains('on')) s.click(); }); await sleep(400);
    say(`  finance: fin rows=${await page.evaluate(() => document.querySelectorAll('#finList [data-fl]').length)}; coupon inputs: code+percent+all (no expiry/usage-cap controls present=${await page.evaluate(() => !document.querySelector('#s3 [id*="couponExp"], #s3 [id*="couponLimit"], #s3 [id*="couponMax"]'))}); receipt card «${await txt(page, '#receiptReviewCard', 260)}»; bale wallet switch visible=${await visible(page, '#enableBaleWallet')}; payment status «${await txt(page, '#createPaymentStatus', 200)}»`);
    say(`  card summary «${await txt(page, '#createCardSummary', 160)}»`);
  });
  await snap(page, `${tag}-owner-c8-finance`);
  await page.click('#btnNext'); await sleep(900);
  say(`  step4 active=${await page.evaluate(() => (document.querySelector('.screen.on') || {}).id)}; review «${await txt(page, '#review', 420)}»`);
  await snap(page, `${tag}-owner-c9-review`);
  const [saveResp] = await Promise.all([
    page.waitForResponse(r => /\/api\/forms(\?|$)/.test(r.url()) && r.request().method() === 'POST', { timeout: 30000 }).catch(() => null),
    page.click('#publish'),
  ]);
  await sleep(2500);
  let created = null; if (saveResp) { try { created = await saveResp.json(); } catch (e) { created = null; } }
  state.newFormId = created && created.id || null;
  say(`  save draft → POST /api/forms ${saveResp ? saveResp.status() : 'no request'}; id=${state.newFormId ? state.newFormId.slice(0, 8) : null}; status=${created && created.status}; version=${created && created.version}; state «${await txt(page, '#ownerApiState', 80)} / ${await txt(page, '#ownerApiMessage', 200)}»`);
  say(`  done card: «${await txt(page, '#doneCard', 320)}»; publish btn visible=${await visible(page, '#donePublish')}; public link «${await txt(page, '#publicFormUrl', 120)}»`);
  await snap(page, `${tag}-owner-c10-saved`);
  await step('publish', async () => {
    const [pubResp] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/publish'), { timeout: 30000 }).catch(() => null),
      page.evaluate(() => { const b = document.querySelector('#donePublish'); if (b) b.click(); else throw new Error('donePublish missing'); }),
    ]);
    await sleep(2500);
    let body = null; if (pubResp) { try { body = await pubResp.json(); } catch (e) { body = null; } }
    say(`  publish → ${pubResp ? pubResp.status() : 'no request'} ${body && body.detail ? JSON.stringify(body.detail).slice(0, 200) : ''}; state «${await txt(page, '#ownerApiMessage', 200)}»; done card «${await txt(page, '#doneCard', 300)}»`);
    await snap(page, `${tag}-owner-c11-published`);
  });
  await step('reopen published form in editor', async () => {
    await page.goto(ORIGIN + '/create.html?fid=' + encodeURIComponent(state.newFormId), { waitUntil: 'load', timeout: 60000 }); await sleep(3500);
    say(`  reopen ?fid: url=${page.url().replace(ORIGIN, '').slice(0, 80)}; title field «${await page.$eval('#fTitle', e => e.value).catch(() => null)}»; fields on canvas=${await page.evaluate(() => { try { return S.fields.length; } catch (e) { return 'n/a'; } })}; api state «${await txt(page, '#ownerApiState', 80)} / ${await txt(page, '#ownerApiMessage', 220)}»; publish btn text «${await txt(page, '#publish', 60)}»`);
    await snap(page, `${tag}-owner-c12-reopen`);
    await page.evaluate(() => { try { go('s4'); } catch (e) {} }); await sleep(600);
    const [putResp] = await Promise.all([
      page.waitForResponse(r => /\/api\/forms\/[^/]+$/.test(r.url()) && r.request().method() === 'PUT', { timeout: 15000 }).catch(() => null),
      page.click('#publish'),
    ]);
    await sleep(2000);
    say(`  save on published form → ${putResp ? 'PUT ' + putResp.status() : 'no PUT sent (client blocked)'}; message «${await txt(page, '#ownerApiMessage', 220)}»`);
    await snap(page, `${tag}-owner-c13-readonly`);
  });
  const apiSummary = {}; api.forEach(l => { apiSummary[l] = (apiSummary[l] || 0) + 1; });
  say(`  API calls from create.html: ${Object.entries(apiSummary).map(([k, v]) => `${k}×${v}`).join('; ')}`);
}

async function publicPass(page, formId, label, tag, maxSteps = 9) {
  const api = []; trackApi(page, api);
  const errors = []; page.on('pageerror', e => errors.push(String(e.message).slice(0, 100)));
  await page.goto(ORIGIN + '/form.html?fid=' + encodeURIComponent(formId), { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
  const head = await page.evaluate(() => ({ title: document.title, active: (document.querySelector('.screen.on') || {}).id, h: (document.querySelector('.screen.on h1, .screen.on h2, #evTitle') || { innerText: '' }).innerText.trim().slice(0, 80), next: (document.querySelector('#next') || { innerText: '' }).innerText.trim(), body: (document.querySelector('.screen.on') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim().slice(0, 260) }));
  say(`- form.html (${tag}/guest) ${label} [${formId.slice(0, 8)}]: active=${head.active}; heading «${head.h}»; CTA «${head.next}»; body «${head.body}»`);
  await snap(page, `${tag}-guest-f-${label}-1-start`);
  let i = 0, last = head.active;
  while (i < maxSteps) {
    i++;
    const nextVisible = await visible(page, '#next'); if (!nextVisible) { say(`  step ${i}: #next not visible; stop`); break; }
    await page.evaluate(() => { const b = document.querySelector('#next'); b.click(); }); await sleep(1200);
    const cur = await page.evaluate(() => ({ active: (document.querySelector('.screen.on') || {}).id, body: (document.querySelector('.screen.on') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim().slice(0, 300), toast: (document.querySelector('#toast') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim().slice(0, 120), next: (document.querySelector('#next') || { innerText: '' }).innerText.trim(), inputs: [...document.querySelectorAll('.screen.on input, .screen.on select, .screen.on textarea')].filter(e => e.type !== 'hidden').length }));
    say(`  step ${i}: ${last} → ${cur.active}; CTA «${cur.next}»; inputs=${cur.inputs}; toast «${cur.toast}»; body «${cur.body.slice(0, 200)}»`);
    await snap(page, `${tag}-guest-f-${label}-${i + 1}-${cur.active}`);
    if (cur.active === last) {
      /* validation stopped us: fill the visible required inputs with synthetic values and try once more */
      await page.evaluate(() => {
        document.querySelectorAll('.screen.on input:not([type=hidden]), .screen.on textarea').forEach(e => {
          if (e.type === 'checkbox' || e.type === 'radio') { e.checked = true; e.dispatchEvent(new Event('change', { bubbles: true })); return; }
          const lbl = (e.closest('label, .fld, .q') || { innerText: '' }).innerText + ' ' + (e.placeholder || '') + ' ' + (e.name || '') + ' ' + (e.id || '');
          let v = 'آزمایش ۹.۷';
          if (/موبایل|mobile/.test(lbl) || e.type === 'tel') v = '09120000097';
          else if (/ملی|nid/.test(lbl)) v = '0012345678';
          else if (/ایمیل|email/.test(lbl) || e.type === 'email') v = 'qa97@example.test';
          else if (e.type === 'number') v = '1';
          e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true }));
        });
        const firstChoice = document.querySelector('.screen.on .opt, .screen.on [role=radio], .screen.on .choice button, .screen.on [data-opt]'); if (firstChoice) firstChoice.click();
      });
      await sleep(500);
      await page.evaluate(() => { const b = document.querySelector('#next'); b.click(); }); await sleep(1200);
      const again = await page.evaluate(() => ({ active: (document.querySelector('.screen.on') || {}).id, toast: (document.querySelector('#toast') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim().slice(0, 120), body: (document.querySelector('.screen.on') || { innerText: '' }).innerText.replace(/\s+/g, ' ').trim().slice(0, 240) }));
      say(`  step ${i} (after filling): → ${again.active}; toast «${again.toast}»; body «${again.body.slice(0, 200)}»`);
      await snap(page, `${tag}-guest-f-${label}-${i + 1}b-${again.active}`);
      if (again.active === cur.active) { say('  stuck on the same screen twice; stop'); break; }
      last = again.active;
    } else last = cur.active;
    if (last === 'u9' || last === 'u12' || last === 'uUnavailable' || last === 'u14') {
      const pay = await page.evaluate(() => ({ methods: [...document.querySelectorAll('#paymentMethodList [data-method]')].map(b => `${b.dataset.method}:${b.hidden ? 'hidden' : b.disabled ? 'disabled' : 'enabled'}`), note: (document.querySelector('#paymentStepNote') || { innerText: '' }).innerText.trim().slice(0, 160), total: (document.querySelector('#paymentTransferTotal, #payAmount') || { innerText: '' }).innerText.trim(), card: (document.querySelector('#paymentBankCardStatus') || { innerText: '' }).innerText.trim().slice(0, 120), coupon: !!document.querySelector('#couponRow') && !document.querySelector('#couponRow').hidden }));
      if (last === 'u9') say(`  payment step: methods ${JSON.stringify(pay.methods)}; note «${pay.note}»; total «${pay.total}»; card «${pay.card}»; coupon row=${pay.coupon}`);
      break;
    }
  }
  const apiSummary = {}; api.forEach(l => { apiSummary[l] = (apiSummary[l] || 0) + 1; });
  say(`  API calls: ${Object.entries(apiSummary).map(([k, v]) => `${k}×${v}`).join('; ')}; JS errors: ${errors.length ? errors.join(' | ') : 'none'}`);
}

(async () => {
  /* 1) owner desktop: builder + create (creates one synthetic form on the TEST DB) */
  {
    const ctx = await context(false); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e.message).slice(0, 120)));
    say('## owner / desktop');
    await staffLogin(page, OWNER);
    await step('builder owner desktop', () => builderPass(page, 'owner', 'desktop'));
    await step('create owner desktop', () => createPass(page, 'desktop'));
    say(`- page JS errors (owner desktop): ${errors.length ? errors.join(' | ') : 'none'}`); say('');
    await ctx.close();
  }
  /* 2) owner mobile: builder + create step1/2 look only */
  {
    const ctx = await context(true); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e.message).slice(0, 120)));
    say('## owner / mobile');
    await staffLogin(page, OWNER);
    await step('builder owner mobile', () => builderPass(page, 'owner', 'mobile'));
    await step('create owner mobile', async () => {
      await page.goto(ORIGIN + '/create.html', { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
      await snap(page, 'mobile-owner-c1-step1');
      await page.click('[data-model="registration"]'); await page.fill('#fTitle', 'نمونهٔ موبایل'); await page.dispatchEvent('#fTitle', 'input'); await page.click('#btnNext'); await sleep(700);
      await page.click('[data-quick="full"]'); await sleep(700); await snap(page, 'mobile-owner-c2-fields');
      const ov = await page.evaluate(() => ({ docW: document.documentElement.scrollWidth, winW: innerWidth, ctx: !!document.querySelector('.ctxbar'), handles: document.querySelectorAll('[data-drag-handle]').length }));
      say(`- create.html mobile: horizontal overflow=${ov.docW > ov.winW} (${ov.docW}/${ov.winW}); field blocks have ctxbar=${ov.ctx}, drag handles=${ov.handles}`);
      await page.evaluate(() => { const b = document.querySelector('#fieldList [data-edit]'); if (b) b.click(); }); await sleep(700); await snap(page, 'mobile-owner-c3-field-editor');
      await page.evaluate(() => { const c = document.querySelector('#shField [data-close]'); if (c) c.click(); }); await sleep(400);
      await page.click('#btnNext'); await sleep(700); await snap(page, 'mobile-owner-c4-settings');
      if (state.newFormId) { await page.goto(ORIGIN + '/create.html?fid=' + encodeURIComponent(state.newFormId), { waitUntil: 'load', timeout: 60000 }); await sleep(3000); await page.evaluate(() => { try { go('s4'); } catch (e) {} }); await sleep(600); await snap(page, 'mobile-owner-c5-review-saved'); }
    });
    say(`- page JS errors (owner mobile): ${errors.length ? errors.join(' | ') : 'none'}`); say('');
    await ctx.close();
  }
  /* 3) manager desktop: builder + create?fid (publish should be owner-only) */
  {
    const ctx = await context(false); const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e.message).slice(0, 120)));
    say('## manager / desktop');
    await staffLogin(page, MANAGER);
    await step('builder manager desktop', () => builderPass(page, 'manager', 'desktop'));
    await step('create manager desktop', async () => {
      await page.goto(ORIGIN + '/create.html', { waitUntil: 'load', timeout: 60000 }); await sleep(2500);
      say(`- create.html (manager): step1 api state «${await txt(page, '#ownerApiState', 80)} / ${await txt(page, '#ownerApiMessage', 200)}»; capability «${await txt(page, '#formCapabilityStatus', 160)}»`);
      await page.click('[data-model="registration"]'); await page.fill('#fTitle', '[QA ۹.۷] پیش‌نویس مدیر'); await page.dispatchEvent('#fTitle', 'input'); await page.click('#btnNext'); await sleep(600);
      await page.click('[data-quick="basic"]'); await sleep(500); await page.click('#btnNext'); await sleep(600);
      say(`  manager step3: finance notice «${await txt(page, '#financeOwnerNotice', 200)}»; finList «${await txt(page, '#finList', 160)}»; addFin disabled=${await page.$eval('#addFin', e => e.disabled).catch(() => 'n/a')}; receipt card «${await txt(page, '#receiptReviewCard', 160)}»`);
      await snap(page, 'desktop-manager-c8-finance');
      await page.click('#btnNext'); await sleep(600);
      const [saveResp] = await Promise.all([page.waitForResponse(r => /\/api\/forms(\?|$)/.test(r.url()) && r.request().method() === 'POST', { timeout: 30000 }).catch(() => null), page.click('#publish')]);
      await sleep(2500);
      let created = null; if (saveResp) { try { created = await saveResp.json(); } catch (e) {} }
      say(`  manager save draft → ${saveResp ? saveResp.status() : 'no request'}; id=${created && created.id ? created.id.slice(0, 8) : null}; message «${await txt(page, '#ownerApiMessage', 220)}»; publish btn visible=${await visible(page, '#donePublish')}; done card «${await txt(page, '#doneCard', 260)}»`);
      await snap(page, 'desktop-manager-c10-saved');
      if (created && created.id) {
        const pub = await page.evaluate(async id => { const r = await fetch(`/api/forms/${id}/publish`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'fetch' }, body: '{}' }); let t = ''; try { t = (await r.text()).slice(0, 160); } catch (e) {} return { status: r.status, t }; }, created.id);
        say(`  manager direct POST /publish → ${pub.status} ${pub.t}`);
        state.managerFormId = created.id;
      }
    });
    say(`- page JS errors (manager desktop): ${errors.length ? errors.join(' | ') : 'none'}`); say('');
    await ctx.close();
  }
  /* 4) guest public forms: desktop + mobile */
  for (const mobile of [false, true]) {
    const tag = mobile ? 'mobile' : 'desktop';
    const ctx = await context(mobile); const page = await ctx.newPage();
    say(`## guest / ${tag}`);
    if (state.newFormId) await step('public new form', () => publicPass(page, state.newFormId, 'new-paid', tag));
    await step('public registration form', () => publicPass(page, REG_FORM_FULL || REG_FORM, 'event-reg', tag));
    await step('public purchase form', () => publicPass(page, PURCHASE_FORM_FULL || PURCHASE_FORM, 'purchase', tag, 4));
    await step('unpublished form', async () => { if (!state.managerFormId) return; await publicPass(page, state.managerFormId, 'draft', tag, 1); });
    say('');
    await ctx.close();
  }
  say('DONE');
})().catch(e => { say('FATAL ' + e.stack); process.exit(1); });
var REG_FORM_FULL = process.env.REG_FORM_FULL || null;
var PURCHASE_FORM_FULL = process.env.PURCHASE_FORM_FULL || null;
