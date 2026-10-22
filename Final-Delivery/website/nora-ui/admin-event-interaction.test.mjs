/* فاز ۸ — پنل: منابع، پرسش‌وپاسخ، دیدگاه‌ها و گزارش‌های رویداد با نشست سروری ساختگی.
   fetch با مسیر دقیق شبیه‌سازی می‌شود؛ هیچ سروری اجرا نمی‌شود و هیچ پیامی فرستاده نمی‌شود.
   مجوز واقعی در سرور است؛ این‌جا فقط سنجیده می‌شود که پنل همان API را درست و صادقانه صدا می‌زند و بازتاب می‌دهد. */
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
const EV = 'ev-qa-phase8';
const RES_FILE = '11111111-1111-4111-8111-111111111111';
const RES_YT = '33333333-3333-4333-8333-333333333399';
const RES_NEW = '11111111-1111-4111-8111-222222222222';
const Q1 = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const Q2 = 'aaaaaaaa-aaaa-4aaa-8aaa-bbbbbbbbbbbb';
const RV1 = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const RP1 = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';

function makeState() {
  return {
    resources: [{ id: RES_FILE, event_id: EV, kind: 'file', title: 'جزوهٔ جلسه', description: '', access: 'registered', status: 'draft', publish_at: null, live: false,
      publisher: '', file_name: '', content_type: '', size: 0, content_hash: '', sort_order: 0, link_url: '', created_by_kind: 'owner', created_at: '2026-10-20T06:00:00+00:00', updated_at: '2026-10-20T06:00:00+00:00', removed_at: null, removed_reason: '',
      storage: { backend: 'local_disk', state: 'empty' } }],
    questions: [
      { id: Q1, event_id: EV, event_title: 'کارگاه آزمایشی', author: 'مینا ر.', mine: false, body: 'ساعت شروع دقیقاً چند است؟', status: 'pending', answered: false, answer: '', answer_official: false, answer_label: '', answered_at: null,
        created_at: '2026-10-20T07:00:00+00:00', updated_at: '2026-10-20T07:00:00+00:00', reported: false, moderation_reason: '', moderated_by_kind: '', moderated_at: null, answered_by_kind: '', notification: null, open_reports: 1 },
      { id: Q2, event_id: EV, event_title: 'کارگاه آزمایشی', author: 'امید ن.', mine: false, body: 'پارکینگ دارد؟', status: 'published', answered: true, answer: 'بله، پارکینگ عمومی روبه‌رو.', answer_official: true, answer_label: 'برگزارکننده', answered_at: '2026-10-20T08:00:00+00:00',
        created_at: '2026-10-19T07:00:00+00:00', updated_at: '2026-10-20T08:00:00+00:00', reported: false, moderation_reason: '', moderated_by_kind: '', moderated_at: null, answered_by_kind: 'owner',
        notification: { id: 'n-1', state: 'failed', delivery_status: 'failed', attempts: 3, last_error: 'provider_delivery_failed', has_bale_target: true, created_at: '2026-10-20T08:00:00+00:00', delivered_at: null }, open_reports: 0 },
    ],
    reviews: [{ id: RV1, event_id: EV, event_title: 'کارگاه آزمایشی', author: 'سارا ک.', mine: false, verified_attendee: true, body: 'کارگاه بسیار مفیدی بود.', status: 'pending', edited: false, edit_count: 0,
      created_at: '2026-10-20T09:00:00+00:00', updated_at: '2026-10-20T09:00:00+00:00', reported: false, response_id: 'r-1', moderation_reason: '', moderated_by_kind: '', moderated_at: null, open_reports: 0 }],
    reports: [{ id: RP1, event_id: EV, event_title: 'کارگاه آزمایشی', target_kind: 'question', target_id: Q1, excerpt: 'ساعت شروع دقیقاً چند است؟', reason: 'تبلیغاتی', status: 'open', resolution_note: '', resolved_by_kind: '', resolved_at: null, created_at: '2026-10-20T10:00:00+00:00' }],
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
        calls.push({ path, method, headers, body: typeof options.body === 'string' ? options.body : null, raw: options.body });
        const json = () => { try { return JSON.parse(options.body || '{}'); } catch (_) { return {}; } };
        const guard = (perm) => {
          if (!has(perm)) return reply(403, { detail: 'permission_denied' });
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
          const item = { id: EV, t: 'کارگاه آزمایشی', status: 'published', kind: 'کارگاه', on: '1405/08/12', updated_at: '2026-10-20T06:00:00+00:00', forms: [{ id: 'form-1' }] };
          return reply(200, { items: [item], total: 1, counts: {}, limit: 20, offset: 0, has_more: false, kind: 'events', version: 1, source: 'site_content', can_edit: has('ev_create'), can_publish: has('ev_publish') });
        }
        if (path === '/api/admin/event-interaction/summary') {
          const g = guard('ev_publish'); if (g) return g;
          return reply(200, { source: 'shared_server_database', unanswered_questions: state.questions.filter((q) => !q.answered).length, pending_reviews: state.reviews.filter((r) => r.status === 'pending').length,
            open_reports: state.reports.filter((r) => r.status === 'open').length, failed_notifications: 1, per_event: [] });
        }
        let m = path.match(/^\/api\/admin\/events\/([^/]+)\/resources(?:\/([^/?]+))?(\/file|\/remove)?(?:\?(.*))?$/);
        if (m) {
          const g = guard('ev_create'); if (g) return g;
          const [, eventId, rid, action, query] = m;
          if (eventId !== EV) return reply(404, { detail: 'content_record_not_found' });
          if (!rid && method === 'GET') {
            const includeRemoved = /include_removed=true/.test(query || '');
            const items = state.resources.filter((r) => includeRemoved || r.status !== 'removed');
            /* فاز ۹.۴: کلیدهای واقعی پاسخ سرور — سقف از سرور، وضعیت حافظهٔ خصوصی بدون مسیر فیزیکی */
            return reply(200, { source: 'shared_server_database', event_id: EV, items, total: items.length,
              limits: { max_bytes: 536870912, inline_max_bytes: 8388608, content_types: ['application/pdf'],
                storage: { configured: true, backend: 'local_disk', max_bytes: 536870912, free_bytes: 19327352832, writable: true } } });
          }
          if (!rid && method === 'POST') {
            const sent = json();
            if (!sent.title || sent.title.length < 2) return reply(422, { detail: { code: 'text_required', field: 'title' } });
            if (sent.kind === 'link' && !/^https:\/\//.test(sent.link_url || '')) return reply(422, { detail: { code: 'invalid_link', field: 'link_url' } });
            /* ۹.۱ §۳: آینهٔ قواعد backend/video_sources.py — فقط شناسهٔ معتبر؛ HTML و میزبان بیگانه ۴۲۲ */
            let video = null;
            if (sent.kind === 'youtube' || sent.kind === 'aparat') {
              const raw = String(sent.link_url || '');
              if (/[<>"']/.test(raw)) return reply(422, { detail: { code: 'html_not_allowed', field: 'link_url' } });
              const yt = raw.match(/^(?:https?:\/\/(?:www\.|m\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)|)([A-Za-z0-9_-]{11})(?:[?&#/].*)?$/);
              const ap = raw.match(/^(?:https?:\/\/(?:www\.)?aparat\.com\/v\/|)([A-Za-z0-9]{3,24})(?:[?&#/].*)?$/);
              if (/^https?:\/\//.test(raw) && !/^https?:\/\/(?:www\.|m\.)?(?:youtube\.com|youtu\.be|aparat\.com)\//.test(raw)) return reply(422, { detail: { code: 'unsupported_video_host', field: 'link_url' } });
              if (sent.kind === 'youtube' && !yt) return reply(422, { detail: { code: 'invalid_video_id', field: 'link_url' } });
              if (sent.kind === 'aparat' && !ap) return reply(422, { detail: { code: 'invalid_video_id', field: 'link_url' } });
              video = sent.kind === 'youtube'
                ? { provider: 'youtube', video_id: yt[1], watch_url: 'https://www.youtube.com/watch?v=' + yt[1], embed_url: 'https://www.youtube-nocookie.com/embed/' + yt[1] + '?rel=0&modestbranding=1&playsinline=1', frame_origin: 'https://www.youtube-nocookie.com' }
                : { provider: 'aparat', video_id: ap[1], watch_url: 'https://www.aparat.com/v/' + ap[1], embed_url: 'https://www.aparat.com/video/video/embed/videohash/' + ap[1] + '/vt/frame', frame_origin: 'https://www.aparat.com' };
            }
            const row = { ...state.resources[0], id: state.nextId || RES_NEW, kind: sent.kind || 'file', title: sent.title, description: sent.description || '', access: sent.access || 'public', status: 'draft', link_url: video ? video.watch_url : (sent.link_url || ''), publisher: sent.publisher || '', video, delivery: video ? 'view' : (sent.delivery || 'download') };
            state.resources.push(row);
            return reply(201, row);
          }
          const row = state.resources.find((r) => r.id === rid);
          if (!row) return reply(404, { detail: 'resource_not_found' });
          if (action === '/file' && method === 'PUT') {
            if (identity.rejectFile) return reply(415, { detail: { code: 'file_type_not_allowed' } });
            row.file_name = decodeURIComponent(String(headers['X-File-Name'] || '')); row.size = options.body && options.body.size || 1; row.content_type = 'application/pdf'; row.content_hash = 'abc';
            row.storage = { backend: 'local_disk', state: identity.fileVanishes ? 'missing' : 'ready' };
            return reply(200, row);
          }
          if (action === '/remove' && method === 'POST') {
            const sent = json();
            if (!sent.reason) return reply(422, { detail: { code: 'text_required', field: 'reason' } });
            row.status = 'removed'; row.removed_reason = sent.reason; row.removed_at = '2026-10-21T00:00:00+00:00';
            return reply(200, row);
          }
          if (!action && method === 'PUT') {
            const sent = json();
            if (sent.status === 'published' && row.kind === 'file' && !row.size) return reply(409, { detail: { code: 'resource_file_missing' } });
            Object.assign(row, sent); if (sent.status === 'published') row.live = true;
            return reply(200, row);
          }
          return reply(404, { detail: 'not_found' });
        }
        m = path.match(/^\/api\/admin\/events\/([^/]+)\/questions(?:\/([^/?]+))?(\/answer|\/status|\/resend-notification)?(?:\?(.*))?$/);
        if (m) {
          const [, eventId, qid, action, query] = m;
          if (eventId !== EV) return reply(404, { detail: 'content_record_not_found' });
          if (!qid) {
            const g = guard('ev_create'); if (g && !has('ev_publish')) return g;
            const p = new URLSearchParams(query || '');
            let items = state.questions.slice();
            if (p.get('status')) items = items.filter((q) => q.status === p.get('status'));
            if (p.get('answered') === 'false') items = items.filter((q) => !q.answered);
            if (p.get('answered') === 'true') items = items.filter((q) => q.answered);
            return reply(200, { source: 'shared_server_database', event_id: EV, items, total: items.length, limit: 20, offset: 0 });
          }
          const g = guard('ev_publish'); if (g) return g;
          const row = state.questions.find((q) => q.id === qid);
          if (!row) return reply(404, { detail: 'question_not_found' });
          const sent = json();
          if (action === '/answer') {
            if (Object.keys(sent).some((k) => !['answer', 'official', 'publish', 'label'].includes(k))) return reply(422, { detail: { code: 'unexpected_fields' } });
            if (!sent.answer) return reply(422, { detail: { code: 'text_required', field: 'answer' } });
            row.answer = sent.answer; row.answered = true; row.answer_official = sent.official !== false; row.answered_at = '2026-10-21T00:00:00+00:00'; row.answer_label = 'برگزارکننده';
            if (sent.publish !== false) row.status = 'published';
            row.notification = { id: 'n-2', state: 'failed', delivery_status: 'failed', attempts: 0, last_error: 'no_bale_identity', has_bale_target: false, created_at: '2026-10-21T00:00:00+00:00', delivered_at: null };
            return reply(200, row);
          }
          if (action === '/status') {
            if (sent.status === 'hidden' && !sent.reason) return reply(422, { detail: { code: 'text_required', field: 'reason' } });
            row.status = sent.status; row.moderation_reason = sent.reason || '';
            return reply(200, row);
          }
          if (action === '/resend-notification') {
            if (!row.answered) return reply(409, { detail: { code: 'question_not_answered' } });
            row.notification = { ...row.notification, state: 'queued', delivery_status: 'queued', attempts: 0, last_error: null };
            return reply(200, row);
          }
          return reply(404, { detail: 'not_found' });
        }
        if (path.startsWith('/api/admin/event-questions')) {
          const items = state.questions.filter((q) => !q.answered);
          return reply(200, { source: 'shared_server_database', items, total: items.length, limit: 20, offset: 0 });
        }
        m = path.match(/^\/api\/admin\/events\/([^/]+)\/reviews(?:\/([^/?]+))?(\/status)?(?:\?(.*))?$/);
        if (m) {
          const [, eventId, rid, action, query] = m;
          if (eventId !== EV) return reply(404, { detail: 'content_record_not_found' });
          if (!rid) {
            const p = new URLSearchParams(query || '');
            let items = state.reviews.slice();
            if (p.get('status')) items = items.filter((r) => r.status === p.get('status'));
            return reply(200, { source: 'shared_server_database', event_id: EV, items, total: items.length, limit: 20, offset: 0 });
          }
          const g = guard('ev_publish'); if (g) return g;
          const row = state.reviews.find((r) => r.id === rid);
          const sent = json();
          if (sent.status === 'hidden' && !sent.reason) return reply(422, { detail: { code: 'text_required', field: 'reason' } });
          row.status = sent.status; row.moderation_reason = sent.reason || '';
          return reply(200, row);
        }
        m = path.match(/^\/api\/admin\/event-reports(?:\/([^/?]+)\/resolve)?(?:\?(.*))?$/);
        if (m) {
          const g = guard('ev_publish'); if (g) return g;
          const [, rid, query] = m;
          if (!rid) {
            const p = new URLSearchParams(query || '');
            let items = state.reports.filter((r) => r.status === (p.get('status') || 'open'));
            if (p.get('event_id')) items = items.filter((r) => r.event_id === p.get('event_id'));
            return reply(200, { source: 'shared_server_database', items, total: items.length, limit: 20, offset: 0 });
          }
          const row = state.reports.find((r) => r.id === rid); const sent = json();
          row.status = sent.status; row.resolution_note = sent.note || '';
          return reply(200, row);
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
  const setField = (sel, value) => {
    const el = doc.querySelector(sel); assert.ok(el, `فیلد پیدا نشد: ${sel}`);
    el.value = value; el.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  };
  const body = () => doc.querySelector('#admBody').textContent;
  const noLeak = () => {
    assert.doesNotMatch(body(), /0912|09\d{9}|hash|token|password/i, 'شماره، هش یا توکن در خروجی پنل نیست');
    assert.doesNotMatch(body(), /سارا محمدی|NL-1024|جلسهٔ شعر و موسیقی/, 'دادهٔ نمونهٔ محلی با دادهٔ سرور قاطی نمی‌شود');
  };
  const pickFile = (sel, name, type, bytes) => {
    const input = doc.querySelector(sel); assert.ok(input, `ورودی فایل پیدا نشد: ${sel}`);
    const file = new dom.window.File([bytes || new Uint8Array(64)], name, { type });
    Object.defineProperty(input, 'files', { configurable: true, value: [file] });
    input.dispatchEvent(new dom.window.Event('change', { bubbles: true }));
  };
  return { dom, doc, calls, click, setField, until, body, noLeak, pickFile, prompts, state, close: () => dom.window.close() };
}

console.log('— مالک: ورود از ردیف رویداد، منابع (ساخت، بارگذاری، انتشار، حذف با دلیل) —');
{
  const app = await loadPanel({ role: 'owner', sec: 'events' });
  try {
    await app.until(() => app.doc.querySelector(`[data-ct-interaction="${EV}"]`), 'دکمهٔ منابع و پرسش‌ها در ردیف رویداد');
    assert.ok(app.doc.querySelector('[data-ei-open-all]'), 'دکمهٔ کارتابل بی‌پاسخ‌ها در بالای فهرست رویدادها');
    app.click(`[data-ct-interaction="${EV}"]`);
    await app.until(() => app.doc.querySelector('[data-ei-panel]') && app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"]`), 'پنل منابع');
    assert.ok(app.calls.some((c) => c.path === `/api/admin/events/${EV}/resources`), 'فهرست منابع از API همان رویداد');
    assert.match(app.body(), /کارگاه آزمایشی/);
    assert.match(app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"]`).textContent, /پیش‌نویس/);
    assert.match(app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"]`).textContent, /بدون فایل/);
    /* فاز ۹.۴: وضعیت ذخیره‌سازی و سقف از سرور، نه از عدد ثابت پنل؛ هیچ مسیر فیزیکی نمایش داده نمی‌شود */
    assert.equal(app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"] [data-ei-res-storage]`).getAttribute('data-ei-res-storage'), 'empty');
    assert.ok(app.doc.querySelector('[data-ei-storage="local_disk"]'), 'خلاصهٔ حافظهٔ خصوصی دیسک');
    assert.match(app.doc.querySelector('[data-ei-storage="local_disk"]').textContent, /۵۱۲ مگابایت/, 'سقف ۵۱۲ مگابایت از پاسخ سرور');
    assert.match(app.doc.querySelector('[data-ei-storage="local_disk"]').textContent, /بیرون ریشهٔ وب/);
    assert.doesNotMatch(app.body(), /\/var\/|\/srv\/|private-store/, 'مسیر فیزیکی هرگز در پنل نیست');

    /* انتشار پیش از بارگذاری فایل: سرور ۴۰۹ می‌دهد و پنل پیام انسانی نشان می‌دهد */
    app.click(`[data-ei-res-status="published"][data-ei-id="${RES_FILE}"]`);
    await app.until(() => /پیش از انتشار باید فایل منبع بارگذاری شود/.test(app.body()), 'خطای ۴۰۹ انسانی');

    /* بارگذاری فایل: PUT خام به نقطهٔ همان منبع با نام درصدکدشده و CSRF */
    app.pickFile(`[data-ei-file="${RES_FILE}"]`, 'جزوه نجوم.pdf', 'application/pdf');
    await app.until(() => app.calls.some((c) => c.method === 'PUT' && c.path === `/api/admin/events/${EV}/resources/${RES_FILE}/file`), 'درخواست بارگذاری');
    const up = app.calls.find((c) => c.method === 'PUT' && c.path.endsWith('/file'));
    assert.equal(up.headers['X-CSRF-Token'], 'owner-csrf');
    assert.match(String(up.headers['X-File-Name']), /^[A-Za-z0-9%._-]+$/, 'نام فایل در سرآیند ASCII (درصدکدشده) است');
    assert.equal(decodeURIComponent(up.headers['X-File-Name']), 'جزوه نجوم.pdf');
    await app.until(() => /در سرور ذخیره شد/.test(app.body()) && /جزوه نجوم\.pdf/.test(app.body()), 'بازتاب فایل ذخیره‌شده');
    await app.until(() => app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"] [data-ei-res-storage="ready"]`), 'برچسب «فایل آماده» پس از بارگذاری');
    assert.match(app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"] [data-ei-res-storage="ready"]`).textContent, /روی دیسک خصوصی سرور/);

    /* اکنون انتشار */
    app.click(`[data-ei-res-status="published"][data-ei-id="${RES_FILE}"]`);
    await app.until(() => app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"]`) && /منتشرشده/.test(app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"]`).textContent), 'منبع منتشر شد');
    const pub = app.calls.filter((c) => c.method === 'PUT' && c.path === `/api/admin/events/${EV}/resources/${RES_FILE}`).pop();
    assert.deepEqual(JSON.parse(pub.body), { status: 'published' }, 'تغییر وضعیت فقط همان فیلد را می‌فرستد');

    /* منبع تازه از نوع پیوند با خطای اعتبارسنجی فیلد از سرور */
    app.click('[data-ei-res-new]');
    await app.until(() => app.doc.querySelector('[data-ei-res-editor]'), 'ویرایشگر منبع');
    app.setField('#eif_kind', 'link');
    await app.until(() => app.doc.querySelector('#eif_link_url'), 'فیلد پیوند');
    app.setField('#eif_title', 'پیوند جلسهٔ برخط');
    app.setField('#eif_access', 'attended');
    app.setField('#eif_link_url', 'http://insecure.example');
    app.click('[data-ei-res-save]');
    await app.until(() => /پیوند باید با https/.test(app.body()), 'خطای فیلد پیوند از سرور کنار فیلد');
    app.setField('#eif_link_url', 'https://example.org/live');
    app.click('[data-ei-res-save]');
    await app.until(() => app.doc.querySelector(`[data-ei-res-row="${RES_NEW}"]`), 'منبع تازه در فهرست');
    const created = app.calls.find((c) => c.method === 'POST' && c.path === `/api/admin/events/${EV}/resources` && /https:\/\/example\.org/.test(c.body || ''));
    assert.ok(created, 'ساخت منبع پیوند');
    assert.equal(JSON.parse(created.body).access, 'attended');
    assert.match(app.doc.querySelector(`[data-ei-res-row="${RES_NEW}"]`).textContent, /حاضران تأییدشده/);

    /* ۹.۱ §۳: منبع ویدیوی یوتیوب/آپارات — فقط نشانی/شناسه، خطاهای سرور کنار فیلد، پیش‌نمایش واقعی از نشانی رسمی */
    app.state.nextId = RES_YT;
    app.click('[data-ei-res-new]');
    await app.until(() => app.doc.querySelector('[data-ei-res-editor]'), 'ویرایشگر منبع (ویدیو)');
    assert.deepEqual(Array.from(app.doc.querySelector('#eif_kind').options).map((o) => o.value), ['file', 'youtube', 'aparat', 'link'], 'سه منبع ویدیو + پیوند؛ هیچ گزینهٔ «کد embed»');
    app.setField('#eif_kind', 'youtube');
    await app.until(() => app.doc.querySelector('#eif_link_url'), 'فیلد نشانی ویدیو');
    assert.match(app.body(), /DRM ندارد/, 'هشدار صادقانه: جاسازی بیرونی میزبانی خصوصی نیست');
    app.setField('#eif_title', 'ویدیوی یوتیوب جلسه');
    app.setField('#eif_link_url', '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe>');
    app.click('[data-ei-res-save]');
    await app.until(() => /کد HTML یا iframe پذیرفته نمی‌شود/.test(app.body()), 'خطای html_not_allowed کنار فیلد');
    app.setField('#eif_link_url', 'https://evil.example/watch?v=dQw4w9WgXcQ');
    app.click('[data-ei-res-save]');
    await app.until(() => /فقط نشانی‌های youtube\.com/.test(app.body()), 'خطای unsupported_video_host کنار فیلد');
    app.setField('#eif_link_url', 'https://youtu.be/dQw4w9WgXcQ?si=tracking');
    app.click('[data-ei-res-save]');
    await app.until(() => app.doc.querySelector(`[data-ei-res-row="${RES_YT}"]`), 'منبع یوتیوب در فهرست');
    const ytCreated = JSON.parse(app.calls.filter((c) => c.method === 'POST' && c.path === `/api/admin/events/${EV}/resources`).pop().body);
    assert.equal(ytCreated.kind, 'youtube'); assert.equal(ytCreated.link_url, 'https://youtu.be/dQw4w9WgXcQ?si=tracking');
    assert.ok(!('embed_html' in ytCreated) && !('embed_url' in ytCreated), 'پنل فقط نشانی خام را می‌فرستد؛ نشانی embed را سرور می‌سازد');
    const ytRow = app.doc.querySelector(`[data-ei-res-row="${RES_YT}"]`);
    assert.match(ytRow.textContent, /ویدیوی یوتیوب/); assert.match(ytRow.textContent, /https:\/\/www\.youtube\.com\/watch\?v=dQw4w9WgXcQ/);
    assert.equal(ytRow.querySelector('iframe'), null, 'پیش‌نمایش پیش از درخواست مدیر بارگذاری نمی‌شود');
    app.click(`[data-ei-res-preview="${RES_YT}"]`);
    await app.until(() => app.doc.querySelector(`[data-ei-video-preview="${RES_YT}"] iframe`), 'پیش‌نمایش واقعی');
    const frame = app.doc.querySelector(`[data-ei-video-preview="${RES_YT}"] iframe`);
    assert.equal(frame.getAttribute('src'), 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?rel=0&modestbranding=1&playsinline=1', 'قاب از نشانی رسمی youtube-nocookie که سرور برگردانده');
    assert.match(app.doc.querySelector(`[data-ei-res-row="${RES_YT}"]`).textContent, /غیرقابل‌جاسازی/, 'توضیح: وضعیت واقعی را خود سکو نشان می‌دهد، سرور تأیید نمی‌کند');
    app.state.nextId = '';

    /* حذف نرم با دلیل اجباری */
    app.click(`[data-ei-res-remove="${RES_NEW}"]`);
    await app.until(() => app.calls.some((c) => c.method === 'POST' && c.path === `/api/admin/events/${EV}/resources/${RES_NEW}/remove`), 'درخواست حذف');
    const removed = app.calls.find((c) => c.path.endsWith('/remove'));
    assert.deepEqual(JSON.parse(removed.body), { reason: 'دلیل آزمایشی' });
    await app.until(() => !app.doc.querySelector(`[data-ei-res-row="${RES_NEW}"]`), 'حذف‌شده در فهرست پیش‌فرض نیست');
    const chk = app.doc.querySelector('[data-ei-res-removed]'); chk.checked = true; chk.dispatchEvent(new app.dom.window.Event('change', { bubbles: true }));
    await app.until(() => app.doc.querySelector(`[data-ei-res-row="${RES_NEW}"]`) && /دلیل حذف: دلیل آزمایشی/.test(app.doc.querySelector(`[data-ei-res-row="${RES_NEW}"]`).textContent), 'حذف‌شده با دلیل، فقط با فیلتر صریح');
    assert.equal(app.doc.querySelector(`[data-ei-res-row="${RES_NEW}"] [data-ei-res-edit]`), null, 'منبع حذف‌شده دکمهٔ ویرایش ندارد');
    app.noLeak();
  } finally { app.close(); }
}

console.log('— مالک: پرسش‌وپاسخ (پاسخ + انتشار، اعلان صف ≠ تحویل، ارسال دوباره، پنهان با دلیل)، دیدگاه‌ها، گزارش‌ها —');
{
  const app = await loadPanel({ role: 'owner', sec: 'events' });
  try {
    await app.until(() => app.doc.querySelector(`[data-ct-interaction="${EV}"]`), 'فهرست رویدادها');
    app.click(`[data-ct-interaction="${EV}"]`);
    await app.until(() => app.doc.querySelector('[data-ei-tab="questions"]'), 'زبانه‌ها');
    app.click('[data-ei-tab="questions"]');
    await app.until(() => app.doc.querySelector(`[data-ei-q-row="${Q1}"]`), 'فهرست پرسش‌ها');
    assert.match(app.doc.querySelector(`[data-ei-q-row="${Q1}"]`).textContent, /بی‌پاسخ/);
    assert.match(app.doc.querySelector(`[data-ei-q-row="${Q1}"]`).textContent, /۱ گزارش باز/);
    const q2 = app.doc.querySelector(`[data-ei-q-row="${Q2}"]`).textContent;
    assert.match(q2, /پاسخ رسمی/);
    assert.match(q2, /ناموفق/);
    assert.match(q2, /provider_delivery_failed/);
    assert.doesNotMatch(q2, /تحویل‌شده/, 'اعلان ناموفق هرگز تحویل‌شده نشان داده نمی‌شود');
    assert.ok(app.doc.querySelector(`[data-ei-q-resend="${Q2}"]`), 'ارسال دوباره فقط برای اعلان تحویل‌نشده');

    /* فیلتر بی‌پاسخ */
    app.click('[data-ei-q-answered="false"]');
    await app.until(() => app.calls.some((c) => /\/questions\?.*answered=false/.test(c.path)), 'فیلتر بی‌پاسخ به سرور');
    await app.until(() => !app.doc.querySelector(`[data-ei-q-row="${Q2}"]`) && app.doc.querySelector(`[data-ei-q-row="${Q1}"]`), 'فقط بی‌پاسخ‌ها');

    /* پاسخ و انتشار */
    app.click(`[data-ei-answer-open="${Q1}"]`);
    await app.until(() => app.doc.querySelector(`[data-ei-answer-text="${Q1}"]`), 'فرم پاسخ');
    app.setField(`[data-ei-answer-text="${Q1}"]`, 'ساعت ده صبح، سالن اصلی.');
    app.click(`[data-ei-answer-send="${Q1}"]:not([data-ei-answer-publish])`);
    await app.until(() => app.calls.some((c) => c.method === 'POST' && c.path === `/api/admin/events/${EV}/questions/${Q1}/answer`), 'ارسال پاسخ');
    const ans = app.calls.find((c) => c.path.endsWith(`/questions/${Q1}/answer`));
    assert.deepEqual(JSON.parse(ans.body), { answer: 'ساعت ده صبح، سالن اصلی.', official: true, publish: true });
    assert.equal(ans.headers['X-CSRF-Token'], 'owner-csrf');
    await app.until(() => /پاسخ ثبت شد و منتشر شد/.test(app.body()), 'پیام نتیجه');
    assert.match(app.body(), /بدون هویت بلهٔ پیوندشده/, 'نبود هویت بله صادقانه گفته می‌شود');
    assert.doesNotMatch(app.body(), /تحویل‌شده/);

    /* پنهان‌کردن بدون دلیل انجام نمی‌شود */
    app.click('[data-ei-q-answered=""]');
    await app.until(() => app.doc.querySelector(`[data-ei-q-row="${Q2}"]`), 'همهٔ پرسش‌ها');
    const before = app.calls.length;
    const hideAttempt = await loadPanel({ role: 'owner', sec: 'events', promptValue: '' });
    try {
      await hideAttempt.until(() => hideAttempt.doc.querySelector(`[data-ct-interaction="${EV}"]`), 'فهرست');
      hideAttempt.click(`[data-ct-interaction="${EV}"]`);
      await hideAttempt.until(() => hideAttempt.doc.querySelector('[data-ei-tab="questions"]'), 'زبانه');
      hideAttempt.click('[data-ei-tab="questions"]');
      await hideAttempt.until(() => hideAttempt.doc.querySelector(`[data-ei-q-status="hidden"][data-ei-id="${Q2}"]`), 'دکمهٔ پنهان');
      hideAttempt.click(`[data-ei-q-status="hidden"][data-ei-id="${Q2}"]`);
      await delay(60);
      assert.equal(hideAttempt.calls.filter((c) => c.path.endsWith('/status')).length, 0, 'بدون دلیل هیچ درخواستی نمی‌رود');
    } finally { hideAttempt.close(); }
    assert.equal(app.calls.length, before);

    app.click(`[data-ei-q-status="hidden"][data-ei-id="${Q2}"]`);
    await app.until(() => app.calls.some((c) => c.path === `/api/admin/events/${EV}/questions/${Q2}/status`), 'درخواست پنهان‌کردن');
    assert.deepEqual(JSON.parse(app.calls.find((c) => c.path.endsWith(`/questions/${Q2}/status`)).body), { status: 'hidden', reason: 'دلیل آزمایشی' });
    await app.until(() => app.doc.querySelector(`[data-ei-q-row="${Q2}"]`) && /پنهان/.test(app.doc.querySelector(`[data-ei-q-row="${Q2}"]`).textContent) && /دلیل: دلیل آزمایشی/.test(app.doc.querySelector(`[data-ei-q-row="${Q2}"]`).textContent), 'وضعیت پنهان با دلیل');

    /* ارسال دوبارهٔ اعلان */
    app.click(`[data-ei-q-resend="${Q2}"]`);
    await app.until(() => app.calls.some((c) => c.path === `/api/admin/events/${EV}/questions/${Q2}/resend-notification`), 'ارسال دوباره');
    await app.until(() => /دوباره در صف قرار گرفت/.test(app.body()), 'پیام صف');
    assert.match(app.body(), /تحویل فقط پس از ارسال واقعی ربات/);
    await app.until(() => /در صف ارسال/.test(app.doc.querySelector(`[data-ei-q-row="${Q2}"]`).textContent), 'وضعیت queued');

    /* دیدگاه‌ها */
    app.click('[data-ei-tab="reviews"]');
    await app.until(() => app.doc.querySelector(`[data-ei-rv-row="${RV1}"]`), 'فهرست دیدگاه‌ها');
    assert.match(app.doc.querySelector(`[data-ei-rv-row="${RV1}"]`).textContent, /شرکت‌کنندهٔ تأییدشده/);
    assert.match(app.doc.querySelector(`[data-ei-rv-row="${RV1}"]`).textContent, /در انتظار تأیید/);
    assert.doesNotMatch(app.body(), /★|امتیاز \d|امتیازدهی/, 'هیچ امتیاز ستاره‌ای یا عددی وجود ندارد');
    app.click(`[data-ei-rv-status="published"][data-ei-id="${RV1}"]`);
    await app.until(() => app.calls.some((c) => c.path === `/api/admin/events/${EV}/reviews/${RV1}/status`), 'انتشار دیدگاه');
    assert.deepEqual(JSON.parse(app.calls.find((c) => c.path.endsWith(`/reviews/${RV1}/status`)).body), { status: 'published', reason: '' });
    await app.until(() => /منتشرشده/.test(app.doc.querySelector(`[data-ei-rv-row="${RV1}"]`).textContent), 'دیدگاه منتشر شد');

    /* گزارش‌ها */
    app.click('[data-ei-tab="reports"]');
    await app.until(() => app.doc.querySelector(`[data-ei-rp-row="${RP1}"]`), 'فهرست گزارش‌ها');
    assert.ok(app.calls.some((c) => c.path.startsWith('/api/admin/event-reports?') && /status=open/.test(c.path) && c.path.includes(`event_id=${EV}`)), 'گزارش‌ها فقط برای همین رویداد');
    assert.match(app.doc.querySelector(`[data-ei-rp-row="${RP1}"]`).textContent, /تبلیغاتی/);
    app.click(`[data-ei-rp-resolve="resolved"][data-ei-id="${RP1}"]`);
    await app.until(() => app.calls.some((c) => c.path === `/api/admin/event-reports/${RP1}/resolve`), 'رسیدگی');
    assert.deepEqual(JSON.parse(app.calls.find((c) => c.path.endsWith('/resolve')).body), { status: 'resolved', note: 'دلیل آزمایشی' });
    await app.until(() => /گزارش بازی وجود ندارد/.test(app.body()), 'فهرست باز خالی و صادقانه');
    app.noLeak();
  } finally { app.close(); }
}

console.log('— داشبورد: خلاصهٔ پرسش‌ها/گزارش‌ها و کارتابل بی‌پاسخ همهٔ رویدادها —');
{
  const app = await loadPanel({ role: 'owner', sec: 'dash' });
  try {
    await app.until(() => app.doc.querySelector('[data-ei-summary]') && /پرسش بی‌پاسخ: ۱/.test(app.body()), 'کارت خلاصه از API');
    assert.match(app.body(), /گزارش باز: ۱/);
    assert.match(app.body(), /اعلان ناموفق: ۱/);
    app.click('[data-ei-summary] [data-ei-open-all]:not([data-ei-open-all="reports"])');
    await app.until(() => app.doc.querySelector('[data-ei-panel]') && app.doc.querySelector(`[data-ei-q-row="${Q1}"]`), 'کارتابل بی‌پاسخ‌ها');
    assert.ok(app.calls.some((c) => /^\/api\/admin\/event-questions\?.*answered=false/.test(c.path)), 'فهرست بی‌پاسخ همهٔ رویدادها');
    assert.match(app.doc.querySelector(`[data-ei-q-row="${Q1}"]`).textContent, /رویداد: کارگاه آزمایشی/);
    assert.equal(app.doc.querySelector('[data-ei-tab="resources"]'), null, 'در نمای همهٔ رویدادها زبانهٔ منابع معنا ندارد');
    app.click('[data-ei-close]');
    await app.until(() => !app.doc.querySelector('[data-ei-panel]') && app.doc.querySelector(`[data-ct-interaction="${EV}"]`), 'بازگشت به فهرست رویدادها');
    app.noLeak();
  } finally { app.close(); }
}

console.log('— مدیر بدون ev_publish: فقط منابع؛ بدون دکمهٔ پاسخ/پنهان/انتشار دیدگاه؛ خلاصهٔ داشبورد نیست —');
{
  const perms = MANAGER.filter((p) => p !== 'ev_publish');
  const app = await loadPanel({ role: 'manager', sec: 'events', permissions: perms });
  try {
    await app.until(() => app.doc.querySelector(`[data-ct-interaction="${EV}"]`), 'فهرست رویدادها');
    assert.equal(app.doc.querySelector('[data-ei-open-all]'), null, 'کارتابل بی‌پاسخ‌ها برای این نقش نمایش داده نمی‌شود');
    app.click(`[data-ct-interaction="${EV}"]`);
    await app.until(() => app.doc.querySelector(`[data-ei-res-row="${RES_FILE}"]`), 'منابع');
    assert.ok(app.doc.querySelector('[data-ei-res-new]'), 'ساخت منبع با ev_create مجاز است');
    assert.equal(app.doc.querySelector('[data-ei-tab="reports"]'), null, 'زبانهٔ گزارش‌ها نیست');
    app.click('[data-ei-tab="questions"]');
    await app.until(() => app.doc.querySelector(`[data-ei-q-row="${Q1}"]`), 'پرسش‌ها خوانده می‌شوند');
    assert.equal(app.doc.querySelector('[data-ei-answer-open]'), null, 'بدون ev_publish دکمهٔ پاسخ نیست');
    assert.equal(app.doc.querySelector('[data-ei-q-status]'), null, 'بدون ev_publish دکمهٔ پنهان/انتشار نیست');
    app.click('[data-ei-tab="reviews"]');
    await app.until(() => app.doc.querySelector(`[data-ei-rv-row="${RV1}"]`), 'دیدگاه‌ها');
    assert.equal(app.doc.querySelector('[data-ei-rv-status]'), null, 'بدون ev_publish تعدیل دیدگاه نیست');
    assert.equal(app.calls.filter((c) => c.path === '/api/admin/event-interaction/summary').length, 0, 'خلاصه برای این نقش درخواست نمی‌شود');
    app.noLeak();
  } finally { app.close(); }
}

console.log('— سرور ۴۰۳ برای اقدام: پیام مجوز، بدون تغییر ظاهری دروغین —');
{
  const app = await loadPanel({ role: 'manager', sec: 'events', permissions: MANAGER.filter((p) => p !== 'ev_publish').concat(['ev_publish']) });
  try {
    await app.until(() => app.doc.querySelector(`[data-ct-interaction="${EV}"]`), 'فهرست');
    app.click(`[data-ct-interaction="${EV}"]`);
    await app.until(() => app.doc.querySelector('[data-ei-tab="questions"]'), 'زبانه');
    app.click('[data-ei-tab="questions"]');
    await app.until(() => app.doc.querySelector(`[data-ei-answer-open="${Q1}"]`), 'پرسش‌ها');
    /* مجوز را در سرور «بردار»: پاسخ ۴۰۳ باید پیام مجوز بدهد و وضعیت ردیف عوض نشود */
    app.state.questions.length; // state shared with fetch mock
    const origFetch = app.dom.window.fetch;
    app.dom.window.fetch = async (url, options) => (String(url).endsWith('/answer') ? reply(403, { detail: 'permission_denied' }) : origFetch(url, options));
    app.click(`[data-ei-answer-open="${Q1}"]`);
    await app.until(() => app.doc.querySelector(`[data-ei-answer-text="${Q1}"]`), 'فرم پاسخ');
    app.setField(`[data-ei-answer-text="${Q1}"]`, 'پاسخ آزمایشی');
    app.click(`[data-ei-answer-send="${Q1}"]:not([data-ei-answer-publish])`);
    await app.until(() => /مجوز این کار را ندارد/.test(app.body()), 'پیام ۴۰۳');
    assert.match(app.doc.querySelector(`[data-ei-q-row="${Q1}"]`).textContent, /بی‌پاسخ/, 'ردیف همچنان بی‌پاسخ است');
  } finally { app.close(); }
}

console.log('آزمون فاز ۸ پنل: قبول');
