/* فاز ۹ — پنل: محصول ضبط‌شدهٔ رویداد (ساخت، جلسات، موانع انتشار، انتشار)، منابعِ جلسه، دسترسی‌ها و کارتابل سفارش‌ها
   با نشست سروری ساختگی. fetch با مسیر دقیق شبیه‌سازی می‌شود؛ هیچ سروری اجرا نمی‌شود و هیچ پرداختی رخ نمی‌دهد.
   مجوز و هر تصمیم مالی در سرور است؛ این‌جا فقط سنجیده می‌شود که پنل همان API را درست صدا می‌زند و پاسخ را صادقانه بازتاب می‌دهد. */
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const ADMIN_HTML = resolve(HERE, 'admin.html');
const fa = (n) => String(n).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d]);
const delay = (ms = 10) => new Promise((done) => setTimeout(done, ms));
const reply = (status, payload = {}) => ({ ok: status >= 200 && status < 300, status, json: async () => payload });
const MANAGER = ['ev_create', 'ev_publish', 'ev_cancel', 'attendance', 'certificate', 'fm_create', 'fm_responses', 'fm_export',
  'receipt_approve', 'us_view', 'us_edit', 'us_approve', 'us_block', 'us_notes', 'us_export', 'sp_answer', 'sp_reopen',
  'qa_audit', 'qa_complaint', 'qa_quality', 'qa_fix', 'qa_report', 'bc_send', 'bc_event', 'pr_media', 'pr_campaign',
  'pr_invite', 'dev_course', 'dev_process', 'dev_kpi', 'dev_review', 'rp_view', 'rp_export'];
const OWNER = [...MANAGER, 'cl_member', 'cl_session', 'cl_cert', 'cl_content', 'cl_dues', 'sys_points', 'finance',
  'role_assign', 'sys_fields', 'sys_settings', 'sys_backup', 'cert_final', 'user_delete', 'public_roster'];
const EV = 'ev-qa-phase9';
const REC_ID = '99999999-9999-4999-8999-999999999999';
const SESS1 = '55555555-5555-4555-8555-555555555551';
const SESS2 = '55555555-5555-4555-8555-555555555552';
const RES1 = '11111111-1111-4111-8111-111111111119';
const ORD1 = '77777777-7777-4777-8777-777777777771';
const ORD2 = '77777777-7777-4777-8777-777777777772';
const ACC1 = '88888888-8888-4888-8888-888888888881';
const ORD3 = '77777777-7777-4777-8777-777777777773';
const FORM = '66666666-6666-4666-8666-666666666661';

/* Mirrors backend `recordings.commerce_for` / `publish_blockers` (phase 9.1): the purchase form is the commercial source. */
function commerceFor(state) {
  const rec = state.recording, f = state.purchaseForm;
  if (!f) return { source: 'product', price: rec.price, currency: 'IRR', free: !(rec.price > 0), methods: [], form_id: null, form_status: '', form_title: '', valid: true, on_sale: true };
  const methods = f.price > 0 ? f.methods.filter((m) => m !== 'bale_wallet' || state.walletReady) : [];
  return { source: 'form', price: f.price, currency: 'IRR', free: !(f.price > 0), methods, form_id: f.id, form_status: f.status, form_title: f.title, valid: f.price != null, on_sale: f.status === 'published' };
}
function blockersFor(state) {
  const rec = state.recording; if (!rec) return [];
  const out = [];
  if (!state.sessions.some((s) => s.status === 'published')) out.push('no_published_session');
  if (!state.resources.some((r) => r.session_id && r.status === 'published')) out.push('no_live_resource');
  const c = commerceFor(state);
  if (c.source !== 'form') { if (c.price > 0) out.push('purchase_form_required'); }
  else if (!c.valid) out.push('purchase_form_invalid_price');
  else if (c.form_status !== 'published') out.push('purchase_form_not_published');
  else if (c.price > 0 && !c.methods.length) out.push('no_payment_method');
  return out;
}
function makeState() {
  return {
    walletReady: false,
    recording: null,
    purchaseForm: null,
    sessions: [],
    resources: [],
    access: [],
    orders: [
      { id: ORD1, recording_id: REC_ID, event_id: EV, event_title: 'کارگاه برگزارشده', product_title: 'ضبط کارگاه نجوم', account_id: 'acc-buyer-1', account_label: 'مینا ر.', method: 'card_transfer', status: 'receipt_submitted', open: true, reviewable: true,
        amount: 1500000, currency: 'IRR', expires_at: '2026-10-24T06:00:00+00:00', payer_bale_user_id: '', transaction_id: '', has_receipt: true, receipt_file_name: 'receipt.jpg', receipt_content_type: 'image/jpeg', receipt_size: 4200, receipt_note: 'واریز از کارت ملت',
        receipt_submitted_at: '2026-10-21T07:00:00+00:00', paid_at: null, decided_at: null, decided_by_kind: '', decision_reason: '', review_note: '', refund_reference: '', refunded_at: null, duplicates: 1, access: null, created_at: '2026-10-21T06:00:00+00:00', updated_at: '2026-10-21T07:00:00+00:00' },
      { id: ORD2, recording_id: REC_ID, event_id: EV, event_title: 'کارگاه برگزارشده', product_title: 'ضبط کارگاه نجوم', account_id: 'acc-buyer-2', account_label: 'امید ن.', method: 'bale_wallet', status: 'paid', open: false, reviewable: false,
        amount: 1500000, currency: 'IRR', expires_at: null, payer_bale_user_id: '4411', transaction_id: 'tx-77', has_receipt: false, receipt_file_name: '', receipt_content_type: '', receipt_size: 0, receipt_note: '',
        receipt_submitted_at: null, paid_at: '2026-10-21T05:00:00+00:00', decided_at: null, decided_by_kind: '', decision_reason: '', review_note: '', refund_reference: '', refunded_at: null, duplicates: 0,
        access: { id: ACC1, state: 'active', status: 'active', source: 'purchase', expires_at: null }, created_at: '2026-10-21T04:50:00+00:00', updated_at: '2026-10-21T05:00:00+00:00' },
      /* Phase 9.1: an order that mirrors a purchase-form payment — its receipt is decided in the shared inbox, never here. */
      { id: ORD3, recording_id: REC_ID, event_id: EV, event_title: 'کارگاه برگزارشده', product_title: 'ضبط کارگاه نجوم', account_id: 'acc-buyer-3', account_label: 'سارا م.', method: 'card_transfer', status: 'receipt_submitted', open: true, reviewable: true,
        amount: 1500000, currency: 'IRR', expires_at: null, payer_bale_user_id: '', transaction_id: '', has_receipt: false, receipt_file_name: '', receipt_content_type: '', receipt_size: 0, receipt_note: '',
        receipt_submitted_at: '2026-10-21T07:10:00+00:00', paid_at: null, decided_at: null, decided_by_kind: '', decision_reason: '', review_note: '', refund_reference: '', refunded_at: null, duplicates: 0, access: null,
        form_response_id: '99999999-9999-4999-8999-999999999991', form_payment_id: '99999999-9999-4999-8999-999999999992', created_at: '2026-10-21T07:00:00+00:00', updated_at: '2026-10-21T07:10:00+00:00' },
    ],
  };
}

