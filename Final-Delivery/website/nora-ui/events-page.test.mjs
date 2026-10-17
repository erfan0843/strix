/* آزمون صفحهٔ عمومی رویدادها روی عکس سرور (بدون فیکسچر محلی):
   صافی نوع/شیوه از رکوردهای واقعی، مرتب‌سازی، نمای تقویم از تاریخ ماشین‌خوان (on)،
   هش‌های قدیمی (#cal/#lib/#upcoming) و نبودِ دادهٔ نمایشی در تولید. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import jsdom from 'jsdom';

const { JSDOM } = jsdom;
/* فقط فایل‌های محلی بارگذاری می‌شوند؛ هیچ درخواست شبکه‌ای از صفحه بیرون نمی‌رود. */
const localOnly = {
  interceptors: [jsdom.requestInterceptor(async request => {
    if (new URL(request.url).protocol !== 'file:') return new Response('', { status: 403 });
    return undefined;
  })]
};
const DIR = fileURLToPath(new URL('./', import.meta.url));
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

const content = {
  events: [
    { id: 'ev-late', t: 'نشست پاییزی', kind: 'نشست', privacy: 'public', d: 'شرح', when: 'دوشنبه ۲۰ مهر', on: '۱۴۰۵/۰۷/۲۰',
      time: '۱۸:۰۰', place: 'https://meet.example/room', price: 500000, cap: 40, tags: ['پاییز'], forms: [{ id: 'f-late', need: 'reg', n: 'ثبت‌نام' }] },
    { id: 'ev-soon', t: 'کارگاه عکاسی', kind: 'کارگاه', privacy: 'public', d: 'شرح', when: 'جمعه ۱۰ مهر', on: '1405/07/10',
      time: '۱۶:۰۰', place: 'سالن اصلی', mode: 'حضوری', price: 0, cap: 20 },
    { id: 'ev-undated', t: 'پویش بدون تاریخ', kind: 'پویش', privacy: 'public', d: 'شرح', when: 'به‌زودی', price: 1200000 },
    { id: 'ev-past', t: 'کارگاه برگزارشده', kind: 'کارگاه', privacy: 'public', past: true, when: 'شنبه ۵ مهر', on: '۱۴۰۵/۰۷/۰۵',
      place: 'سالن اصلی', price: 300000, media: [{ id: 'm1', k: 'audio', t: 'صوت جلسه', src: 'https://cdn.example/a.mp3' }] },
    { id: 'ev-draft', t: 'پیش‌نویس', kind: 'کارگاه', privacy: 'public', status: 'draft', on: '۱۴۰۵/۰۷/۱۱' },
    { id: 'ev-private', t: 'خصوصی', kind: 'کارگاه', privacy: 'private', on: '۱۴۰۵/۰۷/۱۲' },
    { id: 'ev-aban', t: 'اردوی آبان', kind: 'اردو', privacy: 'public', when: 'آبان', on: '۱۴۰۵/۰۸/۰۳', place: 'طبیعت', price: 900000 }
  ],
  people: [], articles: [], partners: [], banners: [], library: [], cooperation: []
};

async function load(query = '', { events = content.events, fixtureMode = false, file = 'events.html', siteContentStatus = 200 } = {}) {
  const errors = [], network = [];
  const url = pathToFileURL(DIR + file).href + query;
  const dom = await JSDOM.fromFile(DIR + file, {
    url, runScripts: 'dangerously', pretendToBeVisual: true, resources: localOnly,
    beforeParse(w) {
      w.scrollTo = () => {};
      if (w.Element && !w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView = () => {};
      if (!w.matchMedia) w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      w.__NORA_TEST_FIXTURE_MODE__ = fixtureMode;
      w.fetch = async path => {
        network.push(String(path));
        if (String(path) === '/api/public/site-content') return { ok: siteContentStatus === 200, status: siteContentStatus, json: async () => ({ content: { ...content, events } }) };
        throw new Error('network disabled: ' + path);
      };
      w.addEventListener('error', e => errors.push('error: ' + (e.message || '')));
      w.console.error = (...args) => errors.push('console.error: ' + args.join(' '));
    }
  });
  const { window } = dom;
  if (window.document.readyState !== 'complete') await new Promise(resolve => {
    const timer = setTimeout(resolve, 5000);
    window.addEventListener('load', () => { clearTimeout(timer); resolve(); }, { once: true });
  });
  if (window.NORA_PUBLIC_READY) await window.NORA_PUBLIC_READY;
  await wait(40);
  const doc = window.document;
  return {
    window, doc, errors, network,
    all: selector => [...doc.querySelectorAll(selector)],
    ids: () => [...doc.querySelectorAll('#eventsList [data-event-id]')].map(el => el.dataset.eventId),
    click: selector => { const el = doc.querySelector(selector); if (!el) throw new Error('نیست: ' + selector);
      el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true })); },
    txt: selector => { const el = doc.querySelector(selector); return el ? el.textContent.replace(/\s+/g, ' ').trim() : ''; }
  };
}

