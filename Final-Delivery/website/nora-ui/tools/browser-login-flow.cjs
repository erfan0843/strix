// End-to-end browser check of the member login path (development-only QA).
//
//   خانه → «ورود/ثبت‌نام» → account.html (نمای مهمان) → «ورود» → login.html?mode=server&next=…
//   → کپچای سرور (تصویر PNG، تازه‌سازی) → ارسال شماره با پاسخ غلط → پیام خطای سرور
//   → (اختیاری) موفقیت OTP با endpoint شبیه‌سازی‌شده در مرورگر → حفظ مقصد بازگشت
//   → (اختیاری) حساب عضو با کوکی نشست آزمایشی: #forms / #payments / #pay / دکمهٔ بازگشت
//
// Never sends a real Bale OTP message: the only successful OTP path is route-mocked inside the
// browser (NORA_QA_MOCK_OTP=0 disables it). Run against a loopback test server only.
//
//   NORA_QA_PUBLIC_URL=http://127.0.0.1:8000  NORA_QA_BROWSER=sparticuz \
//   NORA_QA_MEMBER_COOKIES="nora_account_session=…; nora_account_csrf=…" \
//   node tools/browser-login-flow.cjs
const path = require('node:path');
const fs = require('node:fs');
const { launchBrowser, localOrigin } = require('./browser-launch.cjs');

const origin = localOrigin(process.env.NORA_QA_PUBLIC_URL || 'http://127.0.0.1:8000');
const qaRoot = path.resolve(__dirname, '../.local/qa');
const reportPath = process.env.NORA_QA_LOGIN_REPORT || path.join(qaRoot, 'login-flow.json');
const shotDir = process.env.NORA_QA_SHOT_DIR || path.join(qaRoot, 'login-flow');
const mockOtp = process.env.NORA_QA_MOCK_OTP !== '0';
const memberCookies = String(process.env.NORA_QA_MEMBER_COOKIES || '').split(';').map(s => s.trim()).filter(Boolean)
  .map(pair => { const i = pair.indexOf('='); return { name: pair.slice(0, i), value: pair.slice(i + 1), url: origin }; });
const viewports = { mobile: { width: 390, height: 844 }, desktop: { width: 1280, height: 800 } };

const results = [];
let failed = 0;
function check(ok, label, detail) {
  results.push({ ok: !!ok, label, detail: detail === undefined ? '' : String(detail).slice(0, 300) });
  if (!ok) failed += 1;
  console.log((ok ? '✓ ' : '✗ ') + label + (detail && !ok ? ' — ' + String(detail).slice(0, 160) : ''));
}
function watch(page) {
  const log = { errors: [], failures: [] };
  page.on('pageerror', e => log.errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) log.errors.push(m.text()); });
  page.on('requestfailed', r => log.failures.push(r.url()));
  return log;
}
const rel = url => url.replace(origin + '/', '');
async function shot(page, name) {
  fs.mkdirSync(shotDir, { recursive: true });
  await page.screenshot({ path: path.join(shotDir, name + '.png') }).catch(() => {});
}
async function storageKeys(page) {
  return page.evaluate(() => Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter(k => /otp|phone|challenge|captcha|session|token/i.test(k)));
}

