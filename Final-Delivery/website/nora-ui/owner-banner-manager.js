/* Owner-only editor for server-published home banners. No browser-storage fallback. */
(function (root) {
  'use strict';
  const TEST_FIXTURE_MODE = root.__NORA_TEST_FIXTURE_MODE__ === true;
  const $ = selector => root.document && root.document.querySelector(selector);
  const THEMES = {
    ocean: 'linear-gradient(135deg,#0A56B8,#0B2447)',
    teal: 'linear-gradient(135deg,#2E6B7A,#0B2447)',
    amber: 'linear-gradient(135deg,#7A5A2A,#0A3A82)',
    plum: 'linear-gradient(135deg,#684B86,#241D46)',
    night: 'linear-gradient(135deg,#3E5B84,#0B2447)'
  };
  const DEFAULT_SETTINGS = { enabled: true, auto_rotate: false, interval_seconds: 7, show_controls: true };
  const STATUS_LABELS = { draft: 'پیش‌نویس', published: 'منتشرشده', paused: 'متوقف' };
  const KINDS = ['notice', 'sponsored', 'partner'];
  const KIND_LABELS = { sponsored: 'تبلیغ', partner: 'حامی' };
  const state = { rows: [], settings: Object.assign({}, DEFAULT_SETTINGS), version: 0, selectedId: '',
    loaded: false, busy: false, dirty: false, serial: 0 };
  const clamp = (value, low, high) => Math.max(low, Math.min(high, Number.isFinite(+value) ? +value : low));
  const text = (value, maximum) => String(value == null ? '' : value).trim().slice(0, maximum);
  const escapeHtml = value => String(value == null ? '' : value).replace(/[&<>"']/g, char =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
  const isDataImage = value => /^data:image\/(?:png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+$/i.test(String(value || ''));
  const validRelative = value => {
    if (!value || value.startsWith('//') || value.includes('\\') || /[\u0000-\u001f]/.test(value)) return false;
    if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(value)) return false;
    try {
      const path = decodeURIComponent(value.split(/[?#]/, 1)[0]);
      return !/(?:^|\/)\.\.(?:\/|$)/.test(path)
        && /^[./A-Za-z0-9_~%?=&:+,#-]+$/.test(value);
    } catch (_) { return false; }
  };
  const safeActionUrl = value => {
    const raw = text(value, 2048);
    if (!raw) return true;
    if (/^https:\/\//i.test(raw)) {
      try { const url = new URL(raw); return !!url.hostname && !url.username && !url.password; }
      catch (_) { return false; }
    }
    return validRelative(raw);
  };
  const safeImageUrl = value => {
    const raw = text(value, 1_500_000);
    if (!raw) return true;
    if (isDataImage(raw)) return raw.length <= 1_500_000;
    if (/^https:\/\//i.test(raw)) {
      try { const url = new URL(raw); return !!url.hostname && !url.username && !url.password; }
      catch (_) { return false; }
    }
    return validRelative(raw);
  };
  const localDate = value => {
    if (!value) return '';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
  };
  const utcDate = value => {
    if (!value) return '';
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toISOString() : '';
  };
  function newId() {
    state.serial += 1;
    const token = root.crypto && typeof root.crypto.randomUUID === 'function'
      ? root.crypto.randomUUID().replace(/-/g, '') : Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
    return ('banner_' + token + '_' + state.serial).slice(0, 100);
  }
  function blankBanner(placeholder) {
    return { id: newId(), status: 'draft', active: true, order: state.rows.length,
      t: '', eyebrow: '', subtitle: '', s: '', img: '', imgAlt: '', href: '', primaryLabel: '',
      secondaryHref: '', secondaryLabel: '', theme: 'ocean', layout: 'cover', align: 'right', kind: 'notice',
      overlay: 48, focusX: 50, focusY: 50, startsAt: '', endsAt: '', _placeholder: !!placeholder };
  }
  function setStatus(message, kind) {
    const element = $('#ownerBannerState');
    if (!element) return;
    element.textContent = message;
    if (kind) element.dataset.state = kind;
    else delete element.dataset.state;
  }
  function clearServerState() {
    state.loaded = false; state.rows = []; state.selectedId = '';
    state.settings = Object.assign({}, DEFAULT_SETTINGS); state.version = 0; state.dirty = false;
  }
  function apiErrorMessage(error) {
    if (!error || error.status === 0 || error.code === 'server_unreachable') return 'به API همین سرور دسترسی نیست؛ هیچ تغییری ذخیره نشد.';
    if (error.status === 401) return 'ورود مالک برای مدیریت بنرها لازم است. پس از ورود، «تازه‌سازی» را بزنید.';
    if (error.status === 403) return 'دسترسی مالک یا بررسی مبدأ ناموفق بود؛ مجوزها و نشانی اصلی سایت را بررسی کنید.';
    if (error.status === 404) return 'API محتوای سرور در این میزبان در دسترس نیست؛ بنرها فقط با اتصال backend قابل مدیریت‌اند.';
    if (error.status === 409) return 'نسخهٔ سرور هم‌زمان تغییر کرده است؛ هیچ‌چیز بازنویسی نشد. تازه‌سازی کنید و تغییرها را دوباره اعمال کنید.';
    if (error.status === 413) return 'حجم تصویر یا محتوای بنر از سقف سرور بیشتر است؛ تصویر کوچک‌تری انتخاب کنید.';
    if (error.status === 422) return 'ساختار یکی از بنرها پذیرفته نشد؛ پیوندها، زمان‌بندی و فیلدهای اجباری را بررسی کنید.';
    if (error.status === 503) return 'پایگاه‌دادهٔ سرور آماده نیست؛ تغییری ذخیره نشد.';
    return `ذخیره انجام نشد (${error.code || 'خطای سرور'}).`;
  }
  function currentRow() { return state.rows.find(row => row.id === state.selectedId) || null; }
  function selectedLabel(row) {
    if (row._placeholder) return 'بنر تازه · ذخیره‌نشده';
    return row.t || 'بدون عنوان';
  }
  function renderList() {
    const list = $('#ownerBannerList');
    if (!list) return;
    list.innerHTML = state.rows.map(row => {
      const selected = row.id === state.selectedId;
      const status = row._placeholder ? 'هنوز ذخیره نشده' : (STATUS_LABELS[row.status] || STATUS_LABELS.draft);
      const stateText = row.active === false ? `${status} · نمایش خاموش` : status;
      return `<button class="obm-banner-item${selected ? ' is-selected' : ''}" type="button" role="tab"
        aria-selected="${selected ? 'true' : 'false'}" data-owner-banner-select="${escapeHtml(row.id)}">
        <b>${escapeHtml(selectedLabel(row))}</b><small>${escapeHtml(stateText)} · ترتیب ${escapeHtml(row.order)}</small>
      </button>`;
    }).join('');
    const version = $('#ownerBannerVersion');
    if (version) version.textContent = `نسخهٔ سرور: ${new Intl.NumberFormat('fa-IR').format(state.version)} · ${new Intl.NumberFormat('fa-IR').format(state.rows.filter(row => !row._placeholder).length)} بنر ذخیره‌شده`;
  }
  function field(name) {
    const form = $('#ownerBannerForm');
    return form && form.elements.namedItem(name);
  }
  function imageState(row) {
    const output = $('#ownerBannerImageState');
    if (!output) return;
    if (isDataImage(row && row.img)) output.textContent = 'تصویر درون‌متنی روی سرور نگه‌داری می‌شود؛ برای جایگزینی، فایل تازه انتخاب کنید.';
    else if (row && row.img) output.textContent = 'تصویر از نشانی امن بارگذاری می‌شود.';
    else output.textContent = 'تصویری انتخاب نشده است؛ PNG، JPG، WebP یا GIF تا ۱ مگابایت.';
  }
  function fillForm(row) {
    const form = $('#ownerBannerForm'), empty = $('#ownerBannerEmpty'), del = $('#ownerBannerDelete');
    if (!form || !empty) return;
    if (!row) {
      form.hidden = true; empty.hidden = false; empty.textContent = 'برای ویرایش، یک بنر را انتخاب کنید یا بنر تازه بسازید.';
      if (del) del.disabled = true;
      return;
    }
    empty.hidden = true; form.hidden = false;
    const values = {
      title: row.t, eyebrow: row.eyebrow || row.tag, subtitle: row.subtitle || row.m, body: row.s || row.body,
      imageUrl: isDataImage(row.img || row.image) ? '' : row.img || row.image,
      imageAlt: row.imgAlt || row.alt, primaryLabel: row.primaryLabel || row.primary_label,
      primaryHref: row.href || row.primary_href, secondaryLabel: row.secondaryLabel || row.secondary_label,
      secondaryHref: row.secondaryHref || row.secondary_href,
      layout: ['cover', 'split', 'text'].includes(row.layout) ? row.layout : 'cover',
      theme: Object.prototype.hasOwnProperty.call(THEMES, row.theme) ? row.theme : 'ocean',
      kind: KINDS.includes(row.kind) ? row.kind : 'notice',
      align: row.align === 'center' ? 'center' : 'right', status: STATUS_LABELS[row.status] ? row.status : 'draft',
      active: row.active !== false, order: clamp(row.order, 0, 1000),
      startsAt: localDate(row.startsAt || row.starts_at), endsAt: localDate(row.endsAt || row.ends_at),
      overlay: clamp(row.overlay, 0, 90), focusX: clamp(row.focusX, 0, 100), focusY: clamp(row.focusY, 0, 100),
      bannerEnabled: state.settings.enabled !== false, autoRotate: state.settings.auto_rotate === true,
      rotateInterval: String(clamp(state.settings.interval_seconds, 4, 20)),
      showControls: state.settings.show_controls !== false
    };
    Object.keys(values).forEach(name => {
      const input = field(name);
      if (!input) return;
      if (input.type === 'checkbox') input.checked = !!values[name];
      else input.value = String(values[name] == null ? '' : values[name]);
    });
    const file = $('#ownerBannerImageFile');
    if (file) file.value = '';
    imageState(row);
    if (del) del.disabled = !state.loaded || state.busy || !!row._placeholder;
    renderPreview(row);
    updateRangeLabels(form);
  }
  function updateRangeLabels(form) {
    if (!form) return;
    ['overlay', 'focusX', 'focusY'].forEach(name => {
      const input = field(name), output = form.querySelector(`[data-range-output="${name}"]`);
      if (input && output) output.textContent = `${new Intl.NumberFormat('fa-IR').format(input.value)}٪`;
    });
  }
  function renderPreview(row) {
    const host = $('#ownerBannerPreview');
    if (!host) return;
    host.replaceChildren();
    if (!row) return;
    const card = root.document.createElement('article');
    const layout = ['cover', 'split', 'text'].includes(row.layout) ? row.layout : 'cover';
    card.className = `obm-preview-card layout-${layout} align-${row.align === 'center' ? 'center' : 'right'}`;
    card.style.setProperty('--preview-bg', THEMES[row.theme] || THEMES.ocean);
    card.style.setProperty('--preview-overlay', String(clamp(row.overlay, 0, 90) / 100));
    card.style.setProperty('--preview-x', `${clamp(row.focusX, 0, 100)}%`);
    card.style.setProperty('--preview-y', `${clamp(row.focusY, 0, 100)}%`);
    const imageHost = root.document.createElement('div'); imageHost.className = 'obm-preview-image';
    const image = safeImageUrl(row.img) ? text(row.img, 1_500_000) : '';
    if (image) {
      const img = root.document.createElement('img'); img.src = image; img.alt = text(row.imgAlt, 240);
      img.loading = 'lazy'; img.decoding = 'async'; imageHost.appendChild(img);
    }
    card.appendChild(imageHost);
    if (KIND_LABELS[row.kind]) { const kindTag = root.document.createElement('span'); kindTag.className = 'obm-preview-label obm-preview-kind'; kindTag.textContent = KIND_LABELS[row.kind]; card.appendChild(kindTag); }
    if (row.eyebrow) { const tag = root.document.createElement('span'); tag.className = 'obm-preview-label'; tag.textContent = row.eyebrow; card.appendChild(tag); }
    const content = root.document.createElement('div'); content.className = 'obm-preview-content';
    const title = root.document.createElement('h4'); title.textContent = row.t || 'عنوان بنر'; content.appendChild(title);
    if (row.subtitle) { const subtitle = root.document.createElement('div'); subtitle.className = 'obm-preview-subtitle'; subtitle.textContent = row.subtitle; content.appendChild(subtitle); }
    if (row.s) { const body = root.document.createElement('div'); body.className = 'obm-preview-body'; body.textContent = row.s; content.appendChild(body); }
    const actions = root.document.createElement('div'); actions.className = 'obm-preview-actions';
    [[row.primaryLabel, row.href], [row.secondaryLabel, row.secondaryHref]].forEach(([label, href]) => {
      if (!label || !href) return;
      const button = root.document.createElement('span'); button.textContent = label; actions.appendChild(button);
    });
    if (actions.childNodes.length) content.appendChild(actions);
    card.appendChild(content); host.appendChild(card);
  }
  function readCurrentForm() {
    const row = currentRow();
    if (!row) return null;
    const value = name => field(name) ? field(name).value : '';
    const checked = name => !!(field(name) && field(name).checked);
    const typedImage = text(value('imageUrl'), 1500);
    const retainedInline = isDataImage(row.img) && !typedImage ? row.img : '';
    const next = Object.assign({}, row, {
      t: text(value('title'), 180), eyebrow: text(value('eyebrow'), 80), subtitle: text(value('subtitle'), 180),
      s: text(value('body'), 800), img: typedImage || retainedInline,
      imgAlt: text(value('imageAlt'), 240), primaryLabel: text(value('primaryLabel'), 60),
      href: text(value('primaryHref'), 2048), secondaryLabel: text(value('secondaryLabel'), 60),
      secondaryHref: text(value('secondaryHref'), 2048),
      layout: ['cover', 'split', 'text'].includes(value('layout')) ? value('layout') : 'cover',
      theme: Object.prototype.hasOwnProperty.call(THEMES, value('theme')) ? value('theme') : 'ocean',
      kind: KINDS.includes(value('kind')) ? value('kind') : 'notice',
      align: value('align') === 'center' ? 'center' : 'right',
      status: ['draft', 'published', 'paused'].includes(value('status')) ? value('status') : 'draft',
      active: checked('active'), order: clamp(value('order'), 0, 1000),
      overlay: clamp(value('overlay'), 0, 90), focusX: clamp(value('focusX'), 0, 100), focusY: clamp(value('focusY'), 0, 100),
      startsAt: utcDate(value('startsAt')), endsAt: utcDate(value('endsAt'))
    });
    const hasContent = !!(next.t || next.eyebrow || next.subtitle || next.s || next.img || next.href
      || next.primaryLabel || next.secondaryHref || next.secondaryLabel);
    if (hasContent) delete next._placeholder;
    state.settings = {
      enabled: checked('bannerEnabled'), auto_rotate: checked('autoRotate'),
      interval_seconds: clamp(value('rotateInterval'), 4, 20), show_controls: checked('showControls')
    };
    state.rows = state.rows.map(item => item.id === next.id ? next : item);
    return next;
  }
  function syncAndRender() {
    const row = readCurrentForm();
    if (row) { renderList(); renderPreview(row); imageState(row); }
    state.dirty = true;
    updateRangeLabels($('#ownerBannerForm'));
    setStatus('تغییرها فقط در این ویرایشگرند؛ برای ذخیره روی سرور دکمهٔ «ذخیرهٔ تنظیمات بنر» را بزنید.');
  }
  function render() {
    renderList();
    fillForm(currentRow());
    const form = $('#ownerBannerForm');
    if (form) Array.from(form.elements).forEach(input => { input.disabled = !state.loaded || state.busy; });
    const newButton = $('#ownerBannerNew'), reloadButton = $('#ownerBannerReload'), saveButton = $('#ownerBannerSave');
    if (newButton) newButton.disabled = !state.loaded || state.busy;
    if (reloadButton) { reloadButton.disabled = state.busy; reloadButton.setAttribute('aria-busy', state.busy ? 'true' : 'false'); }
    if (saveButton) saveButton.disabled = !state.loaded || state.busy;
    const del = $('#ownerBannerDelete');
    if (del) del.disabled = !state.loaded || state.busy || !currentRow() || !!currentRow()._placeholder;
  }
  function normalizedRows() {
    return state.rows.filter(row => !row._placeholder).map(row => ({
      id: text(row.id, 100), status: row.status, active: row.active !== false,
      order: Math.round(clamp(row.order, 0, 1000)), t: text(row.t, 180), eyebrow: text(row.eyebrow, 80),
      subtitle: text(row.subtitle, 180), s: text(row.s, 800), img: text(row.img, 1_500_000),
      imgAlt: text(row.imgAlt, 240), href: text(row.href, 2048), primaryLabel: text(row.primaryLabel, 60),
      secondaryHref: text(row.secondaryHref, 2048), secondaryLabel: text(row.secondaryLabel, 60),
      theme: row.theme, layout: row.layout, align: row.align, kind: KINDS.includes(row.kind) ? row.kind : 'notice',
      overlay: Math.round(clamp(row.overlay, 0, 90)),
      focusX: Math.round(clamp(row.focusX, 0, 100)), focusY: Math.round(clamp(row.focusY, 0, 100)),
      startsAt: row.startsAt || '', endsAt: row.endsAt || ''
    }));
  }
  function validate() {
    const rows = normalizedRows();
    if (rows.length > 100) return 'حداکثر ۱۰۰ بنر می‌توان ذخیره کرد.';
    const ids = new Set();
    for (const row of rows) {
      if (!/^[A-Za-z0-9_-]{1,100}$/.test(row.id) || ids.has(row.id)) return 'شناسهٔ یکی از بنرها معتبر یا یکتا نیست.';
      ids.add(row.id);
      if (!row.t) return 'برای هر بنر ذخیره‌شده، عنوان اصلی لازم است.';
      if (!['draft', 'published', 'paused'].includes(row.status)) return 'وضعیت انتشار یکی از بنرها معتبر نیست.';
      if (!['cover', 'split', 'text'].includes(row.layout) || !Object.prototype.hasOwnProperty.call(THEMES, row.theme)
          || !['right', 'center'].includes(row.align)) return 'چیدمان یا تم رنگی یکی از بنرها معتبر نیست.';
      if (!safeImageUrl(row.img)) return 'نشانی تصویر باید HTTPS یا مسیر امن همین سایت باشد.';
      if (!safeActionUrl(row.href) || !safeActionUrl(row.secondaryHref)) return 'پیوند دکمه باید HTTPS یا مسیر امن همین سایت باشد.';
      if (!!row.href !== !!row.primaryLabel) return 'برای دکمهٔ اصلی، متن و پیوند را هر دو وارد کنید یا هر دو را خالی بگذارید.';
      if (!!row.secondaryHref !== !!row.secondaryLabel) return 'برای دکمهٔ دوم، متن و پیوند را هر دو وارد کنید یا هر دو را خالی بگذارید.';
      if ((row.startsAt && !utcDate(row.startsAt)) || (row.endsAt && !utcDate(row.endsAt))) return 'زمان شروع یا پایان نمایش معتبر نیست.';
      if (row.startsAt && row.endsAt && Date.parse(row.startsAt) > Date.parse(row.endsAt)) return 'زمان پایان باید بعد از زمان شروع باشد.';
    }
    if (![4, 5, 6, 7, 8, 9, 10, 12, 15, 20].includes(+state.settings.interval_seconds)) return 'فاصلهٔ چرخش خودکار معتبر نیست.';
    return '';
  }
  async function reload() {
    if (state.busy) return false;
    if (state.dirty && typeof root.confirm === 'function'
        && !root.confirm('تغییرهای ذخیره‌نشده کنار گذاشته می‌شوند و نسخهٔ تازهٔ سرور بارگذاری می‌شود. ادامه می‌دهید؟')) return false;
    const api = root.NORA_SERVER_API;
    if (!api || typeof api.me !== 'function' || typeof api.getOwnerSiteContent !== 'function') {
      clearServerState(); render();
      setStatus('API مالک در این صفحه بارگذاری نشده است؛ هیچ دادهٔ محلی جایگزین منبع سرور نمی‌شود.', 'error');
      return false;
    }
    state.busy = true; render(); setStatus('در حال بررسی مجوز مالک و دریافت نسخهٔ سرور…');
    try {
      const identity = await api.me();
      if (!identity || identity.authenticated !== true || identity.role !== 'owner') {
        throw { status: 403, code: 'owner_role_required' };
      }
      const result = await api.getOwnerSiteContent();
      const content = result && result.content && typeof result.content === 'object' ? result.content : {};
      state.version = Number.isInteger(+result.version) && +result.version >= 0 ? +result.version : 0;
      state.rows = Array.isArray(content.banners) ? content.banners.map((row, index) => Object.assign({}, row, {
        id: /^[A-Za-z0-9_-]{1,100}$/.test(String(row && row.id || '')) ? String(row.id) : newId(),
        status: ['draft', 'published', 'paused'].includes(row && row.status) ? row.status : 'draft',
        active: !row || row.active !== false, order: clamp(row && row.order != null ? row.order : index, 0, 1000),
        theme: Object.prototype.hasOwnProperty.call(THEMES, row && row.theme) ? row.theme : 'ocean',
        layout: ['cover', 'split', 'text'].includes(row && row.layout) ? row.layout : 'cover',
        align: row && row.align === 'center' ? 'center' : 'right', kind: KINDS.includes(row && row.kind) ? row.kind : 'notice',
        overlay: clamp(row && row.overlay, 0, 90), focusX: clamp(row && row.focusX, 0, 100),
        focusY: clamp(row && row.focusY, 0, 100), _placeholder: false
      })) : [];
      state.settings = Object.assign({}, DEFAULT_SETTINGS, content.banner_settings || {});
      state.settings.enabled = state.settings.enabled !== false;
      state.settings.auto_rotate = state.settings.auto_rotate === true;
      state.settings.interval_seconds = Math.round(clamp(state.settings.interval_seconds, 4, 20));
      state.settings.show_controls = state.settings.show_controls !== false;
      if (!state.rows.length) state.rows.push(blankBanner(true));
      state.selectedId = state.rows[0].id;
      state.loaded = true; state.dirty = false;
      setStatus(state.rows.some(row => !row._placeholder)
        ? 'بنرهای عمومی، پیش‌نویس‌ها و تنظیمات چرخش از سرور بارگذاری شدند.'
        : 'هنوز بنری ذخیره نشده است؛ محتوای تازه پس از ذخیره و انتشار در سایت دیده می‌شود.', 'success');
      return true;
    } catch (error) {
      clearServerState();
      setStatus(apiErrorMessage(error), 'error');
      return false;
    } finally {
      state.busy = false; render();
    }
  }
  async function save(event) {
    if (event) event.preventDefault();
    if (!state.loaded || state.busy) return false;
    readCurrentForm();
    const issue = validate();
    if (issue) { setStatus(issue, 'error'); return false; }
    const rows = normalizedRows();
    const activePublished = rows.some(row => row.status === 'published' && row.active)
      && state.settings.enabled;
    const message = rows.length
      ? `تنظیمات و ${new Intl.NumberFormat('fa-IR').format(rows.length)} بنر روی سرور ذخیره می‌شود${activePublished ? '؛ بنرهای منتشرشدهٔ فعال در صفحهٔ خانه نمایش داده می‌شوند' : ''}. ادامه می‌دهید؟`
      : 'همهٔ بنرهای ذخیره‌شده از نسخهٔ عمومی برداشته می‌شوند و تنظیمات ذخیره می‌شود. ادامه می‌دهید؟';
    if (typeof root.confirm === 'function' && !root.confirm(message)) return false;
    const api = root.NORA_SERVER_API;
    if (!api || typeof api.me !== 'function' || typeof api.updateSiteContent !== 'function') {
      setStatus('API ذخیرهٔ مالک در این صفحه بارگذاری نشده است؛ هیچ تغییری ذخیره نشد.', 'error');
      return false;
    }
    state.busy = true; render(); setStatus('در حال بررسی نسخه و ذخیرهٔ بنرها در سرور…');
    try {
      const identity = await api.me();
      if (!identity || identity.authenticated !== true || identity.role !== 'owner') {
        throw { status: 403, code: 'owner_role_required' };
      }
      const result = await api.updateSiteContent({ banners: rows, banner_settings: {
        enabled: state.settings.enabled !== false,
        auto_rotate: state.settings.auto_rotate === true,
        interval_seconds: Math.round(clamp(state.settings.interval_seconds, 4, 20)),
        show_controls: state.settings.show_controls !== false
      } }, state.version);
      state.version = Number.isInteger(+result.version) ? +result.version : state.version + 1;
      const content = result && result.content || {};
      state.rows = Array.isArray(content.banners) ? content.banners.map(row => Object.assign({}, row, { _placeholder: false })) : rows;
      state.settings = Object.assign({}, state.settings, content.banner_settings || {});
      if (!state.rows.length) state.rows.push(blankBanner(true));
      state.selectedId = state.rows.some(row => row.id === state.selectedId) ? state.selectedId : state.rows[0].id;
      state.dirty = false;
      setStatus(`بنرها و تنظیمات در نسخهٔ ${new Intl.NumberFormat('fa-IR').format(state.version)} ذخیره شدند.`, 'success');
      const ui = root.NORA_UI || {};
      if (typeof ui.toast === 'function') ui.toast('تنظیمات بنر در سرور ذخیره شد');
      return true;
    } catch (error) {
      setStatus(apiErrorMessage(error), 'error');
      return false;
    } finally { state.busy = false; render(); }
  }
  function bind() {
    const panel = $('#ownerBannerManager'), form = $('#ownerBannerForm');
    if (!panel || !form) return;
    form.addEventListener('input', event => {
      if (event.target && event.target.id === 'ownerBannerImageFile') return;
      syncAndRender();
    });
    form.addEventListener('change', event => {
      if (event.target && event.target.name && ['layout', 'theme', 'align', 'kind', 'status', 'active', 'bannerEnabled', 'autoRotate', 'rotateInterval', 'showControls'].includes(event.target.name)) syncAndRender();
    });
    form.addEventListener('submit', save);
    $('#ownerBannerReload').addEventListener('click', () => reload());
    $('#ownerBannerNew').addEventListener('click', () => {
      readCurrentForm();
      const row = blankBanner(false);
      state.rows.push(row); state.selectedId = row.id; state.dirty = true;
      render(); setStatus('بنر تازه در ویرایشگر ساخته شد؛ برای ذخیره در سرور، عنوان را کامل کنید و ذخیره را بزنید.');
    });
    $('#ownerBannerDelete').addEventListener('click', () => {
      const row = currentRow(); if (!row || row._placeholder || state.busy) return;
      const name = row.t || 'بدون عنوان';
      if (typeof root.confirm === 'function' && !root.confirm(`«${name}» از فهرست ویرایشگر برداشته می‌شود. برای اعمال نهایی، تغییرها را ذخیره کنید. ادامه می‌دهید؟`)) return;
      state.rows = state.rows.filter(item => item.id !== row.id);
      if (!state.rows.length) state.rows.push(blankBanner(true));
      state.selectedId = state.rows[0].id; state.dirty = true; render();
      setStatus('بنر از فهرست ویرایشگر برداشته شد؛ هنوز روی سرور تغییری نکرده است. برای اعمال، ذخیره را بزنید.');
    });
    $('#ownerBannerCancel').addEventListener('click', () => reload());
    $('#ownerBannerList').addEventListener('click', event => {
      const button = event.target.closest('[data-owner-banner-select]');
      if (!button || !state.rows.some(row => row.id === button.dataset.ownerBannerSelect)) return;
      readCurrentForm(); state.selectedId = button.dataset.ownerBannerSelect; render();
    });
    const urlInput = field('imageUrl');
    if (urlInput) urlInput.addEventListener('input', () => {
      const row = readCurrentForm(); if (row) { renderPreview(row); imageState(row); }
    });
    const removeImage = $('#ownerBannerRemoveImage');
    if (removeImage) removeImage.addEventListener('click', () => {
      const row = currentRow(); if (!row) return;
      row.img = ''; if (urlInput) urlInput.value = '';
      syncAndRender(); setStatus('تصویر از ویرایشگر برداشته شد؛ برای اعمال روی سایت، ذخیره را بزنید.');
    });
    const fileInput = $('#ownerBannerImageFile');
    if (fileInput) fileInput.addEventListener('change', () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (!/^image\/(?:png|jpeg|webp|gif)$/i.test(file.type) || file.size > 1_000_000) {
        fileInput.value = ''; setStatus('فقط تصویر PNG، JPG، WebP یا GIF تا ۱ مگابایت پذیرفته می‌شود.', 'error'); return;
      }
      const rowId = state.selectedId, reader = new FileReader();
      reader.onload = () => {
        const row = state.rows.find(item => item.id === rowId);
        if (!row || !isDataImage(reader.result) || String(reader.result).length > 1_500_000) {
          setStatus('خواندن تصویر کامل نشد؛ تصویر کوچک‌تری انتخاب کنید.', 'error'); return;
        }
        row.img = String(reader.result); delete row._placeholder;
        if (urlInput && row.id === state.selectedId) urlInput.value = '';
        state.dirty = true; render();
        setStatus('تصویر در ویرایشگر آماده است؛ پس از ذخیره، در سرور نگه‌داری می‌شود.');
      };
      reader.onerror = () => setStatus('خواندن تصویر انجام نشد؛ فایل دیگری انتخاب کنید.', 'error');
      reader.readAsDataURL(file);
    });
  }
  function start() {
    if (TEST_FIXTURE_MODE) return;
    if (!$('#ownerBannerManager')) return;
    bind();
    render();
    reload();
  }
  root.NORA_OWNER_BANNER_MANAGER = Object.freeze({ reload, save, state });
  if (root.document) {
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start, { once: true });
    else start();
  }
})(typeof window === 'undefined' ? globalThis : window);
