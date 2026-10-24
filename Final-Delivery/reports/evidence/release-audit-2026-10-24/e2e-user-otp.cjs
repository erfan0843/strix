/* ورود کاربر عادی با OTP در محیط تست (کانال پیامک جعلی: tools/otp-sink-preview.py) — هیچ پیامک/پیام بله‌ای فرستاده نمی‌شود.
   اجرا: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node deps> NORA_REPO_UI=<nora-ui> \
         NORA_E2E_BACKEND=http://127.0.0.1:8004 NORA_OTP_SINK_FILE=<sink.jsonl> NORA_CAPTCHA_ORACLE="<python> <oracle.py>" node e2e-user-otp.cjs <out-dir> */
const path = require('path'); const fs = require('fs'); const { execFileSync } = require('child_process');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const BASE = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8004';
const SINK = process.env.NORA_OTP_SINK_FILE; const ORACLE = (process.env.NORA_CAPTCHA_ORACLE || '').split(' ').filter(Boolean);
const out = process.argv[2] || path.join(__dirname, 'user-otp-shots'); fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const lines = []; let pass = 0, fail = 0;
const L = (...a) => { const s = a.map(x => typeof x === 'string' ? x : JSON.stringify(x)).join(' '); lines.push(s); console.log(s); };
const check = (name, ok) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + name + (ok ? '' : ' ✗')); };
const PHONE = '09120000' + String(Date.now()).slice(-3); // شمارهٔ آزمایشی؛ هیچ پیامکی به آن نمی‌رود

