/* آزمون مسیر تولیدِ مدیریت نهادهای همکار در پنل مالک (API ساختگی با نسخه‌بندی واقعی‌نما).
   این آزمون mock است؛ تأیید روی سرور واقعی در Playwright/pytest جداگانه ثبت می‌شود. */
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const ADMIN_HTML = resolve(HERE, 'admin.html');
const delay = (ms = 10) => new Promise(r => setTimeout(r, ms));
const reply = (status, payload = {}) => ({ ok: status >= 200 && status < 300, status, json: async () => payload });
const OWNER_PERMS = ['ev_create', 'ev_publish', 'fm_create', 'us_view', 'sys_settings', 'role_assign', 'public_roster'];
const CONTENT_KEYS = ['events', 'people', 'articles', 'partners', 'banners', 'cooperation', 'library'];
let passed = 0, failed = 0;
const ok = (cond, name) => { if (cond) { passed++; console.log('PASS ' + name); } else { failed++; console.log('FAIL ' + name); } };

function makeServer() {
  const content = {
    events: [{ id: 'ev-1', t: 'رویداد آزمایشی', partnerId: 'srv-1', d: '۱۴۰۵/۰۸/۰۵', pub: true }],
    people: [{ id: 'np-1', n: 'مدرس آزمایشی' }], articles: [{ id: 'ar-1', t: 'مطلب' }],
    partners: [
      { id: 'srv-1', n: 'نهاد سروری یک', type: 'فرهنگی', s: 'خلاصهٔ یک', d: 'شرح یک', href: 'https://example.org/one', focus: ['آموزش'], links: [{ k: 'mail', v: 'one@example.org' }], mon: 'نی', g: 'linear-gradient(135deg,#2E6B7A,#0B2447)' },
      { id: 'srv-2', n: 'نهاد سروری دو', type: 'آموزشی', mon: 'ند' },
    ],
    banners: [{ id: 'bn-1', t: 'بنر', status: 'published' }], cooperation: [], library: [],
  };
  const server = { content, version: 7, calls: [], fail: null, nextVersionBump: false };
  server.fetch = async (url, options = {}) => {
    const path = String(url), method = String(options.method || 'GET').toUpperCase();
    server.calls.push({ path, method, options });
    if (server.fail === 'network') throw new TypeError('Failed to fetch');
    if (path === '/api/auth/me') return reply(200, { authenticated: true, owner_id: 'owner-01', role: 'owner', permissions: OWNER_PERMS });
    if (path === '/api/account/me') return reply(401, { detail: 'authentication_required' });
    if (path === '/api/health') return reply(200, { ok: true });
    if (path === '/api/integrations/status') return reply(200, { providers: [] });
    if (path === '/api/forms') return reply(200, { items: [] });
    if (path === '/api/owner/site-content' && method === 'GET') {
      if (server.fail === 'get-401') return reply(401, { detail: 'authentication_required' });
      return reply(200, { content: JSON.parse(JSON.stringify(content)), version: server.version, updated_at: null });
    }
    if (path === '/api/owner/site-content' && method === 'PATCH') {
      if (server.fail === 'patch-401') return reply(401, { detail: 'authentication_required' });
      if (server.fail === 'patch-500') return reply(500, { detail: 'boom' });
      const body = JSON.parse(options.body || '{}');
      if (!options.headers || options.headers['X-CSRF-Token'] !== 'owner-csrf') return reply(403, { detail: 'csrf_failed' });
      if (body.expected_version !== server.version) return reply(409, { detail: { code: 'site_content_version_conflict', current_version: server.version } });
      Object.keys(body.content).forEach(key => { content[key] = body.content[key]; });
      server.version += 1;
      return reply(200, { content: JSON.parse(JSON.stringify(content)), version: server.version, updated_at: null });
    }
    return reply(404, { detail: 'not_found' });
  };
  return server;
}

