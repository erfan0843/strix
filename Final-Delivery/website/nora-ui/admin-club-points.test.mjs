/* آزمون فاز ششم پنل: امتیاز باشگاه از آینهٔ خواندنی دفترکل ربات با نشست سروری ساختگی.
   fetch با مسیر دقیق شبیه‌سازی می‌شود؛ هیچ سروری اجرا نمی‌شود و هیچ امتیازی ساخته یا تغییر داده نمی‌شود.
   حالت‌ها: خالی، تاریخچهٔ کامل، تاریخچهٔ ناقص، خطای شبکه/نشست، نبود مجوز (مدیر عادی)، نبودِ هر مسیر نوشتن. */
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
const CLUB = ['cl_member', 'cl_session', 'cl_cert', 'cl_content'];
const OWNER = [...MANAGER, ...CLUB, 'cl_dues', 'sys_points', 'finance',
  'role_assign', 'sys_fields', 'sys_settings', 'sys_backup', 'cert_final', 'user_delete', 'public_roster'];
const ACC_FULL = '0f0f0f0f-1111-4222-8333-444444444444';
const ACC_PART = '0f0f0f0f-1111-4222-8333-555555555555';
const SRC = '0c7f7f5e-9c1e-4a7e-8a1c-2b3d4e5f6a7b';

function makeMirror() {
  const holderFull = { account_id: ACC_FULL, bale_user_id: '910001', display_name: 'زهرا موسوی', name_source: 'profile' };
  const holderPart = { account_id: ACC_PART, bale_user_id: '910005', display_name: '', name_source: 'none' };
  const row = (ledger_id, delta, balance_after, holder, extra = {}) => ({
    id: `e-${ledger_id}`, external_key: `${SRC}:${ledger_id}`, ledger_id, delta, balance_after,
    entry_type: delta > 0 ? 'award' : 'spend', source: 'achievement', ref_key: `ach:${holder.bale_user_id}:k${ledger_id}`,
    reason: '', actor_kind: 'system', reverses_external_key: null, bot_created_at: '2026-10-21 09:00:00',
    synced_at: '2026-10-21T09:05:00+00:00', holder, ...extra,
  });
  const entries = [
    row(1, 120, 120, holderFull, { entry_type: 'opening_balance', source: 'legacy_counter', ref_key: 'opening:910001', reason: 'موجودی شمارندهٔ قدیمی' }),
    row(2, 10, 130, holderFull, { ref_key: 'ach:910001:first_step' }),
    row(3, -30, 100, holderFull, { entry_type: 'spend', source: 'reward_redeem', ref_key: 'redeem:4', actor_kind: 'user' }),
    row(7, 5, 45, holderPart, { ref_key: 'ach:910005:x' }),
  ];
  const members = [
    { account_id: ACC_PART, bale_user_id: '910005', display_name: '', entries: 1, latest_balance: 45, latest_ledger_id: 7, latest_bot_created_at: '2026-10-21 09:00:00', latest_synced_at: '2026-10-21T09:05:00+00:00', history_complete: false, chain_breaks: 1, has_opening: false },
    { account_id: ACC_FULL, bale_user_id: '910001', display_name: 'زهرا موسوی', entries: 3, latest_balance: 100, latest_ledger_id: 3, latest_bot_created_at: '2026-10-21 09:00:00', latest_synced_at: '2026-10-21T09:05:00+00:00', history_complete: true, chain_breaks: 0, has_opening: true },
  ];
  return { entries, members };
}

