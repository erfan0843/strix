/* نورا — بخش‌های تعاملی صفحهٔ رویداد (فاز ۸): فایل‌ها و منابع، پرسش‌وپاسخ، دیدگاه شرکت‌کنندگان.
   همهٔ داده‌ها و تصمیم‌های دسترسی از /api/public/events/{id}/interaction (با کوکی نشست) می‌آید؛
   این فایل فقط وضعیت سرور را نمایش می‌دهد و هیچ مجوزی را خودش حدس نمی‌زند. بدون سرور، چیزی رندر نمی‌شود. */
(function (root) {
  'use strict';

  const doc = root.document;
  if (!doc) return;
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const breaks = value => esc(value).replace(/\r?\n/g, '<br>');
  const fa = value => String(value == null ? '' : value).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
  const when = value => {
    const CD = root.NORA_COUNTDOWN;
    if (CD && typeof CD.formatMoment === 'function') return CD.formatMoment(value);
    const ms = Date.parse(value);
    if (!Number.isFinite(ms)) return '';
    try { return new Intl.DateTimeFormat('fa-IR-u-ca-persian', { timeZone: 'Asia/Tehran', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(ms)); }
    catch (_) { return new Date(ms).toISOString(); }
  };
  const size = bytes => {
    const n = Number(bytes);
    if (!Number.isFinite(n) || n <= 0) return '';
    if (n < 1024) return fa(n) + ' بایت';
    if (n < 1048576) return fa((n / 1024).toFixed(n < 10240 ? 1 : 0)) + ' کیلوبایت';
    return fa((n / 1048576).toFixed(1)) + ' مگابایت';
  };
  const FORMAT = {
    'application/pdf': 'PDF', 'image/jpeg': 'JPG', 'image/png': 'PNG', 'image/webp': 'WebP',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PowerPoint',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'Word',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel',
    'application/zip': 'ZIP', 'audio/mpeg': 'MP3', 'video/mp4': 'ویدئو MP4', 'text/plain': 'متن'
  };
  const ACCESS = { public: 'عمومی', registered: 'ویژهٔ ثبت‌نام‌شدگان', attended: 'ویژهٔ شرکت‌کنندگان', purchased: 'ویژهٔ دارندگان دسترسی محتوای ضبط‌شده', staff: 'ویژهٔ برگزارکنندگان' };
  const REASON = {
    login_required: 'برای دریافت وارد حساب شوید',
    registration_required: 'نیازمند ثبت‌نام تأییدشده',
    attendance_required: 'ویژهٔ شرکت‌کنندگان با حضور تأییدشده',
    staff_only: 'فقط برای برگزارکنندگان',
    not_published: 'هنوز منتشر نشده',
    removed: 'برداشته شده',
    purchase_required: 'ویژهٔ دارندگان دسترسی محتوای ضبط‌شده',
    access_expired: 'مدت دسترسی شما به پایان رسیده',
    access_revoked: 'دسترسی شما لغو شده'
  };
  const ERRORS = {
    duplicate_question: 'همین پرسش را پیش‌تر ثبت کرده‌اید.',
    too_many_open_questions: 'چند پرسش بی‌پاسخ دارید؛ لطفاً تا پاسخ برگزارکننده صبر کنید.',
    qa_closed: 'پرسش‌وپاسخ این رویداد بسته است.',
    text_too_short: 'متن خیلی کوتاه است.',
    text_too_long: 'متن از حد مجاز بلندتر است.',
    text_required: 'متن را بنویسید.',
    review_not_eligible: 'ثبت دیدگاه فقط برای شرکت‌کنندگان با حضور تأییدشده یا دارندگان دسترسی محتوای ضبط‌شده ممکن است.',
    session_not_found: 'جلسهٔ انتخاب‌شده در دسترس نیست؛ پرسش را بدون جلسه ثبت کنید.',
    review_exists: 'برای این رویداد قبلاً دیدگاه ثبت کرده‌اید.',
    review_locked: 'این دیدگاه دیگر قابل ویرایش نیست.',
    authentication_required: 'نشست شما معتبر نیست؛ دوباره وارد شوید.',
    csrf_check_failed: 'نشست شما معتبر نیست؛ صفحه را نوسازی کنید.',
    rate_limited: 'تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید.',
    network: 'ارتباط با سرور برقرار نشد.'
  };
  const SOURCE_READY = () => root.NORA_PUBLIC_SOURCE === 'server';
  const S = { event: null, page: null, data: null, loading: false, error: '', busy: {}, msg: {}, editReview: false, questionSession: '' };

  function csrf() {
    const prefix = 'nora_account_csrf=';
    const item = String(doc.cookie || '').split(';').map(p => p.trim()).find(p => p.startsWith(prefix));
    if (!item) return '';
    try { return decodeURIComponent(item.slice(prefix.length)); } catch (_) { return item.slice(prefix.length); }
  }
  function loginHref(section) {
    const next = `event.html?id=${encodeURIComponent(String(S.event.id))}#${section}`;
    return `login.html?mode=server&next=${encodeURIComponent(next)}`;
  }
  function toast(message) { if (root.NORA_UI && typeof root.NORA_UI.toast === 'function') root.NORA_UI.toast(message); }

  async function api(path, options) {
    const opts = options || {};
    const headers = { Accept: 'application/json' };
    if (opts.body !== undefined) { headers['Content-Type'] = 'application/json'; headers['X-CSRF-Token'] = csrf(); }
    let response;
    try {
      response = await root.fetch(path, {
        method: opts.method || 'GET', headers, credentials: 'same-origin', cache: 'no-store', redirect: 'error',
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined
      });
    } catch (_) {
      throw { code: 'network', status: 0 };
    }
    let payload = null;
    try { payload = await response.json(); } catch (_) { payload = null; }
    if (!response || !response.ok) {
      const detail = payload && payload.detail;
      const code = detail && typeof detail === 'object' ? detail.code : (typeof detail === 'string' ? detail : '');
      throw { code: code || (response && response.status === 429 ? 'rate_limited' : 'server_error'), status: response ? response.status : 0, detail };
    }
    return payload;
  }
  function describe(error) {
    if (!error) return ERRORS.network;
    if (error.code && ERRORS[error.code]) return ERRORS[error.code];
    if (error.status === 401) return ERRORS.authentication_required;
    if (error.status === 403) return 'اجازهٔ این کار را ندارید.';
    if (error.status === 429) return ERRORS.rate_limited;
    if (error.status === 404) return 'این مورد دیگر در دسترس نیست.';
    return 'خطای سرور؛ کمی بعد دوباره تلاش کنید.';
  }

  function containers() {
    const page = S.page || doc;
    return {
      resources: page.querySelector('[data-event-interaction="resources"]'),
      qa: page.querySelector('[data-event-interaction="qa"]'),
      reviews: page.querySelector('[data-event-interaction="reviews"]')
    };
  }

  function section(id, title, inner, extra) {
    return `<section class="event-section ei-section" id="${esc(id)}" aria-labelledby="${esc(id)}-title">
      <div class="ei-head"><h2 id="${esc(id)}-title">${esc(title)}</h2>${extra || ''}</div>${inner}</section>`;
  }
  const loadingBox = label => `<p class="ei-state" role="status" aria-busy="true">${esc(label)}</p>`;
  const errorBox = (label, retryAttr) => `<div class="ei-state ei-error" role="alert"><span>${esc(label)}</span><button type="button" class="btn sm quiet" ${retryAttr}>تلاش دوباره</button></div>`;
  const emptyBox = label => `<p class="ei-state ei-empty">${esc(label)}</p>`;
  const message = key => S.msg[key] ? `<p class="ei-note ${S.msg[key].kind === 'ok' ? 'ok' : 'warn'}" role="status">${esc(S.msg[key].text)}</p>` : '';

  /* ── منابع ── */
  function resourceRow(row) {
    const kind = row.kind === 'link' ? 'پیوند' : row.kind === 'youtube' ? 'ویدیوی یوتیوب' : row.kind === 'aparat' ? 'ویدیوی آپارات' : (FORMAT[row.content_type] || 'فایل');
    const meta = [kind, row.kind === 'file' ? size(row.size) : '', ACCESS[row.access] || '',
      row.publisher ? `ناشر: ${row.publisher}` : '', row.publish_at ? `انتشار: ${when(row.publish_at)}` : ''].filter(Boolean);
    let action;
    if (row.allowed && row.kind === 'file') {
      action = `<a class="btn sm" href="/api/public/events/${encodeURIComponent(S.event.id)}/resources/${encodeURIComponent(row.id)}/download" download data-ei-download>دریافت فایل</a>`;
    } else if (row.allowed && row.kind === 'link' && /^https?:\/\//i.test(String(row.link_url || ''))) {
      action = `<a class="btn sm" href="${esc(row.link_url)}" target="_blank" rel="noopener noreferrer">بازکردن پیوند</a>`;
    } else if (row.allowed && embedOf(row)) {
      action = rEmbed(row, embedOf(row));
    } else if (row.allowed && (row.kind === 'youtube' || row.kind === 'aparat')) {
      action = `<span class="ei-lock">منبع ویدیو در سرور معتبر نیست؛ به برگزارکننده اطلاع دهید.</span>`;
    } else if (row.reason === 'login_required') {
      action = `<a class="btn sm quiet" href="${esc(loginHref('resources'))}">${esc(REASON.login_required)}</a>`;
    } else {
      const pending = row.reason === 'registration_required' && S.data.viewer.participation.pending;
      action = `<span class="ei-lock">${esc(pending ? 'ثبت‌نام شما هنوز نهایی نشده' : REASON[row.reason] || 'در دسترس نیست')}</span>`;
    }
    const staffNote = !row.published && S.data.viewer.staff ? `<span class="tag">${esc(row.status === 'draft' ? 'پیش‌نویس' : 'زمان‌بندی‌شده')}</span>` : '';
    return `<li class="ei-resource" data-resource="${esc(row.id)}"><div class="ei-resource-text"><b>${esc(row.title)}</b>${staffNote}
      ${row.description ? `<p>${breaks(row.description)}</p>` : ''}<small>${esc(meta.join(' · '))}</small></div><div class="ei-resource-action">${action}</div></li>`;
  }
  function renderResources(box) {
    if (!box) return;
    box.hidden = false;
    if (S.loading && !S.data) { box.innerHTML = section('resources', 'فایل‌ها و منابع', loadingBox('در حال خواندن منابع…')); return; }
    if (S.error && !S.data) { box.innerHTML = section('resources', 'فایل‌ها و منابع', errorBox(S.error, 'data-ei-retry')); return; }
    const rows = S.data.resources || [];
    const inner = rows.length ? `<ul class="ei-list">${rows.map(resourceRow).join('')}</ul>`
      : emptyBox('برای این رویداد هنوز فایل یا پیوندی منتشر نشده است.');
    box.innerHTML = section('resources', 'فایل‌ها و منابع', inner);
    wireEmbeds(box);
  }

  /* ── پرسش‌وپاسخ ── */
  function sessionTitle(id) {
    if (!id || !R.data || !Array.isArray(R.data.sessions)) return '';
    const s = R.data.sessions.find(x => x && x.id === id);
    return s ? String(s.title || '') : '';
  }
  function questionRow(row) {
    const anchor = row.session_id ? `<span class="tag" data-ei-session-tag="${esc(row.session_id)}">${esc(sessionTitle(row.session_id) || 'دربارهٔ یکی از جلسات')}</span>` : '';
    const status = row.mine && row.status !== 'published'
      ? `<span class="tag ${row.status === 'hidden' ? 'stop' : ''}">${esc(row.status === 'hidden' ? 'پنهان‌شده' : 'در انتظار بررسی')}</span>` : '';
    const answer = row.answered
      ? `<div class="ei-answer"><b>${esc(row.answer_label || 'برگزارکننده')}${row.answer_official ? ' · پاسخ رسمی' : ''}</b><p>${breaks(row.answer)}</p><small>${esc(when(row.answered_at))}</small></div>`
      : `<small class="ei-wait">${esc(row.mine ? 'هنوز پاسخ داده نشده' : 'در انتظار پاسخ برگزارکننده')}</small>`;
    const report = !row.mine && S.data.viewer.signed_in && !S.data.viewer.staff
      ? (row.reported ? '<small class="ei-wait">گزارش شما ثبت شد</small>' : `<button type="button" class="ei-link" data-ei-report="question" data-id="${esc(row.id)}">گزارش محتوای نامناسب</button>`)
      : '';
    return `<li class="ei-question" data-question="${esc(row.id)}"><div class="ei-byline"><b>${esc(row.author)}</b>${row.mine ? '<span class="tag brand">شما</span>' : ''}${anchor}${status}<small>${esc(when(row.created_at))}</small></div>
      <p>${breaks(row.body)}</p>${answer}${report ? `<div class="ei-actions">${report}</div>` : ''}</li>`;
  }
  function qaForm() {
    const viewer = S.data.viewer, ev = S.data.event;
    if (!ev.qa_open) return `<p class="registration-notice" role="status">${esc(ev.qa_closed_reason === 'cancelled' ? 'این رویداد لغو شده و پرسش تازه پذیرفته نمی‌شود.' : 'پرسش‌وپاسخ این رویداد بسته شده است؛ پرسش‌های پاسخ‌داده‌شده همچنان قابل مشاهده‌اند.')}</p>`;
    if (!viewer.signed_in) return `<div class="ei-login"><span>برای پرسیدن، وارد حساب شوید.</span><a class="btn sm" href="${esc(loginHref('qa'))}">ورود</a></div>`;
    const busy = !!S.busy.question;
    const sessions = R.data && Array.isArray(R.data.sessions) ? R.data.sessions.filter(x => x && x.id && x.status === 'published') : [];
    const picker = sessions.length ? `<label class="cap" for="eiQuestionSession">دربارهٔ کدام بخش؟ (اختیاری)</label>
      <select id="eiQuestionSession" class="input" data-ei-question-session ${busy ? 'disabled' : ''}><option value="">کل رویداد</option>${sessions.map(x => `<option value="${esc(x.id)}" ${S.questionSession === x.id ? 'selected' : ''}>${esc(x.title)}</option>`).join('')}</select>` : '';
    return `<form class="ei-form" data-ei-form="question" novalidate>
      ${picker}
      <label class="cap" for="eiQuestionBody">پرسش شما (حداکثر ۱۰۰۰ نویسه)</label>
      <textarea id="eiQuestionBody" class="input" rows="3" maxlength="1000" required placeholder="پرسش خود را دربارهٔ همین رویداد بنویسید…" ${busy ? 'disabled' : ''}></textarea>
      <div class="ei-form-row"><small class="cap">پرسش پس از بررسی برگزارکننده منتشر می‌شود.</small><button type="submit" class="btn sm primary" ${busy ? 'disabled' : ''}>${busy ? 'در حال ارسال…' : 'ثبت پرسش'}</button></div>
      ${message('question')}</form>`;
  }
  function renderQa(box) {
    if (!box) return;
    box.hidden = false;
    if (S.loading && !S.data) { box.innerHTML = section('qa', 'پرسش‌وپاسخ', loadingBox('در حال خواندن پرسش‌ها…')); return; }
    if (S.error && !S.data) { box.innerHTML = section('qa', 'پرسش‌وپاسخ', errorBox(S.error, 'data-ei-retry')); return; }
    const q = S.data.questions, ev = S.data.event;
    const chip = `<span class="reg-state ${ev.qa_open ? 'live' : 'stop'}">${esc(ev.qa_open ? 'باز' : 'بسته')}</span>`;
    const list = q.items.length ? `<ul class="ei-list">${q.items.map(questionRow).join('')}</ul>`
      : emptyBox(ev.qa_open ? 'هنوز پرسشی ثبت نشده است؛ نخستین پرسش را شما بپرسید.' : 'پرسشی برای این رویداد منتشر نشده است.');
    box.innerHTML = section('qa', 'پرسش‌وپاسخ', `${qaForm()}${list}`, chip);
  }

  /* ── دیدگاه‌ها ── */
  function reviewRow(row) {
    const kind = row.badge || (row.verified_attendee ? 'attendee' : '');
    const badge = kind === 'attendee' ? '<span class="tag ok" data-ei-badge="attendee">شرکت‌کنندهٔ تأییدشده</span>'
      : kind === 'buyer' ? '<span class="tag ok" data-ei-badge="buyer">خریدار تأییدشده</span>' : '';
    const own = row.mine && row.status !== 'published'
      ? `<span class="tag ${row.status === 'hidden' ? 'stop' : ''}">${esc(row.status === 'hidden' ? 'پنهان‌شده' : row.status === 'withdrawn' ? 'پس‌گرفته‌شده' : 'در انتظار تأیید')}</span>` : '';
    const report = !row.mine && S.data.viewer.signed_in && !S.data.viewer.staff
      ? (row.reported ? '<small class="ei-wait">گزارش شما ثبت شد</small>' : `<button type="button" class="ei-link" data-ei-report="review" data-id="${esc(row.id)}">گزارش محتوای نامناسب</button>`)
      : '';
    return `<li class="ei-review" data-review="${esc(row.id)}"><div class="ei-byline"><b>${esc(row.author)}</b>${badge}${row.mine ? '<span class="tag brand">شما</span>' : ''}${own}<small>${esc(when(row.created_at))}${row.edited ? ' · ویرایش‌شده' : ''}</small></div>
      <p>${breaks(row.body)}</p>${report ? `<div class="ei-actions">${report}</div>` : ''}</li>`;
  }
  function reviewForm() {
    const viewer = S.data.viewer, r = S.data.reviews, mine = r.mine;
    const busy = !!S.busy.review;
    if (mine && !S.editReview) {
      const can = mine.status === 'pending' || mine.status === 'published';
      const state = mine.status === 'published' ? 'منتشرشده' : mine.status === 'pending' ? 'در انتظار تأیید برگزارکننده' : mine.status === 'hidden' ? 'پنهان‌شده توسط برگزارکننده' : 'پس‌گرفته‌شده';
      return `<div class="ei-mine"><div class="ei-byline"><b>دیدگاه شما</b><span class="tag">${esc(state)}</span></div><p>${breaks(mine.body)}</p>
        ${can ? `<div class="ei-actions"><button type="button" class="btn sm quiet" data-ei-edit-review ${busy ? 'disabled' : ''}>ویرایش</button><button type="button" class="btn sm quiet" data-ei-withdraw-review ${busy ? 'disabled' : ''}>پس‌گرفتن</button></div>` : ''}
        ${message('review')}</div>`;
    }
    const sellable = !!(S.data.recording && S.data.recording.sellable);
    const who = sellable ? 'شرکت‌کنندگان با حضور تأییدشده و دارندگان دسترسی محتوای ضبط‌شده' : 'شرکت‌کنندگان با حضور تأییدشده';
    if (!viewer.signed_in) return `<div class="ei-login"><span>دیدگاه‌ها فقط از ${esc(who)} پذیرفته می‌شود.</span><a class="btn sm quiet" href="${esc(loginHref('reviews'))}">ورود</a></div>`;
    if (!r.eligible) {
      const p = viewer.participation;
      return `<p class="registration-notice" role="status">${esc(p.registered ? 'ثبت‌نام شما ثبت شده است؛ پس از تأیید حضور در رویداد' + (sellable ? ' یا با دریافت دسترسی محتوای ضبط‌شده' : '') + ' می‌توانید دیدگاه بنویسید.' : 'ثبت دیدگاه فقط برای ' + who + ' ممکن است.')}</p>`;
    }
    const badgeLabel = r.badge === 'buyer' ? 'خریدار تأییدشده' : 'شرکت‌کنندهٔ تأییدشده';
    return `<form class="ei-form" data-ei-form="review" novalidate>
      <label class="cap" for="eiReviewBody">${esc(S.editReview ? 'ویرایش دیدگاه (پس از ویرایش دوباره بررسی می‌شود)' : 'دیدگاه شما دربارهٔ این رویداد (بدون امتیاز؛ فقط متن)')}</label>
      <textarea id="eiReviewBody" class="input" rows="3" maxlength="1500" required placeholder="تجربهٔ خود از این رویداد را بنویسید…" ${busy ? 'disabled' : ''}>${esc(S.editReview && mine ? mine.body : '')}</textarea>
      <div class="ei-form-row"><small class="cap">پس از تأیید برگزارکننده با نشان «${esc(badgeLabel)}» منتشر می‌شود.</small>
        ${S.editReview ? '<button type="button" class="btn sm quiet" data-ei-cancel-edit>انصراف</button>' : ''}
        <button type="submit" class="btn sm primary" ${busy ? 'disabled' : ''}>${busy ? 'در حال ارسال…' : (S.editReview ? 'ذخیرهٔ ویرایش' : 'ثبت دیدگاه')}</button></div>
      ${message('review')}</form>`;
  }
  function renderReviews(box) {
    if (!box) return;
    box.hidden = false;
    if (S.loading && !S.data) { box.innerHTML = section('reviews', 'دیدگاه شرکت‌کنندگان', loadingBox('در حال خواندن دیدگاه‌ها…')); return; }
    if (S.error && !S.data) { box.innerHTML = section('reviews', 'دیدگاه شرکت‌کنندگان', errorBox(S.error, 'data-ei-retry')); return; }
    const r = S.data.reviews;
    const others = r.items.filter(row => !row.mine);
    const list = others.length ? `<ul class="ei-list">${others.map(reviewRow).join('')}</ul>`
      : emptyBox('هنوز دیدگاهی منتشر نشده است.');
    box.innerHTML = section('reviews', 'دیدگاه شرکت‌کنندگان', `${reviewForm()}${list}`);
  }

  /* ── فاز ۹: محصول ضبط‌شدهٔ همین رویداد ──
     همهٔ متن، جلسات، وضعیت دسترسی و «تنها دکمهٔ اقدام» از /api/public/events/{id}/recording می‌آید.
     این بخش هیچ وضعیتی را از داده‌های مرورگر نتیجه نمی‌گیرد: خرید ≠ ثبت‌نام ≠ حضور؛ رسید فقط «ارسال» می‌شود
     و دسترسی تنها پس از تأیید سرور (بررسی رسید یا رویداد تأییدشدهٔ بله) باز می‌شود. بدون شمارش معکوس، بدون شمارندهٔ ساختگی. */
  const R = { data: null, loading: false, error: '', status: 0, busy: '', msg: null, method: '', note: '' };
  const R_ORDER_STATUS = {
    pending: 'در انتظار پرداخت در بله', awaiting_receipt: 'در انتظار واریز و ارسال رسید', receipt_submitted: 'رسید ارسال شد؛ در انتظار بررسی برگزارکننده',
    needs_review: 'پرداخت نیازمند بررسی برگزارکننده', paid: 'پرداخت تأیید شد', paid_manual: 'پرداخت تأیید شد', rejected: 'سفارش رد شد',
    cancelled: 'سفارش لغو شد', expired: 'مهلت سفارش گذشت', refunded: 'بازپرداخت شد'
  };
  const R_ACCESS_REASON = { purchased: 'دسترسی خریداری‌شده', free: 'دسترسی رایگان', granted: 'دسترسی اعطاشده', attendee: 'دسترسی شرکت‌کنندهٔ تأییدشده', staff: 'پیش‌نمایش کادر', preview: 'پیش‌نمایش رایگان',
    access_expired: 'مدت دسترسی شما به پایان رسیده است', access_revoked: 'دسترسی شما لغو شده است', purchase_required: 'نیازمند دسترسی', login_required: 'برای دسترسی وارد حساب شوید', not_published: 'هنوز منتشر نشده' };
  const R_ERRORS = {
    recording_not_free: 'این محتوا رایگان نیست.', access_already_active: 'شما هم‌اکنون دسترسی فعال دارید.', recording_is_free: 'این محتوا رایگان است؛ نیازی به سفارش نیست.',
    payment_method_not_available: 'این روش پرداخت فعلاً در دسترس نیست.', bale_identity_required: 'پرداخت با کیف پول بله فقط با حساب پیوندخورده به بله ممکن است.',
    order_not_awaiting_receipt: 'این سفارش در وضعیت دریافت رسید نیست.', order_not_cancellable: 'این سفارش دیگر قابل لغو نیست.', file_too_large: 'حجم رسید بیش از ۸ مگابایت است.',
    file_type_not_allowed: 'رسید باید تصویر (JPG/PNG/WebP) یا PDF باشد.', file_empty: 'فایل رسید خالی است.', upload_rate_limited: 'شمار بارگذاری‌ها زیاد است؛ کمی بعد دوباره تلاش کنید.',
    sales_paused: 'فروش این محتوا فعلاً متوقف است.', recording_not_available: 'این محتوا در دسترس نیست.',
    use_purchase_form: 'خرید فقط از فرم خرید همین محصول انجام می‌شود.', order_follows_form_payment: 'این سفارش به پرداخت فرم خرید وابسته است و از این‌جا لغو نمی‌شود.',
    recording_not_on_sale: 'این محتوا الان در فروش نیست.', account_required: 'برای خرید باید وارد حساب شوید.'
  };
  function rCertificate(d) {
    const c = d && d.certificate;
    if (!c || c.automatic) return '';
    return c.policy === 'manual'
      ? 'گواهی «پایان محتوای آموزشی ضبط‌شده» فقط با تأیید و صدور دستی برگزارکننده؛ خرید یا تماشا به‌تنهایی گواهی نمی‌سازد و با گواهی حضور رویداد یکی نیست'
      : 'برای این محتوا گواهی صادر نمی‌شود (خرید، حضور در رویداد به شمار نمی‌آید)';
  }
  const rMoney = value => (Number(value) > 0 ? `${fa(Number(value).toLocaleString('en-US'))} ریال` : 'رایگان');
  const rMinutes = value => { const n = Number(value) || 0; if (!n) return ''; const h = Math.floor(n / 60), m = n % 60; return h ? `${fa(h)} ساعت${m ? ` و ${fa(m)} دقیقه` : ''}` : `${fa(m)} دقیقه`; };
  const rDescribe = error => (error && error.code && R_ERRORS[error.code]) ? R_ERRORS[error.code] : describe(error);
  function rContainers() {
    const page = S.page || doc;
    return { section: page.querySelector('[data-event-interaction="recording"]'), aside: doc.querySelector('[data-recording-aside]'), toolbar: doc.querySelector('[data-recording-toolbar]') };
  }
  function rLoginHref() { return loginHref('recording'); }
  /* فاز ۹.۱: ورودی استاندارد خرید، فرم خریدِ فرم‌ساز است (purpose=recording_access)؛ شناسهٔ فرم از سرور می‌آید. */
  function rFormHref(formId) { return /^[A-Za-z0-9_-]{1,100}$/.test(String(formId || '')) ? `form.html?fid=${encodeURIComponent(String(formId))}&kind=reg` : ''; }
  function rFileHref(id) { return `/api/public/events/${encodeURIComponent(String(S.event.id))}/resources/${encodeURIComponent(id)}/download`; }
  /* فاز ۹.۱ §۳: پخش‌کنندهٔ بیرونی فقط از نشانی رسمی‌ای ساخته می‌شود که سرور از شناسهٔ اعتبارسنجی‌شده تولید کرده است؛
     هیچ HTML از سرور یا کاربر تزریق نمی‌شود و اگر نشانی خارج از دو مبدأ مجاز باشد، هیچ قابی ساخته نمی‌شود. */
  const EMBED_ORIGINS = ['https://www.youtube-nocookie.com/embed/', 'https://www.aparat.com/video/video/embed/videohash/'];
  const EMBED_NAME = { youtube: 'یوتیوب', aparat: 'آپارات' };
  const EMBED_SLOW_MS = 12000;
  function embedOf(row) {
    const v = row && row.video;
    if (!v || typeof v !== 'object') return null;
    const embed = String(v.embed_url || ''), watch = String(v.watch_url || '');
    if (!EMBED_ORIGINS.some(origin => embed.startsWith(origin)) || !/^https:\/\/www\.(youtube|aparat)\.com\//.test(watch)) return null;
    return { provider: v.provider === 'aparat' ? 'aparat' : 'youtube', embed, watch };
  }
  function rEmbed(row, video) {
    const name = EMBED_NAME[video.provider];
    return `<div class="ei-embed" data-rec-embed="${esc(row.id)}" data-embed-provider="${esc(video.provider)}" data-embed-state="loading">
        <iframe src="${esc(video.embed)}" title="${esc(row.title)}" loading="lazy" referrerpolicy="strict-origin-when-cross-origin" allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen" allowfullscreen data-rec-embed-frame="${esc(row.id)}"></iframe>
        <div class="ei-embed-state" role="status" data-rec-embed-state><span data-embed-text>در حال بارگذاری پخش‌کنندهٔ ${esc(name)}…</span></div></div>
      <p class="ei-embed-note"><span data-embed-playback-note></span> پخش از ${esc(name)} (میزبانی بیرونی؛ بدون حفاظت یا DRM از سوی نورا). اگر ویدیو خصوصی، حذف‌شده یا «غیرقابل‌جاسازی» باشد یا شناسه‌اش اشتباه ثبت شده باشد، همان پیام یا کد خطای خود ${esc(name)} در قاب دیده می‌شود و نورا نمی‌تواند آن را برطرف کند؛ در این حالت از پیوند روبه‌رو در خود سکو ببینید یا به برگزارکننده اطلاع دهید. <a href="${esc(video.watch)}" target="_blank" rel="noopener noreferrer" data-rec-embed-open="${esc(row.id)}">باز کردن در ${esc(name)}</a></p>`;
  }
  function wireEmbeds(scope) {
    const win = doc.defaultView || window;
    (scope || doc).querySelectorAll('.ei-embed[data-embed-state="loading"]').forEach(box => {
      const frame = box.querySelector('iframe');
      const text = box.querySelector('[data-embed-text]');
      if (!frame) return;
      const slow = win.setTimeout(() => {
        if (box.getAttribute('data-embed-state') !== 'loading') return;
        box.setAttribute('data-embed-state', 'slow');
        if (text) text.textContent = 'پخش‌کننده هنوز بارگذاری نشده است (شبکه یا فیلترینگ؟). می‌توانید ویدیو را مستقیم در ' + (EMBED_NAME[box.getAttribute('data-embed-provider')] || 'سکوی میزبان') + ' باز کنید.';
      }, EMBED_SLOW_MS);
      frame.addEventListener('load', () => {
        win.clearTimeout(slow); box.setAttribute('data-embed-state', 'ready');
        /* «load» فقط یعنی قاب پاسخ داد (حتی صفحهٔ خطای مرورگر)؛ پخش یا خطای ویدیو را خود سکو داخل قاب نشان می‌دهد و نورا آن را تأیید نمی‌کند. */
        box.setAttribute('data-embed-playback', 'unverified');
        const note = box.parentElement && box.parentElement.querySelector('[data-embed-playback-note]');
        if (note) note.textContent = 'پخش‌کننده بارگذاری شد؛ پخش و خطاهای ویدیو را خود ' + (EMBED_NAME[box.getAttribute('data-embed-provider')] || 'سکو') + ' داخل قاب نشان می‌دهد و نورا آن را تأیید نمی‌کند.';
      }, { once: true });
      frame.addEventListener('error', () => { win.clearTimeout(slow); box.setAttribute('data-embed-state', 'error'); if (text) text.textContent = 'پخش‌کننده بارگذاری نشد؛ از پیوند زیر در خود سکو ببینید.'; }, { once: true });
    });
  }

  function rCta(compact) {
    const d = R.data; if (!d) return '';
    const v = d.viewer, cta = v.cta || { kind: 'unavailable' }, kind = cta.kind;
    const expiry = v.access && v.access.expires_at ? `<small class="ei-rec-expiry">دسترسی تا ${esc(when(v.access.expires_at))}</small>` : '';
    const busyAttr = R.busy ? ' disabled aria-busy="true"' : '';
    if (kind === 'view') return `<a class="btn primary" href="#recording-sessions" data-rec-view>مشاهدهٔ جلسات</a>${expiry}${compact ? '' : `<small class="ei-rec-why">${esc(R_ACCESS_REASON[v.access.reason] || 'دسترسی فعال')}</small>`}`;
    if (kind === 'staff_preview') return `<span class="tag">پیش‌نمایش کادر؛ خرید از این حساب انجام نمی‌شود</span>`;
    if (kind === 'login') return `<a class="btn primary" href="${esc(rLoginHref())}" data-rec-login>${d.free ? 'ورود برای دریافت دسترسی رایگان' : 'ورود برای خرید دسترسی'}</a>`;
    if (kind === 'free') return `<button type="button" class="btn primary" data-rec-claim${busyAttr}>${R.busy === 'claim' ? 'در حال ثبت…' : 'دریافت دسترسی رایگان'}</button>${compact ? '' : '<small class="ei-rec-why">بدون پرداخت و بدون تراکنش؛ دسترسی روی حساب شما ثبت می‌شود.</small>'}`;
    if (kind === 'off_sale') return `<span class="ei-lock" data-rec-off-sale>${esc(cta.reason === 'no_payment_method' || cta.reason === 'purchase_form_required' || cta.reason === 'purchase_form_not_published' ? 'فروش این محتوا فعلاً فعال نیست' : 'فروش این محتوا فعلاً متوقف است')}</span>`;
    if (kind === 'order_open') return compact ? `<a class="btn primary" href="#recording-order" data-rec-continue>${esc(R_ORDER_STATUS[cta.reason] || 'ادامهٔ سفارش')}</a>` : '';
    if (kind === 'buy') {
      const methods = Array.isArray(cta.methods) ? cta.methods : [];
      const formHref = rFormHref(cta.form_id);
      const prev = cta.previous && cta.previous.status ? `<small class="ei-rec-why" data-rec-previous="${esc(cta.previous.status)}">${esc(R_ORDER_STATUS[cta.previous.status] || '')}؛ می‌توانید دوباره تلاش کنید.</small>` : '';
      if (!formHref) return `<span class="ei-lock" data-rec-off-sale>فرم خرید این محتوا در دسترس نیست</span>`;
      if (compact) return `<a class="btn primary" href="${esc(formHref)}" data-rec-buy>خرید دسترسی · ${esc(rMoney(d.price))}</a>`;
      const how = methods.map(m => m === 'bale_wallet' ? 'کیف پول بله' : 'کارت‌به‌کارت با بررسی رسید').join(' یا ');
      return `<a class="btn primary" href="${esc(formHref)}" data-rec-buy>خرید دسترسی · ${esc(rMoney(d.price))}</a><small class="ei-rec-why">خرید از فرم خرید همین محصول انجام می‌شود${how ? ` (${esc(how)})` : ''}؛ مبلغ و روش پرداخت را سرور تعیین می‌کند.</small>${prev}`;
    }
    return `<span class="ei-lock">این محتوا در دسترس نیست</span>`;
  }
  function rOrderPanel() {
    const d = R.data; const cta = d && d.viewer.cta;
    if (!cta || cta.kind !== 'order_open' || !cta.order) return '';
    const o = cta.order, status = o.status;
    let body = '';
    const formHref = rFormHref(cta.form_id);
    if (o.form_payment_id || o.form_response_id) {
      /* سفارش فرم‌دار (۹.۱): رسید/پرداخت در خود فرم خرید دنبال می‌شود؛ این‌جا فقط وضعیت واقعی و پیوند ادامه. */
      body += `<p class="cap" data-rec-order-via-form>این سفارش از فرم خرید ثبت شده است. ${esc(status === 'receipt_submitted' ? 'رسید در صف بررسی برگزارکننده است؛ دسترسی فقط پس از تأیید فعال می‌شود.' : status === 'awaiting_receipt' ? 'پس از واریز، رسید را در همان فرم خرید بارگذاری کنید.' : status === 'pending' ? 'پرداخت در بله هنوز تأیید نشده است؛ وضعیت فقط از سرور خوانده می‌شود.' : 'نتیجه پس از بررسی در حساب شما ثبت می‌شود.')}</p>
        <div class="ei-form-row">${formHref ? `<a class="btn primary" href="${esc(formHref)}" data-rec-continue-form>ادامه در فرم خرید</a>` : ''}<button type="button" class="btn sm quiet" data-rec-refresh>بررسی وضعیت</button><a class="btn sm quiet" href="account.html#payments">سفارش‌ها و پرداخت‌ها</a></div>`;
    } else if (o.method === 'card_transfer' && (status === 'awaiting_receipt' || status === 'receipt_submitted')) {
      const card = o.card || {};
      body += `<dl class="ei-rec-card"><div><dt>مبلغ قابل واریز</dt><dd>${esc(rMoney(o.amount))}</dd></div>
        ${card.number ? `<div><dt>شمارهٔ کارت</dt><dd dir="ltr">${esc(String(card.number).replace(/(\d{4})(?=\d)/g, '$1-'))}</dd></div>` : ''}
        ${card.bank ? `<div><dt>بانک</dt><dd>${esc(card.bank)}</dd></div>` : ''}${card.holder ? `<div><dt>به نام</dt><dd>${esc(card.holder)}</dd></div>` : ''}
        ${o.expires_at ? `<div><dt>مهلت ارسال رسید</dt><dd>${esc(when(o.expires_at))}</dd></div>` : ''}</dl>`;
      /* سفارش قدیمی (پیش از ۹.۱) بدون فرم: ارسال رسید از این صفحه بازنشسته شده است؛ مسیر درست، فرم خرید است. */
      body += status === 'receipt_submitted'
        ? `<p class="ei-note ok" role="status">رسید «${esc(o.receipt_file_name || 'فایل')}» در ${esc(when(o.receipt_submitted_at))} ارسال شد. دسترسی فقط پس از بررسی و تأیید برگزارکننده فعال می‌شود؛ نتیجه در «سفارش‌ها و پرداخت‌ها»ی حساب شما ثبت می‌شود.</p>`
        : `<p class="ei-note warn" role="status" data-rec-legacy-order>این سفارش از مسیر قدیمی ثبت شده و رسید آن دیگر از این صفحه پذیرفته نمی‌شود. اگر هنوز واریز نکرده‌اید، سفارش را لغو کنید و از «فرم خرید» ادامه دهید؛ اگر واریز کرده‌اید، با برگزارکننده تماس بگیرید.</p>`;
      body += `<div class="ei-form-row">${status === 'awaiting_receipt' ? `<button type="button" class="btn sm quiet" data-rec-cancel${R.busy ? ' disabled' : ''}>انصراف از سفارش</button>` : ''}${formHref ? `<a class="btn primary" href="${esc(formHref)}" data-rec-continue-form>فرم خرید</a>` : ''}<button type="button" class="btn sm quiet" data-rec-refresh>بررسی وضعیت</button></div>`;
    } else if (o.method === 'bale_wallet' && status === 'pending') {
      body += `<p class="cap">مبلغ ${esc(rMoney(o.amount))} از طریق کیف پول بله پرداخت می‌شود. دسترسی تنها پس از تأیید پرداخت توسط سرور (نه با بازگشت از صفحهٔ پرداخت) فعال می‌شود.${o.expires_at ? ` مهلت پرداخت: ${esc(when(o.expires_at))}.` : ''}</p>
        <div class="ei-form-row">${/^https:\/\//i.test(String(o.invoice_url || '')) ? `<a class="btn primary" href="${esc(o.invoice_url)}" target="_blank" rel="noopener noreferrer" data-rec-invoice>ادامهٔ پرداخت در بله</a>` : '<span class="ei-lock">پیوند پرداخت در دسترس نیست</span>'}
        <button type="button" class="btn sm quiet" data-rec-refresh>بررسی وضعیت</button><button type="button" class="btn sm quiet" data-rec-cancel${R.busy ? ' disabled' : ''}>انصراف</button></div>`;
    } else {
      body += `<p class="ei-note warn" role="status">${esc(R_ORDER_STATUS[status] || status)}. نتیجه پس از بررسی در حساب شما ثبت می‌شود.</p><div class="ei-form-row"><button type="button" class="btn sm quiet" data-rec-refresh>بررسی وضعیت</button></div>`;
    }
    return `<div class="ei-rec-order" id="recording-order" data-ei-order-panel="${esc(status)}"><div class="ei-byline"><b>سفارش شما</b><span class="tag">${esc(R_ORDER_STATUS[status] || status)}</span></div>${body}</div>`;
  }
  function rResourceRow(row, sessionPreview) {
    const label = row.kind === 'link' ? 'پیوند' : row.kind === 'youtube' ? 'ویدیوی یوتیوب' : row.kind === 'aparat' ? 'ویدیوی آپارات' : (FORMAT[row.content_type] || (row.content_type === 'video/mp4' ? 'ویدئو' : 'فایل'));
    const meta = [label, row.kind === 'file' ? size(row.size) : '', row.external ? 'میزبانی بیرونی' : '', row.delivery === 'view' ? 'فقط مشاهدهٔ برخط' : row.downloadable ? 'قابل دانلود' : '', row.preview || sessionPreview ? 'پیش‌نمایش رایگان' : ''].filter(Boolean).join(' · ');
    let action = '';
    if (row.allowed && row.kind === 'file' && row.playable && row.content_type === 'video/mp4') {
      action = `<video controls playsinline preload="none" ${row.downloadable ? '' : 'controlsList="nodownload"'} src="${esc(rFileHref(row.id))}" data-rec-player="${esc(row.id)}">پخش ویدئو در این مرورگر پشتیبانی نمی‌شود.</video>`;
      if (row.downloadable) action += `<a class="btn sm quiet" href="${esc(rFileHref(row.id))}" download data-rec-download="${esc(row.id)}">دریافت فایل</a>`;
    } else if (row.allowed && row.kind === 'file' && row.content_type === 'audio/mpeg') {
      action = `<audio controls preload="none" src="${esc(rFileHref(row.id))}" data-rec-player="${esc(row.id)}"></audio>${row.downloadable ? `<a class="btn sm quiet" href="${esc(rFileHref(row.id))}" download data-rec-download="${esc(row.id)}">دریافت فایل</a>` : ''}`;
    } else if (row.allowed && row.kind === 'file') {
      action = row.downloadable
        ? `<a class="btn sm" href="${esc(rFileHref(row.id))}" download data-rec-download="${esc(row.id)}">دریافت فایل</a>`
        : `<a class="btn sm" href="${esc(rFileHref(row.id))}" target="_blank" rel="noopener" data-rec-open="${esc(row.id)}">مشاهدهٔ فایل</a>`;
    } else if (row.allowed && row.kind === 'link' && /^https?:\/\//i.test(String(row.link_url || ''))) {
      action = `<a class="btn sm" href="${esc(row.link_url)}" target="_blank" rel="noopener noreferrer">بازکردن پیوند</a>`;
    } else if (row.allowed && embedOf(row)) {
      action = rEmbed(row, embedOf(row));
    } else if (row.allowed && (row.kind === 'youtube' || row.kind === 'aparat')) {
      action = `<span class="ei-lock" data-rec-embed-invalid="${esc(row.id)}">منبع ویدیو در سرور معتبر نیست؛ به برگزارکننده اطلاع دهید.</span>`;
    } else if (row.reason === 'login_required') {
      action = `<a class="btn sm quiet" href="${esc(rLoginHref())}">${esc(R_ACCESS_REASON.login_required)}</a>`;
    } else {
      action = `<span class="ei-lock" data-rec-locked="${esc(row.id)}">${esc(R_ACCESS_REASON[row.reason] || 'قفل')}</span>`;
    }
    return `<li class="ei-resource" data-rec-resource="${esc(row.id)}"><div class="ei-resource-text"><b>${esc(row.title)}</b>${row.status && row.status !== 'published' ? `<span class="tag">${esc(row.status === 'draft' ? 'پیش‌نویس' : 'زمان‌بندی‌شده')}</span>` : ''}
      ${row.description ? `<p>${breaks(row.description)}</p>` : ''}<small>${esc(meta)}</small></div><div class="ei-resource-action ei-rec-action">${action}</div></li>`;
  }
  function rSession(row, index) {
    const dur = rMinutes(row.duration_minutes);
    const res = Array.isArray(row.resources) ? row.resources : [];
    return `<li class="ei-rec-session" data-rec-session="${esc(row.id)}"><div class="ei-byline"><b>${fa(index + 1)}. ${esc(row.title)}</b>${row.preview ? '<span class="tag">پیش‌نمایش رایگان</span>' : ''}${row.status && row.status !== 'published' ? `<span class="tag stop">${esc(row.status === 'draft' ? 'پیش‌نویس' : 'پنهان')}</span>` : ''}${dur ? `<small>${esc(dur)}</small>` : ''}</div>
      ${row.description ? `<p>${breaks(row.description)}</p>` : ''}
      ${res.length ? `<ul class="ei-list ei-rec-files">${res.map(r => rResourceRow(r, row.preview)).join('')}</ul>` : '<small class="ei-wait">فایلی برای این جلسه منتشر نشده است.</small>'}</li>`;
  }
  function rBlock(title, text) { return text ? `<div class="ei-rec-block"><b>${esc(title)}</b><p>${breaks(text)}</p></div>` : ''; }
  function renderRecording() {
    const boxes = rContainers();
    const box = boxes.section;
    const fill = (node, html) => { if (node) node.innerHTML = html; };
    if (!box) return;
    if (R.status === 404 || (R.data && R.data.viewer && R.data.viewer.cta && R.data.viewer.cta.kind === 'unavailable' && !R.data.viewer.staff)) {
      box.hidden = true; box.innerHTML = '';
      fill(boxes.aside, '<p class="cap">محتوای ضبط‌شدهٔ این رویداد هنوز منتشر نشده است.</p>'); fill(boxes.toolbar, '');
      return;
    }
    box.hidden = false;
    if (R.loading && !R.data) { box.innerHTML = section('recording', 'محتوای ضبط‌شده', loadingBox('در حال خواندن محتوای ضبط‌شده…')); return; }
    if (R.error && !R.data) { box.innerHTML = section('recording', 'محتوای ضبط‌شده', errorBox(R.error, 'data-rec-retry')); fill(boxes.aside, errorBox(R.error, 'data-rec-retry')); return; }
    const d = R.data, v = d.viewer, sessions = Array.isArray(d.sessions) ? d.sessions : [];
    const facts = [
      ['قیمت', rMoney(d.price)],
      ['مدت دسترسی', d.access_days ? `${fa(d.access_days)} روز پس از فعال‌شدن` : 'دائمی'],
      ['نحوهٔ دریافت', d.download_default ? 'مشاهدهٔ برخط و دانلود (هر فایل طبق تنظیم خود)' : 'مشاهدهٔ برخط (دانلود فقط برای فایل‌های مجاز)'],
      ['جلسات', d.session_count ? `${fa(d.session_count)} جلسه${d.total_minutes ? ` · ${rMinutes(d.total_minutes)}` : ''}` : ''],
      ['انتشار', d.published_at ? when(d.published_at) : ''],
      d.attendee_access ? ['شرکت‌کنندگان', 'برای حاضران تأییدشدهٔ همین رویداد رایگان است'] : null,
      /* گواهی پایان محتوا: فقط آنچه سرور می‌گوید؛ هیچ حالت خودکاری وجود ندارد و خرید، حضور به شمار نمی‌آید. */
      ['گواهی پایان محتوا', rCertificate(d)]
    ].filter(item => item && item[1]);
    const status = d.status !== 'published' ? `<span class="reg-state ${d.status === 'sales_paused' ? 'warn' : 'mute'}">${esc(d.status === 'sales_paused' ? 'فروش متوقف' : d.status === 'archived' ? 'بایگانی' : d.status === 'ready' ? 'آمادهٔ انتشار (فقط کادر)' : 'پیش‌نویس (فقط کادر)')}</span>` : (v.access && v.access.allowed ? `<span class="reg-state ok">دسترسی دارید</span>` : d.free ? `<span class="reg-state ok">دسترسی رایگان</span>` : `<span class="reg-state mute">قابل خرید</span>`);
    const cover = d.cover_url && /^(?:\/api\/public\/media\/[0-9a-f-]{36}|https:\/\/[^\s"']+)$/i.test(String(d.cover_url)) ? `<img class="ei-rec-cover" src="${esc(d.cover_url)}" alt="" loading="lazy" decoding="async"/>` : '';
    const faq = Array.isArray(d.faq) && d.faq.length ? `<div class="ei-rec-block"><b>پرسش‌های متداول</b>${d.faq.map(item => `<details class="ei-rec-faq"><summary>${esc(item.q)}</summary><p>${breaks(item.a)}</p></details>`).join('')}</div>` : '';
    const inner = `${cover}<h3 class="ei-rec-title">${esc(d.title)}</h3>${d.summary ? `<p class="ei-rec-summary">${breaks(d.summary)}</p>` : ''}
      ${message('recording')}<div class="ei-rec-cta" data-rec-cta="${esc(v.cta.kind)}">${rCta(false)}</div>${rOrderPanel()}
      <dl class="ei-rec-facts">${facts.map(([k, val]) => `<div><dt>${esc(k)}</dt><dd>${esc(val)}</dd></div>`).join('')}</dl>
      ${rBlock('دستاوردها', d.outcomes)}${rBlock('مخاطب', d.audience)}${rBlock('شرایط دسترسی', d.access_terms)}${rBlock('سیاست بازپرداخت', d.refund_policy)}
      <h3 class="ei-rec-sub" id="recording-sessions">جلسات</h3>${sessions.length ? `<ol class="ei-rec-sessions">${sessions.map(rSession).join('')}</ol>` : emptyBox('جلسه‌ای منتشر نشده است.')}${faq}`;
    box.innerHTML = section('recording', 'محتوای ضبط‌شده', inner, status);
    wireEmbeds(box);
    fill(boxes.aside, `<p class="event-price">${esc(rMoney(d.price))}</p><div class="event-register-action">${rCta(true)}</div>`);
    fill(boxes.toolbar, rCta(true));
    const bar = doc.getElementById('ctabar');
    if (bar && boxes.toolbar) bar.hidden = !boxes.toolbar.innerHTML.trim();
  }
  async function loadRecording() {
    if (!S.event || !rContainers().section) return;
    R.loading = true; R.error = ''; R.status = 0;
    renderRecording();
    try {
      R.data = await api(`/api/public/events/${encodeURIComponent(String(S.event.id))}/recording`);
      R.data = R.data && R.data.recording ? R.data.recording : null;
      if (!R.data) R.status = 404;
    } catch (error) {
      R.status = error && error.status ? error.status : 0;
      if (R.status !== 404) R.error = describe(error);
    }
    R.loading = false;
    renderRecording();
    /* The Q&A form/list reference the loaded sessions (optional per-session questions); refresh them once. */
    if (S.data) renderQa(containers().qa);
    const target = (root.location.hash || '').replace(/^#/, '');
    if (R_JUMP_TARGETS.indexOf(target) >= 0) rScroll(target);
  }
  /* In-page jumps never fire `hashchange`: the shared shell (ui.js `uiHash`) reacts to it on `?id=` pages by opening the
     legacy demo event sheet over the real page. replaceState + scrollIntoView keeps the URL shareable without that. */
  const R_JUMP_TARGETS = ['recording', 'recording-order', 'recording-sessions'];
  function rScroll(target) {
    const node = doc.getElementById(target);
    if (node && typeof node.scrollIntoView === 'function') { try { node.scrollIntoView({ block: 'start' }); } catch (_) { /* بدون اسکرول */ } }
  }
  function rJump(target) {
    try { if (root.history && typeof root.history.replaceState === 'function') root.history.replaceState(root.history.state, '', '#' + target); } catch (_) { /* بدون تغییر نشانی */ }
    rScroll(target);
  }
  async function rClaim() {
    if (!R.data || R.busy) return;
    R.busy = 'claim'; R.msg = null; renderRecording();
    try {
      await api(`/api/account/recordings/${encodeURIComponent(R.data.id)}/claim`, { method: 'POST', body: {} });
      R.msg = { kind: 'ok', text: 'دسترسی رایگان روی حساب شما ثبت شد.' }; S.msg.recording = R.msg;
    } catch (error) { S.msg.recording = { kind: 'warn', text: rDescribe(error) }; }
    R.busy = '';
    await loadRecording();
  }
  /* ساخت سفارش از صفحهٔ رویداد (POST /orders فاز ۹) حذف شد: سرور آن را با 410 use_purchase_form بسته و خرید فقط از فرم خرید آغاز می‌شود. */
  async function rCancel() {
    const cta = R.data && R.data.viewer.cta; if (!cta || !cta.order || R.busy) return;
    if (typeof root.confirm === 'function' && !root.confirm('سفارش لغو شود؟ اگر مبلغی واریز کرده‌اید، لغو نکنید و با برگزارکننده تماس بگیرید.')) return;
    R.busy = 'cancel'; renderRecording();
    try { await api(`/api/account/recording-orders/${encodeURIComponent(cta.order.id)}/cancel`, { method: 'POST', body: {} }); S.msg.recording = { kind: 'ok', text: 'سفارش لغو شد.' }; }
    catch (error) { S.msg.recording = { kind: 'warn', text: rDescribe(error) }; }
    R.busy = '';
    await loadRecording();
  }
  /* ارسال رسید از صفحهٔ رویداد (مسیر موازی فاز ۹) حذف شد؛ رسید فقط در فرم خرید (form.html) و با بازبینی اینباکس ثبت می‌شود. */
  function rBind(page) {
    if (page.__noraRecordingBound) return;
    page.__noraRecordingBound = true;
    const handler = event => {
      const jump = event.target && event.target.closest ? event.target.closest('a[data-rec-view],a[data-rec-continue],a[data-rec-buy-jump]') : null;
      if (jump) {
        const hash = (jump.getAttribute('href') || '').replace(/^#/, '');
        if (R_JUMP_TARGETS.indexOf(hash) >= 0) { event.preventDefault(); rJump(hash); }
        return;
      }
      const target = event.target && event.target.closest ? event.target.closest('[data-rec-retry],[data-rec-claim],[data-rec-cancel],[data-rec-refresh]') : null;
      if (!target) return;
      event.preventDefault();
      if (target.hasAttribute('data-rec-retry') || target.hasAttribute('data-rec-refresh')) { loadRecording(); return; }
      if (target.hasAttribute('data-rec-claim')) { rClaim(); return; }
      if (target.hasAttribute('data-rec-cancel')) { rCancel(); }
    };
    doc.addEventListener('click', handler);
  }

  function render() {
    const boxes = containers();
    renderResources(boxes.resources);
    renderQa(boxes.qa);
    renderReviews(boxes.reviews);
    if (R.data || R.loading || R.error || R.status) renderRecording();
  }

  async function load() {
    if (!S.event) return;
    S.loading = true; S.error = '';
    render();
    try {
      S.data = await api(`/api/public/events/${encodeURIComponent(String(S.event.id))}/interaction`);
    } catch (error) {
      S.error = error && error.status === 404 ? 'بخش‌های تعاملی این رویداد در دسترس نیست.' : describe(error);
    }
    S.loading = false;
    render();
    const target = (root.location.hash || '').replace(/^#/, '');
    if (['resources', 'qa', 'reviews'].includes(target)) {
      const node = doc.getElementById(target);
      if (node && typeof node.scrollIntoView === 'function') { try { node.scrollIntoView({ block: 'start' }); } catch (_) { /* بدون اسکرول */ } }
    }
  }

  async function submitQuestion(form) {
    const field = form.querySelector('#eiQuestionBody');
    const body = field ? String(field.value || '').trim() : '';
    const select = form.querySelector('[data-ei-question-session]');
    const sessionId = select ? String(select.value || '') : '';
    S.questionSession = sessionId;
    if (body.length < 5) { S.msg.question = { kind: 'warn', text: ERRORS.text_too_short }; render(); return; }
    S.busy.question = true; S.msg.question = null; render();
    try {
      const payload = sessionId ? { body, session_id: sessionId } : { body };
      await api(`/api/account/events/${encodeURIComponent(String(S.event.id))}/questions`, { method: 'POST', body: payload });
      S.questionSession = '';
      S.msg.question = { kind: 'ok', text: 'پرسش شما ثبت شد و پس از بررسی برگزارکننده منتشر می‌شود.' };
      S.busy.question = false;
      await load();
      return;
    } catch (error) {
      S.msg.question = { kind: 'warn', text: describe(error) };
      if (error && error.code === 'duplicate_question') toast(ERRORS.duplicate_question);
    }
    S.busy.question = false; render();
  }

  async function submitReview(form) {
    const field = form.querySelector('#eiReviewBody');
    const body = field ? String(field.value || '').trim() : '';
    if (body.length < 10) { S.msg.review = { kind: 'warn', text: 'دیدگاه باید دست‌کم ۱۰ نویسه باشد.' }; render(); return; }
    S.busy.review = true; S.msg.review = null; render();
    const base = `/api/account/events/${encodeURIComponent(String(S.event.id))}/reviews`;
    try {
      if (S.editReview && S.data.reviews.mine) await api(`${base}/${encodeURIComponent(S.data.reviews.mine.id)}`, { method: 'PUT', body: { body } });
      else await api(base, { method: 'POST', body: { body } });
      S.msg.review = { kind: 'ok', text: 'دیدگاه شما ثبت شد و پس از تأیید برگزارکننده منتشر می‌شود.' };
      S.editReview = false; S.busy.review = false;
      await load();
      return;
    } catch (error) {
      S.msg.review = { kind: 'warn', text: describe(error) };
    }
    S.busy.review = false; render();
  }

  async function withdrawReview() {
    const mine = S.data && S.data.reviews.mine;
    if (!mine) return;
    if (typeof root.confirm === 'function' && !root.confirm('دیدگاه شما پس گرفته می‌شود و دیگر نمایش داده نمی‌شود. ادامه می‌دهید؟')) return;
    S.busy.review = true; render();
    try {
      await api(`/api/account/events/${encodeURIComponent(String(S.event.id))}/reviews/${encodeURIComponent(mine.id)}/withdraw`, { method: 'POST', body: {} });
      S.msg.review = { kind: 'ok', text: 'دیدگاه شما پس گرفته شد.' };
    } catch (error) {
      S.msg.review = { kind: 'warn', text: describe(error) };
    }
    S.busy.review = false;
    await load();
  }

  async function report(kind, id) {
    let reason = '';
    if (typeof root.prompt === 'function') {
      const answer = root.prompt('دلیل گزارش (اختیاری، حداکثر ۳۰۰ نویسه):', '');
      if (answer === null) return;
      reason = String(answer).slice(0, 300);
    }
    const path = `/api/account/events/${encodeURIComponent(String(S.event.id))}/${kind === 'review' ? 'reviews' : 'questions'}/${encodeURIComponent(id)}/report`;
    try {
      await api(path, { method: 'POST', body: { reason } });
      toast('گزارش شما ثبت شد و بررسی می‌شود.');
    } catch (error) {
      toast(describe(error));
    }
    await load();
  }

  function bind(page) {
    if (page.__noraInteractionBound) return;
    page.__noraInteractionBound = true;
    page.addEventListener('click', event => {
      const target = event.target && event.target.closest ? event.target.closest('[data-ei-retry],[data-ei-report],[data-ei-edit-review],[data-ei-withdraw-review],[data-ei-cancel-edit]') : null;
      if (!target) return;
      if (target.hasAttribute('data-ei-retry')) { load(); return; }
      if (target.hasAttribute('data-ei-report')) { report(target.getAttribute('data-ei-report'), target.getAttribute('data-id')); return; }
      if (target.hasAttribute('data-ei-edit-review')) { S.editReview = true; S.msg.review = null; render(); return; }
      if (target.hasAttribute('data-ei-cancel-edit')) { S.editReview = false; render(); return; }
      if (target.hasAttribute('data-ei-withdraw-review')) { withdrawReview(); }
    });
    page.addEventListener('submit', event => {
      const form = event.target && event.target.closest ? event.target.closest('form[data-ei-form]') : null;
      if (!form) return;
      event.preventDefault();
      if (form.getAttribute('data-ei-form') === 'question') submitQuestion(form);
      else submitReview(form);
    });
  }

  function mount(event, page) {
    if (!event || !page || !SOURCE_READY()) return false;
    S.event = event; S.page = page; S.data = null; S.error = ''; S.msg = {}; S.busy = {}; S.editReview = false;
    bind(page);
    R.data = null; R.loading = false; R.error = ''; R.status = 0; R.busy = ''; R.note = '';
    load().catch(() => { /* خطاها داخل load مدیریت می‌شوند */ });
    if (rContainers().section) { rBind(page); loadRecording().catch(() => { /* خطاها داخل loadRecording مدیریت می‌شوند */ }); }
    return true;
  }

  root.NORA_EVENT_INTERACTION = { mount, reload: load, reloadRecording: loadRecording, state: S, recording: R, ERRORS, ACCESS, REASON };
})(typeof window === 'undefined' ? globalThis : window);
