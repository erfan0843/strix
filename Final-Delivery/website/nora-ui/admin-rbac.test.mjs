/* آزمون مسیر تولید پنل: نشست و نقش از API می‌آیند، نه نشست محلی آزمایشی. */
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const ADMIN_HTML = resolve(HERE, 'admin.html');
const delay = (ms = 10) => new Promise((resolveDelay) => setTimeout(resolveDelay, ms));

function reply(status, payload = {}) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload };
}

function rolePermissions(role) {
  const manager = [
    'ev_create', 'ev_publish', 'ev_cancel', 'attendance', 'certificate',
    'fm_create', 'fm_responses', 'fm_export', 'receipt_approve', 'us_view', 'us_edit', 'us_approve',
    'us_block', 'us_notes', 'us_export', 'sp_answer', 'sp_reopen', 'qa_audit',
    'qa_complaint', 'qa_quality', 'qa_fix', 'qa_report', 'bc_send', 'bc_event',
    'pr_media', 'pr_campaign', 'pr_invite', 'dev_course', 'dev_process', 'dev_kpi',
    'dev_review', 'rp_view', 'rp_export',
  ];
  const club = ['cl_member', 'cl_session', 'cl_cert', 'cl_content'];
  if (role === 'manager') return manager;
  if (role === 'club-supervisor') return [...manager, ...club];
  return [...manager, ...club, 'cl_dues', 'sys_points', 'finance', 'role_assign',
    'sys_fields', 'sys_settings', 'sys_backup', 'cert_final', 'user_delete', 'public_roster'];
}

