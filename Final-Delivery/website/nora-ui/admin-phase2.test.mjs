/* آزمون مرحلهٔ دوم پنل: محتوا (site_content)، فهرست کاربران و حضور و غیاب با نشست سروری ساختگی.
   fetch با مسیر دقیق شبیه‌سازی می‌شود؛ هیچ سروری اجرا نمی‌شود. */
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
const RID = '6f905904-fcc5-4003-a16e-000000000001';

function makeWorld() {
  const events = [
    { id: 'ev-a1', t: 'کارگاه نگارش', kind: 'کارگاه', on: '1405/08/12', place: 'تهران', d: 'شرح', status: 'published', updated_at: '2026-10-20T10:00:00+00:00', created_at: '2026-10-19T10:00:00+00:00', public_path: 'event.html?id=ev-a1' },
    { id: 'ev-b2', t: 'نشست پیش‌نویس', kind: 'نشست', on: '1405/09/01', d: '', status: 'draft', updated_at: '2026-10-20T11:00:00+00:00', created_at: '2026-10-20T11:00:00+00:00' },
  ];
  const people = [
    { response_id: RID, name: 'کاربر آزمایشی', mobile_hint: '…۷۷۷', status: 'accepted', payment_approved: true, ticket_eligible: true,
      checked_in: false, checked_in_at: null, checked_in_by: null, serial: 'NORA-TEST0001', companion: 0, ticket_type: 'free' },
  ];
  return { version: 7, events, people };
}

