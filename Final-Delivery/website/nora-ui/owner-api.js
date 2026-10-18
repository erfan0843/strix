/* Same-origin client for server-backed owner and account operations.
   Session tokens stay in HttpOnly cookies; this module never stores credentials. */
(function (root) {
  'use strict';

  const API_ERROR_TEXT=Object.freeze({
    server_unreachable:'ارتباط با سرور برقرار نشد؛ اتصال اینترنت را بررسی کن.',
    csrf_failed:'نشست معتبر نیست؛ صفحه را تازه کن و دوباره وارد شو.',
    csrf_invalid:'نشست معتبر نیست؛ صفحه را تازه کن و دوباره وارد شو.',
    response_draft_account_mismatch:'این پیش‌نویس به حساب دیگری مرتبط است؛ با حساب درست وارد شو.',
    credentials_not_accepted:'اطلاعات محرمانه را در این درخواست نفرست.',
    invalid_payload:'اطلاعات درخواست کامل یا معتبر نیست.',
    response_not_found:'این پاسخ پیدا نشد.',
    form_not_found:'این فرم پیدا نشد.',
    /* پیوند حساب بله: هر کد، یک پیام روشن و قابل‌اقدام. */
    invalid_bale_auth_payload:'درخواست پیوند کامل نبود؛ صفحه را تازه کن و از داخل بله دوباره تلاش کن.',
    invalid_bale_init_data:'امضای بله معتبر یا تازه نیست؛ این صفحه را از داخل خودِ بله باز کن.',
    bale_init_data_replayed:'این درخواست پیوند قبلاً استفاده شده؛ صفحه را تازه کن و دوباره تلاش کن.',
    bale_identity_already_linked:'این حساب بله از قبل به حساب دیگری وصل است؛ برای ادغام از پشتیبانی بخواه.',
    account_already_has_bale_identity:'حساب تو از قبل یک هویت بله دارد؛ اول آن پیوند را بردار.',
    bale_identity_not_linked:'هیچ پیوند بله‌ای برای برداشتن نیست.',
    last_identity_cannot_be_removed:'این تنها راه ورود حساب است و برداشتنش حساب را بی‌صاحب می‌کند.',
    bale_auth_not_configured:'پیوند بله روی این سرور فعال نشده است.',
    authentication_required:'نشست حساب معتبر نیست؛ دوباره وارد شو.'
  });
  function apiErrorMessage(status,code){
    if(typeof code==='string'&&Object.prototype.hasOwnProperty.call(API_ERROR_TEXT,code))return API_ERROR_TEXT[code];
    if(status===0)return 'ارتباط با سرور برقرار نشد؛ دوباره تلاش کن.';
    if(status===401)return 'برای ادامه وارد حساب شو.';
    if(status===403)return 'برای این کار مجوز نداری.';
    if(status===404)return 'اطلاعات درخواستی پیدا نشد.';
    if(status===409)return 'وضعیت اطلاعات تغییر کرده؛ صفحه را تازه کن و دوباره تلاش کن.';
    if(status===413)return 'حجم فایل یا درخواست بیش از حد مجاز است.';
    if(status===422||status===400)return 'اطلاعات واردشده را بررسی کن و دوباره تلاش کن.';
    if(status===429)return 'تعداد درخواست‌ها زیاد است؛ کمی صبر کن و دوباره تلاش کن.';
    if(status>=500)return 'سرور فعلاً پاسخ‌گو نیست؛ کمی بعد دوباره تلاش کن.';
    return 'درخواست انجام نشد؛ دوباره تلاش کن.';
  }

  class OwnerApiError extends Error {
    constructor(status, code, payload) {
      super(apiErrorMessage(status,code));
      this.name = 'OwnerApiError';
      this.status = status;
      this.code = code || 'server_request_failed';
      this.payload = payload;
    }
  }

  function csrfCookie(cookieName) {
    const cookies = String(root.document && root.document.cookie || '').split(';').map(part => part.trim());
    const read = name => {
      const prefix = String(name) + '=';
      const item = cookies.find(part => part.startsWith(prefix));
      if (!item) return '';
      try { return decodeURIComponent(item.slice(prefix.length)); }
      catch (_) { return ''; }
    };
    if (cookieName) return read(cookieName);
    return read('nora_csrf') || read('nora_account_csrf');
  }

  async function request(path, options) {
    const opts = options || {};
    const parts = typeof path === 'string' ? path.split('?', 2) : [];
    const pathname = parts[0] || '';
    const query = parts[1] || '';
    const safeQuery = !query
      || /^(?:limit=\d{1,3}&offset=\d{1,7}|offset=\d{1,7}&limit=\d{1,3})$/.test(query)
      || /^period=(?:7d|30d|90d|365d|all)$/.test(query);
    if (typeof path !== 'string' || !/^\/api\/[A-Za-z0-9/_-]*$/.test(pathname) || pathname.includes('..')
        || !safeQuery) {
      throw new TypeError('Only fixed same-origin API paths are allowed');
    }
    const method = String(opts.method || 'GET').toUpperCase();
    const headers = Object.assign({ Accept: 'application/json' }, opts.headers || {});
    const init = {
      method,
      headers,
      credentials: 'same-origin',
      cache: 'no-store',
      redirect: 'error'
    };
    if (Object.prototype.hasOwnProperty.call(opts, 'body')) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(opts.body);
    }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)
        && (opts.ownerWrite === true || opts.csrfWrite === true)) {
      const csrf = csrfCookie(opts.csrfCookie);
      if (csrf) headers['X-CSRF-Token'] = csrf;
    }
    let response;
    try {
      response = await root.fetch(path, init);
    } catch (_) {
      throw new OwnerApiError(0, 'server_unreachable', null);
    }
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* non-JSON response */ }
    if (!response.ok) {
      const detail = payload && payload.detail;
      const code = (detail && typeof detail === 'object' && detail.code)
        || (typeof detail === 'string' && detail)
        || (payload && (payload.error || payload.code))
        || 'server_request_failed';
      throw new OwnerApiError(response.status, code, payload);
    }
    return payload;
  }

  async function uploadPublicReceipt(formId, blob, fileName, note) {
    const path = '/api/public/forms/' + encodeURIComponent(String(formId)) + '/receipt';
    if (!/^\/api\/public\/forms\/[A-Za-z0-9_-]+\/receipt$/.test(path) || !blob || typeof blob.size !== 'number') {
      throw new TypeError('Invalid public receipt upload');
    }
    const safeName = String(fileName || 'receipt').replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 120) || 'receipt';
    let encodedNote;
    try { encodedNote = encodeURIComponent(String(note || '').replace(/\r\n?/g, '\n').trim().slice(0, 500)); }
    catch (_) { throw new TypeError('Invalid public receipt note'); }
    let response;
    try {
      response = await root.fetch(path, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': blob.type || 'application/octet-stream',
          'X-File-Name': safeName,
          'X-Receipt-Note': encodedNote
        },
        credentials: 'same-origin',
        cache: 'no-store',
        redirect: 'error',
        body: blob
      });
    } catch (_) {
      throw new OwnerApiError(0, 'server_unreachable', null);
    }
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* non-JSON response */ }
    if (!response.ok) {
      const detail = payload && payload.detail;
      const code = (detail && typeof detail === 'object' && detail.code)
        || (typeof detail === 'string' && detail)
        || (payload && (payload.error || payload.code))
        || 'server_request_failed';
      throw new OwnerApiError(response.status, code, payload);
    }
    if (!payload || payload.uploaded !== true || typeof payload.created !== 'boolean') {
      throw new OwnerApiError(502, 'invalid_public_receipt_upload', payload);
    }
    return payload;
  }

  const api = Object.freeze({
    Error: OwnerApiError,
    health: () => request('/api/health'),
    me: () => request('/api/auth/me'),
    accountMe: () => request('/api/account/me'),
    accountProfile: () => request('/api/account/profile'),
    saveAccountProfile: payload => request('/api/account/profile', {
      method: 'PUT', body: payload, csrfWrite: true, csrfCookie: 'nora_account_csrf'
    }),
    /* هویت‌های تأییدشدهٔ حساب. پیوند بله فقط با «مدرک اثبات مالکیت» انجام
       می‌شود و آن مدرک، امضای یک‌بارمصرفِ `initData` خودِ بله است؛ نه شماره
       و نه هیچ شناسه‌ای که این ماژول بفرستد. سرور مرجع نهایی است. */
    getAccountIdentities: () => request('/api/account/identities'),
    linkBaleIdentity: initData => request('/api/account/identities/bale', {
      method: 'POST', body: { init_data: String(initData || '') },
      csrfWrite: true, csrfCookie: 'nora_account_csrf'
    }),
    unlinkBaleIdentity: () => request('/api/account/identities/bale', {
      method: 'DELETE', body: {}, csrfWrite: true, csrfCookie: 'nora_account_csrf'
    }),
    listAccountRoles: (limit, offset) => request('/api/owner/accounts?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))),
    setAccountRole: (accountId, role) => request('/api/owner/accounts/'
      + encodeURIComponent(String(accountId)) + '/role', {
        method: 'PUT', body: { role: role == null ? null : String(role) }, ownerWrite: true
      }),
    setManagerCredentials: (accountId, username, password) => request('/api/owner/accounts/'
      + encodeURIComponent(String(accountId)) + '/manager-credentials', {
        method: 'PUT', body: { username, password }, ownerWrite: true
      }),
    removeManagerCredentials: accountId => request('/api/owner/accounts/'
      + encodeURIComponent(String(accountId)) + '/manager-credentials', {
        method: 'DELETE', body: {}, ownerWrite: true
      }),
    getPublicSiteContent: () => request('/api/public/site-content'),
    getOwnerSiteContent: () => request('/api/owner/site-content'),
    updateSiteContent: (content, expectedVersion) => request('/api/owner/site-content', {
      method: 'PATCH', body: { content, expected_version: Number(expectedVersion) || 0 }, ownerWrite: true
    }),
    login: (username, password) => request('/api/auth/login', {
      method: 'POST', body: { username, password }
    }),
    logout: () => request('/api/auth/logout', {
      method: 'POST', body: {}, ownerWrite: true
    }),
    accountLogout: () => request('/api/auth/account/logout', {
      method: 'POST', body: {}, ownerWrite: true, csrfCookie: 'nora_account_csrf'
    }),
    getFormCapabilities: () => request('/api/public/forms/capabilities'),
    listForms: () => request('/api/forms'),
    getForm: id => request('/api/forms/' + encodeURIComponent(String(id))),
    getFormReadiness: id => request('/api/forms/' + encodeURIComponent(String(id)) + '/readiness'),
    createForm: (payload, idempotencyKey) => request('/api/forms', {
      method: 'POST', body: payload, csrfWrite: true,
      headers: { 'Idempotency-Key': String(idempotencyKey || '') }
    }),
    updateForm: (id, payload) => request('/api/forms/' + encodeURIComponent(String(id)), {
      method: 'PUT', body: payload, csrfWrite: true
    }),
    publishForm: (id, expectedVersion) => request('/api/forms/' + encodeURIComponent(String(id)) + '/publish', {
      method: 'POST', body: { expected_version: Number(expectedVersion) }, ownerWrite: true
    }),
    pauseForm: (id, expectedVersion) => request('/api/forms/' + encodeURIComponent(String(id)) + '/pause', {
      method: 'POST', body: { expected_version: Number(expectedVersion) }, ownerWrite: true
    }),
    listResponses: (id, limit, offset) => request('/api/forms/' + encodeURIComponent(String(id))
      + '/responses?limit=' + encodeURIComponent(String(limit || 50))
      + '&offset=' + encodeURIComponent(String(offset || 0))),
    deleteResponse: (formId, responseId) => request('/api/forms/' + encodeURIComponent(String(formId))
      + '/responses/' + encodeURIComponent(String(responseId)), {
        method: 'DELETE', body: {}, ownerWrite: true
      }),
    listCooperationRequests: (limit, offset) => request('/api/cooperation-requests?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))),
    updateCooperationRequest: (id, status) => request('/api/cooperation-requests/'
      + encodeURIComponent(String(id)), { method: 'PATCH', body: { status }, ownerWrite: true }),
    listAdminInbox: (limit, offset) => request('/api/admin/inbox?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))),
    getReportSummary: period => {
      const allowed = ['7d', '30d', '90d', '365d', 'all'];
      const selected = allowed.includes(String(period)) ? String(period) : '30d';
      return request('/api/admin/reports/summary?period=' + encodeURIComponent(selected));
    },
    decideAdminTask: (taskId, decision, reason, expectedVersion, csrfCookieName) => request(
      '/api/admin/inbox/' + encodeURIComponent(String(taskId)) + '/decision', {
        method: 'POST', body: {
          decision: String(decision), reason: String(reason || ''),
          expected_version: Number(expectedVersion) || 0
        }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    getAccountRegistrations: (limit, offset) => request('/api/account/registrations?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))),
    getAccountNotifications: (limit, offset) => request('/api/account/notifications?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))),
    markAccountNotificationRead: (id, csrfCookieName) => request(
      '/api/account/notifications/' + encodeURIComponent(String(id)) + '/read', {
        method: 'POST', body: {}, csrfWrite: true, csrfCookie: csrfCookieName || 'nora_account_csrf'
      }),
    getAccountFiles: (limit, offset) => request('/api/account/files?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))),
    workflowFileUrl: (taskId, fileId) => '/api/admin/inbox/'
      + encodeURIComponent(String(taskId)) + '/files/' + encodeURIComponent(String(fileId)),
    accountFileUrl: fileId => '/api/account/files/' + encodeURIComponent(String(fileId)),
    getPublicForm: id => request('/api/public/forms/' + encodeURIComponent(String(id))),
    submitCooperationRequest: payload => request('/api/public/cooperation-requests', {
      method: 'POST', body: payload
    }),
    getPublicDraft: id => request('/api/public/forms/' + encodeURIComponent(String(id)) + '/draft'),
    savePublicDraft: (id, payload) => request('/api/public/forms/' + encodeURIComponent(String(id)) + '/draft', {
      method: 'PATCH', body: payload&&typeof payload==='object'&&!Array.isArray(payload)&&Object.prototype.hasOwnProperty.call(payload,'answers')
        ?payload:{answers:payload}
    }),
    submitResponse: (id, payload) => request('/api/public/forms/' + encodeURIComponent(String(id)) + '/responses', {
      method: 'POST', body: payload&&typeof payload==='object'&&!Array.isArray(payload)&&Object.prototype.hasOwnProperty.call(payload,'answers')
        ?payload:{answers:payload}
    }),
    checkPublicCoupon: (id, code) => request('/api/public/forms/' + encodeURIComponent(String(id)) + '/coupon-check', {
      method: 'POST', body: { code: String(code == null ? '' : code).slice(0, 64) }
    }),
    createPublicPaymentIntent: (id, payload) => request('/api/public/forms/' + encodeURIComponent(String(id)) + '/payment-intents', {
      method: 'POST', body: payload
    }),
    getPublicPaymentIntent: (formId, paymentId) => request('/api/public/forms/' + encodeURIComponent(String(formId))
      + '/payment-intents/' + encodeURIComponent(String(paymentId))),
    cancelPublicPaymentIntent: (formId, paymentId) => request('/api/public/forms/' + encodeURIComponent(String(formId))
      + '/payment-intents/' + encodeURIComponent(String(paymentId)), {method: 'DELETE'}),
    createPublicTicketLink: id => request('/api/public/forms/' + encodeURIComponent(String(id)) + '/ticket-link', {
      method: 'POST', body: {}
    }),
    uploadPublicFormReceipt: (id, blob, fileName, note) => uploadPublicReceipt(id, blob, fileName, note),
    clearPublicDraft: id => request('/api/public/forms/' + encodeURIComponent(String(id)) + '/draft', {
      method: 'DELETE'
    })
  });

  root.NORA_SERVER_API = api;
  if (root.NORA_UI) root.NORA_UI.serverAPI = api;
})(typeof window === 'undefined' ? globalThis : window);
