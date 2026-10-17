/* آزمون ورود نورا: OTP پیامکی Safir، نشست سروری و فرم مستقل مالک */
import { readFile } from 'node:fs/promises';
import { JSDOM } from 'jsdom';

const dir = new URL('./', import.meta.url);
const html = await readFile(new URL('login.html', dir), 'utf8');
const script = await readFile(new URL('login.js', dir), 'utf8');
const dataScript = await readFile(new URL('data.js', dir), 'utf8');
const delay = (ms = 0) => new Promise((resolve) => setTimeout(resolve, ms));
let passed = 0;
let failed = 0;
function check(condition, label) {
  if (condition) { passed++; console.log(`✓ ${label}`); }
  else { failed++; console.error(`✗ ${label}`); }
}

/* یک PNG یک‌پیکسلی معتبر؛ فقط برای این‌که قرارداد data URI سرور شبیه‌سازی شود. */
const CAPTCHA_PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
function reply(status, body = {}) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}
const unauthorized = () => reply(401, { detail: 'authentication_required' });

async function load({ routes = {}, cookie = '', url = 'https://nora.test/login.html' } = {}) {
  const dom = new JSDOM(html, { runScripts: 'outside-only', url, pretendToBeVisual: true });
  const { window } = dom;
  window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
  window.scrollTo = () => {};
  if (cookie) window.document.cookie = cookie;

  const storageOps = [];
  const storage = window.localStorage;
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: new Proxy(storage, {
      get(target, property) {
        if (['getItem', 'setItem', 'removeItem', 'clear'].includes(String(property))) {
          return (...args) => {
            storageOps.push({ method: String(property), key: String(args[0] || '') });
            return target[property](...args);
          };
        }
        return Reflect.get(target, property);
      },
    }),
  });

  const calls = [];
  const queues = new Map(Object.entries(routes).map(([path, values]) => [path, [...values]]));
  window.fetch = async (urlValue, options = {}) => {
    const path = String(urlValue);
    calls.push({ url: path, options });
    if (queues.has(path)) {
      const queue = queues.get(path);
      if (!queue.length) throw new Error(`No mocked response left for ${path}`);
      return queue.shift();
    }
    if (path === '/api/auth/captcha') return reply(200, { token: 'captcha-token-test', image: CAPTCHA_PNG, expires_in: 180 });
    if (path === '/api/auth/me' || path === '/api/account/me') return unauthorized();
    throw new Error(`No mocked response for ${path}`);
  };

  window.eval(script);
  window.document.dispatchEvent(new window.Event('DOMContentLoaded', { bubbles: true }));
  await delay(5);

  const click = (selector) => {
    const element = window.document.querySelector(selector);
    if (element) element.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true }));
    return element;
  };
  const text = (selector) => window.document.querySelector(selector)?.textContent.trim() || '';
  const fill = (selector, value) => {
    const element = window.document.querySelector(selector);
    if (element) {
      element.value = value;
      element.dispatchEvent(new window.Event('input', { bubbles: true }));
      element.dispatchEvent(new window.Event('change', { bubbles: true }));
    }
    return element;
  };
  const submit = (selector) => {
    const element = window.document.querySelector(selector);
    if (element) element.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    return element;
  };
  return { dom, window, doc: window.document, calls, storageOps, click, fill, submit, text };
}