async function loadPanel(identity) {
  const world = identity.world || makeWorld();
  const calls = [];
  const dialogs = [];
  const values = new Map([['nora-admin', JSON.stringify({ v: 78, sec: identity.sec || 'events' })]]);
  const store = {
    getItem(k) { return values.has(String(k)) ? values.get(String(k)) : null; },
    setItem(k, v) { values.set(String(k), String(v)); },
    removeItem(k) { values.delete(String(k)); }, clear() { values.clear(); },
    key(i) { return [...values.keys()][i] || null; }, get length() { return values.size; },
  };
  const perms = identity.permissions || (identity.role === 'owner' ? OWNER : MANAGER);
  const has = (p) => perms.includes(p);
  const list = (kind) => ({
    items: kind === 'events' ? world.events : [], total: kind === 'events' ? world.events.length : 0,
    counts: { draft: 1, published: 1, paused: 0, archived: 0 }, limit: 20, offset: 0, has_more: false, kind,
    version: world.version, source: 'site_content', can_edit: has('ev_create'), can_publish: has('ev_publish'),
  });
  const dom = await JSDOM.fromFile(ADMIN_HTML, {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(window) {
      Object.defineProperty(window.navigator, 'userAgent', { configurable: true, value: 'ArenaBrowser/1.0' });
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.scrollTo = () => {};
      window.confirm = (m) => { dialogs.push(['confirm', String(m)]); return identity.confirm !== false; };
      window.prompt = (m) => { dialogs.push(['prompt', String(m)]); return identity.promptAnswer === undefined ? 'اصلاح آزمایشی' : identity.promptAnswer; };
      Object.defineProperty(window.document, 'cookie', { configurable: true, get: () => 'nora_csrf=owner-csrf; nora_account_csrf=account-csrf' });
      window.fetch = async (url, options = {}) => {
        const path = String(url);
        const method = String(options.method || 'GET').toUpperCase();
        const body = options.body ? JSON.parse(options.body) : null;
        calls.push({ path, method, body, headers: options.headers || {} });
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
        if (path === '/api/owner/site-content') return reply(200, { content: {}, version: world.version, updated_at: null });
        if (/^\/api\/admin\/reports\/summary\?period=/.test(path)) return reply(200, { source: 'shared_server_database', period: '30d', forms: { total: 0, by_status: {} }, responses: { total: 0, by_status: {} }, accounts: { total: 0, by_role: {} }, reviews: { total: 0, by_kind: {} }, notifications: { total: 0, by_delivery_status: {} }, cooperation_requests: { total: 0, by_status: {} } });
        if (path.startsWith('/api/admin/inbox')) return reply(200, { items: [], has_more: false });
        if (path.startsWith('/api/owner/audit')) return reply(200, { items: [], limit: 30, offset: 0, has_more: false, actions: [] });

        /* ── محتوا ── */
        const needWrite = () => (has('ev_create') ? null : reply(403, { detail: 'permission_denied' }));
        const needPublish = () => (has('ev_publish') ? null : reply(403, { detail: 'permission_denied' }));
        const m = path.match(/^\/api\/admin\/content\/(events|articles)(?:\/([A-Za-z0-9_-]+))?(\/status)?(?:\?(.*))?$/);
        if (m) {
          if (!has('ev_create') && !has('ev_publish')) return reply(403, { detail: 'permission_denied' });
          const [, kind, id, statusOp, query] = m;
          if (method === 'GET' && !id) {
            const params = new URLSearchParams(query || '');
            const out = list(kind);
            if (params.get('status')) out.items = out.items.filter((e) => e.status === params.get('status'));
            if (params.get('q')) out.items = out.items.filter((e) => e.t.includes(params.get('q')));
            out.total = out.items.length;
            return reply(200, out);
          }
          if (method === 'GET' && id) {
            const rec = world.events.find((e) => e.id === id);
            return rec ? reply(200, { kind, record: rec, version: world.version }) : reply(404, { detail: 'content_record_not_found' });
          }
          if (method === 'POST' && !id) {
            const denied = needWrite(); if (denied) return denied;
            if (body.expected_version !== world.version) return reply(409, { detail: { code: 'site_content_version_conflict', current_version: world.version } });
            if (!String(body.record.t || '').trim()) return reply(422, { detail: { code: 'title_required', field: 't' } });
            if (body.record.on && !/^\d{4}\/\d{2}\/\d{2}$/.test(body.record.on)) return reply(422, { detail: { code: 'invalid_jalali_date', field: 'on' } });
            if (body.status === 'published' && !String(body.record.d || '').trim()) return reply(422, { detail: { code: 'event_description_required', field: 'd' } });
            world.version += 1;
            const rec = { id: 'ev-new1', ...body.record, status: body.status || 'draft', updated_at: '2026-10-21T08:00:00+00:00', created_at: '2026-10-21T08:00:00+00:00' };
            world.events.unshift(rec);
            return reply(200, { kind, record: rec, version: world.version, saved: true });
          }
          if (method === 'PUT' && id) {
            const denied = needWrite(); if (denied) return denied;
            const rec = world.events.find((e) => e.id === id);
            if (!rec) return reply(404, { detail: 'content_record_not_found' });
            if (body.expected_version !== world.version) return reply(409, { detail: { code: 'site_content_version_conflict', current_version: world.version } });
            Object.assign(rec, body.record); world.version += 1;
            return reply(200, { kind, record: rec, version: world.version, saved: true });
          }
          if (method === 'POST' && statusOp) {
            const denied = needPublish(); if (denied) return denied;
            const rec = world.events.find((e) => e.id === id);
            if (!rec) return reply(404, { detail: 'content_record_not_found' });
            if (body.expected_version !== world.version) return reply(409, { detail: { code: 'site_content_version_conflict', current_version: world.version } });
            if (body.status === 'published' && !rec.d) return reply(422, { detail: { code: 'event_description_required', field: 'd' } });
            rec.status = body.status; world.version += 1;
            return reply(200, { kind, record: rec, version: world.version, saved: true });
          }
        }
        /* ── کاربران ── */
        const u = path.match(/^\/api\/admin\/users(?:\/([^?]+))?(?:\?(.*))?$/);
        if (u) {
          if (!has('us_view')) return reply(403, { detail: 'permission_denied' });
          const [, id, query] = u;
          const row = { account_id: ACC, display_name: 'سارا آزمایشی', city: 'تهران', province: 'تهران', role: null, status: 'active',
            created_at: '2026-10-01T08:00:00+00:00', profile_updated_at: null, registrations: 1, pending_reviews: 0, providers: ['phone'], bale_user_id: null, linked: false };
          if (!id) {
            const params = new URLSearchParams(query || '');
            const items = identity.emptyUsers || (params.get('q') && !ACC.startsWith(params.get('q')) && !row.display_name.includes(params.get('q'))) ? [] : [row];
            return reply(200, { items, total: items.length, limit: 20, offset: 0, has_more: false, can_open_roles: identity.role === 'owner' });
          }
          if (id !== ACC) return reply(404, { detail: 'user_not_found' });
          return reply(200, { ...row, source: 'shared_server_database', registration_items: [{ form_name: 'فرم ثبت‌نام', event_title: 'کارگاه نگارش', status: 'accepted', payment_status: 'paid_manual', created_at: '2026-10-02T08:00:00+00:00' }],
            reviews: [], notifications: 2, last_session_at: '2026-10-20T08:00:00+00:00', ...(identity.role === 'owner' ? { email: 'sara@example.test', manager_username: null } : {}) });
        }
        /* ── حضور ── */
        if (path.startsWith('/api/admin/attendance/')) {
          if (!has('attendance')) return reply(403, { detail: 'permission_denied' });
          if (path.startsWith('/api/admin/attendance/forms?')) return reply(200, { items: [{ form_id: 'frm1', title: 'کارگاه رایگان', status: 'published', event_id: 'ev-a1', people: 1, checked_in: world.people.filter((p) => p.checked_in).length }], total: 1, limit: 20, offset: 0, has_more: false });
          if (path.startsWith('/api/admin/attendance/forms/frm1/people')) {
            const params = new URLSearchParams(path.split('?')[1] || '');
            let items = world.people;
            if (params.get('state') === 'checked_in') items = items.filter((p) => p.checked_in);
            if (params.get('state') === 'pending') items = items.filter((p) => !p.checked_in);
            return reply(200, { form: { form_id: 'frm1', title: 'کارگاه رایگان', status: 'published' }, items, total: items.length, limit: 50, offset: 0, has_more: false, counts: { total: world.people.length, checked_in: world.people.filter((p) => p.checked_in).length }, can_mark: true });
          }
          if (path.startsWith('/api/admin/attendance/forms/')) return reply(404, { detail: 'form_not_found' });
          const a = path.match(/^\/api\/admin\/attendance\/responses\/([^/]+)\/(check-in|undo-check-in)$/);
          if (a && method === 'POST') {
            const person = world.people.find((p) => p.response_id === a[1]);
            if (!person) return reply(404, { detail: 'ticket_not_found' });
            if (a[2] === 'check-in') {
              if (person.checked_in) return reply(409, { detail: 'already_checked_in' });
              person.checked_in = true; person.checked_in_at = '2026-10-21T08:30:00+00:00'; person.checked_in_by = { kind: 'web', id: 'owner-01' };
              return reply(200, { person, saved: true });
            }
            if (!person.checked_in) return reply(409, { detail: 'not_checked_in' });
            if (String(body.reason || '').trim().length < 3) return reply(422, { detail: { code: 'reason_required', field: 'reason' } });
            person.checked_in = false; person.checked_in_at = null; person.checked_in_by = null;
            return reply(200, { person, saved: true });
          }
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
    assert.doesNotMatch(text, /سارا محمدی|NL-1024|جلسهٔ شعر و موسیقی/, 'دادهٔ نمونهٔ محلی با دادهٔ سرور قاطی نمی‌شود');
  };
  return { dom, window: dom.window, doc, calls, dialogs, click, type, until, body, noLeak, world, close: () => dom.window.close() };
}

const section = async (app, sec) => {
  app.click(`#admNav [data-sec="${sec}"]`);
  await delay(30);
};

console.log('— مالک: فهرست رویدادها از site_content، فیلتر، ساخت با خطای سرور، انتشار —');
{
  const app = await loadPanel({ role: 'owner', sec: 'events' });
  try {
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست رویدادها');
    const first = app.calls.find((c) => c.path.startsWith('/api/admin/content/events'));
    assert.equal(first.path, '/api/admin/content/events?limit=20&offset=0&sort=updated&order=desc', 'پارامترهای فهرست دقیقاً همان قرارداد API است');
    assert.match(app.body(), /site_content/);
    assert.match(app.body(), /نسخهٔ ۷/);
    assert.ok(app.doc.querySelector('[data-ct-row="ev-b2"]'));
    app.noLeak();

    app.click('[data-ct-status="published"]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/content/events?limit=20&offset=0&status=published&sort=updated&order=desc'), 'فیلتر وضعیت سمت سرور');
    await app.until(() => !app.doc.querySelector('[data-ct-row="ev-b2"]'), 'پیش‌نویس با فیلتر منتشرشده پنهان است');
    app.click('[data-ct-status=""]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-b2"]'), 'بازگشت به همه');

    app.click('[data-ct-new]');
    await app.until(() => app.doc.querySelector('#ctf_t'), 'ویرایشگر رویداد تازه');
    app.type('#ctf_on', '1405/13');
    app.click('[data-ct-save]');
    await app.until(() => app.doc.querySelector('[data-ct-err="t"]')?.textContent.includes('عنوان لازم است'), 'خطای ۴۲۲ سرور زیر فیلد عنوان');
    assert.equal(app.world.events.length, 2, 'با خطای اعتبارسنجی چیزی ساخته نشد');
    app.type('#ctf_t', 'رویداد تازهٔ آزمون');
    app.click('[data-ct-save]');
    await app.until(() => app.doc.querySelector('[data-ct-err="on"]')?.textContent.includes('تاریخ'), 'خطای تاریخ شمسی زیر فیلد تاریخ');
    app.type('#ctf_on', '1405/09/10');
    app.click('[data-ct-save]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-new1"]'), 'رکورد تازه در فهرست');
    assert.match(app.body(), /رکورد ساخته شد · نسخهٔ ۸ · وضعیت از سرور: پیش‌نویس/);
    const create = app.calls.find((c) => c.method === 'POST' && c.path === '/api/admin/content/events');
    assert.equal(create.body.expected_version, 7);
    assert.equal(create.headers['X-CSRF-Token'], 'owner-csrf', 'نوشتن با CSRF مالک');

    app.click('[data-ct-set="published"][data-ct-id="ev-new1"], [data-ct-row="ev-new1"] [data-ct-set="published"]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/content/events/ev-new1/status'), 'درخواست انتشار');
    assert.ok(app.dialogs.some(([k, m]) => k === 'confirm' && m.includes('منتشر می‌شود')), 'انتشار تأیید می‌خواهد');
    await app.until(() => /برای انتشار، شرح رویداد لازم است/.test(app.body()), 'پیام دقیق ۴۲۲ انتشار بدون شرح');
    assert.equal(app.world.events.find((e) => e.id === 'ev-new1').status, 'draft');

    app.click('[data-ct-row="ev-a1"] [data-ct-set="paused"]');
    await app.until(() => app.world.events[1].status === 'paused' || app.world.events.find((e) => e.id === 'ev-a1').status === 'paused', 'توقف انتشار روی سرور');
    await app.until(() => /وضعیت «کارگاه نگارش» از سرور: متوقف/.test(app.body()), 'وضعیت از پاسخ سرور نمایش داده می‌شود');
  } finally { app.close(); }
}

