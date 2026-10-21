/* آزمون مرحلهٔ سوم پنل: گواهینامه‌ها از ثبت مشترک سرور با نشست سروری ساختگی.
   fetch با مسیر دقیق شبیه‌سازی می‌شود؛ هیچ سروری اجرا نمی‌شود و هیچ گواهی‌ای ساخته نمی‌شود. */
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const ADMIN_HTML = resolve(HERE, 'admin.html');
const delay = (ms = 10) => new Promise((done) => setTimeout(done, ms));
const reply = (status, payload = {}) => ({ ok: status >= 200 && status < 300, status, json: async () => payload });
const MANAGER = ['ev_create', 'ev_publish', 'ev_cancel', 'attendance', 'certificate', 'fm_create', 'fm_responses', 'fm_export',
  'receipt_approve', 'us_view', 'us_edit', 'us_approve', 'us_block', 'us_notes', 'us_export', 'sp_answer', 'sp_reopen',
  'qa_audit', 'qa_complaint', 'qa_quality', 'qa_fix', 'qa_report', 'bc_send', 'bc_event', 'pr_media', 'pr_campaign',
  'pr_invite', 'dev_course', 'dev_process', 'dev_kpi', 'dev_review', 'rp_view', 'rp_export'];
const OWNER = [...MANAGER, 'cl_member', 'cl_session', 'cl_cert', 'cl_content', 'cl_dues', 'sys_points', 'finance',
  'role_assign', 'sys_fields', 'sys_settings', 'sys_backup', 'cert_final', 'user_delete', 'public_roster'];
const ACC = '0f0f0f0f-1111-4222-8333-444444444444';
const C1 = 'a165e049-0000-4000-8000-000000000001';
const C2 = 'a165e049-0000-4000-8000-000000000002';
const FILE_ID = 'f1f1f1f1-0000-4000-8000-00000000000f';

function makeCerts() {
  const holder = { account_id: ACC, bale_user_id: '910001', display_name: 'زهرا آزمایشی', name_source: 'profile' };
  return [
    { id: C1, external_key: 'src:1', source: 'bot_legacy', legacy_id: 1, kind: 'event', status: 'issued', effective_status: 'issued',
      serial: 'NC-0001', full_code: '1421/A7K2M9', doc_no: '1421', person_code: 'A7K2M9', event_ref: '17', event_title: 'کارگاه نجوم', title: 'گواهی حضور',
      issued_on: '1405/01/12', expires_on: '', issued_at: '2026-04-01T10:00:00+00:00', revoked_at: null, verify_count: 3, has_file: true, has_preview: false,
      synced_at: '2026-10-21T07:00:00+00:00', created_at: '2026-10-21T07:00:00+00:00', holder },
    { id: C2, external_key: 'src:2', source: 'bot', legacy_id: 2, kind: 'manual', status: 'revoked', effective_status: 'revoked',
      serial: 'NC-0002', full_code: '', doc_no: '', person_code: '', event_ref: '18', event_title: 'دورهٔ تلسکوپ', title: '',
      issued_on: '', expires_on: '', issued_at: '2026-04-02T10:00:00+00:00', revoked_at: '2026-05-01T08:00:00+00:00', verify_count: 0, has_file: false, has_preview: false,
      synced_at: '2026-10-21T07:00:00+00:00', created_at: '2026-10-21T07:01:00+00:00', holder },
  ];
}

