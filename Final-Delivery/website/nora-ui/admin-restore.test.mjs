/* بازیابی پنل (مرحلهٔ A): زیرماژول‌های طراحی در حالت سروری واقعی، فقط با دادهٔ API و مجوز نشست.
   هیچ دادهٔ data.js در این مسیر نباید دیده شود؛ ماژول بدون API با دلیل صریح می‌ماند. */
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const ADMIN_HTML = resolve(HERE, 'admin.html');
const delay = (ms = 10) => new Promise((r) => setTimeout(r, ms));
const reply = (status, payload = {}) => ({ ok: status >= 200 && status < 300, status, json: async () => payload });

const MANAGER_PERMS = ['ev_create', 'ev_publish', 'attendance', 'certificate', 'fm_create', 'fm_responses', 'fm_export', 'receipt_approve',
  'us_view', 'us_approve', 'rp_view', 'sp_answer', 'qa_audit', 'pr_media'];
const OWNER_PERMS = [...MANAGER_PERMS, 'cl_member', 'finance', 'role_assign', 'sys_settings', 'sys_backup'];

const FORMS = [
  { id: 'f-pub-1', name: 'ثبت‌نام کارگاه آزمایشی', model: 'registration', need: 'reg', purpose: 'registration', ev: 'ev-1', status: 'published', version: 3, response_count: 7, updated_at: '2026-10-20T08:00:00+00:00' },
  { id: 'f-draft-1', name: 'نظرسنجی پیش‌نویس', model: 'survey', need: 'survey', purpose: 'survey', ev: '', status: 'draft', version: 1, response_count: 0, updated_at: '2026-10-21T08:00:00+00:00' },
  { id: 'f-buy-1', name: 'خرید محتوای ضبط‌شده', model: 'purchase', need: 'buy', purpose: 'purchase', ev: 'ev-1', recording_id: 'r-1', status: 'paused', version: 2, response_count: 2, updated_at: '2026-10-19T08:00:00+00:00' },
];
const EVENTS = [
  { id: 'ev-1', t: 'کارگاه آیندهٔ آزمایشی', status: 'published', created_at: '2026-10-01T08:00:00+00:00', updated_at: '2026-10-01T08:00:00+00:00', tags: [], kind: 'کارگاه', on: '1405/08/10', when: '1405/08/10', time: '۱۰ تا ۱۲', place: 'سالن', mode: 'حضوری', price: 0, cap: 0, past: false, lifecycle: 'scheduled', startsAt: '2026-11-01T06:30:00Z', regMode: 'auto', forms: [], registration: { form_id: 'fm-1', form_name: 'ثبت‌نام کارگاه', accepted: 18, waitlisted: 2, cap: 20, wait: 5, full: false, source: 'form_responses' } },
  { id: 'ev-old', t: 'کارگاه گذشته', status: 'published', created_at: '2026-09-01T08:00:00+00:00', updated_at: '2026-09-01T08:00:00+00:00', tags: [], kind: 'کارگاه', on: '1405/06/01', when: '1405/06/01', time: '', place: '', mode: 'حضوری', price: 0, cap: 0, past: true, lifecycle: 'ended', startsAt: '2026-08-23T06:30:00Z', regMode: 'auto', forms: [] },
];

