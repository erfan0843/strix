/* فاز ۹ — صفحهٔ عمومی رویداد و فهرست رویدادها: محصول ضبط‌شده با CTA سروری، سفارش کارت‌به‌کارت و رسید، فایل‌های قفل/باز،
   فروش متوقف، پیش‌نمایش، و صافی «ضبط‌شده» در آرشیو. در jsdom با fetch شبیه‌سازی‌شده؛ هیچ سروری اجرا نمی‌شود.
   تصمیم دسترسی و نوع دکمه در سرور است؛ این‌جا فقط باید همان پاسخ صادقانه بازتاب یابد. */
import { fileURLToPath, pathToFileURL } from 'node:url';
import jsdom from 'jsdom';
const { JSDOM } = jsdom;
const DIR = fileURLToPath(new URL('./', import.meta.url));
let checks = 0, fails = 0;
const ok = (condition, message) => { checks++; if (!condition) { fails++; console.log('   ✗ ' + message); } else console.log('   ✓ ' + message); };
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const EV = 'ev-qa-phase9';
const REC = '99999999-9999-4999-8999-999999999999';
const SESS = '55555555-5555-4555-8555-555555555551';
const VID = '11111111-1111-4111-8111-111111111119';
const PDF = '11111111-1111-4111-8111-111111111120';
const ORDER = '77777777-7777-4777-8777-777777777771';
const FORM = '88888888-8888-4888-8888-888888888881';
const card = { id: REC, status: 'published', sellable: true, title: 'ضبط کارگاه نجوم', summary: 'سه جلسه دربارهٔ آسمان شب', price: 1500000, currency: 'IRR', free: false, access_days: null, cover_url: '', session_count: 1, total_minutes: 95, published_at: '2026-10-21T06:00:00Z' };
const heldEvent = { id: EV, t: 'کارگاه نجوم', kind: 'کارگاه', privacy: 'public', past: true, when: '۲۰ مهر', on: '۱۴۰۵/۰۷/۲۰', place: 'رصدخانه', price: 300000, d: 'شرح کارگاه.',
  registration: { state: 'ended', reason: '', lifecycle: 'scheduled', opensAt: '', closesAt: '', startsAt: '', endsAt: '', countdownTo: '', startsIn: '' }, forms: [{ id: 'form-qa-1', need: 'reg', n: 'فرم' }], recording: card };
const content = { events: [heldEvent], people: [], partners: [], posts: [], banners: [], library: [], cooperation: [], banner_settings: {} };
const interaction = () => ({ source: 'shared_server_database', server_time: new Date().toISOString(),
  event: { id: EV, title: 'کارگاه نجوم', published: true, lifecycle: 'scheduled', held: true, qa_open: true, qa_closed_reason: '' },
  viewer: { signed_in: false, staff: false, buyer: false, participation: { registered: false, attended: false, pending: false } },
  resources: [], questions: { items: [], total: 0, mine_pending: 0 }, reviews: { eligible: false, badge: '', items: [], total: 0, mine: null } });
