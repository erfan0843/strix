(function (root) {
  'use strict';

  const $ = selector => root.document.querySelector(selector);
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const textWithBreaks = value => esc(value).replace(/\r?\n/g, '<br>');
  const safeImage = value => {
    const src = String(value || '').trim();
    if (/^https?:\/\//i.test(src)) return src;
    if (/^data:image\/(?:png|jpeg|webp|gif);base64,/i.test(src)) return src;
    if (/^(?:\.\.?\/|\/)?[A-Za-z0-9_~%-][A-Za-z0-9_./~%-]*$/.test(src)
        && !/(?:^|\/)\.\.(?:\/|$)/.test(src)) return src;
    return '';
  };
  const numberFa = value => {
    try { return new Intl.NumberFormat('fa-IR').format(Number(value) || 0); }
    catch (_) { return String(Number(value) || 0); }
  };
  const params = new URLSearchParams(root.location.search);
  const personId = params.get('id') || '';
  const container = $('#personPage');

  function publicData() {
    return root.NORA_PUBLIC || { people: [], events: [], articles: [] };
  }

  function contactHref(link) {
    const value = String((link && link.v) || '').trim();
    const kind = String((link && link.k) || '').toLowerCase();
    if (!value) return '';
    if (kind === 'mail') {
      const email = value.replace(/^mailto:/i, '');
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? `mailto:${email}` : '';
    }
    if (kind === 'tel') {
      const phone = value.replace(/^tel:/i, '').replace(/[^+\d۰-۹٠-٩]/g, '');
      return phone.length >= 8 && phone.length <= 20 ? `tel:${phone}` : '';
    }
    if (kind === 'tg' && !/^https?:/i.test(value)) return `https://t.me/${encodeURIComponent(value.replace(/^@/, ''))}`;
    if (kind === 'ig' && !/^https?:/i.test(value)) return `https://instagram.com/${encodeURIComponent(value.replace(/^@/, ''))}`;
    if (/^https?:\/\//i.test(value)) return value;
    if (kind === 'web' && /^[\w.-]+\.[A-Za-z]{2,}(?:\/.*)?$/.test(value)) return `https://${value}`;
    return '';
  }

  function makeContactRows(person) {
    const rows = Array.isArray(person.links) ? person.links : [];
    return rows.map(link => {
      const href = contactHref(link);
      if (!href) return '';
      const label = ({ tel: 'تلفن', mail: 'رایانامه', tg: 'تلگرام', ig: 'اینستاگرام', web: 'وب‌سایت' })[link.k] || 'پیوند';
      const external = /^https?:/i.test(href) ? ' target="_blank" rel="noopener noreferrer"' : '';
      return `<a class="person-contact" href="${esc(href)}"${external}><span>${esc(label)}</span><b dir="ltr">${esc(link.v)}</b></a>`;
    }).filter(Boolean).join('');
  }

  function eventCard(event) {
    const date = [event.when, event.time].filter(Boolean).join(' · ');
    const meta = [date, event.place].filter(Boolean).map(value => `<span>${esc(value)}</span>`).join('');
    return `<a class="person-event" href="event.html?id=${encodeURIComponent(event.id)}">
      <span class="person-event-icon" aria-hidden="true">${event.past ? '◷' : '◴'}</span>
      <span class="person-event-body"><b>${esc(event.t)}</b><small>${meta}</small></span>
      <span aria-hidden="true" class="person-event-arrow">‹</span>
    </a>`;
  }

  function articleCard(article) {
    if (!article || !(article.t || article.title)) return '';
    return `<article class="person-article"><b>${esc(article.t || article.title)}</b>
      ${article.lead ? `<p>${textWithBreaks(article.lead)}</p>` : ''}</article>`;
  }

  function renderMissing() {
    root.document.title = 'پروفایل پیدا نشد · نورا';
    container.innerHTML = `<section class="person-not-found card paper" role="status">
      <h1>پروفایل در دسترس نیست</h1>
      <p>این پروفایل در فهرست عمومی منتشرشده پیدا نشد.</p>
      <a class="btn primary" href="home.html#teachers">بازگشت به خانه</a>
    </section>`;
  }

  function render(person) {
    const data = publicData();
    const events = (Array.isArray(data.events) ? data.events : [])
      .filter(event => String(event.tchr || '') === String(person.id));
    const articles = (Array.isArray(data.articles) ? data.articles : [])
      .filter(article => String(article.tchr || '') === String(person.id));
    const isStaff = person.kind === 'staff';
    const portrait = safeImage(person.photo);
    const contacts = makeContactRows(person);
    const coursesRaw = String(person.courses || '').trim().replace(/[۰-۹]/g, digit => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit)))
      .replace(/[٠-٩]/g, digit => String('٠١٢٣٤٥٦٧٨٩'.indexOf(digit)));
    const courses = /^\d+$/.test(coursesRaw) && Number(coursesRaw) > 0 ? numberFa(coursesRaw) : '';
    const expertise = (Array.isArray(person.exp) ? person.exp : []).map(item =>
      `<span class="tag">${esc(item)}</span>`
    ).join('');
    const linkedForm = person.form ? String(person.form) : '';
    const hasPublishedForm = !!linkedForm;

    root.document.title = `${person.n} · نورا`;
    const description = $('meta[name="description"]');
    if (description) description.content = `${person.n}${person.r ? ` — ${person.r}` : ''}${person.bio ? ` · ${person.bio.slice(0, 120)}` : ''}`;
    const ogTitle = $('meta[property="og:title"]');
    if (ogTitle) ogTitle.content = person.n;
    const ogDescription = $('meta[property="og:description"]');
    if (ogDescription) ogDescription.content = person.bio || person.r || person.n;

    container.innerHTML = `<nav class="person-breadcrumb" aria-label="مسیر صفحه">
        <a href="home.html">خانه</a><span aria-hidden="true">/</span>
        <a href="home.html#${isStaff ? 'staff' : 'teachers'}">${isStaff ? 'دست‌اندرکاران' : 'اساتید و مدرسان'}</a>
        <span aria-hidden="true">/</span><span aria-current="page">${esc(person.n)}</span>
      </nav>
      <article class="person-profile card paper">
        <header class="person-header">
          <div class="person-avatar">${portrait ? `<img src="${esc(portrait)}" alt="تصویر ${esc(person.n)}" decoding="async"/>` : `<span aria-hidden="true">${esc(person.ini || person.n.slice(0, 1))}</span>`}</div>
          <div class="person-heading"><span class="person-role">${isStaff ? 'دست‌اندرکار' : 'استاد / مدرس'}</span>
            <h1>${esc(person.n)}</h1>
            ${person.r ? `<p>${esc(person.r)}</p>` : ''}
            ${person.role2 ? `<p class="person-role2">${esc(person.role2)}</p>` : ''}
          </div>
        </header>
        ${person.tag || expertise ? `<div class="person-tags">${person.tag ? `<span class="tag brand">${esc(person.tag)}</span>` : ''}${expertise}</div>` : ''}
        ${hasPublishedForm ? `<div class="person-actions"><a class="btn quiet" href="form.html?fid=${encodeURIComponent(linkedForm)}">${esc(person.formTxt || 'فرم ارتباط')}</a></div>` : ''}
        ${person.bio ? `<section class="person-section"><h2>درباره</h2><p class="person-bio">${textWithBreaks(person.bio)}</p></section>` : ''}
        ${person.quote ? `<blockquote class="person-quote">${textWithBreaks(person.quote)}</blockquote>` : ''}
        ${person.where || person.yrs || courses || (!isStaff && events.length) ? `<section class="person-facts" aria-label="اطلاعات تکمیلی">
          ${person.where ? `<div><span>محل فعالیت</span><b>${esc(person.where)}</b></div>` : ''}
          ${person.yrs ? `<div><span>سابقه</span><b>${esc(person.yrs)}</b></div>` : ''}
          ${courses ? `<div><span>دوره‌های ثبت‌شده</span><b>${courses}</b></div>` : ''}
          ${!isStaff && events.length ? `<div><span>رویدادهای منتشرشده</span><b>${numberFa(events.length)}</b></div>` : ''}
        </section>` : ''}
        ${contacts ? `<section class="person-section"><h2>راه‌های ارتباط</h2><div class="person-contact-list">${contacts}</div></section>` : ''}
        ${events.length ? `<section class="person-section"><h2>${isStaff ? 'رویدادهای مرتبط' : 'رویدادهای این مدرس'}</h2>
          <div class="person-event-list">${events.map(eventCard).join('')}</div></section>` : ''}
        ${articles.length ? `<section class="person-section"><h2>مطالب منتشرشده</h2>
          <div class="person-article-list">${articles.map(articleCard).join('')}</div></section>` : ''}
      </article>`;
  }

  function start() {
    if (!container) return;
    const data = publicData();
    const person = (Array.isArray(data.people) ? data.people : [])
      .find(item => String(item.id) === String(personId));
    if (!person) { renderMissing(); return; }
    render(person);
  }

  const ready = root.NORA_PUBLIC_READY && typeof root.NORA_PUBLIC_READY.then === 'function'
    ? root.NORA_PUBLIC_READY : Promise.resolve();
  ready.then(start).catch(start);
})(typeof window === 'undefined' ? globalThis : window);
