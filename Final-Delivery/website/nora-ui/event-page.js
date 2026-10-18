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
    const registration = isPast
      ? `<p class="cap">ثبت‌نام این رویداد پایان یافته است.</p>`
      : form
        ? `<a class="btn primary" href="form.html?fid=${encodeURIComponent(form.id)}&kind=reg" id="reg">
             <svg class="i" aria-hidden="true"><use href="#i-pen"/></svg> فرم ثبت‌نام همین رویداد
           </a>${form.name ? `<small class="cap">${esc(form.name)}</small>` : ''}`
        : `<p class="registration-notice" role="status">فرم ثبت‌نام عمومی برای این رویداد منتشر نشده است.</p>`;

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
              ${isPast ? '<span class="tag">برگزارشده</span>' : ''}</div>
            <h1>${esc(event.t)}</h1>
            ${event.d ? `<p class="event-lead">${textWithBreaks(event.d)}</p>` : ''}
          </div>
          <section class="event-section" aria-labelledby="event-info-title">
            <h2 id="event-info-title">اطلاعات رویداد</h2>
            <div class="detail-grid">
              ${infoRow('تاریخ', event.when)}
              ${infoRow('ساعت', event.time)}
              ${infoRow('شیوهٔ برگزاری', event.mode)}
              ${infoRow('مکان', event.place)}
              ${partner ? `<a class="detail-item event-partner-link" href="partner.html?id=${encodeURIComponent(partner.id)}"><span>نهاد همکار</span><b>${esc(partner.n)}</b></a>` : ''}
              ${infoRow('هزینهٔ ثبت‌نام', isPast ? '' : money(event.price))}
              ${infoRow('ظرفیت', event.cap ? `${digits(event.cap)} نفر` : '')}
              ${infoRow('تعداد جلسه', event.sess > 1 ? `${digits(event.sess)} جلسه` : '')}
            </div>
          </section>
          ${schedule ? `<section class="event-section" aria-labelledby="event-schedule-title">
            <h2 id="event-schedule-title">زمان‌بندی و سرفصل‌ها</h2><ol class="schedule-list">${schedule}</ol>
          </section>` : ''}
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
          ${relatedSection(event)}
        </article>
        <aside class="event-register card paper" aria-labelledby="event-register-title">
          <h2 id="event-register-title">${isPast ? 'اطلاعات آرشیو' : 'ثبت‌نام'}</h2>
          ${!isPast ? `<p class="event-price">${esc(money(event.price))}</p>` : ''}
          <div class="event-register-action">${registration}</div>
          <a class="back-link" href="events.html#list">بازگشت به فهرست رویدادها</a>
        </aside>
      </div>`;

    if (!isPast && form && toolbar && toolbarInner) {
      toolbarInner.innerHTML = `<span><b>${esc(event.t)}</b><small>${esc(event.when || '')}</small></span>
        <span class="sp"></span><a class="btn primary" href="form.html?fid=${encodeURIComponent(form.id)}&kind=reg">ثبت‌نام</a>`;
      toolbar.hidden = false;
    } else {
      toolbar.hidden = true;
    }
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