async function loadProductionSession(identity) {
  const calls = [];
  const storageOps = [];
  const values = new Map([['nora-admin', JSON.stringify({ v: 78, sec: 'users', uV: 'tools', uTool: 'staff' })]]);
  const store = {
    getItem(key) { storageOps.push(['get', String(key)]); return values.has(String(key)) ? values.get(String(key)) : null; },
    setItem(key, value) { storageOps.push(['set', String(key)]); values.set(String(key), String(value)); },
    removeItem(key) { storageOps.push(['remove', String(key)]); values.delete(String(key)); },
    clear() { storageOps.push(['clear', '*']); values.clear(); },
    key(index) { return [...values.keys()][index] || null; },
    get length() { return values.size; },
  };
  const accountRoles = new Map();
  const confirmAnswers = [];
  const decidedTasks = [
    {id:'00000000-0000-4000-8000-000000000009',account_id:'acc-03',bale_user_id:'73429',kind:'receipt_review',
      payload:{amount:120000,currency:'ریال',ref_code:'R-9'},status:'rejected',version:3,
      reviewed_by:'acc-01',reviewed_at:'2026-10-02T10:00:00+00:00',review_reason:'مبلغ ناقص'},
  ];
  const auditEvents = [
    {id:1,created_at:'2026-10-03T09:00:00+00:00',actor_kind:'owner',actor_id:'owner-01',actor_role:'owner',action:'role.set',
      target_type:'account',target_id:'acc-01',outcome:'ok',details:{previous_role:null,role:'manager'}},
    {id:2,created_at:'2026-10-03T09:05:00+00:00',actor_kind:'account',actor_id:'acc-01',actor_role:'manager',action:'workflow.decide',
      target_type:'admin_task',target_id:'00000000-0000-4000-8000-000000000009',outcome:'ok',details:{kind:'receipt_review',decision:'rejected',has_reason:true}},
  ];
  let schedRuns = 0;
  let workflowTasks = [
    {id:'00000000-0000-4000-8000-000000000001',account_id:'acc-01',bale_user_id:'73421',kind:'profile_review',
      payload:{full_name:'آزمایش زنده',file_refs:['00000000-0000-4000-8000-000000000101']},
      files:[{id:'00000000-0000-4000-8000-000000000101',file_name:'profile.png',content_type:'image/png',content_size:128}],status:'pending',version:1},
    {id:'00000000-0000-4000-8000-000000000002',account_id:'acc-02',bale_user_id:'73422',kind:'receipt_review',
      payload:{amount:250000,currency:'ریال',ref_code:'R-102',file_refs:['00000000-0000-4000-8000-000000000103']},
      files:[{id:'00000000-0000-4000-8000-000000000103',file_name:'receipt.pdf',content_type:'application/pdf',content_size:12500}],
      status:'pending',version:2},
  ];
  const account = {
    authenticated: true,
    account_id: 'acc-01',
    provider: identity.provider || 'bale',
    role: identity.role,
    permissions: identity.permissions || rolePermissions(identity.role),
    manager_username: identity.provider === 'manager-password' ? 'qa.manager' : null,
  };
  const owner = {
    authenticated: true,
    owner_id: 'owner-01',
    role: 'owner',
    permissions: rolePermissions('owner'),
  };
  const ownerList = () => ({
    items: [{
      account_id: 'acc-01', provider: 'bale', provider_user_id: '73421', display_name: 'سارا آزمایشی',
      role: accountRoles.get('acc-01') || null,
      permissions: accountRoles.get('acc-01') ? rolePermissions(accountRoles.get('acc-01')) : [],
      manager_username: null,
      manager_login_enabled: false,
      created_at: '2026-10-01T08:00:00+00:00',
    }],
    limit: 50, offset: 0, has_more: false,
  });

  const dom = await JSDOM.fromFile(ADMIN_HTML, {
    runScripts: 'dangerously', resources: 'usable', pretendToBeVisual: true,
    beforeParse(window) {
      Object.defineProperty(window.navigator, 'userAgent', {
        configurable: true, value: 'ArenaBrowser/1.0',
      });
      Object.defineProperty(window, 'localStorage', { configurable: true, value: store });
      window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      window.scrollTo = () => {};
      window.confirm = (message) => { confirmAnswers.push(String(message)); return identity.confirm !== false; };
      Object.defineProperty(window.document, 'cookie', {
        configurable: true, get: () => 'nora_csrf=owner-csrf; nora_account_csrf=account-csrf',
      });
      window.fetch = async (url, options = {}) => {
        const path = String(url);
        const method = String(options.method || 'GET').toUpperCase();
        calls.push({ path, method, options });
        if (identity.apiUnavailable) return reply(404, { detail: 'not_found' });
        if (path === '/api/auth/me') {
          return identity.role === 'owner' ? reply(200, owner) : reply(401, { detail: 'authentication_required' });
        }
        if (path === '/api/account/me') {
          return identity.role === 'owner' ? reply(401, { detail: 'authentication_required' }) : reply(200, account);
        }
        if (path === '/api/health') return reply(200, { ok: true, formsEnabled: true, responsesEnabled: true });
        if (path === '/api/integrations/status') return reply(200, identity.integrationStatus || { providers: [] });
        if (path === '/api/owner/accounts?limit=50&offset=0') return reply(200, ownerList());
        if (path === '/api/owner/accounts?limit=50&offset=0&q=%D8%B3%D8%A7%D8%B1%D8%A7&role=assigned') {
          return reply(200, { ...ownerList(), q: 'سارا', items: accountRoles.get('acc-01') ? ownerList().items : [] });
        }
        const auditPath = path.match(/^\/api\/owner\/audit\?limit=30&offset=0(?:&action=([a-z_.]*))?$/);
        if (auditPath) {
          if (identity.role !== 'owner') return reply(401, { detail: 'authentication_required' });
          const prefix = auditPath[1] || '';
          return reply(200, { items: auditEvents.filter(ev => ev.action.startsWith(prefix)), limit: 30, offset: 0, has_more: false, actions: [] });
        }
        if (path === '/api/owner/site-content') return reply(200, { content: {}, version: 0, updated_at: null });
        if (path === '/api/forms') return reply(200, { items: [] });
        if (path === '/api/cooperation-requests?limit=50&offset=0') return reply(200, { items: [], total: 0 });
        if (path === '/api/admin/inbox?limit=50&offset=0') return reply(200, { items: workflowTasks, has_more: false, status: 'pending' });
        if (path === '/api/admin/inbox?limit=50&offset=0&status=decided') return reply(200, { items: decidedTasks, has_more: false, status: 'decided' });
        const reportPath = path.match(/^\/api\/admin\/reports\/summary\?period=(7d|30d|90d|365d|all)$/);
        if (reportPath) return reply(200, {
          source:'shared_server_database', period:reportPath[1], generated_at:'2026-10-01T08:00:00+00:00',
          forms:{total:3,created_in_period:1,by_status:{published:2,draft:1}},
          responses:{total:8,by_status:{accepted:6,waitlisted:2}},
          accounts:{total:12,by_role:{manager:2,'club-supervisor':1}},
          reviews:{total:4,by_kind:{profile_review:{pending:1,approved:2},receipt_review:{pending:1}}},
          notifications:{total:5,by_delivery_status:{delivered:4,pending:1}},
          cooperation_requests:{total:2,by_status:{new:2}},
        });
        /* Phase 9.4 §8: global outbox list — the stub mirrors the real response keys (no raw bale_user_id). */
        const outboxPath = path.match(/^\/api\/admin\/notifications(?:\?(.*))?$/);
        if (outboxPath) {
          if (identity.outboxForbidden) return reply(403, { detail: 'permission_denied' });
          const params = new URLSearchParams(outboxPath[1] || '');
          const all = [
            { id: '10000000-0000-4000-8000-000000000001', kind: 'recording_access', title: 'دسترسی فعال شد', body: 'دسترسی شما فعال شد.', created_at: '2026-10-22T08:00:00+00:00', delivery_status: 'pending', delivery_state: 'queued', delivery_attempts: 0, last_delivery_error: '', delivered_at: null, link: '/event.html?id=ev-1#recording', account_id: 'acc-h1', account_label: 'مینا ر.', has_bale_identity: true, dedupe_key: 'recording_access:a:granted:-:first', read: false, file_refs: [] },
            { id: '10000000-0000-4000-8000-000000000002', kind: 'recording_content', title: 'جلسهٔ تازه', body: 'جلسهٔ تازه منتشر شد.', created_at: '2026-10-22T07:00:00+00:00', delivery_status: 'pending', delivery_state: 'retrying', delivery_attempts: 2, last_delivery_error: 'bot_send_failed', delivered_at: null, link: '/event.html?id=ev-1#recording', account_id: 'acc-h2', account_label: '', has_bale_identity: true, dedupe_key: 'recording_content:session:s1:acc-h2', read: false, file_refs: [] },
            { id: '10000000-0000-4000-8000-000000000003', kind: 'certificate', title: 'گواهی صادر شد', body: 'گواهی شما صادر شد.', created_at: '2026-10-22T06:00:00+00:00', delivery_status: 'failed', delivery_state: 'failed', delivery_attempts: 0, last_delivery_error: 'no_bale_identity', delivered_at: null, link: '/account.html#certificates', account_id: 'acc-web', account_label: 'حساب وب', has_bale_identity: false, dedupe_key: 'certificate:k1:issued', read: false, file_refs: [] },
            { id: '10000000-0000-4000-8000-000000000005', kind: 'recording_content', title: 'فایل تازه', body: 'فایل تازه منتشر شد.', created_at: '2026-10-22T04:30:00+00:00', delivery_status: 'failed', delivery_state: 'failed', delivery_attempts: 5, last_delivery_error: 'provider_delivery_failed', delivered_at: null, link: '/event.html?id=ev-1#recording', account_id: 'acc-h3', account_label: '', has_bale_identity: true, dedupe_key: 'recording_content:resource:r9:acc-h3', read: false, file_refs: [] },
            { id: '10000000-0000-4000-8000-000000000004', kind: 'recording_order', title: 'سفارش رد شد', body: 'سفارش رد شد.', created_at: '2026-10-22T05:00:00+00:00', delivery_status: 'delivered', delivery_state: 'delivered', delivery_attempts: 1, last_delivery_error: '', delivered_at: '2026-10-22T05:01:00+00:00', link: '/account.html#orders', account_id: 'acc-h3', account_label: 'امید ن.', has_bale_identity: true, dedupe_key: 'recording_order:o1:rejected:-', read: true, file_refs: [] },
          ];
          const state = params.get('state') || '';
          const items = all.filter(item => !state || (state === 'no_bale_identity' ? item.last_delivery_error === 'no_bale_identity' : item.delivery_state === state && item.last_delivery_error !== 'no_bale_identity'));
          return reply(200, { source: 'shared_server_database', items, has_more: false, counts: { queued: 1, retrying: 1, delivered: 1, failed: 1, no_bale_identity: 1 }, limit: 30, offset: 0 });
        }
        /* Phase 9.5 §8: retry re-queues the SAME row (server answers the updated view; no second row). */
        const retryPath = path.match(/^\/api\/admin\/notifications\/([0-9a-f-]{36})\/retry$/);
        if (retryPath && method === 'POST') {
          if (!(identity.permissions || rolePermissions(identity.role)).includes('ev_publish')) return reply(403, { detail: 'permission_denied' });
          if (retryPath[1] === '10000000-0000-4000-8000-000000000003') return reply(409, { detail: { code: 'no_bale_identity' } });
          return reply(200, { id: retryPath[1], kind: 'recording_content', title: 'فایل تازه', body: 'فایل تازه منتشر شد.', created_at: '2026-10-22T04:30:00+00:00', delivery_status: 'pending', delivery_state: 'queued', delivery_attempts: 0, last_delivery_error: null, delivered_at: null, link: '/event.html?id=ev-1#recording', account_id: 'acc-h3', account_label: '', has_bale_identity: true, read: false, file_refs: [] });
        }
        /* Phase 9.5 §8.2: scheduled-publish monitor + manual run (ev_publish). */
        if (path === '/api/admin/scheduled-publish' && method === 'GET') {
          return reply(200, { now: '2026-10-22T09:30:00+00:00', last_run: schedRuns ? { at: '2026-10-22T09:25:00+00:00', ok: true, actor: schedRuns > 1 ? 'owner:acc-owner' : 'cli', due: 1, announced: 1, notified: 3, skipped: 0, errors: 0 } : null,
            pending: { future: 2, due_unannounced: schedRuns ? 0 : 1 }, runner: { interval_hint: 'systemd timer (5 min)', manual: 'POST /api/admin/scheduled-publish/run' } });
        }
        if (path === '/api/admin/scheduled-publish/run' && method === 'POST') {
          if (!(identity.permissions || rolePermissions(identity.role)).includes('ev_publish')) return reply(403, { detail: 'permission_denied' });
          schedRuns += 1;
          return reply(200, { ok: true, actor: 'owner:acc-owner', due: 1, announced: 1, notified: 3, skipped: 0, errors: 0, at: '2026-10-22T09:31:00+00:00' });
        }
        if (path === '/api/admin/integrity/recordings') {
          return reply(200, { generated_at: '2026-10-22T09:00:00+00:00', read_only: true,
            scanned: { purchase_forms: 2, payments: 5, orders: 5, access_rows: 6, products: 2 },
            severity: { error: 1, warning: 0, info: 1 }, counts: { refund_without_revoke: 1, stale_active_status: 1 },
            findings: [
              { code: 'refund_without_revoke', severity: 'error', refs: { access_id: '20000000-0000-4000-8000-000000000001', order_id: '30000000-0000-4000-8000-000000000001' } },
              { code: 'stale_active_status', severity: 'info', refs: { access_id: '20000000-0000-4000-8000-000000000002', recording_id: 'r1', expires_at: '2026-10-01T00:00:00+00:00' } },
            ] });
        }
        const workflowDecision = path.match(/^\/api\/admin\/inbox\/([0-9a-f-]{36})\/decision$/);
        if (workflowDecision && method === 'POST') {
          const body = JSON.parse(options.body || '{}');
          const task = workflowTasks.find(item => item.id === workflowDecision[1]);
          if (!task || task.version !== body.expected_version) return reply(409, { detail: 'workflow_version_conflict' });
          const decided = { ...task, status: body.decision, version: task.version + 1 };
          workflowTasks = workflowTasks.filter(item => item.id !== task.id);
          return reply(200, { task: decided, accepted: true });
        }
        if (path === '/api/owner/accounts/acc-01/role' && method === 'PUT') {
          const body = JSON.parse(options.body || '{}');
          accountRoles.set('acc-01', body.role);
          return reply(200, { account_id: 'acc-01', role: body.role, permissions: rolePermissions(body.role) });
        }
        if (path === '/api/owner/accounts/acc-01/manager-credentials' && method === 'PUT') {
          const body = JSON.parse(options.body || '{}');
          return reply(200, { account_id: 'acc-01', username: body.username.toLowerCase(), configured: true });
        }
        if (path === '/api/owner/accounts/acc-01/manager-credentials' && method === 'DELETE') {
          return reply(200, { account_id: 'acc-01', configured: false });
        }
        return reply(404, { detail: 'not_found' });
      };
    },
  });
  await new Promise((resolveLoad) => {
    if (dom.window.document.readyState === 'complete') return resolveLoad();
    const timer = setTimeout(resolveLoad, 8000);
    dom.window.addEventListener('load', () => { clearTimeout(timer); resolveLoad(); }, { once: true });
  });
  const until = async (predicate, label) => {
    const end = Date.now() + 5000;
    while (Date.now() < end) {
      if (predicate()) return;
      await delay(15);
    }
    throw new Error(`زمان انتظار تمام شد: ${label}`);
  };
  await until(() => !!dom.window.NORA_SERVER_API && (
    dom.window.document.querySelector('a[href="login.html?mode=staff&next=admin.html%23dash"]')
    || dom.window.document.querySelector('#admBar .server-identity')
    || dom.window.document.querySelector('#admBody')?.textContent.includes('API ورود وب در این محیط اجرا نشده است')
  ), 'نشست پنل');
  const click = (selector) => {
    const element = dom.window.document.querySelector(selector);
    assert.ok(element, `عنصر پیدا نشد: ${selector}`);
    element.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
    return element;
  };
  return { dom, window: dom.window, doc: dom.window.document, calls, storageOps, click, until, confirmAnswers };
}