async function loadPanel(identity) {
  const calls = []; const confirms = []; const decisions = [];
  const values = new Map([['nora-admin', JSON.stringify(identity.state || { v: 78, sec: 'dash' })]]);
  const store = {
    getItem(k) { return values.has(String(k)) ? values.get(String(k)) : null; },
    setItem(k, v) { values.set(String(k), String(v)); },
    removeItem(k) { values.delete(String(k)); }, clear() { values.clear(); },
    key(i) { return [...values.keys()][i] || null; }, get length() { return values.size; },
  };
  const session = identity.role === 'owner'
    ? { authenticated: true, owner_id: 'owner-01', role: 'owner', permissions: OWNER_PERMS }
    : { authenticated: true, account_id: 'acc-01', provider: 'manager-password', role: 'manager', permissions: identity.permissions || MANAGER_PERMS, manager_username: 'qa.manager' };
  const dom = await JSDOM.fromFile(ADMIN_HTML, {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(window) {
      Object.defineProperty(window.navigator, 'userAgent', { configurable: true, value: 'ArenaBrowser/1.0' });
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.scrollTo = () => {};
      window.confirm = (message) => { confirms.push(String(message)); return identity.confirm !== false; };
      Object.defineProperty(window.document, 'cookie', { configurable: true, get: () => 'nora_csrf=owner-csrf; nora_account_csrf=account-csrf' });
      window.fetch = async (url, options = {}) => {
        const path = String(url); const method = String(options.method || 'GET').toUpperCase();
        calls.push({ path, method });
        if (path === '/api/auth/me') return identity.role === 'owner' ? reply(200, session) : reply(401, { detail: 'authentication_required' });
        if (path === '/api/account/me') return identity.role === 'owner' ? reply(401, { detail: 'authentication_required' }) : reply(200, session);
        if (path === '/api/health') return reply(200, { ok: true, formsEnabled: true, responsesEnabled: true });
        if (path === '/api/integrations/status') return reply(200, { providers: [] });
        if (path === '/api/forms') return reply(200, { items: FORMS, total: FORMS.length, limit: 100, has_more: false });
        if (path.startsWith('/api/admin/reports/summary')) return reply(200, {
          source: 'shared_server_database', period: '30d', generated_at: '2026-10-01T08:00:00+00:00',
          forms: { total: 3, created_in_period: 1, by_status: { published: 1, draft: 1, paused: 1 } },
          responses: { total: 9, by_status: { accepted: 9 } }, accounts: { total: 4, by_role: { manager: 1 } },
          reviews: { total: 2, by_kind: { profile_review: { pending: 1 }, receipt_review: { pending: 1 } } },
          notifications: { total: 5, by_delivery_status: { delivered: 4, pending: 1 } }, cooperation_requests: { total: 0, by_status: {} },
        });
        if (path === '/api/admin/inbox?limit=20&offset=0') return reply(200, { items: [{ id: '00000000-0000-4000-8000-000000000001', kind: 'profile_review', status: 'pending', version: 1, payload: {}, files: [] }, { id: '00000000-0000-4000-8000-000000000002', kind: 'receipt_review', status: 'pending', version: 1, payload: { amount: 1000 }, files: [] }], has_more: false, status: 'pending' });
        if (path === '/api/admin/inbox?limit=50&offset=0') return reply(200, { items: [
          { id: '00000000-0000-4000-8000-000000000001', account_id: 'acc-02', bale_user_id: '1', kind: 'profile_review', status: 'pending', version: 1, payload: { full_name: 'آزمایش زنده' }, files: [] },
          { id: '00000000-0000-4000-8000-000000000002', account_id: 'acc-03', bale_user_id: '2', kind: 'receipt_review', status: 'pending', version: 3, payload: { amount: 1500000, currency: 'IRR', purchase_source: 'recording_access', note: 'واریز شد' }, files: [] },
        ], has_more: false, status: 'pending' });
        const decisionMatch = path.match(/^\/api\/admin\/inbox\/([^/]+)\/decision$/);
        if (decisionMatch && method === 'POST') {
          const sent = JSON.parse(options.body || '{}'); decisions.push({ id: decisionMatch[1], ...sent });
          return reply(200, { accepted: true, task: { id: decisionMatch[1], status: sent.decision, review_reason: sent.reason, notification: { status: 'queued', attempts: 0, delivered_at: null, last_error: null } } });
        }
        if (path.startsWith('/api/admin/content/events')) {
          const q = new URLSearchParams(path.split('?')[1] || '');
          const items = q.get('status') === 'published' ? EVENTS : EVENTS;
          return reply(200, { items, total: items.length, counts: { published: 2 }, limit: 20, offset: 0, has_more: false, kind: 'events', version: 4, source: 'site_content', can_edit: true, can_publish: true, q: '', status: q.get('status') || '', sort: 'date', order: 'asc' });
        }
        if (path === '/api/admin/scheduled-publish') return reply(200, { now: '2026-10-22T09:30:00+00:00', last_run: { at: '2026-10-22T09:25:00+00:00', ok: true, actor: 'cli', due: 1, announced: 1, notified: 3, skipped: 0, errors: 0 }, pending: { future: 2, due_unannounced: 1 }, runner: { interval_hint: 'systemd timer (5 min)', manual: 'POST /api/admin/scheduled-publish/run' } });
        if (path.startsWith('/api/owner/audit')) {
          if (identity.role !== 'owner') return reply(401, { detail: 'authentication_required' });
          return reply(200, { items: [{ id: 'a1', created_at: '2026-10-03T09:00:00+00:00', actor_kind: 'owner', actor_id: 'owner-01', actor_role: 'owner', action: 'role.set', target_type: 'account', target_id: 'acc-01', outcome: 'ok', details: {} }], limit: 7, offset: 0, has_more: false, actions: [] });
        }
        if (path.startsWith('/api/admin/notifications')) return reply(200, { source: 'shared_server_database', items: [{ id: '10000000-0000-4000-8000-000000000001', kind: 'certificate', title: 'گواهی صادر شد', body: '', created_at: '2026-10-22T06:00:00+00:00', delivery_status: 'failed', delivery_state: 'failed', attempts: 3, last_delivery_error: 'timeout', account_ref: 'acc-02' }], has_more: false, counts: { queued: 4, retrying: 0, delivered: 1, failed: 1, no_bale_identity: 0 }, limit: 30, offset: 0 });
        if (path === '/api/admin/event-interaction/summary') return reply(200, { source: 'shared_server_database', unanswered_questions: 3, pending_reviews: 0, open_reports: 1, failed_notifications: 1, per_event: [] });
        if (path === '/api/admin/recordings/summary') return reply(200, { source: 'shared_server_database', recordings: 1, orders_review: 2, orders_open: 0, orders_paid: 1, orders_refunded: 0, active_access: 1, per_event: [] });
        if (path.startsWith('/api/admin/attendance/forms')) { return reply(200, { source: 'shared_server_database', items: [], total: 0, limit: 20, offset: 0, has_more: false, q: new URLSearchParams(path.split('?')[1] || '').get('q') || '' }); }
        if (path.startsWith('/api/admin/users?')) return reply(200, { source: 'shared_server_database', items: [], total: 0, limit: 20, offset: 0, has_more: false });
        if (path.startsWith('/api/admin/events/ev-1/')) return reply(200, { items: [], total: 0, limit: 20, offset: 0, has_more: false });
        if (path === '/api/admin/storage/health') return reply(200, { ok: true });
        return reply(404, { detail: 'not_found' });
      };
    },
  });
  await new Promise((done) => {
    if (dom.window.document.readyState === 'complete') return done();
    const timer = setTimeout(done, 8000);
    dom.window.addEventListener('load', () => { clearTimeout(timer); done(); }, { once: true });
  });
  const until = async (predicate, label) => {
    const end = Date.now() + 6000;
    while (Date.now() < end) { if (predicate()) return; await delay(15); }
    throw new Error(`زمان انتظار تمام شد: ${label}`);
  };
  await until(() => !!dom.window.NORA_SERVER_API && dom.window.document.querySelector('#admBar .server-identity'), 'نشست پنل');
  const doc = dom.window.document;
  const click = (selector) => { const el = doc.querySelector(selector); assert.ok(el, `عنصر پیدا نشد: ${selector}`); el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true })); return el; };
  const text = (selector) => (doc.querySelector(selector)?.textContent || '').replace(/\s+/g, ' ');
  const stored = () => JSON.parse(values.get('nora-admin') || '{}');
  return { dom, window: dom.window, doc, calls, confirms, decisions, click, until, text, stored };
}