async function loadPanel(identity) {
  const certs = identity.certs || makeCerts();
  const calls = [];
  const values = new Map([['nora-admin', JSON.stringify({ v: 78, sec: identity.sec || 'users', ...(identity.state || {}) })]]);
  const store = {
    getItem(k) { return values.has(String(k)) ? values.get(String(k)) : null; },
    setItem(k, v) { values.set(String(k), String(v)); },
    removeItem(k) { values.delete(String(k)); }, clear() { values.clear(); },
    key(i) { return [...values.keys()][i] || null; }, get length() { return values.size; },
  };
  const perms = identity.permissions || (identity.role === 'owner' ? OWNER : MANAGER);
  const has = (p) => perms.includes(p);
  const dom = await JSDOM.fromFile(ADMIN_HTML, {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(window) {
      Object.defineProperty(window.navigator, 'userAgent', { configurable: true, value: 'ArenaBrowser/1.0' });
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.scrollTo = () => {};
      window.confirm = () => true;
      window.prompt = () => '';
      Object.defineProperty(window.document, 'cookie', { configurable: true, get: () => 'nora_csrf=owner-csrf; nora_account_csrf=account-csrf' });
      window.fetch = async (url, options = {}) => {
        const path = String(url);
        const method = String(options.method || 'GET').toUpperCase();
        calls.push({ path, method, headers: options.headers || {} });
        if (identity.outage && path.startsWith('/api/admin/')) throw new TypeError('network down');
        if (identity.expired && path.startsWith('/api/admin/')) return reply(401, { detail: 'authentication_required' });
        if (path === '/api/auth/me') return identity.role === 'owner'
          ? reply(200, { authenticated: true, owner_id: 'owner-01', role: 'owner', permissions: OWNER })
          : reply(401, { detail: 'authentication_required' });
        if (path === '/api/account/me') return identity.role === 'owner' ? reply(401, { detail: 'authentication_required' })
          : reply(200, { authenticated: true, account_id: 'acc-mgr', provider: 'manager-password', role: identity.role, permissions: perms, manager_username: 'qa.manager' });
        if (path === '/api/health') return reply(200, { ok: true, formsEnabled: true, responsesEnabled: true });
        if (path === '/api/integrations/status') return reply(200, { providers: [] });
        if (path === '/api/forms') return reply(200, { items: [] });
        if (path === '/api/owner/site-content') return reply(200, { content: {}, version: 1, updated_at: null });
        if (/^\/api\/admin\/reports\/summary\?period=/.test(path)) return reply(200, { source: 'shared_server_database', period: '30d', forms: { total: 0, by_status: {} }, responses: { total: 0, by_status: {} }, accounts: { total: 0, by_role: {} }, reviews: { total: 0, by_kind: {} }, notifications: { total: 0, by_delivery_status: {} }, cooperation_requests: { total: 0, by_status: {} } });
        if (path.startsWith('/api/admin/inbox')) return reply(200, { items: [], has_more: false });
        if (path.startsWith('/api/owner/audit')) return reply(200, { items: [], limit: 30, offset: 0, has_more: false, actions: [] });
        if (path.startsWith('/api/admin/content/')) return reply(200, { items: [], total: 0, counts: {}, limit: 20, offset: 0, has_more: false, kind: 'events', version: 1, source: 'site_content', can_edit: true, can_publish: true });
        if (path.startsWith('/api/admin/users')) {
          if (!has('us_view')) return reply(403, { detail: 'permission_denied' });
          const row = { account_id: ACC, display_name: 'زهرا آزمایشی', city: '', province: '', role: null, status: 'active', created_at: '2026-10-01T08:00:00+00:00', profile_updated_at: null, registrations: 0, pending_reviews: 0, providers: ['bale'], bale_user_id: '910001', linked: false };
          if (path === `/api/admin/users/${ACC}`) return reply(200, { ...row, source: 'shared_server_database', registration_items: [], reviews: [], notifications: 0, last_session_at: null });
          return reply(200, { items: [row], total: 1, limit: 20, offset: 0, has_more: false, can_open_roles: identity.role === 'owner' });
        }
        if (path.startsWith('/api/admin/attendance/')) return reply(200, { items: [], total: 0, limit: 20, offset: 0, has_more: false });
        /* ── گواهینامه‌ها ── */
        const m = path.match(/^\/api\/admin\/certificates(?:\/([^/?]+))?(\/file)?(?:\?(.*))?$/);
        if (m) {
          if (!has('certificate')) return reply(403, { detail: 'permission_denied' });
          const [, id, file, query] = m;
          if (!id) {
            const params = new URLSearchParams(query || '');
            let items = certs.slice();
            if (params.get('status')) items = items.filter((c) => c.effective_status === params.get('status'));
            if (params.get('kind')) items = items.filter((c) => c.kind === params.get('kind'));
            if (params.get('event_ref')) items = items.filter((c) => c.event_ref === params.get('event_ref'));
            if (params.get('q')) items = items.filter((c) => [c.serial, c.full_code, c.holder.display_name, c.event_title, c.holder.bale_user_id].join(' ').includes(params.get('q')));
            return reply(200, { source: 'shared_server_database', items, total: items.length, limit: 20, offset: 0, has_more: false, q: params.get('q') || '', status: params.get('status') || '', kind: '', event_ref: '',
              counts: { issued: certs.filter((c) => c.status === 'issued').length, revoked: certs.filter((c) => c.status === 'revoked').length },
              events: [{ event_ref: '17', event_title: 'کارگاه نجوم', count: 1 }, { event_ref: '18', event_title: 'دورهٔ تلسکوپ', count: 1 }], can_revoke: false });
          }
          const rec = certs.find((c) => c.id === id);
          if (!rec) return reply(404, { detail: 'certificate_not_found' });
          if (file) return reply(200, {});
          return reply(200, { source: 'shared_server_database', can_revoke: false, certificate: { ...rec, issued_by_bale_user_id: '70001', source_id: 'src', files: rec.has_file ? [{ slot: 'pdf', file_id: FILE_ID }] : [] } });
        }
        return reply(404, { detail: 'not_found' });
      };
    },
  });
  await new Promise((done) => {
    if (dom.window.document.readyState === 'complete') return done();
    const timer = setTimeout(done, 8000);
    dom.window.addEventListener('load', () => { clearTimeout(timer); done(); }, { once: true });
  });
  const doc = dom.window.document;
  const until = async (pred, label) => {
    const end = Date.now() + 5000;
    while (Date.now() < end) { if (pred()) return; await delay(15); }
    throw new Error(`زمان انتظار تمام شد: ${label}`);
  };
  await until(() => !!dom.window.NORA_SERVER_API && doc.querySelector('#admBar .server-identity'), 'نشست پنل');
  const click = (sel) => {
    const el = doc.querySelector(sel);
    assert.ok(el, `عنصر پیدا نشد: ${sel}`);
    el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
    return el;
  };
  const type = (sel, value) => {
    const el = doc.querySelector(sel); assert.ok(el, `فیلد پیدا نشد: ${sel}`);
    el.value = value; el.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  };
  const body = () => doc.querySelector('#admBody').textContent;
  const noLeak = () => {
    const text = body();
    assert.doesNotMatch(text, /0912|09\d{9}|hash|token|password/i, 'شماره، هش یا توکن در خروجی پنل نیست');
    assert.doesNotMatch(text, /سارا محمدی|NL-1024|جلسهٔ شعر و موسیقی|NORA-۰۵۰۴/, 'دادهٔ نمونهٔ محلی با دادهٔ سرور قاطی نمی‌شود');
  };
  return { dom, window: dom.window, doc, calls, click, type, until, body, noLeak, certs, store: values, close: () => dom.window.close() };
}