let passed = 0, failed = 0;
function ok(condition, label) {
  if (condition) { passed++; console.log('   ✓ ' + label); }
  else { failed++; console.log('   ✗ ' + label); }
}

/* ۱) فهرست از سرور، بدون فیکسچر؛ پیش‌نویس/خصوصی حذف؛ ترتیب «نزدیک‌ترین» */
{
  const p = await load();
  ok(p.errors.length === 0, 'بدون خطای کنسول: ' + p.errors.join(' | '));
  ok(p.network.includes('/api/public/site-content'), 'داده از /api/public/site-content خوانده شد');
  ok(p.window.NORA_PUBLIC_SOURCE === 'server' && !p.window.NORA.EVENTS?.length === false || p.window.NORA_PUBLIC_SOURCE === 'server',
    'منبع داده سرور است');
  const ids = p.ids();
  ok(!ids.includes('ev-draft') && !ids.includes('ev-private'), 'پیش‌نویس و خصوصی در فهرست عمومی نیستند');
  ok(JSON.stringify(ids) === JSON.stringify(['ev-soon', 'ev-late', 'ev-aban', 'ev-undated', 'ev-past']),
    'ترتیب نزدیک‌ترین: پیش‌روها صعودی به تاریخ، بی‌تاریخ در انتها، سپس برگزارشده‌ها: ' + ids.join(','));
  ok(p.txt('#eventsCount').startsWith('۵ رویداد'), 'شمار نتیجه از رکوردهای واقعی: ' + p.txt('#eventsCount'));
  ok(!p.doc.querySelector('#eventToolbar').hidden, 'نوار ابزار با وجود رکورد نمایان است');
  const kinds = p.all('[data-event-kind]').map(el => el.dataset.eventKind);
  ok(JSON.stringify(kinds) === JSON.stringify(['کارگاه', 'اردو', 'پویش', 'نشست']), 'چیپ‌های نوع از رکوردها و مرتب به شمار: ' + kinds.join(','));
  ok(p.txt('[data-event-kind="کارگاه"]').includes('۲'), 'شمار چیپ نوع واقعی است');
  const modes = p.all('[data-event-mode]').map(el => el.dataset.eventMode);
  ok(modes.includes('حضوری') && modes.includes('آنلاین'), 'شیوهٔ برگزاری از mode یا مکان استخراج شد: ' + modes.join(','));
  ok(p.all('.event-list-card .cover-state').length === 1, 'نشان «برگزارشده» فقط روی رویداد گذشته');
  ok(p.txt('[data-event-id="ev-past"] .event-list-meta').includes('۱ رسانهٔ منتشرشده'), 'شمار رسانهٔ آرشیو از رکورد سرور');
  ok(p.doc.querySelector('[data-event-id="ev-late"] a[href="form.html?fid=f-late&kind=reg"]') !== null, 'دکمهٔ ثبت‌نام به فرم منتشرشده');
  ok(p.txt('[data-event-id="ev-soon"] .event-list-actions').includes('فرم ثبت‌نام منتشر نشده'), 'بدون فرم: پیام صادقانه، نه دکمهٔ مرده');
  p.window.close();
}