console.log('\n— ورود عضو با OTP پیامکی Safir —');
{
  const p = await load();
  check(p.doc.title === 'ورود به نورا' && p.doc.documentElement.lang === 'fa' && p.doc.documentElement.dir === 'rtl', 'عنوان و زبان فارسی صفحه درست است');
  check(!!p.doc.querySelector('#lgPhoneForm') && !p.doc.querySelector('#lgPhoneCodeForm'), 'گام نخست فقط شمارهٔ همراه می‌خواهد');
  check(!p.doc.querySelector('#lgDemoPhoneForm, #lgDemoCaptcha, #lgChooseBale, #lgChoosePhone, #lgLogin'), 'پیش‌نمایش، CAPTCHA و روش‌های ورود غیرمرتبط از UI حذف شده‌اند');
  check(!html.includes('tapi.bale.ai/miniapp.js') && !html.includes('پیش‌نمایش محلی'), 'SDK مینی‌اپ و متن پیش‌نمایش در صفحه نیست');
  check(p.doc.querySelectorAll('#lgPhoneCodeMethod a[href*="verification_code_bot"]').length === 0, 'فرم ورود وب از ابتدا لینک ربات OTP بله ندارد');
  check(!p.doc.body.textContent.includes('نشست'), 'متن قابل‌مشاهدهٔ صفحهٔ ورود اصطلاح «نشست» را نمایش نمی‌دهد');
  check(p.calls.map((call) => call.url).filter((url) => url !== '/api/auth/captcha').join(',') === '/api/auth/me,/api/account/me', 'نشست موجود فقط از endpointهای سرور خوانده می‌شود');
  check(p.calls.every((call) => call.options.credentials === 'same-origin' && call.options.cache === 'no-store'), 'خواندن نشست هم‌مبدأ و بدون cache است');
  const managementLinks = [...p.doc.querySelectorAll('#lgAdminEntry a')];
  check(managementLinks.length === 1 && managementLinks[0].textContent.trim() === 'ورود مدیران', 'برچسب ورود مدیریت فقط «مدیران» را نشان می‌دهد');
  check(managementLinks[0]?.getAttribute('href') === 'login.html?mode=staff&next=admin.html%23dash', 'فرم مشترک مدیریت از مسیر عضو جداست');
  check(!p.doc.querySelector('#lgAdminEntry').hidden, 'پیوندهای نام کاربری و گذرواژه در گام ورود عضو در دسترس‌اند');
  p.dom.window.close();
}

console.log('\n— نبود API ورود وب در پیش‌نمایش محلی —');
{
  const p = await load({
    url: 'https://nora.test/login.html?mode=staff&next=admin.html%23dash',
    routes: {
      '/api/auth/me': [reply(404, { error: 'not_found' })],
      '/api/account/me': [reply(404, { error: 'not_found' })],
      '/api/auth/staff-login': [reply(404, { error: 'not_found' })],
    },
  });
  await delay(8);
  check(p.text('#lgStatus').includes('این پیش‌نمایش API ورود وب ندارد'), '404 سرویس به‌جای خطای شبکه، نبود API ورود وب را توضیح می‌دهد');
  check(p.doc.querySelector('#lgStaffForm') && p.text('#lgTitle') === 'ورود مدیران', 'فرم ورود مستقل وب بدون وابستگی به ورود بله باز می‌شود');
  p.fill('#lgStaffUsername', 'manager');
  p.fill('#lgStaffPassword', 'not-a-real-password');
  p.submit('#lgStaffForm');
  await delay(8);
  check(p.text('#lgStatus').includes('API ورود وب در این پیش‌نمایش فعال نیست'), 'ورود در حالت preview ادعای پذیرش اعتبارنامه نمی‌کند');
  p.dom.window.close();
}