function product(viewerKind, extra = {}) {
  const signedIn = viewerKind !== 'guest';
  const allowed = viewerKind === 'buyer';
  const res = (id, title, type, delivery, allowedHere, reason, previewOpen) => ({ id, kind: 'file', title, description: '', access: 'purchased', delivery, file_name: title, content_type: type, size: 4096, published: true, publish_at: '',
    allowed: allowedHere, reason, playable: type === 'video/mp4', downloadable: delivery === 'download', preview: previewOpen });
  const cta = extra.cta || (viewerKind === 'guest' ? { kind: 'login', reason: 'login_required', methods: ['card_transfer'] }
    : viewerKind === 'buyer' ? { kind: 'view', reason: 'purchased', methods: ['card_transfer'] }
      : { kind: 'buy', reason: 'purchase_required', methods: ['card_transfer'], form_id: FORM });
  return { recording: {
    id: REC, event_id: EV, status: extra.status || 'published', title: 'ضبط کارگاه نجوم', summary: 'سه جلسه دربارهٔ آسمان شب.', outcomes: 'شناخت صور فلکی', audience: 'علاقه‌مندان', access_terms: 'مشاهدهٔ برخط؛ جزوه قابل دانلود', refund_policy: 'تا ۷ روز با درخواست کتبی',
    faq: [{ q: 'آیا دانلود دارد؟', a: 'جزوه بله، ویدئو خیر.' }], price: extra.price == null ? 1500000 : extra.price, currency: 'IRR', free: extra.price === 0, access_days: 90, attendee_access: false, download_default: true, cover_url: '', published_at: '2026-10-21T06:00:00Z',
    session_count: 1, total_minutes: 95,
    sessions: [{ id: SESS, title: 'جلسهٔ یکم: آسمان شب', description: '', sort_order: 1, duration_minutes: 95, preview: false, status: 'published', resources: [
      res(VID, 'ویدئوی جلسه', 'video/mp4', 'view', allowed, allowed ? 'purchased' : (signedIn ? 'purchase_required' : 'login_required'), false),
      res(PDF, 'جزوهٔ جلسه', 'application/pdf', 'download', true, allowed ? 'purchased' : 'preview', true) ] }],
    viewer: { signed_in: signedIn, staff: false, access: { state: allowed ? 'active' : 'none', allowed, reason: allowed ? 'purchased' : (signedIn ? 'purchase_required' : 'login_required'), source: allowed ? 'purchase' : '', expires_at: allowed ? '2027-01-19T06:00:00Z' : '' }, cta } } };
}
async function load({ events = content.events, recording = product('guest'), cookie = '', onFetch = null, hash = '', file = 'event.html', interactionPatch = null } = {}) {
  const errors = [], calls = [];
  let current = recording;
  const dom = await JSDOM.fromFile(DIR + file, { url: pathToFileURL(DIR + file).href + (file === 'event.html' ? '?id=' + EV : '') + hash, runScripts: 'dangerously', pretendToBeVisual: true,
    resources: { interceptors: [jsdom.requestInterceptor(async request => new URL(request.url).protocol === 'https:' ? new Response('', { status: 403 }) : undefined)] },
    beforeParse(w) {
      w.scrollTo = () => {}; if (w.Element && !w.Element.prototype.scrollIntoView) w.Element.prototype.scrollIntoView = () => {};
      if (!w.matchMedia) w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {} });
      w.__NORA_TEST_FIXTURE_MODE__ = false; w.confirm = () => true;
      if (w.HTMLMediaElement) { w.HTMLMediaElement.prototype.load = () => {}; w.HTMLMediaElement.prototype.pause = () => {}; }
      if (cookie) Object.defineProperty(w.document, 'cookie', { configurable: true, get: () => cookie, set() {} });
      w.fetch = async (path, init = {}) => {
        const url = String(path || ''); calls.push({ url, init });
        if (onFetch) { const custom = await onFetch(url, init, { set: value => { current = value; } }); if (custom) return custom; }
        if (url === '/api/public/site-content') return { ok: true, status: 200, json: async () => ({ content: { ...content, events }, server_time: new Date().toISOString() }) };
        if (url === '/api/public/events/' + EV + '/interaction') return { ok: true, status: 200, json: async () => interactionPatch ? interactionPatch(interaction()) : interaction() };
        if (url === '/api/public/events/' + EV + '/recording') {
          if (current === 'missing') return { ok: false, status: 404, json: async () => ({ detail: 'recording_not_found' }) };
          if (current === 'fail') return { ok: false, status: 500, json: async () => ({ detail: 'boom' }) };
          return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(current)) };
        }
        return { ok: false, status: 404, json: async () => ({}) };
      };
      w.addEventListener('error', e => errors.push('error: ' + (e.message || '')));
      w.console.error = (...args) => errors.push('console.error: ' + args.join(' '));
    } });
  const { window } = dom;
  if (window.document.readyState !== 'complete') await new Promise(resolve => { const t = setTimeout(resolve, 5000); window.addEventListener('load', () => { clearTimeout(t); resolve(); }, { once: true }); });
  await wait(150);
  const doc = window.document;
  return { dom, window, doc, errors, calls, txt: s => { const el = doc.querySelector(s); return el ? el.textContent.replace(/\s+/g, ' ').trim() : ''; }, click: s => { const el = doc.querySelector(s); if (!el) throw new Error('عنصر پیدا نشد: ' + s); el.dispatchEvent(new window.MouseEvent('click', { bubbles: true, cancelable: true })); return el; } };
}