/* ۲) صافی نوع و شیوه، برداشتن با کلیک دوباره، ترکیب با وضعیت */
{
  const p = await load();
  p.click('[data-event-kind="کارگاه"]');
  ok(JSON.stringify(p.ids()) === JSON.stringify(['ev-soon', 'ev-past']), 'صافی نوع «کارگاه»: ' + p.ids().join(','));
  ok(p.txt('#eventsCount').includes('کارگاه'), 'شمار نتیجه صافی را می‌گوید');
  ok(!p.doc.querySelector('#eventFacetReset').hidden, 'دکمهٔ برداشتن صافی‌ها پیدا شد');
  p.click('[data-event-filter="upcoming"]');
  ok(JSON.stringify(p.ids()) === JSON.stringify(['ev-soon']), 'ترکیب نوع + پیش‌رو: ' + p.ids().join(','));
  p.click('[data-event-kind="کارگاه"]');
  ok(JSON.stringify(p.ids()) === JSON.stringify(['ev-soon', 'ev-late', 'ev-aban', 'ev-undated']), 'کلیک دوباره صافی را برمی‌دارد');
  p.click('[data-event-mode="آنلاین"]');
  ok(JSON.stringify(p.ids()) === JSON.stringify(['ev-late']), 'صافی شیوهٔ آنلاین (مکان = پیوند): ' + p.ids().join(','));
  p.click('#eventFacetReset');
  ok(p.ids().length === 4 && p.doc.querySelector('#eventFacetReset').hidden, 'برداشتن همهٔ صافی‌ها');
  p.window.close();
}

/* ۳) مرتب‌سازی */
{
  const p = await load();
  const sort = p.doc.querySelector('#eventSort');
  sort.value = 'cheap'; sort.dispatchEvent(new p.window.Event('change', { bubbles: true }));
  ok(p.ids()[0] === 'ev-soon' && p.ids()[p.ids().length - 1] === 'ev-undated', 'ارزان‌ترین: رایگان اول، گران‌ترین آخر: ' + p.ids().join(','));
  sort.value = 'dear'; sort.dispatchEvent(new p.window.Event('change', { bubbles: true }));
  ok(p.ids()[0] === 'ev-undated', 'گران‌ترین اول');
  sort.value = 'title'; sort.dispatchEvent(new p.window.Event('change', { bubbles: true }));
  const titles = p.all('#eventsList .event-list-title').map(el => el.textContent);
  ok(JSON.stringify(titles) === JSON.stringify(titles.slice().sort((a, b) => a.localeCompare(b, 'fa'))), 'ترتیب نام فارسی');
  p.window.close();
}

/* ۴) نمای تقویم از تاریخ ماشین‌خوان (on)، با ارقام فارسی و لاتین؛ بی‌تاریخ فقط در فهرست */
{
  const p = await load('#cal');
  ok(p.window.NORA_EVENTS_PAGE.state.view === 'cal', 'هش #cal نمای تقویم را باز می‌کند');
  ok(!p.doc.querySelector('#eventCalendar').hidden && p.doc.querySelector('#eventsList').hidden, 'تقویم نمایان، فهرست پنهان');
  const months = p.all('[data-event-month]').map(el => el.dataset.eventMonth);
  ok(JSON.stringify(months) === JSON.stringify(['1405-7', '1405-8']), 'ماه‌ها فقط از تاریخ‌های واقعی: ' + months.join(','));
  ok(p.txt('[data-event-month="1405-7"]').includes('مهر') && p.txt('[data-event-month="1405-7"]').includes('۳'), 'برچسب ماه و شمار (۳ برنامه در مهر)');
  const hasDays = p.all('.event-cal-cell.has').map(el => el.dataset.eventDay);
  ok(JSON.stringify(hasDays) === JSON.stringify(['5', '10', '20']), 'روزهای دارای برنامه در مهر: ' + hasDays.join(','));
  ok(p.all('.event-cal-cell:not(.blank)').length === 30, 'مهر ۳۰ روز دارد');
  ok(p.all('.event-cal-wd').length === 7 && p.txt('.event-cal-wd') === 'ش', 'هفته از شنبه آغاز می‌شود');
  const blanks = p.all('.event-cal-cell.blank').length;
  ok(blanks === 4, '۱ مهر ۱۴۰۵ چهارشنبه است (۴ خانهٔ خالی پیش از آن)، یافت: ' + blanks);
  ok(p.doc.querySelector('.event-cal-cell[data-event-day="5"]').classList.contains('was'), 'روز با برنامهٔ فقط‌برگزارشده نشان was دارد');
  ok(p.txt('#eventCalendarNote').includes('۱ رویداد بدون تاریخ'), 'یادداشت رویداد بی‌تاریخ: ' + p.txt('#eventCalendarNote'));
  p.click('.event-cal-cell[data-event-day="20"]');
  ok(p.txt('#eventDayTitle') === 'دوشنبه ۲۰ مهر ۱۴۰۵', 'عنوان روز با نام روز هفتهٔ درست: ' + p.txt('#eventDayTitle'));
  ok(p.all('#eventDayList [data-event-id]').map(el => el.dataset.eventId).join() === 'ev-late', 'کارت همان روز');
  p.click('[data-event-month="1405-8"]');
  ok(p.all('.event-cal-cell:not(.blank)').length === 30 && p.all('.event-cal-cell.has').length === 1, 'آبان: ۳۰ روز، یک برنامه');
  ok(p.txt('#eventDayTitle').includes('آبان'), 'روز نخستِ دارای برنامه در ماه تازه انتخاب شد');
  p.click('[data-event-view="list"]');
  ok(!p.doc.querySelector('#eventsList').hidden && p.doc.querySelector('#eventCalendar').hidden && p.window.NORA_EVENTS_PAGE.state.view === 'list',
    'بازگشت به فهرست (replaceState روی file:// در jsdom مجاز نیست و بی‌صدا نادیده گرفته می‌شود)');
  p.window.close();
}