console.log('\n— درخواست و تأیید OTP پیامکی Safir —');
{
  const challengeId = '4fcb1516-b3c9-41ec-a840-01dc18598322';
  const p = await load({ routes: {
    '/api/auth/phone-otp/request': [reply(200, { accepted: true, challenge_id: challengeId, expires_in: 180, resend_in: 90 })],
    '/api/auth/phone-otp/verify': [reply(200, { authenticated: true, account_id: 'phone-account-1', provider: 'phone' })],
    '/api/account/me': [unauthorized(), reply(200, {
      authenticated: true, account_id: 'phone-account-1', provider: 'phone', role: null, permissions: [],
    })],
  } });
  p.fill('#lgPhone', '۰۹۱۲۳۴۵۶۷۸۹');
  p.fill('#lgCapAnswer', '4321');
  p.submit('#lgPhoneForm');
  await delay(8);
  const request = p.calls.find((call) => call.url === '/api/auth/phone-otp/request');
  check(request?.options.method === 'POST' && request.options.credentials === 'same-origin' && request.options.cache === 'no-store', 'درخواست شماره به endpoint واقعی OTP می‌رود');
  check(JSON.stringify(JSON.parse(request?.options.body || '{}')) === JSON.stringify({ phone: '۰۹۱۲۳۴۵۶۷۸۹', captcha_token: 'captcha-token-test', captcha_answer: '4321' }), 'درخواست شماره با کپچای تأییدشده به backend می‌رود');
  check(!!p.doc.querySelector('#lgPhoneCodeForm'), 'پس از پاسخ موفق سرور، گام کد باز می‌شود');
  const smsNotice = p.doc.querySelector('#lgPhoneCodeMethod .lg-otp-sent');
  check(smsNotice?.textContent.includes('ربات بله') && smsNotice.textContent.includes('ارسال شد')
      && !smsNotice.textContent.includes('پیامک'), 'گام کد، ارسال از ربات بله را معرفی می‌کند');
  check(smsNotice?.getAttribute('role') === 'status'
      && p.doc.querySelectorAll('#lgPhoneCodeMethod a[href]').length === 0,
    'اعلان وضعیت در دسترس است و هیچ پیوند ورود جداگانه‌ای نمایش داده نمی‌شود');
  check(p.doc.querySelector('#lgOtpCode')?.getAttribute('autocomplete') === 'one-time-code'
      && p.doc.querySelector('#lgOtpCode')?.maxLength === 6
      && p.doc.querySelectorAll('#lgPhoneCodeMethod [data-otp-slot]').length === 6,
    'ورودی شش‌خانه‌ای از autocomplete امن پشتیبانی می‌کند');
  check(p.doc.querySelector('#lgOtpResend')?.disabled && p.text('#lgOtpResend').includes('۹۰'), 'ارسال مجدد تا زمان اعلام‌شده از سرور غیرفعال است');
  check(!p.doc.querySelector('#lgAdminEntry').hidden && p.doc.querySelectorAll('#lgAdminEntry a').length === 1, 'فرم مشترک مدیر و مالک مستقل از گام OTP می‌ماند');

  const codeInput = p.doc.querySelector('#lgOtpCode');
  p.click('#lgPhoneCodeMethod .lg-otp-control');
  check(p.doc.activeElement !== codeInput, 'فضای بین خانه‌های کد ورودی را فعال نمی‌کند');
  p.click('#lgPhoneCodeMethod [data-otp-slot="2"]');
  check(p.doc.activeElement === codeInput, 'فقط کلیک روی خانهٔ کد ورودی را فعال می‌کند');
  p.fill('#lgOtpCode', 'x۰۰۴۲۷۱z');
  check(codeInput.value === '۰۰۴۲۷۱'
      && [...p.doc.querySelectorAll('#lgPhoneCodeMethod [data-otp-slot]')].map((slot) => slot.textContent).join('') === '۰۰۴۲۷۱',
    'فقط رقم‌ها در خانه‌های متناظر نمایش داده می‌شوند');
  p.submit('#lgPhoneCodeForm');
  await delay(10);
  const verify = p.calls.find((call) => call.url === '/api/auth/phone-otp/verify');
  check(verify?.options.method === 'POST' && verify.options.credentials === 'same-origin' && verify.options.cache === 'no-store', 'کد به endpoint واقعی تأیید سرور می‌رود');
  check(JSON.stringify(JSON.parse(verify?.options.body || '{}')) === JSON.stringify({ challenge_id: challengeId, phone: '۰۹۱۲۳۴۵۶۷۸۹', code: '004271' }), 'کد فارسی پیش از ارسال نرمال و challenge به همان شماره متصل می‌شود');
  check(p.calls.some((call) => call.url === '/api/account/me'), 'پس از تأیید، کوکی نشست با endpoint حساب دوباره بررسی می‌شود');
  check(!!p.doc.querySelector('#lgAuthenticated') && p.text('#lgAuthenticated').includes('ورود با شمارهٔ همراه تأیید شد'), 'ورود OTP فقط پس از تأیید نشست سرور با هویت شمارهٔ همراه اعلام می‌شود');
  check(!!p.doc.querySelector('#lgOrganization'), 'نام مؤسسه پس از تأیید OTP نیز روی صفحه می‌ماند');
  check(p.doc.querySelector('#lgContinue')?.getAttribute('href') === 'account.html', 'عضو به حساب خود می‌رود، نه پنل مدیریت');
  check(p.storageOps.length === 0, 'شماره، کد یا نشست در localStorage ذخیره نمی‌شود');
  p.dom.window.close();
}