console.log('— مالک: تعارض نسخه و رکورد ناموجود —');
{
  const app = await loadPanel({ role: 'owner', sec: 'events' });
  try {
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست');
    app.world.version = 9; /* کسی دیگر محتوا را تغییر داده */
    app.click('[data-ct-row="ev-a1"] [data-ct-set="paused"]');
    await app.until(() => /از جای دیگری تغییر کرده بود/.test(app.body()), 'پیام تعارض نسخه');
    assert.equal(app.world.events[0].status, 'published', 'در تعارض چیزی تغییر نکرد');
    await app.until(() => /نسخهٔ ۹/.test(app.body()), 'فهرست با نسخهٔ جدید تازه شد');
  } finally { app.close(); }
}

console.log('— مدیر بدون ev_publish: فقط ویرایش، بدون دکمهٔ انتشار؛ بدون us_view: فهرست کاربران بسته —');
{
  const perms = MANAGER.filter((p) => p !== 'ev_publish' && p !== 'us_view' && p !== 'attendance');
  const app = await loadPanel({ role: 'manager', sec: 'events', permissions: perms });
  try {
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست برای مدیر');
    assert.equal(app.doc.querySelector('[data-ct-set]'), null, 'بدون ev_publish دکمهٔ تغییر وضعیت نیست');
    assert.ok(app.doc.querySelector('[data-ct-edit="ev-a1"]'), 'ویرایش با ev_create هست');
    await section(app, 'users');
    await delay(80);
    assert.equal(app.calls.filter((c) => c.path.startsWith('/api/admin/users')).length, 0, 'بدون us_view درخواستی به API کاربران نمی‌رود');
    assert.match(app.body(), /مجوز|دسترسی/);
    assert.equal(app.doc.querySelector('[data-user-open]'), null);
  } finally { app.close(); }
}

