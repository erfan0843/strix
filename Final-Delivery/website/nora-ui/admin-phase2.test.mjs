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
  const registrations = [
    { id: 'a1a1a1a1-1111-4222-8333-444444444401', form_id: 'fm-1', form_name: 'فرم ثبت‌نام', event_id: 'ev-a1', event_title: 'کارگاه نگارش', event_date: '1405/08/12', status: 'accepted', payment_status: 'paid_manual', receipt_uploaded: true, ticket_checked_in: true, ticket_type: 'paid', created_at: '2026-10-02T08:00:00+00:00' },
    { id: 'a1a1a1a1-1111-4222-8333-444444444402', form_id: 'fm-2', form_name: 'فرم رایگان', event_id: 'ev-b2', event_title: 'نشست کتاب', event_date: '1405/09/01', status: 'waitlisted', payment_status: null, receipt_uploaded: false, ticket_checked_in: false, ticket_type: 'free', created_at: '2026-10-03T08:00:00+00:00' },
  ];
  const userNotifications = [
    { id: 'n-1', kind: 'registration_accepted', title: 'ثبت‌نام شما پذیرفته شد', body: 'کارگاه نگارش', delivery_status: 'delivered', delivery_state: 'delivered', delivery_attempts: 1, last_delivery_error: null, link: 'event.html?id=ev-a1', created_at: '2026-10-02T08:05:00+00:00', delivered_at: '2026-10-02T08:06:00+00:00', read: true, scope: 'account', has_bale_identity: true, source_task_id: null },
    { id: 'n-2', kind: 'content_published', title: 'رویداد تازه منتشر شد', body: 'نشست کتاب', delivery_status: 'pending', delivery_state: 'retrying', delivery_attempts: 2, last_delivery_error: 'bale_timeout', link: null, created_at: '2026-10-03T08:05:00+00:00', delivered_at: null, read: false, scope: 'audience', has_bale_identity: true, source_task_id: null },
    { id: 'n-3', kind: 'receipt_approved', title: 'فیش تأیید شد', body: '', delivery_status: 'failed', delivery_state: 'failed', delivery_attempts: 0, last_delivery_error: 'no_bale_identity', link: null, created_at: '2026-10-04T08:05:00+00:00', delivered_at: null, read: false, scope: 'account', has_bale_identity: false, source_task_id: null },
  ];
  return { version: 7, events, people, registrations, userNotifications };
}

