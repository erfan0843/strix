(function (root) {
  'use strict';
  /* صفحهٔ اختصاصی نهاد همکار: partner.html?id=…
     داده فقط از snapshot عمومیِ سرور (NORA_PUBLIC.partners) خوانده می‌شود؛ هیچ دادهٔ نمونه،
     آمار ساختگی یا رابطهٔ حدسی ساخته نمی‌شود. رویدادهای مرتبط فقط از فیلد صریح event.partnerId می‌آیند. */

  const $ = selector => root.document.querySelector(selector);
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const textWithBreaks = value => esc(value).replace(/\r?\n/g, '<br>');
  const safeImage = value => {
    const src = String(value || '').trim();
    if (/^https?:\/\//i.test(src)) {
      try { const url = new URL(src); return url.username || url.password ? '' : url.href; } catch (_) { return ''; }
    }
    if (/^data:image\/(?:png|jpeg|webp|gif|svg\+xml);base64,/i.test(src)) return src;
    if (/^(?:\.\.?\/|\/)?[A-Za-z0-9_~%-][A-Za-z0-9_./~%-]*$/.test(src)
        && !/(?:^|\/)\.\.(?:\/|$)/.test(src)) return src;
    return '';
  };
  const safeGradient = value => /^linear-gradient\(135deg,#[0-9a-f]{6},#[0-9a-f]{6}\)$/i.test(String(value || '').trim())
    ? String(value).trim() : 'linear-gradient(135deg,#2E6B7A,#0B2447)';
  const websiteHref = value => {
    const raw = String(value || '').trim();
    if (!raw || raw.startsWith('//') || raw.includes('\\') || /^(?:javascript|vbscript|data):/i.test(raw)) return '';
    try {
      const url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
      return (url.protocol === 'https:' || url.protocol === 'http:') && url.hostname && !url.username && !url.password ? url.href : '';
    } catch (_) { return ''; }
  };
  const websiteHost = href => { try { return new URL(href).hostname.replace(/^www\./, ''); } catch (_) { return ''; } };
  const numberFa = value => {
    try { return new Intl.NumberFormat('fa-IR').format(Number(value) || 0); }
    catch (_) { return String(Number(value) || 0); }
  };
  const params = new URLSearchParams(root.location.search);
  const partnerId = params.get('id') || '';
  const container = $('#partnerPage');

  function publicData() {
    return root.NORA_PUBLIC || { partners: [], events: [] };
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
      return phone.length >= 6 && phone.length <= 20 ? `tel:${phone}` : '';
    }
    if (kind === 'tg' && !/^https?:/i.test(value)) {
      const user = value.replace(/^@/, '');
      return /^[A-Za-z0-9_]{5,32}$/.test(user) ? `https://t.me/${user}` : '';
    }
    if (kind === 'ig' && !/^https?:/i.test(value)) {
      const user = value.replace(/^@/, '');
      return /^[A-Za-z0-9._]{1,30}$/.test(user) ? `https://instagram.com/${user}` : '';
    }
    if (/^https?:\/\//i.test(value)) return websiteHref(value);
    if (kind === 'web' && /^[\w.-]+\.[A-Za-z]{2,}(?:\/.*)?$/.test(value)) return websiteHref(value);
    return '';
  }

  const CONTACT_LABEL = { tel: 'تلفن', mail: 'رایانامه', tg: 'تلگرام', ig: 'اینستاگرام', web: 'وب‌سایت' };
  function contactRows(partner) {
    const rows = Array.isArray(partner.links) ? partner.links : [];
    return rows.map(link => {
      const href = contactHref(link);
      const label = CONTACT_LABEL[link && link.k];
      if (!href || !label) return '';
      const shown = String(link.v || '').replace(/^(?:mailto|tel):/i, '');
      const external = /^https?:/i.test(href) ? ' target="_blank" rel="noopener noreferrer"' : '';
      return `<a class="partner-contact" href="${esc(href)}"${external} data-partner-contact="${esc(link.k)}"><span>${esc(label)}</span><b dir="ltr">${esc(shown)}</b></a>`;
    }).filter(Boolean).join('');
  }

  function eventCard(event) {
    const date = [event.when, event.time].filter(Boolean).join(' · ');
    const meta = [date, event.place, event.past ? 'برگزار شد' : ''].filter(Boolean).map(value => `<span>${esc(value)}</span>`).join('');
    return `<a class="partner-event" href="event.html?id=${encodeURIComponent(event.id)}">
      <span class="partner-event-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7.6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10.8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/><path d="M4 10.6h16M8.6 3.6v3.4M15.4 3.6v3.4"/>${event.past ? '<path d="M9 15.2l2 2 4-4"/>' : ''}</svg></span>
      <span class="partner-event-body"><b>${esc(event.t)}</b><small>${meta}</small></span>
      <span aria-hidden="true" class="partner-event-arrow">‹</span>
    </a>`;
  }

  function setMeta(title, description) {
    root.document.title = title;
    const pairs = [['meta[name="description"]', description], ['meta[property="og:title"]', title],
      ['meta[property="og:description"]', description]];
    pairs.forEach(([selector, value]) => { const tag = $(selector); if (tag) tag.content = value; });
  }

  function renderMissing(source) {
    const unavailable = source === 'unavailable';
    setMeta(unavailable ? 'محتوای زنده در دسترس نیست · نورا' : 'نهاد همکار پیدا نشد · نورا',
      'نهادهای همکار منتشرشدهٔ نورا و گروه فرهنگی خط زندگی.');
    container.innerHTML = `<section class="partner-not-found card paper" role="status">
      <h1>${unavailable ? 'محتوای زنده در دسترس نیست' : 'این نهاد همکار در دسترس نیست'}</h1>
      <p>${unavailable
        ? 'ارتباط با پایگاه عمومی سرور برقرار نشد؛ اطلاعات نهادهای همکار فقط از محتوای منتشرشدهٔ سرور خوانده می‌شود. کمی بعد دوباره تلاش کنید.'
        : 'این نهاد در فهرست عمومی منتشرشده پیدا نشد؛ ممکن است از محتوای عمومی برداشته شده یا نشانی آن نادرست باشد.'}</p>
      <a class="btn primary" href="home.html#partners">بازگشت به نهادهای همکار</a>
    </section>`;
  }

  function render(partner) {
    const data = publicData();
    const events = (Array.isArray(data.events) ? data.events : [])
      .filter(event => event && String(event.partnerId || '') === String(partner.id));
    const upcoming = events.filter(event => !event.past), past = events.filter(event => event.past);
    const logo = safeImage(partner.logo);
    const monogram = String(partner.mon || partner.n || '').trim().slice(0, 2) || '؟';
    const website = websiteHref(partner.href);
    const host = website ? websiteHost(website) : '';
    const contacts = contactRows(partner);
    const focus = (Array.isArray(partner.focus) ? partner.focus : []).map(item => String(item || '').trim()).filter(Boolean);
    const lead = String(partner.s || '').trim();
    const description = String(partner.d || '').trim();
    const sameText = lead && description && lead === description;

    const metaDescription = lead || description || (partner.type ? `${partner.n} — ${partner.type}؛ نهاد همکار نورا.` : `${partner.n}، نهاد همکار گروه فرهنگی خط زندگی در نورا.`);
    setMeta(`${partner.n} · نهادهای همکار نورا`, metaDescription.slice(0, 240));

    container.innerHTML = `<nav class="partner-breadcrumb" aria-label="مسیر صفحه">
        <a href="home.html">خانه</a><span aria-hidden="true">/</span>
        <a href="home.html#partners">نهادهای همکار</a>
        <span aria-hidden="true">/</span><span aria-current="page">${esc(partner.n)}</span>
      </nav>
      <article class="partner-profile card paper">
        <header class="partner-header">
          <div class="partner-logo${logo ? ' has-image' : ''}" style="--g:${safeGradient(partner.g)}" data-partner-logo>${logo
            ? `<img src="${esc(logo)}" alt="نشان ${esc(partner.n)}" decoding="async"/>`
            : `<span aria-hidden="true">${esc(monogram)}</span>`}</div>
          <div class="partner-heading"><span class="partner-kind">نهاد همکار</span>
            <h1>${esc(partner.n)}</h1>
            ${partner.type ? `<p>${esc(partner.type)}</p>` : ''}
          </div>
        </header>
        ${lead ? `<p class="partner-lead">${textWithBreaks(lead)}</p>` : ''}
        ${focus.length ? `<div class="partner-tags" aria-label="حوزه‌های همکاری">${focus.map(item => `<span class="tag">${esc(item)}</span>`).join('')}</div>` : ''}
        ${website ? `<div class="partner-actions"><a class="btn primary partner-site" data-partner-site href="${esc(website)}" target="_blank" rel="noopener noreferrer">وبگاه رسمی${host ? ` <b>${esc(host)}</b>` : ''}</a></div>` : ''}
        ${partner.collab || partner.since ? `<section class="partner-facts" aria-label="اطلاعات همکاری">
          ${partner.collab ? `<div><span>نوع همکاری</span><b>${esc(partner.collab)}</b></div>` : ''}
          ${partner.since ? `<div><span>همکاری از</span><b>${esc(partner.since)}</b></div>` : ''}
        </section>` : ''}
        ${description && !sameText ? `<section class="partner-section"><h2>معرفی</h2><p class="partner-desc">${textWithBreaks(description)}</p></section>` : ''}
        ${contacts ? `<section class="partner-section"><h2>راه‌های ارتباط رسمی</h2><div class="partner-contact-list">${contacts}</div></section>` : ''}
        ${upcoming.length ? `<section class="partner-section"><h2>رویدادهای پیش‌رو با این نهاد</h2>
          <div class="partner-event-list">${upcoming.map(eventCard).join('')}</div></section>` : ''}
        ${past.length ? `<section class="partner-section"><h2>رویدادهای برگزارشده با این نهاد (${numberFa(past.length)})</h2>
          <div class="partner-event-list">${past.map(eventCard).join('')}</div></section>` : ''}
        <nav class="partner-footer-nav" aria-label="ادامهٔ مسیر">
          <a class="btn quiet" href="home.html#partners">همهٔ نهادهای همکار</a>
          <a class="btn quiet" href="home.html">خانه</a>
        </nav>
      </article>`;

    const image = container.querySelector('[data-partner-logo] img');
    if (image) {
      image.addEventListener('error', () => {
        const frame = image.closest('[data-partner-logo]');
        if (!frame) return;
        frame.classList.remove('has-image');
        frame.innerHTML = `<span aria-hidden="true">${esc(monogram)}</span>`;
      }, { once: true });
    }
  }

  function start() {
    if (!container) return;
    const data = publicData();
    const partner = (Array.isArray(data.partners) ? data.partners : [])
      .find(item => item && String(item.id) === String(partnerId));
    if (!partner) { renderMissing(root.NORA_PUBLIC_SOURCE || 'unavailable'); return; }
    render(partner);
  }

  const ready = root.NORA_PUBLIC_READY && typeof root.NORA_PUBLIC_READY.then === 'function'
    ? root.NORA_PUBLIC_READY : Promise.resolve();
  ready.then(start).catch(start);
})(typeof window === 'undefined' ? globalThis : window);