console.log('— مالک: کاربران (فهرست، جست‌وجو، پرونده، شناسهٔ دستکاری‌شده) —');
{
  const app = await loadPanel({ role: 'owner', sec: 'users' });
  try {
    await section(app, 'users');
    if (app.doc.querySelector('[data-uback]') && !app.doc.querySelector('[data-users-panel]')) app.click('[data-uback]');
    await app.until(() => app.doc.querySelector(`[data-user-open="${ACC}"]`), 'فهرست کاربران از سرور');
    assert.ok(app.calls.some((c) => c.path === '/api/admin/users?limit=20&offset=0'));
    app.noLeak();
    app.type('#usersQuery', 'ناموجود');
    app.click('[data-users-search]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/users?limit=20&offset=0&q=' + encodeURIComponent('ناموجود')), 'جست‌وجو سمت سرور');
    await app.until(() => /کاربری پیدا نشد/.test(app.body()), 'خالی بودن نتیجه صادقانه گفته می‌شود');
    app.type('#usersQuery', '0f0f');
    app.click('[data-users-search]');
    await app.until(() => app.doc.querySelector(`[data-user-open="${ACC}"]`), 'جست‌وجو با پیشوند شناسه');
    app.click(`[data-user-open="${ACC}"]`);
    await app.until(() => app.doc.querySelector('[data-user-detail]') && /کارگاه نگارش/.test(app.body()), 'پروندهٔ کاربر با ثبت‌نام‌ها');
    assert.ok(app.calls.some((c) => c.path === '/api/admin/users/' + ACC));
    assert.match(app.body(), /sara@example\.test/, 'مالک ایمیل را می‌بیند');
    assert.match(app.body(), /شماره، کد ملی و اعتبارنامه‌ها نمایش داده نمی‌شوند/);
    app.noLeak();
    /* شناسهٔ دستکاری‌شده: فقط پیام «پیدا نشد»، نه دادهٔ کس دیگر */
    app.click('[data-uback]');
    await app.until(() => app.doc.querySelector('[data-users-panel]'), 'بازگشت');
    const fake = app.doc.querySelector(`[data-user-open="${ACC}"]`); fake.setAttribute('data-user-open', '99999999-9999-4999-8999-999999999999');
    app.click('[data-user-open="99999999-9999-4999-8999-999999999999"]');
    await app.until(() => /پیدا نشد/.test(app.body()), 'پیام ۴۰۴ برای شناسهٔ ناموجود');
    assert.doesNotMatch(app.body(), /sara@example\.test|کارگاه نگارش/);
  } finally { app.close(); }
}