console.log('\n— مسیر پیوند حساب: بازگشت پس از ورود با شماره —');
{
  /* کاربری که از مسیر پیوند حساب (`account.html?link=bale`) به ورود آمده باید
     پس از تأیید شماره به همان مسیر برگردد؛ وگرنه نشانهٔ مسیر گم می‌شود و صفحه
     ورود خودکار مینی‌اپ را دوباره فعال می‌کند. */
  const phoneRoutes = () => ({
    '/api/auth/phone-otp/request': [reply(200, { accepted: true, challenge_id: 'link-challenge', expires_in: 180, resend_in: 90 })],
    '/api/auth/phone-otp/verify': [reply(200, { authenticated: true, account_id: 'phone-link', provider: 'phone' })],
    '/api/account/me': [unauthorized(), reply(200, {
      authenticated: true, account_id: 'phone-link', provider: 'phone', role: null, permissions: [],
    })],
  });
  const drive = async (p) => {
    p.fill('#lgPhone', '۰۹۱۲۳۴۵۶۷۸۹');
    p.fill('#lgCapAnswer', '4321');
    p.submit('#lgPhoneForm');
    await delay(8);
    p.fill('#lgOtpCode', '004271');
    p.submit('#lgPhoneCodeForm');
    await delay(10);
    return p.doc.querySelector('#lgContinue')?.getAttribute('href') || '';
  };

  const marker = await load({
    url: 'https://nora.test/login.html?mode=server&next=account.html%3Flink%3Dbale',
    routes: phoneRoutes(),
  });
  check(await drive(marker) === 'account.html?link=bale',
    'نشانهٔ مسیر پیوند از ورود با شماره جان سالم می‌برد و کاربر به همان مسیر برمی‌گردد');
  check(marker.storageOps.length === 0, 'در مسیر پیوند هم هیچ داده‌ای در localStorage نمی‌نشیند');
  marker.dom.window.close();

  /* هر پرس‌وجوی دیگری هنوز رد می‌شود؛ محافظت مسیر بازگشت شل نشده است. */
  const foreign = await load({
    url: 'https://nora.test/login.html?mode=server&next=account.html%3Fbad%3D1',
    routes: phoneRoutes(),
  });
  check(await drive(foreign) === 'account.html',
    'پرس‌وجوی ناشناس در نشانی بازگشت پذیرفته نمی‌شود و مسیر پیش‌فرض می‌ماند');
  foreign.dom.window.close();

  const otherHash = await load({
    url: 'https://nora.test/login.html?mode=server&next=account.html%23notifications',
    routes: phoneRoutes(),
  });
  check(await drive(otherHash) === 'account.html#notifications',
    'بازگشت به بخش‌های حساب همچنان کار می‌کند');
  otherHash.dom.window.close();

  /* مقصد «پرداخت‌ها» (نورا پی) هم باید بعد از ورود حفظ شود؛ مقصد ناشناخته همچنان به حساب برمی‌گردد. */
  const payments = await load({
    url: 'https://nora.test/login.html?mode=server&next=account.html%23payments',
    routes: phoneRoutes(),
  });
  check(await drive(payments) === 'account.html#payments',
    'ورود از مسیر نورا پی کاربر را به همان بخش پرداخت‌ها برمی‌گرداند');
  payments.dom.window.close();

  const unknownHash = await load({
    url: 'https://nora.test/login.html?mode=server&next=account.html%23wallet-topup',
    routes: phoneRoutes(),
  });
  check(await drive(unknownHash) === 'account.html',
    'بخش ناشناخته در نشانی بازگشت پذیرفته نمی‌شود و به صفحهٔ حساب می‌افتد');
  unknownHash.dom.window.close();
}