let checks = 0; const ok = (cond, label) => { checks += 1; assert.ok(cond, label); };

console.log('— مالک: داشبورد سروری؛ کارهای در انتظار، رویدادهای پیش رو، زمان‌بندی، تاریخچه —');
{
  const app = await loadPanel({ role: 'owner' });
  try {
    await app.until(() => app.doc.querySelector('[data-dashx-queue]') && app.doc.querySelector('[data-dashx-upcoming]') && !app.doc.querySelector('[data-dashx-queue]').textContent.includes('در حال خواندن'), 'داشبورد');
    await app.until(() => app.doc.querySelector('[data-dashx-sched-card]'), 'کارت زمان‌بندی');
    ok(app.doc.querySelector('[data-dashx-bar]'), 'نوار تاریخ جلالی و بازخوانی هست');
    ok(!/همگام با اینترنت|ساعت اینترنتی/.test(app.text('[data-dashx-bar]')), 'ادعای همگام‌سازی اینترنتی نمی‌شود');
    const queue = app.text('[data-dashx-queue]');
    ok(/درخواست‌های کارتابل[^۰-۹0-9]*۲/.test(queue), 'شمار کارتابل از /api/admin/inbox (۲) می‌آید');
    ok(/پرسش‌های بی‌پاسخ[^۰-۹0-9]*۳/.test(queue), 'پرسش‌های بی‌پاسخ از خلاصهٔ تعامل (۳)');
    ok(/سفارش‌های ضبط‌شده در بررسی[^۰-۹0-9]*۲/.test(queue), 'سفارش‌های در بررسی از خلاصهٔ ضبط‌شده (۲)');
    ok(/اعلان‌های ناموفق[^۰-۹0-9]*۱/.test(queue), 'اعلان ناموفق از شمارش صندوق خروجی (۱)');
    ok(/انتشار زمان‌بندی‌شدهٔ معوق[^۰-۹0-9]*۱/.test(queue), 'انتشار معوق از scheduled-publish (۱)');
    ok(app.calls.some(c => c.path === '/api/admin/inbox?limit=20&offset=0'), 'کارتابل با همان API خوانده شد');
    ok(app.calls.some(c => /^\/api\/admin\/content\/events\?.*status=published/.test(c.path)), 'رویدادهای پیش رو از API محتوا');
    const up = app.text('[data-dashx-upcoming]');
    ok(up.includes('کارگاه آیندهٔ آزمایشی') && !up.includes('کارگاه گذشته'), 'فقط رویداد منتشرشدهٔ آینده فهرست می‌شود');
    /* A6: ظرفیت/ثبت‌نام از پاسخ سرور (registration از form_responses)، نه عدد ساختگی؛ ۱۸ از ۲۰ = نزدیک به تکمیل */
    const regLine = app.text('[data-dashx-reg="ev-1"]');
    ok(/ظرفیت ۲۰/.test(regLine) && /ثبت‌نام قطعی ۱۸/.test(regLine) && /در انتظار ۲/.test(regLine), 'کارت رویداد پیش رو ظرفیت/ثبت‌نام قطعی/در انتظار را از سرور نشان می‌دهد');
    ok(up.includes('نزدیک به تکمیل'), 'برچسب «نزدیک به تکمیل» با ۸۰٪ ظرفیت');
    ok(/۲/.test(app.text('[data-dashx-sched-card]')) && app.text('[data-dashx-sched-card]').includes('systemd timer'), 'کارت زمان‌بندی خروجی API را نشان می‌دهد');
    ok(app.text('[data-dashx-audit]').includes('role.set'), 'تاریخچهٔ عملیات مالک از /api/owner/audit');
    ok(!/سارا محمدی|NL-1024|جلسهٔ شعر و موسیقی/.test(app.text('#admBody')), 'هیچ دادهٔ نمونهٔ data.js روی داشبورد نیست');
    app.click('[data-dashx-map]'); await delay(30);
    ok(app.doc.querySelector('[data-panel-map]'), 'نقشهٔ امکانات باز می‌شود');
    const mapText = app.text('[data-panel-map]');
    ok(mapText.includes('نیازمند سرویس') && mapText.includes('متصل به سرور'), 'نقشه وضعیت متصل و نیازمند سرویس را جدا می‌گوید');
    ok(!app.doc.querySelector('[data-panel-map] [data-dashx-leave-map][data-sec]') || true, 'ردیف‌های مسدود دکمهٔ پرش ندارند (بررسی بعدی)');
    const blockedRows = [...app.doc.querySelectorAll('[data-panel-map] .admlirow')].filter(r => r.textContent.includes('نیازمند سرویس'));
    ok(blockedRows.length >= 5 && blockedRows.every(r => !r.querySelector('button')), 'هیچ ردیف مسدودی دکمهٔ پرش ندارد');
    app.click('[data-panel-map] [data-dashx-leave-map]'); await delay(30);
    ok(app.doc.querySelector('[data-dashx-bar]'), 'بازگشت به داشبورد');
    app.click('.utile[data-sec="forms"]'); await app.until(() => app.doc.querySelectorAll('[data-fs-row]').length === 3, 'فهرست فرم‌های سرور');
    ok(app.stored().sec === 'forms', 'بخش فرم‌ها داخل همان پنل است');
    ok(app.doc.querySelector('a[href="create.html?fid=f-pub-1"]') && app.doc.querySelector('a[href="builder.html?fid=f-pub-1#responses"]'), 'ویرایش و پاسخ‌ها به فرم‌ساز موجود می‌روند؛ ویرایشگر دوم نیست');
    ok(app.doc.querySelector('[data-fs-row="f-pub-1"] a[href^="form.html?fid=f-pub-1"]') && !app.doc.querySelector('[data-fs-row="f-draft-1"] a[href^="form.html"]'), 'پیوند عمومی فقط برای فرم منتشرشده');
    ok(app.doc.querySelector('[data-fs-export="f-pub-1"]')?.getAttribute('href') === '/api/forms/f-pub-1/responses?format=csv', 'خروجی CSV به endpoint واقعی سرور اشاره می‌کند، نه فایل ساختگی');
    ok(![...app.doc.querySelectorAll('[data-forms-panel] a[download]')].length, 'هیچ دانلود ساختگی سمت مرورگر نیست');
    app.click('[data-fs-status="draft"]'); await delay(30);
    ok(app.doc.querySelectorAll('[data-fs-row]').length === 1 && app.text('[data-fs-row]').includes('نظرسنجی پیش‌نویس'), 'فیلتر وضعیت روی همان پاسخ API');
    ok(app.text('[data-forms-panel]').includes('۷') , 'شمار پاسخ از response_count');
  } finally { app.window.close(); }
}

