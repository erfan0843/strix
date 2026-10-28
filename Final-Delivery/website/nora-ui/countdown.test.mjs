import assert from 'node:assert/strict';
import fs from 'node:fs';
import { JSDOM } from 'jsdom';

const source = fs.readFileSync(new URL('./countdown.js', import.meta.url), 'utf8');
const publicData = fs.readFileSync(new URL('./public-data.js', import.meta.url), 'utf8');

const serverNow = Date.parse('2026-10-21T12:00:00Z');
const browserNow = serverNow - 5 * 60_000; // مرورگر پنج دقیقه عقب است
const iso = ms => new Date(ms).toISOString();
const eventId = 'ev-qa-countdown';
const payload = {
  server_time: iso(serverNow),
  content: {
    people: [], articles: [], partners: [], library: [], cooperation: [],
    banner_settings: { enabled: true },
    events: [
      { id: eventId, t: 'رویداد آزمایشی', status: 'published', privacy: 'public', on: '1405/08/12',
        startsAt: iso(serverNow + 20 * 86_400_000), regClosesAt: iso(serverNow + 3 * 86_400_000 + 2 * 3_600_000 + 30 * 60_000),
        lifecycle: 'scheduled', regMode: 'auto', forms: [{ id: 'form-1', need: 'reg', n: 'فرم' }],
        registration: { state: 'open', reason: '', lifecycle: 'scheduled', opensAt: '', closesAt: iso(serverNow + 3 * 86_400_000 + 2 * 3_600_000 + 30 * 60_000),
          startsAt: iso(serverNow + 20 * 86_400_000), endsAt: '', countdownTo: iso(serverNow + 3 * 86_400_000 + 2 * 3_600_000 + 30 * 60_000), startsIn: iso(serverNow + 20 * 86_400_000) } },
      { id: 'ev-cancelled', t: 'لغوشده', status: 'published', privacy: 'public', on: '1405/08/13',
        registration: { state: 'cancelled', lifecycle: 'cancelled', countdownTo: iso(serverNow + 86_400_000), startsIn: iso(serverNow + 86_400_000) } },
      { id: 'ev-legacy', t: 'بدون زمان معتبر', status: 'published', privacy: 'public', on: '1405/08/14' },
      { id: 'ev-fake', t: 'شمارشگر جعلی', status: 'published', privacy: 'public', on: '1405/08/15',
        registration: { state: 'open', countdownTo: 'فردا', startsIn: 'not-a-date' } }
    ],
    banners: [
      { id: 'b-reg', status: 'published', t: 'ثبت‌نام', eventId, countdown: 'reg_close', countdownTo: iso(serverNow + 90_000), countdownEnded: false,
        afterEnd: 'message', afterEndText: 'تمام شد', href: `event.html?id=${eventId}`, primaryLabel: 'جزئیات',
        event: { id: eventId, t: 'رویداد آزمایشی', when: '۱۲ آبان', state: 'open', lifecycle: 'scheduled' } },
      { id: 'b-ended-hidden', status: 'published', t: 'تمام‌شدهٔ پنهان', countdown: 'campaign_end', countdownEnded: true, afterEnd: 'hide' },
      { id: 'b-ended-msg', status: 'published', t: 'تمام‌شده با پیام', countdown: 'campaign_end', countdownEnded: true, afterEnd: 'message', afterEndText: 'فرصت تمام شد' },
      { id: 'b-bad-target', status: 'published', t: 'هدف نامعتبر', countdown: 'campaign_end', countdownTo: 'next week', countdownEnded: false },
      { id: 'b-window', status: 'published', t: 'پنجرهٔ سرور', endsAt: iso(serverNow - 60_000) },
      { id: 'b-window-live', status: 'published', t: 'هنوز در بازه', endsAt: iso(serverNow + 2 * 60_000) }
    ]
  }
};

const dom = new JSDOM('<!doctype html><html><body><div id="host"></div></body></html>', {
  url: 'https://nora.test/home.html',
  runScripts: 'dangerously',
  beforeParse(window) {
    window.Date.now = () => browserNow;
    window.fetch = async () => ({ ok: true, json: async () => payload });
  }
});
const { window } = dom;
window.eval(publicData);
window.eval(source);
await window.NORA_PUBLIC_READY;
const CD = window.NORA_COUNTDOWN;

// ساعت سرور، نه مرورگر
assert.equal(window.NORA_SERVER_CLOCK.offsetMs, 5 * 60_000);
assert.equal(CD.serverNow(), serverNow);

