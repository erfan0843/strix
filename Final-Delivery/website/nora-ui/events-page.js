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
  let status = 'all';
  let query = '';
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

  function eventMatches(event) {
    if (status === 'upcoming' && event.past) return false;
    if (status === 'past' && !event.past) return false;
    if (!query) return true;
    const teacher = person(event);
    const haystack = [event.t, event.kind, event.d, event.when, event.time, event.place,
      ...(Array.isArray(event.tags) ? event.tags : []), teacher && teacher.n, teacher && teacher.r]
      .filter(Boolean).join(' ').toLocaleLowerCase();
    return haystack.includes(query.toLocaleLowerCase());
  }

  function card(event) {
    const formId = registrationForm(event);
    const profile = person(event);
    const cover = safeUrl(event.posterUp || event.poster);
    const when = [event.when, event.time].filter(Boolean).join(' · ');
    const tags = (Array.isArray(event.tags) ? event.tags : []).slice(0, 4);
    if (event.kind && !tags.includes(event.kind)) tags.unshift(event.kind);
    const detailHref = `event.html?id=${encodeURIComponent(event.id)}`;
    const coverHtml = cover ? `<img src="${esc(cover)}" alt="" loading="lazy" decoding="async"/>` : '';
    const formButton = event.past
      ? ''
      : formId
        ? `<a class="btn primary" href="form.html?fid=${encodeURIComponent(formId)}&kind=reg">ثبت‌نام</a>`
        : `<span class="event-register-missing">فرم ثبت‌نام منتشر نشده است</span>`;
    return `<article class="event-list-card card paper">
      <a class="event-list-cover" href="${detailHref}" aria-label="جزئیات ${esc(event.t)}">
        ${coverHtml}<span class="cover-shade"></span>
        ${event.kind ? `<span class="cover-kind">${esc(event.kind)}</span>` : ''}
        ${when ? `<span class="cover-date">${esc(when)}</span>` : ''}
      </a>
      <div class="event-list-body">
        ${tags.length ? `<div class="event-list-tags">${tags.slice(0, 4).map((tag, index) => `<span class="tag${index === 0 ? ' brand' : ''}">${esc(tag)}</span>`).join('')}</div>` : ''}
        <a class="event-list-title" href="${detailHref}">${esc(event.t)}</a>
        ${event.d ? `<p class="event-list-description">${esc(cut(event.d, 700))}</p>` : ''}
        <div class="event-list-meta">
          ${when ? `<span><svg class="i" aria-hidden="true"><use href="#i-clock"/></svg><span>${esc(when)}</span></span>` : ''}
          ${event.place ? `<span><svg class="i" aria-hidden="true"><use href="#i-pin"/></svg><span>${esc(event.place)}</span></span>` : ''}
          ${event.cap ? `<span><svg class="i" aria-hidden="true"><use href="#i-user"/></svg><span>ظرفیت ${fa(event.cap)} نفر</span></span>` : ''}
          ${!event.past ? `<span><svg class="i" aria-hidden="true"><use href="#i-calendar"/></svg><span>${event.price ? `${fa(event.price)} ریال` : 'رایگان'}</span></span>` : ''}
        </div>
        ${profile ? `<a class="event-list-teacher" href="person.html?id=${encodeURIComponent(profile.id)}"><svg class="i" aria-hidden="true"><use href="#i-graduation"/></svg>${esc(profile.n)}</a>` : ''}
        <div class="event-list-actions"><a class="btn quiet" href="${detailHref}">جزئیات کامل</a>${formButton}</div>
      </div>
    </article>`;
  }

  function render() {
    const visible = records.filter(eventMatches);
    const list = $('#eventsList'), empty = $('#eventsEmpty'), count = $('#eventsCount');
    list.innerHTML = visible.map(card).join('');
    list.hidden = !visible.length;
    empty.hidden = !!visible.length;
    count.textContent = visible.length
      ? `${fa(visible.length)} رویداد${status === 'upcoming' ? ' پیش‌رو' : status === 'past' ? ' برگزارشده' : ' منتشرشده'}`
      : 'نتیجه‌ای پیدا نشد';
    if (!records.length) $('#eventsEmptyMessage').textContent = 'در حال حاضر رویدادی در فهرست عمومی منتشر نشده است.';
    else $('#eventsEmptyMessage').textContent = query ? 'واژهٔ جست‌وجو یا فیلتر را تغییر دهید.' : 'برای این وضعیت رویدادی در دسترس نیست.';
    document.querySelectorAll('[data-event-filter]').forEach(button => {
      const active = button.dataset.eventFilter === status;
      button.classList.toggle('on', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function start() {
    const data = root.NORA_PUBLIC || { events: [] };
    records = (Array.isArray(data.events) ? data.events : []).slice();
    const search = $('#eventSearch');
    const clear = $('#clearSearch');
    const initialSearch = params.get('q') || '';
    const initialEvent = params.get('ev');
    search.value = initialSearch;
    query = initialSearch.trim();
    if (params.get('status') === 'past') status = 'past';
    else if (params.get('status') === 'upcoming') status = 'upcoming';
    if (initialEvent) {
      const match = records.find(event => String(event.id) === initialEvent);
      if (match) root.location.replace(`event.html?id=${encodeURIComponent(match.id)}`);
    }
    clear.hidden = !search.value;
    search.addEventListener('input', () => {
      query = search.value.trim(); clear.hidden = !query; render();
    });
    clear.addEventListener('click', () => {
      search.value = ''; query = ''; clear.hidden = true; search.focus(); render();
    });
    document.querySelectorAll('[data-event-filter]').forEach(button => {
      button.addEventListener('click', () => { status = button.dataset.eventFilter; render(); });
    });
    render();
    if (root.location.hash === '#list' || root.location.hash === '#cal' || root.location.hash === '#cat') {
      requestAnimationFrame(() => $('#eventsList').scrollIntoView({ block: 'start' }));
    }
  }

  const ready = root.NORA_PUBLIC_READY && typeof root.NORA_PUBLIC_READY.then === 'function'
    ? root.NORA_PUBLIC_READY : Promise.resolve();
  ready.then(start).catch(start);
})(typeof window === 'undefined' ? globalThis : window);
