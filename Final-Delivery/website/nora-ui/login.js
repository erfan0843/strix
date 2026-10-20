/* ورود نورا: OTP واقعی از API سرور؛ کد محلی ساخته نمی‌شود. */
(function () {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const state = {
    captchaToken: '',
    captchaImage: '',
    captchaBusy: false,
    captchaFailed: false,
    authenticated: false,
    provider: '',
    busy: false,
    mode: 'phone',
    entryMode: 'phone',
    phone: '',
    otpChallengeId: '',
    otpExpiresAt: 0,
    otpResendAt: 0,
    otpTimerId: 0,
    role: null,
    permissions: [],
    accountCreated: false,
    profileSaved: true,
    deliveryBotUrl: '',
  };

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function normalizeDigits(value) {
    return String(value == null ? '' : value)
      .replace(/[۰-۹]/g, (digit) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit)))
      .replace(/[٠-٩]/g, (digit) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(digit)));
  }

  function persianDigits(value) {
    return String(value == null ? '' : value)
      .replace(/[0-9]/g, (digit) => '۰۱۲۳۴۵۶۷۸۹'[Number(digit)]);
  }

  function displayPhone(value) {
    const digits = normalizeDigits(value).replace(/[^0-9]/g, '');
    const local = digits.startsWith('98') && digits.length === 12 ? '0' + digits.slice(2) : digits;
    const grouped = local.length === 11 ? `${local.slice(0, 4)} ${local.slice(4, 7)} ${local.slice(7)}` : local;
    return persianDigits(grouped);
  }

  function clockLabel(seconds) {
    const total = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(total / 60);
    const rest = String(total % 60).padStart(2, '0');
    return persianDigits(`${minutes}:${rest}`);
  }

  function otpSlotsMarkup() {
    return `<div class="lg-otp-slots" aria-hidden="true">${Array.from({ length: 6 }, (_, index) => `<span class="lg-otp-slot" data-otp-slot="${index}"></span>`).join('')}</div>`;
  }

  function syncOtpSlots(input) {
    if (!input) return;
    const original = String(input.value || '');
    const clean = original.replace(/[^0-9۰-۹٠-٩]/g, '').slice(0, 6);
    if (clean !== original) {
      const oldCaret = Number.isInteger(input.selectionStart) ? input.selectionStart : clean.length;
      input.value = clean;
      try { input.setSelectionRange(Math.min(oldCaret, clean.length), Math.min(oldCaret, clean.length)); } catch (_) {}
    }
    const digits = normalizeDigits(clean);
    const slots = input.closest('.lg-otp-control')?.querySelectorAll('[data-otp-slot]');
    if (!slots) return;
    const caret = Number.isInteger(input.selectionStart) ? input.selectionStart : digits.length;
    slots.forEach((slot, index) => {
      const digit = digits.charAt(index);
      slot.textContent = digit ? persianDigits(digit) : '';
      slot.classList.toggle('is-filled', Boolean(digit));
      slot.classList.toggle('is-current', !input.disabled && input === document.activeElement
        && digits.length < 6 && index === Math.min(caret, 5));
    });
  }

  function setLead(message) {
    const element = $('#lgLead');
    if (element) element.textContent = message || '';
  }

  function setTitle(message) {
    const element = $('#lgTitle');
    if (element) element.textContent = message || 'ورود به نورا';
    const staffLike = /مدیر|مالک/.test(message || '');
    const eyebrow = $('#lgEyebrow span');
    if (eyebrow) eyebrow.textContent = staffLike ? 'پنل مدیریت نورا' : 'حساب کاربری نورا';
    const secure = $('.lgsecure');
    if (secure) secure.hidden = staffLike;
  }

  function setStatus(message, kind) {
    const element = $('#lgStatus');
    if (!element) return;
    element.hidden = !message;
    element.textContent = message || '';
    element.dataset.kind = kind || 'info';
  }

  function setAdminEntryVisible(visible) {
    const element = $('#lgAdminEntry');
    if (element) element.hidden = !visible;
  }

  function requestedNext() {
    return new URLSearchParams(location.search).get('next') || '';
  }

  /* فهرست سفید مسیر بازگشت. تنها یک پارامتر پرس‌وجو مجاز است: نشانهٔ صریح
     «مسیر پیوند حساب» (`?link=bale`). این نشانه باید از ورود با شماره جان سالم
     ببرد، وگرنه کاربر پس از ورود به صفحهٔ بی‌نشانه برمی‌گردد. هیچ پرس‌وجوی
     دیگری پذیرفته نمی‌شود تا محافظت بازکردن نشانی دلخواه باز هم برجا بماند. */
  function safeAccountNext() {
    const requested = new URLSearchParams(location.search).get('next') || '';
    return /^account\.html(?:\?link=bale)?(?:#(?:events|profile|pay|book|notifications|my-files|account-data|info|auth|login|forms|payments|privacy|club|points|invite))?$/.test(requested)
      ? requested
      : '';
  }

  function safeOwnerNext() {
    const requested = requestedNext();
    return /^(?:admin|create|builder)\.html(?:#[A-Za-z0-9_-]+)?$/.test(requested)
      ? requested
      : '';
  }

  function safeManagerNext() {
    const requested = requestedNext();
    return /^admin\.html(?:#[A-Za-z0-9_-]+)?$/.test(requested)
      ? requested
      : '';
  }

  function continueAfterLogin(provider) {
    if (provider === 'owner') return;
    const managerEntry = ['staff', 'manager', 'owner'].includes(state.entryMode);
    const managerTarget = managerEntry ? safeManagerNext() : '';
    if (provider === 'manager-password' && managerTarget
        && ['manager', 'club-supervisor'].includes(state.role)) {
      location.replace(managerTarget);
      return;
    }
    if (state.accountCreated) return; /* حساب تازه: اول کارت تأیید و راهنمای تکمیل پروفایل دیده می‌شود */
    const accountTarget = safeAccountNext();
    if (accountTarget) location.replace(accountTarget);
  }

  function renderLoading() {
    setAdminEntryVisible(false);
    setTitle(state.mode === 'staff' ? 'ورود مدیران' : 'ورود به نورا');
    setLead('');
    const body = $('#lgBody');
    if (body) body.innerHTML = '<div class="lgstep lg-loading" role="status" aria-label="در حال بررسی ورود"><span class="lg-spinner" aria-hidden="true"></span></div>';
    setStatus('');
  }

  function clearOtpTimer() {
    if (state.otpTimerId) window.clearInterval(state.otpTimerId);
    state.otpTimerId = 0;
  }

  function renderPhoneLogin() {
    clearOtpTimer();
    setAdminEntryVisible(true);
    setTitle('ورود یا ثبت‌نام');
    setLead('');
    const body = $('#lgBody');
    if (!body) return;

    if (!state.otpChallengeId) {
      setLead('شمارهٔ همراهت را وارد کن؛ کد یک‌بارمصرف در ربات بله می‌آید. حساب نداری؟ ساخته می‌شود.');
      body.innerHTML = `<div class="lgstep" id="lgPhoneMethod">
        <form class="lgform" id="lgPhoneForm" autocomplete="on" novalidate>
          <label class="lgfield" for="lgPhone">
            <span class="lglbl">شمارهٔ همراه</span>
            <input class="lgtext" id="lgPhone" name="phone" type="tel" inputmode="tel" autocomplete="tel-national"
              required maxlength="32" dir="ltr" value="${escapeHtml(state.phone)}" placeholder="۰۹۱۲۳۴۵۶۷۸۹" aria-label="شمارهٔ همراه"${state.busy ? ' disabled' : ''}/>
          </label>
          <div class="lgfield">
            <label class="lglbl" for="lgCapAnswer">کد امنیتی داخل تصویر</label>
            <div class="lg-captcha">
              <div class="lg-cap-img" id="lgCapImg" aria-hidden="true">${state.captchaImage ? `<img class="lg-cap-pic" src="${escapeHtml(state.captchaImage)}" alt="" width="180" height="60" draggable="false"/>` : (state.captchaFailed ? '<span class="lg-cap-fail">کد امنیتی بارگذاری نشد</span>' : '<span class="lg-spinner"></span>')}</div>
              <input class="lgtext" id="lgCapAnswer" name="captcha" type="text" inputmode="numeric" autocomplete="off"
                required minlength="4" maxlength="4" pattern="[0-9۰-۹٠-٩]{4}" dir="ltr" aria-label="کد امنیتی چهار رقمی" placeholder="۴ رقم"${state.busy ? ' disabled' : ''}/>
              <button class="lgbtn quiet" type="button" id="lgCapNew" aria-label="کد امنیتی تازه" title="کد امنیتی تازه"${state.busy || state.captchaBusy ? ' disabled' : ''}><svg aria-hidden="true"><use href="#i-refresh"/></svg></button>
            </div>
          </div>
          <button class="lgbtn" type="submit" id="lgPhoneSubmit"${state.busy ? ' disabled aria-busy="true"' : ''}>${state.busy ? 'در حال ارسال کد…' : 'دریافت کد'}</button>
        </form>
      </div>`;
      if (!state.captchaToken && !state.captchaBusy && !state.captchaFailed) loadCaptcha();
      return;
    }

    setTitle('کد ورود');
    setLead('');
    const wait = Math.max(0, Math.ceil((state.otpResendAt - Date.now()) / 1000));
    const expiresIn = Math.max(0, Math.ceil((state.otpExpiresAt - Date.now()) / 1000));
    const resendLabel = wait
      ? `ارسال دوباره تا ${persianDigits(wait)} ثانیه دیگر`
      : 'ارسال دوبارهٔ کد';
    body.innerHTML = `<div class="lgstep" id="lgPhoneCodeMethod">
      <p class="lg-otp-sent" role="status">کد شش‌رقمی از ربات بله به <b>${escapeHtml(displayPhone(state.phone))}</b> ارسال شد.</p>
      <form class="lgform" id="lgPhoneCodeForm" autocomplete="on" novalidate>
        <label class="lgfield lg-otp-field" for="lgOtpCode">
          <span class="lglbl">کد را این‌جا وارد کن</span>
          <div class="lg-otp-control">
            ${otpSlotsMarkup()}
            <input class="lgtext lgcode" id="lgOtpCode" name="code" type="text" inputmode="numeric" autocomplete="one-time-code"
              required minlength="6" maxlength="6" pattern="[0-9۰-۹٠-٩]{6}" dir="ltr" aria-label="کد یک‌بارمصرف شش‌رقمی"${state.busy ? ' disabled' : ''}/>
          </div>
        </label>
        <p class="lg-otp-meta${expiresIn ? '' : ' is-over'}" id="lgOtpMeta">${expiresIn ? `اعتبار کد: ${clockLabel(expiresIn)}` : 'مهلت کد تمام شد؛ کد تازه بگیر.'}</p>
        <button class="lgbtn" type="submit" id="lgOtpVerify"${state.busy ? ' disabled aria-busy="true"' : ''}>${state.busy ? 'در حال بررسی کد…' : 'تأیید و ورود'}</button>
      </form>
      <div class="lg-phone-actions">
        <button class="lgbtn quiet" type="button" id="lgOtpResend"${state.busy || wait ? ' disabled' : ''}>${resendLabel}</button>
        <button class="lgbtn quiet" type="button" id="lgPhoneChange"${state.busy ? ' disabled' : ''}>تغییر شماره</button>
      </div>
      <p class="lg-otp-help">کد در گفت‌وگوی ربات بله می‌آید. اگر چیزی نرسید، مطمئن شو بله با همین شماره روی گوشی‌ات فعال است.</p>
    </div>`;

    syncOtpSlots($('#lgOtpCode'));
    state.otpTimerId = window.setInterval(() => {
      if (state.mode !== 'phone' || !state.otpChallengeId) {
        clearOtpTimer();
        return;
      }
      const secondsToResend = Math.max(0, Math.ceil((state.otpResendAt - Date.now()) / 1000));
      const secondsToExpiry = Math.max(0, Math.ceil((state.otpExpiresAt - Date.now()) / 1000));
      const resendButton = $('#lgOtpResend');
      const meta = $('#lgOtpMeta');
      if (resendButton) {
        resendButton.disabled = state.busy || secondsToResend > 0;
        resendButton.textContent = secondsToResend
          ? `ارسال دوباره تا ${persianDigits(secondsToResend)} ثانیه دیگر`
          : 'ارسال دوبارهٔ کد';
      }
      if (meta) {
        meta.textContent = secondsToExpiry
          ? `اعتبار کد: ${clockLabel(secondsToExpiry)}`
          : 'مهلت کد تمام شد؛ کد تازه بگیر.';
        meta.classList.toggle('is-over', !secondsToExpiry);
      }
      if (!secondsToResend && !secondsToExpiry) clearOtpTimer();
    }, 1000);
  }

  function renderStaffLogin() {
    clearOtpTimer();
    setAdminEntryVisible(false);
    setTitle('ورود مدیران');
    setLead('با نام کاربری و گذرواژه‌ای که برایت ساخته شده وارد شو.');
    const body = $('#lgBody');
    if (!body) return;
    body.innerHTML = `<div class="lgstep" id="lgStaffMethod">
      <form class="lgform" id="lgStaffForm" autocomplete="on" novalidate>
        <label class="lgfield" for="lgStaffUsername">
          <span class="lglbl">نام کاربری</span>
          <input class="lgtext" id="lgStaffUsername" name="username" type="text" autocomplete="username"
            required maxlength="160" dir="ltr"/>
        </label>
        <label class="lgfield" for="lgStaffPassword">
          <span class="lglbl">گذرواژه</span>
          <input class="lgtext" id="lgStaffPassword" name="password" type="password" autocomplete="current-password"
            required maxlength="1024" dir="ltr"/>
        </label>
        <button class="lgbtn" type="submit" id="lgStaffSubmit"${state.busy ? ' disabled aria-busy="true"' : ''}>${state.busy ? 'در حال بررسی…' : 'ورود'}</button>
      </form>
      <button class="lgbtn quiet" type="button" id="lgBack"${state.busy ? ' disabled' : ''}>ورود اعضا با شمارهٔ همراه</button>
    </div>`;
  }

  function renderAuthenticated() {
    clearOtpTimer();
    setTitle(state.provider === 'owner' || state.provider === 'manager-password' ? 'ورود مدیران' : 'ورود به نورا');
    setLead('');
    const body = $('#lgBody');
    if (!body) return;
    setAdminEntryVisible(false);

    const isOwner = state.provider === 'owner';
    const hasAdminRole = ['manager', 'club-supervisor'].includes(state.role);
    const requestedManagerEntry = !isOwner && ['staff', 'manager', 'owner'].includes(state.entryMode);
    const canContinueToManager = requestedManagerEntry && state.provider === 'manager-password' && hasAdminRole;
    const managerDenied = requestedManagerEntry && !canContinueToManager;
    const target = isOwner
      ? (safeOwnerNext() || 'admin.html#money')
      : canContinueToManager
        ? (safeManagerNext() || 'admin.html#dash')
        : (safeAccountNext() || 'account.html');
    const destination = isOwner
      ? 'رفتن به پنل مدیریت'
      : canContinueToManager
        ? 'رفتن به پنل مدیریت'
        : 'رفتن به حساب من';
    const newPhoneAccount = state.provider === 'phone' && state.accountCreated && !managerDenied;
    const heading = isOwner ? 'ورود مالک تأیید شد'
      : state.provider === 'manager-password' ? 'ورود مدیر تأیید شد'
        : newPhoneAccount ? 'حسابت ساخته شد'
          : state.provider === 'phone' ? 'ورود با شمارهٔ همراه تأیید شد'
            : state.provider === 'bale' ? 'ورود با بله تأیید شد' : 'ورود تأیید شد';
    const description = managerDenied
      ? hasAdminRole
        ? 'برای ورود مدیریت، نام کاربری و گذرواژه لازم است.'
        : 'دسترسی مدیریت برای این حساب فعال نیست.'
      : newPhoneAccount
        ? 'حساب نورا با همین شماره ساخته و وارد شد. اطلاعات تکمیلی پروفایل در ربات بله ثبت می‌شود و وضعیتش در «حساب من» دیده می‌شود.'
        : '';
    const botLink = newPhoneAccount && state.deliveryBotUrl
      ? `<a class="lgbtn quiet" href="${escapeHtml(state.deliveryBotUrl)}" target="_blank" rel="noopener">تکمیل پروفایل در ربات بله</a>`
      : '';

    body.innerHTML = `<div class="lgstep lg-authenticated" id="lgAuthenticated">
      <span class="lgcheck ok" aria-hidden="true"><svg><use href="#i-check"/></svg></span>
      <h2 class="lgdtitle">${heading}</h2>
      ${description ? `<p class="lgdle">${description}</p>` : ''}
      <a class="lgbtn" id="lgContinue" href="${escapeHtml(target)}">${destination}</a>
      ${botLink}
      <button class="lgbtn quiet" type="button" id="lgLogout"${state.busy ? ' disabled aria-busy="true"' : ''}>${state.busy ? 'در حال خروج…' : 'خروج از حساب'}</button>
    </div>`;
    setStatus('');
  }

  function render() {
    if (state.authenticated) return renderAuthenticated();
    if (state.mode === 'staff') return renderStaffLogin();
    return renderPhoneLogin();
  }

  async function responseError(response) {
    if (response && response.status === 404) {
      return { code: 'api_not_found', message: 'API ورود وب در این پیش‌نمایش فعال نیست؛ backend وب باید متصل باشد.' };
    }
    let payload = {};
    try { payload = await response.json(); } catch (_) {}
    const detail = payload && payload.detail;
    const code = typeof detail === 'string' ? detail : (detail && detail.code) || payload.error || '';
    const messages = {
      owner_login_not_configured: 'ورود مالک هنوز روی سرور فعال نیست.',
      manager_login_not_configured: 'ورود مدیران هنوز روی سرور فعال نیست.',
      staff_login_not_configured: 'ورود مدیریت هنوز روی سرور فعال نیست.',
      invalid_credentials: 'نام کاربری یا گذرواژه درست نیست.',
      database_unavailable: 'ورود موقتاً در دسترس نیست.',
      phone_otp_not_configured: 'سرویس ارسال کد روی سرور تنظیم نشده است.',
      invalid_captcha: 'کد امنیتی درست نیست؛ کد جدید را وارد کن.',
      captcha_not_configured: 'کد امنیتی روی سرور تنظیم نشده است.',
      phone_otp_delivery_unavailable: 'ارسال کد به بله انجام نشد. مطمئن شو این شماره در بله فعال است و کمی بعد دوباره تلاش کن.',
      phone_otp_unavailable: 'ارسال کد موقتاً در دسترس نیست.',
      account_session_unavailable: 'ورود حساب تأیید نشد؛ دوباره تلاش کن.',
      invalid_phone_number: 'شمارهٔ همراه درست نیست؛ یک شمارهٔ ایرانی مثل ۰۹۱۲۳۴۵۶۷۸۹ بنویس.',
      invalid_or_expired_otp: 'کد نادرست است یا مهلتش گذشته است.',
      otp_resend_too_soon: 'برای ارسال دوباره کمی صبر کن.',
      login_temporarily_blocked: 'تلاش‌های زیادی انجام شده؛ کمی بعد دوباره امتحان کن.',
      same_origin_required: 'صفحه را تازه کن و دوباره تلاش کن.',
    };
    return { code, message: messages[code] || 'ورود انجام نشد؛ دوباره تلاش کن.' };
  }

  /* همان نشانه‌ای که account.js پس از تأیید نشست سرور می‌گذارد: برچسب ناوبری «حساب من» می‌شود
     و نگهبان پیوندهای بیرونی ui.js، پیوند ربات بله را که از سرور آمده غیرفعال نمی‌کند. */
  function markServerAccount(on) {
    try {
      if (on) window.NORA_ACCOUNT_SOURCE = 'server'; else delete window.NORA_ACCOUNT_SOURCE;
      if (window.NORA_UI && typeof window.NORA_UI.updateAccountNavigation === 'function') window.NORA_UI.updateAccountNavigation();
    } catch (_) {}
  }

  function restoreStaffUsername(username, focusPassword) {
    const field = $('#lgStaffUsername');
    if (field) field.value = username || '';
    if (focusPassword) { const pw = $('#lgStaffPassword'); if (pw && pw.focus) pw.focus(); }
  }

  async function staffLogin(form) {
    if (state.busy || state.authenticated || !form) return;
    const username = String(form.elements.username && form.elements.username.value || '').trim();
    const password = String(form.elements.password && form.elements.password.value || '');
    if (!username || !password) {
      setStatus('نام کاربری و گذرواژه را وارد کن.', 'error');
      return;
    }

    state.busy = true;
    state.mode = 'staff';
    renderStaffLogin();
    restoreStaffUsername(username);
    setStatus('در حال بررسی…');
    let serverAccepted = false;
    try {
      const response = await fetch('/api/auth/staff-login', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        const error = await responseError(response);
        state.busy = false;
        renderStaffLogin();
        restoreStaffUsername(username, true);
        setStatus(error.message, 'error');
        return;
      }
      const payload = await response.json();
      if (!payload || payload.authenticated !== true
          || !['owner', 'manager-password'].includes(payload.provider)) {
        throw new Error('unexpected_staff_auth_response');
      }
      serverAccepted = true;
      const isOwner = payload.provider === 'owner';
      const sessionResponse = await fetch(isOwner ? '/api/auth/me' : '/api/account/me', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Accept': 'application/json' },
      });
      if (!sessionResponse.ok) throw new Error('staff_session_not_confirmed');
      const session = await sessionResponse.json();
      if (isOwner) {
        if (!session || session.authenticated !== true || session.role !== 'owner'
            || session.owner_id !== payload.owner_id) {
          throw new Error('unexpected_staff_owner_session');
        }
        state.provider = 'owner';
        state.role = 'owner';
      } else {
        if (!session || session.authenticated !== true || session.provider !== 'manager-password'
            || typeof payload.account_id !== 'string' || session.account_id !== payload.account_id
            || !['manager', 'club-supervisor'].includes(session.role)) {
          throw new Error('unexpected_staff_manager_session');
        }
        state.provider = 'manager-password';
        state.role = session.role;
      }
      state.permissions = Array.isArray(session.permissions) ? session.permissions.slice() : [];
      state.authenticated = true;
      state.busy = false;
      state.mode = 'authenticated';
      renderAuthenticated();
      continueAfterLogin(state.provider);
    } catch (_) {
      state.busy = false;
      state.authenticated = false;
      state.provider = '';
      state.role = null;
      state.permissions = [];
      state.mode = 'staff';
      renderStaffLogin();
      restoreStaffUsername(username, true);
      setStatus(serverAccepted
        ? 'ورود پذیرفته شد، اما دسترسی سرور تأیید نشد؛ دوباره تلاش کن.'
        : 'ورود انجام نشد؛ نام کاربری و گذرواژه را بررسی کن.', 'error');
    }
  }

  /* تصویر کپچا فقط PNG رستری سرور است؛ هیچ markup سروری در DOM تزریق نمی‌شود و رقمی به‌صورت متن وجود ندارد. */
  const CAPTCHA_IMAGE_RE = /^data:image\/png;base64,[A-Za-z0-9+/]+=*$/;
  function isCaptchaImage(value) {
    return typeof value === 'string' && value.length < 200000 && CAPTCHA_IMAGE_RE.test(value);
  }

  async function loadCaptcha() {
    if (state.captchaBusy) return;
    state.captchaBusy = true;
    state.captchaFailed = false;
    state.captchaToken = '';
    try {
      const response = await fetch('/api/auth/captcha', {
        method: 'GET', credentials: 'same-origin', cache: 'no-store', headers: { 'Accept': 'application/json' },
      });
      if (!response.ok) throw new Error('captcha');
      const payload = await response.json();
      if (!payload || typeof payload.token !== 'string' || !isCaptchaImage(payload.image)) throw new Error('captcha');
      state.captchaToken = payload.token;
      state.captchaImage = payload.image;
    } catch (_) {
      state.captchaImage = '';
      state.captchaFailed = true;
      setStatus('کد امنیتی بارگذاری نشد؛ دوباره تلاش کن.', 'error');
    }
    state.captchaBusy = false;
    if (state.mode !== 'phone' || state.otpChallengeId) return;
    const slot = $('#lgCapImg');
    const refresh = $('#lgCapNew');
    if (slot && refresh && $('#lgPhoneForm')) {
      /* فقط تصویر را تازه می‌کنیم تا شماره و کد تایپ‌شدهٔ کاربر از بین نرود */
      slot.innerHTML = state.captchaImage
        ? `<img class="lg-cap-pic" src="${escapeHtml(state.captchaImage)}" alt="" width="180" height="60" draggable="false"/>`
        : '<span class="lg-cap-fail">کد امنیتی بارگذاری نشد</span>';
      refresh.disabled = state.busy;
      const answer = $('#lgCapAnswer');
      if (answer) answer.value = '';
      return;
    }
    renderPhoneLogin();
  }

  /* آینهٔ همان قاعدهٔ سرور (backend/otp.py normalize_iran_phone) فقط برای پیام زودهنگام؛
     داوری نهایی با سرور است. شمارهٔ نامعتبر، کد امنیتی را هدر نمی‌دهد. */
  function normalizeIranPhone(value) {
    const raw = normalizeDigits(String(value || '')).trim();
    if (!raw || raw.length > 32) return null;
    let compact = raw.replace(/[\s().-]/g, '');
    if (compact.startsWith('+98')) compact = '0' + compact.slice(3);
    else if (compact.startsWith('0098')) compact = '0' + compact.slice(4);
    else if (compact.startsWith('98')) compact = '0' + compact.slice(2);
    else if (compact.length === 10 && compact.startsWith('9')) compact = '0' + compact;
    return /^09[0-9]{9}$/.test(compact) ? compact : null;
  }

  async function requestPhoneOtp(form) {
    if (state.busy || state.authenticated) return;
    const typedPhone = String(form && form.elements.phone && form.elements.phone.value || '').trim();
    if (typedPhone && !normalizeIranPhone(typedPhone)) {
      setStatus('شمارهٔ همراه درست نیست؛ یک شمارهٔ ایرانی مثل ۰۹۱۲۳۴۵۶۷۸۹ بنویس.', 'error');
      const phoneField = form && form.elements.phone;
      if (phoneField && phoneField.setAttribute) phoneField.setAttribute('aria-invalid', 'true');
      if (phoneField && phoneField.focus) phoneField.focus();
      return;
    }
    const captchaAnswer = normalizeDigits(form && form.elements.captcha && form.elements.captcha.value || '').trim();
    if (!/^[0-9]{4}$/.test(captchaAnswer)) {
      setStatus('کد امنیتی چهار رقمی را وارد کن.', 'error');
      return;
    }
    if (!state.captchaToken) {
      setStatus('کد امنیتی هنوز آماده نیست؛ چند لحظه صبر کن.', 'error');
      loadCaptcha();
      return;
    }
    const phone = String(form && form.elements.phone && form.elements.phone.value || state.phone || '').trim();
    if (!phone) {
      setStatus('شمارهٔ همراه را وارد کن.', 'error');
      return;
    }

    state.phone = phone;
    state.busy = true;
    state.mode = 'phone';
    renderPhoneLogin();
    setStatus('در حال ارسال کد…');
    try {
      const response = await fetch('/api/auth/phone-otp/request', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, captcha_token: state.captchaToken, captcha_answer: captchaAnswer }),
      });
      if (!response.ok) {
        const error = await responseError(response);
        state.busy = false;
        state.captchaToken = '';
        renderPhoneLogin();
        setStatus(error.message, 'error');
        loadCaptcha();
        return;
      }
      state.captchaToken = '';
      const payload = await response.json();
      if (!payload || payload.accepted !== true || typeof payload.challenge_id !== 'string'
          || !Number.isFinite(Number(payload.expires_in)) || !Number.isFinite(Number(payload.resend_in))) {
        throw new Error('invalid_phone_otp_response');
      }
      state.otpChallengeId = payload.challenge_id;
      state.otpExpiresAt = Date.now() + Math.max(1, Number(payload.expires_in)) * 1000;
      state.otpResendAt = Date.now() + Math.max(0, Number(payload.resend_in)) * 1000;
      state.busy = false;
      renderPhoneLogin();
      setStatus('');
    } catch (_) {
      state.busy = false;
      renderPhoneLogin();
      setStatus('ارتباط با سرویس ورود برقرار نشد؛ دوباره تلاش کن.', 'error');
    }
  }

  async function verifyPhoneOtp(form) {
    if (state.busy || state.authenticated || !form || !state.otpChallengeId) return;
    const code = normalizeDigits(form.elements.code && form.elements.code.value || '').trim();
    if (!/^[0-9]{6}$/.test(code)) {
      setStatus('کد شش‌رقمی را کامل وارد کن.', 'error');
      return;
    }

    state.busy = true;
    state.mode = 'phone';
    renderPhoneLogin();
    setStatus('در حال تأیید کد…');
    let serverAccepted = false;
    try {
      const response = await fetch('/api/auth/phone-otp/verify', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ challenge_id: state.otpChallengeId, phone: state.phone, code }),
      });
      if (!response.ok) {
        const error = await responseError(response);
        state.busy = false;
        renderPhoneLogin();
        setStatus(error.message, 'error');
        return;
      }
      const payload = await response.json();
      if (!payload || payload.authenticated !== true || payload.provider !== 'phone') {
        throw new Error('unexpected_phone_auth_response');
      }
      serverAccepted = true;
      const sessionResponse = await fetch('/api/account/me', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Accept': 'application/json' },
      });
      if (!sessionResponse.ok) throw new Error('phone_session_not_confirmed');
      const session = await sessionResponse.json();
      if (!session || session.authenticated !== true || session.provider !== 'phone'
          || session.account_id !== payload.account_id) {
        throw new Error('unexpected_phone_session');
      }
      state.provider = 'phone';
      state.role = typeof session.role === 'string' ? session.role : null;
      state.permissions = Array.isArray(session.permissions) ? session.permissions.slice() : [];
      /* تصمیم «حساب تازه / عضو قدیمی» فقط از پاسخ سرور و فقط پس از تأیید کد می‌آید */
      state.accountCreated = payload.created === true;
      state.profileSaved = payload.profile_saved !== false;
      state.deliveryBotUrl = typeof session.delivery_bot_url === 'string'
        && /^https:\/\/ble\.ir\/[A-Za-z0-9_]{3,64}$/.test(session.delivery_bot_url) ? session.delivery_bot_url : '';
      markServerAccount(true);
      state.authenticated = true;
      state.busy = false;
      state.phone = '';
      state.otpChallengeId = '';
      state.otpExpiresAt = 0;
      state.otpResendAt = 0;
      state.mode = 'authenticated';
      renderAuthenticated();
      continueAfterLogin('phone');
    } catch (_) {
      state.busy = false;
      if (serverAccepted) {
        state.phone = '';
        state.otpChallengeId = '';
        state.otpExpiresAt = 0;
        state.otpResendAt = 0;
        state.mode = 'phone';
        renderPhoneLogin();
        setStatus('کد پذیرفته شد، اما ورود به حساب تأیید نشد؛ دوباره وارد شو.', 'error');
        return;
      }
      renderPhoneLogin();
      setStatus('ارتباط با سرور برقرار نشد؛ دوباره تلاش کن.', 'error');
    }
  }

  function cookieValue(name) {
    const prefix = name + '=';
    for (const item of document.cookie.split(';')) {
      const part = item.trim();
      if (part.startsWith(prefix)) {
        try { return decodeURIComponent(part.slice(prefix.length)); }
        catch (_) { return part.slice(prefix.length); }
      }
    }
    return '';
  }

  async function logout() {
    if (state.busy || !state.authenticated) return;
    const owner = state.provider === 'owner';
    const csrf = cookieValue(owner ? 'nora_csrf' : 'nora_account_csrf');
    if (!csrf) {
      setStatus('ورود امن پیدا نشد؛ صفحه را تازه کن.', 'error');
      return;
    }

    state.busy = true;
    renderAuthenticated();
    try {
      const response = await fetch(owner ? '/api/auth/logout' : '/api/auth/account/logout', {
        method: 'POST',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrf,
        },
        body: '{}',
      });
      if (!response.ok && response.status !== 401) {
        const error = await responseError(response);
        state.busy = false;
        renderAuthenticated();
        setStatus(error.message, 'error');
        return;
      }
      if (response.status !== 401) {
        const payload = await response.json();
        if (!payload || payload.authenticated !== false) throw new Error('unexpected_logout_response');
      }
      state.authenticated = false;
      state.busy = false;
      state.provider = '';
      state.role = null;
      state.permissions = [];
      state.accountCreated = false;
      state.profileSaved = true;
      state.deliveryBotUrl = '';
      markServerAccount(false);
      state.phone = '';
      state.otpChallengeId = '';
      state.otpExpiresAt = 0;
      state.otpResendAt = 0;
      state.mode = state.entryMode;
      render();
      setStatus('از حساب خارج شدی.', 'info');
    } catch (_) {
      state.busy = false;
      renderAuthenticated();
      setStatus('خروج انجام نشد؛ دوباره تلاش کن.', 'error');
    }
  }

  async function checkSession() {
    if (state.mode === 'staff') renderLoading();
    else renderPhoneLogin();
    let unavailable = false;
    let authApiMissing = false;

    try {
      const response = await fetch('/api/auth/me', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Accept': 'application/json' },
      });
      if (response.ok) {
        const payload = await response.json();
        if (payload && payload.authenticated === true && payload.role === 'owner') {
          state.provider = 'owner';
          state.role = 'owner';
          state.permissions = Array.isArray(payload.permissions) ? payload.permissions.slice() : [];
          state.authenticated = true;
          state.mode = 'authenticated';
          renderAuthenticated();
          continueAfterLogin('owner');
          return;
        }
        throw new Error('unexpected_owner_session');
      }
      if (response.status !== 401) unavailable = true;
      if (response.status === 404) authApiMissing = true;
    } catch (_) {
      unavailable = true;
    }

    try {
      const response = await fetch('/api/account/me', {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        headers: { 'Accept': 'application/json' },
      });
      if (response.ok) {
        const payload = await response.json();
        if (payload && payload.authenticated === true && ['bale', 'phone', 'manager-password'].includes(payload.provider)) {
          markServerAccount(true);
          state.provider = payload.provider;
          state.role = typeof payload.role === 'string' ? payload.role : null;
          state.permissions = Array.isArray(payload.permissions) ? payload.permissions.slice() : [];
          state.authenticated = true;
          state.phone = '';
          state.mode = 'authenticated';
          renderAuthenticated();
          continueAfterLogin(payload.provider);
          return;
        }
        throw new Error('unexpected_account_session');
      }
      if (response.status !== 401) unavailable = true;
      if (response.status === 404) authApiMissing = true;
    } catch (_) {
      unavailable = true;
    }

    state.authenticated = false;
    state.provider = '';
    state.role = null;
    state.permissions = [];
    state.mode = state.entryMode;
    render();
    if (unavailable) setStatus(authApiMissing
      ? 'این پیش‌نمایش API ورود وب ندارد؛ backend وب باید متصل باشد.'
      : 'ارتباط با سرور برقرار نشد.', 'error');
  }

  function boot() {
    const requestedMode = new URLSearchParams(location.search).get('mode') || '';
    const requestedStaff = ['staff', 'manager', 'owner'].includes(requestedMode)
      || ((requestedMode === 'server' || !requestedMode) && Boolean(safeOwnerNext()));
    state.entryMode = requestedStaff ? 'staff' : 'phone';
    state.mode = state.entryMode;
    checkSession();
  }

  document.addEventListener('input', (event) => {
    if (event.target && event.target.id === 'lgOtpCode') syncOtpSlots(event.target);
    if (event.target && event.target.id === 'lgPhone' && event.target.getAttribute('aria-invalid')) event.target.removeAttribute('aria-invalid');
  });

  document.addEventListener('focusin', (event) => {
    if (event.target && event.target.id === 'lgOtpCode') syncOtpSlots(event.target);
  });

  document.addEventListener('focusout', (event) => {
    if (event.target && event.target.id === 'lgOtpCode') syncOtpSlots(event.target);
  });

  document.addEventListener('click', (event) => {
    const target = event.target;
    if (!target || typeof target.closest !== 'function') return;
    const otpControl = target.closest('.lg-otp-control');
    if (otpControl) {
      event.preventDefault();
      const slot = target.closest('[data-otp-slot]');
      const input = otpControl.querySelector('.lgcode');
      if (!slot || !input || input.disabled) return;
      const slotIndex = Number(slot.dataset.otpSlot);
      const caret = Math.min(Number.isInteger(slotIndex) ? slotIndex : 0, input.value.length);
      input.focus();
      try { input.setSelectionRange(caret, caret); } catch (_) {}
      syncOtpSlots(input);
      return;
    }
    if (target.closest('#lgBack')) {
      event.preventDefault();
      state.entryMode = 'phone';
      state.mode = 'phone';
      state.phone = '';
      state.otpChallengeId = '';
      state.otpExpiresAt = 0;
      state.otpResendAt = 0;
      try { history.replaceState(null, '', location.pathname); } catch (_) {}
      renderPhoneLogin();
      setStatus('');
      return;
    }
    if (target.closest('#lgPhoneChange')) {
      event.preventDefault();
      state.otpChallengeId = '';
      state.otpExpiresAt = 0;
      state.otpResendAt = 0;
      renderPhoneLogin();
      setStatus('');
      $('#lgPhone')?.focus();
      return;
    }
    if (target.closest('#lgOtpResend')) {
      event.preventDefault();
      if (target.closest('#lgOtpResend').disabled || state.busy) return;
      state.otpChallengeId = '';
      state.otpExpiresAt = 0;
      state.otpResendAt = 0;
      state.captchaToken = '';
      state.captchaImage = '';
      state.captchaFailed = false;
      renderPhoneLogin();
      setStatus('برای ارسال دوبارهٔ کد، کد امنیتی تازه را وارد کن و «دریافت کد» را بزن.', 'note');
      $('#lgCapAnswer')?.focus();
      return;
    }
    if (target.closest('#lgLogout')) {
      event.preventDefault();
      logout();
    }
  });

  document.addEventListener('click', (event) => {
    const target = event.target && event.target.closest ? event.target.closest('#lgCapNew') : null;
    if (target) loadCaptcha();
    const rules = event.target && event.target.closest ? event.target.closest('#rulesBtn') : null;
    if (rules && typeof window.openSheet === 'function') { event.preventDefault(); window.openSheet('shRules'); return; }
    const close = event.target && event.target.closest
      ? (event.target.closest('#shRules [data-close]') || event.target.closest('.scrim')) : null;
    if (close && typeof window.closeSheets === 'function') { event.preventDefault(); window.closeSheets(); }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || typeof window.closeSheets !== 'function') return;
    const sheet = $('#shRules');
    if (sheet && sheet.classList.contains('on')) { event.preventDefault(); window.closeSheets(); const btn = $('#rulesBtn'); if (btn && btn.focus) btn.focus(); }
  });

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!form || !form.id) return;
    event.preventDefault();
    if (form.id === 'lgPhoneForm') requestPhoneOtp(form);
    else if (form.id === 'lgPhoneCodeForm') verifyPhoneOtp(form);
    else if (form.id === 'lgStaffForm') staffLogin(form);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
}());