console.log('\n— مهمان روی رویداد برگزارشده با محصول منتشرشده: بخش محصول، CTA ورود، بدون شمارش معکوس، فایل قفل —');
{
  const p = await load();
  ok(p.errors.length === 0, 'صفحه بدون خطای JavaScript بار شد' + (p.errors.length ? ': ' + p.errors[0] : ''));
  ok(p.calls.some(c => c.url === '/api/public/events/' + EV + '/recording'), 'محصول از API همان رویداد خوانده می‌شود');
  const sec = p.doc.querySelector('#recording');
  ok(!!sec && p.txt('#recording').includes('ضبط کارگاه نجوم') && p.txt('#recording').includes('قابل خرید'), 'بخش «محتوای ضبط‌شده» داخل همان صفحهٔ رویداد با وضعیت «قابل خرید»');
  const cta = p.doc.querySelector('[data-rec-cta="login"] a[data-rec-login]');
  ok(cta && cta.getAttribute('href') === 'login.html?mode=server&next=' + encodeURIComponent('event.html?id=' + EV + '#recording'), 'تنها CTA مهمان: ورود با بازگشت به #recording');
  ok(!p.doc.querySelector('[data-rec-order]') && !p.doc.querySelector('[data-rec-claim]'), 'مهمان دکمهٔ خرید یا دریافت رایگان ندارد');
  ok(!p.doc.querySelector('.nora-countdown') && !p.doc.querySelector('[data-reg-timer]'), 'برای رویداد برگزارشده هیچ شمارش معکوسی ساخته نمی‌شود');
  ok(!p.doc.querySelector('#reg') && p.txt('.event-register').includes('محتوای ضبط‌شده') && p.doc.querySelector('[data-recording-aside] [data-rec-login]'), 'ستون کناری به‌جای ثبت‌نام، پنل فشردهٔ محصول با همان CTA را نشان می‌دهد؛ فرم ثبت‌نام بسته است');
  ok(p.txt('#recording').includes('۹۰ روز پس از فعال‌شدن') && p.txt('#recording').includes('۱ جلسه') && p.txt('#recording').includes('۱ ساعت و ۳۵ دقیقه'), 'مدت دسترسی، شمار جلسات و مدت واقعی از سرور نمایش داده می‌شود');
  ok(!/تخفیف|نفر خریده|پرفروش|محبوب/.test(p.txt('#recording')), 'هیچ شمارندهٔ ساختگی، تخفیف یا برچسب محبوبیت نیست');
  const vid = p.doc.querySelector('[data-rec-resource="' + VID + '"]');
  ok(vid && !vid.querySelector('video') && !vid.querySelector('a[download]') && vid.textContent.includes('برای دسترسی وارد حساب شوید'), 'ویدئوی قفل برای مهمان: نه پخش‌کننده، نه پیوند؛ فقط دعوت به ورود');
  const pdf = p.doc.querySelector('[data-rec-resource="' + PDF + '"] a[download]');
  ok(pdf && pdf.getAttribute('href') === '/api/public/events/' + EV + '/resources/' + PDF + '/download' && p.txt('[data-rec-resource="' + PDF + '"]').includes('پیش‌نمایش رایگان'), 'فایل پیش‌نمایش برای همه از نقطهٔ مجوزدار سرور قابل دریافت است');
  ok(p.txt('#recording').includes('آیا دانلود دارد؟') && p.txt('#recording').includes('تا ۷ روز با درخواست کتبی'), 'پرسش‌های متداول و سیاست بازپرداخت از سرور');
  ok(p.doc.querySelector('#qa') && p.doc.querySelector('#reviews'), 'پرسش‌وپاسخ و دیدگاه‌ها همچنان داخل همین صفحه‌اند');
  p.dom.window.close();
}