console.log('— پیش‌نمایش بدون API ورود وب —');
{
  const app = await loadProductionSession({ apiUnavailable: true });
  try {
    const message = app.doc.querySelector('#admBody').textContent;
    assert.match(message, /API ورود وب در این محیط اجرا نشده است/);
    assert.match(message, /حساب مدیر با نام کاربری و گذرواژهٔ وب وارد می‌شود/);
    assert.doesNotMatch(message, /نشست OTP/);
    assert.equal(app.doc.querySelector('a[href^="login.html?mode=staff"]'), null,
      'در اسکلت preview پیوند ورود بی‌اثر نشان داده نمی‌شود');
    assert.ok(app.calls.some(call => call.path === '/api/auth/me'));
    assert.ok(app.calls.some(call => call.path === '/api/account/me'));
  } finally {
    app.dom.window.close();
  }
}

console.log('— نقش حساب از نشست سرور —');
{
  const app = await loadProductionSession({ role: 'manager', provider: 'manager-password' });
  try {
    await app.until(() => app.doc.querySelector('#admNav [data-sec="users"]'), 'ناوبری مدیر');
    assert.match(app.doc.querySelector('#admBar').textContent, /مدیر/);
    assert.match(app.doc.querySelector('#admBar .server-identity').textContent, /qa\.manager/,
      'نشان هویت، نام کاربری واقعی مدیر را از /api/account/me نشان می‌دهد نه متن ثابت');
    assert.equal(app.doc.querySelector('#admBar .searchbox'), null, 'جعبهٔ جست‌وجوی بی‌اثر در حالت سروری نیست');
    assert.match(app.doc.querySelector('[data-preview-badge]').textContent, /وضعیت از API سرور/);
    assert.ok(app.doc.querySelector('#admNav a[data-center-href]'));
    const settingsNav = [...app.doc.getElementById('admNav').getElementsByTagName('button')]
      .find((node) => node.dataset.sec === 'settings');
    assert.equal(settingsNav?.dataset.locked, '1');
    assert.ok(app.calls.some((call) => call.path === '/api/auth/me'));
    assert.ok(app.calls.some((call) => call.path === '/api/account/me'));
    assert.equal(app.storageOps.filter(([, key]) => key === 'nora-admin-session').length, 0,
      'نشست محلی برای احراز هویت خوانده نمی‌شود');
    assert.equal(app.doc.querySelector('[data-utool="staff"]'), null,
      'مدیر پنل واگذاری نقش‌ها را نمی‌بیند');
    assert.equal(app.doc.querySelector('[data-server-roleassign]'), null);
    assert.match(app.doc.querySelector('#admBody').textContent, /فقط با مالک/);
    assert.doesNotMatch(app.doc.querySelector('#admBody').textContent, /سارا محمدی|NL-1024|جلسهٔ شعر و موسیقی|رویدادهای نزدیک/,
      'ورود سروری فهرست، رویداد یا داشبورد آزمایشی را به حساب واقعی نشان نمی‌دهد');
    assert.equal(app.doc.querySelector('[data-server-logout]') !== null, true);

    app.click('#admNav [data-sec="dash"]');
    await app.until(() => app.doc.querySelector('#admBody .dash-kpis'), 'شمارش‌های داشبورد از API گزارش');
    assert.ok(app.calls.some(call => call.path === '/api/admin/reports/summary?period=30d'), 'داشبورد همان API گزارش را می‌خواند');
    assert.match(app.doc.querySelector('#admBody .dash-kpis').textContent, /فرم‌های سرور/);
    assert.match(app.doc.querySelector('#admBody .dash-kpis').textContent, /۳|3/);
    assert.match(app.doc.querySelector('#admBody .dash-kpis').textContent, /در انتظار بررسی/);
    assert.match(app.doc.querySelector('#admBody').textContent, /\/api\/admin\/reports\/summary/);

    app.click('#admNav [data-sec="users"]');
    if(!app.doc.querySelector('[data-open-workflow-inbox]')&&app.doc.querySelector('[data-uback]')) app.click('[data-uback]');
    await app.until(() => app.doc.querySelector('[data-open-workflow-inbox]'), 'پیوند کارتابل مشترک');
    app.click('[data-open-workflow-inbox]');
    await app.until(() => app.doc.querySelectorAll('[data-workflow-card]').length === 2, 'فهرست درخواست‌های مشترک');
    assert.match(app.doc.querySelector('[data-workflow-card="00000000-0000-4000-8000-000000000001"]').textContent, /آزمایش زنده/);
    assert.match(app.doc.querySelector('[data-workflow-card="00000000-0000-4000-8000-000000000002"]').textContent, /۲۵۰,۰۰۰|250,000/);
    assert.match(app.doc.querySelector('[data-workflow-card="00000000-0000-4000-8000-000000000001"] img').src,
      /\/api\/admin\/inbox\/00000000-0000-4000-8000-000000000001\/files\/00000000-0000-4000-8000-000000000101/);
    const receiptPdf=app.doc.querySelector('[data-workflow-card="00000000-0000-4000-8000-000000000002"] .workflow-file-download');
    assert.match(receiptPdf?.href||'',/\/api\/admin\/inbox\/00000000-0000-4000-8000-000000000002\/files\/00000000-0000-4000-8000-000000000103/);
    assert.match(receiptPdf?.textContent||'',/receipt\.pdf/);

    app.click('[data-workflow-approve="00000000-0000-4000-8000-000000000001"]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/inbox/00000000-0000-4000-8000-000000000001/decision'
      && call.method === 'POST'), 'ثبت تأیید پروفایل');
    const profileDecision = app.calls.find(call => call.path === '/api/admin/inbox/00000000-0000-4000-8000-000000000001/decision');
    assert.equal(profileDecision.options.headers['X-CSRF-Token'], 'account-csrf');
    assert.deepEqual(JSON.parse(profileDecision.options.body), { decision:'approved', reason:'', expected_version:1 });

    const reason = app.doc.querySelector('[data-workflow-reason="00000000-0000-4000-8000-000000000002"]');
    reason.value = 'تصویر خوانا نیست';
    app.click('[data-workflow-reject="00000000-0000-4000-8000-000000000002"]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/inbox/00000000-0000-4000-8000-000000000002/decision'
      && call.method === 'POST'), 'ثبت رد فیش');
    const receiptDecision = app.calls.find(call => call.path === '/api/admin/inbox/00000000-0000-4000-8000-000000000002/decision');
    assert.deepEqual(JSON.parse(receiptDecision.options.body), {
      decision:'rejected', reason:'تصویر خوانا نیست', expected_version:2,
    });

    app.click('[data-workflow-status="decided"]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/inbox?limit=50&offset=0&status=decided'), 'خواندن تاریخچهٔ تصمیم‌ها');
    await app.until(() => app.doc.querySelector('[data-workflow-card="00000000-0000-4000-8000-000000000009"]'), 'کارت تاریخچه');
    const historyCard = app.doc.querySelector('[data-workflow-card="00000000-0000-4000-8000-000000000009"]');
    assert.match(historyCard.textContent, /ردشده/);
    assert.match(historyCard.textContent, /مبلغ ناقص/);
    assert.match(historyCard.textContent, /شما/, 'تصمیم‌گیرندهٔ برابر با حساب جاری «شما» نشان داده می‌شود');
    assert.equal(historyCard.querySelector('[data-workflow-approve],[data-workflow-reject]'), null, 'کارت تاریخچه فقط‌خواندنی است');
    app.click('[data-workflow-status="pending"]');
    await app.until(() => app.doc.querySelector('[data-workflow-status="pending"].on'), 'بازگشت به در انتظار');

    app.click('[data-uback]');
    app.click('[data-user-hub="reports"]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/reports/summary?period=30d'), 'گزارش سروری');
    await app.until(() => app.doc.querySelector('#admBody .admkpi'), 'بارگذاری گزارش زنده');
    assert.match(app.doc.querySelector('#admBody').textContent, /پاسخ‌های نهایی/);
    assert.match(app.doc.querySelector('#admBody').textContent, /حساب‌های تأییدشده/);
    assert.doesNotMatch(app.doc.querySelector('#admBody').textContent, /فروش محاسبه‌شدهٔ نمونه/);

    app.click('[data-server-report-period="7d"]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/reports/summary?period=7d'), 'بازهٔ هفت‌روزه');
    await app.until(() => app.doc.querySelector('#admBody')?.textContent.includes('پاسخ‌های نهایی · ۷ روز'), 'نمای بازهٔ هفت‌روزه');

    /* فاز ۹.۴ §۸: صندوق خروجی اعلان‌ها در همان صفحهٔ گزارش (rp_view) — صف/تلاش دوباره/تحویل/ناموفق/بدون هویت بله از سرور. */
    await app.until(() => app.calls.some(call => call.path === '/api/admin/notifications?limit=30'), 'خواندن صندوق خروجی');
    await app.until(() => app.doc.querySelectorAll('[data-server-outbox-row]').length === 5, 'پنج ردیف صندوق خروجی');
    const outbox = app.doc.querySelector('[data-server-outbox]');
    assert.equal(outbox.querySelector('[data-server-outbox-row][data-server-outbox-state-row="queued"]').textContent.includes('در صف'), true);
    assert.match(outbox.querySelector('[data-server-outbox-state-row="retrying"]').textContent, /۲ تلاش/, 'شمار تلاش‌ها دیده می‌شود');
    assert.match(outbox.querySelector('[data-server-outbox-state-row="retrying"]').textContent, /bot_send_failed/, 'آخرین خطای ارسال دیده می‌شود');
    assert.match(outbox.querySelector('[data-server-outbox-state-row="no_bale_identity"]').textContent, /بدون هویت بله/);
    assert.match(outbox.querySelector('[data-server-outbox-state-row="delivered"]').textContent, /تحویل‌شده/);
    assert.match(outbox.querySelector('[data-server-outbox-state="no_bale_identity"]').textContent, /۱/, 'شمارندهٔ وضعیت از counts سرور');
    assert.doesNotMatch(outbox.textContent, /dedupe_key|recording_access:a:granted|4411/, 'کلید داخلی و شناسهٔ خام بله نمایش داده نمی‌شود');
    /* فاز ۹.۵ §۸: دکمهٔ «تلاش دوبارهٔ ارسال» فقط روی ردیف ناموفقِ دارای هویت بله؛ نه روی «بدون هویت بله»، نه روی در صف/تحویل‌شده. */
    assert.equal(outbox.querySelectorAll('[data-server-outbox-retry]').length, 1, 'فقط یک ردیف قابل صف‌گذاری دوباره');
    assert.equal(outbox.querySelector('[data-server-outbox-retry]').dataset.serverOutboxRetry, '10000000-0000-4000-8000-000000000005');
    assert.equal(outbox.querySelector('[data-server-outbox-state-row="no_bale_identity"] [data-server-outbox-retry]'), null, 'بدون هویت بله دکمهٔ تلاش ندارد');
    app.click('[data-server-outbox-retry]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/notifications/10000000-0000-4000-8000-000000000005/retry' && call.method === 'POST'), 'درخواست صف‌گذاری دوباره');
    const retryCall = app.calls.find(call => call.path === '/api/admin/notifications/10000000-0000-4000-8000-000000000005/retry');
    assert.equal(retryCall.options.headers['X-CSRF-Token'], 'account-csrf', 'نوشتن با CSRF');
    await app.until(() => app.doc.querySelector('[data-server-outbox-row="10000000-0000-4000-8000-000000000005"]')?.dataset.serverOutboxStateRow === 'queued', 'همان ردیف به «در صف» برگشت');
    assert.equal(app.doc.querySelectorAll('[data-server-outbox-row]').length, 5, 'ردیف تازه‌ای ساخته نشد');
    assert.match(app.doc.querySelector('[data-server-outbox]').textContent, /ردیف تازه‌ای ساخته نشد/);
    assert.doesNotMatch(app.doc.querySelector('[data-server-outbox]').textContent, /تحویل شد\b/, 'صف‌گذاری دوباره «تحویل» اعلام نمی‌شود');

    /* فاز ۹.۵ §۸.۲: کارت زمان‌بند — خودکار خوانده می‌شود، «در موعد ولی اعلان‌نشده» هشدار می‌دهد، اجرای دستی همان مسیر سرور است. */
    await app.until(() => app.calls.some(call => call.path === '/api/admin/scheduled-publish' && call.method === 'GET'), 'خواندن وضعیت زمان‌بند');
    await app.until(() => app.doc.querySelector('[data-server-sched][data-server-sched-state="stalled"]'), 'وضعیت متوقف‌مانده');
    const sched = app.doc.querySelector('[data-server-sched]');
    assert.match(sched.textContent, /هنوز هیچ اجرایی ثبت نشده/, 'بدون اجرای قبلی، موفقیت ادعا نمی‌شود');
    assert.match(sched.textContent, /تایمر اجرا نشده است/);
    assert.equal(app.calls.some(call => call.path === '/api/admin/scheduled-publish/run'), false, 'اجرای دستی خودکار نیست');
    const confirmsBefore = app.confirmAnswers.length;
    app.click('[data-server-sched-run-now]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/scheduled-publish/run' && call.method === 'POST'), 'اجرای دستی');
    assert.equal(app.confirmAnswers.length, confirmsBefore + 1, 'اجرای دستی زمان‌بند تأییدیه می‌گیرد (ممیزی A7)');
    assert.match(app.confirmAnswers.at(-1), /سررسیده/);
    assert.equal(app.calls.find(call => call.path === '/api/admin/scheduled-publish/run').options.headers['X-CSRF-Token'], 'account-csrf');
    await app.until(() => app.doc.querySelector('[data-server-sched][data-server-sched-state="ok"]'), 'پس از اجرا وضعیت سالم');
    const schedAfter = app.doc.querySelector('[data-server-sched]');
    assert.match(schedAfter.querySelector('[data-server-sched-run]').textContent, /تایمر\/خط فرمان|دستی از پنل/);
    // فاز ۹.۶ §۷: زمان UTC سرور (09:25Z) به وقت تهران (۱۲:۵۵، ۱۴۰۵/۰۷/۳۰) نمایش داده می‌شود و مقدار خام در datetime می‌ماند.
    const runTime = schedAfter.querySelector('[data-server-sched-run] time');
    assert.ok(runTime && runTime.getAttribute('datetime') === '2026-10-22T09:25:00+00:00', 'مقدار خام UTC در datetime');
    assert.match(runTime.textContent, /۱۴۰۵\/۰۷\/۳۰ ۱۲:۵۵ به وقت تهران/);
    assert.doesNotMatch(schedAfter.querySelector('[data-server-sched-run]').textContent, /T09:25:00/);
    assert.match(schedAfter.querySelector('[data-server-sched-manual]').textContent, /اعلان‌شده ۱/);
    assert.match(schedAfter.textContent, /زمان‌بندی‌شده برای آینده/);

    app.click('[data-server-outbox-state="no_bale_identity"]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/notifications?state=no_bale_identity&limit=30'), 'فیلتر بدون هویت بله');
    await app.until(() => app.doc.querySelectorAll('[data-server-outbox-row]').length === 1, 'فقط یک ردیف بدون هویت بله');
    assert.equal(app.doc.querySelector('[data-server-outbox-row]').dataset.serverOutboxStateRow, 'no_bale_identity');

    /* فاز ۹.۵ §۳: ممیزی یکپارچگی فقط با کلیک اجرا می‌شود (GET فقط‌خواندنی) و فقط شمارش/کد نشان می‌دهد. */
    const integrity = app.doc.querySelector('[data-server-integrity]');
    assert.ok(integrity, 'کارت ممیزی در صفحهٔ گزارش');
    assert.equal(app.calls.some(call => call.path === '/api/admin/integrity/recordings'), false, 'ممیزی خودکار اجرا نمی‌شود');
    assert.match(integrity.textContent, /هنوز اجرا نشده/);
    app.click('[data-server-integrity-run]');
    await app.until(() => app.calls.some(call => call.path === '/api/admin/integrity/recordings' && call.method === 'GET'), 'اجرای ممیزی');
    await app.until(() => app.doc.querySelector('[data-server-integrity-row]'), 'ردیف یافته‌ها');
    const integrityCard = app.doc.querySelector('[data-server-integrity]');
    assert.match(integrityCard.querySelector('[data-server-integrity-row="refund_without_revoke"]').textContent, /بازپرداخت بدون لغو دسترسی/);
    assert.match(integrityCard.textContent, /خطا/);
    assert.doesNotMatch(integrityCard.textContent, /acc-secret|۰۹۱۲/, 'هیچ دادهٔ شخصی در کارت');
  } finally {
    app.dom.window.close();
  }
}