async function loadPanel(identity) {
  const state = makeState();
  const calls = [];
  const values = new Map([['nora-admin', JSON.stringify({ v: 78, sec: identity.sec || 'events', ...(identity.state || {}) })]]);
  const store = {
    getItem(k) { return values.has(String(k)) ? values.get(String(k)) : null; },
    setItem(k, v) { values.set(String(k), String(v)); },
    removeItem(k) { values.delete(String(k)); }, clear() { values.clear(); },
    key(i) { return [...values.keys()][i] || null; }, get length() { return values.size; },
  };
  const perms = identity.permissions || (identity.role === 'owner' ? OWNER : MANAGER);
  const has = (p) => perms.includes(p);
  const prompts = [];
  const adminRecording = () => {
    const rec = state.recording; if (!rec) return null;
    const published = state.sessions.filter((s) => s.status === 'published').length;
    return { ...rec, sessions: state.sessions.map((s) => ({ ...s, resource_count: state.resources.filter((r) => r.session_id === s.id && r.status !== 'removed').length })),
      commerce: commerceFor(state), publish_blockers: blockersFor(state), transitions: { draft: ['ready', 'archived'], ready: ['draft', 'published', 'archived'], published: ['sales_paused', 'archived'], sales_paused: ['published', 'archived'], archived: ['ready'] }[rec.status],
      /* Same keys as backend `_recording_admin_counts` (app.py) — the panel must read these, not invented ones. */
      counts: { orders_open: state.orders.filter((o) => o.open).length, orders_review: state.orders.filter((o) => o.status === 'receipt_submitted' || o.status === 'needs_review').length, orders_paid: state.orders.filter((o) => /^paid/.test(o.status)).length, orders_refunded: 0, access_active: state.access.filter((a) => a.state === 'active').length, access_total: state.access.length } };
  };
  const dom = await JSDOM.fromFile(ADMIN_HTML, {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(window) {
      Object.defineProperty(window.navigator, 'userAgent', { configurable: true, value: 'ArenaBrowser/1.0' });
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.scrollTo = () => {};
      window.confirm = () => true;
      window.prompt = (text) => { prompts.push(text); return identity.promptValue === undefined ? 'دلیل آزمایشی' : identity.promptValue; };
      Object.defineProperty(window.document, 'cookie', { configurable: true, get: () => 'nora_csrf=owner-csrf; nora_account_csrf=account-csrf' });
      window.fetch = async (url, options = {}) => {
        const path = String(url);
        const method = String(options.method || 'GET').toUpperCase();
        const headers = options.headers || {};
        calls.push({ path, method, headers, body: typeof options.body === 'string' ? options.body : null });
        const json = () => { try { return JSON.parse(options.body || '{}'); } catch (_) { return {}; } };
        const guard = (...needed) => {
          if (!needed.some(has)) return reply(403, { detail: 'permission_denied' });
          if (method !== 'GET' && !headers['X-CSRF-Token']) return reply(403, { detail: 'csrf_check_failed' });
          return null;
        };
        if (path === '/api/auth/me') return identity.role === 'owner'
          ? reply(200, { authenticated: true, owner_id: 'owner-01', role: 'owner', permissions: OWNER })
          : reply(401, { detail: 'authentication_required' });
        if (path === '/api/account/me') return identity.role === 'owner' ? reply(401, { detail: 'authentication_required' })
          : reply(200, { authenticated: true, account_id: 'acc-mgr', provider: 'manager-password', role: identity.role, permissions: perms, manager_username: 'qa.manager' });
        if (path === '/api/health') return reply(200, { ok: true, formsEnabled: true, responsesEnabled: true });
        if (path === '/api/integrations/status') return reply(200, { providers: [] });
        if (path === '/api/forms') return reply(200, { items: [] });
        if (path === '/api/owner/site-content') return reply(200, { content: {}, version: 1, updated_at: null });
        if (/^\/api\/admin\/reports\/summary\?period=/.test(path)) return reply(200, { source: 'shared_server_database', period: '30d', forms: { total: 0, by_status: {} }, responses: { total: 0, by_status: {} }, accounts: { total: 0 } });
        if (path.startsWith('/api/admin/inbox')) return reply(200, { items: [], has_more: false });
        if (path.startsWith('/api/owner/audit')) return reply(200, { items: [], limit: 30, offset: 0, has_more: false, actions: [] });
        if (path.startsWith('/api/admin/content/')) {
          const item = { id: EV, t: 'کارگاه برگزارشده', status: 'published', kind: 'کارگاه', on: '1405/07/20', updated_at: '2026-10-20T06:00:00+00:00', forms: [] };
          return reply(200, { items: [item], total: 1, counts: {}, limit: 20, offset: 0, has_more: false, kind: 'events', version: 1, source: 'site_content', can_edit: has('ev_create'), can_publish: has('ev_publish') });
        }
        if (path === '/api/admin/event-interaction/summary') return reply(200, { source: 'shared_server_database', unanswered_questions: 0, pending_reviews: 0, open_reports: 0, failed_notifications: 0, per_event: [] });
        if (path === '/api/admin/recordings/summary') {
          const g = guard('receipt_approve', 'ev_publish', 'finance'); if (g) return g;
          return reply(200, { source: 'shared_server_database', recordings: { published: 2, ready: 1, draft: 0, sales_paused: 0, archived: 1 }, orders: { receipt_submitted: 1, needs_review: 0, paid: 1, paid_manual: 3 }, orders_refunded: 1, active_access: 4 });
        }
        if (path.startsWith('/api/admin/event-questions') || /\/questions(\?|$)/.test(path) || /\/reviews(\?|$)/.test(path) || path.startsWith('/api/admin/event-reports')) return reply(200, { items: [], total: 0, limit: 20, offset: 0 });
        let m = path.match(/^\/api\/admin\/events\/([^/]+)\/resources(?:\/([^/?]+))?(\/file|\/remove)?(?:\?(.*))?$/);
        if (m) {
          const g = guard('ev_create'); if (g) return g;
          const [, eventId, rid, action] = m;
          if (eventId !== EV) return reply(404, { detail: 'content_record_not_found' });
          if (!rid && method === 'GET') return reply(200, { source: 'shared_server_database', event_id: EV, items: state.resources, total: state.resources.length, max_bytes: 8388608, allowed_types: ['application/pdf', 'video/mp4'] });
          if (!rid && method === 'POST') {
            const sent = json();
            if (sent.session_id && !state.sessions.some((s) => s.id === sent.session_id)) return reply(404, { detail: 'session_not_found' });
            const row = { id: RES1, event_id: EV, kind: sent.kind || 'file', title: sent.title, description: sent.description || '', access: sent.access || 'public', status: 'draft', publish_at: null, live: false, publisher: '', file_name: '', content_type: '', size: 0,
              link_url: '', session_id: sent.session_id || '', delivery: sent.delivery || 'download', removed_at: null, removed_reason: '', created_at: '2026-10-21T06:00:00+00:00', updated_at: '2026-10-21T06:00:00+00:00' };
            state.resources.push(row); return reply(201, row);
          }
          const row = state.resources.find((r) => r.id === rid); if (!row) return reply(404, { detail: 'resource_not_found' });
          if (action === '/file' && method === 'PUT') { row.file_name = decodeURIComponent(String(headers['X-File-Name'] || '')); row.size = 64; row.content_type = 'video/mp4'; return reply(200, row); }
          if (!action && method === 'PUT') { const sent = json(); if (sent.status === 'published' && !row.size) return reply(409, { detail: { code: 'resource_file_missing' } }); Object.assign(row, sent); if (sent.status === 'published') row.live = true; return reply(200, row); }
          return reply(404, { detail: 'not_found' });
        }
        m = path.match(/^\/api\/admin\/events\/([^/]+)\/recording(?:\/(status|sessions|access))?(?:\/([^/?]+))?(?:\/(revoke))?$/);
        if (m) {
          const [, eventId, part, sub, action] = m;
          if (eventId !== EV) return reply(404, { detail: 'content_record_not_found' });
          const base = { source: 'shared_server_database', event_id: EV, event_held: true, event_published: true, wallet_ready: state.walletReady, limits: { max_bytes: 8388608, content_types: ['video/mp4'], max_price: 2000000000, max_access_days: 3650, max_sessions: 60, streaming: 'none' } };
          if (!part && method === 'GET') { const g = guard('ev_create', 'ev_publish', 'receipt_approve'); if (g) return g; return reply(200, { ...base, recording: adminRecording() }); }
          if (!part && method === 'PUT') {
            const g = guard('ev_create'); if (g) return g;
            const sent = json();
            if (!sent.title || sent.title.length < 2) return reply(422, { detail: { code: 'text_required', field: 'title' } });
            if (sent.payment_card && !/^\d{16}$/.test(sent.payment_card.number || '')) return reply(422, { detail: { code: 'invalid_payment_card', field: 'payment_card' } });
            if (state.recording && state.purchaseForm && ['price', 'payment_card', 'bale_enabled'].some((k) => k in sent && JSON.stringify(sent[k]) !== JSON.stringify(state.recording[k]))) return reply(409, { detail: { code: 'commercial_settings_in_form', fields: ['price'], form_id: state.purchaseForm.id } });
            if (state.recording && state.recording.status === 'published' && 'price' in sent && sent.price !== state.recording.price && state.orders.some((o) => o.open)) return reply(409, { detail: { code: 'open_orders_block_price_change' } });
            const prev = state.recording;
            state.recording = { id: REC_ID, event_id: EV, event_title: 'کارگاه برگزارشده', status: prev ? prev.status : 'draft', status_reason: prev ? prev.status_reason : '', currency: 'IRR', published_at: null, version: prev ? prev.version + 1 : 1, created_at: '2026-10-21T06:00:00+00:00', updated_at: '2026-10-21T06:00:00+00:00',
              title: sent.title, summary: sent.summary || '', outcomes: sent.outcomes || '', audience: sent.audience || '', access_terms: sent.access_terms || '', refund_policy: sent.refund_policy || '', faq: sent.faq || [], price: 'price' in sent ? sent.price : (prev ? prev.price : 0), access_days: sent.access_days,
              attendee_access: !!sent.attendee_access, download_default: sent.download_default !== false, bale_enabled: prev ? prev.bale_enabled : true, payment_card: prev ? prev.payment_card : null, cover_url: sent.cover_url || '',
              certificate_policy: 'certificate_policy' in sent ? sent.certificate_policy : (prev ? prev.certificate_policy : 'none') };
            if (!['none', 'manual'].includes(state.recording.certificate_policy)) return reply(422, { detail: { code: 'invalid_choice', field: 'certificate_policy' } });
            state.recording.certificate = { kind: 'recording_completion', policy: state.recording.certificate_policy, automatic: false, manual_issue_only: state.recording.certificate_policy === 'manual', counts_as_attendance: false };
            return reply(prev ? 200 : 201, adminRecording());
          }
          if (part === 'status') {
            const g = guard('ev_publish'); if (g) return g;
            const sent = json();
            if (sent.status === 'published' && blockersFor(state).length) return reply(409, { detail: { code: 'publish_blocked', blockers: blockersFor(state) } });
            if ((sent.status === 'sales_paused' || sent.status === 'archived') && !sent.reason) return reply(422, { detail: { code: 'reason_required', field: 'reason' } });
            state.recording.status = sent.status; state.recording.status_reason = sent.reason || ''; state.recording.version += 1;
            return reply(200, adminRecording());
          }
          if (part === 'sessions') {
            const g = guard('ev_create'); if (g) return g;
            if (!sub && method === 'POST') { const sent = json(); if (!sent.title || sent.title.length < 2) return reply(422, { detail: { code: 'text_required', field: 'title' } });
              const row = { id: state.sessions.length ? SESS2 : SESS1, recording_id: REC_ID, title: sent.title, description: sent.description || '', sort_order: sent.sort_order || state.sessions.length + 1, duration_minutes: sent.duration_minutes || null, status: 'draft', preview: !!sent.preview, resource_count: 0, created_at: '2026-10-21T06:00:00+00:00', updated_at: '2026-10-21T06:00:00+00:00' };
              state.sessions.push(row); return reply(201, row); }
            const row = state.sessions.find((s) => s.id === sub); if (!row) return reply(404, { detail: 'session_not_found' });
            if (method === 'PUT') { Object.assign(row, json()); return reply(200, row); }
            if (method === 'DELETE') { if (state.resources.some((r) => r.session_id === row.id && r.status !== 'removed')) return reply(409, { detail: { code: 'session_has_resources' } }); state.sessions = state.sessions.filter((s) => s !== row); return reply(200, { deleted: true }); }
          }
          if (part === 'access') {
            if (!sub && method === 'GET') { const g = guard('ev_create', 'ev_publish', 'receipt_approve'); if (g) return g; return reply(200, { source: 'shared_server_database', items: state.access, total: state.access.length }); }
            const g = guard('ev_publish'); if (g) return g;
            if (!sub && method === 'POST') { const sent = json(); if (!sent.reason) return reply(422, { detail: { code: 'text_required', field: 'reason' } }); if (sent.account_id !== 'acc-member-9') return reply(404, { detail: { code: 'account_not_found' } });
              const row = { id: ACC1, recording_id: REC_ID, account_id: sent.account_id, account_label: 'سارا ک.', source: 'granted', status: 'active', state: 'active', order_id: null, expires_at: sent.access_days ? '2026-11-20T06:00:00+00:00' : null, granted_by_kind: 'owner', reason: sent.reason, revoked_at: null, revoke_reason: '', created_at: '2026-10-21T06:00:00+00:00', updated_at: '2026-10-21T06:00:00+00:00' };
              state.access.push(row); return reply(201, { created: true, access: row }); }
            if (action === 'revoke') { const row = state.access.find((a) => a.id === sub); const sent = json(); if (!sent.reason) return reply(422, { detail: { code: 'text_required', field: 'reason' } }); row.status = 'revoked'; row.state = 'revoked'; row.revoke_reason = sent.reason; return reply(200, row); }
          }
          return reply(404, { detail: 'not_found' });
        }
        m = path.match(/^\/api\/admin\/recording-orders(?:\/([^/?]+))?(?:\/(receipt|decision|refund))?(?:\?(.*))?$/);
        if (m) {
          const [, oid, action, query] = m;
          if (!oid) {
            const g = guard('receipt_approve', 'ev_publish', 'finance'); if (g) return g;
            const p = new URLSearchParams(query || '');
            const sets = { review: ['receipt_submitted', 'needs_review'], open: ['pending', 'awaiting_receipt', 'receipt_submitted', 'needs_review'], paid: ['paid', 'paid_manual'], closed: ['rejected', 'cancelled', 'expired', 'refunded'] };
            let items = state.orders.slice();
            if (p.get('status')) items = items.filter((o) => (sets[p.get('status')] || [p.get('status')]).includes(o.status));
            if (p.get('q')) items = items.filter((o) => o.id.includes(p.get('q')) || o.account_id.includes(p.get('q')));
            return reply(200, { source: 'shared_server_database', items, total: items.length, limit: 20, offset: 0 });
          }
          const row = state.orders.find((o) => o.id === oid); if (!row) return reply(404, { detail: 'order_not_found' });
          if (!action) return reply(200, { ...row, history: [{ action: 'recording.order.approve', actor_kind: 'owner', actor_role: 'owner', outcome: 'ok', details: { reason: 'رسید بررسی شد' }, at: '2026-10-21T07:30:00+00:00' }] });
          if (action === 'decision') {
            const g = guard('receipt_approve'); if (g) return g;
            const sent = json(); if (!sent.reason) return reply(422, { detail: { code: 'text_required', field: 'reason' } });
            if (!row.reviewable) return reply(409, { detail: { code: 'order_not_reviewable' } });
            if (row.form_payment_id) return reply(409, { detail: { code: 'decide_in_inbox', task_id: 'task-1' } });
            row.status = sent.decision === 'approve' ? 'paid_manual' : 'rejected'; row.open = false; row.reviewable = false; row.decided_at = '2026-10-21T08:00:00+00:00'; row.decision_reason = sent.reason;
            if (sent.decision === 'approve') { row.paid_at = row.decided_at; row.access = { id: 'acc-x', state: 'active', status: 'active', source: 'purchase', expires_at: null }; }
            return reply(200, row);
          }
          if (action === 'refund') {
            const g = guard('finance'); if (g) return g;
            const sent = json(); if (!sent.reference) return reply(422, { detail: { code: 'refund_reference_required', field: 'reference' } });
            row.status = 'refunded'; row.refund_reference = sent.reference; row.refunded_at = '2026-10-21T09:00:00+00:00'; if (row.access) row.access = { ...row.access, state: 'revoked', status: 'revoked' };
            return reply(200, row);
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
  const click = (sel) => { const el = doc.querySelector(sel); assert.ok(el, `عنصر پیدا نشد: ${sel}`); el.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true })); return el; };
  const setField = (sel, value) => { const el = doc.querySelector(sel); assert.ok(el, `فیلد پیدا نشد: ${sel}`); el.value = value; el.dispatchEvent(new dom.window.Event('change', { bubbles: true })); };
  const body = () => doc.querySelector('#admBody').textContent;
  const noLeak = () => assert.doesNotMatch(body(), /0912|09\d{9}|hash|token|password/i, 'شماره، هش یا توکن در خروجی پنل نیست');
  const openEvent = async () => { await until(() => doc.querySelector(`[data-ct-interaction="${EV}"]`), 'ردیف رویداد'); click(`[data-ct-interaction="${EV}"]`); await until(() => doc.querySelector('[data-ei-panel]'), 'پنل رویداد'); };
  return { dom, doc, calls, click, setField, until, body, noLeak, prompts, state, openEvent, close: () => dom.window.close() };
}

console.log('— مالک: ساخت محصول، جلسه، فایل جلسه از زبانهٔ منابع، موانع انتشار از سرور، انتشار —');
{
  const app = await loadPanel({ role: 'owner', sec: 'events' });
  try {
    await app.openEvent();
    assert.ok(app.doc.querySelector('[data-ei-tab="recording"]'), 'زبانهٔ «ضبط‌شده و فروش» داخل همان ابزار رویداد');
    assert.ok(app.doc.querySelector('[data-ei-tab="orders"]'), 'زبانهٔ سفارش‌ها');
    app.click('[data-ei-tab="recording"]');
    await app.until(() => app.doc.querySelector('[data-rec-panel]') && app.doc.querySelector('[data-rec-create]'), 'حالت خالی با دکمهٔ ساخت');
    assert.ok(app.calls.some((c) => c.path === `/api/admin/events/${EV}/recording`), 'خواندن محصول از API همان رویداد');
    assert.match(app.body(), /هنوز محصول ضبط‌شده‌ای ساخته نشده/);
    assert.match(app.doc.querySelector('[data-rec-limits]').textContent, /پخش جریانی\/CDN\/حفاظت از کپی وجود ندارد/, 'محدودیت زیرساخت صادقانه اعلام می‌شود');
    app.click('[data-rec-create]');
    await app.until(() => app.doc.querySelector('[data-rec-editor]'), 'ویرایشگر محصول');
    app.setField('#recf_title', 'ضبط کارگاه نجوم');
    app.setField('#recf_price', '1500000');
    /* ۹.۱: کارت مقصد و کلید کیف پول روی محصول نیستند؛ منبع آن‌ها فرم خرید است */
    assert.equal(app.doc.querySelector('#recf_card_number'), null, 'ویرایشگر محصول فیلد کارت مقصد ندارد');
    assert.equal(app.doc.querySelector('[data-rec-flag="bale_enabled"]'), null, 'ویرایشگر محصول کلید کیف پول ندارد');
    assert.match(app.doc.querySelector('[data-rec-commerce-note]').textContent, /در «فرم خرید» همین محصول/, 'توضیح منبع تجاری');
    app.setField('#recf_faq', 'آیا دانلود دارد؟ :: بله، جزوه‌ها قابل دانلود است.');
    /* ۹.۱ §۲: گواهی پایان محتوا یک سوییچ صریح با دو حالت است؛ هیچ گزینهٔ خودکاری وجود ندارد */
    const certSelect = app.doc.querySelector('#recf_certificate_policy');
    assert.ok(certSelect && certSelect.tagName === 'SELECT', 'انتخاب‌گر سیاست گواهی پایان محتوا');
    assert.deepEqual(Array.from(certSelect.options).map((o) => o.value), ['none', 'manual'], 'فقط «صادر نمی‌شود» و «صدور دستی»');
    assert.equal(certSelect.value, 'none', 'پیش‌فرض: بدون گواهی');
    assert.match(app.doc.querySelector('[data-rec-certificate]').textContent, /هیچ‌وقت خودکار صادر نمی‌شود/, 'توضیح صادقانه: صدور خودکار وجود ندارد');
    app.click('[data-rec-save]');
    await app.until(() => app.doc.querySelector('[data-rec-status-box]'), 'محصول ساخته شد');
    const created = app.calls.find((c) => c.method === 'PUT' && c.path === `/api/admin/events/${EV}/recording`);
    const sentBody = JSON.parse(created.body);
    assert.equal(sentBody.price, 1500000); assert.equal(sentBody.access_days, null);
    assert.equal(sentBody.certificate_policy, 'none', 'سیاست گواهی در payload می‌رود');
    assert.match(app.doc.querySelector('[data-rec-status-box]').textContent, /بدون گواهی پایان محتوا/, 'کادر وضعیت سیاست گواهی را نشان می‌دهد');
    assert.ok(!('payment_card' in sentBody) && !('bale_enabled' in sentBody), 'کارت مقصد/کیف پول در payload محصول فرستاده نمی‌شود');
    assert.deepEqual(sentBody.faq, [{ q: 'آیا دانلود دارد؟', a: 'بله، جزوه‌ها قابل دانلود است.' }]);
    assert.equal(created.headers['X-CSRF-Token'], 'owner-csrf');
    assert.match(app.doc.querySelector('[data-rec-status-box]').textContent, /پیش‌نویس/);
    assert.match(app.doc.querySelector('[data-rec-blockers]').textContent, /دست‌کم یک جلسهٔ منتشرشده لازم است/, 'موانع انتشار از سرور');
    assert.match(app.doc.querySelector('[data-rec-blockers]').textContent, /هنوز فرم خریدی برای این محصول ساخته نشده/, 'مانع purchase_form_required با متن روشن');
    const createForm = app.doc.querySelector('[data-rec-commerce="product"] a[data-rec-form-create]');
    assert.ok(createForm, 'جعبهٔ «فروش و قیمت» پیوند ساخت فرم خرید دارد');
    assert.equal(createForm.getAttribute('href'), `create.html?purpose=recording_access&recording=${REC_ID}&ev=${EV}&back=${encodeURIComponent('admin.html#newev')}`, 'پیوند فرم‌ساز با شناسهٔ محصول و رویداد (سرور دوباره می‌سنجد)');
    assert.equal(app.doc.querySelector('[data-rec-status="published"]'), null, 'در پیش‌نویس دکمهٔ انتشار وجود ندارد (گذار سرور)');
    assert.ok(app.doc.querySelector('[data-rec-status="ready"]'));

    /* جلسهٔ تازه */
    app.click('[data-rec-sess-new]');
    await app.until(() => app.doc.querySelector('[data-rec-sess-editor]'), 'ویرایشگر جلسه');
    app.setField('#recs_title', 'جلسهٔ یکم: آسمان شب');
    app.setField('#recs_duration_minutes', '95');
    app.click('[data-rec-sess-save]');
    await app.until(() => app.doc.querySelector(`[data-rec-sess-row="${SESS1}"]`), 'جلسه در فهرست');
    const sess = JSON.parse(app.calls.find((c) => c.method === 'POST' && c.path === `/api/admin/events/${EV}/recording/sessions`).body);
    assert.equal(sess.duration_minutes, 95); assert.equal(sess.preview, false);
    assert.match(app.doc.querySelector(`[data-rec-sess-row="${SESS1}"]`).textContent, /هنوز فایلی ندارد/);

    /* افزودن فایل به جلسه: می‌رود به زبانهٔ منابع با جلسه و سطح «دارندگان دسترسی» از پیش انتخاب‌شده */
    app.click(`[data-rec-sess-add="${SESS1}"]`);
    await app.until(() => app.doc.querySelector('[data-ei-res-editor]') && app.doc.querySelector('#eif_session_id'), 'ویرایشگر منبع با فیلد جلسه');
    assert.equal(app.doc.querySelector('#eif_session_id').value, SESS1);
    assert.equal(app.doc.querySelector('#eif_access').value, 'purchased');
    /* فاز ۹.۳: منبع بیرونیِ پولی → هشدار صریح سطح حفاظت (Unlisted/عمومی)؛ رایگان → فقط یادآوری بدون DRM؛ فایل → هیچ هشداری */
    app.setField('#eif_kind', 'youtube');
    await app.until(() => app.doc.querySelector('[data-ei-external-warning="paid"]'), 'هشدار منبع بیرونی پولی');
    assert.match(app.doc.querySelector('[data-ei-external-warning="paid"]').textContent, /Unlisted/);
    assert.match(app.doc.querySelector('[data-ei-external-warning="paid"]').textContent, /نباید «ویدیوی محافظت‌شده» معرفی کرد/);
    app.setField('#eif_access', 'public');
    await app.until(() => app.doc.querySelector('[data-ei-external-warning="free"]'), 'یادآوری منبع بیرونی رایگان');
    assert.doesNotMatch(app.doc.querySelector('[data-ei-external-warning="free"]').textContent, /Unlisted/);
    app.setField('#eif_access', 'purchased');
    app.setField('#eif_kind', 'file');
    await app.until(() => !app.doc.querySelector('[data-ei-external-warning]'), 'فایل خصوصی: بدون هشدار بیرونی');
    assert.equal(app.doc.querySelector('#eif_access').value, 'purchased');
    assert.equal(app.doc.querySelector('#eif_session_id').value, SESS1);
    app.setField('#eif_title', 'ویدئوی جلسهٔ یکم');
    app.setField('#eif_delivery', 'view');
    app.click('[data-ei-res-save]');
    await app.until(() => app.doc.querySelector(`[data-ei-res-row="${RES1}"]`), 'منبع جلسه ساخته شد');
    const resCreated = JSON.parse(app.calls.find((c) => c.method === 'POST' && c.path === `/api/admin/events/${EV}/resources`).body);
    assert.equal(resCreated.session_id, SESS1); assert.equal(resCreated.delivery, 'view'); assert.equal(resCreated.access, 'purchased');
    assert.match(app.doc.querySelector(`[data-ei-res-row="${RES1}"]`).textContent, /جلسه: جلسهٔ یکم/);
    assert.match(app.doc.querySelector(`[data-ei-res-row="${RES1}"]`).textContent, /فقط مشاهدهٔ برخط/);
    const input = app.doc.querySelector(`[data-ei-file="${RES1}"]`);
    const file = new app.dom.window.File([new Uint8Array(64)], 'session1.mp4', { type: 'video/mp4' });
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    input.dispatchEvent(new app.dom.window.Event('change', { bubbles: true }));
    await app.until(() => /session1\.mp4/.test(app.body()), 'فایل ویدئو ذخیره شد');
    app.click(`[data-ei-res-status="published"][data-ei-id="${RES1}"]`);
    await app.until(() => /منتشرشده/.test(app.doc.querySelector(`[data-ei-res-row="${RES1}"]`).textContent), 'منبع جلسه منتشر شد');

    /* بازگشت به زبانهٔ محصول: انتشار جلسه، آماده‌سازی، انتشار */
    app.click('[data-ei-tab="recording"]');
    await app.until(() => app.doc.querySelector(`[data-rec-sess-row="${SESS1}"]`) && /فایل‌های جلسه \(۱\)/.test(app.doc.querySelector(`[data-rec-sess-row="${SESS1}"]`).textContent), 'شمار فایل جلسه');
    app.click(`[data-rec-sess-status="published"][data-rec-id="${SESS1}"]`);
    await app.until(() => app.doc.querySelector('[data-rec-blockers]') && !/جلسهٔ منتشرشده لازم/.test(app.doc.querySelector('[data-rec-blockers]').textContent), 'موانع جلسه/فایل برطرف شد');
    assert.match(app.doc.querySelector('[data-rec-blockers]').textContent, /هنوز فرم خریدی/, 'بدون فرم خرید همچنان منتشر نمی‌شود');
    /* فرم خرید در فرم‌ساز ساخته شد (پیش‌نویس) → سرور مانع purchase_form_not_published می‌دهد */
    app.state.purchaseForm = { id: FORM, status: 'draft', title: 'خرید ضبط کارگاه نجوم', price: 1500000, methods: ['card_transfer'] };
    app.click('[data-ei-tab="orders"]'); await app.until(() => app.doc.querySelector('[data-rec-orders]'), 'زبانهٔ سفارش‌ها');
    app.click('[data-ei-tab="recording"]'); await app.until(() => app.doc.querySelector('[data-rec-commerce="form"]'), 'جعبهٔ فروش از فرم');
    assert.match(app.doc.querySelector('[data-rec-blockers]').textContent, /فرم خرید این محصول هنوز منتشر نشده/, 'مانع purchase_form_not_published');
    const formBox = app.doc.querySelector('[data-rec-commerce="form"]');
    assert.match(formBox.textContent, /خرید ضبط کارگاه نجوم/); assert.match(formBox.textContent, /پیش‌نویس/); assert.match(formBox.textContent, /۱,۵۰۰,۰۰۰ ریال/); assert.match(formBox.textContent, /کارت‌به‌کارت/);
    assert.equal(formBox.querySelector('a[data-rec-form-edit]').getAttribute('href'), `create.html?fid=${FORM}&back=${encodeURIComponent('admin.html#newev')}`, 'ویرایش فقط در فرم‌ساز');
    assert.equal(formBox.querySelector('a[data-rec-form-public]'), null, 'فرم منتشرنشده پیوند عمومی ندارد');
    /* ویرایش محصول با فرم متصل: قیمت قفل است و در payload نمی‌رود */
    app.click('[data-rec-edit]'); await app.until(() => app.doc.querySelector('[data-rec-editor]'), 'ویرایشگر');
    assert.equal(app.doc.querySelector('#recf_price'), null, 'با فرم متصل، فیلد قیمت وجود ندارد');
    assert.match(app.doc.querySelector('[data-rec-price-locked]').textContent, /از فرم‌ساز تغییر می‌کنند/);
    app.setField('#recf_summary', 'خلاصهٔ تازه'); app.setField('#recf_certificate_policy', 'manual'); app.click('[data-rec-save]');
    await app.until(() => app.doc.querySelector('[data-rec-status-box]'), 'ذخیرهٔ غیرتجاری');
    const edited = JSON.parse(app.calls.filter((c) => c.method === 'PUT' && c.path === `/api/admin/events/${EV}/recording`).pop().body);
    assert.ok(!('price' in edited) && edited.summary === 'خلاصهٔ تازه', 'ویرایش غیرتجاری بدون فیلد قیمت فرستاده می‌شود');
    assert.equal(edited.certificate_policy, 'manual', 'سوییچ گواهی دستی ذخیره می‌شود');
    assert.match(app.doc.querySelector('[data-rec-status-box]').textContent, /گواهی پایان محتوا: صدور دستی/, 'وضعیت پس از تغییر سیاست');
    assert.equal(app.doc.querySelector('[data-rec-issue-certificate], [data-rec-cert-issue]'), null, 'پنل دکمهٔ صدور گواهی برای محصول ندارد (مسیر صدور فقط مسیر موجود گواهینامه است)');
    /* انتشار فرم خرید در فرم‌ساز → مانع برطرف */
    app.state.purchaseForm.status = 'published';
    app.click('[data-ei-tab="orders"]'); await app.until(() => app.doc.querySelector('[data-rec-orders]'), 'زبانهٔ سفارش‌ها');
    app.click('[data-ei-tab="recording"]'); await app.until(() => app.doc.querySelector('[data-rec-commerce="form"]') && !app.doc.querySelector('[data-rec-blockers]'), 'موانع انتشار برطرف شد');
    assert.equal(app.doc.querySelector('[data-rec-commerce="form"] a[data-rec-form-public]').getAttribute('href'), `form.html?fid=${FORM}&kind=reg`, 'پیوند فرم خرید عمومی = form.html همان فرم');
    app.click('[data-rec-status="ready"]');
    await app.until(() => app.doc.querySelector('[data-rec-status="published"]'), 'دکمهٔ انتشار پس از آماده‌سازی');
    app.click('[data-rec-status="published"]');
    await app.until(() => /در حال فروش/.test(app.doc.querySelector('[data-rec-status-box]').textContent), 'منتشر شد');
    const statusCalls = app.calls.filter((c) => c.method === 'POST' && c.path === `/api/admin/events/${EV}/recording/status`).map((c) => JSON.parse(c.body));
    assert.deepEqual(statusCalls, [{ status: 'ready' }, { status: 'published' }], 'گذارها فقط وضعیت را می‌فرستند؛ دلیل تنها برای توقف/بایگانی');
    /* شمارنده‌ها از کلیدهای واقعی سرور (orders_open/orders_review/orders_paid/access_active/access_total) و فهرست جلسات خوانده می‌شوند؛ صفر ساختگی ممنوع */
    {
      const counts = app.doc.querySelector('[data-rec-counts]').textContent;
      const want = { open: app.state.orders.filter((o) => o.open).length, review: app.state.orders.filter((o) => o.status === 'receipt_submitted' || o.status === 'needs_review').length, sessions: app.state.sessions.filter((x) => x.status === 'published').length };
      assert.ok(want.open > 0 && want.sessions > 0, 'دادهٔ آزمون باید سفارش باز و جلسهٔ منتشرشده داشته باشد');
      assert.match(counts, new RegExp('سفارش‌های باز: ' + fa(want.open) + ' · در انتظار بررسی: ' + fa(want.review)), 'سفارش‌های باز/در انتظار بررسی از شمارندهٔ سرور');
      assert.match(counts, new RegExp('جلسات منتشرشده: ' + fa(want.sessions)), 'جلسات منتشرشده از فهرست واقعی جلسات');
      assert.doesNotMatch(counts, /سفارش‌های باز: ۰/, 'با سفارش باز واقعی، صفر نمایش داده نمی‌شود');
    }

    /* توقف فروش بدون دلیل انجام نمی‌شود */
    app.click('[data-rec-status="sales_paused"]');
    await app.until(() => app.prompts.length > 0, 'درخواست دلیل');
    await app.until(() => /فروش متوقف/.test(app.doc.querySelector('[data-rec-status-box]').textContent), 'توقف فروش با دلیل');
    const paused = JSON.parse(app.calls.filter((c) => c.path.endsWith('/recording/status')).pop().body);
    assert.deepEqual(paused, { status: 'sales_paused', reason: 'دلیل آزمایشی' });
    assert.match(app.doc.querySelector('[data-rec-status-box]').textContent, /دلیل آخرین تغییر وضعیت: دلیل آزمایشی/);

    /* اعطای دستی: فقط حساب واقعی + دلیل؛ ۴۰۴ سرور صادقانه */
    app.click('[data-rec-grant-open]');
    await app.until(() => app.doc.querySelector('[data-rec-grant-form]'), 'فرم اعطا');
    app.setField('#recg_account', 'acc-ghost'); app.setField('#recg_reason', 'بورسیهٔ انجمن');
    app.click('[data-rec-grant-save]');
    await app.until(() => /حسابی با این شناسه پیدا نشد/.test(app.body()), 'خطای حساب ناموجود');
    app.setField('#recg_account', 'acc-member-9'); app.setField('#recg_days', '30');
    app.click('[data-rec-grant-save]');
    await app.until(() => app.doc.querySelector(`[data-rec-access-row="${ACC1}"]`), 'دسترسی اعطاشده در فهرست');
    const grant = JSON.parse(app.calls.filter((c) => c.method === 'POST' && c.path === `/api/admin/events/${EV}/recording/access`).pop().body);
    assert.deepEqual(grant, { account_id: 'acc-member-9', reason: 'بورسیهٔ انجمن', access_days: 30 });
    assert.match(app.doc.querySelector(`[data-rec-access-row="${ACC1}"]`).textContent, /اعطای دستی/);
    app.click(`[data-rec-access-revoke="${ACC1}"]`);
    await app.until(() => /لغوشده/.test((app.doc.querySelector(`[data-rec-access-row="${ACC1}"]`) || {}).textContent || ''), 'لغو با دلیل');
    assert.equal(app.doc.querySelector(`[data-rec-access-row="${ACC1}"] [data-rec-access-revoke]`), null, 'دسترسی لغوشده دکمهٔ لغو ندارد');
    app.noLeak();
    assert.doesNotMatch(app.body(), /تخفیف|نفر خریده‌اند|پرفروش/, 'هیچ شمارندهٔ ساختگی یا تخفیف نمایشی');
  } finally { app.close(); }
}

console.log('— مالک: کارتابل سفارش‌ها (رسید ≠ پرداخت، تأیید با دلیل، تاریخچه، بازپرداخت فقط با شمارهٔ پیگیری، خروجی CSV) —');
{
  const app = await loadPanel({ role: 'owner', sec: 'events' });
  try {
    await app.openEvent();
    app.click('[data-ei-tab="orders"]');
    await app.until(() => app.doc.querySelector(`[data-rec-order-row="${ORD1}"]`), 'سفارش نیازمند بررسی');
    const listed = app.calls.find((c) => c.path.startsWith('/api/admin/recording-orders?'));
    assert.match(listed.path, /status=review/); assert.match(listed.path, new RegExp(`event_id=${EV}`));
    assert.equal(app.doc.querySelector(`[data-rec-order-row="${ORD2}"]`), null, 'فیلتر پیش‌فرض فقط نیازمند بررسی');
    const row = app.doc.querySelector(`[data-rec-order-row="${ORD1}"]`).textContent;
    assert.match(row, /رسید ارسال‌شده؛ نیازمند بررسی/); assert.match(row, /کارت‌به‌کارت/); assert.match(row, /۱ سفارش دیگر از همین حساب/); assert.match(row, /دسترسی: ندارد/);
    assert.match(row, /سفارش قدیمی/, 'سفارش بدون فرم به‌روشنی «قدیمی» است');
    /* ۹.۱: سفارش فرم‌دار فقط به صندوق پیام‌ها می‌رود */
    const viaForm = app.doc.querySelector(`[data-rec-order-row="${ORD3}"]`);
    assert.ok(viaForm, 'سفارش فرم‌دار در فهرست نیازمند بررسی');
    assert.match(viaForm.textContent, /ثبت‌شده از فرم خرید/);
    assert.equal(viaForm.querySelector('[data-rec-order-decide]'), null, 'بدون دکمهٔ تأیید/رد مستقیم');
    assert.equal(viaForm.querySelector(`a[data-rec-order-inbox="${ORD3}"]`).getAttribute('href'), 'admin.html#inbox', 'بررسی در صندوق پیام‌ها');
    assert.doesNotMatch(row, /پرداخت تأییدشده/, 'رسید به‌تنهایی پرداخت تأییدشده نشان داده نمی‌شود');
    const receipt = app.doc.querySelector(`[data-rec-order-row="${ORD1}"] a[href$="/receipt"]`);
    assert.ok(receipt && receipt.getAttribute('href') === `/api/admin/recording-orders/${ORD1}/receipt`, 'رسید فقط از نقطهٔ مجوزدار سرور');
    const csv = app.doc.querySelector('[data-rec-order-export]');
    assert.ok(csv, 'خروجی CSV برای finance'); assert.match(csv.getAttribute('href'), /format=csv/);
    app.click(`[data-rec-order-detail="${ORD1}"]`);
    await app.until(() => /رسید بررسی شد/.test(app.body()), 'تاریخچه از سرور');
    app.click(`[data-rec-order-decide="approve"][data-rec-id="${ORD1}"]`);
    await app.until(() => app.calls.some((c) => c.method === 'POST' && c.path === `/api/admin/recording-orders/${ORD1}/decision`), 'درخواست تصمیم');
    const decision = app.calls.find((c) => c.path.endsWith('/decision'));
    assert.deepEqual(JSON.parse(decision.body), { decision: 'approve', reason: 'دلیل آزمایشی' });
    await app.until(() => /پرداخت تأیید و دسترسی خریدار فعال شد/.test(app.body()), 'پیام موفقیت پس از پاسخ سرور');
    app.click('[data-rec-order-filter="paid"]');
    await app.until(() => app.doc.querySelector(`[data-rec-order-row="${ORD2}"]`) && app.doc.querySelector(`[data-rec-order-row="${ORD1}"]`), 'پرداخت‌شده‌ها');
    assert.match(app.doc.querySelector(`[data-rec-order-row="${ORD1}"]`).textContent, /بررسی دستی/);
    assert.match(app.doc.querySelector(`[data-rec-order-row="${ORD2}"]`).textContent, /کیف پول بله/);
    assert.ok(app.doc.querySelector(`[data-rec-order-refund="${ORD2}"]`), 'بازپرداخت فقط برای پرداخت‌شده');
    app.click(`[data-rec-order-refund="${ORD2}"]`);
    await app.until(() => app.calls.some((c) => c.path.endsWith('/refund')), 'درخواست بازپرداخت');
    assert.deepEqual(JSON.parse(app.calls.find((c) => c.path.endsWith('/refund')).body), { reference: 'دلیل آزمایشی', reason: 'دلیل آزمایشی' });
    await app.until(() => !app.doc.querySelector(`[data-rec-order-row="${ORD2}"]`), 'بازپرداخت‌شده دیگر در فیلتر پرداخت‌شده نیست');
    app.click('[data-rec-order-filter="closed"]');
    await app.until(() => app.doc.querySelector(`[data-rec-order-row="${ORD2}"]`) && /بازپرداخت‌شده/.test(app.doc.querySelector(`[data-rec-order-row="${ORD2}"]`).textContent), 'بسته‌شده‌ها');
    assert.match(app.doc.querySelector(`[data-rec-order-row="${ORD2}"]`).textContent, /لغوشده/, 'دسترسی پس از بازپرداخت لغو شده است');
    app.noLeak();
  } finally { app.close(); }
}

console.log('— بازپرداخت بدون شمارهٔ پیگیری: هیچ درخواستی فرستاده نمی‌شود —');
{
  const app = await loadPanel({ role: 'owner', sec: 'events', promptValue: '' });
  try {
    await app.openEvent();
    app.click('[data-ei-tab="orders"]');
    await app.until(() => app.doc.querySelector(`[data-rec-order-row="${ORD1}"]`), 'سفارش‌ها');
    app.click('[data-rec-order-filter="paid"]');
    await app.until(() => app.doc.querySelector(`[data-rec-order-refund="${ORD2}"]`), 'پرداخت‌شده');
    app.click(`[data-rec-order-refund="${ORD2}"]`);
    await delay(80);
    assert.ok(!app.calls.some((c) => c.path.endsWith('/refund')), 'بدون شمارهٔ پیگیری درخواست بازپرداخت نمی‌رود');
    app.click('[data-rec-order-filter="review"]');
    await app.until(() => app.doc.querySelector(`[data-rec-order-decide="reject"][data-rec-id="${ORD1}"]`), 'نیازمند بررسی');
    app.click(`[data-rec-order-decide="reject"][data-rec-id="${ORD1}"]`);
    await delay(80);
    assert.ok(!app.calls.some((c) => c.path.endsWith('/decision')), 'تصمیم بدون دلیل فرستاده نمی‌شود');
  } finally { app.close(); }
}

console.log('— داشبورد: خلاصهٔ فروش فقط از API؛ مدیر بدون finance: بدون بازپرداخت/CSV؛ ۴۰۳ صادقانه —');
{
  const app = await loadPanel({ role: 'owner', sec: 'dash' });
  try {
    await app.until(() => app.doc.querySelector('[data-rec-summary]') && /دسترسی فعال/.test(app.doc.querySelector('[data-rec-summary]').textContent), 'کارت خلاصه');
    const card = app.doc.querySelector('[data-rec-summary]').textContent;
    assert.match(card, /۴/); assert.match(card, /۲/);
    assert.ok(app.calls.some((c) => c.path === '/api/admin/recordings/summary'));
    app.click('[data-rec-open-orders]');
    await app.until(() => app.doc.querySelector(`[data-rec-order-row="${ORD1}"]`), 'کارتابل همهٔ رویدادها');
    assert.doesNotMatch(app.calls.filter((c) => c.path.startsWith('/api/admin/recording-orders?')).pop().path, /event_id=/, 'کارتابل سراسری بدون فیلتر رویداد');
  } finally { app.close(); }
  const mgr = await loadPanel({ role: 'manager', sec: 'events' });
  try {
    await mgr.openEvent();
    mgr.click('[data-ei-tab="orders"]');
    await mgr.until(() => mgr.doc.querySelector(`[data-rec-order-row="${ORD1}"]`), 'سفارش‌ها برای مدیر');
    assert.ok(mgr.doc.querySelector(`[data-rec-order-decide="approve"][data-rec-id="${ORD1}"]`), 'مدیر با receipt_approve تصمیم می‌گیرد');
    assert.equal(mgr.doc.querySelector('[data-rec-order-export]'), null, 'CSV فقط finance');
    mgr.click('[data-rec-order-filter="paid"]');
    await mgr.until(() => mgr.doc.querySelector(`[data-rec-order-row="${ORD2}"]`), 'پرداخت‌شده');
    assert.equal(mgr.doc.querySelector(`[data-rec-order-refund="${ORD2}"]`), null, 'بازپرداخت فقط finance');
    assert.equal(mgr.doc.querySelector('[data-rec-summary]'), null);
  } finally { mgr.close(); }
  const limited = await loadPanel({ role: 'manager', sec: 'events', permissions: ['ev_create', 'ev_publish', 'receipt_approve', 'us_view'] });
  try {
    await limited.openEvent();
    limited.click('[data-ei-tab="orders"]');
    await limited.until(() => limited.doc.querySelector(`[data-rec-order-row="${ORD1}"]`), 'سفارش‌ها');
    limited.dom.window.fetch = (() => { const orig = limited.dom.window.fetch; return async (u, o) => { const r = await orig(u, o); return String(u).endsWith('/decision') ? reply(403, { detail: 'permission_denied' }) : r; }; })();
    limited.click(`[data-rec-order-decide="approve"][data-rec-id="${ORD1}"]`);
    await limited.until(() => /مجوز/.test(limited.body()), 'پیام ۴۰۳');
    assert.doesNotMatch(limited.body(), /دسترسی خریدار فعال شد/, 'بدون موفقیت ساختگی');
  } finally { limited.close(); }
}

console.log('— مسیرهای نام‌دار مرجع (#money، #club، #att) در حالت سرور به مقصد واقعی می‌روند —');
{
  /* ممیزی ۱۴۰۵/۰۸/۰۱ ردیف A8: `#money` برای دارندهٔ مجوز سفارش‌ها = کارتابل سفارش‌های ضبط‌شده (همهٔ رویدادها)، نه صفحهٔ «API متصل نشده» و نه تنظیمات قفل‌شده. */
  const mgr = await loadPanel({ role: 'manager', sec: 'dash' });
  try {
    await mgr.until(() => mgr.doc.querySelector('#admNav [data-sec="events"]'), 'ناوبری');
    mgr.dom.window.location.hash = '#money';
    await mgr.until(() => mgr.doc.querySelector('[data-ei-tab="orders"].on'), 'زبانهٔ سفارش‌ها پس از #money');
    await mgr.until(() => mgr.doc.querySelector(`[data-rec-order-row="${ORD1}"]`), 'سفارش‌ها بارگذاری شد');
    assert.doesNotMatch(mgr.body(), /API مدیریتی این بخش هنوز به پنل متصل نشده/, 'مسیر مرده نیست');
    assert.doesNotMatch(mgr.calls.filter((c) => c.path.startsWith('/api/admin/recording-orders?')).pop().path, /event_id=/, 'کارتابل سراسری');
    /* اصلاح هش با history.replaceState در jsdom روی file:// ممکن نیست؛ در مرورگر واقعی بررسی می‌شود. */
  } finally { mgr.close(); }
  /* بدون مجوز سفارش/گزارش: داشبورد می‌ماند و هیچ API مالی صدا زده نمی‌شود. */
  const noFin = await loadPanel({ role: 'manager', sec: 'dash', permissions: ['us_view'] });
  try {
    await noFin.until(() => noFin.doc.querySelector('#admNav [data-sec="users"]'), 'ناوبری');
    noFin.dom.window.location.hash = '#money';
    await delay(80);
    assert.ok(noFin.doc.querySelector('#admNav [data-sec="dash"].on'), 'بی‌مجوز روی داشبورد می‌ماند');
    assert.equal(noFin.calls.some((c) => c.path.startsWith('/api/admin/recording-orders')), false, 'بدون مجوز، API سفارش‌ها صدا زده نمی‌شود');
    assert.doesNotMatch(noFin.body(), /API مدیریتی این بخش هنوز به پنل متصل نشده/);
    noFin.dom.window.location.hash = '#club';
    await delay(80);
    assert.ok(noFin.doc.querySelector('#admNav [data-sec="dash"].on'), '#club بدون سرپرستی باشگاه → داشبورد');
    assert.equal(noFin.calls.some((c) => c.path.startsWith('/api/admin/club')), false, 'API باشگاه صدا زده نمی‌شود');
  } finally { noFin.close(); }
  /* مالک: #club → مدیریت باشگاه، #att → حضور و غیاب. */
  const own = await loadPanel({ role: 'owner', sec: 'dash' });
  try {
    await own.until(() => own.doc.querySelector('#admNav [data-sec="users"]'), 'ناوبری');
    own.dom.window.location.hash = '#club';
    await delay(80);
    assert.ok(own.doc.querySelector('#admNav [data-sec="users"].on'), '#club → بخش کاربران');
    assert.ok(own.doc.querySelector('[data-uv=""], [data-uback], .hub-tabs'), 'نمای داخلی کاربران باز است');
    own.dom.window.location.hash = '#att';
    await delay(80);
    assert.ok(own.doc.querySelector('#admNav [data-sec="users"].on'), '#att → بخش کاربران');
  } finally { own.close(); }
}

console.log('admin-recordings.test.mjs: همهٔ بررسی‌ها گذشت');