async function loadOwnerPanel(server, { hash = '#partners', role = 'owner' } = {}) {
  const values = new Map([['nora-admin', JSON.stringify({ v: 78, sec: 'dash' })]]);
  const store = {
    getItem(k) { return values.has(String(k)) ? values.get(String(k)) : null; },
    setItem(k, v) { values.set(String(k), String(v)); }, removeItem(k) { values.delete(String(k)); },
    clear() { values.clear(); }, key(i) { return [...values.keys()][i] || null; }, get length() { return values.size; },
  };
  const confirms = [];
  const dom = await JSDOM.fromFile(ADMIN_HTML, {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true, url: pathToFileURL(ADMIN_HTML).href + hash,
    beforeParse(window) {
      Object.defineProperty(window.navigator, 'userAgent', { configurable: true, value: 'ArenaBrowser/1.0' });
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.scrollTo = () => {};
      window.confirm = message => { confirms.push(message); return true; };
      Object.defineProperty(window.document, 'cookie', { configurable: true, get: () => 'nora_csrf=owner-csrf; nora_account_csrf=account-csrf' });
      window.fetch = async (url, options = {}) => {
        if (role !== 'owner') {
          const path = String(url);
          if (path === '/api/auth/me') return reply(401, { detail: 'authentication_required' });
          if (path === '/api/account/me') return reply(200, { authenticated: true, account_id: 'acc-01', provider: 'manager-password', role: 'manager', permissions: ['ev_create'] });
        }
        return server.fetch(url, options);
      };
    },
  });
  await new Promise(r => { if (dom.window.document.readyState === 'complete') return r(); const t = setTimeout(r, 8000); dom.window.addEventListener('load', () => { clearTimeout(t); r(); }, { once: true }); });
  const doc = dom.window.document;
  const until = async (pred, label, ms = 5000) => { const end = Date.now() + ms; while (Date.now() < end) { if (pred()) return true; await delay(15); } throw new Error('زمان انتظار تمام شد: ' + label); };
  const click = sel => { const el = doc.querySelector(sel); assert.ok(el, 'عنصر پیدا نشد: ' + sel); el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true })); return el; };
  const type = (sel, value) => { const el = doc.querySelector(sel); assert.ok(el, 'ورودی پیدا نشد: ' + sel); el.value = value; el.dispatchEvent(new dom.window.Event('input', { bubbles: true })); };
  const text = sel => (doc.querySelector(sel) || {}).textContent || '';
  const patches = () => server.calls.filter(c => c.path === '/api/owner/site-content' && c.method === 'PATCH');
  return { dom, window: dom.window, doc, until, click, type, text, patches, confirms, store: values };
}