(async () => {
  const browser = await launchBrowser();
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'fa-IR', isMobile: true, hasTouch: true });
  const page = await ctx.newPage(); page.on('dialog', d => d.accept());
  const shot = (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const has = sel => page.evaluate(q => !!document.querySelector(q), sel);
  const txt = sel => page.evaluate(q => { const e = document.querySelector(q); return e ? e.textContent.trim() : null; }, sel);
  const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (e) {} await sleep(150); } return false; };
  const api = (p, init) => page.evaluate(async ([p, init]) => { const r = await fetch(p, Object.assign({ credentials: 'same-origin' }, init || {})); let b = null; try { b = await r.json(); } catch (e) {} return { status: r.status, body: b }; }, [p, init || null]);
  const sinkLines = () => (fs.existsSync(SINK) ? fs.readFileSync(SINK, 'utf8').trim().split('\n').filter(Boolean) : []);
  try {
    const before = sinkLines().length;
    // ۱) صفحهٔ ورود کاربر (نه مدیران): فقط شماره + کد امنیتی؛ بدون رمز
    await page.goto(BASE + '/login.html?next=account.html', { waitUntil: 'load' }); await sleep(1200);
    check('login page: phone form shown, no staff password field', await has('#lgPhoneForm') && await has('#lgPhone') && !(await has('#lgStaffPassword')));
    check('captcha image rendered from server', await waitFor(() => has('#lgCapImg img')) );
    await shot('01-login-phone', true);
    // ۲) کد امنیتی را با همان تابع سرور (اوراکل آزمون روی توکنِ خود صفحه) حل می‌کنیم — نه با دور زدن
    await page.fill('#lgPhone', PHONE);
    const [capResp] = await Promise.all([page.waitForResponse(r => r.url().includes('/api/auth/captcha') && r.status() === 200, { timeout: 8000 }), page.click('#lgCapNew')]);
    const capToken = (await capResp.json()).token; await sleep(300);
    let answer = '';
    try { answer = execFileSync(ORACLE[0], ORACLE.slice(1).concat([capToken]), { encoding: 'utf8' }).trim(); } catch (e) { L('oracle failed', String(e.message || e)); }
    check('captcha solved through the server verifier (test oracle)', /^\d{4}$/.test(answer));
    await page.fill('#lgCapAnswer', answer);
    const [reqResp] = await Promise.all([page.waitForResponse(r => r.url().includes('/api/auth/phone-otp/request'), { timeout: 10000 }), page.click('#lgPhoneSubmit')]);
    L('otp request status', reqResp.status());
    check('OTP request accepted (200) through the real endpoint', reqResp.status() === 200);
    check('code step shown with masked destination + resend', await waitFor(() => has('#lgOtpCode')) && await has('#lgOtpResend'));
    await shot('02-otp-code-step', true);
    // ۳) کد از فایل سینک محلی می‌آید (نه پیامک)؛ یک رکورد جدید، شمارهٔ همین آزمون
    const after = sinkLines(); const last = after.length ? JSON.parse(after[after.length - 1]) : null;
    check('exactly one code written to the local sink for this phone (no SMS)', after.length === before + 1 && last && last.phone.endsWith(PHONE.slice(1)) && /^\d{4,8}$/.test(last.code));
    // ۴) کد اشتباه → خطا و ماندن در همان مرحله؛ کد درست → نشست کاربر
    await page.fill('#lgOtpCode', '000000');
    const [badResp] = await Promise.all([page.waitForResponse(r => r.url().includes('/api/auth/phone-otp/verify'), { timeout: 10000 }), page.click('#lgOtpVerify')]);
    check('wrong code rejected by server (4xx), still on code step', badResp.status() >= 400 && badResp.status() < 500 && await has('#lgOtpCode'));
    await sleep(400);
    await page.fill('#lgOtpCode', last.code);
    const [okResp] = await Promise.all([page.waitForResponse(r => r.url().includes('/api/auth/phone-otp/verify'), { timeout: 10000 }), page.click('#lgOtpVerify')]);
    L('otp verify status', okResp.status());
    check('correct code → verify 200', okResp.status() === 200);
    check('login page shows authenticated state / continue to account', await waitFor(async () => (await has('#lgAuthenticated')) || (await has('#lgContinue')) || /account\.html/.test(page.url())));
    await shot('03-otp-verified', true);
    // ۵) نشست واقعی کاربر: /api/account/me احراز شده با provider تلفن؛ بدون نقش ستادی
    const me = await api('/api/account/me'); L('account/me', { status: me.status, authenticated: me.body && me.body.authenticated, provider: me.body && me.body.provider, role: me.body && me.body.role });
    check('account/me: authenticated phone user, no staff role', me.status === 200 && me.body.authenticated === true && /phone/.test(String(me.body.provider || '')) && !me.body.role);
    // ۶) مجوزها در API: کاربر عادی به پروندهٔ رویداد/مدیریت نمی‌رسد
    const ev = await api('/api/admin/content/events?limit=1'); const forms = await api('/api/forms');
    check('user session: admin events API 401/403', ev.status === 401 || ev.status === 403);
    check('user session: forms (owner) API 401/403', forms.status === 401 || forms.status === 403);
    // ۷) صفحهٔ حساب با نشست کاربر باز می‌شود
    await page.goto(BASE + '/account.html', { waitUntil: 'load' }); await sleep(1500);
    check('account page loads for the phone user', /account\.html/.test(page.url()) && !/login\.html/.test(page.url()));
    await shot('04-account-page', true);
    // ۸) ورود مستقیم به پنل مدیران با نشست کاربر: به ورود مدیران برمی‌گردد یا پنل قفل است (هیچ دادهٔ مدیریتی نمی‌آید)
    await page.goto(BASE + '/admin.html#events', { waitUntil: 'load' }); await sleep(2500);
    const adminUrl = page.url(); const adminApi = await api('/api/admin/content/events?limit=1');
    L('admin direct', { url: adminUrl.replace(BASE, ''), adminApi: adminApi.status });
    check('direct admin URL with a user session: no admin data (API 401/403)', adminApi.status === 401 || adminApi.status === 403);
    await shot('05-admin-direct-as-user', true);
    // ۹) خروج
    const noCsrf = await api('/api/auth/account/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    check('logout without CSRF token is refused (403) and the session stays', noCsrf.status === 403 && (await api('/api/account/me')).body.authenticated === true);
    const logout = await page.evaluate(async () => { const m = document.cookie.match(/(?:^|; )nora_account_csrf=([^;]+)/); const r = await fetch('/api/auth/account/logout', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': m ? decodeURIComponent(m[1]) : '' }, body: '{}' }); return r.status; });
    const meAfter = await api('/api/account/me'); L('logout', { status: logout, authenticatedAfter: meAfter.body && meAfter.body.authenticated });
    check('logout with CSRF ends the session (account/me unauthenticated)', (logout === 200 || logout === 204) && !(meAfter.body && meAfter.body.authenticated === true));
  } catch (e) { L('E2E crashed: ' + (e && e.stack || e)); fail++; }
  L('TOTAL PASS ' + pass + ' / FAIL ' + fail);
  fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\n');
  await browser.close(); process.exit(fail ? 1 : 0);
})();