console.log('— مدیر: پروندهٔ کاربر بدون ایمیل —');
{
  const app = await loadPanel({ role: 'manager', sec: 'users' });
  try {
    await section(app, 'users');
    if (app.doc.querySelector('[data-uback]') && !app.doc.querySelector('[data-users-panel]')) app.click('[data-uback]');
    await app.until(() => app.doc.querySelector(`[data-user-open="${ACC}"]`), 'فهرست');
    app.click(`[data-user-open="${ACC}"]`);
    await app.until(() => /کارگاه نگارش/.test(app.body()), 'پرونده');
    assert.doesNotMatch(app.body(), /sara@example|ایمیل/, 'مدیر ایمیل نمی‌بیند');
    assert.equal(app.doc.querySelector('[data-server-role-module]'), null, 'پیوند حساب‌ها و نقش‌ها فقط برای مالک');
  } finally { app.close(); }
}

console.log('— مالک: حضور و غیاب (ثبت، تکرار، برگرداندن با دلیل، فیلتر) —');
{
  const app = await loadPanel({ role: 'owner', sec: 'users' });
  try {
    await section(app, 'users');
    if (app.doc.querySelector('[data-uback]') && !app.doc.querySelector('[data-users-panel]')) app.click('[data-uback]');
    await app.until(() => app.doc.querySelector('[data-open-attendance]'), 'کارت حضور');
    app.click('[data-open-attendance]');
    await app.until(() => app.doc.querySelector('[data-att-form="frm1"]'), 'فهرست فرم‌ها');
    assert.ok(app.calls.some((c) => c.path === '/api/admin/attendance/forms?limit=20&offset=0'));
    app.click('[data-att-form="frm1"]');
    await app.until(() => app.doc.querySelector(`[data-att-checkin="${RID}"]`), 'فهرست افراد');
    assert.ok(app.calls.some((c) => c.path === '/api/admin/attendance/forms/frm1/people?limit=50&offset=0'));
    assert.match(app.body(), /ثبت‌نشده/);
    app.noLeak();
    app.click(`[data-att-checkin="${RID}"]`);
    await app.until(() => app.calls.some((c) => c.method === 'POST' && c.path === `/api/admin/attendance/responses/${RID}/check-in`), 'درخواست ثبت حضور');
    assert.ok(app.dialogs.some(([k, m]) => k === 'confirm' && m.includes('زمان سرور')));
    await app.until(() => app.doc.querySelector(`[data-att-undo="${RID}"]`), 'پس از ثبت، دکمهٔ برگرداندن');
    assert.match(app.body(), /ثبت شد · زمان سرور/);
    assert.match(app.body(), /از پنل/);
    assert.equal(app.world.people[0].checked_in, true);

    /* تکرار از راه دیگر (دکمه دیگر نیست؛ مستقیم API) → ۴۰۹ و پیام */
    const dup = await app.window.NORA_SERVER_API.attendanceCheckIn(RID, '', 'nora_csrf').catch((e) => e);
    assert.equal(dup.status, 409); assert.equal(dup.code, 'already_checked_in');

    app.click('[data-att-state="checked_in"]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/attendance/forms/frm1/people?limit=50&offset=0&state=checked_in'), 'فیلتر حاضران سمت سرور');
    app.click('[data-att-state="pending"]');
    await app.until(() => /کسی پیدا نشد/.test(app.body()), 'فیلتر ثبت‌نشده خالی است');
    app.click('[data-att-state=""]');
    await app.until(() => app.doc.querySelector(`[data-att-undo="${RID}"]`), 'همه');
    app.click(`[data-att-undo="${RID}"]`);
    await app.until(() => app.calls.some((c) => c.method === 'POST' && c.path === `/api/admin/attendance/responses/${RID}/undo-check-in`), 'برگرداندن');
    const undo = app.calls.find((c) => c.path.endsWith('/undo-check-in'));
    assert.equal(undo.body.reason, 'اصلاح آزمایشی', 'دلیل از کاربر پرسیده و فرستاده می‌شود');
    await app.until(() => app.doc.querySelector(`[data-att-checkin="${RID}"]`), 'دوباره ثبت‌نشده');
    assert.match(app.body(), /برگردانده شد و با دلیل/);
  } finally { app.close(); }
}