console.log('\n— خطاهای API بدون fallback محلی —');
{
  const p = await load({ routes: {
    '/api/auth/phone-otp/request': [reply(503, { detail: 'phone_otp_not_configured' })],
  } });
  p.fill('#lgPhone', '09123456789');
  p.fill('#lgCapAnswer', '4321');
  p.submit('#lgPhoneForm');
  await delay(6);
  check(p.text('#lgStatus').includes('سرویس ارسال کد روی سرور تنظیم نشده است'), 'خاموش بودن تنظیم Safir به‌عنوان موفقیت پنهان نمی‌شود');
  check(!!p.doc.querySelector('#lgPhoneForm') && !p.doc.querySelector('#lgAuthenticated'), 'خطای ارسال کد نشست یا ورود محلی نمی‌سازد');
  check(p.storageOps.length === 0, 'در شکست درخواست هم چیزی در localStorage نوشته نمی‌شود');
  p.dom.window.close();
}
{
  const p = await load({ routes: {
    '/api/auth/phone-otp/request': [reply(200, { accepted: true, challenge_id: '4fcb1516-b3c9-41ec-a840-01dc18598322', expires_in: 180, resend_in: 90 })],
    '/api/auth/phone-otp/verify': [reply(401, { detail: 'invalid_or_expired_otp' })],
  } });
  p.fill('#lgPhone', '09123456789');
  p.fill('#lgCapAnswer', '4321');
  p.submit('#lgPhoneForm');
  await delay(5);
  p.fill('#lgOtpCode', '12345');
  p.submit('#lgPhoneCodeForm');
  await delay(3);
  check(!p.calls.some((call) => call.url === '/api/auth/phone-otp/verify'), 'کد ناقص به سرور ارسال نمی‌شود');
  p.fill('#lgOtpCode', '123456');
  p.submit('#lgPhoneCodeForm');
  await delay(6);
  check(p.text('#lgStatus').includes('کد نادرست است یا مهلتش گذشته'), 'خطای کد سرور روشن نمایش داده می‌شود');
  check(!p.doc.querySelector('#lgAuthenticated') && p.storageOps.length === 0, 'کد ردشده نشست محلی نمی‌سازد');
  p.dom.window.close();
}
{
  const p = await load();
  p.fill('#lgPhone', '09123456789');
  p.fill('#lgCapAnswer', '4321');
  p.submit('#lgPhoneForm');
  await delay(6);
  check(p.text('#lgStatus').includes('ارتباط با سرویس ورود برقرار نشد'), 'قطع شبکه ادعای ارسال کد نمی‌کند');
  check(!p.doc.querySelector('#lgPhoneCodeForm, #lgAuthenticated') && p.storageOps.length === 0, 'در قطع شبکه گام کد یا نشست جعلی ساخته نمی‌شود');
  p.dom.window.close();
}