console.log('— الزام گذرواژه برای ورود وبِ حساب مدیر —');
{
  const app = await loadProductionSession({ role: 'manager', provider: 'phone' });
  try {
    await app.until(() => app.doc.querySelector('a[href="login.html?mode=staff&next=admin.html%23dash"]'), 'دروازهٔ ورود مشترک مدیر و مالک');
    assert.match(app.doc.querySelector('#admBody').textContent, /نام کاربری و گذرواژهٔ حساب مدیر یا مالک/);
    assert.match(app.doc.querySelector('#admBody').textContent, /ورود مدیران و مالک سامانه/);
    assert.ok(app.doc.querySelector('a[href="login.html?mode=staff&next=admin.html%23dash"]'));
    assert.equal(app.doc.querySelector('[data-server-logout]'), null);
    assert.equal(app.calls.some(call => call.path === '/api/forms'), false,
      'ورود عادی حساب به‌تنهایی API مدیریتی وب را باز نمی‌کند');
  } finally {
    app.dom.window.close();
  }
}

console.log('— تنظیمات مالک: بدون زبانهٔ اسکلت پیام‌رسان؛ تاریخچهٔ عملیات —');
{
  const app = await loadProductionSession({ role: 'owner' });
  try {
    await app.until(() => app.doc.querySelector('#admBar .server-identity'), 'ورود مالک');
    app.click('#admNav [data-sec="settings"]');
    await app.until(() => app.doc.querySelector('[data-setg="services"]'), 'زبانه‌های تنظیمات');
    assert.equal(app.doc.querySelector('[data-setg="bots"]'), null, 'زبانهٔ اسکلت «وضعیت پیام‌رسان» که همیشه «وصل نیست» می‌گفت حذف شده است');
    assert.equal(app.doc.querySelector('[data-bot-status]'), null);
    assert.ok(app.calls.every(call => call.path !== '/api/integrations/status'), 'پنل سروری اسکلت عمومی را صدا نمی‌زند');
    app.click('[data-setg="performance"]');
    assert.equal(app.doc.querySelector('[data-perf="imageQuality"]'), null, 'ترجیح‌های فقط‌مرورگری (WebP/لودر) در پنل سروری به‌عنوان تنظیم سامانه نشان داده نمی‌شوند');
    assert.ok(app.doc.querySelector('[data-perf-check]'), 'بررسی سلامت شبکه باقی است');
    app.click('[data-setg="security"]');
    await app.until(() => app.calls.some(call => call.path === '/api/owner/audit?limit=30&offset=0'), 'خواندن تاریخچهٔ عملیات');
    await app.until(() => app.doc.querySelectorAll('[data-audit-panel] .audit-row').length === 2, 'دو ردیف تاریخچه');
    const audit = app.doc.querySelector('[data-audit-panel]').textContent;
    assert.match(audit, /تعیین نقش/);
    assert.match(audit, /بدون نقش ← مدیر/);
    assert.match(audit, /تصمیم کارتابل/);
    assert.match(audit, /فیش · رد · با دلیل/);
    app.click('[data-audit-action="workflow."]');
    await app.until(() => app.calls.some(call => call.path === '/api/owner/audit?limit=30&offset=0&action=workflow.'), 'فیلتر تاریخچه');
    await app.until(() => app.doc.querySelectorAll('[data-audit-panel] .audit-row').length === 1, 'فقط ردیف کارتابل');
  } finally {
    app.dom.window.close();
  }
}

