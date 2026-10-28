(function (root) {
  'use strict';
  const $ = selector => root.document.querySelector(selector);
  const TEST_FIXTURE_MODE = root.__NORA_TEST_FIXTURE_MODE__ === true;
  const KEY_MAP = {
    events: 'رویدادها', people: 'پروفایل‌ها', articles: 'مطالب',
    partners: 'نهادهای همکار', banners: 'بنرها', cooperation: 'فرم همکاری', library: 'کتابخانه'
  };
  const COOPERATION_STORAGE_KEY = 'nora-cooperation-form-id';
  const FORM_ID_RE = /^[A-Za-z0-9_-]{1,120}$/;
  const read = key => {
    try { return JSON.parse(root.localStorage.getItem(key) || 'null'); }
    catch (_) { return null; }
  };
  const cleanFormId = value => {
    const id = String(value == null ? '' : value).trim();
    return FORM_ID_RE.test(id) ? id : '';
  };
  let selectedCooperationId = cleanFormId(read(COOPERATION_STORAGE_KEY));
  let serverCooperationLoaded = false;
  function saveCooperationFormId(value) {
    selectedCooperationId = cleanFormId(value);
    try { root.localStorage.setItem(COOPERATION_STORAGE_KEY, JSON.stringify(selectedCooperationId)); }
    catch (_) { /* Cross-device publication remains authoritative. */ }
    return selectedCooperationId;
  }
  function cooperationFormId() {
    const select = $('#cooperationFormSelect');
    const value = select && select.dataset.ready === 'true'
      ? select.value
      : selectedCooperationId || read(COOPERATION_STORAGE_KEY);
    return cleanFormId(value);
  }
  const array = value => Array.isArray(value) ? value : [];
  const publishedEvents = () => {
    if (!TEST_FIXTURE_MODE) return [];
    const ui = root.NORA_UI || {};
    return (typeof ui.pubEvents === 'function' ? array(ui.pubEvents()) : [])
      .filter(item => item && item.privacy === 'public' && item.hidden !== true && item.status !== 'draft');
  };
  const publishedPeople = () => {
    if (!TEST_FIXTURE_MODE) return [];
    const value = read('nora-people');
    return array(value && Array.isArray(value.list) ? value.list : value);
      // Only the owner's explicitly published profile list is read.
  };
  const publishedArticles = () => {
    if (!TEST_FIXTURE_MODE) return [];
    const ui = root.NORA_UI || {};
    if (typeof ui.postsAll !== 'function') return [];
    return array(ui.postsAll()).filter(item => item && item.pub && !item.pend);
  };
  const publishedPartners = () => {
    if (!TEST_FIXTURE_MODE) return [];
    const value = read('nora-partners');
    const rows = array(value && Array.isArray(value.list) ? value.list : value);
    return rows.filter(item => item && item.hidden !== true && item.status !== 'draft');
  };
  const publishedBanners = () => TEST_FIXTURE_MODE
    ? array(read('nora-public-banners')).filter(item => item && item.hidden !== true && item.status !== 'draft') : [];
  const publishedLibrary = () => TEST_FIXTURE_MODE
    ? array(read('nora-clublib')).filter(item => item && item.pub !== 0 && item.hidden !== true && item.status !== 'draft') : [];
  const snapshot = () => {
    const formId = (TEST_FIXTURE_MODE||serverCooperationLoaded)?cooperationFormId():'';
    return {
      events: publishedEvents(), people: publishedPeople(), articles: publishedArticles(),
      partners: publishedPartners(), banners: publishedBanners(), library: publishedLibrary(),
      cooperation: formId ? [{ formId }] : []
    };
  };
  const selected = () => Array.from(root.document.querySelectorAll('[data-sync-category]:checked'))
    .map(input => input.dataset.syncCategory)
    .filter(key => Object.prototype.hasOwnProperty.call(KEY_MAP, key)
      && (TEST_FIXTURE_MODE || (serverCooperationLoaded && key === 'cooperation')));
  function setState(message, state) {
    const status = $('#siteContentSyncState');
    if (!status) return;
    status.textContent = message;
    if (state) status.dataset.state = state;
    else delete status.dataset.state;
  }

  function refreshCounts() {
    const content = snapshot();
    Object.keys(KEY_MAP).forEach(key => {
      const count = $(`[data-sync-count="${key}"]`);
      const checkbox = $(`[data-sync-category="${key}"]`);
      if (count) count.textContent = new Intl.NumberFormat('fa-IR').format(content[key].length);
      if (checkbox && !TEST_FIXTURE_MODE) {
        const enabled=key==='cooperation'&&serverCooperationLoaded;
        checkbox.disabled=!enabled;
        if(!enabled){checkbox.checked=false;checkbox.dataset.initialized='true';
          checkbox.title=key==='banners'
            ?'بنرهای خانه را از مدیر سروریِ همین بخش تنظیم کنید؛ همگام‌سازی محلی بنر خاموش است.'
            :key==='partners'
              ?'نهادهای همکار از کاشی «مدیران و اساتید ← نهادهای همکار» مستقیماً روی سرور ذخیره می‌شوند؛ همگام‌سازی محلی خاموش است.'
              :'برای جلوگیری از انتشار دادهٔ مرورگر، این دسته تا اتصال ویرایشگر سروری غیرفعال است.'}
      }
      if (checkbox && !checkbox.dataset.initialized) {
        checkbox.checked = content[key].length > 0;
        checkbox.dataset.initialized = 'true';
      }
    });
    return content;
  }

  function apiErrorMessage(error) {
    if (!error || error.code === 'server_unreachable' || error.status === 0)
      return 'به API همین سرور دسترسی نیست؛ محتوا در مرورگر دست‌نخورده ماند.';
    if (error.status === 401) return 'ورود مالک برای انتشار محتوای عمومی لازم است؛ وارد شوید.';
    if (error.status === 403) return 'بررسی مبدأ یا CSRF ناموفق بود؛ همین صفحه را از نشانی اصلی سایت باز کنید.';
    if (error.status === 404) return 'API انتشار محتوا روی این میزبان نصب نشده است؛ سرویس FastAPI و migration را بررسی کنید.';
    if (error.status === 409) return 'نسخهٔ سرور هم‌زمان تغییر کرده است؛ محتوا ارسال نشد. دوباره همگام‌سازی کنید.';
    if (error.status === 413) return 'حجم محتوای انتخاب‌شده از سقف سرور بیشتر است؛ عکس‌ها یا فایل‌های درون‌متنی را کوچک کنید.';
    if (error.status === 422) return 'ساختار بخشی از محتوای منتشرشده پذیرفته نشد؛ اطلاعات پنل را بررسی کنید.';
    if (error.status === 503) return 'پایگاه‌داده یا migration سرور آماده نیست؛ محتوای عمومی تغییر نکرد.';
    return `همگام‌سازی انجام نشد (${error.code || 'خطای سرور'}).`;
  }

  async function checkOwner() {
    const api = root.NORA_SERVER_API;
    if (!api) throw { status: 404, code: 'owner_api_unavailable' };
    return api.me();
  }

  function setCooperationFormOptions(items, currentId) {
    const select = $('#cooperationFormSelect');
    if (!select) return;
    serverCooperationLoaded = true;
    const forms = array(items).filter(item => item && item.status === 'published'
      && item.need === 'other' && cleanFormId(item.id));
    select.replaceChildren();
    const empty = root.document.createElement('option');
    empty.value = '';
    empty.textContent = 'فرمی انتخاب نشده';
    select.appendChild(empty);
    forms.forEach(form => {
      const option = root.document.createElement('option');
      option.value = cleanFormId(form.id);
      option.textContent = String(form.name || form.title || 'فرم بی‌نام').slice(0, 160);
      select.appendChild(option);
    });
    select.dataset.ready = 'true';
    select.disabled = false;
    const existing = cleanFormId(currentId);
    const found = forms.some(form => cleanFormId(form.id) === existing);
    select.value = found ? existing : '';
    saveCooperationFormId(select.value);
    const help = $('#cooperationFormHelp');
    if (help) help.textContent = existing && !found
      ? 'فرم قبلی دیگر منتشر نیست؛ آن را در فرم‌ساز منتشر کن و دوباره انتخابش کن.'
      : forms.length
        ? 'یک فرم منتشرشده انتخاب کن؛ برای ساخت یا انتشار، از فرم‌ساز استفاده کن.'
        : 'هنوز فرم منتشرشده‌ای نیست؛ ابتدا فرم را در فرم‌ساز بساز و منتشر کن.';
    const checkbox = $('[data-sync-category="cooperation"]');
    if (checkbox) {
      checkbox.checked = !!select.value;
      checkbox.dataset.initialized = 'true';
    }
    refreshCounts();
  }

  async function loadCooperationSettings() {
    const api = root.NORA_SERVER_API;
    if (!api || typeof api.getOwnerSiteContent !== 'function' || typeof api.listForms !== 'function')
      throw { status: 404, code: 'cooperation_form_api_unavailable' };
    const [siteContent, formResult] = await Promise.all([api.getOwnerSiteContent(), api.listForms()]);
    const rows = siteContent && siteContent.content && Array.isArray(siteContent.content.cooperation)
      ? siteContent.content.cooperation : [];
    const currentId = rows[0] && rows[0].formId || '';
    setCooperationFormOptions(formResult && formResult.items, currentId);
    return currentId;
  }

  async function synchronize() {
    const api = root.NORA_SERVER_API;
    if (!api || typeof api.getOwnerSiteContent !== 'function' || typeof api.updateSiteContent !== 'function') {
      setState('API محتوای سرور در این صفحه بارگذاری نشده است؛ محتوای محلی پاک یا ارسال نشد.', 'error');
      return false;
    }
    if(!TEST_FIXTURE_MODE&&!serverCooperationLoaded){
      setState('دستهٔ همکاری هنوز با فهرست فرم‌های منتشرشدهٔ سرور تطبیق داده نشده است؛ چیزی ارسال نشد.','error');
      return false;
    }
    const categories = selected();
    if (!TEST_FIXTURE_MODE&&categories.some(key=>key!=='cooperation')){
      setState('دستهٔ انتخاب‌شده ویرایشگر سروری ندارد؛ اطلاعات مرورگر ارسال نشد.','error');
      return false;
    }
    if (!categories.length) {
      setState('دست‌کم یک دسته را برای همگام‌سازی انتخاب کنید.', 'error');
      return false;
    }
    const all = refreshCounts();
    const updates = Object.fromEntries(categories.map(key => [key, all[key]]));
    const summary = categories.map(key => `${KEY_MAP[key]}: ${new Intl.NumberFormat('fa-IR').format(updates[key].length)}`).join('، ');
    const confirmMessage = `دسته‌های انتخاب‌شده در سرور جایگزین می‌شوند: ${summary}.\n\nبرای دستهٔ خالی، محتوای عمومی قبلی پاک می‌شود. ادامه می‌دهید؟`;
    if (typeof root.confirm === 'function' && !root.confirm(confirmMessage)) return false;

    const button = $('#siteContentSyncNow');
    if (button) { button.disabled = true; button.setAttribute('aria-busy', 'true'); }
    setState('در حال بررسی دسترسی مالک و نسخهٔ محتوا…');
    try {
      await api.me();
      const current = await api.getOwnerSiteContent();
      const result = await api.updateSiteContent(updates, Number(current && current.version) || 0);
      const version = Number(result && result.version) || 0;
      setState(`محتوای انتخاب‌شده روی سرور منتشر شد (نسخهٔ ${new Intl.NumberFormat('fa-IR').format(version)}).`, 'success');
      const ui = root.NORA_UI || {};
      if (typeof ui.toast === 'function') ui.toast('محتوای عمومی با موفقیت به سرور منتقل شد');
      return true;
    } catch (error) {
      setState(apiErrorMessage(error), 'error');
      if (error && error.status === 401) {
        const details = $('#siteContentOwnerLogin');
        if (details) details.open = true;
      }
      return false;
    } finally {
      if (button) { button.disabled = false; button.removeAttribute('aria-busy'); }
    }
  }

  function start() {
    const panel = $('#siteContentSync');
    if (!panel) return;
    refreshCounts();
    const cooperationSelect = $('#cooperationFormSelect');
    if (cooperationSelect) cooperationSelect.addEventListener('change', () => {
      saveCooperationFormId(cooperationSelect.value);
      const checkbox = $('[data-sync-category="cooperation"]');
      if (checkbox) { checkbox.checked = true; checkbox.dataset.initialized = 'true'; }
      refreshCounts();
      setState('فرم همکاری انتخاب شد؛ برای انتشار یا برداشتن آن، دستهٔ فرم همکاری را همگام‌سازی کنید.');
    });
    const button = $('#siteContentSyncNow');
    if (button) button.addEventListener('click', synchronize);
    const form = $('#siteContentOwnerLoginForm');
    if (form) form.addEventListener('submit', async event => {
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]');
      const username = form.elements.username.value.trim();
      const password = form.elements.password.value;
      if (submit) { submit.disabled = true; submit.setAttribute('aria-busy', 'true'); }
      setState('در حال ورود مالک از طریق API هم‌مبدأ…');
      try {
        const api = root.NORA_SERVER_API;
        if (!api) throw { status: 404, code: 'owner_api_unavailable' };
        await api.login(username, password);
        form.elements.password.value = '';
        await checkOwner();
        await loadCooperationSettings();
        setState('ورود مالک تأیید شد؛ محتوای انتخاب‌شده را برای انتشار بفرستید.', 'success');
        await synchronize();
        if (root.NORA_COOPERATION_INBOX) root.NORA_COOPERATION_INBOX.refresh();
      } catch (error) {
        setState(apiErrorMessage(error), 'error');
      } finally {
        form.elements.password.value = '';
        if (submit) { submit.disabled = false; submit.removeAttribute('aria-busy'); }
      }
    });
    checkOwner().then(async () => {
      await loadCooperationSettings();
      setState('دسترسی مالک فعال است؛ انتخاب کنید کدام محتوای پشتیبانی‌شده روی نسخهٔ عمومی سرور جایگزین شود.');
    }).catch(error => {
      if (error && error.status === 401) setState('برای انتشار عمومی، ابتدا با حساب مالک وارد شوید.');
      else setState(apiErrorMessage(error), 'error');
    });
  }

  root.NORA_SITE_CONTENT_SYNC = Object.freeze({ snapshot, synchronize, refreshCounts });
  if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})(typeof window === 'undefined' ? globalThis : window);