// وضعیت و هدف رویداد از سرور
const event = window.NORA_PUBLIC.events.find(e => e.id === eventId);
assert.equal(event.registration.state, 'open');
const target = CD.eventTarget(event);
assert.equal(target.kind, 'reg_close');
assert.equal(target.at, event.registration.countdownTo);
const parts = CD.remaining(event.registration.countdownTo);
assert.deepEqual([parts.d, parts.h, parts.m, parts.s, parts.ended], [3, 2, 30, 0, false]);
assert.equal(CD.phrase(parts), '۳ روز و ۲ ساعت و ۳۰ دقیقه');
assert.equal(CD.stateLabel(event.registration), 'ثبت‌نام باز است');
assert.equal(CD.stateTone(event.registration), 'live');

// لغوشده: هیچ شمارشگری، نشان «لغو شد»
const cancelled = window.NORA_PUBLIC.events.find(e => e.id === 'ev-cancelled');
assert.equal(CD.eventTarget(cancelled), null);
assert.equal(CD.stateLabel(cancelled.registration), 'لغو شد');
assert.equal(CD.stateTone(cancelled.registration), 'stop');

// رویداد قدیمی بدون وضعیت سرور یا با هدف نامعتبر: شمارشگر ساخته نمی‌شود
const legacy = window.NORA_PUBLIC.events.find(e => e.id === 'ev-legacy');
assert.equal(legacy.registration, null);
assert.equal(CD.eventTarget(legacy), null);
assert.equal(CD.markup(CD.eventTarget(legacy)), '');
const fake = window.NORA_PUBLIC.events.find(e => e.id === 'ev-fake');
assert.equal(fake.registration.countdownTo, '');
assert.equal(CD.eventTarget(fake), null);
assert.equal(CD.markup({ kind: 'reg_close', at: 'فردا' }), '');

// زیر یک دقیقه، پایان‌یافته، بدون تاریخ
assert.equal(CD.phrase(CD.remaining(iso(serverNow + 30_000))), 'کمتر از یک دقیقه');
assert.equal(CD.remaining(iso(serverNow - 1)).ended, true);
assert.equal(CD.phrase(CD.remaining(iso(serverNow - 1))), 'به پایان رسید');
assert.equal(CD.remaining(''), null);
assert.equal(CD.remaining('garbage'), null);

// بنرها: پنجره با ساعت سرور، رفتار پس از پایان، هدف نامعتبر
const banners = Object.fromEntries(window.NORA_PUBLIC.banners.map(b => [b.id, b]));
assert.deepEqual(Object.keys(banners).sort(), ['b-bad-target', 'b-ended-msg', 'b-reg', 'b-window-live']);
assert.equal(banners['b-reg'].countdown, 'reg_close');
assert.equal(banners['b-reg'].countdownTo, payload.content.banners[0].countdownTo);
assert.equal(banners['b-reg'].event.id, eventId);
assert.equal(banners['b-ended-msg'].countdownEnded, true);
assert.equal(banners['b-ended-msg'].countdownTo, '');
assert.equal(banners['b-bad-target'].countdown, '');
assert.equal(banners['b-bad-target'].countdownTo, '');

// نشانه و تیک زنده؛ پایان → رویداد DOM، بدون تغییر وضعیت
const host = window.document.getElementById('host');
host.innerHTML = CD.markup({ kind: 'reg_close', at: iso(serverNow + 1500) }) + CD.markup({ kind: 'event_start', at: event.registration.startsIn }, { compact: true });
assert.equal(CD.mount(host), 2);
const timers = host.querySelectorAll('[data-countdown]');
assert.equal(timers[0].getAttribute('role'), 'timer');
assert.match(timers[0].textContent, /تا پایان ثبت‌نام/);
assert.match(timers[0].textContent, /کمتر از یک دقیقه/);
assert.match(timers[1].textContent, /روز/);
assert.ok(timers[1].classList.contains('is-compact'));
let endedEvents = 0;
host.addEventListener('nora:countdown-ended', () => { endedEvents += 1; });
window.Date.now = () => browserNow + 3000;
await new Promise(resolve => setTimeout(resolve, 1300));
assert.ok(timers[0].classList.contains('is-ended'), 'first timer should be ended');
assert.match(timers[0].textContent, /مهلت ثبت‌نام به پایان رسید/);
assert.equal(endedEvents, 1);
assert.ok(!timers[1].classList.contains('is-ended'));
window.close();
console.log('countdown.test.mjs: ok');