console.log('— پنل مالک: فهرست نهادها از سرور —');
{
  const server = makeServer();
  const app = await loadOwnerPanel(server);
  try {
    await app.until(() => app.doc.querySelectorAll('[data-ppartner-row]').length === 2, 'فهرست سروری نهادها');
    ok(app.text('#ppPartnerSrvState').includes('۲ نهاد منتشرشده از سرور') && app.text('#ppPartnerSrvState').includes('نسخهٔ ۷'), 'وضعیت: فهرست از سرور با نسخهٔ واقعی بارگذاری شد');
    ok(!app.doc.querySelector('[data-ppartner-pub]') && !app.doc.querySelector('[data-ppartner-hide]') && !app.doc.querySelector('[data-ppartner-hidden]'), 'در تولید دکمهٔ انتشار محلی/پنهان‌سازی نمایش داده نمی‌شود');
    ok(!/گروه آموزشی نمونه|فضای فرهنگی نمونه/.test(app.text('#ppPartnerList')), 'دادهٔ نمونهٔ data.js جای فهرست سرور را نمی‌گیرد');
    ok(app.doc.querySelector('[data-ppartner-row="srv-1"] a[href="partner.html?id=srv-1"]'), 'پیوند صفحهٔ عمومی هر نهاد');

    // افزودن
    app.click('[data-ppartner-new]');
    app.type('[data-ppartner-field="n"]', 'نهاد تازهٔ آزمایشی');
    app.type('[data-ppartner-field="type"]', 'خدماتی');
    app.type('[data-ppartner-field="s"]', 'خلاصهٔ تازه');
    app.type('[data-ppartner-field="href"]', 'example.org/new');
    app.type('[data-ppartner-field="focus"]', 'آموزش، رسانه');
    app.click('[data-ppartner-link-add]');
    app.click('[data-ppartner-link-kind="0"][data-ppartner-kind="tg"]');
    app.type('[data-ppartner-link="0"]', '@nora_new');
    app.click('[data-ppartner-save]');
    await app.until(() => app.patches().length === 1 && app.doc.querySelectorAll('[data-ppartner-row]').length === 3, 'ذخیرهٔ نهاد تازه روی سرور');
    const first = JSON.parse(app.patches()[0].options.body);
    ok(Object.keys(first.content).join() === 'partners' && first.expected_version === 7, 'PATCH فقط دستهٔ partners را با expected_version فعلی می‌فرستد');
    ok(first.content.partners.length === 3 && first.content.partners[2].n === 'نهاد تازهٔ آزمایشی' && first.content.partners[2].href === 'https://example.org/new'
      && first.content.partners[2].links[0].href === 'https://t.me/nora_new' && first.content.partners[2].pub === true, 'ردیف تازه با فیلدهای پاک‌شده و pub=true ارسال شد');
    ok(server.content.events.length === 1 && server.content.banners.length === 1 && server.content.people.length === 1, 'رویدادها، بنرها و پروفایل‌ها دست‌نخورده ماندند');
    ok(app.text('#ppPartnerSrvState').includes('نسخهٔ ۸') && app.doc.querySelector('#ppPartnerSrvState').dataset.state === 'success' && !app.doc.querySelector('[data-ppartner-save]'), 'پیام موفقیت فقط پس از پاسخ سرور و بستن ویرایشگر');

    // ویرایش
    app.click('[data-ppartner-edit="srv-2"]');
    app.type('[data-ppartner-field="n"]', 'نهاد سروری دو (ویرایش‌شده)');
    app.click('[data-ppartner-save]');
    await app.until(() => app.patches().length === 2, 'ذخیرهٔ ویرایش');
    const second = JSON.parse(app.patches()[1].options.body);
    ok(second.expected_version === 8 && second.content.partners.find(p => p.id === 'srv-2').n === 'نهاد سروری دو (ویرایش‌شده)' && second.content.partners.length === 3, 'ویرایش با نسخهٔ تازه و حفظ سایر نهادها');
    await app.until(() => app.text('[data-ppartner-row="srv-2"]').includes('ویرایش‌شده'), 'فهرست از پاسخ سرور نو شد');

    // ترتیب
    app.click('[data-ppartner-up="1"]');
    await app.until(() => app.patches().length === 3, 'ذخیرهٔ ترتیب');
    ok(JSON.parse(app.patches()[2].options.body).content.partners[0].id === 'srv-2', 'جابه‌جایی ترتیب روی سرور ذخیره می‌شود');

    // تعارض نسخه: شخص دیگری هم‌زمان نهاد دیگری را تغییر می‌دهد
    await app.until(() => !server.calls.length || app.doc.querySelector('[data-ppartner-edit="srv-2"]') && app.doc.querySelector('#ppPartnerSrvState')?.dataset.state === 'success', 'پایان ذخیرهٔ ترتیب');
    server.content.partners[1].n = 'نهاد یک (تغییر شخص دیگر)'; server.version += 1;
    app.click('[data-ppartner-edit="srv-2"]');
    await app.until(() => app.doc.querySelector('[data-ppartner-field="type"]'), 'ویرایشگر برای سناریوی تعارض');
    app.type('[data-ppartner-field="type"]', 'تعارض');
    app.click('[data-ppartner-save]');
    await app.until(() => app.patches().length === 4 && app.doc.querySelector('#ppPartnerSrvState')?.dataset.state === 'error', 'پاسخ ۴۰۹');
    await app.until(() => server.calls.filter(c => c.path === '/api/owner/site-content' && c.method === 'GET').length >= 2 && /نهاد یک \(تغییر شخص دیگر\)/.test(app.text('#ppPartnerPreview') + app.text('#admBody')) || app.text('#ppPartnerSrvState').includes('هم‌زمان'), 'بازخوانی پس از تعارض');
    ok(app.text('#ppPartnerSrvState').includes('هم‌زمان') && app.text('#ppPartnerSrvState').includes('ذخیره نشد'), '۴۰۹: پیام تعارض، بدون موفقیت کاذب');
    ok(server.content.partners.find(p => p.id === 'srv-1').n === 'نهاد یک (تغییر شخص دیگر)' && server.version === 11, 'تغییر شخص دیگر بی‌صدا حذف نشد');
    ok(!!app.doc.querySelector('[data-ppartner-save]') && app.doc.querySelector('[data-ppartner-field="type"]').value === 'تعارض', 'پیش‌نویس مالک پس از تعارض باز می‌ماند');
    app.click('[data-ppartner-save]');
    await app.until(() => app.patches().length === 5 && app.doc.querySelector('#ppPartnerSrvState')?.dataset.state === 'success', 'ذخیرهٔ دوباره با نسخهٔ تازه');
    ok(JSON.parse(app.patches()[4].options.body).expected_version === 11 && server.content.partners.find(p => p.id === 'srv-1').n === 'نهاد یک (تغییر شخص دیگر)' && server.content.partners.find(p => p.id === 'srv-2').type === 'تعارض', 'ذخیرهٔ مجدد روی نسخهٔ تازه، هر دو تغییر حفظ شد');

    // حذف با تأیید
    const before = app.confirms.length;
    app.click('[data-ppartner-del="srv-1"]');
    await app.until(() => app.patches().length === 6, 'ذخیرهٔ حذف');
    ok(app.confirms.length === before + 1 && /حذف شود/.test(app.confirms[before]), 'حذف تأیید صریح می‌گیرد');
    ok(!server.content.partners.some(p => p.id === 'srv-1') && server.content.partners.length === 2 && server.content.events[0].partnerId === 'srv-1', 'نهاد از سرور حذف شد؛ رویداد مرتبط دست نخورد');
    await app.until(() => !app.doc.querySelector('[data-ppartner-row="srv-1"]'), 'فهرست پس از حذف');

    // خطاها: ۴۰۱، ۵۰۰، شبکه → بدون موفقیت کاذب
    for (const [mode, needle] of [['patch-401', 'نشست مالک'], ['patch-500', 'پاسخ‌گو نیست'], ['network', 'دسترسی نیست']]) {
      server.fail = mode;
      const n = app.patches().length;
      app.click('[data-ppartner-edit="srv-2"]');
      app.type('[data-ppartner-field="s"]', 'تلاش ' + mode);
      app.click('[data-ppartner-save]');
      await app.until(() => app.doc.querySelector('#ppPartnerSrvState')?.dataset.state === 'error' && app.text('#ppPartnerSrvState').includes(needle), 'خطای ' + mode, 6000);
      ok(server.content.partners.find(p => p.id === 'srv-2').s !== 'تلاش ' + mode && !!app.doc.querySelector('[data-ppartner-save]'), mode + ': چیزی ذخیره نشد و ویرایشگر باز ماند');
      server.fail = null; app.click('[data-ppartner-cancel]');
      void n;
    }
  } finally { app.dom.window.close(); }
}

