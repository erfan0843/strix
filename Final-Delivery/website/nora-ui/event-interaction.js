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
    'application/zip': 'ZIP', 'audio/mpeg': 'MP3', 'text/plain': 'متن'
  };
  const ACCESS = { public: 'عمومی', registered: 'ویژهٔ ثبت‌نام‌شدگان', attended: 'ویژهٔ شرکت‌کنندگان', staff: 'ویژهٔ برگزارکنندگان' };
  const REASON = {
    login_required: 'برای دریافت وارد حساب شوید',
    registration_required: 'نیازمند ثبت‌نام تأییدشده',
    attendance_required: 'ویژهٔ شرکت‌کنندگان با حضور تأییدشده',
    staff_only: 'فقط برای برگزارکنندگان',
    not_published: 'هنوز منتشر نشده',
    removed: 'برداشته شده'
  };
  const ERRORS = {
    duplicate_question: 'همین پرسش را پیش‌تر ثبت کرده‌اید.',
    too_many_open_questions: 'چند پرسش بی‌پاسخ دارید؛ لطفاً تا پاسخ برگزارکننده صبر کنید.',
    qa_closed: 'پرسش‌وپاسخ این رویداد بسته است.',
    text_too_short: 'متن خیلی کوتاه است.',
    text_too_long: 'متن از حد مجاز بلندتر است.',
    text_required: 'متن را بنویسید.',
    review_not_eligible: 'ثبت دیدگاه فقط برای شرکت‌کنندگان با حضور تأییدشده ممکن است.',
    review_exists: 'برای این رویداد قبلاً دیدگاه ثبت کرده‌اید.',
    review_locked: 'این دیدگاه دیگر قابل ویرایش نیست.',
    authentication_required: 'نشست شما معتبر نیست؛ دوباره وارد شوید.',
    csrf_check_failed: 'نشست شما معتبر نیست؛ صفحه را نوسازی کنید.',
    rate_limited: 'تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید.',
    network: 'ارتباط با سرور برقرار نشد.'
  };
  const SOURCE_READY = () => root.NORA_PUBLIC_SOURCE === 'server';
  const S = { event: null, page: null, data: null, loading: false, error: '', busy: {}, msg: {}, editReview: false };

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
    const kind = row.kind === 'link' ? 'پیوند' : (FORMAT[row.content_type] || 'فایل');
    const meta = [kind, row.kind === 'file' ? size(row.size) : '', ACCESS[row.access] || '',
      row.publisher ? `ناشر: ${row.publisher}` : '', row.publish_at ? `انتشار: ${when(row.publish_at)}` : ''].filter(Boolean);
    let action;
    if (row.allowed && row.kind === 'file') {
      action = `<a class="btn sm" href="/api/public/events/${encodeURIComponent(S.event.id)}/resources/${encodeURIComponent(row.id)}/download" download data-ei-download>دریافت فایل</a>`;
    } else if (row.allowed && row.kind === 'link' && /^https?:\/\//i.test(String(row.link_url || ''))) {
      action = `<a class="btn sm" href="${esc(row.link_url)}" target="_blank" rel="noopener noreferrer">بازکردن پیوند</a>`;
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
  }

  /* ── پرسش‌وپاسخ ── */
  function questionRow(row) {
    const status = row.mine && row.status !== 'published'
      ? `<span class="tag ${row.status === 'hidden' ? 'stop' : ''}">${esc(row.status === 'hidden' ? 'پنهان‌شده' : 'در انتظار بررسی')}</span>` : '';
    const answer = row.answered
      ? `<div class="ei-answer"><b>${esc(row.answer_label || 'برگزارکننده')}${row.answer_official ? ' · پاسخ رسمی' : ''}</b><p>${breaks(row.answer)}</p><small>${esc(when(row.answered_at))}</small></div>`
      : `<small class="ei-wait">${esc(row.mine ? 'هنوز پاسخ داده نشده' : 'در انتظار پاسخ برگزارکننده')}</small>`;
    const report = !row.mine && S.data.viewer.signed_in && !S.data.viewer.staff
      ? (row.reported ? '<small class="ei-wait">گزارش شما ثبت شد</small>' : `<button type="button" class="ei-link" data-ei-report="question" data-id="${esc(row.id)}">گزارش محتوای نامناسب</button>`)
      : '';
    return `<li class="ei-question" data-question="${esc(row.id)}"><div class="ei-byline"><b>${esc(row.author)}</b>${row.mine ? '<span class="tag brand">شما</span>' : ''}${status}<small>${esc(when(row.created_at))}</small></div>
      <p>${breaks(row.body)}</p>${answer}${report ? `<div class="ei-actions">${report}</div>` : ''}</li>`;
  }
  function qaForm() {
    const viewer = S.data.viewer, ev = S.data.event;
    if (!ev.qa_open) return `<p class="registration-notice" role="status">${esc(ev.qa_closed_reason === 'cancelled' ? 'این رویداد لغو شده و پرسش تازه پذیرفته نمی‌شود.' : 'پرسش‌وپاسخ این رویداد بسته شده است؛ پرسش‌های پاسخ‌داده‌شده همچنان قابل مشاهده‌اند.')}</p>`;
    if (!viewer.signed_in) return `<div class="ei-login"><span>برای پرسیدن، وارد حساب شوید.</span><a class="btn sm" href="${esc(loginHref('qa'))}">ورود</a></div>`;
    const busy = !!S.busy.question;
    return `<form class="ei-form" data-ei-form="question" novalidate>
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
    const badge = row.verified_attendee ? '<span class="tag ok">شرکت‌کنندهٔ تأییدشده</span>' : '';
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
    if (!viewer.signed_in) return `<div class="ei-login"><span>دیدگاه‌ها فقط از شرکت‌کنندگان با حضور تأییدشده پذیرفته می‌شود.</span><a class="btn sm quiet" href="${esc(loginHref('reviews'))}">ورود</a></div>`;
    if (!r.eligible) {
      const p = viewer.participation;
      return `<p class="registration-notice" role="status">${esc(p.registered ? 'ثبت‌نام شما ثبت شده است؛ پس از تأیید حضور در رویداد می‌توانید دیدگاه بنویسید.' : 'ثبت دیدگاه فقط برای شرکت‌کنندگانی که حضورشان تأیید شده ممکن است.')}</p>`;
    }
    return `<form class="ei-form" data-ei-form="review" novalidate>
      <label class="cap" for="eiReviewBody">${esc(S.editReview ? 'ویرایش دیدگاه (پس از ویرایش دوباره بررسی می‌شود)' : 'دیدگاه شما دربارهٔ این رویداد (بدون امتیاز؛ فقط متن)')}</label>
      <textarea id="eiReviewBody" class="input" rows="3" maxlength="1500" required placeholder="تجربهٔ خود از این رویداد را بنویسید…" ${busy ? 'disabled' : ''}>${esc(S.editReview && mine ? mine.body : '')}</textarea>
      <div class="ei-form-row"><small class="cap">پس از تأیید برگزارکننده با نشان «شرکت‌کنندهٔ تأییدشده» منتشر می‌شود.</small>
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

  function render() {
    const boxes = containers();
    renderResources(boxes.resources);
    renderQa(boxes.qa);
    renderReviews(boxes.reviews);
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
    if (body.length < 5) { S.msg.question = { kind: 'warn', text: ERRORS.text_too_short }; render(); return; }
    S.busy.question = true; S.msg.question = null; render();
    try {
      await api(`/api/account/events/${encodeURIComponent(String(S.event.id))}/questions`, { method: 'POST', body: { body } });
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
    load().catch(() => { /* خطاها داخل load مدیریت می‌شوند */ });
    return true;
  }

  root.NORA_EVENT_INTERACTION = { mount, reload: load, state: S, ERRORS, ACCESS, REASON };
})(typeof window === 'undefined' ? globalThis : window);