console.log('\n— کاربر واردشده (فاز ۹.۱): خرید فقط از فرم خریدِ فرم‌ساز؛ سفارش فرم‌دار باز بدون مسیر رسید موازی —');
{
  const p = await load({ recording: product('member'), cookie: 'nora_account_csrf=csrf-token-123' });
  ok(p.errors.length === 0, 'بدون خطای JavaScript' + (p.errors.length ? ': ' + p.errors[0] : ''));
  const buy = p.doc.querySelector('[data-rec-cta="buy"] a[data-rec-buy]');
  ok(!!buy && buy.getAttribute('href') === 'form.html?fid=' + FORM + '&kind=reg', 'CTA خرید یک پیوند به فرم خرید همان محصول است (شناسهٔ فرم از سرور)');
  ok(!p.doc.querySelector('[data-rec-order]') && !p.doc.querySelector('form[data-rec-receipt-form]'), 'هیچ دکمهٔ سفارش یا فرم رسید موازی در صفحهٔ رویداد نیست');
  ok(p.txt('[data-rec-cta="buy"]').includes('کارت‌به‌کارت با بررسی رسید') && !p.txt('[data-rec-cta="buy"]').includes('کیف پول بله'), 'فقط روش‌هایی که سرور اعلام کرده نام برده می‌شود');
  ok(!p.calls.some(c => c.url.endsWith('/orders')), 'هیچ درخواستی به مسیر بازنشستهٔ سفارش فرستاده نمی‌شود');
  ok(!p.doc.querySelector('[data-rec-resource="' + VID + '"] video') && p.txt('[data-rec-resource="' + VID + '"]').includes('نیازمند دسترسی'), 'پیش از خرید، ویدئو قفل است');
  const aside = p.doc.querySelector('[data-recording-aside] a[data-rec-buy]');
  ok(aside && aside.getAttribute('href') === 'form.html?fid=' + FORM + '&kind=reg', 'پنل کناری هم به همان فرم خرید می‌رود');
  p.dom.window.close();

  const order = { id: ORDER, recording_id: REC, method: 'card_transfer', status: 'receipt_submitted', open: true, paid: false, amount: 1500000, currency: 'IRR', expires_at: '', receipt_submitted: true, receipt_submitted_at: '2026-10-21T07:00:00Z', receipt_file_name: 'receipt.jpg', paid_at: '', decided_at: '', decision_reason: '', refunded_at: '', form_response_id: '99999999-9999-4999-8999-999999999991', form_payment_id: '99999999-9999-4999-8999-999999999992', created_at: '2026-10-21T06:00:00Z', updated_at: '', event_id: EV, title: 'ضبط کارگاه نجوم' };
  const open = await load({ recording: product('member', { cta: { kind: 'order_open', reason: 'receipt_submitted', methods: ['card_transfer'], form_id: FORM, order } }), cookie: 'nora_account_csrf=csrf-token-123' });
  const panel = open.doc.querySelector('#recording-order[data-ei-order-panel="receipt_submitted"]');
  ok(!!panel && panel.querySelector('[data-rec-order-via-form]') && panel.querySelector('a[data-rec-continue-form]').getAttribute('href') === 'form.html?fid=' + FORM + '&kind=reg', 'سفارش فرم‌دار: وضعیت واقعی + «ادامه در فرم خرید»، بدون فرم رسید');
  ok(!panel.querySelector('form') && !panel.querySelector('[data-rec-cancel]') && panel.textContent.includes('دسترسی فقط پس از تأیید فعال می‌شود'), 'بدون انصراف/رسید موازی؛ توضیح صادقانه دربارهٔ تأیید');
  ok(!open.doc.querySelector('[data-rec-resource="' + VID + '"] video') && !open.doc.querySelector('[data-rec-view]') && !/دسترسی دارید/.test(open.txt('#recording')), 'رسید به‌تنهایی هیچ دسترسی یا نشان «دسترسی دارید» نمی‌سازد');
  open.dom.window.close();

  const legacy = await load({ recording: product('member', { cta: { kind: 'order_open', reason: 'awaiting_receipt', methods: ['card_transfer'], form_id: FORM, order: { ...order, status: 'awaiting_receipt', receipt_submitted: false, receipt_file_name: '', form_response_id: null, form_payment_id: null, card: { number: '6037997599999993', bank: 'ملی', holder: 'انجمن نجوم' } } } }), cookie: 'nora_account_csrf=csrf-token-123' });
  const legacyPanel = legacy.doc.querySelector('#recording-order[data-ei-order-panel="awaiting_receipt"]');
  ok(!!legacyPanel && legacyPanel.querySelector('[data-rec-legacy-order]') && legacyPanel.querySelector('[data-rec-cancel]') && !legacyPanel.querySelector('form[data-rec-receipt-form]'), 'سفارش قدیمی بدون فرم: هشدار، انصراف و پیوند فرم خرید؛ بدون بارگذاری رسید');
  legacy.dom.window.close();
}