console.log('— برگرداندن بدون دلیل انجام نمی‌شود —');
{
  const world = makeWorld(); world.people[0].checked_in = true; world.people[0].checked_in_at = '2026-10-21T08:00:00+00:00'; world.people[0].checked_in_by = { kind: 'bot', id: '1' };
  const app = await loadPanel({ role: 'manager', sec: 'users', world, promptAnswer: 'x' });
  try {
    await section(app, 'users');
    if (app.doc.querySelector('[data-uback]') && !app.doc.querySelector('[data-users-panel]')) app.click('[data-uback]');
    await app.until(() => app.doc.querySelector('[data-open-attendance]'), 'کارت حضور');
    app.click('[data-open-attendance]');
    await app.until(() => app.doc.querySelector('[data-att-form="frm1"]'), 'فرم‌ها');
    app.click('[data-att-form="frm1"]');
    await app.until(() => app.doc.querySelector(`[data-att-undo="${RID}"]`), 'حاضر از ربات');
    assert.match(app.body(), /ربات/);
    app.click(`[data-att-undo="${RID}"]`);
    await delay(80);
    assert.equal(app.calls.filter((c) => c.path.endsWith('/undo-check-in')).length, 0, 'دلیل کوتاه: درخواستی فرستاده نمی‌شود');
    assert.equal(app.world.people[0].checked_in, true);
  } finally { app.close(); }
}