console.log('\n— فرم مشترک نام کاربری و گذرواژهٔ مدیر/مالک —');
{
  const p = await load({
    url: 'https://nora.test/login.html?mode=staff&next=admin.html%23money',
    routes: {
      '/api/auth/me': [unauthorized(), reply(200, { authenticated: true, owner_id: 'owner-id', role: 'owner', permissions: ['fm_create'] })],
      '/api/auth/staff-login': [reply(200, { authenticated: true, provider: 'owner', owner_id: 'owner-id', role: 'owner' })],
    },
  });
  check(!!p.doc.querySelector('#lgStaffForm') && !p.doc.querySelector('#lgPhoneForm'), 'یک فرم مشترک مدیریت برای مالک و مدیر باز می‌شود');
  check(p.text('#lgTitle') === 'ورود مدیران', 'عنوان فرم ورود فقط مدیران را نشان می‌دهد');
  check(p.doc.querySelector('#lgStaffUsername')?.getAttribute('autocomplete') === 'username'
      && p.doc.querySelector('#lgStaffPassword')?.getAttribute('autocomplete') === 'current-password', 'فرم مشترک autocomplete استاندارد دارد');
  p.fill('#lgStaffUsername', 'owner-name');
  p.fill('#lgStaffPassword', 'test-password-not-stored');
  p.submit('#lgStaffForm');
  await delay(10);
  const login = p.calls.find((call) => call.url === '/api/auth/staff-login');
  const confirmedSession = p.calls.filter((call) => call.url === '/api/auth/me').at(-1);
  check(login?.options.method === 'POST' && login.options.credentials === 'same-origin' && login.options.cache === 'no-store', 'اعتبارنامه‌ها به endpoint مشترک هم‌مبدأ می‌روند');
  check(JSON.stringify(JSON.parse(login?.options.body || '{}')) === JSON.stringify({ username: 'owner-name', password: 'test-password-not-stored' }), 'فرم فقط نام کاربری و گذرواژه می‌فرستد');
  check(confirmedSession?.options.method === 'GET', 'هویت مالک پس از ورود دوباره از سرور تأیید می‌شود');
  check(!!p.doc.querySelector('#lgAuthenticated') && p.text('#lgAuthenticated').includes('ورود مالک تأیید شد'), 'سرور نشست مشترک را به‌درستی به مالک نسبت می‌دهد');
  check(p.doc.querySelector('#lgContinue')?.getAttribute('href') === 'admin.html#money', 'مالک به مقصد مدیریت امن می‌رود');
  check(!p.doc.querySelector('#lgStaffPassword') && p.storageOps.length === 0, 'گذرواژه و نشست در localStorage نمی‌مانند');
  p.dom.window.close();
}
{
  const p = await load({
    url: 'https://nora.test/login.html?mode=owner&next=admin.html%23dash',
    routes: { '/api/auth/staff-login': [reply(401, { detail: 'invalid_credentials' })] },
  });
  check(!!p.doc.querySelector('#lgStaffForm') && p.text('#lgTitle') === 'ورود مدیران', 'پیوند مدیریت هم به فرم می‌رسد و عنوان فقط مدیران را نشان می‌دهد');
  p.fill('#lgStaffUsername', 'owner-name');
  p.fill('#lgStaffPassword', 'wrong-password');
  p.submit('#lgStaffForm');
  await delay(6);
  check(p.text('#lgStatus').includes('نام کاربری یا گذرواژه درست نیست'), 'اعتبارنامهٔ نادرست پیام عمومی دارد');
  check(!!p.doc.querySelector('#lgStaffForm') && !p.doc.querySelector('#lgStaffPassword')?.value, 'گذرواژه پس از خطا پاک می‌شود');
  check(!p.doc.querySelector('#lgAuthenticated') && p.storageOps.length === 0, 'خطای ورود نشست محلی نمی‌سازد');
  p.dom.window.close();
}