console.log('\n— خریدار: CTA مشاهده، پخش‌کنندهٔ ویدئو فقط از نقطهٔ مجوزدار، دانلود فقط برای فایل قابل دانلود، تاریخ انقضا —');
{
  const p = await load({ recording: product('buyer'), cookie: 'nora_account_csrf=csrf-token-123', hash: '#recording' });
  ok(p.errors.length === 0, 'بدون خطای JavaScript');
  const view = p.doc.querySelector('[data-rec-cta="view"] a[data-rec-view]');
  ok(view && view.getAttribute('href') === '#recording-sessions' && p.txt('[data-rec-cta="view"]').includes('دسترسی تا'), 'CTA خریدار: «مشاهدهٔ جلسات» با تاریخ انقضای واقعی');
  ok(p.txt('#recording').includes('دسترسی دارید') && !p.doc.querySelector('[data-rec-order]'), 'وضعیت «دسترسی دارید» و بدون دکمهٔ خرید');
  const video = p.doc.querySelector('[data-rec-resource="' + VID + '"] video[data-rec-player]');
  ok(video && video.getAttribute('src') === '/api/public/events/' + EV + '/resources/' + VID + '/download' && !p.doc.querySelector('[data-rec-resource="' + VID + '"] a[download]'), 'ویدئوی «فقط مشاهده»: پخش‌کننده از نقطهٔ مجوزدار سرور، بدون پیوند دانلود');
  ok(p.doc.querySelector('[data-rec-resource="' + PDF + '"] a[download]'), 'جزوهٔ قابل دانلود پیوند دریافت دارد');
  ok(p.doc.querySelector('[data-recording-aside] [data-rec-view]'), 'پنل کناری هم به مشاهده تغییر کرده است');
  /* ui.js `uiHash` opens the legacy demo event sheet on every hashchange of a `?id=` page; the CTAs must jump without it. */
  let hashChanges = 0, scrolled = ''; p.dom.window.addEventListener('hashchange', () => { hashChanges += 1; });
  p.doc.getElementById('recording-sessions').scrollIntoView = () => { scrolled = 'recording-sessions'; };
  view.dispatchEvent(new p.dom.window.MouseEvent('click', { bubbles: true, cancelable: true }));
  await new Promise(resolve => setTimeout(resolve, 50));
  /* jsdom rejects replaceState on file:// URLs, so only the behaviour that matters is asserted: scroll, no hashchange, no sheet. */
  ok(scrolled === 'recording-sessions' && hashChanges === 0 && !p.doc.getElementById('shEvent'), 'پرش «مشاهدهٔ جلسات» بدون hashchange: ورقهٔ نمایشی قدیمی (NaN خرید) باز نمی‌شود');
  p.dom.window.close();
}

console.log('\n— محصول رایگان: دریافت بدون تراکنش؛ فروش متوقف: بدون دکمهٔ مرده؛ سفارش قبلی ردشده: تلاش دوباره —');
{
  let state = product('member', { price: 0, cta: { kind: 'free', reason: 'free', methods: [] } });
  const p = await load({ recording: state, cookie: 'nora_account_csrf=csrf-token-123', onFetch: async (url, init, ctl) => {
    if (url === '/api/account/recordings/' + REC + '/claim' && init.method === 'POST') {
      state = product('buyer', { price: 0 }); ctl.set(state);
      return { ok: true, status: 201, json: async () => ({ claimed: true, created: true }) };
    }
    return null;
  } });
  ok(p.txt('#recording').includes('رایگان') && p.doc.querySelector('[data-rec-cta="free"] [data-rec-claim]') && !p.doc.querySelector('[data-rec-order]'), 'محصول رایگان: دکمهٔ «دریافت دسترسی رایگان» و هیچ مسیر پرداختی');
  p.click('[data-rec-claim]');
  await wait(200);
  ok(p.calls.some(c => c.url === '/api/account/recordings/' + REC + '/claim') && !p.calls.some(c => c.url.endsWith('/orders')), 'دریافت رایگان فقط claim می‌زند؛ هیچ سفارش/تراکنشی ساخته نمی‌شود');
  ok(p.doc.querySelector('[data-rec-cta="view"]'), 'پس از ثبت سروری، CTA به مشاهده تغییر می‌کند');
  p.dom.window.close();

  const paused = await load({ recording: product('member', { status: 'sales_paused', cta: { kind: 'off_sale', reason: 'sales_paused', methods: [] } }), cookie: 'nora_account_csrf=x' });
  ok(paused.doc.querySelector('[data-rec-cta="off_sale"] [data-rec-off-sale]') && !paused.doc.querySelector('[data-rec-cta] button, [data-rec-cta] a.btn') && paused.txt('#recording').includes('فروش متوقف'), 'فروش متوقف: متن وضعیت، بدون هیچ دکمه‌ای');
  paused.dom.window.close();

  const retry = await load({ recording: product('member', { cta: { kind: 'buy', reason: 'purchase_required', methods: ['card_transfer', 'bale_wallet'], form_id: FORM, previous: { status: 'rejected', id: ORDER } } }), cookie: 'nora_account_csrf=x' });
  ok(retry.doc.querySelector('[data-rec-previous="rejected"]') && retry.txt('[data-rec-cta="buy"]').includes('سفارش رد شد') && retry.txt('[data-rec-cta="buy"]').includes('کیف پول بله') && retry.doc.querySelector('[data-rec-cta="buy"] a[data-rec-buy]'), 'سفارش قبلی ردشده: توضیح + هر دو روش اعلام‌شدهٔ سرور + پیوند فرم خرید');
  retry.dom.window.close();
}

