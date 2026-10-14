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
  };
  const owner = {
    authenticated: true,
    owner_id: 'owner-01',
    role: 'owner',
    permissions: rolePermissions('owner'),
  };
  const ownerList = () => ({
    items: [{
      account_id: 'acc-01', provider: 'bale', provider_user_id: '73421',
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
        if (path === '/api/owner/site-content') return reply(200, { content: {}, version: 0, updated_at: null });
        if (path === '/api/forms') return reply(200, { items: [] });
        if (path === '/api/cooperation-requests?limit=50&offset=0') return reply(200, { items: [], total: 0 });
        if (path === '/api/admin/inbox?limit=50&offset=0') return reply(200, { items: workflowTasks, has_more: false });
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
  return { dom, window: dom.window, doc: dom.window.document, calls, storageOps, click, until };
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

console.log('— وضعیت واقعی اتصال پیام‌رسان‌ها —');
{
  const app = await loadProductionSession({
    role: 'owner',
    integrationStatus: {
      mode: 'server-scaffold', deliveryEnabled: false, queueEnabled: false,
      providers: [
        { id: 'bale', connected: false, state: 'not_connected' },
        { id: 'eitaa', connected: false, state: 'mini_app_not_connected' },
      ],
    },
  });
  try {
    await app.until(() => app.doc.querySelector('#admBar .server-identity'), 'ورود مالک');
    app.click('#admNav [data-sec="settings"]');
    app.click('[data-setg="bots"]');
    await app.until(() => app.doc.querySelector('[data-bot-status]')?.textContent.includes('ربات و مینی‌اپ وصل نیستند'), 'وضعیت پیام‌رسان از API');
    const status = app.doc.querySelector('[data-bot-status]').textContent;
    assert.match(status, /ارسال خاموش است/);
    assert.match(status, /مینی‌اپ وصل نیست؛ اعلان بیرونی خاموش است/);
    assert.doesNotMatch(status, /اسکلت آماده|نمونه|در حال آزمایش/);
    assert.ok(app.calls.some(call => call.path === '/api/integrations/status' && call.method === 'GET'));
    assert.ok(app.calls.every(call => call.path !== '/api/outbox'), 'بازخوانی وضعیت هیچ ارسال یا صفی ایجاد نمی‌کند');
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

    const select = app.doc.querySelector('[data-server-roleassign="acc-01"]');
    assert.deepEqual([...select.options].map((option) => option.value), ['', 'manager', 'club-supervisor']);
    assert.equal(app.doc.querySelector('[data-server-roleassign="acc-01"] option[value="owner"]'), null);
    select.value = 'club-supervisor';
    app.click('[data-save-server-role="acc-01"]');
    await app.until(() => app.calls.some((call) => call.path === '/api/owner/accounts/acc-01/role' && call.method === 'PUT'), 'ذخیرهٔ نقش');
    await app.until(() => app.doc.querySelector('.server-role-row')?.textContent.includes('سرپرست باشگاه'), 'نمایش نقش تازه');

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
    const credentialsDelete = app.calls.find(call => call.path === '/api/owner/accounts/acc-01/manager-credentials'
      && call.method === 'DELETE');
    assert.equal(credentialsDelete.options.headers['X-CSRF-Token'], 'owner-csrf');
    await app.until(() => !app.doc.querySelector('[data-remove-manager-credentials="acc-01"]'), 'بسته‌شدن ورود مدیر');
  } finally {
    app.dom.window.close();
  }
}

console.log('آزمون نقش زندهٔ پنل: قبول');
