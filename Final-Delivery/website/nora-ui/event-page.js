(function (root) {
  'use strict';

  const $ = selector => root.document.querySelector(selector);
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const textWithBreaks = value => esc(value).replace(/\r?\n/g, '<br>');
  const safeUrl = value => {
    const url = String(value || '').trim();
    if (/^https?:\/\//i.test(url) || /^data:image\/(?:png|jpeg|webp|gif);base64,/i.test(url)) return url;
    if (/^(?:\.\.?\/|\/)?[A-Za-z0-9_~%-][A-Za-z0-9_./~%-]*$/.test(url)
        && !/(?:^|\/)\.\.(?:\/|$)/.test(url)) return url;
    return '';
  };
  const safeMediaUrl = value => {
    const url = String(value || '').trim();
    if (/^data:(?:application\/(?:pdf|zip|x-zip-compressed|octet-stream)|audio\/(?:mpeg|mp4|ogg|wav|webm)|video\/(?:mp4|webm|ogg));base64,/i.test(url)) return url;
    return safeUrl(url);
  };
  const digits = value => {
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0) return '';
    try { return new Intl.NumberFormat('fa-IR').format(number); }
    catch (_) { return String(number); }
  };
  const money = value => value ? `${digits(value)} ریال` : 'رایگان';
  const eventId = new URLSearchParams(root.location.search).get('id')
    || root.location.hash.replace(/^#/, '');
  const page = $('#page');
  const toolbar = $('#ctabar');
  const toolbarInner = $('#ctaIn');

  function eventById(id) {
    const publicEvents = root.NORA_PUBLIC && Array.isArray(root.NORA_PUBLIC.events)
      ? root.NORA_PUBLIC.events : [];
    return publicEvents.find(event => String(event.id) === String(id)) || null;
  }

  function personById(id) {
    const people = root.NORA_PUBLIC && Array.isArray(root.NORA_PUBLIC.people)
      ? root.NORA_PUBLIC.people : [];
    return people.find(person => String(person.id) === String(id)) || null;
  }

  function partnerById(id) {
    const partners = root.NORA_PUBLIC && Array.isArray(root.NORA_PUBLIC.partners)
      ? root.NORA_PUBLIC.partners : [];
    return partners.find(partner => String(partner.id) === String(id)) || null;
  }

  function registrationForm(event) {
    const listed = (Array.isArray(event.forms) ? event.forms : []).find(form =>
      form && form.id && (!form.need || form.need === 'reg')
    );
    if (listed) return { id: String(listed.id), name: listed.n || '' };
    if (root.NORA_PUBLIC_SOURCE === 'server') return null;
    const ui = root.NORA_UI || {};
    const localForms = typeof ui.formsFor === 'function' ? ui.formsFor(String(event.id)) : [];
    const eligible = (Array.isArray(localForms) ? localForms : []).find(form => {
      const need = form && (form.need || 'reg');
      return need === 'reg' && form.id && form.status !== 'draft'
        && form.serverDraft !== true && form.eventVisible !== false;
    });
    const id = (eligible && eligible.id) || event.regForm || '';
    return id ? { id: String(id), name: (eligible && eligible.name) || event.regName || '' } : null;
  }

  /* برنامه‌های دیگر از همان عکس عمومی سرور: هم‌وضعیت (پیش‌رو/برگزارشده)، اول هم‌نوع، تا ۴ مورد */
  function relatedEvents(event) {
    const publicEvents = root.NORA_PUBLIC && Array.isArray(root.NORA_PUBLIC.events)
      ? root.NORA_PUBLIC.events : [];
    const others = publicEvents.filter(item => item && String(item.id) !== String(event.id) && !!item.past === !!event.past);
    const sameKind = others.filter(item => item.kind && item.kind === event.kind);
    const rest = others.filter(item => !sameKind.includes(item));
    return sameKind.concat(rest).slice(0, 4);
  }

  function relatedSection(event) {
    const list = relatedEvents(event);
    if (!list.length) return '';
    return `<section class="event-section event-related" aria-labelledby="event-related-title">
      <h2 id="event-related-title">${event.past ? 'برنامه‌های برگزارشدهٔ دیگر' : 'برنامه‌های دیگر'}</h2>
      <ul class="related-list">${list.map(item => `<li><a href="event.html?id=${encodeURIComponent(item.id)}" data-related-event="${esc(item.id)}">
        <b>${esc(item.t)}</b><small>${esc([item.kind, item.when].filter(Boolean).join(' · '))}</small></a></li>`).join('')}</ul>
      <a class="back-link" href="events.html${event.past ? '?status=past' : '?status=upcoming'}">همهٔ ${event.past ? 'برگزارشده‌ها' : 'برنامه‌های پیش‌رو'}</a>
    </section>`;
  }

  function infoRow(label, value) {
    if (!value) return '';
    return `<div class="detail-item"><span>${esc(label)}</span><b>${esc(value)}</b></div>`;
  }

  function renderMissing() {
    root.document.title = 'رویداد پیدا نشد · نورا';
    page.innerHTML = `<section class="empty-state card paper" role="status">
      <h1>این رویداد در دسترس نیست</h1>
      <p>ممکن است رویداد از فهرست عمومی برداشته شده باشد یا نشانی آن نادرست باشد.</p>
      <a class="btn primary" href="events.html#list">بازگشت به رویدادها</a>
    </section>`;
    toolbar.hidden = true;
  }

  function renderEvent(event) {
    const instructor = personById(event.tchr);
    const partner = partnerById(event.partnerId);
    const form = registrationForm(event);
    const isPast = !!event.past;
    const serverSnapshot = root.NORA_PUBLIC_SOURCE === 'server';
    /* فاز ۸: منابع/پرسش‌وپاسخ/دیدگاه فقط با API سرور معنا دارند؛ بدون سرور هیچ بخش خالی یا ساختگی ساخته نمی‌شود. */
    const interactive = serverSnapshot && root.NORA_EVENT_INTERACTION && typeof root.NORA_EVENT_INTERACTION.mount === 'function';
    const cover = safeUrl(event.posterUp || event.poster);
    const coverHtml = cover
      ? `<img class="event-cover-image" src="${esc(cover)}" alt="پوستر ${esc(event.t)}" decoding="async"/>`
      : `<div class="event-cover-fallback" aria-hidden="true"><span>${esc(event.kind || 'رویداد')}</span></div>`;
    const schedule = (Array.isArray(event.parts) ? event.parts : []).map((part, index) => {
      const heading = part.title || `جلسهٔ ${digits(index + 1)}`;
      const when = [part.date, part.time, part.to && `تا ${part.to}`].filter(Boolean).join(' · ');
      return `<li><b>${esc(heading)}</b>${when ? `<span>${esc(when)}</span>` : ''}
        ${part.description ? `<p>${textWithBreaks(part.description)}</p>` : ''}</li>`;
    }).join('');
    const tags = (Array.isArray(event.tags) ? event.tags : []).map(tag =>
      `<span class="tag">${esc(tag)}</span>`
    ).join('');
    /* وضعیت ثبت‌نام فقط از سرور (event.registration)؛ بدون آن (سرور قدیمی) رفتار پیشین حفظ می‌شود */
    const CD = root.NORA_COUNTDOWN;
    const reg = event.registration && typeof event.registration === 'object' ? event.registration : null;
    const lifecycle = reg ? reg.lifecycle : (event.lifecycle || 'scheduled');
    const inactive = lifecycle === 'cancelled' || lifecycle === 'postponed';
    const regOpen = reg ? (reg.state === 'open' && !inactive) : (!!form && !inactive);
    const stateText = CD && reg ? CD.stateLabel(reg) : (lifecycle === 'cancelled' ? 'لغو شد' : lifecycle === 'postponed' ? 'به تعویق افتاد' : '');
    const stateTone = CD && reg ? CD.stateTone(reg) : (inactive ? 'stop' : 'mute');
    const target = CD && !isPast ? CD.eventTarget(event) : null;
    const when = value => (CD && value ? CD.formatMoment(value) : '');
    const formLink = form ? `<a class="btn primary" href="form.html?fid=${encodeURIComponent(form.id)}&kind=reg" id="reg">
             <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> فرم ثبت‌نام همین رویداد
           </a>${form.name ? `<small class="cap">${esc(form.name)}</small>` : ''}` : '';
    const regNotes = [];
    if (reg && reg.state === 'open' && reg.closesAt) regNotes.push(`مهلت ثبت‌نام تا ${when(reg.closesAt)}`);
    if (reg && reg.state === 'not_started' && reg.opensAt) regNotes.push(`ثبت‌نام از ${when(reg.opensAt)} آغاز می‌شود`);
    if (reg && reg.state === 'closed' && reg.closesAt) regNotes.push(`مهلت ثبت‌نام ${when(reg.closesAt)} به پایان رسید`);
    if (reg && reg.state === 'full') regNotes.push('ظرفیت این رویداد تکمیل شده است؛ ثبت‌نام تازه پذیرفته نمی‌شود.');
    if (lifecycle === 'cancelled') regNotes.push('این رویداد لغو شده است و ثبت‌نامی انجام نمی‌شود.');
    if (lifecycle === 'postponed') regNotes.push('این رویداد به تعویق افتاده است؛ تا اعلام زمان تازه، ثبت‌نام باز نیست.');
    const registration = isPast
      ? `<p class="cap">ثبت‌نام این رویداد پایان یافته است.</p>`
      : `${stateText ? `<p class="event-reg-state"><span class="reg-state ${esc(stateTone)}">${esc(stateText)}</span></p>` : ''}
         ${target ? `<div class="event-reg-timer" data-reg-timer>${CD.markup(target)}</div>` : ''}
         ${regNotes.length ? `<p class="cap event-reg-note">${regNotes.map(esc).join('<br>')}</p>` : ''}
         <div data-reg-action>${regOpen && form ? formLink
           : reg && reg.state === 'none' || (!form && !inactive) ? `<p class="registration-notice" role="status">فرم ثبت‌نام عمومی برای این رویداد منتشر نشده است.</p>`
           : ''}</div>`;
    const calendarButton = event.startsAt && Number.isFinite(Date.parse(event.startsAt)) && !isPast && lifecycle !== 'cancelled'
      ? `<button type="button" class="btn quiet" id="addToCalendar"><svg class="i" aria-hidden="true"><use href="#i-calendar"/></svg> افزودن به تقویم</button>` : '';
    const shareButton = `<button type="button" class="btn quiet" id="shareEvent"><svg class="i" aria-hidden="true"><use href="#i-share"/></svg> اشتراک‌گذاری</button>`;

    root.document.title = `${event.t} · نورا`;
    const descriptionMeta = $('meta[name="description"]');
    if (descriptionMeta) descriptionMeta.content = `${event.t}${event.d ? ` — ${event.d.slice(0, 150)}` : ''}`;
    const ogTitle = $('meta[property="og:title"]');
    if (ogTitle) ogTitle.content = event.t;
    const ogDescription = $('meta[property="og:description"]');
    if (ogDescription) ogDescription.content = event.d.slice(0, 200) || event.t;

    page.innerHTML = `<nav class="event-breadcrumb" aria-label="مسیر صفحه">
        <a href="home.html">خانه</a><span aria-hidden="true">/</span>
        <a href="events.html#list">رویدادها</a><span aria-hidden="true">/</span><span aria-current="page">${esc(event.t)}</span>
      </nav>
      <div class="event-layout">
        <article class="event-detail card paper">
          <div class="event-cover">${coverHtml}</div>
          <div class="event-heading">
            <div class="event-tags">${tags}${event.kind ? `<span class="tag brand">${esc(event.kind)}</span>` : ''}
              ${isPast ? '<span class="tag">برگزارشده</span>' : ''}${!isPast && stateText ? `<span class="reg-state ${esc(stateTone)}">${esc(stateText)}</span>` : ''}</div>
            <h1>${esc(event.t)}</h1>
            ${event.d ? `<p class="event-lead">${textWithBreaks(event.d)}</p>` : ''}
          </div>
          <section class="event-section" aria-labelledby="event-info-title">
            <h2 id="event-info-title">اطلاعات رویداد</h2>
            <div class="detail-grid">
              ${infoRow('تاریخ', event.when)}
              ${infoRow('ساعت', event.time)}
              ${infoRow('شروع (به وقت تهران)', when(event.startsAt))}
              ${infoRow('پایان', when(event.endsAt))}
              ${!isPast ? infoRow('مهلت ثبت‌نام', when(reg ? reg.closesAt : event.regClosesAt)) : ''}
              ${infoRow('شیوهٔ برگزاری', event.mode)}
              ${infoRow('مکان', event.place)}
              ${partner ? `<a class="detail-item event-partner-link" href="partner.html?id=${encodeURIComponent(partner.id)}"><span>نهاد همکار</span><b>${esc(partner.n)}</b></a>` : ''}
              ${infoRow('هزینهٔ ثبت‌نام', isPast ? '' : money(event.price))}
              ${infoRow('ظرفیت', event.cap ? `${digits(event.cap)} نفر` : '')}
              ${infoRow('تعداد جلسه', event.sess > 1 ? `${digits(event.sess)} جلسه` : '')}
            </div>
            ${event.conditions ? `<div class="event-conditions"><b>شرایط شرکت</b><p>${textWithBreaks(event.conditions)}</p></div>` : ''}
          </section>
          ${schedule ? `<section class="event-section" aria-labelledby="event-schedule-title">
            <h2 id="event-schedule-title">زمان‌بندی و سرفصل‌ها</h2><ol class="schedule-list">${schedule}</ol>
          </section>` : ''}
          ${interactive ? '<div data-event-interaction="resources" hidden></div>' : ''}
          ${instructor ? `<section class="event-section" aria-labelledby="event-instructor-title">
            <h2 id="event-instructor-title">مدرس / برگزارکننده</h2>
            <a class="event-person" href="person.html?id=${encodeURIComponent(instructor.id)}">
              <span class="event-person-avatar">${instructor.photo ? `<img src="${esc(instructor.photo)}" alt="" loading="lazy"/>` : esc(instructor.ini || instructor.n.slice(0, 1))}</span>
              <span><b>${esc(instructor.n)}</b><small>${esc(instructor.r || instructor.role2)}</small></span>
              <span class="event-person-arrow" aria-hidden="true">‹</span>
            </a>
          </section>` : ''}
          ${isPast && Array.isArray(event.media) && event.media.length ? `<section class="event-section" data-uimedia aria-labelledby="event-media-title">
            <h2 id="event-media-title">رسانه‌های منتشرشده</h2>
            <ul class="media-list">${event.media.map(item => {
              const row=item&&typeof item==='object'?item:{}, kind=String(row.k||row.kind||'').toLowerCase(),
                title=row.t||row.n||'رسانهٔ رویداد', url=safeMediaUrl(row.src||row.url), ui=root.NORA_UI||{},
                audio=['audio','aud'].includes(kind)||String(row.mime||row.content_type||'').toLowerCase().startsWith('audio/'),
                video=['video','vid'].includes(kind)||String(row.mime||row.content_type||'').toLowerCase().startsWith('video/'),
                receive=/^[0-9a-f]{32}$/i.test(String(row.delivery_id||''))&&row.available===true
                  &&typeof ui.baleStartHref==='function'?ui.baleStartHref('file_'+row.delivery_id):'';
              let content='';
              if(audio&&url) content=`<div class="event-media-player"><b>${esc(title)}</b><audio controls controlsList="nodownload" preload="metadata" src="${esc(url)}">پخش صدا در این مرورگر پشتیبانی نمی‌شود.</audio></div>`;
              else if(video&&url) content=`<div class="event-media-player"><b>${esc(title)}</b><video controls controlsList="nodownload" playsinline preload="metadata" src="${esc(url)}">پخش ویدیو در این مرورگر پشتیبانی نمی‌شود.</video></div>`;
              else if(receive) content=`<a href="${esc(receive)}" target="_blank" rel="noopener noreferrer">${esc(title)} · دریافت در بات بله</a>`;
              else if(kind==='link'&&url) content=`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(title)} · بازکردن پیوند</a>`;
              else content=`<span>${esc(title)}${row.available?' · پیوند دریافت بات تنظیم نشده':' · دریافت از بات منتشر نشده'}</span>`;
              return `<li>${content}${row.s?`<small>${esc(row.s)}</small>`:''}</li>`;
            }).join('')}</ul>
          </section>` : ''}
          ${isPast && event.cert ? `<section class="event-section" data-cert-requirement aria-labelledby="event-cert-title">
            <h2 id="event-cert-title">شرایط گواهی</h2>
            ${event.certMin > 0 ? `<p class="cap">${serverSnapshot?'حداقل حضور برای درخواست گواهی':'حداقل حضور نمایشی'} ٪${digits(event.certMin)}</p>` : ''}
            ${event.certNote ? `<p>${textWithBreaks(event.certNote)}</p>` : ''}
            <p class="cap">${serverSnapshot?'این شرط از اطلاعات منتشرشدهٔ سرور است. این صفحه گواهی صادر یا استعلام نمی‌کند؛ روند صدور و تأیید را از برگزارکننده پیگیری کنید.':'این شرط صرفاً نمایشی است؛ بررسی درخواست و تأیید گواهی فقط پس از تأیید مالک انجام می‌شود. این صفحه گواهی رسمی صادر یا استعلام نمی‌کند.'}</p>
          </section>` : ''}
          ${interactive ? '<div data-event-interaction="qa" hidden></div><div data-event-interaction="reviews" hidden></div>' : ''}
          ${relatedSection(event)}
        </article>
        <aside class="event-register card paper" aria-labelledby="event-register-title">
          <h2 id="event-register-title">${isPast ? 'اطلاعات آرشیو' : 'ثبت‌نام'}</h2>
          ${!isPast ? `<p class="event-price">${esc(money(event.price))}</p>` : ''}
          <div class="event-register-action">${registration}</div>
          <div class="event-share-row">${calendarButton}${shareButton}</div>
          <div class="event-share-fallback" id="shareFallback" hidden><label class="cap" for="shareUrl">پیوند این رویداد</label><input id="shareUrl" class="input" type="text" readonly dir="ltr"/></div>
          <a class="back-link" href="events.html#list">بازگشت به فهرست رویدادها</a>
        </aside>
      </div>`;

    if (!isPast && regOpen && form && toolbar && toolbarInner) {
      toolbarInner.innerHTML = `<span><b>${esc(event.t)}</b><small>${esc(event.when || '')}</small></span>
        <span class="sp"></span><a class="btn primary" href="form.html?fid=${encodeURIComponent(form.id)}&kind=reg">ثبت‌نام</a>`;
      toolbar.hidden = false;
    } else {
      toolbar.hidden = true;
    }
    if (CD) CD.mount(page);
    bindActions(event, { form, regOpen });
    if (interactive) root.NORA_EVENT_INTERACTION.mount(event, page);
  }

  /* پایان شمارش مهلت: دکمهٔ ثبت‌نام برداشته می‌شود، ولی وضعیت قطعی فقط با عکس تازهٔ سرور (نوسازی) تعیین می‌شود؛
     سرور هم در GET فرم و ثبت پاسخ، مهلت را جداگانه بررسی می‌کند (۴۰۹ registration_closed). */
  function onDeadlineEnded(detail) {
    if (!detail || detail.kind !== 'reg_close') return;
    const action = page.querySelector('[data-reg-action]');
    if (action) action.innerHTML = `<p class="registration-notice" role="status">مهلت ثبت‌نام طبق ساعت سرور به پایان رسید. برای وضعیت قطعی، صفحه را نوسازی کنید.</p>
      <button type="button" class="btn quiet" id="refreshState">به‌روزرسانی وضعیت</button>`;
    if (toolbar) toolbar.hidden = true;
    const refresh = page.querySelector('#refreshState');
    if (refresh) refresh.addEventListener('click', () => root.location.reload());
  }

  function icsText(event) {
    const stamp = value => new Date(value).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
    const clean = value => String(value || '').replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/[,;]/g, m => '\\' + m);
    const start = Date.parse(event.startsAt);
    const end = Number.isFinite(Date.parse(event.endsAt)) && Date.parse(event.endsAt) > start ? Date.parse(event.endsAt) : start + 3600000;
    const url = new URL(`event.html?id=${encodeURIComponent(event.id)}`, root.location.href).href;
    return ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Nora//Event//FA', 'BEGIN:VEVENT',
      `UID:${clean(event.id)}@nora`, `DTSTAMP:${stamp(Date.now())}`, `DTSTART:${stamp(start)}`, `DTEND:${stamp(end)}`,
      `SUMMARY:${clean(event.t)}`, event.place ? `LOCATION:${clean(event.place)}` : '', `URL:${url}`,
      `DESCRIPTION:${clean((event.d || '').slice(0, 500))}`, 'END:VEVENT', 'END:VCALENDAR'].filter(Boolean).join('\r\n');
  }

  function bindActions(event) {
    page.addEventListener('nora:countdown-ended', e => onDeadlineEnded(e.detail), { once: true });
    const calendar = page.querySelector('#addToCalendar');
    if (calendar) calendar.addEventListener('click', () => {
      try {
        const blob = new root.Blob([icsText(event)], { type: 'text/calendar;charset=utf-8' });
        const href = root.URL.createObjectURL(blob);
        const link = root.document.createElement('a');
        link.href = href; link.download = `nora-${String(event.id).replace(/[^A-Za-z0-9_-]/g, '')}.ics`;
        root.document.body.appendChild(link); link.click(); link.remove();
        root.setTimeout(() => root.URL.revokeObjectURL(href), 2000);
      } catch (_) {
        if (root.NORA_UI && root.NORA_UI.toast) root.NORA_UI.toast('ساخت فایل تقویم در این مرورگر ممکن نشد.');
      }
    });
    const share = page.querySelector('#shareEvent');
    if (share) share.addEventListener('click', async () => {
      const url = new URL(`event.html?id=${encodeURIComponent(event.id)}`, root.location.href).href;
      const payload = { title: event.t, text: [event.when, event.time, event.place].filter(Boolean).join(' · '), url };
      const toast = msg => { if (root.NORA_UI && root.NORA_UI.toast) root.NORA_UI.toast(msg); };
      try {
        if (root.navigator && typeof root.navigator.share === 'function') { await root.navigator.share(payload); return; }
      } catch (error) { if (error && error.name === 'AbortError') return; }
      try {
        if (root.navigator && root.navigator.clipboard && typeof root.navigator.clipboard.writeText === 'function') {
          await root.navigator.clipboard.writeText(url); toast('پیوند رویداد کپی شد'); return;
        }
      } catch (_) { /* به حالت دستی می‌رویم */ }
      const box = page.querySelector('#shareFallback'), input = page.querySelector('#shareUrl');
      if (box && input) { input.value = url; box.hidden = false; input.focus(); input.select(); }
    });
  }

  function start() {
    if (!page) return;
    const event = eventById(eventId);
    if (!event) { renderMissing(); return; }
    renderEvent(event);
  }

  const ready = root.NORA_PUBLIC_READY && typeof root.NORA_PUBLIC_READY.then === 'function'
    ? root.NORA_PUBLIC_READY : Promise.resolve();
  ready.then(start).catch(start);
})(typeof window === 'undefined' ? globalThis : window);