console.log('\n— محصول منتشرنشده (۴۰۴ برای غیرکادر) و خطای سرور: بدون بخش ساختگی —');
{
  const missing = await load({ recording: 'missing' });
  ok(missing.errors.length === 0 && !missing.doc.querySelector('#recording') && missing.doc.querySelector('[data-event-interaction="recording"]').hidden, 'بدون محصول منتشرشده، بخش پنهان می‌ماند و هیچ کارت خریدی ساخته نمی‌شود');
  missing.dom.window.close();
  const failed = await load({ recording: 'fail' });
  ok(failed.doc.querySelector('#recording .ei-error [data-rec-retry]') && !failed.doc.querySelector('[data-rec-order]'), 'خطای سرور: پیام و تلاش دوباره، بدون دکمهٔ خرید');
  failed.dom.window.close();
}

console.log('\n— رویداد برگزارشده بدون محصول: نه بخش محصول، نه فرم ثبت‌نام —');
{
  const plain = { ...heldEvent, recording: undefined };
  const p = await load({ events: [plain], recording: 'missing' });
  ok(!p.doc.querySelector('[data-event-interaction="recording"]') && !p.calls.some(c => c.url.endsWith('/recording')) && !p.doc.querySelector('#reg') && p.txt('.event-register').includes('ثبت‌نام این رویداد پایان یافته'), 'بدون کارت محصول در عکس سرور، هیچ درخواست/بخشی ساخته نمی‌شود و ثبت‌نام بسته است');
  p.dom.window.close();
}