/* ۵) هش‌های قدیمی پیوندها: #upcoming و #lib خطا نمی‌دهند و وضعیت درست می‌گیرند */
{
  const up = await load('#upcoming');
  ok(up.errors.length === 0 && !up.ids().includes('ev-past'), '#upcoming فقط پیش‌روها');
  up.window.close();
  const lib = await load('#lib');
  ok(lib.errors.length === 0 && JSON.stringify(lib.ids()) === JSON.stringify(['ev-past']), '#lib (کتابخانه) = آرشیو برگزارشده‌ها');
  lib.window.close();
  const q = await load('?status=past&kind=کارگاه');
  ok(JSON.stringify(q.ids()) === JSON.stringify(['ev-past']) && q.window.NORA_EVENTS_PAGE.state.kind === 'کارگاه', 'پارامترهای status و kind از نشانی');
  const bad = await load('?kind=ناموجود');
  ok(bad.window.NORA_EVENTS_PAGE.state.kind === '', 'kind ناشناخته نادیده گرفته می‌شود');
  q.window.close(); bad.window.close();
}

/* ۶) تولید بدون رویداد: هیچ دادهٔ نمایشی، پیام صادقانه، تقویم خالی بی‌خطا */
{
  const p = await load('#cal', { events: [] });
  ok(p.errors.length === 0, 'بدون خطا با فهرست خالی');
  ok(p.ids().length === 0 && p.doc.querySelector('#eventToolbar').hidden, 'بدون رکورد: نه کارت، نه نوار ابزار');
  ok(p.txt('#eventCalendarNote') === 'هنوز رویدادی منتشر نشده است.', 'یادداشت تقویم خالی');
  p.click('[data-event-view="list"]');
  ok(!p.doc.querySelector('#eventsEmpty').hidden && p.txt('#eventsEmptyMessage').includes('منتشر نشده'), 'حالت خالی فهرست');
  ok(!(p.window.NORA && Array.isArray(p.window.NORA.EVENTS) && p.window.NORA.EVENTS.length), 'data.js نمونه بارگذاری نشده است');
  p.window.close();
}

/* ۷) تجزیهٔ تاریخ و شیوه، مستقیم */
{
  const p = await load();
  const { parseJalali, modeOf } = p.window.NORA_EVENTS_PAGE;
  ok(JSON.stringify(parseJalali('۱۴۰۳/۱۲/۳۰')) === JSON.stringify({ jy: 1403, jm: 12, jd: 30 }), '۱۴۰۳ کبیسه است: ۳۰ اسفند معتبر');
  ok(parseJalali('1404/12/30') === null, '۱۴۰۴ کبیسه نیست: ۳۰ اسفند نامعتبر');
  ok(parseJalali('جمعه ۱۰ مهر') === null && parseJalali('') === null, 'متن آزاد تاریخ ماشینی نیست');
  ok(JSON.stringify(parseJalali('1405-07-10 16:00')) === JSON.stringify({ jy: 1405, jm: 7, jd: 10 }), 'جداکنندهٔ خط تیره و دنبالهٔ ساعت');
  ok(modeOf({ place: 'https://x.example' }) === 'آنلاین' && modeOf({ place: 'سالن' }) === 'حضوری'
    && modeOf({ mode: 'حضوری و آنلاین' }) === 'حضوری و آنلاین' && modeOf({}) === '', 'استخراج شیوهٔ برگزاری');
  p.window.close();
}