async function loadPanel(identity) {
  const world = identity.world || makeWorld();
  const calls = [];
  const dialogs = [];
  const values = new Map([['nora-admin', JSON.stringify({ v: 78, sec: identity.sec || 'events', ...(identity.state || {}) })]]);
  const store = {
    getItem(k) { return values.has(String(k)) ? values.get(String(k)) : null; },
    setItem(k, v) { values.set(String(k), String(v)); },
    removeItem(k) { values.delete(String(k)); }, clear() { values.clear(); },
    key(i) { return [...values.keys()][i] || null; }, get length() { return values.size; },
  };
  const sessionValues = identity.sessionValues || new Map();
  const sessionStore = {
    getItem(k) { return sessionValues.has(String(k)) ? sessionValues.get(String(k)) : null; },
    setItem(k, v) { sessionValues.set(String(k), String(v)); },
    removeItem(k) { sessionValues.delete(String(k)); }, clear() { sessionValues.clear(); },
    key(i) { return [...sessionValues.keys()][i] || null; }, get length() { return sessionValues.size; },
  };
  const perms = identity.permissions || (identity.role === 'owner' ? OWNER : MANAGER);
  const has = (p) => perms.includes(p);
  const list = (kind) => ({
    items: kind === 'events' ? world.events : (world.articles || []), total: kind === 'events' ? world.events.length : (world.articles || []).length,
    counts: { draft: 1, published: 1, paused: 0, archived: 0 }, limit: 20, offset: 0, has_more: false, kind,
    version: world.version, source: 'site_content', can_edit: has('ev_create'), can_publish: has('ev_publish'),
  });
  const dom = await JSDOM.fromFile(ADMIN_HTML, {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(window) {
      Object.defineProperty(window.navigator, 'userAgent', { configurable: true, value: 'ArenaBrowser/1.0' });
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      Object.defineProperty(window, 'sessionStorage', { configurable: true, value: sessionStore });
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
        if (path === '/api/forms') return reply(200, { items: identity.forms || [] });
        if (path === '/api/owner/site-content') {
          if (identity.role !== 'owner') return reply(401, { detail: 'authentication_required' });
          if (!world.siteContent) return reply(200, { content: {}, version: world.version, updated_at: null });
          const view = () => ({ content: JSON.parse(JSON.stringify(world.siteContent)), version: world.version, updated_at: '2026-10-22T08:00:00+00:00' });
          if (method === 'GET') return reply(200, view());
          if (method !== 'PATCH') return reply(405, { detail: 'method_not_allowed' });
          /* همان قرارداد PATCH /api/owner/site-content: CSRF، بدنهٔ دقیق، نسخه، ردیف‌های ردشده، نگهبان ارجاع */
          if ((options.headers || {})['X-CSRF-Token'] !== 'owner-csrf') return reply(403, { detail: 'csrf_check_failed' });
          if (!body || Object.keys(body).sort().join() !== 'content,expected_version') return reply(400, { detail: 'invalid_site_content_request' });
          if (body.expected_version !== world.version) return reply(409, { detail: { code: 'site_content_version_conflict', current_version: world.version } });
          const rejected = {};
          const incoming = {};
          for (const key of Object.keys(body.content || {})) {
            const rows = Array.isArray(body.content[key]) ? body.content[key] : [];
            const kept = [];
            rows.forEach((row, index) => {
              if (!row || typeof row !== 'object') { (rejected[key] ||= []).push({ index, id: '', reason: 'invalid_row' }); return; }
              if (!row.id || !String(row.n || '').trim()) { (rejected[key] ||= []).push({ index, id: String(row.id || ''), reason: 'missing_required_fields' }); return; }
              if (row.hidden) { (rejected[key] ||= []).push({ index, id: String(row.id), reason: 'non_public' }); return; }
              kept.push(row);
            });
            incoming[key] = kept;
          }
          if (incoming.people) {
            const next = new Set(incoming.people.map((r) => String(r.id)));
            const usedBy = (world.siteContent.events || []).filter((e) => e.tchr && !next.has(String(e.tchr)) && (world.siteContent.people || []).some((p) => String(p.id) === String(e.tchr)))
              .map((e) => ({ kind: 'events', id: e.id, t: e.t, ref: e.tchr }));
            if (usedBy.length) return reply(422, { detail: { code: 'reference_in_use', field: 'people', ids: [...new Set(usedBy.map((u) => u.ref))], used_by: usedBy } });
          }
          Object.assign(world.siteContent, incoming); world.version += 1; world.patches = (world.patches || 0) + 1;
          return reply(200, { ...view(), rejected_rows: rejected });
        }
        if (/^\/api\/admin\/reports\/summary\?period=/.test(path)) return reply(200, { source: 'shared_server_database', period: '30d', forms: { total: 0, by_status: {} }, responses: { total: 0, by_status: {} }, accounts: { total: 0, by_role: {} }, reviews: { total: 0, by_kind: {} }, notifications: { total: 0, by_delivery_status: {} }, cooperation_requests: { total: 0, by_status: {} } });
        if (path.startsWith('/api/admin/inbox')) return reply(200, { items: [], has_more: false });
        if (path.startsWith('/api/owner/audit')) {
          if (identity.role !== 'owner') return reply(401, { detail: 'owner_session_required' });
          const qs = new URLSearchParams(path.split('?')[1] || '');
          world.auditCalls = (world.auditCalls || 0) + 1;
          if (world.auditFailOnce) { world.auditFailOnce = false; return reply(503, { detail: 'service_unavailable' }); }
          const tid = qs.get('target_id') || '';
          if (tid) {
            /* فیلتر سمت سرور: فقط ردیف‌های همین هدف */
            const all = (world.auditByTarget || {})[tid] || [];
            const off = +qs.get('offset') || 0, lim = +qs.get('limit') || 20;
            return reply(200, { items: all.slice(off, off + lim), limit: lim, offset: off, has_more: off + lim < all.length, actions: [] });
          }
          return reply(200, { items: [], limit: 30, offset: 0, has_more: false, actions: [] });
        }

        /* B1: tchr/partnerId must be ids of people/partners in the same document */
        const refCheck = (kind, record) => {
          const site = world.siteContent || { people: [], partners: [] };
          const refs = kind === 'events' ? [['tchr', 'people'], ['partnerId', 'partners']] : [['tchr', 'people']];
          for (const [field, cat] of refs) {
            const value = String((record || {})[field] || '');
            if (value && !(site[cat] || []).some((r) => String(r.id) === value)) return reply(422, { detail: { code: 'unknown_reference', field } });
          }
          return null;
        };
        if (path === '/api/public/site-content') {
          if (!world.siteContent) return reply(404, { detail: 'site_content_not_published' });
          const pub = (rows) => (rows || []).filter((r) => !r.hidden);
          return reply(200, { content: { people: pub(world.siteContent.people), partners: pub(world.siteContent.partners), events: [], articles: [] }, version: world.version });
        }
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
            const rec = (kind === 'articles' ? (world.articles || []) : world.events).find((e) => e.id === id);
            if (!rec) return reply(404, { detail: 'content_record_not_found' });
            /* مانند content_admin.detail: زمان‌ها UTC ذخیره‌اند و local_times شمسی/تهران برمی‌گردد */
            const detail = { ...rec, local_times: { startsAt: rec.startsAt ? '1405/08/12 10:00' : '', endsAt: '', regOpensAt: '', regClosesAt: rec.regClosesAt ? '1405/08/10 23:59' : '' },
              registration: { state: rec.lifecycle === 'cancelled' ? 'cancelled' : 'open', reason: '' } };
            return reply(200, { kind, record: detail, version: world.version });
          }
          if (method === 'POST' && !id) {
            const denied = needWrite(); if (denied) return denied;
            if (body.expected_version !== world.version) return reply(409, { detail: { code: 'site_content_version_conflict', current_version: world.version } });
            if (!String(body.record.t || '').trim()) return reply(422, { detail: { code: 'title_required', field: 't' } });
            if (body.record.on && !/^\d{4}\/\d{2}\/\d{2}$/.test(body.record.on)) return reply(422, { detail: { code: 'invalid_jalali_date', field: 'on' } });
            if (body.record.regClosesAt && !/^\d{4}\/\d{2}\/\d{2}( ([01]\d|2[0-3]):[0-5]\d)?$/.test(body.record.regClosesAt)) return reply(422, { detail: { code: 'invalid_datetime', field: 'regClosesAt' } });
            if (body.status === 'published' && !String(body.record.d || '').trim()) return reply(422, { detail: { code: 'event_description_required', field: 'd' } });
            const refErr = refCheck(kind, body.record); if (refErr) return refErr;
            world.version += 1;
            const rec = { id: kind === 'articles' ? 'ar-new1' : 'ev-new1', ...body.record, status: body.status || 'draft', updated_at: '2026-10-21T08:00:00+00:00', created_at: '2026-10-21T08:00:00+00:00' };
            (kind === 'articles' ? (world.articles ||= []) : world.events).unshift(rec);
            return reply(200, { kind, record: rec, version: world.version, saved: true });
          }
          if (method === 'PUT' && id) {
            const denied = needWrite(); if (denied) return denied;
            const rec = (kind === 'articles' ? (world.articles || []) : world.events).find((e) => e.id === id);
            if (!rec) return reply(404, { detail: 'content_record_not_found' });
            if (body.expected_version !== world.version) return reply(409, { detail: { code: 'site_content_version_conflict', current_version: world.version } });
            const refErr = refCheck(kind, body.record); if (refErr) return refErr;
            if (Array.isArray(body.record.blocks) && body.record.blocks.some((b) => b && b.ty === 'img' && /^javascript:/i.test(b.src || ''))) return reply(422, { detail: { code: 'invalid_image', field: 'blocks' } });
            Object.assign(rec, body.record); world.version += 1;
            return reply(200, { kind, record: rec, version: world.version, saved: true });
          }
          if (method === 'POST' && statusOp) {
            const denied = needPublish(); if (denied) return denied;
            const rec = (kind === 'articles' ? (world.articles || []) : world.events).find((e) => e.id === id);
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
          const [, idPath, query] = u;
          const [id, sub, subId] = String(idPath || '').split('/');
          if (sub) {
            /* U4/U5: فقط حساب هدف؛ شناسهٔ حساب دیگر یا پاسخ حساب دیگر → ۴۰۴ (در سرور داخل scope جست‌وجو می‌شود) */
            if (id !== ACC) return reply(404, { detail: 'user_not_found' });
            const params = new URLSearchParams(query || '');
            const limit = Number(params.get('limit') || 20), offset = Number(params.get('offset') || 0);
            const finance = has('finance');
            if (sub === 'registrations' && !subId) {
              if (identity.regsFail && !world.regsOk) return reply(503, { detail: 'service_unavailable' });
              const all = world.registrations || [];
              const items = all.slice(offset, offset + limit);
              return reply(200, { source: 'shared_server_database', account_id: ACC, items, total: all.length, limit, offset, has_more: offset + limit < all.length });
            }
            if (sub === 'registrations' && subId) {
              const row = (world.registrations || []).find((r) => r.id === subId);
              if (!row) return reply(404, { detail: 'registration_not_found' });
              const payment = row.payment_status ? { status: row.payment_status, method: 'card_transfer', ...(finance ? { amount: 1200000, currency: 'IRR', transaction_id: 'TRX-778899' } : {}) } : null;
              return reply(200, { ...row, source: 'shared_server_database', account_id: ACC, response_id: row.id,
                form: { id: 'fm-1', name: row.form_name, version: 3 }, event: { id: row.event_id, title: row.event_title, date: row.event_date }, registrant_name: 'سارا آزمایشی',
                answers: [
                  { field_id: 'f_name', label: 'نام و نام خانوادگی', type: 'text', value: 'سارا آزمایشی', masked: null },
                  { field_id: 'f_mobile', label: 'شمارهٔ همراه', type: 'mobile', value: null, masked: 'mobile', hint: '4321' },
                  { field_id: 'f_nid', label: 'کد ملی', type: 'nid', value: null, masked: 'national_id', hint: '' },
                  { field_id: 'f_meal', label: 'وعدهٔ غذایی', type: 'select', value: ['گیاهی'], masked: null },
                ],
                companions: [{ id: 'c0c0c0c0-1111-4222-8333-444444444499', name: 'همراه یکم', status: 'accepted', ticket_checked_in: false }],
                payment, finance_visible: finance,
                receipt: { uploaded: !!row.receipt_uploaded, task_id: row.receipt_uploaded ? 't0t0t0t0-1111-4222-8333-444444444477' : null, task_status: row.receipt_uploaded ? 'approved' : null },
                attendance: { checked_in: !!row.ticket_checked_in, checked_in_at: row.ticket_checked_in ? '2026-10-05T15:00:00+00:00' : null, checked_in_by: row.ticket_checked_in ? { kind: 'bot', id: '123456' } : null },
                updated_at: '2026-10-05T15:00:00+00:00' });
            }
            if (sub === 'notifications' && !subId) {
              const all = world.userNotifications || [];
              const items = all.slice(offset, offset + limit);
              return reply(200, { source: 'shared_server_database', account_id: ACC, items, total: all.length, limit, offset, has_more: offset + limit < all.length });
            }
            return reply(404, { detail: 'not_found' });
          }
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
  return { dom, window: dom.window, doc, calls, dialogs, click, type, until, body, noLeak, world, sessionValues, close: () => dom.window.close() };
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
    /* فاز ۷: زمان‌بندی دقیق؛ خطای ۴۲۲ سرور زیر همان فیلد و ارسال حالت ثبت‌نام/وضعیت برگزاری */
    assert.equal(app.doc.querySelector('#ctf_regMode').value, 'auto', 'حالت ثبت‌نام پیش‌فرض خودکار است');
    assert.equal(app.doc.querySelector('#ctf_lifecycle').value, 'scheduled');
    app.type('#ctf_regClosesAt', '1405/08/10 25:99');
    app.click('[data-ct-save]');
    await app.until(() => app.doc.querySelector('[data-ct-err="regClosesAt"]')?.textContent.includes('ساعت تهران'), 'خطای زمان نامعتبر زیر فیلد مهلت ثبت‌نام');
    assert.equal(app.world.events.length, 2, 'با زمان نامعتبر چیزی ساخته نشد');
    app.type('#ctf_regClosesAt', '1405/08/10 23:59');
    app.type('#ctf_startsAt', '1405/08/12 10:00');
    app.type('#ctf_conditions', 'ویژهٔ نوجوانان ۱۲ تا ۱۶ سال');
    app.click('[data-ct-save]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-new1"]'), 'رکورد تازه در فهرست');
    {
      const created = app.calls.find((c) => c.method === 'POST' && c.path === '/api/admin/content/events' && c.body.record.regClosesAt === '1405/08/10 23:59');
      assert.ok(created, 'مهلت ثبت‌نام به همان شکل ورودی به سرور می‌رود تا سرور به UTC تبدیل کند');
      assert.equal(created.body.record.startsAt, '1405/08/12 10:00');
      assert.equal(created.body.record.regMode, 'auto');
      assert.equal(created.body.record.lifecycle, 'scheduled');
      assert.equal(created.body.record.conditions, 'ویژهٔ نوجوانان ۱۲ تا ۱۶ سال');
    }
    assert.match(app.body(), /رکورد ساخته شد · نسخهٔ ۸ · وضعیت از سرور: پیش‌نویس/);
    const create = app.calls.find((c) => c.method === 'POST' && c.path === '/api/admin/content/events');
    assert.equal(create.body.expected_version, 7);
    assert.equal(create.headers['X-CSRF-Token'], 'owner-csrf', 'نوشتن با CSRF مالک');

    app.click('[data-ct-edit="ev-new1"]');
    await app.until(() => app.doc.querySelector('#ctf_startsAt')?.value === '1405/08/12 10:00', 'پرکردن دوبارهٔ زمان‌ها از local_times سرور (نه مقدار خام UTC)');
    assert.equal(app.doc.querySelector('#ctf_regClosesAt').value, '1405/08/10 23:59');
    assert.match(app.doc.querySelector('[data-ct-reg-state]').textContent, /ثبت‌نام باز/, 'وضعیت فعلی ثبت‌نام از سرور نمایش داده می‌شود');
    app.click('[data-ct-cancel]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-new1"]'), 'بازگشت به فهرست');
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

console.log('— B4 ممیزی مالک: فرم‌های ثبت‌نام همین رویداد در ویرایشگر؛ ساخت فرم با شناسهٔ رویداد بدون تایپ دوباره؛ بدون مجوز فرم‌ساز هیچ پیوندی —');
{
  const forms = [
    { id: 'f-reg-1', name: 'فرم ثبت‌نام کارگاه', need: 'reg', ev: 'ev-a1', purpose: 'registration', status: 'published', response_count: 4 },
    { id: 'f-other', name: 'فرم رویداد دیگر', need: 'reg', ev: 'ev-zzz', purpose: 'registration', status: 'draft', response_count: 0 },
    { id: 'f-buy', name: 'فرم خرید ضبط', need: 'reg', ev: 'ev-a1', purpose: 'recording_access', status: 'published', response_count: 1 },
  ];
  const app = await loadPanel({ role: 'owner', sec: 'events', forms });
  try {
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست');
    app.click('[data-ct-edit="ev-a1"]');
    await app.until(() => app.doc.querySelector('[data-ct-forms="ev-a1"]'), 'بلوک فرم‌های رویداد در ویرایشگر');
    await app.until(() => app.doc.querySelector('[data-ct-form-row="f-reg-1"]'), 'فرم ثبت‌نام همین رویداد از GET /api/forms فهرست شد');
    assert.equal(app.doc.querySelector('[data-ct-form-row="f-other"]'), null, 'فرم رویداد دیگر نشان داده نمی‌شود');
    assert.equal(app.doc.querySelector('[data-ct-form-row="f-buy"]'), null, 'فرم خرید ضبط جزو ثبت‌نام نیست (خرید ≠ ثبت‌نام)');
    const make = app.doc.querySelector('[data-ct-form-create="ev-a1"]');
    assert.ok(make, 'دکمهٔ ساخت فرم برای همین رویداد');
    const href = new URL(make.getAttribute('href'), 'http://x/');
    assert.equal(href.pathname, '/create.html');
    assert.equal(href.searchParams.get('ev'), 'ev-a1', 'شناسهٔ رویداد در آدرس فرم‌ساز (بدون تایپ دوباره)');
    assert.equal(href.searchParams.get('need'), 'reg');
    assert.equal(href.searchParams.get('name'), 'کارگاه نگارش');
    assert.ok(app.doc.querySelector('[data-ct-form-row="f-reg-1"] a[href="create.html?fid=f-reg-1"]'), 'ویرایش فرم در فرم‌ساز');
    assert.ok(app.doc.querySelector('[data-ct-form-row="f-reg-1"] a[href="builder.html?fid=f-reg-1#responses"]'), 'پاسخ‌های فرم');
    app.click('[data-ct-cancel]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-b2"]'), 'بازگشت');
    app.click('[data-ct-edit="ev-b2"]');
    await app.until(() => app.doc.querySelector('[data-ct-forms="ev-b2"]'), 'بلوک برای رویداد بدون فرم');
    assert.match(app.doc.querySelector('[data-ct-forms="ev-b2"]').textContent, /هنوز فرمی به این رویداد وصل نیست/);
    assert.equal(app.doc.querySelector('[data-ct-form-row]'), null);
    app.click('[data-ct-cancel]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-b2"]'), 'بازگشت');
    app.click('[data-ct-new]');
    await app.until(() => app.doc.querySelector('#ctf_t'), 'ویرایشگر رویداد تازه');
    assert.ok(app.doc.querySelector('[data-ct-forms="unsaved"]'), 'رویداد ذخیره‌نشده: راهنما به‌جای پیوند');
    assert.equal(app.doc.querySelector('[data-ct-form-create]'), null, 'بدون شناسه، پیوند ساخت فرم نیست');
  } finally { app.close(); }
  const noForms = await loadPanel({ role: 'manager', sec: 'events', forms, permissions: MANAGER.filter((p) => p !== 'fm_create' && p !== 'fm_responses' && p !== 'fm_export') });
  try {
    await noForms.until(() => noForms.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست مدیر');
    noForms.click('[data-ct-edit="ev-a1"]');
    await noForms.until(() => noForms.doc.querySelector('#ctf_t'), 'ویرایشگر');
    await delay(120);
    assert.equal(noForms.doc.querySelector('[data-ct-forms]'), null, 'بدون مجوز فرم‌ساز بلوک فرم‌ها نیست');
    assert.equal(noForms.calls.filter((c) => c.path === '/api/forms').length, 0, 'بدون مجوز، درخواستی به /api/forms نمی‌رود');
  } finally { noForms.close(); }
}

console.log('— H1 مالک: ویرایشگر سروری افراد روی GET/PATCH /api/owner/site-content؛ جست‌وجو، ویرایش، پیش‌نمایش، تأیید انتشار، ردیف ردشده، ۴۰۹ بدون از دست رفتن نوشته، نگهبان حذف —');
{
  const makeSite = () => ({
    people: [
      { id: 'pp-ali', n: 'علی موسوی', r: 'مدرس فن بیان', role2: '', kind: 'teacher', bio: 'ده سال تدریس', quote: '', where: 'تهران', yrs: '۱۰ سال', courses: '12', rate: '۴٫۸', tag: 'پیشنهادی', exp: ['فن بیان', 'تنفس'], links: [{ k: 'tg', v: 'alimousavi' }], photo: '', g: 'linear-gradient(135deg,#1E6FD0,#0A3A82)', form: '', formTxt: '' },
      { id: 'pp-sara', n: 'سارا کریمی', r: 'دست‌اندرکار اجرا', role2: '', kind: 'staff', bio: '', quote: '', where: '', yrs: '', courses: '0', rate: '', tag: '', exp: ['هماهنگی'], links: [], photo: '', g: '', form: '', formTxt: '' },
    ],
    partners: [],
    events: [{ id: 'ev-a1', t: 'کارگاه نگارش', when: 'پنجشنبه', tchr: 'pp-ali' }],
    articles: [],
  });
  const world = { ...makeWorld(), siteContent: makeSite() };
  const forms = [{ id: 'f-ask', name: 'پرسش از استاد', purpose: 'survey', status: 'published', fields: [{ id: 'q1' }] }];
  const app = await loadPanel({ role: 'owner', sec: 'settings', state: { setG: 'people' }, world, forms });
  try {
    await app.until(() => app.doc.querySelector('[data-pe-row="pp-ali"]'), 'فهرست افراد از GET /api/owner/site-content');
    assert.ok(app.doc.querySelector('[data-pe-row="pp-sara"]'));
    assert.match(app.doc.querySelector('#peSrvState').textContent, /۲ پروفایل .*نسخهٔ ۷/);
    assert.match(app.doc.querySelector('[data-pe-row="pp-ali"]').textContent, /۱ رویداد منتشرشده/, 'پیوند واقعی رویداد↔پروفایل در فهرست');
    app.noLeak();

    /* جست‌وجو بر پایهٔ نام/نقش/تخصص بدون درخواست تازه */
    const before = app.calls.length;
    app.type('[data-pe-q]', 'هماهنگی');
    assert.equal(app.doc.querySelector('[data-pe-row="pp-ali"]'), null, 'جست‌وجو بر پایهٔ تخصص');
    assert.ok(app.doc.querySelector('[data-pe-row="pp-sara"]'));
    app.type('[data-pe-q]', '');
    app.click('[data-pe-kind="staff"]');
    assert.equal(app.doc.querySelector('[data-pe-row="pp-ali"]'), null, 'فیلتر نوع');
    app.click('[data-pe-kind=""]');
    assert.equal(app.calls.length, before, 'جست‌وجو و فیلتر سمت مرورگر روی همان فهرست سرور است');

    /* ویرایش: فرم طراحی + پیش‌نمایش زنده + توضیح «ذخیره = انتشار فوری» */
    app.click('[data-pe-edit="pp-ali"]');
    await app.until(() => app.doc.querySelector('[data-pe-editor="pp-ali"]'), 'ویرایشگر');
    assert.match(app.doc.querySelector('[data-pe-publish-note]').textContent, /ذخیره = انتشار فوری/);
    assert.equal(app.doc.querySelector('[data-ppf="n"]').value, 'علی موسوی');
    assert.ok(app.doc.querySelector('#ppPrev .tcard'), 'پیش‌نمایش کارت');
    assert.equal(app.doc.querySelector('[data-ppstar]'), null, 'فیلدی که سرور ذخیره نمی‌کند (معرفی‌شده) در حالت سرور نیست');
    assert.equal(app.doc.querySelector('[data-ppic]'), null, 'آیکون کارت هم ذخیره نمی‌شود');
    assert.equal(app.doc.querySelector('[data-pplkv="other"]'), null, 'نوع پیوند «دیگر» را سرور می‌اندازد؛ پیشنهاد نمی‌شود');
    assert.match(app.doc.querySelector('[data-pe-editor] .ppsec:last-of-type, [data-pe-editor]').textContent, /کارگاه نگارش/, 'رویداد وصل‌شده در ویرایشگر');
    await app.until(() => app.doc.querySelector('[data-ppform="f-ask"]'), 'فرم‌های سروری (/api/forms) در انتخاب فرم پیوست');
    app.type('[data-ppf="r"]', 'مدرس ارشد فن بیان');
    assert.match(app.doc.querySelector('#ppPrev').textContent, /مدرس ارشد فن بیان/, 'پیش‌نمایش زنده');
    app.click('[data-ppform="f-ask"]');
    await app.until(() => app.doc.querySelector('[data-ppform=""]'), 'فرم وصل شد');

    /* انصراف نوشته را نگه نمی‌دارد؛ ولی ذخیره فقط با تأیید انجام می‌شود */
    app.dialogs.length = 0;
    app.click('[data-pe-save]');
    await app.until(() => app.world.patches === 1, 'PATCH پس از تأیید');
    assert.equal(app.dialogs.length, 1);
    assert.match(app.dialogs[0][1], /بلافاصله در سایت عمومی منتشر می‌شود/, 'پیش از ذخیره توضیح انتشار فوری');
    const patch = app.calls.filter((c) => c.path === '/api/owner/site-content' && c.method === 'PATCH').pop();
    assert.deepEqual(Object.keys(patch.body).sort(), ['content', 'expected_version'], 'بدنهٔ دقیق قرارداد');
    assert.equal(patch.body.expected_version, 7);
    assert.equal(patch.headers['X-CSRF-Token'], 'owner-csrf', 'CSRF مالک');
    assert.deepEqual(Object.keys(patch.body.content), ['people'], 'فقط دستهٔ people فرستاده می‌شود');
    const sent = patch.body.content.people.find((p) => p.id === 'pp-ali');
    assert.equal(sent.r, 'مدرس ارشد فن بیان');
    assert.equal(sent.form, 'f-ask');
    assert.equal(sent.kind, 'teacher');
    for (const key of Object.keys(sent)) assert.ok(['id', 'n', 'ini', 'r', 'role2', 'kind', 'bio', 'quote', 'where', 'yrs', 'courses', 'rate', 'tag', 'exp', 'links', 'photo', 'g', 'form', 'formTxt'].includes(key), `فیلد غیرمجاز فرستاده شد: ${key}`);
    assert.equal(patch.body.content.people.length, 2, 'ردیف دیگر دست‌نخورده می‌ماند');
    await app.until(() => /نسخهٔ ۸ سرور ذخیره شد/.test(app.doc.querySelector('#peSrvState').textContent), 'پیام موفقیت فقط پس از پاسخ سرور');
    assert.equal(app.doc.querySelector('[data-pe-editor]'), null, 'ویرایشگر پس از موفقیت بسته می‌شود');
    assert.match(app.doc.querySelector('[data-pe-row="pp-ali"]').textContent, /مدرس ارشد فن بیان/);

    /* ترتیب: یک PATCH با همان نسخهٔ تازه */
    app.click('[data-pe-down="pp-ali"]');
    await app.until(() => app.world.patches === 2, 'PATCH ترتیب');
    assert.deepEqual(app.world.siteContent.people.map((p) => p.id), ['pp-sara', 'pp-ali']);
    assert.equal(app.calls.filter((c) => c.method === 'PATCH').pop().body.expected_version, 8);

    /* شخص تازه: تأیید صریح؛ انصراف از تأیید = هیچ درخواستی */
    app.click('[data-pe-new]');
    await app.until(() => app.doc.querySelector('[data-pe-editor="new"]'), 'ویرایشگر شخص تازه');
    app.dialogs.length = 0;
    app.click('[data-pe-save]');
    await delay(30);
    assert.equal(app.world.patches, 2, 'بدون نام، درخواستی نمی‌رود');
    app.type('[data-ppf="n"]', 'مدرس آزمایشی تازه');
    app.type('[data-ppf="exp"]', 'نجوم، رصد');
    app.window.confirm = (m) => { app.dialogs.push(['confirm', String(m)]); return false; };
    app.click('[data-pe-save]');
    await delay(30);
    assert.equal(app.world.patches, 2, 'بدون تأیید، شخص تازه منتشر نمی‌شود');
    assert.match(app.dialogs.pop()[1], /همین حالا روی سرور ذخیره و بلافاصله در سایت عمومی منتشر می‌شود/);
    assert.ok(app.doc.querySelector('[data-pe-editor="new"]'), 'نوشته پس از انصراف باقی است');
    app.window.confirm = () => true;
    app.click('[data-pe-save]');
    await app.until(() => app.world.patches === 3, 'PATCH شخص تازه');
    const created = app.world.siteContent.people.find((p) => p.n === 'مدرس آزمایشی تازه');
    assert.ok(created && /^pp-/.test(created.id), 'شناسهٔ تازه ساخته شد');
    assert.deepEqual(created.exp, ['نجوم', 'رصد']);
    await app.until(() => app.doc.querySelector(`[data-pe-row="${created.id}"]`), 'ردیف تازه در فهرست');

    /* ردیف ردشده: موفقیت کامل گزارش نمی‌شود */
    app.world.siteContent.people.push({ id: 'pp-hid', n: 'پنهان', kind: 'teacher', hidden: true });
    app.click('[data-pe-refresh]');
    await app.until(() => app.doc.querySelector('[data-pe-row="pp-hid"]'), 'ردیف غیرعمومی (شبیه‌سازی)');
    app.click('[data-pe-edit="pp-sara"]');
    await app.until(() => app.doc.querySelector('[data-pe-editor="pp-sara"]'), 'ویرایشگر');
    app.type('[data-ppf="r"]', 'هماهنگ‌کنندهٔ اجرا');
    app.click('[data-pe-save]');
    await app.until(() => app.world.patches === 4, 'PATCH');
    await app.until(() => app.doc.querySelector('[data-pe-rejected]'), 'ردیف ردشده نمایش داده می‌شود');
    assert.match(app.doc.querySelector('#peSrvState').textContent, /۱ ردیف پذیرفته و منتشر نشد/);
    assert.match(app.doc.querySelector('#peSrvState').textContent, /pp-hid/);
    assert.doesNotMatch(app.doc.querySelector('#peSrvState').textContent, /همین حالا در سایت دیده می‌شود/, 'جملهٔ موفقیت کامل نیست');
    assert.equal(app.doc.querySelector('[data-pe-rejected]').getAttribute('data-state'), 'warn');
    assert.equal(app.doc.querySelector('[data-pe-editor]'), null, 'ردیف ویرایش‌شدهٔ خودِ مالک پذیرفته شده بود؛ ویرایشگر بسته شد');

    /* ۴۰۹: نوشتهٔ مالک حفظ می‌شود، فهرست تازه می‌شود، تطبیق فیلدها و ذخیرهٔ دوباره */
    app.click('[data-pe-edit="pp-ali"]');
    await app.until(() => app.doc.querySelector('[data-pe-editor="pp-ali"]'), 'ویرایشگر');
    app.type('[data-ppf="bio"]', 'زندگی‌نامهٔ تازهٔ من');
    /* شخص دیگری هم‌زمان سرور را عوض می‌کند */
    app.world.siteContent.people.find((p) => p.id === 'pp-ali').where = 'شیراز';
    app.world.version += 1;
    app.click('[data-pe-save]');
    await app.until(() => app.doc.querySelector('[data-pe-conflict]'), 'پنل تعارض نسخه');
    assert.match(app.doc.querySelector('#peSrvState').textContent, /نوشته‌هایتان همین‌جا مانده/);
    assert.equal(app.doc.querySelector('[data-ppf="bio"]').value, 'زندگی‌نامهٔ تازهٔ من', 'نوشتهٔ مالک پس از ۴۰۹ از دست نرفته');
    assert.ok(app.doc.querySelector('[data-pe-diff="where"]'), 'تفاوتِ تغییرِ دیگری (محل) نمایش داده می‌شود');
    assert.match(app.doc.querySelector('[data-pe-diff="where"]').textContent, /روی سرور تغییر کرده/);
    assert.ok(app.doc.querySelector('[data-pe-diff="bio"]'), 'تفاوتِ نوشتهٔ خودم');
    app.click('[data-pe-take="where"]');
    await delay(20);
    assert.equal(app.doc.querySelector('[data-ppf="where"]').value, 'شیراز', 'گرفتن مقدار سرور برای یک فیلد');
    assert.equal(app.doc.querySelector('[data-pe-diff="where"]'), null);
    app.click('[data-pe-save]');
    await app.until(() => app.world.patches === 5, 'ذخیرهٔ دوباره روی نسخهٔ تازه');
    const again = app.calls.filter((c) => c.method === 'PATCH').pop();
    assert.equal(again.body.expected_version, 12, 'نسخهٔ تازه پس از بارگذاری مجدد');
    const ali = again.body.content.people.find((p) => p.id === 'pp-ali');
    assert.equal(ali.bio, 'زندگی‌نامهٔ تازهٔ من');
    assert.equal(ali.where, 'شیراز');
    await app.until(() => !app.doc.querySelector('[data-pe-editor]'), 'بسته شد');

    /* حذفِ شخصِ وصل‌شده: سرور ۴۲۲ reference_in_use می‌دهد و پیام رویداد را نام می‌برد؛ فهرست دست‌نخورده */
    const patchesBefore = app.calls.filter((c) => c.method === 'PATCH').length;
    app.click('[data-pe-del="pp-ali"]');
    await app.until(() => app.calls.filter((c) => c.method === 'PATCH').length === patchesBefore + 1, 'PATCH حذف');
    await app.until(() => /حذف انجام نشد/.test(app.doc.querySelector('#peSrvState').textContent), 'پیام نگهبان ارجاع');
    assert.match(app.doc.querySelector('#peSrvState').textContent, /کارگاه نگارش/);
    assert.ok(app.doc.querySelector('[data-pe-row="pp-ali"]'));
    assert.ok(app.world.siteContent.people.some((p) => p.id === 'pp-ali'));
    /* حذف شخص آزاد پس از تأیید */
    app.click(`[data-pe-del="${created.id}"]`);
    await app.until(() => !app.world.siteContent.people.some((p) => p.id === created.id), 'حذف شخص آزاد');
    app.noLeak();
  } finally { app.close(); }

  /* مدیر (غیرمالک): تب افراد ویرایشگر ندارد و هیچ درخواستی به API مالک نمی‌رود */
  const mgr = await loadPanel({ role: 'manager', sec: 'settings', state: { setG: 'people' }, world: { ...makeWorld(), siteContent: makeSite() } });
  try {
    await delay(150);
    assert.equal(mgr.doc.querySelector('#peList'), null, 'بدون نشست مالک ویرایشگری نیست');
    assert.equal(mgr.calls.filter((c) => c.path === '/api/owner/site-content').length, 0, 'مدیر به API مالک درخواست نمی‌فرستد');
  } finally { mgr.close(); }
}

console.log('— مرحلهٔ ۲: انتخاب‌گر شناسه‌ای مدرس/نهاد در رویداد و نویسنده در مطلب؛ فهرست از /api/public/site-content؛ جست‌وجو، Enter، شناسهٔ ناموجود، ذخیره و بازخوانی —');
{
  const site = () => ({
    people: [
      { id: 'pp-ali', n: 'علی موسوی', r: 'مدرس فن بیان', kind: 'teacher', exp: ['فن بیان', 'تنفس'], g: '' },
      { id: 'pp-sara', n: 'سارا کریمی', r: 'دست‌اندرکار اجرا', kind: 'staff', exp: ['هماهنگی'], g: '' },
      { id: 'pp-hid', n: 'پنهان', r: 'مدرس', kind: 'teacher', hidden: true },
    ],
    partners: [{ id: 'pt-1', n: 'دانشگاه آزمایشی', type: 'دانشگاهی', collab: 'میزبانی', focus: ['سالن'] }],
    events: [], articles: [],
  });
  const world = { ...makeWorld(), siteContent: site(), articles: [
    { id: 'ar-1', t: 'یادداشت سردبیر', cat: 'یادداشت', who: '', tchr: '', lead: 'لید', body: ['بند'], status: 'draft', updated_at: '2026-10-20T10:00:00+00:00', created_at: '2026-10-20T10:00:00+00:00' },
  ] };
  world.events[1].tchr = 'pp-ghost'; /* ردیف قدیمی با شناسهٔ آویزان */
  const app = await loadPanel({ role: 'owner', sec: 'events', world });
  try {
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست');
    const ownerCalls0 = app.calls.filter((c) => c.path === '/api/owner/site-content').length;
    app.click('[data-ct-edit="ev-a1"]');
    await app.until(() => app.doc.querySelector('[data-ct-pick="tchr"]') && app.doc.querySelector('[data-ct-pick="partnerId"]'), 'دو انتخاب‌گر در ویرایشگر رویداد');
    await app.until(() => app.doc.querySelector('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-ali"]'), 'فهرست افراد از سرور عمومی');
    assert.equal(app.calls.filter((c) => c.path === '/api/public/site-content').length, 1, 'یک درخواست برای هر دو انتخاب‌گر');
    assert.equal(app.calls.filter((c) => c.path === '/api/owner/site-content').length, ownerCalls0, 'انتخاب‌گر به API مالک نیاز ندارد');
    assert.equal(app.doc.querySelector('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-hid"]'), null, 'ردیف غیرعمومی پیشنهاد نمی‌شود');
    assert.ok(app.doc.querySelector('[data-ct-pick-empty="tchr"]'), 'حالت «مدرسی وصل نیست»');
    assert.ok(app.doc.querySelector('[data-ct-pick-manage="people"]'), 'مالک: میان‌بر مدیریت افراد');

    /* جست‌وجو با تخصص + Enter = انتخاب نخستین نتیجه؛ بدون درخواست تازه */
    const calls0 = app.calls.length;
    app.type('[data-ct-pick-q="tchr"]', 'هماهنگی');
    assert.equal(app.doc.querySelector('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-ali"]'), null, 'فیلتر تخصص');
    assert.ok(app.doc.querySelector('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-sara"]'));
    assert.equal(app.doc.activeElement, app.doc.querySelector('[data-ct-pick-q="tchr"]'), 'فوکوس روی جست‌وجو می‌ماند');
    app.doc.querySelector('[data-ct-pick-q="tchr"]').dispatchEvent(new app.window.KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }));
    await delay(20);
    assert.ok(app.doc.querySelector('[data-ct-pick-current="pp-sara"]'), 'Enter نخستین نتیجه را انتخاب کرد');
    assert.equal(app.calls.length, calls0, 'جست‌وجو و انتخاب سمت مرورگر است');
    assert.match(app.doc.querySelector('#ctPreview').textContent, /مدرس: سارا کریمی/, 'پیش‌نمایش کارت نام پروفایل را نشان می‌دهد');
    /* انتخاب با کلیک (جایگزینی) و نهاد */
    app.type('[data-ct-pick-q="tchr"]', '');
    app.click('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-ali"]');
    await delay(20);
    assert.ok(app.doc.querySelector('[data-ct-pick-current="pp-ali"]'));
    assert.ok(app.doc.querySelector('[data-ct-pick-current="pp-ali"] a[href="person.html?id=pp-ali"]'), 'پیوند صفحهٔ عمومی همان شناسه');
    app.click('[data-ct-pick-set="partnerId"][data-ct-pick-id="pt-1"]');
    await delay(20);
    assert.ok(app.doc.querySelector('[data-ct-pick-current="pt-1"]'));
    assert.match(app.doc.querySelector('#ctPreview').textContent, /با همکاری دانشگاه آزمایشی/);
    app.click('[data-ct-save]');
    await app.until(() => app.world.events.find((e) => e.id === 'ev-a1').tchr === 'pp-ali', 'ذخیره با شناسه');
    const put = app.calls.filter((c) => c.method === 'PUT' && c.path === '/api/admin/content/events/ev-a1').pop();
    assert.equal(put.body.record.tchr, 'pp-ali'); assert.equal(put.body.record.partnerId, 'pt-1');
    await app.until(() => /مدرس: علی موسوی/.test((app.doc.querySelector('[data-ct-row="ev-a1"]') || {}).textContent || ''), 'ردیف فهرست وضعیت پیوند را نشان می‌دهد');
    assert.match(app.doc.querySelector('[data-ct-row="ev-a1"]').textContent, /نهاد: دانشگاه آزمایشی/);
    /* بازخوانی: مقدار ذخیره‌شده دوباره به‌صورت کارت وصل‌شده می‌آید */
    app.click('[data-ct-edit="ev-a1"]');
    await app.until(() => app.doc.querySelector('[data-ct-pick-current="pp-ali"]'), 'پس از بازخوانی وصل است');
    app.click('[data-ct-cancel]');

    /* شناسهٔ ناموجود روی ردیف قدیمی: هشدار، ذخیره بدون درخواست متوقف می‌شود، با برداشتن پیوند ذخیره می‌شود */
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-b2"]'), 'فهرست');
    assert.match(app.doc.querySelector('[data-ct-row="ev-b2"]').textContent, /مدرس ناموجود: pp-ghost/);
    app.click('[data-ct-edit="ev-b2"]');
    await app.until(() => app.doc.querySelector('[data-ct-pick-invalid]'), 'هشدار شناسهٔ ناموجود');
    const puts = app.calls.filter((c) => c.method === 'PUT').length;
    app.click('[data-ct-save]');
    await delay(60);
    assert.equal(app.calls.filter((c) => c.method === 'PUT').length, puts, 'با شناسهٔ ناموجود درخواستی نمی‌رود');
    assert.match(app.doc.querySelector('[data-ct-err="tchr"]').textContent, /وجود ندارد/, 'خطای همان فیلد');
    app.click('[data-ct-pick-clear="tchr"]');
    await delay(20);
    assert.ok(app.doc.querySelector('[data-ct-pick-empty="tchr"]'));
    app.click('[data-ct-save]');
    await app.until(() => app.calls.filter((c) => c.method === 'PUT').length === puts + 1, 'ذخیره پس از برداشتن');
    assert.equal(app.calls.filter((c) => c.method === 'PUT').pop().body.record.tchr, '', 'پاک‌کردن پیوند');

    /* سرور هم مرجع نهایی است: اگر فهرست مرورگر کهنه باشد، ۴۲۲ unknown_reference روی همان فیلد می‌نشیند */
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-b2"]'), 'فهرست');
    app.click('[data-ct-edit="ev-b2"]');
    await app.until(() => app.doc.querySelector('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-sara"]'), 'انتخاب‌گر');
    app.click('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-sara"]');
    await delay(20);
    app.world.siteContent.people = app.world.siteContent.people.filter((p) => p.id !== 'pp-sara'); /* حذف هم‌زمان روی سرور */
    app.click('[data-ct-save]');
    await app.until(() => /وجود ندارد/.test((app.doc.querySelector('[data-ct-err="tchr"]') || {}).textContent || ''), 'خطای سرور روی فیلد مدرس');
    app.click('[data-ct-cancel]');

    /* مطلب: نویسندهٔ پروفایلی + نام میهمان آزاد */
    app.click('[data-ct-kind="articles"]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ar-1"]'), 'فهرست مطالب');
    app.click('[data-ct-edit="ar-1"]');
    await app.until(() => app.doc.querySelector('[data-ct-pick="tchr"]'), 'انتخاب‌گر نویسنده');
    assert.equal(app.doc.querySelector('[data-ct-pick="partnerId"]'), null, 'مطلب نهاد ندارد');
    assert.ok(app.doc.querySelector('#ctf_who'), 'نام میهمان آزاد باقی است');
    await app.until(() => app.doc.querySelector('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-ali"]'), 'فهرست');
    app.click('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-ali"]');
    await delay(20);
    assert.match(app.doc.querySelector('#ctPreview').textContent, /علی موسوی/);
    app.click('[data-ct-save]');
    await app.until(() => app.world.articles[0].tchr === 'pp-ali', 'نویسندهٔ پروفایلی ذخیره شد');
    await app.until(() => /نویسنده: علی موسوی/.test((app.doc.querySelector('[data-ct-row="ar-1"]') || {}).textContent || ''), 'ردیف مطلب نویسندهٔ پروفایلی را نشان می‌دهد');
    app.noLeak();
  } finally { app.close(); }

  /* مدیر با ev_create: همان انتخاب‌گر از منبع عمومی، بدون API مالک و بدون میان‌بر مدیریت افراد */
  const mgr = await loadPanel({ role: 'manager', sec: 'events', world: { ...makeWorld(), siteContent: site() } });
  try {
    await mgr.until(() => mgr.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست مدیر');
    mgr.click('[data-ct-edit="ev-a1"]');
    await mgr.until(() => mgr.doc.querySelector('[data-ct-pick-set="tchr"][data-ct-pick-id="pp-ali"]'), 'انتخاب‌گر برای مدیر');
    assert.equal(mgr.calls.filter((c) => c.path === '/api/owner/site-content').length, 0);
    assert.equal(mgr.doc.querySelector('[data-ct-pick-manage]'), null, 'مدیر میان‌بر مدیریت افراد ندارد');
  } finally { mgr.close(); }
}