console.log('— نقش مدیر بدون مجوز مالک —');
{
  const server = makeServer();
  const app = await loadOwnerPanel(server, { role: 'manager' });
  try {
    await app.until(() => app.doc.querySelector('#admNav [data-sec]') || app.doc.querySelector('a[href^="login.html?mode=staff"]'), 'ورود مدیر');
    await delay(300);
    ok(!app.doc.querySelector('[data-ppartner-row]') && !app.doc.querySelector('#ppPartnerSrvState'), 'مدیر با #partners به مدیریت نهادها نمی‌رسد');
    ok(app.patches().length === 0, 'هیچ PATCH از نشست مدیر ارسال نشد');
  } finally { app.dom.window.close(); }
}

console.log('— نشست نامعتبر هنگام بارگذاری فهرست —');
{
  const server = makeServer(); server.fail = 'get-401';
  const app = await loadOwnerPanel(server);
  try {
    await app.until(() => app.doc.querySelector('#ppPartnerSrvState')?.dataset.state === 'error', 'خطای بارگذاری');
    ok(app.text('#ppPartnerSrvState').includes('نشست مالک') && !app.doc.querySelector('[data-ppartner-row]') && app.doc.querySelector('[data-ppartner-reload]'), 'بدون نشست معتبر: فهرست خالی، پیام روشن، دکمهٔ تازه‌سازی');
    server.fail = null; app.click('[data-ppartner-reload]');
    await app.until(() => app.doc.querySelectorAll('[data-ppartner-row]').length === 2, 'تازه‌سازی پس از رفع خطا');
    ok(true, 'تازه‌سازی از سرور فهرست را بازمی‌گرداند');
  } finally { app.dom.window.close(); }
}

console.log(`admin-partners-server: ${passed} قبول، ${failed} خطا`);
if (failed) process.exit(1);