async function guestFlow(browser, vp) {
  const context = await browser.newContext({ viewport: viewports[vp], locale: 'fa-IR', serviceWorkers: 'block' });
  const page = await context.newPage();
  const log = watch(page);
  const tag = `[${vp}] `;

  // 1) خانه → تب «ورود/ثبت‌نام»
  await page.goto(origin + '/home.html', { waitUntil: 'load' });
  await page.waitForTimeout(1200);
  const nav = page.locator('.tabbar [data-account-nav]').first();
  check(await nav.count() === 1 && /ورود\/ثبت‌نام/.test(await nav.innerText()), tag + 'تب «ورود/ثبت‌نام» در نوار پایین خانه برای مهمان دیده می‌شود');
  await Promise.all([page.waitForNavigation({ waitUntil: 'load', timeout: 15000 }).catch(() => {}), nav.click()]);
  await page.waitForTimeout(1200);
  const authSheetOpen = await page.evaluate(() => !!document.querySelector('#shAuth.on, #shAccount.on, #uimob, #srvmob'));
  check(/\/account\.html$/.test(page.url().split('#')[0]) && !authSheetOpen, tag + 'کلیک «ورود/ثبت‌نام» به account.html می‌رود و ورقهٔ ورود قدیمی باز نمی‌شود', page.url() + ' sheet=' + authSheetOpen);
  await shot(page, `01-account-guest-${vp}`);

  // ۴۰۱ برای داده‌های خصوصی بدون نشست (از همان صفحهٔ مهمان؛ کروم تک‌پردازشی کوکی‌ها را بین context‌ها مشترک می‌کند)
  const guestApiCode = await page.evaluate(async base => (await fetch(base + '/api/account/registrations?limit=5&offset=0', { credentials: 'same-origin' })).status, origin).catch(() => null);
  check(guestApiCode === 401, tag + 'بدون نشست، API ثبت‌نام‌های حساب ۴۰۱ می‌دهد', 'HTTP ' + guestApiCode);

  // 2) نمای مهمان حساب: کارت‌های طراحی و دکمهٔ ورود امن
  const promo = await page.locator('.account-promo, #profBox').first().innerText().catch(() => '');
  check(/نورا پی/.test(promo) && /باشگاه کتاب‌خوانی/.test(promo), tag + 'نمای مهمان حساب، «نورا پی» و «باشگاه کتاب‌خوانی» را نشان می‌دهد');
  check(!/۵۴۳۲۱|حساب نمونه|ورود آزمایشی/.test(promo), tag + 'هیچ کد نمونه یا حساب آزمایشی در نمای مهمان نیست');
  const loginBtn = page.locator('#profBox a[href^="login.html?mode=server"]').first();
  check(await loginBtn.count() > 0, tag + 'دکمهٔ ورود مهمان به login.html?mode=server اشاره می‌کند', await loginBtn.getAttribute('href').catch(() => ''));

  // 3) مسیر نورا پی برای مهمان: #pay → #payments → ورود با next=payments
  await page.goto(origin + '/account.html#pay', { waitUntil: 'load' });
  await page.waitForTimeout(1200);
  const payView = await page.locator('#viewBox').innerText().catch(() => '');
  check(/پرداخت‌ها/.test(payView) && !/موجودی|کیف پول/.test(payView), tag + '#pay قدیمی در نسخهٔ سروری همان نمای پرداخت‌های واقعی را باز می‌کند', payView.slice(0, 80));
  const payLogin = page.locator('#viewBox a[href^="login.html?mode=server"]').first();
  const payHref = await payLogin.getAttribute('href').catch(() => '');
  check(payHref === 'login.html?mode=server&next=account.html%23payments', tag + 'دکمهٔ ورود در پرداخت‌ها مقصد #payments را نگه می‌دارد', payHref);
  await Promise.all([page.waitForNavigation({ waitUntil: 'load', timeout: 15000 }).catch(() => {}), payLogin.click()]);
  await page.waitForTimeout(1500);
  check(/\/login\.html\?mode=server&next=account\.html%23payments$/.test(page.url()), tag + 'به صفحهٔ ورود مستقل با next رسیدیم', page.url());

  // 4) صفحهٔ ورود: فرم، کپچای سرور، تازه‌سازی
  const phone = page.locator('#lgPhone');
  const answer = page.locator('#lgCapAnswer');
  check(await phone.isVisible() && await answer.isVisible() && await page.locator('#lgPhoneSubmit').isVisible(), tag + 'فرم شماره، کد امنیتی و دکمهٔ «دریافت کد» دیده می‌شوند');
  const capImg = page.locator('#lgCapImg img.lg-cap-pic');
  const capStatus = await page.evaluate(() => (document.querySelector('#lgStatus') || {}).textContent || '');
  const captchaAvailable = await capImg.count() === 1;
  const slotHtml = await page.evaluate(() => (document.querySelector('#lgCapImg') || {}).innerHTML || '');
  if (captchaAvailable) {
    const src1 = await capImg.getAttribute('src');
    check(/^data:image\/png;base64,/.test(src1) && !/<svg|<text|[0-9]{4}/.test(slotHtml.replace(/src="[^"]*"/, '')), tag + 'کپچا تصویر PNG سرور است و رقمی در DOM خوانده نمی‌شود');
    await page.locator('#lgCapNew').click();
    await page.waitForTimeout(1200);
    const src2 = await page.locator('#lgCapImg img.lg-cap-pic').getAttribute('src').catch(() => '');
    check(src2 && src2 !== src1, tag + '«کد جدید» تصویر کپچای تازه می‌گیرد');
  } else {
    check(/کد امنیتی بارگذاری نشد/.test(capStatus), tag + 'بدون NORA_OTP_PEPPER، خطای کپچا با پیام روشن نمایش داده می‌شود (کپچا در این سرور پیکربندی نشده)', capStatus);
  }
  await shot(page, `02-login-${vp}`);

  // 5) ارسال شماره با پاسخ غلط → خطای سرور با پیام قابل فهم، بدون نشست محلی
  await phone.fill('09120000000');
  await answer.fill('0000');
  const [reqResponse] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/auth/phone-otp/request'), { timeout: 10000 }).catch(() => null),
    page.locator('#lgPhoneSubmit').click(),
  ]);
  await page.waitForTimeout(1500);
  const status = await page.locator('#lgStatus').innerText().catch(() => '');
  const code = reqResponse ? reqResponse.status() : null;
  check(code === 422 || code === 503 || code === 429, tag + 'درخواست کد واقعاً به سرور رفت و با خطای سرور پاسخ گرفت', 'HTTP ' + code);
  check(status.trim().length > 0 && !(await page.locator('#lgPhoneCodeForm').count()), tag + 'پیام خطا نمایش داده شد و گام کد باز نشد', status);
  check((await storageKeys(page)).length === 0, tag + 'هیچ شماره/کد/نشستی در storage مرورگر ذخیره نشد');
  await shot(page, `03-login-error-${vp}`);
  results.push({ ok: true, label: tag + 'وضعیت سرویس ارسال کد بله (Safir) در این سرور', detail: 'HTTP ' + code + ' · ' + status.trim().slice(0, 120) });

  // 6) موفقیت OTP فقط با endpoint شبیه‌سازی‌شده (پیام واقعی بله ارسال نمی‌شود) → حفظ مقصد
  if (mockOtp) {
    const challenge = '11111111-2222-4333-8444-555555555555';
    await page.route('**/api/auth/phone-otp/request', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ accepted: true, challenge_id: challenge, expires_in: 180, resend_in: 90 }) }));
    await page.route('**/api/auth/phone-otp/verify', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: true, account_id: 'qa-mock-account', provider: 'phone' }) }));
    await page.route('**/api/account/me', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: true, account_id: 'qa-mock-account', provider: 'phone', role: null, permissions: [] }) }));
    await page.locator('#lgCapNew').click().catch(() => {});
    await page.waitForTimeout(1200);
    await page.locator('#lgPhone').fill('09120000000');
    await page.locator('#lgCapAnswer').fill('1234');
    await page.locator('#lgPhoneSubmit').click();
    await page.waitForSelector('#lgPhoneCodeForm', { timeout: 8000 }).catch(() => {});
    check(await page.locator('#lgOtpCode').count() === 1, tag + '[mock] پس از پاسخ موفق سرور، گام کد ۶ رقمی باز می‌شود');
    await page.locator('#lgOtpCode').fill('123456');
    await Promise.all([
      page.waitForURL(/\/account\.html#payments$/, { timeout: 10000 }).catch(() => {}),
      page.locator('#lgPhoneCodeForm button[type=submit]').first().click(),
    ]);
    await page.waitForTimeout(1200);
    check(/\/account\.html#payments$/.test(page.url()), tag + '[mock] پس از تأیید سرور، مرورگر خودکار به همان مقصد account.html#payments برمی‌گردد', page.url());
    check((await storageKeys(page)).length === 0, tag + '[mock] پس از ورود هم چیزی در storage مرورگر نیست');
    await shot(page, `04-login-done-${vp}`);
    await page.unroute('**/api/auth/phone-otp/request'); await page.unroute('**/api/auth/phone-otp/verify'); await page.unroute('**/api/account/me');
  }

  // 7) مسیر مدیران جداست
  await page.goto(origin + '/login.html?mode=staff&next=admin.html%23dash', { waitUntil: 'load' });
  await page.waitForTimeout(1000);
  check(await page.locator('#lgPhone').count() === 0 && await page.locator('input[type=password]').count() === 1, tag + 'ورود مدیران فرم نام کاربری/گذرواژه دارد و با ورود عضو یکی نیست');

  check(log.errors.length === 0, tag + 'در کل مسیر مهمان هیچ خطای JavaScript رخ نداد', log.errors.join(' | '));
  await page.close();
}