console.log('— B20 ممیزی: بدنهٔ مطلب بلوکی (بند/تیتر/تصویر/فهرست) با همان API محتوا؛ مطلب قدیمیِ body-فقط بند می‌شود؛ ۴۲۲ روی بلوک‌ها؛ جابه‌جایی و حذف —');
{
  const world = { ...makeWorld(), articles: [
    { id: 'ar-1', t: 'یادداشت سردبیر', cat: 'یادداشت', who: '', tchr: '', lead: 'لید', body: ['بند نخست', 'بند دوم'], status: 'draft', updated_at: '2026-10-20T10:00:00+00:00', created_at: '2026-10-20T10:00:00+00:00' },
  ] };
  const app = await loadPanel({ role: 'owner', sec: 'events', world });
  try {
    await app.until(() => app.doc.querySelector('[data-ct-kind="articles"]'), 'زبانهٔ مطالب');
    app.click('[data-ct-kind="articles"]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ar-1"]'), 'فهرست مطالب');
    app.click('[data-ct-edit="ar-1"]');
    await app.until(() => app.doc.querySelector('[data-ct-blocks]'), 'ویرایشگر بلوکی');
    assert.equal(app.doc.querySelector('#ctf_body'), null, 'متن آزاد قدیمی جای خود را به بلوک‌ها داده');
    const rows = app.doc.querySelectorAll('[data-ct-block-row]');
    assert.equal(rows.length, 1, 'body قدیمی یک بلوک «بند» می‌شود');
    assert.equal(rows[0].getAttribute('data-ct-block-type'), 'p');
    assert.equal(app.doc.querySelector('[data-ct-block="0"][data-ct-block-field="x"]').value, 'بند نخست\n\nبند دوم', 'بندها با خط خالی در یک جعبه');

    /* افزودن تیتر، تصویر و فهرست از پالت؛ ترتیب با دکمه‌های بالا/پایین */
    app.click('[data-ct-block-add="h"]');
    await app.until(() => app.doc.querySelector('[data-ct-block="1"][data-ct-block-field="x"]'), 'بلوک تیتر');
    assert.equal(app.doc.activeElement, app.doc.querySelector('[data-ct-block="1"][data-ct-block-field="x"]'), 'فوکوس روی بلوک تازه');
    app.type('[data-ct-block="1"][data-ct-block-field="x"]', 'عنوان بخش');
    app.click('[data-ct-block-move="1"][data-ct-block-dir="-1"]');
    await app.until(() => app.doc.querySelector('[data-ct-block-row="0"]').getAttribute('data-ct-block-type') === 'h', 'تیتر بالا رفت');
    app.click('[data-ct-block-add="img"]');
    await app.until(() => app.doc.querySelector('[data-ct-block="2"][data-ct-block-field="src"]'), 'بلوک تصویر');
    assert.ok(app.doc.querySelector('[data-ct-image="block:2"]'), 'بارگذاری تصویر بلوک از همان مسیر رسانهٔ سرور');
    app.type('[data-ct-block="2"][data-ct-block-field="src"]', 'javascript:alert(1)');
    app.type('[data-ct-block="2"][data-ct-block-field="cap"]', 'زیرنویس');
    app.click('[data-ct-block-add="ul"]');
    await app.until(() => app.doc.querySelector('[data-ct-block="3"][data-ct-block-field="x"]'), 'بلوک فهرست');
    app.type('[data-ct-block="3"][data-ct-block-field="x"]', 'یک\nدو');
    app.click('[data-ct-block-add="hr"]');
    await app.until(() => app.doc.querySelectorAll('[data-ct-block-row]').length === 5, 'جداکننده');

    /* سرور نشانی ناامن تصویر را رد می‌کند → خطا روی بلوک‌ها، چیزی ذخیره نشد، نوشته‌ها می‌مانند */
    const putsBefore = app.calls.filter((c) => c.method === 'PUT').length;
    app.click('[data-ct-save]');
    await app.until(() => /تصویر معتبر نیست/.test((app.doc.querySelector('[data-ct-err="blocks"]') || {}).textContent || ''), 'خطای ۴۲۲ روی بلوک‌ها');
    const badPut = app.calls.filter((c) => c.method === 'PUT').pop();
    assert.equal(app.calls.filter((c) => c.method === 'PUT').length, putsBefore + 1);
    assert.deepEqual(badPut.body.record.blocks.map((b) => b.ty), ['h', 'p', 'p', 'img', 'ul', 'hr'], 'بند چندپاراگرافی به چند بلوک p شکسته می‌شود');
    assert.deepEqual(badPut.body.record.body, ['بند نخست', 'بند دوم'], 'body از بندهای متنی مشتق می‌شود');
    assert.deepEqual(app.world.articles[0].body, ['بند نخست', 'بند دوم']);
    assert.equal(app.world.articles[0].blocks, undefined, 'چیزی ذخیره نشد');
    assert.equal(app.doc.querySelector('[data-ct-block="1"][data-ct-block-field="x"]').value, 'بند نخست\n\nبند دوم', 'نوشته‌ها پس از خطا باقی‌اند');

    /* اصلاح نشانی، حذف جداکننده با تأیید و ذخیرهٔ موفق */
    app.type('[data-ct-block="2"][data-ct-block-field="src"]', '/api/public/media/med-77');
    assert.equal((app.doc.querySelector('[data-ct-err="blocks"]') || {}).getAttribute('style'), null, 'با تایپ، خطا پاک می‌شود');
    app.click('[data-ct-block-del="4"]');
    await app.until(() => app.doc.querySelectorAll('[data-ct-block-row]').length === 4, 'جداکننده برداشته شد');
    app.click('[data-ct-save]');
    await app.until(() => Array.isArray(app.world.articles[0].blocks), 'ذخیره شد');
    assert.deepEqual(app.world.articles[0].blocks, [
      { ty: 'h', x: 'عنوان بخش', lv: 2 }, { ty: 'p', x: 'بند نخست' }, { ty: 'p', x: 'بند دوم' },
      { ty: 'img', src: '/api/public/media/med-77', cap: 'زیرنویس' }, { ty: 'ul', x: 'یک\nدو' },
    ]);
    app.noLeak();

    /* بازگشایی: بلوک‌های ذخیره‌شده همان‌طور برمی‌گردند (بدون ادغام دوباره با body) */
    await app.until(() => app.doc.querySelector('[data-ct-row="ar-1"]'), 'فهرست پس از ذخیره');
    app.click('[data-ct-edit="ar-1"]');
    await app.until(() => app.doc.querySelectorAll('[data-ct-block-row]').length === 5, 'پنج بلوک ذخیره‌شده');
    assert.deepEqual([...app.doc.querySelectorAll('[data-ct-block-row]')].map((r) => r.getAttribute('data-ct-block-type')), ['h', 'p', 'p', 'img', 'ul']);
  } finally { app.close(); }
}