console.log('— مدیر: تاریخچهٔ عملیات و زبانهٔ تنظیمات بسته است —');
{
  const app = await loadProductionSession({ role: 'manager', provider: 'manager-password' });
  try {
    await app.until(() => app.doc.querySelector('#admNav [data-sec="users"]'), 'ناوبری مدیر');
    app.window.location.hash = '#settings';
    app.click('#admNav [data-sec="settings"]');
    await delay(60);
    assert.equal(app.doc.querySelector('[data-audit-panel]'), null, 'مدیر تاریخچهٔ عملیات مالک را نمی‌بیند');
    assert.ok(app.calls.every(call => !call.path.startsWith('/api/owner/audit')), 'مدیر API تاریخچهٔ مالک را صدا نمی‌زند');
  } finally {
    app.dom.window.close();
  }
}

console.log('— واگذاری نقش با نشست مالک و CSRF —');
{
  const app = await loadProductionSession({ role: 'owner' });
  try {
    await app.until(() => app.doc.querySelector('#admBar .server-identity'), 'نشست مالک');
    await app.until(() => app.doc.querySelector('[data-server-roleassign="acc-01"]'), 'فهرست حساب‌های بله');

    assert.match(app.doc.querySelector('.server-role-row').textContent, /سارا آزمایشی/, 'نام پروفایل کنار شناسهٔ بله نشان داده می‌شود');
    const select = app.doc.querySelector('[data-server-roleassign="acc-01"]');
    assert.deepEqual([...select.options].map((option) => option.value), ['', 'manager', 'club-supervisor']);
    assert.equal(app.doc.querySelector('[data-server-roleassign="acc-01"] option[value="owner"]'), null);
    select.value = 'club-supervisor';
    app.click('[data-save-server-role="acc-01"]');
    await app.until(() => app.calls.some((call) => call.path === '/api/owner/accounts/acc-01/role' && call.method === 'PUT'), 'ذخیرهٔ نقش');
    await app.until(() => app.doc.querySelector('.server-role-row')?.textContent.includes('سرپرست باشگاه'), 'نمایش نقش تازه');
    assert.equal(app.confirmAnswers.length, 0, 'تعیین نقش تأییدیهٔ اضافی نمی‌خواهد');

    app.doc.querySelector('#serverRoleQuery').value = 'سارا';
    app.click('[data-role-filter="assigned"]');
    await app.until(() => app.calls.some(call => call.path === '/api/owner/accounts?limit=50&offset=0&role=assigned'), 'فیلتر دارای نقش');
    app.doc.querySelector('#serverRoleQuery').value = 'سارا';
    app.click('[data-role-search]');
    await app.until(() => app.calls.some(call => call.path === '/api/owner/accounts?limit=50&offset=0&q=%D8%B3%D8%A7%D8%B1%D8%A7&role=assigned'), 'جست‌وجوی نام');
    await app.until(() => app.doc.querySelector('[data-server-roleassign="acc-01"]'), 'نتیجهٔ جست‌وجو');

    const write = app.calls.find((call) => call.path === '/api/owner/accounts/acc-01/role' && call.method === 'PUT');
    assert.equal(write.options.headers['X-CSRF-Token'], 'owner-csrf');
    assert.deepEqual(JSON.parse(write.options.body), { role: 'club-supervisor' });
    assert.equal(app.storageOps.filter(([, key]) => key === 'nora-admin-session').length, 0);
    const storedPanel = app.window.localStorage.getItem('nora-admin');
    assert.ok(!storedPanel || !String(storedPanel).includes('club-supervisor'),
      'تعیین نقش از مسیر API انجام می‌شود، نه ذخیرهٔ محلی پنل');

    await app.until(() => app.doc.querySelector('[data-manager-username="acc-01"]'), 'فرم اعتبارنامهٔ مدیر');
    app.doc.querySelector('[data-manager-username="acc-01"]').value = 'Case.Manager';
    app.doc.querySelector('[data-manager-password="acc-01"]').value = 'manager-password-test-2026';
    app.click('[data-save-manager-credentials="acc-01"]');
    await app.until(() => app.calls.some(call => call.path === '/api/owner/accounts/acc-01/manager-credentials'
      && call.method === 'PUT'), 'ذخیرهٔ ورود مدیر');
    const credentialsWrite = app.calls.find(call => call.path === '/api/owner/accounts/acc-01/manager-credentials'
      && call.method === 'PUT');
    assert.equal(credentialsWrite.options.headers['X-CSRF-Token'], 'owner-csrf');
    assert.deepEqual(JSON.parse(credentialsWrite.options.body), {
      username: 'Case.Manager', password: 'manager-password-test-2026',
    });
    await app.until(() => app.doc.querySelector('[data-remove-manager-credentials="acc-01"]'), 'نمایش وضعیت ورود فعال');
    assert.equal(app.doc.querySelector('[data-manager-password="acc-01"]')?.value, '',
      'گذرواژه پس از ارسال از فرم پاک می‌شود');
    assert.ok(!String(app.window.localStorage.getItem('nora-admin') || '').includes('manager-password-test-2026'),
      'گذرواژهٔ مدیر در storage مرورگر نوشته نمی‌شود');

    app.click('[data-remove-manager-credentials="acc-01"]');
    await app.until(() => app.calls.some(call => call.path === '/api/owner/accounts/acc-01/manager-credentials'
      && call.method === 'DELETE'), 'حذف ورود مدیر');
    assert.match(app.confirmAnswers.at(-1) || '', /ورود با نام کاربری این مدیر حذف/, 'حذف ورود مدیر تأییدیه می‌گیرد');
    const credentialsDelete = app.calls.find(call => call.path === '/api/owner/accounts/acc-01/manager-credentials'
      && call.method === 'DELETE');
    assert.equal(credentialsDelete.options.headers['X-CSRF-Token'], 'owner-csrf');
    await app.until(() => !app.doc.querySelector('[data-remove-manager-credentials="acc-01"]'), 'بسته‌شدن ورود مدیر');
  } finally {
    app.dom.window.close();
  }
}