console.log('\n— تشخیص نقش مدیر توسط endpoint مشترک —');
{
  const p = await load({
    url: 'https://nora.test/login.html?mode=manager',
    routes: {
      '/api/auth/staff-login': [reply(200, {
        authenticated: true, account_id: 'manager-account-1', provider: 'manager-password',
      })],
      '/api/account/me': [unauthorized(), reply(200, {
        authenticated: true, account_id: 'manager-account-1', provider: 'manager-password',
        role: 'manager', permissions: ['fm_create'],
      })],
    },
  });
  check(!!p.doc.querySelector('#lgStaffForm') && !p.doc.querySelector('#lgPhoneForm'), 'پیوند مدیر هم همان فرم مشترک را باز می‌کند');
  check(p.text('#lgTitle') === 'ورود مدیران', 'عنوان فرم ورود فقط مدیران را نشان می‌دهد');
  p.fill('#lgStaffUsername', 'manager.one');
  p.fill('#lgStaffPassword', 'manager-password-test-2026');
  p.submit('#lgStaffForm');
  await delay(10);
  const login = p.calls.find((call) => call.url === '/api/auth/staff-login');
  const confirmedSession = p.calls.filter((call) => call.url === '/api/account/me').at(-1);
  check(login?.options.method === 'POST' && login.options.credentials === 'same-origin' && login.options.cache === 'no-store', 'نام کاربری و گذرواژه به endpoint مشترک می‌روند');
  check(JSON.stringify(JSON.parse(login?.options.body || '{}')) === JSON.stringify({
    username: 'manager.one', password: 'manager-password-test-2026',
  }), 'در درخواست نقش یا مجوز ارسالی وجود ندارد');
  check(confirmedSession?.options.method === 'GET', 'نشست و نقش مدیر دوباره از backend تأیید می‌شود');
  check(!!p.doc.querySelector('#lgAuthenticated') && p.text('#lgAuthenticated').includes('ورود مدیر تأیید شد'), 'سرور نشست مشترک را به‌درستی به مدیر دارای نقش نسبت می‌دهد');
  check(p.doc.querySelector('#lgContinue')?.getAttribute('href') === 'admin.html#dash', 'مدیر به پنل می‌رود');
  check(!p.doc.querySelector('#lgStaffPassword') && p.storageOps.length === 0, 'گذرواژه و نشست مدیر در localStorage نمی‌مانند');
  p.dom.window.close();
}
{
  const p = await load({
    url: 'https://nora.test/login.html?mode=staff&next=admin.html%23dash',
    routes: { '/api/auth/staff-login': [reply(401, { detail: 'invalid_credentials' })] },
  });
  p.fill('#lgStaffUsername', 'manager.one');
  p.fill('#lgStaffPassword', 'wrong-manager-password');
  p.submit('#lgStaffForm');
  await delay(7);
  check(p.text('#lgStatus').includes('نام کاربری یا گذرواژه درست نیست'), 'اعتبارنامهٔ نادرست مدیر پیام عمومی دارد');
  check(!!p.doc.querySelector('#lgStaffForm') && !p.doc.querySelector('#lgStaffPassword')?.value, 'گذرواژهٔ ردشده پاک می‌شود');
  check(!p.doc.querySelector('#lgAuthenticated') && p.storageOps.length === 0, 'خطای مدیر نشست یا نقش نمونه نمی‌سازد');
  p.dom.window.close();
}
{
  const p = await load({
    url: 'https://nora.test/login.html?mode=manager&next=admin.html%23dash',
    routes: { '/api/account/me': [reply(200, {
      authenticated: true, account_id: 'otp-manager', provider: 'phone',
      role: 'manager', permissions: ['fm_create'],
    })] },
  });
  check(!!p.doc.querySelector('#lgAuthenticated') && p.text('#lgAuthenticated').includes('برای ورود مدیریت، نام کاربری و گذرواژه لازم است'), 'نشست OTP با نقش مدیر باز هم باید از فرم مشترک گذرواژه استفاده کند');
  check(p.doc.querySelector('#lgContinue')?.getAttribute('href') === 'account.html', 'نشست OTP از فرم مشترک به پنل هدایت نمی‌شود');
  check(p.storageOps.length === 0, 'تشخیص نقش مدیر از OTP هیچ دادهٔ محلی نمی‌سازد');
  p.dom.window.close();
}

console.log('\n— تشخیص نشست سروری و خروج CSRFدار —');
{
  const p = await load({ routes: {
    '/api/auth/me': [reply(200, { authenticated: true, owner_id: 'owner-id', role: 'owner', permissions: [] })],
    '/api/auth/logout': [reply(200, { authenticated: false })],
  } });
  check(!!p.doc.querySelector('#lgAuthenticated') && p.text('#lgAuthenticated').includes('مالک'), 'نشست موجود مالک از سرور تشخیص داده می‌شود');
  check(!p.calls.some((call) => call.url === '/api/account/me'), 'پس از نشست مالک حساب عضو اشتباه بررسی نمی‌شود');
  check(!!p.doc.querySelector('#lgLogout'), 'خروج برای نشست مالک نمایش داده می‌شود');
  p.click('#lgLogout');
  await delay(2);
  check(!p.calls.some((call) => call.url === '/api/auth/logout'), 'بدون CSRF خروج مالک فرستاده نمی‌شود');
  p.window.document.cookie = 'nora_csrf=csrf-value; path=/';
  p.click('#lgLogout');
  await delay(6);
  const logout = p.calls.find((call) => call.url === '/api/auth/logout');
  check(logout?.options.method === 'POST' && logout.options.headers?.['X-CSRF-Token'] === 'csrf-value', 'خروج مالک CSRFدار است');
  check(!!p.doc.querySelector('#lgPhoneForm') && p.storageOps.length === 0, 'خروج، صفحه را به ورود واقعی شماره برمی‌گرداند');
  p.dom.window.close();
}
{
  const p = await load({
    cookie: 'nora_account_csrf=csrf-value; path=/',
    routes: {
      '/api/account/me': [reply(200, { authenticated: true, account_id: 'phone-id', provider: 'phone', role: null, permissions: [] })],
      '/api/auth/account/logout': [reply(200, { authenticated: false })],
    },
  });
  check(!!p.doc.querySelector('#lgAuthenticated') && p.text('#lgAuthenticated').includes('ورود با شمارهٔ همراه تأیید شد'), 'نشست OTP عضو از حساب server-side با provider=phone خوانده می‌شود');
  p.click('#lgLogout');
  await delay(6);
  const logout = p.calls.find((call) => call.url === '/api/auth/account/logout');
  check(logout?.options.method === 'POST' && logout.options.headers?.['X-CSRF-Token'] === 'csrf-value', 'خروج عضو با CSRF انجام می‌شود');
  check(!!p.doc.querySelector('#lgPhoneForm') && p.text('#lgStatus').includes('از حساب خارج شدی'), 'پس از خروج، فقط فرم OTP عضو نمایش داده می‌شود');
  p.dom.window.close();
}