console.log('— مرحلهٔ ۳: پروندهٔ کاربر U4/U5؛ ثبت‌نام‌های صفحه‌بندی‌شده، جزئیات از form_snapshot با ماسک، مالی فقط با finance، اعلان‌های همین حساب با scope/delivery_state/has_bale_identity —');
{
  const REG1 = 'a1a1a1a1-1111-4222-8333-444444444401', REG2 = 'a1a1a1a1-1111-4222-8333-444444444402';
  const openFile = async (app) => {
    await section(app, 'users');
    if (app.doc.querySelector('[data-uback]') && !app.doc.querySelector('[data-users-panel]')) app.click('[data-uback]');
    await app.until(() => app.doc.querySelector(`[data-user-open="${ACC}"]`), 'فهرست کاربران');
    app.click(`[data-user-open="${ACC}"]`);
    await app.until(() => app.doc.querySelector('[data-user-detail]') && app.doc.querySelector(`[data-uf-reg="${REG1}"]`), 'پرونده + فهرست ثبت‌نام‌ها از API اختصاصی');
  };
  /* مالک (با finance) */
  const app = await loadPanel({ role: 'owner', sec: 'users' });
  try {
    await openFile(app);
    assert.ok(app.calls.some((c) => c.path === `/api/admin/users/${ACC}/registrations?limit=20&offset=0`), 'فهرست ثبت‌نام‌ها از /registrations صفحه‌بندی‌شده');
    assert.equal(app.doc.querySelectorAll('[data-uf-reg]').length, 2, 'دو ثبت‌نام');
    assert.match(app.body(), /نشست کتاب/); assert.match(app.body(), /فهرست انتظار/); assert.match(app.body(), /حاضر/);
    assert.equal(app.calls.filter((c) => c.path.includes('/notifications')).length, 0, 'اعلان‌ها تا باز شدن زبانه خوانده نمی‌شوند');
    app.noLeak();
    /* جزئیات */
    app.click(`[data-uf-reg="${REG1}"]`);
    await app.until(() => app.doc.querySelector('[data-uf-reg-detail]') && app.doc.querySelector('[data-uf-answers]'), 'جزئیات ثبت‌نام');
    assert.ok(app.calls.some((c) => c.path === `/api/admin/users/${ACC}/registrations/${REG1}`), 'جزئیات از مسیر همین حساب');
    const detail = app.doc.querySelector('[data-uf-reg-detail]');
    assert.equal(detail.getAttribute('data-uf-finance'), '1');
    assert.match(detail.textContent, /نام و نام خانوادگی/); assert.match(detail.textContent, /وعدهٔ غذایی[\s\S]*گیاهی/);
    assert.equal(app.doc.querySelectorAll('[data-uf-masked]').length, 2, 'دو پاسخ ماسک‌شده (همراه + کد ملی)');
    assert.match(detail.textContent, /•••••••4321/, 'چهار رقم پایانی همراه فقط به‌صورت راهنما');
    assert.doesNotMatch(detail.textContent.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, ''), /09\d{9}|\d{10}|[۰-۹]{10}/, 'هیچ شمارهٔ کامل یا کد ملی (جز شناسهٔ UUID پاسخ)');
    assert.match(detail.textContent, /همراه یکم/); assert.match(detail.textContent, /حضور ثبت نشده/);
    assert.match(detail.textContent, /کارت‌به‌کارت/); assert.match(detail.textContent, /۱,۲۰۰,۰۰۰ ریال/); assert.match(detail.textContent, /TRX-778899/, 'مالک با finance مبلغ و تراکنش را می‌بیند');
    assert.equal(app.doc.querySelector('[data-uf-finance-hidden]'), null);
    assert.match(detail.textContent, /بارگذاری شده · بررسی: تأیید شد/); assert.match(detail.textContent, /حاضر · /); assert.match(detail.textContent, /ثبت‌کننده: ربات/);
    assert.match(detail.textContent, /نسخهٔ ۳/, 'نسخهٔ فرم از snapshot');
    app.noLeak();
    app.click('[data-uf-reg-back]');
    await app.until(() => app.doc.querySelector(`[data-uf-reg="${REG2}"]`), 'بازگشت به فهرست ثبت‌نام‌ها');
    app.click(`[data-uf-reg="${REG2}"]`);
    await app.until(() => app.doc.querySelector('[data-uf-reg-detail]') && /رکورد پرداخت ندارد/.test(app.body()), 'ثبت‌نام رایگان بدون رکورد پرداخت');
    /* اعلان‌ها */
    app.click('[data-uf-tab="notifs"]');
    await app.until(() => app.doc.querySelectorAll('[data-uf-notif]').length === 3, 'سه اعلان همین حساب');
    assert.ok(app.calls.some((c) => c.path === `/api/admin/users/${ACC}/notifications?limit=20&offset=0`), 'از مسیر اختصاصی حساب، نه صف عمومی');
    assert.equal(app.calls.filter((c) => c.path.startsWith('/api/admin/notifications')).length, 0, 'صف عمومی اعلان‌ها خوانده نشد');
    const states = [...app.doc.querySelectorAll('[data-uf-notif]')].map((el) => el.getAttribute('data-uf-delivery'));
    assert.deepEqual(states, ['delivered', 'retrying', 'failed']);
    const nb = app.doc.querySelector('[data-uf-notifs]').textContent;
    assert.match(nb, /تحویل‌شده/); assert.match(nb, /در حال تلاش دوباره/); assert.match(nb, /ناموفق/); assert.match(nb, /همگانی/); assert.match(nb, /شخصی/); assert.match(nb, /بدون شناسهٔ بله/); assert.match(nb, /bale_timeout/);
    assert.equal(app.doc.querySelectorAll('[data-uf-notif] .tag.ok').length, 1, 'فقط ردیف تحویل‌شده سبز است؛ در صف ≠ تحویل');
    assert.equal(app.doc.querySelector('[data-uf-notif] button'), null, 'بدون دکمهٔ ارسال/تلاش دوباره');
    app.noLeak();
    /* زبانهٔ کارتابل هنوز هست */
    app.click('[data-uf-tab="reviews"]');
    await app.until(() => /درخواست پروفایل یا فیشی/.test(app.body()), 'زبانهٔ کارتابل');

    /* C5: تاریخچهٔ حساب — فقط مالک؛ فراخوانی جدا و فقط هنگام باز کردن زبانه؛ فیلتر target_id سمت سرور؛ خطا/تلاش دوباره/خالی/صفحه‌بندی */
    assert.equal(app.world.auditCalls || 0, 0, 'تا زبانه باز نشود هیچ تماسی با مسیر ممیزی مالک نیست');
    app.world.auditByTarget = { [ACC]: [
      { id: 'au-1', created_at: '2026-10-22T10:00:00+00:00', actor_kind: 'owner', actor_id: 'owner-01', actor_role: 'owner', action: 'role.set', target_type: 'account', target_id: ACC, outcome: 'ok', details: { previous_role: null, role: 'manager' } },
      { id: 'au-2', created_at: '2026-10-21T10:00:00+00:00', actor_kind: 'owner', actor_id: 'owner-01', actor_role: 'owner', action: 'manager_credentials.set', target_type: 'account', target_id: ACC, outcome: 'ok', details: { username: 'm.one', replaced: false } },
    ], 'other-acc': [
      { id: 'au-9', created_at: '2026-10-20T10:00:00+00:00', actor_kind: 'owner', actor_id: 'owner-01', actor_role: 'owner', action: 'role.clear', target_type: 'account', target_id: 'other-acc', outcome: 'ok', details: {} },
    ] };
    app.world.auditFailOnce = true;
    assert.ok(app.doc.querySelector('[data-uf-tab="hist"]'), 'زبانهٔ تاریخچه برای مالک');
    app.click('[data-uf-tab="hist"]');
    await app.until(() => app.doc.querySelector('[data-uf-hist-refresh]') && /دریافت نشد|در دسترس نیست|خطا/.test(app.doc.querySelector('[data-uf-hist-list]').textContent), 'خطای سرور + دکمهٔ تلاش دوباره');
    const histCall = app.calls.filter((c) => c.path.startsWith('/api/owner/audit')).pop();
    assert.ok(histCall && histCall.path.includes('target_type=account') && histCall.path.includes(`target_id=${ACC}`), 'فیلتر دقیق هدف در خود درخواست، نه در مرورگر');
    assert.equal(app.doc.querySelectorAll('[data-uf-hist]').length, 0);
    app.click('[data-uf-hist-refresh]');
    await app.until(() => app.doc.querySelectorAll('[data-uf-hist]').length === 2, 'دو ردیف تاریخچهٔ همین حساب');
    const hl = app.doc.querySelector('[data-uf-hist-list]').textContent;
    assert.match(hl, /تعیین نقش/); assert.match(hl, /تعریف ورود مدیر/); assert.match(hl, /m\.one/);
    assert.doesNotMatch(hl, /برداشتن نقش/, 'ردیف حساب دیگر دیده نمی‌شود');
    assert.equal(app.doc.querySelector('[data-uf-hist-page]'), null, 'بدون صفحهٔ بعد وقتی has_more=false');
    app.noLeak();
    /* حساب بدون سابقه: پیام خالی صادقانه */
    app.world.auditByTarget[ACC] = [];
    app.click('[data-uf-hist-refresh]');
    await app.until(() => /ثبت نشده است/.test(app.doc.querySelector('[data-uf-hist-list]').textContent), 'حالت خالی');
    assert.equal(app.doc.querySelectorAll('[data-uf-hist]').length, 0);
  } finally { app.close(); }
  /* مدیر us_view بدون finance */
  const mgr = await loadPanel({ role: 'manager', sec: 'users' });
  try {
    await openFile(mgr);
    mgr.click(`[data-uf-reg="${REG1}"]`);
    await mgr.until(() => mgr.doc.querySelector('[data-uf-reg-detail][data-uf-finance="0"]'), 'جزئیات برای مدیر بدون finance');
    const d = mgr.doc.querySelector('[data-uf-reg-detail]');
    assert.match(d.textContent, /فیش تأییدشده/); assert.match(d.textContent, /کارت‌به‌کارت/);
    assert.doesNotMatch(d.textContent, /TRX-778899|۱,۲۰۰,۰۰۰|ریال/, 'مبلغ و تراکنش برای مدیر بدون finance نمایش داده نمی‌شود');
    assert.ok(mgr.doc.querySelector('[data-uf-finance-hidden]'), 'یادداشت صادقانهٔ «فقط با مجوز مالی»');
    assert.equal(mgr.doc.querySelectorAll('[data-uf-masked]').length, 2);
    mgr.noLeak();
    /* خطای سرور + تلاش دوباره؛ شناسهٔ پاسخ حساب دیگر → پیدا نشد */
    mgr.click('[data-uf-reg-back]');
    await mgr.until(() => mgr.doc.querySelector(`[data-uf-reg="${REG2}"]`), 'فهرست');
    const el = mgr.doc.querySelector(`[data-uf-reg="${REG2}"]`); el.setAttribute('data-uf-reg', 'b2b2b2b2-1111-4222-8333-444444444499');
    mgr.click('[data-uf-reg="b2b2b2b2-1111-4222-8333-444444444499"]');
    await mgr.until(() => /پیدا نشد/.test(mgr.body()), 'پاسخ حساب دیگر: فقط پیام پیدا نشد');
    assert.equal(mgr.doc.querySelector('[data-uf-answers]'), null, 'هیچ پاسخی از حساب دیگر نشت نکرد');
    /* C5: مدیر زبانهٔ تاریخچه ندارد و هیچ تماسی با مسیر مالک نمی‌گیرد */
    assert.equal(mgr.doc.querySelector('[data-uf-tab="hist"]'), null, 'مدیر زبانهٔ تاریخچهٔ حساب ندارد');
    assert.equal(mgr.calls.filter((c) => c.path.startsWith('/api/owner/')).length, 0, 'مدیر هیچ درخواستی به مسیرهای مالک نمی‌فرستد');
  } finally { mgr.close(); }
  /* خطای فهرست ثبت‌نام‌ها + تلاش دوباره */
  const bad = await loadPanel({ role: 'owner', sec: 'users', regsFail: true });
  try {
    await section(bad, 'users');
    if (bad.doc.querySelector('[data-uback]') && !bad.doc.querySelector('[data-users-panel]')) bad.click('[data-uback]');
    await bad.until(() => bad.doc.querySelector(`[data-user-open="${ACC}"]`), 'فهرست');
    bad.click(`[data-user-open="${ACC}"]`);
    await bad.until(() => bad.doc.querySelector('[data-uf-regs-refresh]') && !bad.doc.querySelector('[data-uf-reg]'), 'خطای فهرست ثبت‌نام‌ها با دکمهٔ تلاش دوباره');
    assert.ok(bad.doc.querySelector('[data-user-detail]'), 'بقیهٔ پرونده با خطای یک بخش از بین نمی‌رود');
    bad.world.regsOk = true;
    bad.click('[data-uf-regs-refresh]');
    await bad.until(() => bad.doc.querySelector(`[data-uf-reg="${REG1}"]`), 'تلاش دوباره موفق');
  } finally { bad.close(); }
}

