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
    authentication_required:'نشست حساب معتبر نیست؛ دوباره وارد شو.',
    /* وضعیت حساب (مسدود/فعال) و یادداشت داخلی */
    account_blocked:'این حساب مسدود شده است؛ برای پیگیری با پشتیبانی نورا تماس بگیر.',
    owner_account_protected:'حساب مالک مسدودشدنی نیست.',
    block_reason_required:'برای مسدودسازی نوشتن دلیل (دست‌کم ۳ نویسه) لازم است.',
    block_reason_too_long:'دلیل مسدودسازی طولانی‌تر از حد مجاز است.',
    invalid_account_status:'وضعیت درخواستی معتبر نیست.',
    note_too_long:'یادداشت داخلی طولانی‌تر از حد مجاز است.',
    account_not_found:'این حساب پیدا نشد.',
    user_not_found:'این کاربر در پایگاه مشترک پیدا نشد.'
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

  const ADMIN_QUERY_KEYS = ['limit', 'offset', 'q', 'status', 'sort', 'order', 'provider', 'role', 'state', 'kind', 'event_ref', 'slot', 'entry_type', 'account_id', 'bale_user_id', 'answered', 'include_removed', 'event_id', 'format', 'when', 'mode'];
  function adminQuery(params) {
    const source = params && typeof params === 'object' ? params : {};
    const parts = [];
    ADMIN_QUERY_KEYS.forEach(key => {
      if (source[key] === undefined || source[key] === null || source[key] === '') return;
      parts.push(key + '=' + encodeURIComponent(String(source[key]).slice(0, 80)));
    });
    return parts.length ? '?' + parts.join('&') : '';
  }
  function contentKind(kind) {
    if (kind !== 'events' && kind !== 'articles') throw new TypeError('Unknown content kind');
    return kind;
  }
  function recordId(value) {
    const id = String(value || '');
    if (!/^[A-Za-z0-9_-]{1,100}$/.test(id)) throw new TypeError('Invalid record id');
    return id;
  }

  async function request(path, options) {
    const opts = options || {};
    const parts = typeof path === 'string' ? path.split('?', 2) : [];
    const pathname = parts[0] || '';
    const query = parts[1] || '';
    /* فقط پارامترهای ثابت و شناخته‌شده: صفحه‌بندی، بازهٔ گزارش، و فیلترهای محدود
       (جست‌وجوی حساب، نقش، وضعیت کارتابل، پیشوند عملیات تاریخچه). */
    const safeQuery = !query
      || /^(?:limit=\d{1,3}&offset=\d{1,7}|offset=\d{1,7}&limit=\d{1,3})(?:&q=[A-Za-z0-9%._-]{0,240})?(?:&role=(?:assigned|manager|club-supervisor|none))?(?:&status=(?:pending|decided|approved|rejected))?(?:&action=[a-z_.]{0,64})?$/.test(query)
      || /^period=(?:7d|30d|90d|365d|all)$/.test(query)
      /* فهرست‌های مدیریتی مرحلهٔ دوم به بعد (محتوا، کاربران، حضور، گواهی، امتیاز باشگاه): فقط کلیدهای ثابت با مقدار کدشده */
      || /^(?:(?:limit|offset|q|status|sort|order|provider|role|state|kind|event_ref|slot|entry_type|account_id|bale_user_id|answered|include_removed|event_id|target_type|target_id|when|mode)=[A-Za-z0-9%._-]{0,240})(?:&(?:limit|offset|q|status|sort|order|provider|role|state|kind|event_ref|slot|entry_type|account_id|bale_user_id|answered|include_removed|event_id|target_type|target_id|when|mode)=[A-Za-z0-9%._-]{0,240}){0,8}$/.test(query);
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

  /* بارگذاری تصویر عمومی پنل (پوستر/جلد): بدنهٔ خام، نام فقط نمایشی؛ سرور نوع واقعی را از بایت‌ها تشخیص می‌دهد. */
  async function uploadAdminMedia(blob, fileName, csrfCookieName) {
    if (!blob || typeof blob.size !== 'number') throw new TypeError('Invalid media upload');
    const safeName = String(fileName || 'image').replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 120) || 'image';
    const headers = {
      Accept: 'application/json',
      'Content-Type': blob.type || 'application/octet-stream',
      'X-File-Name': safeName
    };
    const csrf = csrfCookie(csrfCookieName);
    if (csrf) headers['X-CSRF-Token'] = csrf;
    let response;
    try {
      response = await root.fetch('/api/admin/media', {
        method: 'POST', headers, credentials: 'same-origin', cache: 'no-store', redirect: 'error', body: blob
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
    if (!payload || typeof payload.url !== 'string' || !/^\/api\/public\/media\/[0-9a-f-]{36}$/.test(payload.url)) {
      throw new OwnerApiError(502, 'invalid_media_upload', payload);
    }
    return payload;
  }

  /* فاز ۸ — بارگذاری/جایگزینی فایل منبع رویداد: بدنهٔ خام؛ نام فقط اعلامی (درصدکدشده تا سرآیند ASCII بماند)؛ سرور نوع واقعی را از بایت‌ها می‌سنجد. */
  async function uploadEventResourceFile(eventId, resourceId, blob, fileName, csrfCookieName) {
    if (!blob || typeof blob.size !== 'number') throw new TypeError('Invalid resource upload');
    const path = '/api/admin/events/' + recordId(eventId) + '/resources/' + recordId(resourceId) + '/file';
    const safeName = encodeURIComponent(String(fileName || 'resource').replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').slice(0, 120) || 'resource');
    const headers = {
      Accept: 'application/json',
      'Content-Type': blob.type || 'application/octet-stream',
      'X-File-Name': safeName
    };
    const csrf = csrfCookie(csrfCookieName);
    if (csrf) headers['X-CSRF-Token'] = csrf;
    let response;
    try {
      response = await root.fetch(path, {
        method: 'PUT', headers, credentials: 'same-origin', cache: 'no-store', redirect: 'error', body: blob
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
    return payload;
  }

  /* فاز ۹.۵ §۵.۲ — بارگذاری قطعه‌ای قابل ادامه (قرارداد داخلی محدود؛ فقط با حافظهٔ خصوصی سرور).
     هر قطعه با sha256 همان قطعه می‌رود؛ sha256 کل فایل به‌صورت افزایشی (بدون نگه‌داشتن کل فایل در حافظه) محاسبه و
     در «complete» تحویل سرور می‌شود؛ پس از قطع شبکه، offset واقعی از سرور خوانده و از همان‌جا ادامه می‌یابد. */
  const SHA256_K = new Uint32Array([0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2]);
  function createSha256() {
    const h = new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
    const w = new Uint32Array(64); const buffer = new Uint8Array(64); let bufferLength = 0; let totalBytes = 0;
    function block(bytes, offset) {
      for (let i = 0; i < 16; i++) w[i] = (bytes[offset + i * 4] << 24) | (bytes[offset + i * 4 + 1] << 16) | (bytes[offset + i * 4 + 2] << 8) | bytes[offset + i * 4 + 3];
      for (let i = 16; i < 64; i++) {
        const s0 = ((w[i-15] >>> 7) | (w[i-15] << 25)) ^ ((w[i-15] >>> 18) | (w[i-15] << 14)) ^ (w[i-15] >>> 3);
        const s1 = ((w[i-2] >>> 17) | (w[i-2] << 15)) ^ ((w[i-2] >>> 19) | (w[i-2] << 13)) ^ (w[i-2] >>> 10);
        w[i] = (w[i-16] + s0 + w[i-7] + s1) >>> 0;
      }
      let a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], k = h[7];
      for (let i = 0; i < 64; i++) {
        const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        const ch = (e & f) ^ (~e & g);
        const t1 = (k + S1 + ch + SHA256_K[i] + w[i]) >>> 0;
        const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
        const maj = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (S0 + maj) >>> 0;
        k = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
      }
      h[0] = (h[0] + a) >>> 0; h[1] = (h[1] + b) >>> 0; h[2] = (h[2] + c) >>> 0; h[3] = (h[3] + d) >>> 0;
      h[4] = (h[4] + e) >>> 0; h[5] = (h[5] + f) >>> 0; h[6] = (h[6] + g) >>> 0; h[7] = (h[7] + k) >>> 0;
    }
    return {
      update(bytes) {
        totalBytes += bytes.length; let i = 0;
        if (bufferLength) {
          while (bufferLength < 64 && i < bytes.length) buffer[bufferLength++] = bytes[i++];
          if (bufferLength < 64) return; block(buffer, 0); bufferLength = 0;
        }
        for (; i + 64 <= bytes.length; i += 64) block(bytes, i);
        while (i < bytes.length) buffer[bufferLength++] = bytes[i++];
      },
      hex() {
        const bits = totalBytes * 8; const pad = new Uint8Array(((bufferLength + 8) >> 6 << 6) + 64 - bufferLength);
        pad[0] = 0x80; const view = new DataView(pad.buffer);
        view.setUint32(pad.length - 8, Math.floor(bits / 0x100000000)); view.setUint32(pad.length - 4, bits >>> 0);
        this.update(pad);
        return Array.from(h, x => x.toString(16).padStart(8, '0')).join('');
      }
    };
  }
  async function digestChunkHex(bytes) {
    const subtle = root.crypto && root.crypto.subtle;
    if (subtle && typeof subtle.digest === 'function') {
      const digest = await subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
    }
    const hasher = createSha256(); hasher.update(bytes); return hasher.hex();
  }
  function uploadSessionsPath(eventId, resourceId) {
    return '/api/admin/events/' + recordId(eventId) + '/resources/' + recordId(resourceId) + '/upload-sessions';
  }
  async function rawRequest(path, init) {
    let response;
    try { response = await root.fetch(path, Object.assign({ credentials: 'same-origin', cache: 'no-store', redirect: 'error' }, init)); }
    catch (_) { throw new OwnerApiError(0, 'server_unreachable', null); }
    let payload = null;
    try { payload = await response.json(); } catch (_) { /* non-JSON */ }
    if (!response.ok) {
      const detail = payload && payload.detail;
      const code = (detail && typeof detail === 'object' && detail.code) || (typeof detail === 'string' && detail) || 'server_request_failed';
      throw new OwnerApiError(response.status, code, payload);
    }
    return payload;
  }
  /* options: {onProgress(sentBytes,totalBytes,phase), signal, chunkBytes, maxRetries} */
  async function uploadEventResourceFileResumable(eventId, resourceId, blob, fileName, csrfCookieName, options) {
    if (!blob || typeof blob.size !== 'number' || typeof blob.slice !== 'function') throw new TypeError('Invalid resource upload');
    const opts = options || {}; const base = uploadSessionsPath(eventId, resourceId);
    const safeName = String(fileName || 'resource').replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').slice(0, 120) || 'resource';
    const csrf = csrfCookie(csrfCookieName); const writeHeaders = { Accept: 'application/json' };
    if (csrf) writeHeaders['X-CSRF-Token'] = csrf;
    const progress = typeof opts.onProgress === 'function' ? opts.onProgress : () => {};
    const aborted = () => { if (opts.signal && opts.signal.aborted) throw new OwnerApiError(0, 'upload_cancelled', null); };
    const session = await rawRequest(base, { method: 'POST', headers: Object.assign({ 'Content-Type': 'application/json' }, writeHeaders),
      body: JSON.stringify({ size: blob.size, file_name: safeName }) });
    if (!session || typeof session.id !== 'string' || !Number.isSafeInteger(session.offset) || !Number.isSafeInteger(session.chunk_bytes)) {
      throw new OwnerApiError(502, 'invalid_upload_session', session);
    }
    const chunkBytes = Math.max(64 * 1024, Math.min(Number(opts.chunkBytes) || session.chunk_bytes, session.max_chunk_bytes || session.chunk_bytes));
    const maxRetries = Number.isSafeInteger(opts.maxRetries) ? opts.maxRetries : 5;
    const whole = createSha256(); let hashed = 0; let offset = session.offset; let retries = 0;
    const hashUpTo = async (end) => { /* the whole-file digest must cover the bytes already on the server too (resume) */
      while (hashed < end) {
        const piece = new Uint8Array(await blob.slice(hashed, Math.min(end, hashed + chunkBytes)).arrayBuffer());
        whole.update(piece); hashed += piece.length;
      }
    };
    await hashUpTo(offset);
    progress(offset, blob.size, session.resumed ? 'resumed' : 'started');
    while (offset < blob.size) {
      aborted();
      const bytes = new Uint8Array(await blob.slice(offset, Math.min(blob.size, offset + chunkBytes)).arrayBuffer());
      const checksum = await digestChunkHex(bytes);
      try {
        const pushed = await rawRequest(base + '/' + encodeURIComponent(session.id), { method: 'PATCH', body: bytes,
          headers: Object.assign({ 'Content-Type': 'application/octet-stream', 'Upload-Offset': String(offset), 'Upload-Checksum': 'sha256 ' + checksum }, writeHeaders) });
        if (!pushed || !Number.isSafeInteger(pushed.offset) || pushed.offset < offset) throw new OwnerApiError(502, 'invalid_upload_chunk', pushed);
        whole.update(bytes); hashed = pushed.offset; offset = pushed.offset; retries = 0;
        progress(offset, blob.size, 'uploading');
      } catch (error) {
        const transient = error && (error.status === 0 || error.status >= 500 || (error.status === 409 && error.code === 'offset_mismatch'));
        if (!transient || retries >= maxRetries) throw error;
        retries += 1; aborted();
        const state = await rawRequest(base + '/' + encodeURIComponent(session.id), { method: 'GET', headers: { Accept: 'application/json' } });
        if (!state || state.status !== 'open' || !Number.isSafeInteger(state.offset)) throw new OwnerApiError(410, (state && 'upload_session_' + state.status) || 'upload_session_lost', state);
        if (state.offset < hashed) { /* the server kept less than we hashed: re-hash from scratch up to its offset */
          const fresh = createSha256(); hashed = 0; Object.assign(whole, fresh);
        }
        offset = state.offset; await hashUpTo(offset);
        progress(offset, blob.size, 'resumed');
      }
    }
    progress(blob.size, blob.size, 'finalizing');
    const saved = await rawRequest(base + '/' + encodeURIComponent(session.id) + '/complete', { method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, writeHeaders), body: JSON.stringify({ sha256: whole.hex() }) });
    if (!saved || typeof saved.id !== 'string') throw new OwnerApiError(502, 'invalid_resource_upload', saved);
    return saved;
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

  /* فاز ۹.۱ — رسید سفارش محتوای ضبط‌شده دیگر از حساب فرستاده نمی‌شود؛ رسید فقط از فرم خرید
     (uploadPublicFormReceipt) می‌رود و سرور مسیر حساب را با 410 use_purchase_form بسته است. */

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
    listAccountRoles: (limit, offset, query, roleFilter) => request('/api/owner/accounts?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))
      + (query ? '&q=' + encodeURIComponent(String(query).slice(0, 80)) : '')
      + (roleFilter ? '&role=' + encodeURIComponent(String(roleFilter)) : '')),
    /* ردپای عملیات مدیریتی: فقط مالک؛ فقط شناسه و نتیجه، هیچ مقدار محرمانه‌ای در آن نیست. */
    listAuditEvents: (limit, offset, action) => request('/api/owner/audit?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))
      + (action ? '&action=' + encodeURIComponent(String(action)) : '')),
    /* تاریخچهٔ یک هدف مشخص (پروندهٔ کاربر): همان API مالک با فیلتر دقیق target_type/target_id */
    listTargetAuditEvents: (targetType, targetId, params) => {
      const p = params || {};
      return request('/api/owner/audit?limit=' + encodeURIComponent(String(p.limit || 20))
        + '&offset=' + encodeURIComponent(String(p.offset || 0))
        + '&target_type=' + encodeURIComponent(String(targetType || ''))
        + '&target_id=' + encodeURIComponent(String(targetId || '')));
    },
    setAccountRole: (accountId, role) => request('/api/owner/accounts/'
      + encodeURIComponent(String(accountId)) + '/role', {
        method: 'PUT', body: { role: role == null ? null : String(role) }, ownerWrite: true
      }),
    setAccountStatus: (accountId, status, reason) => request('/api/owner/accounts/'
      + encodeURIComponent(String(accountId)) + '/status', {
        method: 'PUT', body: reason == null ? { status: String(status) } : { status: String(status), reason: String(reason) }, ownerWrite: true
      }),
    setAdminUserNote: (accountId, note, csrfCookieName) => request('/api/admin/users/' + recordId(accountId) + '/note', {
      method: 'PUT', body: { note: String(note == null ? '' : note) }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
    }),
    setManagerCredentials: (accountId, username, password) => request('/api/owner/accounts/'
      + encodeURIComponent(String(accountId)) + '/manager-credentials', {
        method: 'PUT', body: { username, password }, ownerWrite: true
      }),
    removeManagerCredentials: accountId => request('/api/owner/accounts/'
      + encodeURIComponent(String(accountId)) + '/manager-credentials', {
        method: 'DELETE', body: {}, ownerWrite: true
      }),
    /* مدیریت رکوردی رویداد/مطلب روی همان سند site_content */
    listAdminContent: (kind, params) => request('/api/admin/content/' + contentKind(kind) + adminQuery(params)),
    getAdminContent: (kind, id) => request('/api/admin/content/' + contentKind(kind) + '/' + recordId(id)),
    createAdminContent: (kind, record, expectedVersion, status, csrfCookieName) => request(
      '/api/admin/content/' + contentKind(kind), {
        method: 'POST',
        body: Object.assign({ record, expected_version: Number(expectedVersion) || 0 },
          status ? { status: String(status) } : {}),
        csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    updateAdminContent: (kind, id, record, expectedVersion, csrfCookieName) => request(
      '/api/admin/content/' + contentKind(kind) + '/' + recordId(id), {
        method: 'PUT', body: { record, expected_version: Number(expectedVersion) || 0 },
        csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    setAdminContentStatus: (kind, id, status, expectedVersion, csrfCookieName) => request(
      '/api/admin/content/' + contentKind(kind) + '/' + recordId(id) + '/status', {
        method: 'POST', body: { status: String(status), expected_version: Number(expectedVersion) || 0 },
        csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    /* فهرست کاربران (us_view) و حضور و غیاب (attendance) */
    listAdminUsers: params => request('/api/admin/users' + adminQuery(params)),
    getAdminUser: accountId => request('/api/admin/users/' + recordId(accountId)),
    /* U4/U5: پروندهٔ کاربر؛ فقط ردیف‌های همین حساب (فیلتر در سرور)، صفحه‌بندی‌شده */
    listAdminUserRegistrations: (accountId, params) => request('/api/admin/users/' + recordId(accountId) + '/registrations' + adminQuery(params)),
    getAdminUserRegistration: (accountId, responseId) => request('/api/admin/users/' + recordId(accountId) + '/registrations/' + recordId(responseId)),
    listAdminUserNotifications: (accountId, params) => request('/api/admin/users/' + recordId(accountId) + '/notifications' + adminQuery(params)),
    /* گواهینامه‌ها (certificate): آینهٔ تأییدشدهٔ گواهی‌های ربات در پایگاه مشترک؛ فقط‌خواندنی */
    listAdminCertificates: params => request('/api/admin/certificates' + adminQuery(params)),
    getAdminCertificate: certificateId => request('/api/admin/certificates/' + recordId(certificateId)),
    adminCertificateFileUrl: (certificateId, slot) => '/api/admin/certificates/' + recordId(certificateId) + '/file' + adminQuery({ slot: slot || 'pdf' }),
    /* امتیاز باشگاه (cl_member): آینهٔ فقط‌خواندنی دفترکل ربات؛ هیچ مسیر نوشتن امتیازی در پنل وجود ندارد */
    listAdminClubPoints: params => request('/api/admin/club/points' + adminQuery(params)),
    listAdminClubMembers: params => request('/api/admin/club/points/members' + adminQuery(params)),
    getAdminClubMember: accountId => request('/api/admin/club/points/members/' + recordId(accountId)),
    /* تصاویر عمومی (ev_create): بارگذاری، فهرست با وضعیت استفاده در site_content، حذف صریحِ بدون‌استفاده */
    uploadAdminMedia,
    listAdminMedia: params => request('/api/admin/media' + adminQuery(params)),
    deleteAdminMedia: (mediaId, csrfCookieName) => request('/api/admin/media/' + recordId(mediaId), {
      method: 'DELETE', csrfWrite: true, csrfCookie: csrfCookieName || undefined
    }),
    /* فاز ۸ — منابع، پرسش‌وپاسخ، دیدگاه و گزارش‌های رویداد (ev_create / ev_publish؛ تصمیم نهایی در سرور) */
    listEventResources: (eventId, params) => request('/api/admin/events/' + recordId(eventId) + '/resources' + adminQuery(params)),
    createEventResource: (eventId, payload, csrfCookieName) => request('/api/admin/events/' + recordId(eventId) + '/resources', {
      method: 'POST', body: payload, csrfWrite: true, csrfCookie: csrfCookieName || undefined
    }),
    updateEventResource: (eventId, resourceId, payload, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/resources/' + recordId(resourceId), {
        method: 'PUT', body: payload, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    uploadEventResourceFile,
    uploadEventResourceFileResumable,
    getStorageHealth: () => request('/api/admin/storage/health'),
    removeEventResource: (eventId, resourceId, reason, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/resources/' + recordId(resourceId) + '/remove', {
        method: 'POST', body: { reason: String(reason || '') }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    listEventQuestions: (eventId, params) => request('/api/admin/events/' + recordId(eventId) + '/questions' + adminQuery(params)),
    listAllEventQuestions: params => request('/api/admin/event-questions' + adminQuery(params)),
    answerEventQuestion: (eventId, questionId, payload, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/questions/' + recordId(questionId) + '/answer', {
        method: 'POST', body: payload, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    setEventQuestionStatus: (eventId, questionId, status, reason, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/questions/' + recordId(questionId) + '/status', {
        method: 'POST', body: { status: String(status), reason: String(reason || '') }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    resendEventQuestionNotification: (eventId, questionId, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/questions/' + recordId(questionId) + '/resend-notification', {
        method: 'POST', body: {}, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    listEventReviews: (eventId, params) => request('/api/admin/events/' + recordId(eventId) + '/reviews' + adminQuery(params)),
    setEventReviewStatus: (eventId, reviewId, status, reason, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/reviews/' + recordId(reviewId) + '/status', {
        method: 'POST', body: { status: String(status), reason: String(reason || '') }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    listEventReports: params => request('/api/admin/event-reports' + adminQuery(params)),
    resolveEventReport: (reportId, status, note, csrfCookieName) => request(
      '/api/admin/event-reports/' + recordId(reportId) + '/resolve', {
        method: 'POST', body: { status: String(status), note: String(note || '') }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    eventInteractionSummary: () => request('/api/admin/event-interaction/summary'),
    /* فاز ۹ — محصول ضبط‌شدهٔ رویداد، جلسات، وضعیت فروش، سفارش‌ها و دسترسی‌ها (ev_create / ev_publish / receipt_approve / finance؛ همه در سرور) */
    getEventRecording: eventId => request('/api/admin/events/' + recordId(eventId) + '/recording'),
    saveEventRecording: (eventId, payload, csrfCookieName) => request('/api/admin/events/' + recordId(eventId) + '/recording', {
      method: 'PUT', body: payload, csrfWrite: true, csrfCookie: csrfCookieName || undefined
    }),
    setEventRecordingStatus: (eventId, status, reason, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/recording/status', {
        method: 'POST', body: reason ? { status: String(status), reason: String(reason) } : { status: String(status) },
        csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    createRecordingSession: (eventId, payload, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/recording/sessions', {
        method: 'POST', body: payload, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    updateRecordingSession: (eventId, sessionId, payload, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/recording/sessions/' + recordId(sessionId), {
        method: 'PUT', body: payload, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    deleteRecordingSession: (eventId, sessionId, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/recording/sessions/' + recordId(sessionId), {
        method: 'DELETE', csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    listRecordingAccess: eventId => request('/api/admin/events/' + recordId(eventId) + '/recording/access'),
    grantRecordingAccess: (eventId, payload, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/recording/access', {
        method: 'POST', body: payload, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    revokeRecordingAccess: (eventId, accessId, reason, csrfCookieName) => request(
      '/api/admin/events/' + recordId(eventId) + '/recording/access/' + recordId(accessId) + '/revoke', {
        method: 'POST', body: { reason: String(reason || '') }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    listRecordingOrders: params => request('/api/admin/recording-orders' + adminQuery(params)),
    getRecordingOrder: orderId => request('/api/admin/recording-orders/' + recordId(orderId)),
    recordingOrderReceiptUrl: orderId => '/api/admin/recording-orders/' + recordId(orderId) + '/receipt',
    recordingOrdersExportUrl: params => '/api/admin/recording-orders' + adminQuery(Object.assign({}, params || {}, { format: 'csv' })),
    decideRecordingOrder: (orderId, decision, reason, csrfCookieName) => request(
      '/api/admin/recording-orders/' + recordId(orderId) + '/decision', {
        method: 'POST', body: { decision: String(decision), reason: String(reason || '') }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    refundRecordingOrder: (orderId, reference, reason, csrfCookieName) => request(
      '/api/admin/recording-orders/' + recordId(orderId) + '/refund', {
        method: 'POST', body: { reference: String(reference || ''), reason: String(reason || '') }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    recordingsSummary: () => request('/api/admin/recordings/summary'),
    listAttendanceForms: params => request('/api/admin/attendance/forms' + adminQuery(params)),
    listAttendancePeople: (formId, params) => request('/api/admin/attendance/forms/' + recordId(formId) + '/people' + adminQuery(params)),
    attendanceCheckIn: (responseId, reason, csrfCookieName) => request(
      '/api/admin/attendance/responses/' + recordId(responseId) + '/check-in', {
        method: 'POST', body: reason ? { reason: String(reason) } : {}, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    attendanceUndoCheckIn: (responseId, reason, csrfCookieName) => request(
      '/api/admin/attendance/responses/' + recordId(responseId) + '/undo-check-in', {
        method: 'POST', body: { reason: String(reason || '') }, csrfWrite: true, csrfCookie: csrfCookieName || undefined
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
    /* گام ۴ ویزارد رویداد: فقط مرجع رویداد فرم جابه‌جا می‌شود (POST /api/forms/{id}/event)؛ تعریف فرم دست‌نخورده می‌ماند */
    linkFormEvent: (id, eventId, expectedVersion, csrfCookieName) => request('/api/forms/' + encodeURIComponent(String(id)) + '/event', {
      method: 'POST', body: { ev: eventId == null ? '' : String(eventId), expected_version: Number(expectedVersion) },
      csrfWrite: true, csrfCookie: csrfCookieName || undefined
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
    /* status: pending (پیش‌فرض) | decided | approved | rejected — تاریخچهٔ تصمیم‌ها از همان جدول خوانده می‌شود. */
    listAdminInbox: (limit, offset, status) => request('/api/admin/inbox?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))
      + (status && status !== 'pending' ? '&status=' + encodeURIComponent(String(status)) : '')),
    listAdminNotifications: params => {
      const source = params && typeof params === 'object' ? params : {};
      const states = ['queued', 'retrying', 'delivered', 'failed', 'no_bale_identity'];
      const parts = [];
      if (states.includes(String(source.state))) parts.push('state=' + encodeURIComponent(String(source.state)));
      if (/^[a-z_]{1,40}$/.test(String(source.kind || ''))) parts.push('kind=' + String(source.kind));
      const limit = Number(source.limit); const offset = Number(source.offset);
      if (Number.isSafeInteger(limit) && limit > 0 && limit <= 100) parts.push('limit=' + limit);
      if (Number.isSafeInteger(offset) && offset > 0) parts.push('offset=' + offset);
      return request('/api/admin/notifications' + (parts.length ? '?' + parts.join('&') : ''));
    },
    /* Phase 9.5 §3: read-only purchase-chain audit (ids only; the server never fixes anything). */
    getRecordingIntegrity: () => request('/api/admin/integrity/recordings'),
    /* Phase 9.5 §8: re-queue one failed outbox row (same row, never a second one) — ev_publish on the server. */
    retryAdminNotification: (notificationId, csrfCookieName) => request(
      '/api/admin/notifications/' + recordId(notificationId) + '/retry', {
        method: 'POST', body: {}, csrfWrite: true, csrfCookie: csrfCookieName || undefined
      }),
    /* Phase 9.5 §8.2: scheduled-publish monitor (last timer run + pending rows) and the manual run. */
    getScheduledPublish: () => request('/api/admin/scheduled-publish'),
    runScheduledPublish: csrfCookieName => request('/api/admin/scheduled-publish/run', {
      method: 'POST', body: {}, csrfWrite: true, csrfCookie: csrfCookieName || undefined
    }),
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
    /* فاز ۹ — حساب کاربر: «محتوای من» (دسترسی‌های واقعی با وضعیت فعال/منقضی/لغوشده) و
       «سفارش‌ها و پرداخت‌ها» (سفارش‌های محتوای ضبط‌شده). هیچ‌کدام دسترسی نمی‌سازند؛ فقط می‌خوانند. */
    getAccountRecordings: () => request('/api/account/recordings'),
    /* فاز ۹.۲ — «گواهینامه‌های من»: آینهٔ سرور از صدور واقعی ربات؛ فقط خواندنی، فایل از ربات بله. */
    getAccountCertificates: () => request('/api/account/certificates'),
    getAccountRecordingOrders: (limit, offset) => request('/api/account/recording-orders?limit='
      + encodeURIComponent(String(limit || 50)) + '&offset=' + encodeURIComponent(String(offset || 0))),
    getAccountRecordingOrder: id => request('/api/account/recording-orders/' + encodeURIComponent(String(id))),
    cancelAccountRecordingOrder: id => request('/api/account/recording-orders/' + encodeURIComponent(String(id)) + '/cancel', {
      method: 'POST', body: {}, csrfWrite: true, csrfCookie: 'nora_account_csrf'
    }),
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