async function loadPanel(identity) {
  const mirror = identity.mirror || makeMirror();
  const calls = [];
  const values = new Map([['nora-admin', JSON.stringify({ v: 78, sec: 'users', ...(identity.state || {}) })]]);
  const store = {
    getItem(k) { return values.has(String(k)) ? values.get(String(k)) : null; },
    setItem(k, v) { values.set(String(k), String(v)); },
    removeItem(k) { values.delete(String(k)); }, clear() { values.clear(); },
    key(i) { return [...values.keys()][i] || null; }, get length() { return values.size; },
  };
  const perms = identity.permissions || (identity.role === 'owner' ? OWNER : identity.role === 'club-supervisor' ? [...MANAGER, ...CLUB] : MANAGER);
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
        calls.push({ path, method, headers: options.headers || {}, body: typeof options.body === 'string' ? options.body : null });
        if (identity.outage && path.startsWith('/api/admin/club/')) throw new TypeError('network down');
        if (identity.expired && path.startsWith('/api/admin/club/')) return reply(401, { detail: 'authentication_required' });
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
        if (path.startsWith('/api/admin/content/')) return reply(200, { items: [], total: 0, counts: {}, limit: 20, offset: 0, has_more: false, kind: 'events', version: 1, source: 'site_content', can_edit: has('ev_create'), can_publish: has('ev_publish') });
        if (path.startsWith('/api/admin/media')) return reply(200, { source: 'shared_server_database', items: [], total: 0, limit: 20, offset: 0, has_more: false, unused: 0, max_bytes: 3145728 });
        if (path.startsWith('/api/admin/users')) return reply(200, { items: [], total: 0, limit: 20, offset: 0, has_more: false, can_open_roles: identity.role === 'owner' });
        if (path.startsWith('/api/admin/attendance/')) return reply(200, { items: [], total: 0, limit: 20, offset: 0, has_more: false });
        if (path.startsWith('/api/admin/certificates')) return reply(200, { source: 'shared_server_database', items: [], total: 0, limit: 20, offset: 0, has_more: false, counts: { issued: 0, revoked: 0 }, events: [], can_revoke: false });
        /* ── امتیاز باشگاه: فقط GET؛ هر متد دیگری ۴۰۵ ── */
        if (path.startsWith('/api/admin/club/points')) {
          if (method !== 'GET') return reply(405, { detail: 'method_not_allowed' });
          if (!has('cl_member')) return reply(403, { detail: 'permission_denied' });
          const one = path.match(/^\/api\/admin\/club\/points\/members\/([^/?]+)$/);
          if (one) {
            const m = mirror.members.find((x) => x.account_id === one[1]);
            if (!m) return reply(404, { detail: 'member_not_found' });
            return reply(200, { ...m, source: 'shared_server_database', history: mirror.entries.filter((e) => e.holder.account_id === m.account_id).sort((a, b) => b.ledger_id - a.ledger_id) });
          }
          const query = Object.fromEntries(new URLSearchParams(path.split('?')[1] || ''));
          const q = String(query.q || '');
          if (path.startsWith('/api/admin/club/points/members')) {
            const items = mirror.members.filter((m) => !q || (m.display_name + ' ' + m.bale_user_id).includes(q));
            return reply(200, { source: 'shared_server_database', items, total: items.length, limit: 20, offset: 0, has_more: false, q, partial: items.filter((m) => !m.history_complete).length, write_routes: false });
          }
          let items = mirror.entries.slice().sort((a, b) => b.ledger_id - a.ledger_id);
          if (query.entry_type) items = items.filter((e) => e.entry_type === query.entry_type);
          if (q) items = items.filter((e) => (e.ref_key + ' ' + e.holder.display_name + ' ' + e.reason).includes(q));
          const counts = { opening_balance: 0, award: 0, spend: 0, refund: 0, reversal: 0, manual_adjust: 0 };
          mirror.entries.forEach((e) => { counts[e.entry_type] += 1; });
          return reply(200, { source: 'shared_server_database', items, total: items.length, limit: 20, offset: 0, has_more: false, q, entry_type: query.entry_type || '', counts, write_routes: false });
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
  const noWrite = () => {
    assert.equal(doc.querySelector('[data-club-adjust], [data-club-award], [data-club-spend], [data-club-delete], [data-club-edit], #clubDelta, #clubReason'), null, 'هیچ دکمه یا فیلد تغییر امتیاز در پنل نیست');
    assert.ok(calls.filter((c) => c.path.startsWith('/api/admin/club/')).every((c) => c.method === 'GET'), 'پنل به مسیر امتیاز فقط GET می‌زند');
  };
  return { dom, doc, calls, click, type, until, body, noLeak, noWrite, mirror, close: () => dom.window.close() };
}

const openClub = async (app) => {
  app.click('#admNav [data-sec="users"]');
  await delay(30);
  if (app.doc.querySelector('[data-uback]') && !app.doc.querySelector('[data-users-panel]') && !app.doc.querySelector('[data-club-panel]')) app.click('[data-uback]');
  await app.until(() => app.doc.querySelector('[data-open-club]') || app.doc.querySelector('[data-club-panel]'), 'کارت امتیاز باشگاه');
  if (app.doc.querySelector('[data-open-club]')) app.click('[data-open-club]');
};

console.log('— مالک: اعضا از آینهٔ دفترکل، ناقص/کامل، جزئیات عضو، همهٔ ردیف‌ها، فیلتر و جست‌وجو —');
{
  const app = await loadPanel({ role: 'owner' });
  try {
    await openClub(app);
    await app.until(() => app.doc.querySelector(`[data-club-member="${ACC_FULL}"]`), 'فهرست اعضا');
    const first = app.calls.find((c) => c.path.startsWith('/api/admin/club/'));
    assert.equal(first.path, '/api/admin/club/points/members?limit=20&offset=0', 'پارامترهای فهرست اعضا دقیقاً همان قرارداد API است');
    assert.match(app.body(), /آینهٔ خواندنی دفترکل ربات/);
    assert.match(app.body(), /زهرا موسوی/);
    assert.match(app.body(), /تاریخچهٔ کامل/);
    assert.match(app.body(), /تاریخچهٔ ناقص/);
    assert.match(app.body(), /۱ عضو تاریخچهٔ ناقص دارند/);
    assert.match(app.body(), /امتیاز فقط در ربات داده، خرج یا تعدیل می‌شود/);
    app.noLeak(); app.noWrite();

    app.click(`[data-club-member="${ACC_FULL}"]`);
    await app.until(() => app.doc.querySelector('[data-club-member-detail]') && /تاریخچه \(تازه‌ترین بالا\)/.test(app.body()), 'جزئیات عضو');
    assert.ok(app.calls.some((c) => c.path === `/api/admin/club/points/members/${ACC_FULL}`), 'جزئیات از مسیر عضو خوانده می‌شود');
    const rows = [...app.doc.querySelectorAll('[data-club-entry]')].map((el) => el.dataset.clubEntry);
    assert.deepEqual(rows, [`${SRC}:3`, `${SRC}:2`, `${SRC}:1`], 'تاریخچه با ترتیب و کلید پایدار ربات نمایش داده می‌شود');
    assert.match(app.body(), /موجودی طبق آخرین ردیف رسیده/);
    assert.match(app.body(), /۱۰۰/);
    assert.match(app.body(), /موجودی افتتاحیه/);
    assert.match(app.body(), /خرید پاداش/);
    assert.match(app.body(), /کامل \(زنجیرهٔ موجودی/);
    app.noLeak(); app.noWrite();

    app.click('[data-club-back]');
    await app.until(() => app.doc.querySelector('[data-club-panel]'), 'بازگشت به فهرست');
    app.click(`[data-club-member="${ACC_PART}"]`);
    await app.until(() => app.doc.querySelector('[data-club-member-detail]') && /ناقص \(/.test(app.body()), 'عضو با تاریخچهٔ ناقص');
    assert.match(app.body(), /فقط «آخرین ردیف رسیده» است/);
    assert.match(app.body(), /بدون نام ثبت‌شده/);
    app.click('[data-club-back]');
    await app.until(() => app.doc.querySelector('[data-club-panel]'), 'بازگشت دوباره');

    app.click('[data-club-mode="entries"]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/club/points?limit=20&offset=0'), 'همهٔ ردیف‌ها از سرور');
    await app.until(() => app.doc.querySelectorAll('[data-club-entry]').length === 4, 'چهار ردیف');
    app.click('[data-club-type="spend"]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/club/points?limit=20&offset=0&entry_type=spend'), 'فیلتر نوع سمت سرور');
    await app.until(() => app.doc.querySelectorAll('[data-club-entry]').length === 1, 'فقط کسرها');
    app.click('[data-club-type=""]');
    await app.until(() => app.doc.querySelectorAll('[data-club-entry]').length === 4, 'بازگشت به همه');
    app.type('#clubQuery', 'redeem:4');
    app.click('[data-club-search]');
    await app.until(() => app.calls.some((c) => c.path === '/api/admin/club/points?limit=20&offset=0&q=redeem%3A4'), 'جست‌وجوی سمت سرور');
    await app.until(() => app.doc.querySelectorAll('[data-club-entry]').length === 1, 'نتیجهٔ جست‌وجو');
    app.type('#clubQuery', 'چیزی-که-نیست');
    app.click('[data-club-search]');
    await app.until(() => /با این جست‌وجو یا فیلتر ردیفی پیدا نشد/.test(app.body()), 'خالی با فیلتر');
    app.noLeak(); app.noWrite();
  } finally { app.close(); }
}

console.log('— حالت خالی: هیچ ردیفی هنوز نرسیده؛ پنل چیزی نمی‌سازد —');
{
  const app = await loadPanel({ role: 'owner', mirror: { entries: [], members: [] } });
  try {
    await openClub(app);
    await app.until(() => /هنوز هیچ ردیفی از دفترکل امتیاز ربات به پایگاه مشترک نرسیده است/.test(app.body()), 'پیام خالی صادقانه');
    assert.equal(app.doc.querySelector('[data-club-member]'), null, 'عضوی ساخته نمی‌شود');
    assert.doesNotMatch(app.body(), /تاریخچهٔ کامل|تاریخچهٔ ناقص/, 'بدون عضو، نشانی هم نیست');
    app.noLeak(); app.noWrite();
  } finally { app.close(); }
}

console.log('— خطای شبکه و نشست منقضی: پیام صریح و تلاش دوباره؛ بدون عدد ساختگی —');
{
  const app = await loadPanel({ role: 'owner', outage: true });
  try {
    await openClub(app);
    await app.until(() => app.doc.querySelector('[data-club-refresh]') && /در دسترس نیست|دریافت نشد|اتصال را بررسی کنید/.test(app.body()), 'پیام خطا');
    assert.equal(app.doc.querySelector('[data-club-member]'), null, 'با خطا عضوی نشان داده نمی‌شود');
    assert.doesNotMatch(app.body(), /۱۰۰|۴۵ امتیاز/, 'عدد ساختگی نیست');
    app.noWrite();
  } finally { app.close(); }
  const expired = await loadPanel({ role: 'owner', expired: true });
  try {
    await openClub(expired);
    await expired.until(() => expired.doc.querySelector('[data-club-refresh]') || /نشست|ورود/.test(expired.body()), 'نشست منقضی');
    assert.equal(expired.doc.querySelector('[data-club-member]'), null);
  } finally { expired.close(); }
}

console.log('— سرپرست باشگاه (cl_member) می‌بیند؛ مدیر عادی کارت و صفحه را ندارد —');
{
  const supervisor = await loadPanel({ role: 'club-supervisor' });
  try {
    await openClub(supervisor);
    await supervisor.until(() => supervisor.doc.querySelector(`[data-club-member="${ACC_FULL}"]`), 'فهرست اعضا برای سرپرست');
    supervisor.noLeak(); supervisor.noWrite();
  } finally { supervisor.close(); }
  const manager = await loadPanel({ role: 'manager' });
  try {
    manager.click('#admNav [data-sec="users"]');
    await delay(60);
    if (manager.doc.querySelector('[data-uback]') && !manager.doc.querySelector('[data-users-panel]')) manager.click('[data-uback]');
    await manager.until(() => manager.doc.querySelector('[data-open-cert]') || manager.doc.querySelector('[data-users-panel]'), 'هاب کاربران مدیر');
    assert.equal(manager.doc.querySelector('[data-open-club]'), null, 'کارت امتیاز باشگاه برای مدیر عادی نیست');
    assert.ok(!manager.calls.some((c) => c.path.startsWith('/api/admin/club/')), 'مدیر عادی درخواستی به مسیر امتیاز نمی‌زند');
  } finally { manager.close(); }
  /* حتی با حالت ذخیره‌شدهٔ uV=club، صفحه برای مدیر عادی فقط پیام مجوز است (نه داده، نه درخواست) */
  const forced = await loadPanel({ role: 'manager', state: { uV: 'club' } });
  try {
    forced.click('#admNav [data-sec="users"]');
    await forced.until(() => /فقط برای مالک و سرپرست باشگاه باز است/.test(forced.body()) || forced.doc.querySelector('[data-open-cert]'), 'پیام مجوز');
    assert.equal(forced.doc.querySelector('[data-club-panel]'), null, 'پنل امتیاز برای مدیر عادی رندر نمی‌شود');
    assert.ok(!forced.calls.some((c) => c.path.startsWith('/api/admin/club/')), 'هیچ درخواستی به مسیر امتیاز');
  } finally { forced.close(); }
}

console.log('✅ admin-club-points: همهٔ حالت‌های آینهٔ دفترکل امتیاز سبز');
