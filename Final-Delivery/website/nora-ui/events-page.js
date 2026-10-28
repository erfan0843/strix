/* صفحهٔ عمومی رویدادها.
   داده فقط از رکوردهای منتشرشدهٔ سرور (public-data.js) می‌آید؛ صافی نوع/شیوه،
   مرتب‌سازی و نمای تقویم همگی از همان رکوردها ساخته می‌شوند و هیچ عدد یا
   برنامهٔ نمایشی ندارند. طرح نوار صافی‌ها/ابزار/تقویم از نسخهٔ طراحی ۲۷ شهریور
   آورده شده و روی مدل دادهٔ سرور بازنویسی شده است. */
(function (root) {
  'use strict';
  const $ = selector => root.document.querySelector(selector);
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const cut = (value, length) => String(value || '').trim().slice(0, length);
  const fa = value => {
    try { return new Intl.NumberFormat('fa-IR').format(Number(value) || 0); }
    catch (_) { return String(Number(value) || 0); }
  };
  const safeUrl = value => {
    const url = String(value || '').trim();
    if (/^https?:\/\//i.test(url) || /^data:image\/(?:png|jpeg|webp|gif);base64,/i.test(url)) return url;
    if (/^(?:\.\.?\/|\/)?[A-Za-z0-9_~%-][A-Za-z0-9_./~%-]*$/.test(url)
        && !/(?:^|\/)\.\.(?:\/|$)/.test(url)) return url;
    return '';
  };

  /* ── تقویم جلالی (همان الگوریتم ui.js؛ این‌جا مستقل تا بستهٔ مشترک بزرگ نشود) ── */
  const jdiv = (a, b) => Math.trunc(a / b), jmod = (a, b) => a - Math.trunc(a / b) * b;
  const BREAKS = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
  function jalCal(jy) {
    const gy = jy + 621;
    let leapJ = -14, jp = BREAKS[0], jm = 0, jump = 0;
    for (let i = 1; i < BREAKS.length; i++) {
      jm = BREAKS[i]; jump = jm - jp;
      if (jy < jm) break;
      leapJ += jdiv(jump, 33) * 8 + jdiv(jmod(jump, 33), 4); jp = jm;
    }
    let n = jy - jp, L = leapJ + jdiv(n, 33) * 8 + jdiv(jmod(n, 33) + 3, 4);
    if (jmod(jump, 33) === 4 && jump - n === 4) L++;
    const leapG = jdiv(gy, 4) - jdiv((jdiv(gy, 100) + 1) * 3, 4) - 150;
    const march = 20 + L - leapG;
    if (jump - n < 6) n = n - jump + jdiv(jump + 4, 33) * 33;
    let leap = jmod(jmod(n + 1, 33) - 1, 4);
    if (leap === -1) leap = 4;
    return { leap, march, gy };
  }
  const g2d = (gy, gm, gd) => {
    let d = jdiv((gy + jdiv(gm - 8, 6) + 100100) * 1461, 4) + jdiv(153 * jmod(gm + 9, 12) + 2, 5) + gd - 34840408;
    d = d - jdiv(jdiv(gy + 100100 + jdiv(gm - 8, 6), 100) * 3, 4) + 752; return d;
  };
  const d2g = jdn => {
    let j = 4 * jdn + 139361631; j = j + jdiv(jdiv(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
    const i = jdiv(jmod(j, 1461), 4) * 5 + 308, gd = jdiv(jmod(i, 153), 5) + 1, gm = jmod(jdiv(i, 153), 12) + 1;
    return { gy: jdiv(j, 1461) - 100100 + jdiv(8 - gm, 6), gm, gd };
  };
  const j2d = (jy, jm, jd) => { const r = jalCal(jy); return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - jdiv(jm, 7) * (jm - 7) + jd - 1; };
  const d2j = jdn => {
    const g = d2g(jdn), gy = g.gy;
    let jy = gy - 621;
    const r = jalCal(jy), jdn1f = g2d(gy, 3, r.march);
    let k = jdn - jdn1f, jm, jd;
    if (k >= 0) { if (k <= 185) { jm = 1 + jdiv(k, 31); jd = jmod(k, 31) + 1; return { jy, jm, jd }; } k -= 186; }
    else { jy--; k += 179; if (r.leap === 1) k++; }
    jm = 7 + jdiv(k, 30); jd = jmod(k, 30) + 1; return { jy, jm, jd };
  };
  const isLeapJ = jy => jalCal(jy).leap === 0;
  const daysInJ = (jy, jm) => jm === 12 ? (isLeapJ(jy) ? 30 : 29) : (jm <= 6 ? 31 : 30);
  const MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
  /* شنبه نخستین ستون است */
  const WD_SHORT = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];
  const WD_NAME = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه'];
  const weekdayIndex = (jy, jm, jd) => {
    const g = d2g(j2d(jy, jm, jd));
    return (new Date(Date.UTC(g.gy, g.gm - 1, g.gd)).getUTCDay() + 1) % 7;
  };
  const todayJ = () => { const g = new Date(); return d2j(g2d(g.getFullYear(), g.getMonth() + 1, g.getDate())); };
  const latinDigits = value => String(value || '')
    .replace(/[۰-۹]/g, ch => String(ch.charCodeAt(0) - 1776))
    .replace(/[٠-٩]/g, ch => String(ch.charCodeAt(0) - 1632));
  /* «۱۴۰۵/۰۷/۱۰» یا «1405-7-10» → {jy,jm,jd}؛ هر شکل دیگر → null (رویداد بی‌تاریخ ماشینی) */
  function parseJalali(value) {
    const text = latinDigits(value).replace(/[-.]/g, '/').trim();
    const match = text.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})(?:\D.*)?$/);
    if (!match) return null;
    const jy = +match[1], jm = +match[2], jd = +match[3];
    if (jy < 1300 || jy > 1500 || jm < 1 || jm > 12 || jd < 1 || jd > daysInJ(jy, jm)) return null;
    return { jy, jm, jd };
  }
  const dateOf = event => parseJalali(event.on) || parseJalali(event.when);
  const dateKey = date => date ? date.jy * 10000 + date.jm * 100 + date.jd : 0;
  const monthKey = date => `${date.jy}-${date.jm}`;
  const monthLabel = (jy, jm) => `${MONTHS[jm - 1]} ${fa(jy).replace(/٬/g, '')}`;

  /* ── وضعیت صفحه ── */
  const state = { status: 'all', kind: '', mode: '', access: '', sort: 'near', view: 'list', month: '', day: 0, query: '' };
  /* فاز ۹: «ضبط‌شده» یعنی محصول منتشرشدهٔ سرور برای همین رویداد؛ برگزارشده بدون محصول منتشرشده، قابل خرید نیست */
  const recorded = event => !!(event.recording && event.recording.sellable);
  const recordedAccess = event => recorded(event) ? (event.recording.free ? 'رایگان' : 'قابل خرید') : '';
  let records = [];
  const params = new URLSearchParams(root.location.search);

  function registrationForm(event) {
    const linked = (Array.isArray(event.forms) ? event.forms : []).find(item => item && item.id
      && (!item.need || item.need === 'reg'));
    if (linked) return String(linked.id);
    if (root.NORA_PUBLIC_SOURCE === 'server') return '';
    const ui = root.NORA_UI || {};
    const local = typeof ui.formsFor === 'function' ? ui.formsFor(String(event.id)) : [];
    const form = (Array.isArray(local) ? local : []).find(item => item && item.id
      && (item.need || 'reg') === 'reg' && item.status !== 'draft'
      && item.serverDraft !== true && item.eventVisible !== false);
    const id = (form && form.id) || event.regForm || '';
    return id ? String(id) : '';
  }

  function person(event) {
    const list = root.NORA_PUBLIC && Array.isArray(root.NORA_PUBLIC.people)
      ? root.NORA_PUBLIC.people : [];
    return list.find(item => String(item.id) === String(event.tchr || '')) || null;
  }

  /* شیوهٔ برگزاری: از فیلد mode، وگرنه از مکان (پیوند یا «آنلاین» = آنلاین؛ مکان متنی = حضوری) */
  function modeOf(event) {
    const mode = String(event.mode || '').trim();
    if (/آنلاین|مجازی|online/i.test(mode)) return /حضوری/.test(mode) ? 'حضوری و آنلاین' : 'آنلاین';
    if (/حضوری|physical/i.test(mode)) return 'حضوری';
    const place = String(event.place || '').trim();
    if (!place) return '';
    if (/^https?:\/\//i.test(place) || /^آنلاین$/.test(place) || /^(?:online|مجازی)$/i.test(place)) return 'آنلاین';
    return 'حضوری';
  }

  function statusMatches(event) {
    if (state.status === 'upcoming' && event.past) return false;
    if (state.status === 'past' && !event.past) return false;
    if (state.status === 'recorded' && !recorded(event)) return false;
    return true;
  }
  function facetMatches(event, ignore) {
    if (ignore !== 'kind' && state.kind && String(event.kind || '') !== state.kind) return false;
    if (ignore !== 'mode' && state.mode && modeOf(event) !== state.mode) return false;
    if (ignore !== 'access' && state.access && recordedAccess(event) !== state.access) return false;
    return true;
  }
  function queryMatches(event) {
    if (!state.query) return true;
    const teacher = person(event);
    const haystack = [event.t, event.kind, event.d, event.when, event.time, event.place, modeOf(event),
      ...(Array.isArray(event.tags) ? event.tags : []), teacher && teacher.n, teacher && teacher.r, recorded(event) ? event.recording.title : '']
      .filter(Boolean).join(' ').toLocaleLowerCase();
    return haystack.includes(state.query.toLocaleLowerCase());
  }
  const eventMatches = event => statusMatches(event) && facetMatches(event) && queryMatches(event);

  /* ترتیب: نزدیک‌ترین = پیش‌روها صعودی به تاریخ، سپس برگزارشده‌ها نزولی؛ بی‌تاریخ‌ها در انتهای گروه خود با ترتیب انتشار */
  function sorted(list) {
    const indexed = list.map((event, index) => ({ event, index, key: dateKey(dateOf(event)) }));
    const byDate = (dir) => (a, b) => {
      if (a.key && b.key && a.key !== b.key) return (a.key - b.key) * dir;
      if (!!a.key !== !!b.key) return a.key ? -1 : 1;
      return a.index - b.index;
    };
    if (state.sort === 'cheap' || state.sort === 'dear') {
      const dir = state.sort === 'cheap' ? 1 : -1;
      indexed.sort((a, b) => ((+a.event.price || 0) - (+b.event.price || 0)) * dir || byDate(1)(a, b));
    } else if (state.sort === 'title') {
      indexed.sort((a, b) => String(a.event.t).localeCompare(String(b.event.t), 'fa') || a.index - b.index);
    } else {
      const upcoming = indexed.filter(item => !item.event.past).sort(byDate(1));
      const past = indexed.filter(item => item.event.past).sort(byDate(-1));
      return upcoming.concat(past).map(item => item.event);
    }
    return indexed.map(item => item.event);
  }

  function card(event) {
    const formId = registrationForm(event);
    const profile = person(event);
    const cover = safeUrl(event.posterUp || event.poster);
    const when = [event.when, event.time].filter(Boolean).join(' · ');
    const mode = modeOf(event);
    /* بازآرایی ۱۴۰۵/۰۸/۰۳: نوع برنامه فقط یک بار روی قاب پوستر (cover-kind) می‌آید و تاریخ فقط در ردیف مشخصات زیر عنوان؛ هیچ‌کدام تکرار نمی‌شوند */
    const tags = (Array.isArray(event.tags) ? event.tags : []).filter(tag => tag && tag !== event.kind).slice(0, 4);
    const detailHref = `event.html?id=${encodeURIComponent(event.id)}`;
    const coverHtml = cover ? `<img src="${esc(cover)}" alt="" loading="lazy" decoding="async"/>` : '';
    /* وضعیت ثبت‌نام فقط از سرور؛ دکمهٔ ثبت‌نام تنها در حالت «باز» به فرم می‌رود و در بقیهٔ حالت‌ها وضعیت صادقانه نوشته می‌شود */
    const CD = window.NORA_COUNTDOWN;
    const reg = event.registration && typeof event.registration === 'object' ? event.registration : null;
    const regOpen = !!(reg && reg.state === 'open' && reg.lifecycle !== 'cancelled' && reg.lifecycle !== 'postponed');
    const stateText = CD && reg ? CD.stateLabel(reg) : '';
    const stateTone = CD && reg ? CD.stateTone(reg) : 'mute';
    const target = CD && !event.past ? CD.eventTarget(event) : null;
    const timerHtml = target ? CD.markup(target, { compact: true }) : '';
    const formButton = event.past
      ? ''
      : regOpen && formId
        ? `<a class="btn primary" href="form.html?fid=${encodeURIComponent(formId)}&kind=reg">ثبت‌نام</a>`
        : reg && reg.state && reg.state !== 'none'
          ? `<span class="event-register-missing reg-state ${esc(stateTone)}">${esc(stateText || 'ثبت‌نام در دسترس نیست')}</span>`
          : formId && !reg
            ? `<a class="btn primary" href="form.html?fid=${encodeURIComponent(formId)}&kind=reg">ثبت‌نام</a>`
            : `<span class="event-register-missing">فرم ثبت‌نام منتشر نشده است</span>`;
    const coverState = event.past ? 'برگزارشده' : (reg && reg.lifecycle === 'cancelled') ? 'لغو شد' : (reg && reg.lifecycle === 'postponed') ? 'به تعویق افتاد' : '';
    const rec = recorded(event) ? event.recording : null;
    const recMeta = rec ? [rec.sessionCount ? `${fa(rec.sessionCount)} جلسه` : '', rec.totalMinutes ? `${fa(rec.totalMinutes)} دقیقه` : '', rec.free ? 'دسترسی رایگان' : `${fa(rec.price)} ریال`].filter(Boolean).join(' · ') : '';
    const recButton = rec ? `<a class="btn ${event.past ? 'primary' : 'quiet'}" href="${detailHref}#recording" data-event-recording="${esc(event.id)}">${rec.free ? 'محتوای ضبط‌شده (رایگان)' : 'خرید محتوای ضبط‌شده'}</a>` : '';
    return `<article class="event-list-card card paper" data-event-id="${esc(event.id)}"${rec ? ' data-event-recorded="true"' : ''}>
      <a class="event-list-cover${cover ? ' has-poster' : ''}" href="${detailHref}" aria-label="جزئیات ${esc(event.t)}">
        ${coverHtml}<span class="cover-shade"></span>
        ${event.kind ? `<span class="cover-kind">${esc(event.kind)}</span>` : ''}
        ${coverState ? `<span class="cover-state">${esc(coverState)}${rec ? ' · ضبط‌شده' : ''}</span>` : rec ? '<span class="cover-state">ضبط‌شده</span>' : ''}
      </a>
      <div class="event-list-body">
        ${tags.length ? `<div class="event-list-tags">${tags.slice(0, 4).map((tag, index) => `<span class="tag${index === 0 ? ' brand' : ''}">${esc(tag)}</span>`).join('')}</div>` : ''}
        ${!event.past && stateText ? `<div class="event-list-state"><span class="reg-state ${esc(stateTone)}">${esc(stateText)}</span>${timerHtml}</div>` : ''}
        <a class="event-list-title" href="${detailHref}">${esc(event.t)}</a>
        ${event.d ? `<p class="event-list-description">${esc(cut(event.d, 700))}</p>` : ''}
        <div class="event-list-meta">
          ${when ? `<span><svg class="i" aria-hidden="true"><use href="#i-clock"/></svg><span>${esc(when)}</span></span>` : ''}
          ${event.place ? `<span><svg class="i" aria-hidden="true"><use href="#i-pin"/></svg><span>${esc(event.place)}</span></span>` : ''}
          ${mode ? `<span><svg class="i" aria-hidden="true"><use href="#i-grid"/></svg><span>${esc(mode)}</span></span>` : ''}
          ${event.cap ? `<span><svg class="i" aria-hidden="true"><use href="#i-user"/></svg><span>ظرفیت ${fa(event.cap)} نفر</span></span>` : ''}
          ${!event.past ? `<span><svg class="i" aria-hidden="true"><use href="#i-calendar"/></svg><span>${event.price ? `${fa(event.price)} ریال` : 'رایگان'}</span></span>` : ''}
          ${event.past && Array.isArray(event.media) && event.media.length ? `<span><svg class="i" aria-hidden="true"><use href="#i-archive"/></svg><span>${fa(event.media.length)} رسانهٔ منتشرشده</span></span>` : ''}
          ${rec ? `<span data-event-recording-meta><svg class="i" aria-hidden="true"><use href="#i-play"/></svg><span>${esc(['ضبط‌شده', recMeta].filter(Boolean).join(' · '))}</span></span>` : ''}
        </div>
        ${profile ? `<a class="event-list-teacher" href="person.html?id=${encodeURIComponent(profile.id)}"><svg class="i" aria-hidden="true"><use href="#i-graduation"/></svg>${esc(profile.n)}</a>` : ''}
        <div class="event-list-actions"><a class="btn quiet" href="${detailHref}">جزئیات کامل</a>${formButton}${recButton}</div>
      </div>
    </article>`;
  }

  /* ── صافی‌های نوع و شیوه: فقط مقادیری که واقعاً در رکوردها هست، با شمار همان رکوردها ── */
  function chipRow(label, attr, items, current) {
    if (!items.length) return '';
    return `<div class="event-facet-row" role="group" aria-label="${esc(label)}"><span class="event-facet-label">${esc(label)}</span><div class="event-facet-chips">${
      items.map(item => `<button type="button" class="chip${current === item.k ? ' on' : ''}" data-event-${attr}="${esc(item.k)}" aria-pressed="${current === item.k ? 'true' : 'false'}">${esc(item.k)} <small>${fa(item.c)}</small></button>`).join('')
    }</div></div>`;
  }
  function renderFacets() {
    const host = $('#eventFacets');
    if (!host) return;
    const base = records.filter(event => statusMatches(event) && queryMatches(event));
    const count = (list, pick) => {
      const map = new Map();
      list.forEach(event => { const key = pick(event); if (key) map.set(key, (map.get(key) || 0) + 1); });
      return [...map].map(([k, c]) => ({ k, c })).sort((a, b) => b.c - a.c || a.k.localeCompare(b.k, 'fa'));
    };
    const kinds = count(base.filter(event => facetMatches(event, 'kind')), event => String(event.kind || '').trim());
    const modes = count(base.filter(event => facetMatches(event, 'mode')), modeOf);
    if (state.kind && !kinds.some(item => item.k === state.kind)) kinds.push({ k: state.kind, c: 0 });
    if (state.mode && !modes.some(item => item.k === state.mode)) modes.push({ k: state.mode, c: 0 });
    const access = state.status === 'recorded' ? count(base.filter(event => facetMatches(event, 'access')), recordedAccess) : [];
    if (state.access && !access.some(item => item.k === state.access)) access.push({ k: state.access, c: 0 });
    const html = chipRow('نوع برنامه', 'kind', kinds.length > 1 || state.kind ? kinds : [], state.kind)
      + chipRow('شیوهٔ برگزاری', 'mode', modes.length > 1 || state.mode ? modes : [], state.mode)
      + chipRow('دسترسی محتوای ضبط‌شده', 'access', access.length > 1 || state.access ? access : [], state.access);
    host.innerHTML = html;
    host.hidden = !html;
    const reset = $('#eventFacetReset');
    if (reset) reset.hidden = !(state.kind || state.mode || state.access);
  }

  /* ── تقویم ماهانه از تاریخ‌های واقعی ── */
  function datedEvents() {
    return records.filter(eventMatches).map(event => ({ event, date: dateOf(event) })).filter(item => item.date);
  }
  function renderCalendar() {
    const monthsHost = $('#eventMonths'), gridHost = $('#eventCalendarGrid'), dayHost = $('#eventDayList');
    const dayTitle = $('#eventDayTitle'), dayCount = $('#eventDayCount'), note = $('#eventCalendarNote');
    if (!monthsHost || !gridHost || !dayHost) return;
    const dated = datedEvents();
    const undated = records.filter(eventMatches).length - dated.length;
    const months = new Map();
    dated.forEach(item => {
      const key = monthKey(item.date);
      if (!months.has(key)) months.set(key, { jy: item.date.jy, jm: item.date.jm, items: [] });
      months.get(key).items.push(item);
    });
    const ordered = [...months.values()].sort((a, b) => a.jy - b.jy || a.jm - b.jm);
    if (!ordered.length) {
      monthsHost.innerHTML = '';
      gridHost.innerHTML = '';
      dayHost.innerHTML = '';
      if (dayTitle) dayTitle.textContent = '';
      if (dayCount) dayCount.textContent = '';
      if (note) note.textContent = records.length
        ? 'برای رویدادهای منتشرشده تاریخ ماشین‌خوان ثبت نشده است؛ فهرست را ببینید.'
        : 'هنوز رویدادی منتشر نشده است.';
      return;
    }
    const today = todayJ();
    if (!state.month || !months.has(state.month)) {
      const current = ordered.find(month => month.jy > today.jy || (month.jy === today.jy && month.jm >= today.jm)) || ordered[ordered.length - 1];
      state.month = monthKey(current);
      state.day = 0;
    }
    const month = months.get(state.month);
    monthsHost.innerHTML = ordered.map(item => {
      const key = monthKey(item);
      const upcoming = item.items.filter(row => !row.event.past).length;
      return `<button type="button" class="chip${key === state.month ? ' on' : ''}${upcoming ? '' : ' was'}" data-event-month="${esc(key)}" role="tab" aria-selected="${key === state.month ? 'true' : 'false'}">${esc(monthLabel(item.jy, item.jm))} <small>${fa(item.items.length)}</small></button>`;
    }).join('');
    const days = daysInJ(month.jy, month.jm), start = weekdayIndex(month.jy, month.jm, 1);
    const byDay = new Map();
    month.items.forEach(item => { const list = byDay.get(item.date.jd) || []; list.push(item); byDay.set(item.date.jd, list); });
    if (!state.day || !byDay.has(state.day)) {
      const first = [...byDay.keys()].sort((a, b) => a - b);
      const todayDay = month.jy === today.jy && month.jm === today.jm ? today.jd : 0;
      state.day = first.find(day => day >= todayDay) || first[first.length - 1] || 0;
    }
    const cells = WD_SHORT.map(name => `<span class="event-cal-wd" aria-hidden="true">${name}</span>`);
    for (let i = 0; i < start; i++) cells.push('<span class="event-cal-cell blank"></span>');
    for (let day = 1; day <= days; day++) {
      const items = byDay.get(day) || [];
      const upcoming = items.filter(item => !item.event.past).length, past = items.length - upcoming;
      const isToday = month.jy === today.jy && month.jm === today.jm && day === today.jd;
      const label = `${fa(day)} ${monthLabel(month.jy, month.jm)}${upcoming ? `، ${fa(upcoming)} برنامهٔ پیش‌رو` : ''}${past ? `، ${fa(past)} برگزارشده` : ''}`;
      cells.push(`<button type="button" class="event-cal-cell${items.length ? ' has' : ''}${past && !upcoming ? ' was' : ''}${isToday ? ' today' : ''}${state.day === day ? ' sel' : ''}" data-event-day="${day}" aria-label="${esc(label)}" aria-pressed="${state.day === day ? 'true' : 'false'}"${items.length ? '' : ' disabled'}>${fa(day)}<span class="event-cal-dots">${upcoming ? '<i></i>' : ''}${past ? '<i class="p"></i>' : ''}</span></button>`);
    }
    gridHost.innerHTML = cells.join('');
    const selected = byDay.get(state.day) || [];
    if (dayTitle) dayTitle.textContent = state.day
      ? `${WD_NAME[weekdayIndex(month.jy, month.jm, state.day)]} ${fa(state.day)} ${monthLabel(month.jy, month.jm)}`
      : monthLabel(month.jy, month.jm);
    if (dayCount) dayCount.textContent = selected.length ? `${fa(selected.length)} برنامه در این روز` : 'برنامه‌ای در این روز نیست';
    dayHost.innerHTML = selected.map(item => card(item.event)).join('');
    if (root.NORA_COUNTDOWN) root.NORA_COUNTDOWN.mount(dayHost);
    if (note) note.textContent = undated > 0
      ? `${fa(undated)} رویداد بدون تاریخ ماشین‌خوان فقط در نمای فهرست دیده می‌شود.`
      : '';
  }

  function render() {
    const visible = sorted(records.filter(eventMatches));
    const list = $('#eventsList'), empty = $('#eventsEmpty'), count = $('#eventsCount');
    const calendar = $('#eventCalendar'), toolbar = $('#eventToolbar');
    const calendarMode = state.view === 'cal';
    list.innerHTML = calendarMode ? '' : visible.map(card).join('');
    list.hidden = calendarMode || !visible.length;
    if (root.NORA_COUNTDOWN) root.NORA_COUNTDOWN.mount(list);
    empty.hidden = calendarMode || !!visible.length;
    if (calendar) calendar.hidden = !calendarMode;
    if (toolbar) toolbar.hidden = !records.length;
    const statusLabel = state.status === 'upcoming' ? ' پیش‌رو' : state.status === 'past' ? ' برگزارشده' : state.status === 'recorded' ? ' با محتوای ضبط‌شده' : ' منتشرشده';
    const facetLabel = [state.kind, state.mode, state.access].filter(Boolean).map(item => ` · ${item}`).join('');
    count.textContent = visible.length
      ? `${fa(visible.length)} رویداد${statusLabel}${facetLabel}`
      : 'نتیجه‌ای پیدا نشد';
    if (!records.length) $('#eventsEmptyMessage').textContent = root.NORA_PUBLIC_SOURCE === 'unavailable'
      ? 'به پایگاه عمومی سرور دسترسی نیست؛ فهرست رویدادها فعلاً قابل نمایش نیست. کمی بعد دوباره تلاش کن.'
      : 'در حال حاضر رویدادی در فهرست عمومی منتشر نشده است.';
    else $('#eventsEmptyMessage').textContent = state.query || state.kind || state.mode || state.access ? 'واژهٔ جست‌وجو یا صافی‌ها را تغییر دهید.'
      : state.status === 'recorded' ? 'هنوز محتوای ضبط‌شده‌ای برای فروش یا دسترسی منتشر نشده است.' : 'برای این وضعیت رویدادی در دسترس نیست.';
    root.document.querySelectorAll('[data-event-filter]').forEach(button => {
      const active = button.dataset.eventFilter === state.status;
      button.classList.toggle('on', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    root.document.querySelectorAll('[data-event-view]').forEach(button => {
      const active = button.dataset.eventView === state.view;
      button.classList.toggle('on', active);
      button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    const sort = $('#eventSort');
    if (sort && sort.value !== state.sort) sort.value = state.sort;
    renderFacets();
    if (calendarMode) renderCalendar();
  }

  function setView(view, { updateHash = true } = {}) {
    state.view = view === 'cal' ? 'cal' : 'list';
    if (updateHash) { try { root.history.replaceState(null, '', '#' + (state.view === 'cal' ? 'cal' : 'list')); } catch (_) { /* ignore */ } }
    render();
  }
  function viewFromHash() {
    const hash = String(root.location.hash || '').replace('#', '');
    if (hash === 'cal') setView('cal', { updateHash: false });
    else if (hash === 'list' || hash === 'upcoming' || hash === 'cat' || hash === 'lib' || hash === 'library' || hash === 'recorded') {
      if (hash === 'upcoming') state.status = 'upcoming';
      if (hash === 'lib' || hash === 'library') state.status = 'past';
      if (hash === 'recorded') state.status = 'recorded';
      setView('list', { updateHash: false });
    }
  }

  function start() {
    const data = root.NORA_PUBLIC || { events: [] };
    records = (Array.isArray(data.events) ? data.events : []).slice();
    const search = $('#eventSearch');
    const clear = $('#clearSearch');
    const initialSearch = params.get('q') || '';
    const initialEvent = params.get('ev');
    search.value = initialSearch;
    state.query = initialSearch.trim();
    if (params.get('status') === 'past') state.status = 'past';
    else if (params.get('status') === 'upcoming') state.status = 'upcoming';
    else if (params.get('status') === 'recorded') state.status = 'recorded';
    const initialKind = cut(params.get('kind') || '', 80);
    if (initialKind && records.some(event => String(event.kind || '') === initialKind)) state.kind = initialKind;
    if (params.get('view') === 'cal' || root.location.hash === '#cal') state.view = 'cal';
    if (root.location.hash === '#upcoming') state.status = 'upcoming';
    if (root.location.hash === '#lib' || root.location.hash === '#library') state.status = 'past';
    if (root.location.hash === '#recorded') state.status = 'recorded';
    if (initialEvent) {
      const match = records.find(event => String(event.id) === initialEvent);
      if (match) root.location.replace(`event.html?id=${encodeURIComponent(match.id)}`);
    }
    clear.hidden = !search.value;
    search.addEventListener('input', () => {
      state.query = search.value.trim(); clear.hidden = !state.query; render();
    });
    clear.addEventListener('click', () => {
      search.value = ''; state.query = ''; clear.hidden = true; search.focus(); render();
    });
    root.document.querySelectorAll('[data-event-filter]').forEach(button => {
      button.addEventListener('click', () => { state.status = button.dataset.eventFilter; state.day = 0; if (state.status !== 'recorded') state.access = ''; render(); });
    });
    root.document.querySelectorAll('[data-event-view]').forEach(button => {
      button.addEventListener('click', () => setView(button.dataset.eventView));
    });
    const sort = $('#eventSort');
    if (sort) sort.addEventListener('change', () => { state.sort = ['near', 'cheap', 'dear', 'title'].includes(sort.value) ? sort.value : 'near'; render(); });
    const reset = $('#eventFacetReset');
    if (reset) reset.addEventListener('click', () => { state.kind = ''; state.mode = ''; state.access = ''; render(); });
    root.document.addEventListener('click', ev => {
      const target = ev.target && ev.target.closest ? ev.target : null;
      if (!target) return;
      const kind = target.closest('[data-event-kind]');
      if (kind) { state.kind = state.kind === kind.dataset.eventKind ? '' : kind.dataset.eventKind; state.day = 0; render(); return; }
      const mode = target.closest('[data-event-mode]');
      if (mode) { state.mode = state.mode === mode.dataset.eventMode ? '' : mode.dataset.eventMode; state.day = 0; render(); return; }
      const access = target.closest('[data-event-access]');
      if (access) { state.access = state.access === access.dataset.eventAccess ? '' : access.dataset.eventAccess; state.day = 0; render(); return; }
      const month = target.closest('[data-event-month]');
      if (month) { state.month = month.dataset.eventMonth; state.day = 0; renderCalendar(); return; }
      const day = target.closest('[data-event-day]');
      if (day && !day.disabled) { state.day = +day.dataset.eventDay || 0; renderCalendar(); }
    });
    root.addEventListener('hashchange', viewFromHash);
    render();
    if (['#list', '#cal', '#cat', '#lib', '#library', '#upcoming', '#recorded'].includes(root.location.hash)) {
      requestAnimationFrame(() => { const anchor = $('#eventToolbar') || $('#eventsList'); if (anchor && anchor.scrollIntoView) anchor.scrollIntoView({ block: 'start' }); });
    }
  }

  const ready = root.NORA_PUBLIC_READY && typeof root.NORA_PUBLIC_READY.then === 'function'
    ? root.NORA_PUBLIC_READY : Promise.resolve();
  ready.then(start).catch(start);
  root.NORA_EVENTS_PAGE = { parseJalali, modeOf, state };
})(typeof window === 'undefined' ? globalThis : window);