console.log('\n— فهرست رویدادها: صافی «ضبط‌شده»، برچسب و پیوند به صفحهٔ فروش، صافی رایگان/قابل خرید —');
{
  const freeHeld = { ...heldEvent, id: 'ev-free', t: 'نشست رایگان', recording: { ...card, id: 'rec-free', title: 'ضبط نشست', price: 0, free: true, session_count: 2, total_minutes: 0 } };
  const heldNoProduct = { ...heldEvent, id: 'ev-none', t: 'کارگاه بدون ضبط', recording: undefined };
  const draftProduct = { ...heldEvent, id: 'ev-draft-rec', t: 'کارگاه با ضبط پیش‌نویس', recording: { ...card, id: 'rec-draft', status: 'ready', sellable: false } };
  const upcoming = { id: 'ev-up', t: 'کارگاه آینده', kind: 'کارگاه', privacy: 'public', when: 'آبان', on: '۱۴۰۵/۰۸/۱۰', price: 100000, registration: { state: 'open', reason: '', lifecycle: 'scheduled', opensAt: '', closesAt: '', startsAt: '', endsAt: '', countdownTo: '', startsIn: '' }, forms: [{ id: 'f-up', need: 'reg', n: 'فرم' }] };
  const p = await load({ file: 'events.html', events: [heldEvent, freeHeld, heldNoProduct, draftProduct, upcoming], hash: '#recorded' });
  ok(p.errors.length === 0, 'صفحهٔ رویدادها بدون خطا' + (p.errors.length ? ': ' + p.errors[0] : ''));
  const ids = [...p.doc.querySelectorAll('#eventsList [data-event-id]')].map(el => el.dataset.eventId);
  ok(ids.length === 2 && ids.includes(EV) && ids.includes('ev-free'), 'هش #recorded فقط رویدادهای با محصول منتشرشده را نشان می‌دهد (برگزارشدهٔ بدون محصول و محصول پیش‌نویس حذف‌اند): ' + ids.join(','));
  ok(p.doc.querySelector('[data-event-filter="recorded"].on'), 'چیپ «ضبط‌شده» فعال است');
  const paid = p.doc.querySelector('[data-event-id="' + EV + '"]');
  ok(paid.textContent.includes('ضبط‌شده') && paid.textContent.includes('۱٬۵۰۰٬۰۰۰ ریال') && paid.textContent.includes('۹۵ دقیقه') && paid.querySelector('a[data-event-recording]').getAttribute('href') === 'event.html?id=' + EV + '#recording', 'کارت: برچسب ضبط‌شده، قیمت و مدت واقعی، پیوند به بخش فروش همان صفحه');
  ok(!paid.querySelector('.nora-countdown') && !paid.textContent.includes('ثبت‌نام'), 'کارت برگزارشده: بدون شمارش معکوس و بدون دکمهٔ ثبت‌نام');
  const free = p.doc.querySelector('[data-event-id="ev-free"]');
  ok(free.textContent.includes('دسترسی رایگان') && free.textContent.includes('۲ جلسه') && !free.textContent.includes('دقیقه'), 'محصول رایگان: برچسب رایگان؛ مدت فقط وقتی واقعی باشد');
  const chips = [...p.doc.querySelectorAll('[data-event-access]')].map(el => el.dataset.eventAccess);
  ok(chips.includes('رایگان') && chips.includes('قابل خرید'), 'صافی دسترسی رایگان/قابل خرید فقط در نمای ضبط‌شده: ' + chips.join(','));
  p.click('[data-event-access="رایگان"]');
  await wait(50);
  const after = [...p.doc.querySelectorAll('#eventsList [data-event-id]')].map(el => el.dataset.eventId);
  ok(after.length === 1 && after[0] === 'ev-free', 'صافی رایگان فقط محصول رایگان را می‌گذارد');
  p.click('[data-event-filter="all"]');
  await wait(50);
  ok(p.doc.querySelectorAll('#eventsList [data-event-id]').length === 5 && !p.doc.querySelector('[data-event-access]'), 'بازگشت به «همه»: صافی دسترسی برداشته می‌شود');
  ok(!p.doc.querySelector('[data-event-id="ev-none"] [data-event-recording]') && !p.doc.querySelector('[data-event-id="ev-draft-rec"] [data-event-recording]'), 'برگزارشدهٔ بدون محصول منتشرشده هیچ دکمهٔ خریدی ندارد');
  ok(p.doc.querySelector('[data-event-id="ev-up"] a[href^="form.html"]'), 'رویداد پیش‌رو همچنان دکمهٔ ثبت‌نام خود را دارد');
  p.dom.window.close();
}