const openCerts = async (app) => {
  app.click('#admNav [data-sec="users"]');
  await delay(30);
  if (app.doc.querySelector('[data-uback]') && !app.doc.querySelector('[data-users-panel]') && !app.doc.querySelector('[data-cert-panel]') && !app.doc.querySelector('[data-cert-detail]')) app.click('[data-uback]');
  await app.until(() => app.doc.querySelector('[data-open-cert]') || app.doc.querySelector('[data-cert-panel]') || app.doc.querySelector('[data-cert-detail]'), 'کارت گواهینامه‌ها');
  if (app.doc.querySelector('[data-open-cert]')) app.click('[data-open-cert]');
};

console.log('— مالک: فهرست گواهی‌ها از پایگاه مشترک، جست‌وجو، فیلتر وضعیت، جزئیات و فایل —');
{
  const app = await loadPanel({ role: 'owner', sec: 'users' });
  try {
    await openCerts(app);
    await app.until(() => app.doc.querySelector(`[data-cert-open="${C1}"]`), 'فهرست گواهی‌ها');
    const first = app.calls.find((c) => c.path.startsWith('/api/admin/certificates'));
    assert.equal(first.path, '/api/admin/certificates?limit=20&offset=0', 'پارامترهای فهرست دقیقاً همان قرارداد API است');
    assert.match(app.body(), /پایگاه مشترک سرور/);
    assert.match(app.body(), /۱ صادرشده · ۱ باطل/);
    assert.match(app.body(), /NC-0001/);
    assert.match(app.body(), /باطل‌شده/);
    assert.equal(app.doc.querySelector('[data-cert-revoke], [data-cert-delete], [data-cert-issue]'), null, 'هیچ دکمهٔ صدور/ابطال در پنل نیست');
    app.noLeak();

    app.click('[data-cert-status="revoked"]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/certificates?limit=20&offset=0&status=revoked'), 'فیلتر وضعیت سمت سرور');
    await app.until(() => !app.doc.querySelector(`[data-cert-open="${C1}"]`) && app.doc.querySelector(`[data-cert-open="${C2}"]`), 'فقط باطل‌شده‌ها');
    app.click('[data-cert-status=""]');
    await app.until(() => app.doc.querySelector(`[data-cert-open="${C1}"]`), 'بازگشت به همه');

    app.type('#certQuery', 'A7K2M9');
    app.click('[data-cert-search]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/certificates?limit=20&offset=0&q=A7K2M9'), 'جست‌وجوی سمت سرور');
    await app.until(() => !app.doc.querySelector(`[data-cert-open="${C2}"]`), 'نتیجهٔ جست‌وجو فقط گواهی اول');
    app.type('#certQuery', 'چیزی-که-نیست');
    app.click('[data-cert-search]');
    await app.until(() => /با این جست‌وجو یا فیلتر گواهی‌ای پیدا نشد/.test(app.body()), 'حالت خالی صادقانه');
    app.type('#certQuery', '');
    app.click('[data-cert-search]');
    await app.until(() => app.doc.querySelector(`[data-cert-open="${C1}"]`), 'پاک‌کردن جست‌وجو');

    app.click(`[data-cert-open="${C1}"]`);
    await app.until(() => app.doc.querySelector('[data-cert-detail]') && /کد استعلام/.test(app.body()), 'جزئیات گواهی');
    assert.ok(app.calls.some((c) => c.path === `/api/admin/certificates/${C1}`));
    assert.match(app.body(), /1421\/A7K2M9/);
    assert.match(app.body(), /پروفایل حساب سرور/);
    assert.match(app.body(), /انتقال کنترل‌شده از پایگاه قدیمی ربات/);
    const link = app.doc.querySelector('[data-cert-file="pdf"]');
    assert.ok(link, 'پیوند فایل PDF');
    assert.equal(link.getAttribute('href'), `/api/admin/certificates/${C1}/file?slot=pdf`);
    assert.ok(link.hasAttribute('download'));
    assert.equal(app.doc.querySelector('[data-cert-file="png"]'), null, 'پیش‌نمایشی که وجود ندارد نشان داده نمی‌شود');
    assert.equal(app.doc.querySelector('[data-cert-revoke]'), null);
    app.noLeak();

    /* پایداری پس از بارگذاری مجدد: همان گواهی باز می‌ماند */
    const saved = JSON.parse(app.store.get('nora-admin'));
    assert.equal(saved.certSel, C1);
    app.click('[data-cert-back]');
    await app.until(() => app.doc.querySelector('[data-cert-panel]'), 'بازگشت به فهرست');
    assert.equal(JSON.parse(app.store.get('nora-admin')).certSel, '');
  } finally { app.close(); }
}