/* ۸) صفحهٔ رویداد: «برنامه‌های دیگر» از همان عکس سرور، هم‌وضعیت، اول هم‌نوع، بدون خود رویداد */
{
  const p = await load('?id=ev-soon', { file: 'event.html' });
  ok(p.errors.length === 0, 'صفحهٔ رویداد بدون خطا');
  const related = p.all('[data-related-event]').map(el => el.dataset.relatedEvent);
  ok(JSON.stringify(related) === JSON.stringify(['ev-late', 'ev-undated', 'ev-aban']),
    'پیش‌رو: فقط پیش‌روهای دیگر (ev-past حذف)، بدون خود رویداد: ' + related.join(','));
  ok(p.doc.querySelector('.event-related .back-link')?.getAttribute('href') === 'events.html?status=upcoming', 'پیوند «همهٔ برنامه‌های پیش‌رو»');
  p.window.close();
  const past = await load('?id=ev-past', { file: 'event.html' });
  ok(past.all('[data-related-event]').length === 0 && past.doc.querySelector('.event-related') === null,
    'برگزارشدهٔ تنها: بخش «برنامه‌های دیگر» اصلاً ساخته نمی‌شود (نه فهرست خالی)');
  past.window.close();
  const kindFirst = await load('?id=ev-aban', { file: 'event.html', events: content.events.concat([
    { id: 'ev-aban-2', t: 'اردوی دوم', kind: 'اردو', privacy: 'public', when: 'آذر', on: '۱۴۰۵/۰۹/۰۱' }]) });
  ok(kindFirst.all('[data-related-event]')[0]?.dataset.relatedEvent === 'ev-aban-2', 'هم‌نوع‌ها اول می‌آیند');
  kindFirst.window.close();
}

/* ۹) نسخهٔ فایل‌ها در صفحه */
{
  const html = fs.readFileSync(DIR + 'events.html', 'utf8');
  ok(html.includes('events-page.js?v=102') && html.includes('events-page.css?v=101'), 'نسخهٔ اسکریپت/استایل صفحه جلو رفته است');
  ok(/__NORA_TEST_FIXTURE_MODE__===true\)document\.write/.test(html), 'data.js فقط در حالت آزمون صریح');
  const detail = fs.readFileSync(DIR + 'event.html', 'utf8');
  ok(detail.includes('event-page.js?v=101'), 'نسخهٔ اسکریپت صفحهٔ رویداد جلو رفته است');
}

/* ۱۱) خطای API (مثلاً ۵۰۳): صفحهٔ رویدادها «منتشر نشده» نمی‌گوید؛ نبودِ دسترسی به سرور را روشن می‌گوید */
{
  const p = await load('', { events: [] , siteContentStatus: 503 });
  ok(p.window.NORA_PUBLIC_SOURCE === 'unavailable', 'منبع محتوای عمومی در خطای سرور unavailable است');
  ok(/دسترسی نیست/.test(p.txt('#eventsEmptyMessage')) && !/منتشر نشده/.test(p.txt('#eventsEmptyMessage')), 'پیام خالی‌بودن فهرست، خطای سرور را با «رویدادی منتشر نشده» اشتباه نمی‌گیرد');
  ok(p.errors.length === 0, 'بدون خطای JavaScript');
  p.window.close();
}

/* ۱۰) کلید شب/روز در صفحه‌هایی که initUI را صدا نمی‌زنند هم واقعاً کار می‌کند (ui.js آن را یک‌جا وصل می‌کند) */
for (const file of ['events.html', 'event.html']) {
  const p = await load(file === 'event.html' ? '?id=ev-1' : '', { file });
  const root = p.doc.documentElement;
  const now = () => (root.dataset.theme === 'dark' ? 'dark' : 'light');
  const t0 = now();
  p.click('[data-theme-toggle]');
  const t1 = now();
  p.click('[data-theme-toggle]');
  ok(t1 !== t0 && now() === t0, file + ': هر کلیک روی کلید شب/روز دقیقاً یک بار تم را عوض می‌کند');
  ok(p.doc.querySelector('[data-theme-toggle]').getAttribute('aria-checked') === (t0 === 'dark' ? 'true' : 'false'), file + ': وضعیت aria-checked کلید با تم هم‌گام است');
  p.window.close();
}

console.log(`\nevents-page: ${passed} قبول، ${failed} خطا`);
process.exit(failed ? 1 : 0);