console.log('— ممیزی ۱۴۰۵/۰۸/۰۱ بخش B: قالب، تقویم شمسی و روز هفته، همگام‌سازی تاریخ/ساعت، دونقطهٔ خودکار، جلسه‌ها، فوکوس روی اولین خطا، تکثیر، پیش‌نویس محلی —');
{
  let app = await loadPanel({ role: 'owner', sec: 'events' });
  try {
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست');
    app.click('[data-ct-new]');
    await app.until(() => app.doc.querySelector('#ctf_t'), 'ویرایشگر تازه');
    /* B2: قالب فقط فیلدهای خالی را پر می‌کند و چیزی نمی‌فرستد */
    assert.ok(app.doc.querySelector('[data-ct-templates]'), 'قالب‌ها فقط برای رکورد تازه');
    app.type('#ctf_kind', 'نشست ویژه');
    const postsBefore = app.calls.filter((c) => c.method === 'POST').length;
    app.click('[data-ct-template="certified"]');
    await app.until(() => app.doc.querySelector('[data-ct-template="certified"].on'), 'قالب انتخاب شد');
    assert.equal(app.doc.querySelector('#ctf_kind').value, 'نشست ویژه', 'فیلد پرشده دست نمی‌خورد');
    assert.equal(app.doc.querySelector('#ctf_mode').value, 'حضوری', 'فیلد خالی از قالب پر شد');
    assert.ok(app.doc.querySelector('#ctf_certMin'), 'گواهی از قالب روشن شد');
    assert.equal(app.calls.filter((c) => c.method === 'POST').length, postsBefore, 'قالب هیچ درخواستی نمی‌فرستد');
    /* B7: روز هفته + همگام‌سازی شروع/پایان با تاریخ شمسی */
    app.type('#ctf_on', '1405/08/14');
    assert.match(app.doc.querySelector('[data-ct-weekday="on"]').textContent, /پنجشنبه/, 'روز هفته از تاریخ شمسی');
    assert.equal(app.doc.querySelector('#ctf_startsAt').value, '1405/08/14', 'شروع رویداد همراه تاریخ شمسی پر شد');
    assert.match(app.doc.querySelector('#ctf_when').value, /پنجشنبه ۱۴ آبان/, 'زمان به نوشتار از تاریخ پر شد');
    /* B8: ساعت با عدد خالص دونقطه می‌گیرد و به شروع می‌رود؛ متن آزاد دست‌نخورده می‌ماند */
    app.type('#ctf_time', '1030');
    assert.equal(app.doc.querySelector('#ctf_time').value, '10:30', 'دونقطهٔ خودکار');
    assert.equal(app.doc.querySelector('#ctf_startsAt').value, '1405/08/14 10:30', 'ساعت به شروع رویداد رفت');
    app.type('#ctf_time', '10 تا 13');
    assert.equal(app.doc.querySelector('#ctf_time').value, '10 تا 13', 'متن آزاد ساعت تغییر نمی‌کند');
    app.type('#ctf_on', '1405/08/21');
    assert.equal(app.doc.querySelector('#ctf_startsAt').value, '1405/08/21 10:30', 'تغییر تاریخ شمسی، تاریخ شروع را (با حفظ ساعت) جابه‌جا می‌کند');
    app.type('#ctf_startsAt', '1405/08/21 0900');
    app.doc.querySelector('#ctf_startsAt').dispatchEvent(new app.dom.window.Event('focusout', { bubbles: true }));
    assert.equal(app.doc.querySelector('#ctf_startsAt').value, '1405/08/21 09:00', 'ساعت در فیلد تاریخ‌ساعت هم با ترک قلم کامل می‌شود');
    app.type('#ctf_endsAt', '1405/08/21 12:00');
    app.type('#ctf_on', '1405/08/28');
    assert.equal(app.doc.querySelector('#ctf_startsAt').value, '1405/08/28 09:00');
    assert.equal(app.doc.querySelector('#ctf_endsAt').value, '1405/08/28 12:00', 'پایان که هم‌تاریخ شروع بود همراه می‌آید');
    /* تقویم کوچک: باز، روز، بسته */
    app.click('[data-ctdp="on"]');
    await app.until(() => app.doc.querySelector('[data-ctdp-box="on"]'), 'تقویم باز شد');
    assert.match(app.doc.querySelector('[data-ctdp-box="on"] .dphead b').textContent, /آبان ۱۴۰۵/);
    app.click('[data-ctdp-box="on"] [data-ctdp-day="5"]');
    await app.until(() => !app.doc.querySelector('[data-ctdp-box]'), 'تقویم بسته شد');
    assert.equal(app.doc.querySelector('#ctf_on').value, '1405/08/05', 'روز از تقویم با رقم لاتین نشست');
    assert.equal(app.doc.querySelector('#ctf_startsAt').value, '1405/08/05 09:00');
    /* B9: جلسه‌ها */
    app.click('[data-ct-part-add]');
    await app.until(() => app.doc.querySelector('[data-ct-part-row="0"]'), 'ردیف جلسه');
    assert.equal(app.doc.querySelector('[data-ct-part="0"][data-ct-part-field="date"]').value, '1405/08/05', 'تاریخ جلسهٔ اول از تاریخ رویداد');
    app.type('[data-ct-part="0"][data-ct-part-field="title"]', 'مقدمه');
    app.type('[data-ct-part="0"][data-ct-part-field="time"]', '0900');
    assert.equal(app.doc.querySelector('[data-ct-part="0"][data-ct-part-field="time"]').value, '09:00');
    app.click('[data-ct-part-add]');
    await app.until(() => app.doc.querySelector('[data-ct-part-row="1"]'), 'جلسهٔ دوم');
    assert.equal(app.doc.querySelector('[data-ct-part="1"][data-ct-part-field="time"]').value, '09:00', 'ساعت جلسهٔ قبلی پیشنهاد می‌شود');
    app.click('[data-ct-part-del="1"]');
    await app.until(() => !app.doc.querySelector('[data-ct-part-row="1"]'), 'حذف جلسه');
    /* B3: ذخیره با خطای سرور → فوکوس روی اولین فیلد خطادار */
    app.type('#ctf_t', '');
    app.click('[data-ct-save]');
    await app.until(() => app.doc.querySelector('[data-ct-err="t"]')?.textContent.includes('عنوان لازم است'), 'خطا');
    assert.equal(app.doc.activeElement, app.doc.querySelector('#ctf_t'), 'فوکوس روی اولین فیلد خطادار');
    /* B17: پیش‌نویس محلی — ترک ویرایشگر و بازگشت، بازیابی با تأیید صریح */
    app.type('#ctf_t', 'رویداد با جلسه');
    app.type('#ctf_d', 'شرح کامل');
    const draftKeys = () => [...app.sessionValues.keys()].filter((k) => k.startsWith('nora-admin-ct-draft:'));
    assert.equal(draftKeys().length, 1, 'پیش‌نویس در sessionStorage همین زبانه');
    app.close();
    /* بارگذاری دوبارهٔ پنل در همان زبانه (همان sessionStorage): پیش‌نویس فقط با تأیید صریح برمی‌گردد و روی رکورد دیگر نشان داده نمی‌شود */
    app = await loadPanel({ role: 'owner', sec: 'events', world: app.world, sessionValues: app.sessionValues });
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست پس از بارگذاری دوباره');
    app.click('[data-ct-edit="ev-a1"]');
    await app.until(() => app.doc.querySelector('#ctf_t')?.value === 'کارگاه نگارش', 'ویرایش رکورد موجود');
    assert.equal(app.doc.querySelector('[data-ct-draft]'), null, 'پیش‌نویس رکورد تازه روی رکورد دیگر نشان داده نمی‌شود');
    app.click('[data-ct-cancel]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'بازگشت');
    assert.equal(draftKeys().length, 1, 'انصراف از رکورد دیگر، پیش‌نویس رکورد تازه را پاک نمی‌کند');
    app.click('[data-ct-new]');
    await app.until(() => app.doc.querySelector('[data-ct-draft]'), 'هشدار پیش‌نویس ذخیره‌نشده');
    assert.equal(app.doc.querySelector('#ctf_t').value, '', 'تا تأیید، فرم با پیش‌نویس پر نمی‌شود');
    app.click('[data-ct-draft-restore]');
    await app.until(() => app.doc.querySelector('#ctf_t')?.value === 'رویداد با جلسه', 'بازیابی');
    assert.equal(app.doc.querySelector('[data-ct-part="0"][data-ct-part-field="title"]').value, 'مقدمه', 'جلسه‌ها هم برگشتند');
    app.click('[data-ct-save]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-new1"]'), 'ذخیره شد');
    const created = app.calls.filter((c) => c.method === 'POST' && c.path === '/api/admin/content/events').pop();
    assert.deepEqual(created.body.record.parts, [{ title: 'مقدمه', date: '1405/08/05', time: '09:00', to: '', description: '' }], 'جلسه‌ها به همان شکل قرارداد سرور');
    assert.equal(created.body.record.on, '1405/08/05');
    assert.equal(created.body.record.startsAt, '1405/08/05 09:00');
    assert.equal(draftKeys().length, 0, 'پس از ذخیره پیش‌نویس محلی پاک می‌شود');
    /* B16: تکثیر = ویرایشگر تازه با نسخهٔ پرشده؛ تا ذخیره هیچ POSTی نیست */
    const posts = app.calls.filter((c) => c.method === 'POST').length;
    app.click('[data-ct-dup="ev-a1"]');
    await app.until(() => app.doc.querySelector('[data-ct-copy-of="ev-a1"]'), 'رونوشت باز شد');
    assert.equal(app.doc.querySelector('#ctf_t').value, 'کارگاه نگارش (رونوشت)');
    assert.equal(app.doc.querySelector('#ctf_place').value, 'تهران');
    assert.equal(app.calls.filter((c) => c.method === 'POST').length, posts, 'تکثیر بدون ذخیره درخواستی نمی‌فرستد');
    assert.match(app.body(), /هنوز ذخیره نشده/);
    app.click('[data-ct-cancel]');
    await app.until(() => app.doc.querySelector('[data-ct-row="ev-a1"]'), 'انصراف از رونوشت');
    assert.equal(app.world.events.filter((e) => e.t.includes('رونوشت')).length, 0);
  } finally { app.close(); }
  /* مدیر بدون ev_create: دکمهٔ تکثیر نیست */
  const ro = await loadPanel({ role: 'manager', sec: 'events', permissions: ['ev_publish', 'pr_media', 'us_view'] });
  try {
    await ro.until(() => ro.doc.querySelector('[data-ct-row="ev-a1"]'), 'فهرست');
    assert.equal(ro.doc.querySelector('[data-ct-dup]'), null, 'بدون ev_create تکثیر نیست');
  } finally { ro.close(); }
}

console.log('آزمون مرحلهٔ دوم و سوم پنل: قبول');