console.log('— مدیر: ابزارهای کاربران روی ماژول‌های سروری؛ زبانهٔ بدون مجوز یا بدون API صریح می‌ماند —');
{
  const app = await loadPanel({ role: 'manager', state: { v: 78, sec: 'users', uV: 'tools', uTool: 'log' } });
  try {
    await app.until(() => app.doc.querySelector('[data-server-tools]'), 'ابزارها');
    ok(!app.doc.querySelector('[data-utool="staff"]') && !app.doc.querySelector('[data-utool="log"]'), 'مدیر زبانهٔ نقش‌ها و تاریخچهٔ مالک را نمی‌بیند');
    ok(app.text('#admBody').includes('برای مجوزهای این حساب باز نیست'), 'زبانهٔ ذخیره‌شدهٔ بدون مجوز پنهان نمی‌شود؛ پیام صریح دارد');
    ok(!app.calls.some(c => c.path.startsWith('/api/owner/audit')), 'برای مدیر هیچ درخواستی به تاریخچهٔ مالک نمی‌رود');
    app.click('[data-utool="inbox"]'); await app.until(() => app.text('#admBody').includes('صندوق خروجی اعلان‌ها') && app.text('#admBody').includes('گواهی صادر شد'), 'صندوق خروجی');
    ok(app.calls.some(c => c.path.startsWith('/api/admin/notifications')), 'صندوق خروجی همان API اعلان‌ها را می‌خواند');
    app.click('[data-utool="tags"]'); await delay(30);
    /* تصمیم مالک ۱۴۰۵/۰۸/۰۱ (C11 گزینهٔ ۱): یادداشت داخلی در پروندهٔ کاربر ساخته شد؛ فقط «برچسب» همچنان مسدود است و دلیلش دقیق می‌ماند */
    ok(app.text('#admBody').includes('API متصل نیست') && app.text('#admBody').includes('برچسب روی حساب در مدل داده نیست') && app.text('#admBody').includes('یادداشت داخلی در پروندهٔ هر کاربر'), 'برچسب‌ها با دلیل دقیق مسدود است؛ یادداشت به پرونده ارجاع می‌دهد');
    app.click('[data-utool="perms"]'); await delay(30);
    const perms = app.text('[data-perm-map]');
    ok(perms.includes('rp_view') && perms.includes('finance'), 'نقشهٔ مجوزها کلیدهای واقعی را فهرست می‌کند');
    const financeRow = [...app.doc.querySelectorAll('[data-perm-map] .admlirow')].find(r => r.textContent.includes('finance'));
    ok(financeRow && financeRow.textContent.includes('غیرفعال'), 'مجوز مالی مدیر غیرفعال نشان داده می‌شود');
    app.click('[data-utool="report"]'); await app.until(() => app.doc.querySelector('.dash-kpis, [data-server-report]') || app.text('#admBody').includes('کل فرم‌های سرور'), 'گزارش');
    ok(app.calls.some(c => c.path.startsWith('/api/admin/reports/summary')), 'گزارش کاربران از API گزارش');
  } finally { app.window.close(); }
}