console.log('— قطع سرور و نشست منقضی: پیام و تلاش دوباره، بدون دادهٔ نمونه —');
{
  const app = await loadPanel({ role: 'owner', sec: 'events', outage: true });
  try {
    await app.until(() => /سرور در دسترس نیست/.test(app.body()), 'پیام قطع سرور');
    assert.ok(app.doc.querySelector('[data-ct-refresh]'), 'دکمهٔ تلاش دوباره');
    app.noLeak();
    assert.equal(app.doc.querySelector('[data-ct-row]'), null);
  } finally { app.close(); }
  const expired = await loadPanel({ role: 'owner', sec: 'users', expired: true });
  try {
    await section(expired, 'users');
    if (expired.doc.querySelector('[data-uback]') && !expired.doc.querySelector('[data-users-panel]')) expired.click('[data-uback]');
    await expired.until(() => /دوباره وارد شوید/.test(expired.body()), 'پیام نشست منقضی');
    assert.equal(expired.doc.querySelector('[data-user-open]'), null);
  } finally { expired.close(); }
  const empty = await loadPanel({ role: 'owner', sec: 'users', emptyUsers: true });
  try {
    await section(empty, 'users');
    if (empty.doc.querySelector('[data-uback]') && !empty.doc.querySelector('[data-users-panel]')) empty.click('[data-uback]');
    await empty.until(() => /هنوز کاربری/.test(empty.body()), 'فهرست خالی صادقانه');
    empty.noLeak();
  } finally { empty.close(); }
}

console.log('آزمون مرحلهٔ دوم پنل: قبول');