console.log('— بازگشت پس از بارگذاری مجدد: جزئیات انتخاب‌شده از حالت ذخیره‌شده بازیابی می‌شود —');
{
  const app = await loadPanel({ role: 'owner', sec: 'users', state: { uV: 'cert', certSel: C2 } });
  try {
    await app.until(() => app.doc.querySelector('[data-cert-detail]') && /NC-0002/.test(app.body()), 'جزئیات پس از reload');
    assert.ok(app.calls.some((c) => c.path === `/api/admin/certificates/${C2}`));
    assert.match(app.body(), /باطل‌شده/);
    assert.match(app.body(), /فایلی برای این گواهی در پایگاه مشترک نیست/);
  } finally { app.close(); }
}

console.log('— مدیر: مجوز certificate دارد و همان فهرست را می‌بیند؛ بدون مجوز: کارت و فهرست نیست —');
{
  const app = await loadPanel({ role: 'manager', sec: 'users' });
  try {
    await openCerts(app);
    await app.until(() => app.doc.querySelector(`[data-cert-open="${C1}"]`), 'فهرست برای مدیر');
    assert.ok(app.calls.every((c) => !c.path.startsWith('/api/admin/certificates') || c.method === 'GET'), 'مدیر فقط می‌خواند');
    app.noLeak();
  } finally { app.close(); }
  const limited = await loadPanel({ role: 'manager', sec: 'users', permissions: MANAGER.filter((p) => p !== 'certificate') });
  try {
    limited.click('#admNav [data-sec="users"]');
    await delay(60);
    if (limited.doc.querySelector('[data-uback]') && !limited.doc.querySelector('[data-users-panel]')) limited.click('[data-uback]');
    await limited.until(() => limited.doc.querySelector('[data-users-panel]') || limited.doc.querySelector('[data-open-attendance]'), 'صفحهٔ کاربران');
    assert.equal(limited.doc.querySelector('[data-open-cert]'), null, 'کارت گواهینامه بدون مجوز نیست');
    assert.ok(limited.calls.every((c) => !c.path.startsWith('/api/admin/certificates')), 'بدون مجوز هیچ درخواست گواهی فرستاده نمی‌شود');
  } finally { limited.close(); }
}