console.log('\n— تفکیک هویت Bale از ورود شماره‌ای —');
{
  const p = await load({ routes: {
    '/api/account/me': [reply(200, { authenticated: true, account_id: 'bale-id', provider: 'bale', role: null, permissions: [] })],
  } });
  check(!!p.doc.querySelector('#lgAuthenticated') && p.text('#lgAuthenticated').includes('ورود با بله تأیید شد'), 'فقط نشست server-side با provider=bale با هویت بله معرفی می‌شود');
  p.dom.window.close();
}

console.log('\n— تصویر کپچا فقط PNG رستری است و پاسخ در DOM نیست —');
{
  const p = await load({});
  await delay(6);
  const pic = p.doc.querySelector('#lgCapImg img.lg-cap-pic');
  check(!!pic && pic.getAttribute('src') === CAPTCHA_PNG && pic.getAttribute('alt') === '',
    'کپچای سرور به‌صورت <img> با data URI نمایش داده می‌شود');
  check(!p.doc.querySelector('#lgCapImg svg, #lgCapImg text') && p.text('#lgCapImg').trim() === ''
      && !/[0-9]/.test(p.doc.querySelector('#lgCapImg').innerHTML.replace(/src="[^"]*"/, '').replace(/width="180" height="60"/, '')),
    'هیچ رقم یا متنی از پاسخ کپچا در DOM قابل خواندن نیست');
  check(!script.includes('captcha_answer:') || !/captcha_answer:\s*['"][0-9]{4}['"]/.test(script),
    'پاسخ کپچا در کد کلاینت ثابت نشده است');
  p.dom.window.close();

  const markup = await load({ routes: {
    '/api/auth/captcha': [reply(200, { token: 'captcha-token-test', image: '<svg xmlns="http://www.w3.org/2000/svg"><text>1234</text></svg>', expires_in: 180 })],
  } });
  await delay(6);
  check(!markup.doc.querySelector('#lgCapImg svg') && markup.text('#lgCapImg').includes('کد امنیتی بارگذاری نشد'),
    'پاسخ غیر PNG (markup) تزریق نمی‌شود و به‌عنوان خطای بارگذاری برخورد می‌شود');
  markup.dom.window.close();
}

console.log('\n— شکست بارگذاری کپچا بدون اسپینر ماندگار —');
{
  const p = await load({ routes: { '/api/auth/captcha': [reply(503, { detail: 'captcha_not_configured' })] } });
  await delay(6);
  const slot = p.doc.querySelector('#lgCapImg');
  check(!!slot && !slot.querySelector('.lg-spinner'), 'پس از شکست کپچا اسپینر باقی نمی‌ماند');
  check(!!slot && slot.textContent.includes('کد امنیتی بارگذاری نشد'), 'پس از شکست کپچا پیام ثابت و قابل فهم نمایش داده می‌شود');
  p.dom.window.close();
}

console.log('\n— نگه‌داشتن کد modal مستقل —');
check(dataScript.includes("codeLen:6") && !dataScript.includes("codeDemo:'54321'"), 'کد ۶ رقمی سرور در داده‌ی ورود؛ کد نمایشی ۵ رقمی حذف شده');
check(!script.includes('54321') && !script.includes('5432') && !script.includes('localStorage'), 'ورود صفحه نه کد نمونه دارد و نه از storage محلی استفاده می‌کند');

console.log(`\nآزمون ورود OTP پیامکی: ${passed} قبول، ${failed} خطا`);
if (failed) process.exitCode = 1;