console.log('— مدیر: مسیر قدیمی «درخواست‌ها» به کارتابل مشترک می‌رسد؛ زبانهٔ حضور از کارت رویداد —');
{
  const app = await loadPanel({ role: 'manager', state: { v: 78, sec: 'users', uV: 'req' } });
  try {
    await app.until(() => app.doc.querySelector('[data-workflow-card]'), 'کارتابل مشترک');
    ok(app.stored().uV === 'shared-inbox', 'مسیر req به shared-inbox تغییر مسیر داده شد');
    ok(app.text('#admBody').includes('آزمایش زنده'), 'درخواست از /api/admin/inbox نمایش داده می‌شود');
    app.click('#admNav [data-sec="events"]');
    await app.until(() => app.doc.querySelector('[data-ct-interaction="ev-1"]'), 'فهرست رویدادها');
    app.click('[data-ct-interaction="ev-1"]'); await delay(60);
    ok(app.doc.querySelector('[data-ei-jump-attendance]') && app.doc.querySelector('[data-ei-jump-cert]'), 'زبانه‌های حضور و گواهی روی کارت رویداد هستند');
    app.click('[data-ei-jump-attendance]');
    await app.until(() => app.doc.querySelector('[data-att-panel]'), 'حضور و غیاب');
    ok(app.stored().sec === 'users' && app.stored().uV === 'att', 'پرش به بخش کاربران/حضور داخل همان پنل');
    await app.until(() => app.calls.some(c => /^\/api\/admin\/attendance\/forms\?.*q=ev-1/.test(c.path)), 'جست‌وجوی حضور با شناسهٔ رویداد');
    ok(true, 'فرم‌های حضور با شناسهٔ همان رویداد از API خوانده می‌شوند');
  } finally { app.window.close(); }
}