console.log('— قطع سرور و نشست منقضی: پیام و تلاش دوباره، بدون دادهٔ نمونه —');
{
  const app = await loadPanel({ role: 'owner', sec: 'users', state: { uV: 'cert' }, outage: true });
  try {
    await app.until(() => /سرور در دسترس نیست/.test(app.body()), 'پیام قطع سرور');
    assert.ok(app.doc.querySelector('[data-cert-refresh]'), 'دکمهٔ تلاش دوباره');
    assert.equal(app.doc.querySelector('[data-cert-open]'), null);
    app.noLeak();
  } finally { app.close(); }
  const expired = await loadPanel({ role: 'owner', sec: 'users', state: { uV: 'cert' }, expired: true });
  try {
    await expired.until(() => /دوباره وارد شوید/.test(expired.body()), 'پیام نشست منقضی');
    assert.equal(expired.doc.querySelector('[data-cert-open]'), null);
  } finally { expired.close(); }
  const empty = await loadPanel({ role: 'owner', sec: 'users', state: { uV: 'cert' }, certs: [] });
  try {
    await empty.until(() => /فهرست خالی است/.test(empty.body()), 'فهرست خالی صادقانه');
    assert.equal(empty.doc.querySelector('[data-cert-open]'), null);
    empty.noLeak();
  } finally { empty.close(); }
}

console.log('آزمون مرحلهٔ سوم پنل: قبول');
