(function (root) {
  'use strict';
  const $ = selector => root.document.querySelector(selector);
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const labels = { new: 'جدید', reviewing: 'در حال بررسی', contacted: 'پیگیری شد', closed: 'بسته' };
  let loading = false;

  function state(message, error) {
    const node = $('#cooperationInboxState');
    if (!node) return;
    node.textContent = message;
    if (error) node.dataset.state = 'error';
    else delete node.dataset.state;
  }

  function apiMessage(error) {
    if (!error || error.code === 'server_unreachable' || error.status === 0)
      return 'اتصال به سرور برقرار نشد؛ صندوق درخواست‌ها در دسترس نیست.';
    if (error.status === 401) return 'برای دسترسی به درخواست‌ها، با حساب مالک وارد شوید.';
    if (error.status === 403) return 'اعتبارسنجی امنیتی صفحه ناموفق بود؛ صفحه را از نشانی اصلی سامانه باز کنید.';
    if (error.status === 404) return 'API صندوق همکاری روی این میزبان در دسترس نیست.';
    if (error.status === 503) return 'پایگاه‌داده یا migration سرور آماده نیست.';
    return `دریافت صندوق انجام نشد (${error.code || 'خطای سرور'}).`;
  }

  function contactMarkup(value) {
    const text = String(value || '').trim();
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) return `<a href="mailto:${esc(text)}" dir="ltr">${esc(text)}</a>`;
    const digits = text.replace(/[^+\d۰-۹٠-٩]/g, '');
    if (digits.length >= 8 && digits.length <= 20) return `<a href="tel:${esc(digits)}" dir="ltr">${esc(text)}</a>`;
    return `<span dir="ltr">${esc(text)}</span>`;
  }

  function dateText(value) {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    try { return new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium', timeStyle: 'short' }).format(date); }
    catch (_) { return date.toLocaleString(); }
  }

  function row(item) {
    const kind = item.kind === 'teaching' ? 'همکاری آموزشی'
      : item.kind === 'institution' ? 'همکاری نهادی' : 'پیشنهاد دیگر';
    const status = labels[item.status] || labels.new;
    return `<article class="cooperation-request" data-request-id="${esc(item.id)}">
      <header class="request-head"><div><h3>${esc(item.name)}</h3><p>${kind}${item.organization ? ` · ${esc(item.organization)}` : ''}</p></div>
        <span class="request-date">${esc(dateText(item.created_at))}</span></header>
      <div class="request-contact">${contactMarkup(item.contact)}</div>
      <p class="request-message">${esc(item.message).replace(/\r?\n/g, '<br>')}</p>
      <footer class="request-footer"><span class="request-current">وضعیت: ${esc(status)}</span><span class="sp"></span>
        <label><span class="visually-hidden">تغییر وضعیت درخواست ${esc(item.name)}</span>
          <select data-request-status="${esc(item.id)}">${Object.keys(labels).map(key => `<option value="${key}"${key === item.status ? ' selected' : ''}>${labels[key]}</option>`).join('')}</select>
        </label>
        <button class="btn sm quiet" type="button" data-request-save="${esc(item.id)}">ذخیرهٔ وضعیت</button>
      </footer>
    </article>`;
  }

  async function refresh() {
    if (loading) return false;
    const api = root.NORA_SERVER_API;
    if (!api || typeof api.listCooperationRequests !== 'function') {
      state('API صندوق همکاری در این صفحه بارگذاری نشده است.', true);
      return false;
    }
    loading = true;
    const button = $('#refreshCooperationInbox');
    if (button) { button.disabled = true; button.setAttribute('aria-busy', 'true'); }
    state('در حال دریافت درخواست‌های ثبت‌شده…');
    try {
      const response = await api.listCooperationRequests(100, 0);
      const items = Array.isArray(response && response.items) ? response.items : [];
      $('#cooperationInboxList').innerHTML = items.length
        ? items.map(row).join('')
        : '<p class="inbox-empty">درخواست همکاری ثبت‌شده‌ای وجود ندارد.</p>';
      const total = Number(response && response.total) || 0;
      state(`${new Intl.NumberFormat('fa-IR').format(total)} درخواست در صندوق ثبت شده است${total > items.length ? `؛ ${new Intl.NumberFormat('fa-IR').format(items.length)} مورد تازه نمایش داده شد.` : '.'}`);
      return true;
    } catch (error) {
      state(apiMessage(error), true);
      if (error && error.status === 401) {
        const login = $('#siteContentOwnerLogin');
        if (login) login.open = true;
      }
      return false;
    } finally {
      loading = false;
      if (button) { button.disabled = false; button.removeAttribute('aria-busy'); }
    }
  }

  async function update(requestId) {
    const api = root.NORA_SERVER_API;
    const select = $(`[data-request-status="${CSS.escape(requestId)}"]`);
    const button = $(`[data-request-save="${CSS.escape(requestId)}"]`);
    if (!select || !button || !api) return;
    button.disabled = true;
    try {
      await api.updateCooperationRequest(requestId, select.value);
      await refresh();
      const ui = root.NORA_UI || {};
      if (typeof ui.toast === 'function') ui.toast('وضعیت درخواست همکاری ذخیره شد');
    } catch (error) {
      state(apiMessage(error), true);
      if (error && error.status === 401) {
        const login = $('#siteContentOwnerLogin');
        if (login) login.open = true;
      }
    } finally { button.disabled = false; }
  }

  function start() {
    if (!$('#cooperationInbox')) return;
    const refreshButton = $('#refreshCooperationInbox');
    if (refreshButton) refreshButton.addEventListener('click', refresh);
    $('#cooperationInboxList').addEventListener('click', event => {
      const button = event.target.closest('[data-request-save]');
      if (button) update(button.dataset.requestSave);
    });
    root.NORA_COOPERATION_INBOX = Object.freeze({ refresh });
    const api = root.NORA_SERVER_API;
    if (api && typeof api.me === 'function') api.me().then(refresh).catch(() => {});
  }

  if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})(typeof window === 'undefined' ? globalThis : window);