console.log('\n— پرسش‌وپاسخ و دیدگاه‌ها: پرسش جلسه‌ای اختیاری، نشان «خریدار تأییدشده» از سرور، پیام واجد شرایط بودن —');
{
  const patch = base => { base.viewer.signed_in = true; base.viewer.buyer = true; base.recording = { id: REC, status: 'published', sellable: true };
    base.reviews = { eligible: true, badge: 'buyer', items: [
      { id: 'rv-1', event_id: EV, author: 'م. ر.', mine: false, verified_attendee: true, badge: 'attendee', body: 'کارگاه عالی بود', status: 'published', edited: false, created_at: '2026-10-19T06:00:00Z', updated_at: '', reported: false },
      { id: 'rv-2', event_id: EV, author: 'س. ک.', mine: false, verified_attendee: false, badge: 'buyer', body: 'ضبط باکیفیت بود', status: 'published', edited: false, created_at: '2026-10-20T06:00:00Z', updated_at: '', reported: false } ], total: 2, mine: null };
    base.questions = { items: [ { id: 'q-1', event_id: EV, author: 'ن. ا.', mine: false, session_id: SESS, body: 'آیا اسلایدها هم هست؟', status: 'published', answered: true, answer: 'بله، جزوه ضمیمه است.', answer_official: true, answer_label: 'برگزارکننده', answered_at: '2026-10-20T07:00:00Z', created_at: '2026-10-20T06:00:00Z', reported: false },
      { id: 'q-2', event_id: EV, author: 'ن. ا.', mine: true, session_id: null, body: 'پرسش کلی من', status: 'pending', answered: false, answer: '', answer_official: false, answer_label: '', answered_at: '', created_at: '2026-10-21T06:00:00Z', reported: false } ], total: 2, mine_pending: 1 };
    return base; };
  const posted = [];
  const p = await load({ recording: product('buyer'), cookie: 'nora_account_csrf=csrf-token-123', interactionPatch: patch, onFetch: async (url, init) => {
    if (url === '/api/account/events/' + EV + '/questions' && init.method === 'POST') { posted.push(JSON.parse(init.body)); return { ok: true, status: 201, json: async () => ({ id: 'q-3', status: 'pending' }) }; }
    return null;
  } });
  ok(p.errors.length === 0, 'بدون خطای JavaScript' + (p.errors.length ? ': ' + p.errors[0] : ''));
  ok(p.doc.querySelector('[data-review="rv-1"] [data-ei-badge="attendee"]') && p.doc.querySelector('[data-review="rv-2"] [data-ei-badge="buyer"]')
    && p.txt('[data-review="rv-2"]').includes('خریدار تأییدشده') && !p.doc.querySelector('#reviews [data-ei-star], #reviews .stars'), 'نشان‌های «شرکت‌کنندهٔ تأییدشده» و «خریدار تأییدشده» از مقدار سرور؛ بدون امتیاز ستاره‌ای');
  ok(p.doc.querySelector('form[data-ei-form="review"]') && p.txt('form[data-ei-form="review"]').includes('با نشان «خریدار تأییدشده» منتشر می‌شود'), 'خریدار واجد شرایط دیدگاه است و نشان آیندهٔ خودش را می‌بیند');
  const tag = p.doc.querySelector('[data-question="q-1"] [data-ei-session-tag="' + SESS + '"]');
  ok(tag && tag.textContent.includes('جلسهٔ یکم') && !p.doc.querySelector('[data-question="q-2"] [data-ei-session-tag]'), 'پرسش جلسه‌ای با عنوان واقعی جلسه برچسب می‌خورد؛ پرسش کلی برچسب ندارد');
  const select = p.doc.querySelector('form[data-ei-form="question"] select[data-ei-question-session]');
  ok(select && select.options.length === 2 && select.options[0].value === '' && select.options[1].value === SESS, 'انتخاب‌گر اختیاری جلسه فقط جلسات منتشرشدهٔ محصول را دارد و پیش‌فرض «کل رویداد» است');
  select.value = SESS;
  p.doc.querySelector('#eiQuestionBody').value = 'پرسش دربارهٔ جلسهٔ یکم';
  p.doc.querySelector('form[data-ei-form="question"]').dispatchEvent(new p.window.Event('submit', { bubbles: true, cancelable: true }));
  await wait(200);
  ok(posted.length === 1 && posted[0].session_id === SESS && posted[0].body === 'پرسش دربارهٔ جلسهٔ یکم', 'پرسش با شناسهٔ جلسه فرستاده می‌شود؛ تصمیم اعتبار آن با سرور است');
  p.dom.window.close();

  const notEligible = await load({ recording: product('member'), cookie: 'nora_account_csrf=x', interactionPatch: base => { base.viewer.signed_in = true; base.recording = { id: REC, status: 'published', sellable: true }; return base; } });
  ok(!notEligible.doc.querySelector('form[data-ei-form="review"]') && notEligible.txt('#reviews').includes('دارندگان دسترسی محتوای ضبط‌شده'), 'غیرشرکت‌کنندهٔ بدون خرید: فرم دیدگاه نیست و پیام راه‌های واقعی واجد شرایط شدن را می‌گوید');
  notEligible.dom.window.close();
}

console.log(`\nevent-recording: ${checks} بررسی، ${fails} خطا`);
if (fails) process.exit(1);