console.log('— انصراف از برداشتن نقش —');
{
  const app = await loadProductionSession({ role: 'owner', confirm: false });
  try {
    await app.until(() => app.doc.querySelector('[data-server-roleassign="acc-01"]'), 'فهرست حساب‌ها');
    const select = app.doc.querySelector('[data-server-roleassign="acc-01"]');
    select.value = 'manager';
    app.click('[data-save-server-role="acc-01"]');
    await app.until(() => app.calls.filter(call => call.path === '/api/owner/accounts/acc-01/role' && call.method === 'PUT').length === 1, 'تعیین نقش');
    await app.until(() => app.doc.querySelector('[data-server-roleassign="acc-01"]')?.value === 'manager'
      && !app.doc.querySelector('[data-save-server-role="acc-01"]')?.disabled, 'نقش مدیر از فهرست تازه');
    const clear = app.doc.querySelector('[data-server-roleassign="acc-01"]');
    clear.value = '';
    app.click('[data-save-server-role="acc-01"]');
    await delay(80);
    assert.match(app.confirmAnswers.at(-1) || '', /نقش این حساب برداشته می‌شود/, 'برداشتن نقش تأییدیه می‌خواهد');
    assert.equal(app.calls.filter(call => call.path === '/api/owner/accounts/acc-01/role' && call.method === 'PUT').length, 1,
      'با انصراف، هیچ درخواست حذف نقشی به سرور نمی‌رود');
  } finally {
    app.dom.window.close();
  }
}

console.log('آزمون نقش زندهٔ پنل: قبول');