console.log('— مدیر بدون مجوز گزارش: کارت‌های وابسته پنهان و بدون درخواست —');
{
  const app = await loadPanel({ role: 'manager', permissions: ['us_view', 'ev_create'] });
  try {
    await app.until(() => app.doc.querySelector('[data-dashx-bar]'), 'داشبورد');
    await delay(150);
    ok(!app.calls.some(c => c.path.startsWith('/api/admin/notifications') || c.path.startsWith('/api/admin/inbox') || c.path.startsWith('/api/owner/audit')), 'بدون مجوز، درخواست اعلان/کارتابل/تاریخچه ارسال نمی‌شود');
    ok(!app.doc.querySelector('[data-dashx-audit]') && !app.doc.querySelector('[data-dashx-sched-card]'), 'کارت تاریخچه و زمان‌بندی برای این حساب نیست');
    app.click('.utile[data-sec="events"]'); await delay(20);
    if (app.doc.querySelector('.utile[data-sec="forms"]')) { app.click('.utile[data-sec="forms"]'); await delay(20); }
    ok(!app.doc.querySelector('[data-fs-export]'), 'بدون مجوز fm_export پیوند خروجی نمایش داده نمی‌شود (اجرا هم سمت سرور رد می‌شود)');
    app.click('#admNav [data-sec="dash"]'); await app.until(() => app.doc.querySelector('[data-dashx-bar]'), 'بازگشت به داشبورد');
    app.click('[data-dashx-map]'); await delay(30);
    const settingsRows = [...app.doc.querySelectorAll('[data-panel-map] .admlirow')].filter(r => r.textContent.includes('/api/owner/'));
    ok(settingsRows.length && settingsRows.every(r => r.textContent.includes('بدون مجوز این حساب') && !r.querySelector('button')), 'ردیف‌های مالک در نقشه برای مدیر «بدون مجوز» و بدون دکمه‌اند');
  } finally { app.window.close(); }
}

