/* شمارشگر مشترک نورا (خانه، کارت رویداد، صفحهٔ رویداد، بنر).
   قاعده‌ها:
   - زمان مبنا، ساعت سرور است: public-data.js اختلاف `server_time` را در
     `NORA_SERVER_CLOCK` می‌گذارد و این‌جا فقط از همان اختلاف استفاده می‌شود.
   - هدف شمارش فقط از مقادیر معتبر سرور (`registration.countdownTo`,
     `registration.startsIn`, `banner.countdownTo`) خوانده می‌شود؛ اگر هدف معتبر
     نباشد هیچ شمارشگری ساخته نمی‌شود (صادق، نه نمایشی).
   - رسیدن شمارشگر به صفر به‌تنهایی وضعیت ثبت‌نام را عوض نمی‌کند؛ رویداد
     `nora:countdown-ended` فرستاده می‌شود تا صفحه، عکس تازهٔ سرور را بگیرد. */
(function (root) {
  'use strict';
  const doc = root.document;
  const fa = value => {
    try { return new Intl.NumberFormat('fa-IR').format(Number(value) || 0); }
    catch (_) { return String(Number(value) || 0); }
  };
  const LABELS = {
    reg_close: 'تا پایان ثبت‌نام',
    reg_open: 'تا آغاز ثبت‌نام',
    event_start: 'تا شروع رویداد',
    campaign_end: 'تا پایان فرصت'
  };
  const ENDED = {
    reg_close: 'مهلت ثبت‌نام به پایان رسید',
    reg_open: 'ثبت‌نام آغاز شد؛ وضعیت از سرور به‌روز می‌شود',
    event_start: 'رویداد آغاز شده است',
    campaign_end: 'این فرصت به پایان رسید'
  };
  const STATES = {
    open: 'ثبت‌نام باز است',
    not_started: 'ثبت‌نام هنوز آغاز نشده',
    full: 'ظرفیت تکمیل شد',
    closed: 'ثبت‌نام بسته شد',
    ended: 'برگزار شد',
    cancelled: 'لغو شد',
    none: 'فرم ثبت‌نام منتشر نشده'
  };
  const LIFECYCLE = { cancelled: 'لغو شد', postponed: 'به تعویق افتاد' };

  function serverNow() {
    const clock = root.NORA_SERVER_CLOCK;
    const offset = clock && Number.isFinite(clock.offsetMs) ? clock.offsetMs : 0;
    return Date.now() + offset;
  }
  function parseTarget(value) {
    const text = String(value == null ? '' : value).trim();
    if (!text) return NaN;
    const ms = Date.parse(text);
    return Number.isFinite(ms) ? ms : NaN;
  }
  /* باقی‌مانده به روز/ساعت/دقیقه/ثانیه؛ `ended` وقتی هدف گذشته باشد */
  function remaining(target, now) {
    const ms = parseTarget(target);
    if (!Number.isFinite(ms)) return null;
    const diff = ms - (Number.isFinite(now) ? now : serverNow());
    const total = Math.max(0, Math.floor(diff / 1000));
    return {
      ended: diff <= 0,
      underMinute: diff > 0 && diff < 60_000,
      d: Math.floor(total / 86400),
      h: Math.floor((total % 86400) / 3600),
      m: Math.floor((total % 3600) / 60),
      s: total % 60,
      totalSeconds: total
    };
  }
  function phrase(parts) {
    if (!parts) return '';
    if (parts.ended) return 'به پایان رسید';
    if (parts.underMinute) return 'کمتر از یک دقیقه';
    const chunks = [];
    if (parts.d) chunks.push(`${fa(parts.d)} روز`);
    if (parts.h || parts.d) chunks.push(`${fa(parts.h)} ساعت`);
    chunks.push(`${fa(parts.m)} دقیقه`);
    if (!parts.d) chunks.push(`${fa(parts.s)} ثانیه`);
    return chunks.join(' و ');
  }
  function stateLabel(registration) {
    if (!registration || typeof registration !== 'object') return '';
    if (registration.lifecycle && LIFECYCLE[registration.lifecycle]) return LIFECYCLE[registration.lifecycle];
    return STATES[registration.state] || '';
  }
  /* نوع نشان وضعیت برای CSS: live / wait / stop / mute */
  function stateTone(registration) {
    const lifecycle = registration && registration.lifecycle;
    if (lifecycle === 'cancelled') return 'stop';
    if (lifecycle === 'postponed') return 'wait';
    const state = registration && registration.state;
    if (state === 'open') return 'live';
    if (state === 'not_started') return 'wait';
    if (state === 'full' || state === 'closed' || state === 'cancelled') return 'stop';
    return 'mute';
  }
  /* هدف شمارش یک رویداد از روی وضعیت سرور: اول مهلت ثبت‌نام، بعد شروع */
  function eventTarget(event) {
    const registration = event && event.registration;
    if (!registration || typeof registration !== 'object') return null;
    if (registration.lifecycle === 'cancelled' || registration.lifecycle === 'postponed') return null;
    if (registration.state === 'open' && registration.countdownTo) return { kind: 'reg_close', at: registration.countdownTo };
    if (registration.state === 'not_started' && registration.countdownTo) return { kind: 'reg_open', at: registration.countdownTo };
    if (registration.startsIn && ['open', 'none', 'full', 'closed'].includes(registration.state)) return { kind: 'event_start', at: registration.startsIn };
    return null;
  }
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  /* بلوک‌های عددی (روز/ساعت/دقیقه/ثانیه) فقط نمایشی‌اند (aria-hidden)؛ متن کامل در
     `.nora-countdown-value` می‌ماند تا صفحه‌خوان و آزمون‌ها همان عبارت قبلی را بخوانند.
     قاعدهٔ نمایش واحدها همان قاعدهٔ `phrase()` است: با وجود روز، ثانیه پنهان می‌شود و
     بدون روز، بلوک روز پنهان است (`data-cd-units`). */
  const UNITS = [['d', 'روز'], ['h', 'ساعت'], ['m', 'دقیقه'], ['s', 'ثانیه']];
  const two = value => fa(value).padStart(2, fa(0));
  function unitText(parts, unit) {
    const value = parts ? parts[unit] : 0;
    return unit === 'd' ? fa(value) : two(value);
  }
  function blocksMarkup(parts) {
    return `<span class="nora-countdown-blocks" aria-hidden="true">` + UNITS.map(([unit, name]) =>
      `<span class="cdb" data-unit="${unit}"><b class="cdb-n">${unitText(parts, unit)}</b><i class="cdb-u">${name}</i></span>`
    ).join('') + `</span>`;
  }
  /* نشانهٔ HTML؛ `data-countdown` بعداً با `mount()` زنده می‌شود.
     گزینه‌ها: compact (کارت‌ها)، hero (بنر/خانه)، label (متن سرآیند) */
  function markup(target, options) {
    const opts = options || {};
    if (!target || !Number.isFinite(parseTarget(target.at))) return '';
    const kind = LABELS[target.kind] ? target.kind : 'campaign_end';
    const parts = remaining(target.at);
    const label = opts.label || LABELS[kind];
    const size = opts.compact ? ' is-compact' : opts.hero ? ' is-hero' : '';
    const ended = !!(parts && parts.ended);
    return `<span class="nora-countdown${size}${ended ? ' is-ended' : ''}" data-countdown="${esc(target.at)}" data-countdown-kind="${esc(kind)}" data-cd-units="${parts && parts.d ? 'dhm' : 'hms'}" role="timer" aria-live="off" aria-label="${esc(label)}">`
      + `<span class="nora-countdown-head"><svg class="i" aria-hidden="true"><use href="#i-clock"/></svg>`
      + `<span class="nora-countdown-label">${esc(label)}</span></span>`
      + blocksMarkup(parts)
      + `<b class="nora-countdown-value">${esc(ended ? ENDED[kind] : phrase(parts))}</b></span>`;
  }
  const timers = new WeakMap();
  /* تغییر عدد یک بلوک؛ کلاس `is-tick` فقط یک حرکت کوتاه CSS است که زیر
     prefers-reduced-motion خنثی می‌شود (در countdown.css) */
  function setNumber(node, text) {
    if (!node || node.textContent === text) return;
    node.textContent = text;
    node.classList.remove('is-tick');
    void node.offsetWidth;
    node.classList.add('is-tick');
  }
  function tick(element) {
    const parts = remaining(element.dataset.countdown);
    const kind = element.dataset.countdownKind || 'campaign_end';
    const value = element.querySelector('.nora-countdown-value');
    if (!parts) { element.hidden = true; return false; }
    if (value) value.textContent = parts.ended ? (ENDED[kind] || 'به پایان رسید') : phrase(parts);
    element.dataset.cdUnits = parts.d ? 'dhm' : 'hms';
    UNITS.forEach(([unit]) => setNumber(element.querySelector(`.cdb[data-unit="${unit}"] .cdb-n`), unitText(parts, unit)));
    element.classList.toggle('is-ended', parts.ended);
    element.classList.toggle('is-soon', !parts.ended && parts.totalSeconds < 3600);
    if (parts.ended && element.dataset.countdownEnded !== '1') {
      element.dataset.countdownEnded = '1';
      try { element.dispatchEvent(new root.CustomEvent('nora:countdown-ended', { bubbles: true, detail: { kind, at: element.dataset.countdown } })); }
      catch (_) { /* محیط بدون CustomEvent */ }
    }
    return !parts.ended;
  }
  /* همهٔ `[data-countdown]` داخل ریشه را زنده می‌کند؛ ثانیه‌ای، با توقف خودکار پس از پایان */
  function mount(scope) {
    const host = scope && scope.querySelectorAll ? scope : doc;
    if (!host) return 0;
    let count = 0;
    host.querySelectorAll('[data-countdown]').forEach(element => {
      count += 1;
      if (timers.has(element)) return;
      if (!tick(element)) return;
      const interval = root.setInterval(() => {
        if (!element.isConnected) { root.clearInterval(interval); timers.delete(element); return; }
        if (!tick(element)) { root.clearInterval(interval); timers.delete(element); }
      }, 1000);
      timers.set(element, interval);
    });
    return count;
  }
  /* نمایش یک لحظهٔ UTC سرور به وقت مرجع (همان منطقهٔ زمانی backend/event_time.py: Asia/Tehran) با تقویم شمسی */
  function formatMoment(value, options) {
    const ms = parseTarget(value);
    if (!Number.isFinite(ms)) return '';
    const opts = options || {};
    try {
      return new Intl.DateTimeFormat('fa-IR-u-ca-persian', Object.assign({ timeZone: 'Asia/Tehran', dateStyle: 'medium' }, opts.dateOnly ? {} : { timeStyle: 'short' })).format(new Date(ms));
    } catch (_) {
      try { return new Date(ms).toLocaleString('fa-IR', { timeZone: 'Asia/Tehran' }); } catch (__) { return new Date(ms).toISOString(); }
    }
  }
  root.NORA_COUNTDOWN = { serverNow, remaining, phrase, markup, mount, eventTarget, stateLabel, stateTone, formatMoment, LABELS, STATES, ENDED };
})(typeof window === 'undefined' ? globalThis : window);
