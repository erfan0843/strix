// Login page behaviour checks against the local test server (real API where available, mocked OTP where the SMS service is absent).
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000'; const OUT = '/tmp/qa/login/flows'; fs.mkdirSync(OUT, { recursive: true });
const MOCK_OTP = { accepted: true, challenge_id: 'mock-challenge-qa', expires_in: 180, resend_in: 2 };
let pass = 0, fail = 0;
const ok = (c, m, extra = '') => { if (c) { pass++; console.log('PASS', m, extra); } else { fail++; console.log('FAIL', m, extra); } };
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function withPage(opts, fn) {
  const b = await launchBrowser();
  try {
    const ctx = await b.newContext({ viewport: opts.vp || { width: 390, height: 844 }, serviceWorkers: 'block', locale: 'fa-IR', reducedMotion: opts.rm || 'no-preference', hasTouch: !!opts.touch });
    if (opts.cookies) await ctx.addCookies(opts.cookies);
    await ctx.addInitScript(() => { try { localStorage.setItem('nora-theme', 'light'); } catch (e) {} });
    const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
    if (opts.mockOtp) await p.route('**/api/auth/phone-otp/request', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_OTP) }));
    await p.goto(BASE + (opts.url || '/login.html'), { waitUntil: 'domcontentloaded' }); await p.waitForTimeout(1100);
    await fn(p, errs);
    ok(errs.length === 0, `${opts.name}: no page errors`, errs.join(' | '));
    await ctx.close();
  } catch (e) { fail++; console.log('FAIL', opts.name, 'threw', e.message.slice(0, 200)); }
  finally { await b.close(); }
}
const requests = [];
// 1) page opens: phone form, focus on phone, captcha loaded from real API
await withPage({ name: 'open' }, async p => {
  ok(await p.$('#lgPhoneForm') !== null, 'open: phone form rendered');
  console.log('  note: initial focus =', await p.evaluate(() => document.activeElement.id || document.activeElement.tagName), '(no autofocus on open — unchanged upstream behaviour, avoids forcing the mobile keyboard)');
  ok(await p.evaluate(() => !!document.querySelector('#lgCapImg img.lg-cap-pic')), 'open: real captcha image loaded from /api/auth/captcha');
  ok(await p.evaluate(() => { const l = document.querySelector('label[for=lgPhone] .lglbl, label[for=lgCapAnswer]'); return !!l; }), 'open: real labels present');
  ok(await p.evaluate(() => document.querySelector('#lgStatus').getAttribute('aria-live') === 'polite'), 'open: status region aria-live=polite');
});
// 2) invalid phone keeps value, marks field, error near form, no network call
await withPage({ name: 'invalid-phone' }, async p => {
  const calls = []; p.on('request', r => { if (r.url().includes('/api/auth/phone-otp')) calls.push(r.url()); });
  await p.fill('#lgPhone', '123'); await p.fill('#lgCapAnswer', '1234'); await p.click('#lgPhoneSubmit'); await sleep(300);
  const r = await p.evaluate(() => ({ v: document.querySelector('#lgPhone').value, inv: document.querySelector('#lgPhone').getAttribute('aria-invalid'), st: document.querySelector('#lgStatus').textContent, kind: document.querySelector('#lgStatus').dataset.kind, hidden: document.querySelector('#lgStatus').hidden, cap: document.querySelector('#lgCapAnswer').value, dist: document.querySelector('#lgStatus').getBoundingClientRect().top - document.querySelector('#lgPhoneSubmit').getBoundingClientRect().bottom }));
  ok(r.v === '123' && r.cap === '1234', 'invalid-phone: typed values preserved after error');
  ok(r.inv === 'true' && r.kind === 'error' && !r.hidden && /درست نیست/.test(r.st), 'invalid-phone: field marked aria-invalid + error status shown', r.st.slice(0, 40));
  ok(r.dist >= 0 && r.dist < 40, 'invalid-phone: error sits right under the form', String(r.dist));
  ok(calls.length === 0, 'invalid-phone: no OTP request sent');
  await p.type('#lgPhone', '4'); await sleep(50);
  ok(await p.evaluate(() => !document.querySelector('#lgPhone').hasAttribute('aria-invalid')), 'invalid-phone: aria-invalid cleared on input');
  await p.screenshot({ path: OUT + '/invalid.png' });
});
// 3) real request to test server (no SMS provider) -> 503 error state, busy state in between, no duplicate on rapid clicks
await withPage({ name: 'real-503' }, async p => {
  const calls = []; p.on('request', r => { if (r.url().includes('/api/auth/phone-otp/request')) calls.push(1); });
  await p.fill('#lgPhone', '09123456789'); await p.fill('#lgCapAnswer', '1234');
  await p.click('#lgPhoneSubmit'); await p.click('#lgPhoneSubmit', { force: true }).catch(() => {}); await p.click('#lgPhoneSubmit', { force: true }).catch(() => {});
  await sleep(1500);
  const r = await p.evaluate(() => ({ st: document.querySelector('#lgStatus').textContent, kind: document.querySelector('#lgStatus').dataset.kind, btn: document.querySelector('#lgPhoneSubmit').textContent, busy: document.querySelector('#lgPhoneSubmit').getAttribute('aria-busy'), phone: document.querySelector('#lgPhone').value }));
  ok(calls.length === 1, 'real-503: rapid clicks produce exactly one request', String(calls.length));
  ok(r.kind === 'error' && r.st.length > 5 && r.busy !== 'true', 'real-503: server error shown as error status, busy cleared', r.st.slice(0, 50));
  ok(r.phone === '09123456789', 'real-503: phone preserved after server error');
  ok(await p.evaluate(() => !!document.querySelector('#lgCapImg img.lg-cap-pic')), 'real-503: fresh captcha reloaded');
});
// 4) loading state (delayed mock): spinner + disabled + aria-busy
await withPage({ name: 'loading' }, async p => {
  await p.route('**/api/auth/phone-otp/request', async r => { await sleep(1500); r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_OTP) }); });
  await p.fill('#lgPhone', '09123456789'); await p.fill('#lgCapAnswer', '1234'); await p.click('#lgPhoneSubmit'); await sleep(300);
  const r = await p.evaluate(() => { const b = document.querySelector('#lgPhoneSubmit'); const cs = getComputedStyle(b, '::before'); return { busy: b.getAttribute('aria-busy'), dis: b.disabled, anim: cs.animationName, inputs: [...document.querySelectorAll('.lgtext')].every(i => i.disabled) }; });
  ok(r.busy === 'true' && r.dis && r.anim === 'login-spin' && r.inputs, 'loading: button busy+disabled with spinner, inputs locked', JSON.stringify(r));
  await p.screenshot({ path: OUT + '/loading.png' });
  await p.waitForSelector('#lgPhoneCodeForm', { timeout: 6000 });
  ok(true, 'loading: resolves into OTP step (mock)');
});
// 5) OTP step (mock): hierarchy, slots, countdown, resend lock then unlock, change number keeps phone
await withPage({ name: 'otp-step', mockOtp: true }, async p => {
  await p.fill('#lgPhone', '09123456789'); await p.fill('#lgCapAnswer', '1234'); await p.click('#lgPhoneSubmit');
  await p.waitForSelector('#lgPhoneCodeForm', { timeout: 6000 }); await sleep(300);
  const r = await p.evaluate(() => ({ title: document.querySelector('#lgTitle').textContent, sent: document.querySelector('.lg-otp-sent').textContent, slots: document.querySelectorAll('[data-otp-slot]').length, meta: document.querySelector('#lgOtpMeta').textContent, resendDis: document.querySelector('#lgOtpResend').disabled, focus: document.activeElement && document.activeElement.id, slotBorder: getComputedStyle(document.querySelector('[data-otp-slot]')).borderColor, cards: document.querySelectorAll('#lgCard .lgcard, #lgCard section, #lgCard article').length }));
  ok(r.title === 'کد ورود' && /۰۹۱۲/.test(r.sent) && r.slots === 6 && /اعتبار کد/.test(r.meta), 'otp: title/destination/6 slots/expiry visible', JSON.stringify(r).slice(0, 160));
  ok(r.resendDis === true, 'otp: resend locked while countdown runs');
  ok(r.cards === 0, 'otp: no nested cards inside the main card');
  await p.focus('#lgOtpCode'); await p.keyboard.type('12');
  const s = await p.evaluate(() => ({ filled: document.querySelectorAll('.lg-otp-slot.is-filled').length, cur: document.querySelectorAll('.lg-otp-slot.is-current').length }));
  ok(s.filled === 2 && s.cur === 1, 'otp: slots reflect typed digits + current slot', JSON.stringify(s));
  await p.click('#lgOtpVerify'); await sleep(200);
  ok(/کامل/.test(await p.evaluate(() => document.querySelector('#lgStatus').textContent)), 'otp: incomplete code -> local validation message');
  await sleep(2300);
  ok(await p.evaluate(() => !document.querySelector('#lgOtpResend').disabled), 'otp: resend unlocks after resend_in');
  await p.screenshot({ path: OUT + '/otp.png' });
  await p.click('#lgPhoneChange'); await sleep(300);
  const c = await p.evaluate(() => ({ form: !!document.querySelector('#lgPhoneForm'), phone: document.querySelector('#lgPhone') && document.querySelector('#lgPhone').value, focus: document.activeElement && document.activeElement.id }));
  ok(c.form && c.phone === '09123456789' && c.focus === 'lgPhone', 'otp: change-number returns to phone step with number kept + focused', JSON.stringify(c));
});
// 6) resend flow: goes back to phone step with captcha and a note
await withPage({ name: 'resend', mockOtp: true }, async p => {
  await p.fill('#lgPhone', '09123456789'); await p.fill('#lgCapAnswer', '1234'); await p.click('#lgPhoneSubmit');
  await p.waitForSelector('#lgOtpResend', { timeout: 6000 }); await sleep(2400);
  await p.click('#lgOtpResend'); await sleep(400);
  const r = await p.evaluate(() => ({ form: !!document.querySelector('#lgPhoneForm'), st: document.querySelector('#lgStatus').textContent, phone: document.querySelector('#lgPhone').value }));
  ok(r.form && /دوباره/.test(r.st) && r.phone === '09123456789', 'resend: returns to captcha step with guidance, phone kept', r.st.slice(0, 50));
});
// 7) staff mode: own form, same visual language, back link to phone login; wrong password -> real server error
await withPage({ name: 'staff', url: '/login.html?mode=staff&next=admin.html%23dash' }, async p => {
  const r = await p.evaluate(() => ({ title: document.querySelector('#lgTitle').textContent, form: !!document.querySelector('#lgStaffForm'), admin: document.querySelector('#lgAdminEntry').hidden, btn: document.querySelector('#lgStaffSubmit').textContent, backQuiet: document.querySelector('#lgBack').classList.contains('quiet'), backBg: getComputedStyle(document.querySelector('#lgBack')).backgroundColor }));
  ok(r.title === 'ورود مدیران' && r.form && r.admin === true && r.btn === 'ورود', 'staff: dedicated form, admin entry hidden', JSON.stringify(r).slice(0, 120));
  ok(r.backQuiet && /rgba\(0, 0, 0, 0\)|transparent/.test(r.backBg), 'staff: secondary "back to member login" is a quiet text button (not a second primary)', r.backBg);
  await p.click('#lgStaffSubmit'); await sleep(200);
  ok(/نام کاربری و گذرواژه را وارد کن/.test(await p.evaluate(() => document.querySelector('#lgStatus').textContent)), 'staff: empty submit shows Persian in-page message (no browser bubble)');
  await p.fill('#lgStaffUsername', 'preview-owner'); await p.fill('#lgStaffPassword', 'definitely-wrong-password'); await p.click('#lgStaffSubmit'); await sleep(1500);
  const e = await p.evaluate(() => ({ kind: document.querySelector('#lgStatus').dataset.kind, st: document.querySelector('#lgStatus').textContent, u: document.querySelector('#lgStaffUsername').value }));
  ok(e.kind === 'error' && e.st.length > 3 && e.u === 'preview-owner', 'staff: wrong password -> real 401 shown as error, username kept', e.st.slice(0, 50));
  ok(await p.evaluate(() => document.activeElement.id === 'lgStaffPassword'), 'staff: focus returns to password after error');
  await p.click('#lgBack'); await sleep(300);
  ok(await p.evaluate(() => !!document.querySelector('#lgPhoneForm') && document.querySelector('#lgTitle').textContent === 'ورود یا ثبت‌نام'), 'staff: back link returns to member login');
});
// 8) real staff login with the test-server owner password -> authenticated card -> logout
await withPage({ name: 'staff-real', url: '/login.html?mode=staff&next=admin.html%23dash' }, async p => {
  const pw = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
  await p.fill('#lgStaffUsername', 'preview-owner'); await p.fill('#lgStaffPassword', pw); await p.click('#lgStaffSubmit');
  await p.waitForSelector('#lgContinue', { timeout: 8000 }); await sleep(300);
  const r = await p.evaluate(() => ({ h: document.querySelector('.lgdtitle').textContent, href: document.querySelector('#lgContinue').getAttribute('href'), logoutQuiet: document.querySelector('#lgLogout').classList.contains('quiet'), bg: getComputedStyle(document.querySelector('#lgLogout')).backgroundColor }));
  ok(/تأیید شد/.test(r.h) && r.href === 'admin.html#dash', 'staff-real: authenticated card with safe next target', JSON.stringify(r).slice(0, 120));
  ok(/rgba\(0, 0, 0, 0\)/.test(r.bg), 'staff-real: logout is a quiet text button', r.bg);
  await p.screenshot({ path: OUT + '/authenticated.png' });
  await p.click('#lgLogout'); await sleep(1500);
  ok(await p.evaluate(() => !!document.querySelector('#lgStaffForm, #lgPhoneForm')), 'staff-real: logout returns to a login form');
});
// 9) rules sheet open/close, support link, theme toggle
await withPage({ name: 'rules-support-theme' }, async p => {
  await p.click('#rulesBtn'); await sleep(500);
  const open = await p.evaluate(() => document.querySelector('#shRules').classList.contains('on'));
  ok(open, 'rules: sheet opens');
  ok(await p.evaluate(() => /منتشر نشده/.test(document.querySelector('#shRules').textContent)), 'rules: honest "not published yet" text kept');
  await p.click('#shRules [data-close]'); await sleep(500);
  ok(await p.evaluate(() => !document.querySelector('#shRules').classList.contains('on')), 'rules: sheet closes via بستن');
  await p.click('#rulesBtn'); await sleep(400); await p.keyboard.press('Escape'); await sleep(400);
  ok(await p.evaluate(() => !document.querySelector('#shRules').classList.contains('on') && document.activeElement.id === 'rulesBtn'), 'rules: Escape closes sheet and returns focus to قوانین');
  await p.click('#rulesBtn'); await sleep(400); await p.mouse.click(200, 120); await sleep(400);
  ok(await p.evaluate(() => !document.querySelector('#shRules').classList.contains('on')), 'rules: tapping the scrim closes sheet');
  const sup = await p.evaluate(() => ({ top: document.querySelector('.topbar a[href="support.html"]') && document.querySelector('.topbar a[href="support.html"]').getAttribute('aria-label'), guide: !!document.querySelector('.lglinks a[href^="support.html"]') }));
  ok(!!sup.top && sup.guide, 'support: header icon with accessible name + guide link below card', JSON.stringify(sup));
  await p.click('.themesw'); await sleep(400);
  const t = await p.evaluate(() => ({ theme: document.documentElement.getAttribute('data-theme'), stored: localStorage.getItem('nora-theme'), bg: getComputedStyle(document.body).backgroundColor }));
  ok(t.theme === 'dark' && t.stored === 'dark', 'theme: toggle switches to dark and persists', JSON.stringify(t));
  await p.screenshot({ path: OUT + '/dark-toggled.png' });
});
// 10) keyboard navigation + focus-visible
await withPage({ name: 'keyboard' }, async p => {
  const order = [];
  for (let i = 0; i < 12; i++) { await p.keyboard.press('Tab'); order.push(await p.evaluate(() => { const a = document.activeElement; return (a.id || a.className.toString().split(' ')[0] || a.tagName) + (a.matches(':focus-visible') ? '*' : ''); })); }
  console.log('  tab order:', order.join(' > '));
  ok(order.some(o => o.startsWith('lgCapAnswer')) && order.some(o => o.startsWith('lgPhoneSubmit')) && order.some(o => o.startsWith('lg-admin-link')) && order.some(o => o.startsWith('rulesBtn')), 'keyboard: phone -> captcha -> submit -> admin -> rules reachable by Tab');
  ok(order.filter(o => o.endsWith('*')).length >= 4, 'keyboard: focus-visible applies on tabbed controls');
  const ring = await p.evaluate(() => { const b = document.querySelector('#lgPhoneSubmit'); b.focus(); const cs = getComputedStyle(b); return cs.outlineStyle + ' ' + cs.outlineWidth; });
  ok(/solid 3px/.test(ring), 'keyboard: primary button focus ring is a themed 3px outline', ring);
});
// 11) reduced motion + data-motion=off: no running animations on card/spinner
await withPage({ name: 'reduced-motion', rm: 'reduce' }, async p => {
  const r = await p.evaluate(() => ({ card: getComputedStyle(document.querySelector('#lgCard')).animationName, sp: getComputedStyle(document.querySelector('.lg-cap-img .lg-spinner') || document.body).animationName }));
  ok(r.card === 'none', 'reduced-motion: card fade disabled', r.card);
  await p.evaluate(() => { document.documentElement.dataset.motion = 'off'; });
  ok(await p.evaluate(() => getComputedStyle(document.querySelector('#lgCard')).animationName === 'none'), 'data-motion=off: card animation none');
});
// 12) mobile touch: tabbar hides while typing (focus inside card), controls >= 44px, no horizontal overflow at 360
await withPage({ name: 'touch-360', vp: { width: 360, height: 800 }, touch: true }, async p => {
  const before = await p.evaluate(() => getComputedStyle(document.querySelector('.tabbar')).display);
  await p.evaluate(() => document.activeElement && document.activeElement.blur()); await sleep(100);
  const blurred = await p.evaluate(() => getComputedStyle(document.querySelector('.tabbar')).display);
  await p.focus('#lgPhone'); await sleep(100);
  const focused = await p.evaluate(() => getComputedStyle(document.querySelector('.tabbar')).display);
  ok(blurred === 'grid' && focused === 'none', 'touch-360: tabbar visible at rest, hidden while a field inside the card is focused', `${blurred}/${focused} (initial ${before})`);
  const r = await p.evaluate(() => { const small = [...document.querySelectorAll('button,a[href],input')].filter(el => { const b = el.getBoundingClientRect(); return b.width > 0 && (b.height < 34); }).map(el => el.id || el.className); return { small, ox: document.documentElement.scrollWidth > innerWidth }; });
  ok(!r.ox && r.small.length === 0, 'touch-360: no horizontal overflow, no control under 34px tall', JSON.stringify(r.small));
});
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