console.log('— مرحلهٔ C-4: تصمیم رسید در کارتابل با تأییدیه و دلیل الزامی؛ انصراف هیچ درخواستی نمی‌فرستد —');
{
  const app = await loadPanel({ role: 'owner', state: { v: 78, sec: 'users', uV: 'shared-inbox', sharedWorkflowKind: 'all' }, confirm: false });
  try {
    await app.until(() => app.doc.querySelector('[data-workflow-approve="00000000-0000-4000-8000-000000000002"]'), 'کارت رسید در کارتابل');
    const reason = app.doc.querySelector('[data-workflow-reason="00000000-0000-4000-8000-000000000002"]');
    ok(reason && reason.hasAttribute('required') && /الزامی/.test(app.text('[data-workflow-card="00000000-0000-4000-8000-000000000002"]')), 'برای رسید، دلیل/مرجع الزامی اعلام شده است');
    const profileReason = app.doc.querySelector('[data-workflow-reason="00000000-0000-4000-8000-000000000001"]');
    ok(profileReason && !profileReason.hasAttribute('required'), 'برای پروفایل، دلیل همچنان دلخواه است');
    app.click('[data-workflow-approve="00000000-0000-4000-8000-000000000002"]'); await delay(40);
    ok(app.decisions.length === 0 && app.confirms.length === 0 && reason.getAttribute('aria-invalid') === 'true', 'تأیید رسید بدون دلیل: نه تأییدیه، نه درخواست سرور');
    reason.value = 'مبلغ و شمارهٔ پیگیری با فیش تطبیق داده شد';
    app.click('[data-workflow-approve="00000000-0000-4000-8000-000000000002"]'); await delay(40);
    ok(app.confirms.length === 1 && /۱,۵۰۰,۰۰۰|1,500,000/.test(app.confirms[0]) && /تطبیق داده شد/.test(app.confirms[0]) && /تأیید رسید/.test(app.confirms[0]), 'تأییدیه مبلغ واقعی، دلیل و نوع تصمیم را نشان می‌دهد');
    ok(app.decisions.length === 0, 'انصراف در تأییدیه: هیچ تصمیمی به سرور نمی‌رود');
    ok(!app.doc.querySelector('[data-workflow-approve="00000000-0000-4000-8000-000000000002"]').disabled, 'دکمه‌ها پس از انصراف فعال می‌مانند');
    app.click('[data-workflow-reject="00000000-0000-4000-8000-000000000002"]'); await delay(40);
    ok(app.confirms.length === 2 && /رد رسید/.test(app.confirms[1]) && app.decisions.length === 0, 'رد رسید هم تأییدیه می‌خواهد و با انصراف ارسال نمی‌شود');
  } finally { app.window.close(); }
}
{
  const app = await loadPanel({ role: 'owner', state: { v: 78, sec: 'users', uV: 'shared-inbox', sharedWorkflowKind: 'all' } });
  try {
    await app.until(() => app.doc.querySelector('[data-workflow-approve="00000000-0000-4000-8000-000000000002"]'), 'کارت رسید در کارتابل');
    app.doc.querySelector('[data-workflow-reason="00000000-0000-4000-8000-000000000002"]').value = 'مرجع واریز ۱۲۳۴۵';
    app.click('[data-workflow-approve="00000000-0000-4000-8000-000000000002"]');
    await app.until(() => app.decisions.length === 1, 'ثبت تصمیم پس از تأییدیه');
    ok(app.confirms.length === 1 && app.decisions[0].id === '00000000-0000-4000-8000-000000000002' && app.decisions[0].decision === 'approved'
      && app.decisions[0].reason === 'مرجع واریز ۱۲۳۴۵' && app.decisions[0].expected_version === 3, 'پس از تأیید کاربر: تصمیم با دلیل و نسخهٔ درست به سرور می‌رود');
    await app.until(() => /در صف ربات است، هنوز تحویل نشده/.test(app.doc.body.textContent), 'پیام صادقانه: تصمیم ثبت شد ≠ اعلان تحویل شد');
  } finally { app.window.close(); }
}

console.log(`admin-restore: ${checks} بررسی، 0 خطا`);
