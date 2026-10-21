/* Public pages use server-published records. Local panel fixtures are available
   only when a test harness explicitly enables fixture mode. */
(function (root) {
  'use strict';

  const N = root.NORA || (root.NORA = {});
  const UI = root.NORA_UI || {};
  const TEST_FIXTURE_MODE = root.__NORA_TEST_FIXTURE_MODE__ === true;
  const CONTENT_URL = '/api/public/site-content';
  const CONTENT_KEYS = ['events', 'people', 'articles', 'partners', 'banners', 'cooperation', 'library'];
  const asList = value => Array.isArray(value) ? value : [];
  const readJson = (key, fallback) => {
    try {
      const value = JSON.parse(root.localStorage.getItem(key) || 'null');
      return value == null ? fallback : value;
    } catch (_) { return fallback; }
  };
  const text = (value, max = 4000) => String(value == null ? '' : value).trim().slice(0, max);
  const listField = value => asList(value).map(item => text(item, 160)).filter(Boolean).slice(0, 40);
  const publicPath = value => {
    const path = text(value, 2048);
    if (!path || /^(?:javascript|vbscript):/i.test(path)) return '';
    if (/^(?:https?:|mailto:|tel:)/i.test(path) || /^data:image\/(?:png|jpeg|webp|gif);base64,/i.test(path)) return path;
    if (/^[./A-Za-z0-9_~%-][A-Za-z0-9_./~%-]*$/.test(path) && !/(?:^|\/)\.\.(?:\/|$)/.test(path)) return path;
    return '';
  };
  const bannerLink = value => {
    const path = text(value, 2048);
    if (!path || path.includes('\\') || /[\u0000-\u001f]/.test(path) || path.startsWith('//')) return '';
    if (/^https:\/\//i.test(path)) {
      try { const url = new URL(path); return url.hostname && !url.username && !url.password ? path : ''; }
      catch (_) { return ''; }
    }
    if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(path)) return '';
    try {
      const url = new URL(path, 'https://nora.invalid/');
      const relativePath = path.split(/[?#]/, 1)[0];
      const decodedPath = decodeURIComponent(relativePath);
      if (url.origin !== 'https://nora.invalid' || /(?:^|\/)\.\.(?:\/|$)/.test(decodedPath)) return '';
      return path;
    } catch (_) { return ''; }
  };
  const publicMediaPath = value => {
    const path = text(value, 1500000);
    if (/^data:(?:image\/(?:png|jpeg|webp|gif)|application\/(?:pdf|zip|x-zip-compressed|octet-stream|epub[+]zip|vnd[.]openxmlformats-officedocument[.](?:wordprocessingml[.]document|presentationml[.]presentation)|vnd[.]ms-powerpoint)|audio\/(?:mpeg|mp4|ogg|wav|webm)|video\/(?:mp4|webm|ogg));base64,[A-Za-z0-9+/=]+$/i.test(path)) return path;
    return publicPath(path);
  };
  const deliveryCode = value => /^[0-9a-f]{32}$/i.test(String(value || '')) ? String(value).toLowerCase() : '';
  /* ساعت مرجع: اختلاف ساعت سرور با مرورگر؛ تا پاسخ سرور نرسد صفر است */
  const serverNow = () => Date.now() + ((root.NORA_SERVER_CLOCK && Number.isFinite(root.NORA_SERVER_CLOCK.offsetMs)) ? root.NORA_SERVER_CLOCK.offsetMs : 0);
  const rememberServerClock = value => {
    const ms = Date.parse(String(value || ''));
    if (!Number.isFinite(ms)) return;
    root.NORA_SERVER_CLOCK = { serverTime: new Date(ms).toISOString(), offsetMs: ms - Date.now(), receivedAt: Date.now() };
  };
  const publicBotUrl = value => { const url = text(value, 256); return /^https:\/\/ble[.]ir\/[A-Za-z0-9_]{3,64}$/i.test(url) ? url : ''; };
  const fileMedia = item => {
    const kind = text(item && (item.k || item.kind), 24).toLowerCase();
    const mime = text(item && (item.mime || item.content_type), 120).toLowerCase();
    const name = text(item && (item.file_name || item.t || item.n || item.url || item.src), 500).toLowerCase();
    const playable = ['audio', 'video', 'aud', 'vid'].includes(kind)
      || mime.startsWith('audio/') || mime.startsWith('video/');
    const file = ['image', 'pdf', 'slide', 'file', 'document'].includes(kind)
      || mime.startsWith('application/') || mime.startsWith('image/')
      || /[.](pdf|zip|epub|docx|pptx|ppt|jpe?g|png|webp)(?:[?#]|$)/i.test(name);
    return file && !playable;
  };

  function localSnapshot() {
    const panelPeople = readJson('nora-people', null);
    const localPartners = readJson('nora-partners', null);
    const panelArticles = typeof UI.postsFeed === 'function' ? UI.postsFeed() : [];
    const articles = asList(panelArticles).length ? panelArticles : asList(N.ARTICLES);
    const panelEvents = typeof UI.pubEvents === 'function' ? UI.pubEvents() : [];
    const events = asList(panelEvents).length ? panelEvents : asList(N.EVENTS).map(event => Object.assign({}, event, { past: false }))
      .concat(asList(N.PAST).map(event => Object.assign({}, event, { past: true })));
    const cooperationId = text(readJson('nora-cooperation-form-id', ''), 120);
    const cooperation = /^[A-Za-z0-9_-]{1,120}$/.test(cooperationId) ? [{ formId: cooperationId }] : [];
    return {
      events: asList(events),
      people: panelPeople && Array.isArray(panelPeople.list) ? panelPeople.list : [],
      articles: asList(articles),
      partners: localPartners && Array.isArray(localPartners.list)
        ? localPartners.list
        : asList(localPartners),
      banners: asList(readJson('nora-public-banners', [])),
      library: asList(readJson('nora-clublib', [])),
      cooperation
    };
  }

  function normalizePerson(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)
        || record.hidden === true || record.pub === false || record.status === 'draft') return null;
    const id = text(record.id, 80);
    const name = text(record.n || record.name, 160);
    if (!id || !name) return null;
    return Object.assign({}, record, {
      id,
      n: name,
      ini: text(record.ini || name.slice(0, 1), 8),
      r: text(record.r || record.role, 240),
      role2: text(record.role2, 240),
      kind: record.kind === 'staff' ? 'staff' : 'teacher',
      bio: text(record.bio, 8000),
      quote: text(record.quote, 1200),
      where: text(record.where, 240),
      yrs: text(record.yrs, 120),
      courses: text(record.courses, 80),
      tag: text(record.tag, 80),
      exp: listField(record.exp),
      links: asList(record.links).slice(0, 12).map(link => ({
        k: text(link && link.k, 24), v: text(link && link.v, 300)
      })).filter(link => link.v),
      photo: publicPath(record.photo),
      g: text(record.g, 240),
      form: text(record.form, 120),
      formTxt: text(record.formTxt, 160)
    });
  }

  function normalizeEvent(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)) return null;
    const id = text(record.id, 100);
    const title = text(record.t || record.n || record.name, 240);
    if (!id || !title) return null;
    const privacy = text(record.privacy || 'public', 20).toLowerCase();
    if (record.hidden === true || record.pub === false || record.status === 'draft' || privacy !== 'public') return null;
    const forms = asList(record.forms).slice(0, 20).map(form => ({
      id: text(form && form.id, 120),
      need: text(form && form.need, 24),
      n: text(form && (form.n || form.name), 160),
      money: Number.isFinite(+((form || {}).money)) ? +form.money : 0,
      link: text(form && form.link, 300)
    })).filter(form => form.id);
    const parts = asList(record.parts || record.agenda || record.sess).slice(0, 80).map(part => {
      if (typeof part === 'string') return { title: text(part, 240) };
      return {
        title: text(part && (part.title || part.t || part.n), 240),
        date: text(part && (part.date || part.d), 80),
        time: text(part && (part.time || part.t), 80),
        to: text(part && part.to, 80),
        description: text(part && (part.description || part.d), 1200)
      };
    }).filter(part => part.title || part.date || part.time || part.description);
    const past = record.past === true || record.pubPast === true || record.state === 'past';
    const media = (past ? asList(record.media) : []).slice(0, 100).map(item => {
      const file = fileMedia(item || {});
      const code = deliveryCode(item && item.delivery_id);
      const row = {
        id: text(item && item.id, 100),
        k: text(item && (item.k || item.kind), 24),
        t: text(item && (item.t || item.n), 240),
        d: text(item && (item.d || item.at), 240),
        s: text(item && item.s, 80),
        mime: text(item && (item.mime || item.content_type), 120),
        file_name: text(item && item.file_name, 180),
        content_size: Number.isFinite(+(item || {}).content_size) ? Math.max(0, +(item || {}).content_size) : 0,
        external: !!(item && item.external)
      };
      if (file) {
        row.src = '';
        row.url = '';
        row.delivery_id = code;
        row.available = !!(code && item && item.available === true);
      } else {
        row.src = publicMediaPath(item && item.src);
        row.url = publicPath(item && item.url);
      }
      return row;
    }).filter(item => item.t || item.src || item.url || item.delivery_id);
    const registrationRaw = record.registration && typeof record.registration === 'object' ? record.registration : {};
    const REG_STATES = ['open', 'not_started', 'full', 'closed', 'ended', 'cancelled', 'none'];
    const LIFECYCLES = ['scheduled', 'cancelled', 'postponed'];
    const isoText = value => { const raw = text(value, 40); return raw && Number.isFinite(Date.parse(raw)) ? raw : ''; };
    const lifecycle = LIFECYCLES.includes(record.lifecycle) ? record.lifecycle : 'scheduled';
    /* وضعیت ثبت‌نام فقط از سرور می‌آید؛ اگر سرور قدیمی باشد و چیزی نفرستد، «نامشخص» می‌ماند و شمارشگری ساخته نمی‌شود */
    const registration = REG_STATES.includes(registrationRaw.state) ? {
      state: registrationRaw.state,
      reason: text(registrationRaw.reason, 24),
      lifecycle: LIFECYCLES.includes(registrationRaw.lifecycle) ? registrationRaw.lifecycle : lifecycle,
      opensAt: isoText(registrationRaw.opensAt),
      closesAt: isoText(registrationRaw.closesAt),
      startsAt: isoText(registrationRaw.startsAt),
      endsAt: isoText(registrationRaw.endsAt),
      countdownTo: isoText(registrationRaw.countdownTo),
      startsIn: isoText(registrationRaw.startsIn)
    } : null;
    const normalized = Object.assign({}, record, {
      id,
      t: title,
      kind: text(record.kind || 'رویداد', 80),
      d: text(record.d || record.about || record.description || record.rep, 10000),
      when: text(record.when || record.d, 120),
      on: text(record.on, 40),
      time: text(record.time, 120),
      place: text(record.place, 240),
      mode: text(record.mode, 80),
      poster: publicPath(record.poster),
      posterUp: publicPath(record.posterUp),
      partnerId: text(record.partnerId, 100),
      partnerName: text(record.partnerName, 180),
      tchr: text(record.tchr, 100),
      tags: listField(record.tags),
      parts,
      forms,
      price: Number.isFinite(+record.price) && +record.price >= 0 ? +record.price : 0,
      cap: Number.isFinite(+record.cap) && +record.cap >= 0 ? +record.cap : 0,
      past,
      media,
      cert: record.cert === true,
      certMin: Number.isFinite(+record.certMin) ? Math.max(0, Math.min(100, +record.certMin)) : 0,
      certNote: text(record.certNote, 1000),
      startsAt: isoText(record.startsAt),
      endsAt: isoText(record.endsAt),
      regOpensAt: isoText(record.regOpensAt),
      regClosesAt: isoText(record.regClosesAt),
      regMode: ['auto', 'closed', 'full'].includes(record.regMode) ? record.regMode : 'auto',
      lifecycle,
      conditions: text(record.conditions, 1000),
      registration,
      privacy
    });
    ['code', 'regs', 'reg', 'taken', 'spots', 'sold', 'attendees', 'registrants'].forEach(key => delete normalized[key]);
    return normalized;
  }

  function normalizeArticle(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)) return null;
    const id = text(record.id, 100), title = text(record.t || record.title, 240);
    if (!id || !title) return null;
    const blocks = asList(record.blocks).slice(0, 100).map(block => {
      if (typeof block === 'string') return text(block, 8000);
      if (!block || typeof block !== 'object') return '';
      if (block.ty === 'file') {
        const code = deliveryCode(block.delivery_id);
        return {
          ty: 'file', t: text(block.t || block.cap, 240), cap: text(block.cap, 500),
          file_name: text(block.file_name, 180), content_type: text(block.content_type, 120),
          content_size: Number.isFinite(+block.content_size) ? Math.max(0, +block.content_size) : 0,
          delivery_id: code, available: !!(code && block.available === true)
        };
      }
      const playerBlock = ['img', 'vid', 'aud', 'gal'].includes(block.ty);
      return Object.assign({}, block, {
        x: text(block.x || block.text || block.title, 8000),
        src: playerBlock ? publicMediaPath(block.src || block.url) : publicPath(block.src || block.url),
        up: playerBlock ? publicMediaPath(block.up) : publicPath(block.up)
      });
    }).filter(block => typeof block === 'string' ? block : (block.x || block.src || block.ty === 'file'));
    return Object.assign({}, record, {
      id, t: title,
      cat: text(record.cat || 'مطلب', 80),
      lead: text(record.lead, 1000),
      body: asList(record.body).map(item => text(item, 8000)).filter(Boolean).slice(0, 100),
      blocks,
      tags: listField(record.tags),
      cov: publicPath(record.cov),
      who: text(record.who, 160),
      tchr: text(record.tchr, 100)
    });
  }

  function normalizeLibrary(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)
        || record.hidden === true || record.pub === false || record.pub === 0 || record.status === 'draft') return null;
    const id = text(record.id || record.k, 100);
    const title = text(record.t || record.title || record.n, 240);
    if (!id || !title) return null;
    const kind = text(record.kind, 40);
    const audio = ['صدا', 'audio', 'پادکست'].includes(kind.toLowerCase());
    const code = deliveryCode(record.delivery_id);
    return {
      id, t: title, kind,
      by: text(record.by, 180), sub: text(record.sub, 240),
      file_name: text(record.file_name || record.fname, 180),
      content_type: text(record.content_type || record.mime, 120),
      content_size: Number.isFinite(+record.content_size) ? Math.max(0, +record.content_size) : 0,
      delivery_id: code, available: !!(code && record.available === true),
      src: audio ? publicMediaPath(record.src || record.file) : ''
    };
  }

  function normalizePartner(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)
        || record.hidden === true || record.pub === false || record.status === 'draft') return null;
    const id = text(record.id, 100), name = text(record.n || record.name, 180);
    if (!id || !name) return null;
    return Object.assign({}, record, {
      id, n: name,
      type: text(record.type, 160),
      s: text(record.s || record.summary, 600),
      collab: text(record.collab, 160),
      since: text(record.since, 80),
      focus: listField(record.focus).slice(0, 12),
      d: text(record.d || record.description, 4000),
      logo: publicPath(record.logo),
      href: publicPath(record.href || record.url),
      links: asList(record.links).slice(0, 12).map(link => ({
        k: text(link && link.k, 24), v: text(link && link.v, 300)
      })).filter(link => link.v),
      mon: text(record.mon, 8),
      g: text(record.g, 240)
    });
  }

  function normalizeBanner(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)
        || record.hidden === true || record.active === false
        || String(record.status || '').toLowerCase() !== 'published') return null;
    const title = text(record.t || record.title, 180);
    if (!title) return null;
    const startsAt = text(record.startsAt || record.starts_at, 40);
    const endsAt = text(record.endsAt || record.ends_at, 40);
    /* بازهٔ نمایش با ساعت سرور سنجیده می‌شود (public-data اختلاف را نگه می‌دارد)، نه ساعت مرورگر */
    const now = serverNow();
    const start = startsAt ? Date.parse(startsAt) : NaN;
    const end = endsAt ? Date.parse(endsAt) : NaN;
    if ((startsAt && !Number.isFinite(start)) || (endsAt && !Number.isFinite(end))
        || (Number.isFinite(start) && now < start) || (Number.isFinite(end) && now > end)
        || (Number.isFinite(start) && Number.isFinite(end) && start > end)) return null;
    const href = bannerLink(record.href || record.primary_href);
    const primaryLabel = text(record.primaryLabel || record.primary_label || (href ? 'جزئیات' : ''), 60);
    const secondaryHref = bannerLink(record.secondaryHref || record.secondary_href);
    const secondaryLabel = text(record.secondaryLabel || record.secondary_label, 60);
    const theme = ['ocean', 'teal', 'amber', 'plum', 'night'].includes(record.theme) ? record.theme : 'ocean';
    const layout = ['cover', 'split', 'text'].includes(record.layout) ? record.layout : 'cover';
    const align = ['right', 'center'].includes(record.align) ? record.align : 'right';
    // نوع بنر: «sponsored» و «partner» در خانه برچسب روشن «تبلیغ»/«حامی» می‌گیرند؛ هر مقدار دیگر اعلان عادی است.
    const kind = ['sponsored', 'partner'].includes(record.kind) ? record.kind : 'notice';
    const overlay = Number.isFinite(+record.overlay) ? Math.max(0, Math.min(90, Math.round(+record.overlay))) : 48;
    /* شمارشگر بنر: نوع و هدف فقط از سرور (رویداد یا کمپین)؛ پس از پایان، رفتار پیکربندی‌شده */
    const countdown = ['reg_close', 'reg_open', 'event_start', 'campaign_end'].includes(record.countdown) ? record.countdown : '';
    const countdownTo = text(record.countdownTo, 40);
    const countdownEnded = record.countdownEnded === true;
    const afterEnd = ['hide', 'message', 'details'].includes(record.afterEnd) ? record.afterEnd : 'hide';
    if (countdownEnded && afterEnd === 'hide') return null;
    const linked = record.event && typeof record.event === 'object' ? record.event : null;
    const event = linked && text(linked.id, 100) ? {
      id: text(linked.id, 100), t: text(linked.t, 240), when: text(linked.when, 120),
      state: text(linked.state, 24), lifecycle: text(linked.lifecycle, 24) || 'scheduled'
    } : null;
    return {
      id: text(record.id, 100), status: 'published', active: true,
      eventId: text(record.eventId, 100), event,
      countdown: countdown && (countdownEnded || Number.isFinite(Date.parse(countdownTo))) ? countdown : '',
      countdownTo: countdown && !countdownEnded && Number.isFinite(Date.parse(countdownTo)) ? countdownTo : '',
      countdownEnded: !!countdown && countdownEnded,
      afterEnd, afterEndText: text(record.afterEndText, 160),
      order: Number.isFinite(+record.order) ? Math.max(0, Math.min(1000, Math.round(+record.order))) : 0,
      t: title,
      tag: text(record.eyebrow || record.tag, 80),
      m: text(record.subtitle || record.m, 180),
      s: text(record.s || record.body || record.description, 800),
      img: publicMediaPath(record.img || record.image),
      imgAlt: text(record.imgAlt || record.alt, 240),
      href, primaryLabel: href && primaryLabel ? primaryLabel : '',
      secondaryHref, secondaryLabel: secondaryHref && secondaryLabel ? secondaryLabel : '',
      theme, layout, align, overlay, kind,
      focusX: Number.isFinite(+record.focusX) ? Math.max(0, Math.min(100, Math.round(+record.focusX))) : 50,
      focusY: Number.isFinite(+record.focusY) ? Math.max(0, Math.min(100, Math.round(+record.focusY))) : 50,
      startsAt, endsAt
    };
  }

  function normalizeBannerSettings(value) {
    const source = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    const interval = Number(source.interval_seconds);
    return {
      enabled: source.enabled !== false,
      auto_rotate: source.auto_rotate === true,
      interval_seconds: Number.isFinite(interval) ? Math.max(4, Math.min(20, Math.round(interval))) : 7,
      show_controls: source.show_controls !== false
    };
  }

  function normalizeCooperation(record) {
    if (!record || typeof record !== 'object' || Array.isArray(record)) return null;
    const formId = text(record.formId, 120);
    return /^[A-Za-z0-9_-]{1,120}$/.test(formId) ? { formId } : null;
  }

  function applySnapshot(snapshot, deliveryBotUrl) {
    const content = snapshot && typeof snapshot === 'object' ? snapshot : {};
    const botUrl = publicBotUrl(deliveryBotUrl || root.NORA_BALE_BOT_URL);
    const events = asList(content.events).map(normalizeEvent).filter(Boolean);
    const people = asList(content.people).map(normalizePerson).filter(Boolean);
    const articles = asList(content.articles).map(normalizeArticle).filter(Boolean);
    const partners = asList(content.partners).map(normalizePartner).filter(Boolean);
    const banners = asList(content.banners).map(normalizeBanner).filter(Boolean)
      .sort((a, b) => a.order - b.order || a.t.localeCompare(b.t, 'fa'));
    const bannerSettings = normalizeBannerSettings(content.banner_settings);
    const cooperation = asList(content.cooperation).slice(0, 1).map(normalizeCooperation).filter(Boolean);
    const library = asList(content.library).map(normalizeLibrary).filter(Boolean);
    N.EVENTS = events.filter(event => !event.past);
    N.PAST = events.filter(event => event.past);
    N.PEOPLE = people;
    N.ARTICLES = articles;
    N.PARTNERS = partners;
    N.BANNERS = banners;
    N.BANNER_SETTINGS = bannerSettings;
    N.COOPERATION = cooperation;
    N.LIBRARY = library;
    N.BALE_BOT_URL = botUrl;
    N.COOPERATION_FORM_ID = cooperation[0] ? cooperation[0].formId : '';
    N.STORIES = [];
    N.LIVE = [];
    N.ACT = { vals: [], months: [], sum: [], note: '' };
    N.VOICES = [];
    N.NOTICES = [];
    N.FAQ = [];
    N.CERTS = [];
    N.CLUB = null;
    N.TOTAL_MEDIA = N.PAST.reduce((count, event) => count + (Array.isArray(event.media) ? event.media.length : 0), 0);
    N.ARCHIVE = { hours: 0 };
    N.CATS = [...new Set(events.map(event => event.kind).filter(Boolean))].map(name => ({ n: name }));
    N.DAYS = [];
    N.QTAGS = [];
    N.TRUST = { row: [], short: {} };
    const quick = [
      { k: 'events', settingsKeys: ['events', 'past'], i: 'i-calendar', n: 'رویدادها و آرشیو', s: 'برنامه‌های پیش‌رو، برگزارشده و ثبت‌نام', href: 'events.html' },
      { k: 'articles', settingsKeys: ['club', 'articles'], i: 'i-book', n: 'مطالب و مطالعه', s: 'مطالب، رسانه و باشگاه کتاب‌خوانی', j: 'articles' },
      { k: 'people', settingsKeys: ['people', 'partners'], i: 'i-users', n: 'افراد و نهادها', s: 'اساتید، دست‌اندرکاران و همکاران', href: 'home.html#teachers' },
      { k: 'verify', settingsKeys: ['verify'], i: 'i-qr', n: 'استعلام گواهی', s: 'بررسی گواهی در سامانه', f: 'shVerify' },
      { k: 'support', settingsKeys: ['support'], i: 'i-headphone', n: 'پشتیبانی و راهنما', s: 'راهنما و مسیر پیگیری درخواست‌ها', href: 'support.html' }
    ];
    const menu = [
      { g: 'برنامه‌ها و رویدادها', i: 'i-calendar', rows: [
        { i: 'i-calendar', t: 'رویدادهای پیش‌رو', s: 'فهرست برنامه‌های منتشرشده', href: 'events.html?status=upcoming' },
        { i: 'i-archive', t: 'آرشیو رویدادها', s: 'برنامه‌های برگزارشده', href: 'events.html?status=past' },
        { i: 'i-play', t: 'همهٔ برنامه‌ها', s: 'رویدادها و برنامه‌های منتشرشده', href: 'events.html' },
        { i: 'i-book', t: 'باشگاه کتاب‌خوانی', s: 'دسترسی از بخش حساب من', href: 'account.html#book' },
        { i: 'i-ticket', t: 'ثبت‌نام در رویدادها', s: 'فرم هر برنامه از صفحهٔ همان رویداد باز می‌شود', href: 'events.html' }
      ] },
      { g: 'آموزش و محتوا', i: 'i-graduation', rows: [
        { i: 'i-article', t: 'مطالب و مقالات', s: 'مطالب منتشرشده', j: 'articles' },
        { i: 'i-play', t: 'رسانه و آرشیو برنامه‌ها', s: 'محتوای رویدادهای برگزارشده', href: 'events.html?status=past' },
        { i: 'i-list', t: 'فرم‌های من', s: 'فرم‌ها و پاسخ‌های حساب کاربری', href: 'account.html#forms' },
        { i: 'i-qr', t: 'استعلام گواهی', s: 'بررسی گواهی در سامانه', href: 'home.html#verify' }
      ] },
      { g: 'افراد و نهادها', i: 'i-users', rows: [
        { i: 'i-graduation', t: 'اساتید و مدرسان', s: 'پروفایل‌های منتشرشده', j: 'teachers' },
        { i: 'i-idcard', t: 'دست‌اندرکاران', s: 'پروفایل‌های منتشرشده', j: 'staff' },
        { i: 'i-handshake', t: 'نهادهای همکار', s: 'نهادهای منتشرشده', j: 'partners' },
      ] },
      { g: 'حساب من', i: 'i-idcard', rows: [
        { i: 'i-idcard', t: 'حساب من', s: 'ورود به صفحهٔ حساب کاربری', href: 'account.html' },
        { i: 'i-wallet', t: 'پرداخت‌ها و حساب مالی', s: 'بخش حساب من', href: 'account.html#pay' },
        { i: 'i-calendar', t: 'رویدادهای من', s: 'ثبت‌نام‌ها و برنامه‌های حساب کاربری', href: 'account.html#events' },
        { i: 'i-idcard', t: 'پروفایل من', s: 'اطلاعات و تنظیمات حساب کاربری', href: 'account.html#profile' }
      ] },
      { g: 'راهنما و آشنایی', i: 'i-headphone', rows: [
        { i: 'i-headphone', t: 'پشتیبانی و راهنما', s: 'راهنمای استفاده از سامانه', href: 'support.html' },
        { i: 'i-doc', t: 'قواعد و شرایط', s: 'راهنمای سامانه', href: 'support.html' },
        { i: 'i-list', t: 'فرم‌ها و پاسخ‌ها', s: 'دسترسی به فرم‌های حساب کاربری', href: 'account.html#forms' },
      ] }
    ];
    N.MENU = menu;
    N.QUICK = quick;
    root.NORA_PUBLIC = { events, people, articles, partners, banners, bannerSettings, cooperation, library, menu, quick, deliveryBotUrl: botUrl };

    return root.NORA_PUBLIC;
  }

  function showDelayedWarning() {
    if (!root.document || !root.document.body || root.document.getElementById('noraPublicLoadWarning')) return;
    const warning = root.document.createElement('div');
    warning.id = 'noraPublicLoadWarning';
    warning.setAttribute('role', 'status');
    warning.setAttribute('aria-live', 'polite');
    warning.style.cssText = 'position:fixed;z-index:9999;inset-block-start:12px;inset-inline:12px auto;max-width:520px;padding:12px 14px;border:1px solid var(--hairline,#ddd);border-radius:14px;background:var(--surface,#fff);color:var(--ink,#222);box-shadow:0 8px 28px rgba(0,0,0,.16);font:13px/1.8 system-ui,sans-serif';
    warning.innerHTML = '<span>دریافت محتوای منتشرشده بیش از ۱۰ ثانیه طول کشید؛ اتصال سرور را بررسی کنید.</span> <button type="button" style="margin-inline-start:8px" data-public-retry>تلاش دوباره</button>';
    warning.querySelector('[data-public-retry]').addEventListener('click', function () { root.location.reload(); });
    root.document.body.appendChild(warning);
  }

  const fixtureFallback = TEST_FIXTURE_MODE ? localSnapshot() : null;
  root.NORA_PUBLIC_READY = (async function () {
    let remote = null, deliveryBotUrl = '', timedOut = false, requestSucceeded = false;
    let controller = typeof root.AbortController === 'function' ? new root.AbortController() : null;
    const timeout = setTimeout(function () {
      timedOut = true;
      showDelayedWarning();
      if (controller) controller.abort();
    }, 10_000);
    try {
      const response = await root.fetch(CONTENT_URL, {
        credentials: 'same-origin', cache: 'no-store',
        ...(controller ? { signal: controller.signal } : {})
      });
      requestSucceeded = !!response.ok;
      if (response.ok) {
        const payload = await response.json();
        if (payload && payload.content && typeof payload.content === 'object' && !Array.isArray(payload.content)) {
          remote = payload.content;
          deliveryBotUrl = publicBotUrl(payload.delivery_bot_url);
          rememberServerClock(payload.server_time);
        }
      } else if (response.status === 404) {
        // سرور سالم است ولی مالک هنوز چیزی منتشر نکرده؛ این «خالی» است، نه «در دسترس نبودن».
        try {
          const payload = await response.json();
          if (payload && payload.detail === 'site_content_not_published') requestSucceeded = true;
        } catch (_) { /* 404 غیرمنتظره همچنان «در دسترس نیست» می‌ماند */ }
      }
    } catch (_) { /* Production stays empty when the server cannot provide public content. */ }
    finally { clearTimeout(timeout); }
    const selected = {};
    CONTENT_KEYS.forEach(key => {
      selected[key] = remote && Array.isArray(remote[key])
        ? remote[key]
        : TEST_FIXTURE_MODE && fixtureFallback ? fixtureFallback[key] : [];
    });
    selected.banner_settings = remote && remote.banner_settings ? remote.banner_settings : null;
    root.NORA_PUBLIC_SOURCE = remote ? 'server'
      : TEST_FIXTURE_MODE ? 'test-fixture' : requestSucceeded ? 'empty' : 'unavailable';
    if (remote && !timedOut) {
      const warning = root.document && root.document.getElementById('noraPublicLoadWarning');
      if (warning) warning.remove();
    }
    return applySnapshot(selected, deliveryBotUrl);
  })();
})(typeof window === 'undefined' ? globalThis : window);