async function memberFlow(browser, vp) {
  const tag = `[${vp}] `;
  if (!memberCookies.length) {
    results.push({ ok: true, label: tag + 'مسیر عضو اجرا نشد', detail: 'NORA_QA_MEMBER_COOKIES تنظیم نشده' });
    console.log('– ' + tag + 'مسیر عضو: کوکی نشست آزمایشی داده نشده؛ رد شد');
    return;
  }
  const context = await browser.newContext({ viewport: viewports[vp], locale: 'fa-IR', serviceWorkers: 'block' });
  await context.addCookies(memberCookies);
  const page = await context.newPage();
  const log = watch(page);
  await page.goto(origin + '/account.html', { waitUntil: 'load' });
  await page.waitForSelector('.server-account-head', { timeout: 10000 }).catch(() => {});
  const head = await page.locator('#profBox').innerText().catch(() => '');
  check(/وصل است/.test(head) && /نورا پی/.test(head) && /باشگاه کتاب‌خوانی/.test(head), tag + 'عضو واردشده سر صفحه، نورا پی و بخش‌های من را می‌بیند');
  await shot(page, `05-account-member-${vp}`);
  const tab = await page.locator('.tabbar [data-account-nav]').first().innerText().catch(() => '');
  check(!/ورود\/ثبت‌نام/.test(tab), tag + 'برچسب تب حساب برای عضو دیگر «ورود/ثبت‌نام» نیست', tab);

  await page.goto(origin + '/account.html#forms', { waitUntil: 'load' });
  await page.waitForSelector('#viewBox .server-registration, #viewBox .empty, #viewBox [data-server-account-retry]', { timeout: 10000 }).catch(() => {});
  const forms = await page.locator('#viewBox').innerText().catch(() => '');
  const regCall = await page.evaluate(() => performance.getEntriesByType('resource').some(e => /\/api\/account\/registrations/.test(e.name)));
  check(regCall && !/۵۴۳۲۱|نمونه/.test(forms), tag + '#forms فهرست را از API حساب می‌خواند و دادهٔ نمونه ندارد');
  await shot(page, `06-account-forms-${vp}`);

  await page.goto(origin + '/account.html#pay', { waitUntil: 'load' });
  await page.waitForTimeout(1200);
  const payText = await page.locator('#viewBox').innerText();
  check(/پرداخت‌ها و رسیدها/.test(payText) && /ثبت‌نام/.test(payText), tag + '#pay قدیمی برای عضو هم نمای پرداخت‌های واقعی ثبت‌نام‌ها را باز می‌کند', payText.slice(0, 80));
  check(!/موجودی:|تومان/.test(payText), tag + 'در پرداخت‌ها هیچ موجودی یا مبلغ نمونه‌ای نشان داده نمی‌شود');
  await shot(page, `07-account-payments-${vp}`);

  await page.goBack({ waitUntil: 'load' }).catch(() => {});
  await page.waitForTimeout(1000);
  check(/#forms/.test(page.url()) || /#payments/.test(page.url()), tag + 'دکمهٔ بازگشت مرورگر بین بخش‌های حساب کار می‌کند', page.url());

  await page.goto(origin + '/account.html#book', { waitUntil: 'load' });
  await page.waitForTimeout(1200);
  const book = await page.locator('#viewBox').innerText();
  check(/باشگاه/.test(book) && !/چراغ‌ها را من خاموش می‌کنم|۱۲ عضو/.test(book), tag + 'باشگاه کتاب‌خوانی با حالت خالی روشن و بدون کتاب نمونه');

  check(log.errors.length === 0, tag + 'در مسیر عضو هیچ خطای JavaScript رخ نداد', log.errors.join(' | '));
  await page.close();
}

(async () => {
  let browser;
  try {
    for (const vp of ['mobile', 'desktop']) {
      browser = await launchBrowser();
      if (vp === 'mobile') console.log('Chromium', browser.version(), '·', origin, '· mock OTP:', mockOtp);
      await guestFlow(browser, vp);
      await browser.close().catch(() => {});
      browser = await launchBrowser();
      await memberFlow(browser, vp);
      await browser.close().catch(() => {});
      browser = null;
    }
  } finally {
    if (browser) await browser.close().catch(() => {});
    fs.mkdirSync(path.dirname(reportPath), { recursive: true });
    fs.writeFileSync(reportPath, JSON.stringify({ origin, mockOtp, member: memberCookies.length > 0, results }, null, 2));
  }
  console.log(`\nlogin-flow: ${results.filter(r => r.ok).length} قبول، ${failed} خطا → ${reportPath}`);
  if (failed) process.exitCode = 1;
})().catch(e => { console.error(e); process.exitCode = 1; });
