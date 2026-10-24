/* فاز ۷ — جریان مرورگر روی سرور آزمایشی (دادهٔ آزمون برچسب‌خورده «[آزمون]»). خروجی: اسکرین‌شات + لاگ. */
import path from 'node:path'; import os from 'node:os'; import fs from 'node:fs'; import { createRequire } from 'node:module'; import { execFileSync } from 'node:child_process';
const dep = createRequire('/home/user/nora-node/package.json'); const { chromium: pw } = dep('playwright-core');
const HOST = '8000-ivyx47rwkw8o6w7u1vo8a.e2b.app', B = `https://${HOST}`, OUT = process.env.P7_OUT || '/tmp/qa/p7/ui', log = []; fs.mkdirSync(OUT, { recursive: true });
const say = (m) => { log.push(m); console.log(m); };
let checks = 0, fails = 0; const ok = (c, label) => { checks++; if (!c) fails++; say(`  ${c ? '✓' : '✗'} ${label}`); };
async function launch() { const mod = dep('@sparticuz/chromium'); const chromium = mod.default || mod; const root = path.resolve(path.dirname(dep.resolve('@sparticuz/chromium')), '..'); const { inflate } = await import('file://' + path.join(root, 'build/lambdafs.js')); await inflate(path.join(root, 'bin/al2023.tar.br')); const executablePath = await chromium.executablePath(); const env = { ...process.env }; const lib = path.join(os.tmpdir(), 'al2023/lib'); if (fs.existsSync(lib)) env.LD_LIBRARY_PATH = [lib, env.LD_LIBRARY_PATH].filter(Boolean).join(path.delimiter); const fonts = path.join(os.tmpdir(), 'fonts'); if (fs.existsSync(fonts)) env.FONTCONFIG_PATH = fonts; return pw.launch({ executablePath, headless: true, args: chromium.args.filter((a) => !['--single-process', '--disable-web-security', '--allow-running-insecure-content'].includes(a)).concat([`--host-resolver-rules=MAP ${HOST} 127.0.0.1:8443`]), env }); }
const creds = (u) => fs.readFileSync(`/tmp/nora-preview/${u}-pw.txt`, 'utf8').trim();
const shot = async (page, n) => { await page.screenshot({ path: path.join(OUT, n + '.png'), animations: 'disabled', timeout: 60000 }); say('  shot ' + n); };
/* API مالک از طریق curl + کوکی‌های جلسهٔ قبلاً گرفته‌شده (برای تغییر مهلت در میانهٔ جریان) */
const CJ = '/tmp/p7-cj'; const csrf = () => fs.readFileSync(CJ, 'utf8').split('\n').find(l => l.includes('\tnora_csrf\t')).split('\t')[6].trim();
function api(method, p, body) { const args = ['-sk', '--resolve', `${HOST}:8443:127.0.0.1`, '-b', CJ, '-c', CJ, '-H', `Origin: https://${HOST}:8443`, '-H', `X-CSRF-Token: ${csrf()}`, '-H', 'Content-Type: application/json', '-X', method, `https://${HOST}:8443${p}`]; if (body) args.push('-d', JSON.stringify(body)); return JSON.parse(execFileSync('curl', args, { encoding: 'utf8' })); }
const EV_OPEN = 'ev-61f2ac7e51', EV_WAIT = 'ev-c99fd10306', EV_FULL = 'ev-6d70bd6c77', EV_CANCEL = 'ev-0e796f247d', FORM_OPEN = 'f96eb4ab-96d9-4bf6-8111-9239f207bf28';
function setDeadline(iso) { const d = api('GET', `/api/admin/content/events/${EV_OPEN}`); const rec = {}; for (const k of ['t', 'kind', 'd', 'on', 'when', 'time', 'place', 'mode', 'price', 'cap', 'tags', 'conditions', 'regMode', 'lifecycle']) rec[k] = d.record[k]; Object.assign(rec, d.record.local_times); rec.regClosesAt = iso; const r = api('PUT', `/api/admin/content/events/${EV_OPEN}`, { record: rec, expected_version: d.version }); return r.record ? r.record.registration : r; }
const targets = (page) => page.evaluate(() => ({ banner: document.querySelector('#bsdeck [data-countdown]')?.dataset.countdown || '', card: [...document.querySelectorAll('#evSec .evcard')].find(c => c.textContent.includes('کارگاه با ثبت‌نام باز'))?.querySelector('[data-countdown]')?.dataset.countdown || '', serverClock: window.NORA_SERVER_CLOCK?.serverTime || '' }));
async function staffLogin(page, u, p) { await page.goto(`${B}/login.html?mode=staff&next=admin.html%23dash`, { waitUntil: 'domcontentloaded' }); await page.waitForSelector('#lgStaffUsername', { timeout: 20000 }); await page.fill('#lgStaffUsername', u); await page.fill('#lgStaffPassword', p); await page.click('#lgStaffSubmit'); await Promise.race([page.waitForSelector('#lgContinue', { timeout: 15000 }).then(() => page.click('#lgContinue')).catch(() => {}), page.waitForURL(/admin\.html/, { timeout: 15000 }).catch(() => {})]); await page.waitForURL(/admin\.html/, { timeout: 15000 }); await page.waitForSelector('#admBar .server-identity', { timeout: 15000 }); say(`  logged in as ${u}`); }
const browser = await launch();
try {
  const pub = api('GET', '/api/public/site-content'); say('server_time=' + pub.server_time + ' events=' + pub.content.events.length + ' banners=' + pub.content.banners.length);
  /* ── ۱) عمومی: دسکتاپ ── */
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fa-IR', ignoreHTTPSErrors: true }); const page = await ctx.newPage();
  const errors = [], bad = []; page.on('pageerror', (e) => errors.push(String(e))); page.on('response', (r) => { if (r.status() >= 400 && !/\/api\/auth\/(me|captcha)|\/api\/account\/me|sitemap|\/draft/.test(r.url())) bad.push(r.status() + ' ' + r.url()); });
  say('== home (desktop) =='); await page.goto(`${B}/home.html`, { waitUntil: 'domcontentloaded' }); await page.waitForSelector('#bsdeck .bs', { timeout: 20000 }); await page.waitForTimeout(800);
  const home = await page.evaluate(() => ({ banners: [...document.querySelectorAll('#bsdeck .bs')].map(b => ({ t: b.querySelector('h2')?.textContent, timer: b.querySelector('.btimer')?.textContent.replace(/\s+/g, ' ').trim() || '', note: b.querySelector('.bnote')?.textContent || '', cta: b.querySelector('.bacts a')?.getAttribute('href') || '' })), top: [...document.querySelectorAll('#evTop .evcard')].map(c => ({ t: c.querySelector('.evc-ttl')?.textContent, state: c.querySelector('.reg-state')?.textContent || '', timer: c.querySelector('.nora-countdown')?.textContent.replace(/\s+/g, ' ').trim() || '', cta: c.querySelector('.evc-cta')?.textContent.trim() })), openHidden: document.querySelector('#evOpenGroup')?.hidden, soon: [...document.querySelectorAll('#evSoon .evc-ttl')].map(e => e.textContent), past: [...document.querySelectorAll('#pastList .evc-ttl')].map(e => e.textContent) }));
  say('  home: ' + JSON.stringify(home));
  ok(home.banners.length === 3 && /تا پایان ثبت‌نام/.test(home.banners[0].timer) && home.banners[0].cta.endsWith(`/event.html?id=${EV_OPEN}`), 'بنر وصل به رویداد: شمارشگر مهلت از رویداد و مقصد صفحهٔ جزئیات');
  ok(/تا پایان فرصت/.test(home.banners[1].timer), 'بنر کمپین مستقل: شمارشگر کمپین');
  ok(home.banners[2].note === 'ظرفیت این اردو تکمیل شد' && home.banners[2].cta.endsWith(`/event.html?id=${EV_FULL}`), 'بنر رویداد پرشده: متن پایان و فقط جزئیات');
  ok(home.top[0] && /ثبت‌نام باز/.test(home.top[0].state) && /تا پایان ثبت‌نام/.test(home.top[0].timer) && /ثبت‌نام و جزئیات/.test(home.top[0].cta), 'ویترین: کارت باز اول با نشان و شمارشگر');
  ok(!home.banners.some(b => /زمان‌بندی‌شدهٔ آینده|بنر خاموش/.test(b.t)), 'بنر خاموش و زمان‌بندی‌شدهٔ آینده نمایش داده نمی‌شوند');
  await shot(page, '01-home-desktop');
  await page.evaluate(() => document.querySelector('#evSec')?.scrollIntoView({ block: 'start' })); await page.waitForTimeout(300); await shot(page, '02-home-events-desktop');
  const t0 = await targets(page); say('  targets home: ' + JSON.stringify(t0));
  say('== events (desktop) =='); await page.goto(`${B}/events.html`, { waitUntil: 'domcontentloaded' }); await page.waitForSelector('#eventsList .event-list-card', { timeout: 20000 }); await page.waitForTimeout(600);
  const cards = await page.evaluate(() => [...document.querySelectorAll('#eventsList .event-list-card')].map(c => ({ id: c.dataset.eventId, state: c.querySelector('.event-list-state .reg-state')?.textContent || '', timer: c.querySelector('[data-countdown]')?.dataset.countdown || '', cover: c.querySelector('.cover-state')?.textContent || '', reg: c.querySelector('.event-list-actions a.primary')?.getAttribute('href') || '', missing: c.querySelector('.event-register-missing')?.textContent || '' })));
  say('  cards: ' + JSON.stringify(cards));
  const byId = Object.fromEntries(cards.map(c => [c.id, c]));
  ok(byId[EV_OPEN]?.reg === `form.html?fid=${FORM_OPEN}&kind=reg` && /ثبت‌نام باز/.test(byId[EV_OPEN]?.state), 'کارت باز: دکمهٔ ثبت‌نام به فرم موجود');
  ok(byId[EV_WAIT] && !byId[EV_WAIT].reg && /آغاز نشده/.test(byId[EV_WAIT].missing), 'کارت آغازنشده: بدون دکمهٔ فرم');
  ok(byId[EV_FULL] && !byId[EV_FULL].reg && /ظرفیت تکمیل/.test(byId[EV_FULL].missing), 'کارت تکمیل ظرفیت: بدون دکمهٔ فرم');
  ok(byId[EV_CANCEL] && !byId[EV_CANCEL].reg && byId[EV_CANCEL].cover === 'لغو شد', 'کارت لغوشده: نشان لغو، بدون فرم');
  ok(byId[EV_OPEN]?.timer === t0.card && t0.card === t0.banner && t0.card !== '', 'هدف شمارشگر کارت صفحهٔ رویدادها = کارت خانه = بنر');
  await shot(page, '03-events-desktop');
  say('== detail pages (desktop) ==');
  const detail = async (id, name) => { await page.goto(`${B}/event.html?id=${id}`, { waitUntil: 'domcontentloaded' }); await page.waitForSelector('.event-register', { timeout: 20000 }); await page.waitForTimeout(500); const d = await page.evaluate(() => ({ state: document.querySelector('.event-register .reg-state')?.textContent || '', timer: document.querySelector('[data-reg-timer] [data-countdown]')?.dataset.countdown || '', reg: document.querySelector('#reg')?.getAttribute('href') || '', bar: document.querySelector('#ctabar')?.hidden, notes: document.querySelector('.event-reg-note')?.textContent || '', start: [...document.querySelectorAll('.detail-item')].map(i => i.textContent.replace(/\s+/g, ' ')).find(t => /شروع/.test(t)) || '', calendar: !!document.querySelector('#addToCalendar'), share: !!document.querySelector('#shareEvent'), tags: document.querySelector('.event-heading')?.textContent.replace(/\s+/g, ' ') })); say(`  ${name}: ${JSON.stringify(d)}`); await shot(page, name); return d; };
  const dOpen = await detail(EV_OPEN, '04-detail-open-desktop');
  ok(/ثبت‌نام باز/.test(dOpen.state) && dOpen.reg === `form.html?fid=${FORM_OPEN}&kind=reg` && dOpen.bar === false && dOpen.timer === t0.card && dOpen.calendar && dOpen.share, 'جزئیات باز: وضعیت، CTA فرم، نوار پایین، همان هدف شمارش، تقویم و اشتراک');
  const dWait = await detail(EV_WAIT, '05-detail-not-started-desktop'); ok(/آغاز نشده/.test(dWait.state) && !dWait.reg && dWait.bar === true && /آغاز می‌شود/.test(dWait.notes), 'جزئیات آغازنشده: بدون CTA، زمان آغاز ثبت‌نام');
  const dFull = await detail(EV_FULL, '06-detail-full-desktop'); ok(/ظرفیت تکمیل/.test(dFull.state) && !dFull.reg && dFull.bar === true, 'جزئیات تکمیل ظرفیت: بدون CTA');
  const dCancel = await detail(EV_CANCEL, '07-detail-cancelled-desktop'); ok(/لغو شد/.test(dCancel.state) && !dCancel.reg && !dCancel.timer && !dCancel.calendar, 'جزئیات لغوشده: بدون CTA/شمارشگر/تقویم');
  /* ── ۲) قبل/بعد از پایان مهلت (مهلت را به ۷۵ ثانیهٔ آینده می‌بریم) ── */
  say('== deadline before/after ==');
  const soon = new Date(Date.now() + 75_000).toISOString().replace(/\.\d{3}Z$/, 'Z'); const setR = setDeadline(soon); say('  set regClosesAt=' + soon + ' → server state ' + JSON.stringify(setR.state));
  await page.goto(`${B}/event.html?id=${EV_OPEN}`, { waitUntil: 'domcontentloaded' }); await page.waitForSelector('#reg', { timeout: 20000 }); await page.waitForTimeout(500);
  const before = await page.evaluate(() => ({ reg: !!document.querySelector('#reg'), timer: document.querySelector('[data-reg-timer] .nora-countdown-value')?.textContent, soonCls: document.querySelector('[data-reg-timer] .nora-countdown')?.className })); say('  before: ' + JSON.stringify(before));
  ok(before.reg && /دقیقه|ثانیه/.test(before.timer || ''), 'قبل از پایان مهلت: دکمهٔ ثبت‌نام و شمارش ثانیه‌ای');
  await shot(page, '08-detail-before-deadline-desktop');
  await page.waitForFunction(() => !document.querySelector('#reg'), null, { timeout: 120000 });
  const after = await page.evaluate(() => ({ reg: !!document.querySelector('#reg'), action: document.querySelector('[data-reg-action]')?.textContent.replace(/\s+/g, ' ').trim(), ended: document.querySelector('[data-reg-timer] .nora-countdown.is-ended')?.textContent.replace(/\s+/g, ' ').trim(), bar: document.querySelector('#ctabar')?.hidden })); say('  after (client): ' + JSON.stringify(after));
  ok(!after.reg && /نوسازی/.test(after.action) && after.bar === true, 'پس از پایان مهلت (بدون نوسازی): CTA برداشته شد، دعوت به به‌روزرسانی');
  await shot(page, '09-detail-after-deadline-client-desktop');
  await page.click('#refreshState'); await page.waitForSelector('.event-register', { timeout: 20000 }); await page.waitForTimeout(600);
  const reloaded = await page.evaluate(() => ({ state: document.querySelector('.event-register .reg-state')?.textContent, reg: !!document.querySelector('#reg'), timer: !!document.querySelector('[data-reg-timer] [data-countdown]'), startTimer: document.querySelector('[data-countdown]')?.closest('.nora-countdown')?.textContent.replace(/\s+/g,' ').trim() || '', notes: document.querySelector('.event-reg-note')?.textContent })); say('  after (server): ' + JSON.stringify(reloaded));
  ok(/ثبت‌نام بسته/.test(reloaded.state) && !reloaded.reg && !/تا پایان ثبت‌نام/.test(reloaded.startTimer), 'پس از نوسازی: وضعیت «ثبت‌نام بسته شد» از سرور، بدون شمارشگر مهلت (فقط شمارش تا شروع رویداد مجاز است)');
  await shot(page, '10-detail-after-deadline-server-desktop');
  const formStatus = await page.evaluate(async (fid) => { const r = await fetch(`/api/public/forms/${fid}`); const j = await r.json().catch(() => ({})); return { status: r.status, code: j.detail?.code, state: j.detail?.state }; }, FORM_OPEN); say('  API after deadline: ' + JSON.stringify(formStatus));
  ok(formStatus.status === 409 && formStatus.code === 'registration_closed', 'API فرم پس از مهلت: ۴۰۹ registration_closed (دور زدن از مسیر مستقیم ممکن نیست)');
  await page.goto(`${B}/form.html?fid=${FORM_OPEN}&kind=reg`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(800);
  const gated = await page.evaluate(() => ({ title: document.querySelector('#unavailableTitle')?.textContent, back: document.querySelector('#unavailableBack')?.getAttribute('href'), screen: [...document.querySelectorAll('.screen.on')].map(s => s.id).join() })); say('  form.html gated: ' + JSON.stringify(gated));
  ok(gated.title === 'ثبت‌نام این رویداد باز نیست' && gated.back === `event.html?id=${EV_OPEN}`, 'فرم با پیوند مستقیم پس از مهلت: پیام بسته‌بودن و بازگشت به همان رویداد');
  await shot(page, '11-form-gated-after-deadline-desktop');
  await page.goto(`${B}/home.html`, { waitUntil: 'domcontentloaded' }); await page.waitForSelector('#bsdeck .bs', { timeout: 20000 }); await page.waitForTimeout(600);
  const homeAfter = await page.evaluate(() => ({ banner: document.querySelector('#bsdeck .bs .btimer')?.textContent.replace(/\s+/g, ' ').trim(), cta: document.querySelector('#bsdeck .bs .bacts a')?.getAttribute('href'), card: [...document.querySelectorAll('#evSec .evcard')].find(c => c.textContent.includes('کارگاه با ثبت‌نام باز'))?.querySelector('.reg-state')?.textContent })); say('  home after deadline: ' + JSON.stringify(homeAfter));
  ok(/پایان/.test(homeAfter.banner || '') && (homeAfter.cta||'').endsWith(`/event.html?id=${EV_OPEN}`) && /بسته/.test(homeAfter.card || ''), 'خانه پس از مهلت: بنر «پایان‌یافته» با مقصد جزئیات و کارت «ثبت‌نام بسته شد»');
  await shot(page, '12-home-after-deadline-desktop');
  const restore = setDeadline(new Date(Date.now() + 26.5 * 3600_000).toISOString().replace(/\.\d{3}Z$/, 'Z')); say('  restored deadline → ' + restore.state);
  say('  public page errors: ' + JSON.stringify(errors)); say('  HTTP>=400 (excluding expected probes): ' + JSON.stringify(bad));
  ok(errors.length === 0, 'بدون خطای جاوااسکریپت در صفحه‌های عمومی');
  await ctx.close();
  /* ── ۳) عمومی: موبایل ۳۹۰×۸۴۴ ── */
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: 'fa-IR', ignoreHTTPSErrors: true }); const mp = await mctx.newPage(); const merr = []; mp.on('pageerror', (e) => merr.push(String(e)));
  say('== mobile ==');
  for (const [url, name, sel] of [[`/home.html`, '13-home-mobile', '#bsdeck .bs'], [`/events.html`, '14-events-mobile', '#eventsList .event-list-card'], [`/event.html?id=${EV_OPEN}`, '15-detail-open-mobile', '.event-register'], [`/event.html?id=${EV_CANCEL}`, '16-detail-cancelled-mobile', '.event-register']]) {
    await mp.goto(B + url, { waitUntil: 'domcontentloaded' }); await mp.waitForSelector(sel, { timeout: 20000 }); await mp.waitForTimeout(600);
    const overflow = await mp.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth); ok(overflow <= 1, `${name}: بدون سرریز افقی (${overflow}px)`); await shot(mp, name);
  }
  await mp.goto(`${B}/home.html`, { waitUntil: 'domcontentloaded' }); await mp.waitForSelector('#evTop .evcard', { timeout: 20000 }); await mp.evaluate(() => document.querySelector('#evSec')?.scrollIntoView({ block: 'start' })); await mp.waitForTimeout(400); await shot(mp, '17-home-events-mobile');
  ok(merr.length === 0, 'بدون خطای جاوااسکریپت در موبایل: ' + JSON.stringify(merr));
  await mctx.close();
  /* ── ۴) پنل مالک: ویرایشگر رویداد و مدیریت بنر ── */
  const actx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fa-IR', ignoreHTTPSErrors: true }); const ap = await actx.newPage(); ap.on('dialog', d => { say('  dialog(' + d.type() + '): ' + d.message().slice(0, 90)); d.accept(); }); const aerr = []; ap.on('pageerror', (e) => aerr.push(String(e)));
  say('== owner panel =='); await staffLogin(ap, 'qa-owner', creds('owner'));
  await ap.evaluate(() => { location.hash = '#events'; }); await ap.waitForSelector(`[data-ct-edit="${EV_OPEN}"]`, { timeout: 20000 }); await ap.click(`[data-ct-edit="${EV_OPEN}"]`); await ap.waitForSelector('#ctf_regClosesAt', { timeout: 20000 }); await ap.waitForTimeout(400);
  const editor = await ap.evaluate(() => ({ startsAt: document.querySelector('#ctf_startsAt').value, regClosesAt: document.querySelector('#ctf_regClosesAt').value, regMode: document.querySelector('#ctf_regMode').value, lifecycle: document.querySelector('#ctf_lifecycle').value, state: document.querySelector('[data-ct-reg-state]')?.textContent })); say('  editor: ' + JSON.stringify(editor));
  ok(/^\d{4}\/\d{2}\/\d{2} \d{2}:\d{2}$/.test(editor.regClosesAt) && /ثبت‌نام باز/.test(editor.state || ''), 'ویرایشگر رویداد: زمان‌ها به شمسی/تهران پر شده و وضعیت ثبت‌نام سرور نشان داده می‌شود');
  await ap.evaluate(() => document.querySelector('[data-ct-schedule]')?.scrollIntoView({ block: 'center' })); await shot(ap, '18-admin-event-editor-schedule-desktop');
  await ap.setViewportSize({ width: 390, height: 844 }); await ap.waitForTimeout(400); await ap.evaluate(() => document.querySelector('[data-ct-schedule]')?.scrollIntoView({ block: 'start' })); await shot(ap, '19-admin-event-editor-schedule-mobile'); await ap.setViewportSize({ width: 1280, height: 800 });
  await ap.evaluate(() => { location.hash = '#settings'; }); await ap.waitForSelector('[data-setg="publishing"]', { timeout: 20000 }); await ap.click('[data-setg="publishing"]');
  await ap.waitForSelector('[data-owner-banner-select="p7-banner-open"]', { timeout: 20000 }); await ap.click('[data-owner-banner-select="p7-banner-open"]'); await ap.waitForTimeout(500);
  const bm = await ap.evaluate(() => ({ event: document.querySelector('#ownerBannerEvent').value, countdown: document.querySelector('#ownerBannerForm [name=countdown]').value, afterEnd: document.querySelector('#ownerBannerForm [name=afterEnd]').value, eventState: document.querySelector('#ownerBannerEventState')?.textContent, preview: document.querySelector('#ownerBannerPreview .obm-preview-countdown')?.textContent, options: [...document.querySelectorAll('#ownerBannerEvent option')].map(o => o.textContent) })); say('  banner manager: ' + JSON.stringify(bm));
  ok(bm.event === EV_OPEN && bm.countdown === 'reg_close' && /تا پایان ثبت‌نام/.test(bm.preview || '') && !bm.options.some(o => /بارگذاری از مرورگر/.test(o)), 'مدیریت بنر: رویداد پیوندشده، نوع شمارشگر و پیش‌نمایش از مهلت رویداد؛ رویداد پیش‌نویس در فهرست نیست');
  await ap.evaluate(() => document.querySelector('#ownerBannerPreview')?.scrollIntoView({ block: 'center' })); await shot(ap, '20-admin-banner-preview-desktop');
  await ap.click('[data-obm-preview-mode="mobile"]'); await ap.waitForTimeout(300); ok(await ap.evaluate(() => document.querySelector('#ownerBannerPreview').dataset.previewMode === 'mobile'), 'پیش‌نمایش موبایل فعال شد'); await shot(ap, '21-admin-banner-preview-mobile-mode');
  /* سناریوی ۷: ویرایش بنر، ذخیره، بارگذاری دوباره */
  const stamp = 'متن پایان آزمون ' + new Date().toISOString().slice(11, 19);
  await ap.fill('#ownerBannerForm [name=afterEndText]', stamp); await ap.selectOption('#ownerBannerForm [name=afterEnd]', 'message'); await ap.click('#ownerBannerSave');
  await ap.waitForFunction(() => /ذخیره شد|نسخهٔ/.test(document.querySelector('#ownerBannerState')?.textContent || '') && !/در حال/.test(document.querySelector('#ownerBannerState')?.textContent || ''), null, { timeout: 20000 });
  say('  save state: ' + (await ap.evaluate(() => document.querySelector('#ownerBannerState')?.textContent.trim())));
  await ap.reload({ waitUntil: 'domcontentloaded' }); await ap.waitForSelector('#admBar .server-identity', { timeout: 20000 }); await ap.evaluate(() => { location.hash = '#settings'; }); await ap.waitForSelector('[data-setg="publishing"]', { timeout: 20000 }); await ap.click('[data-setg="publishing"]');
  await ap.waitForSelector('[data-owner-banner-select="p7-banner-open"]', { timeout: 20000 }); await ap.click('[data-owner-banner-select="p7-banner-open"]'); await ap.waitForTimeout(500);
  const persisted = await ap.evaluate(() => ({ text: document.querySelector('#ownerBannerForm [name=afterEndText]').value, afterEnd: document.querySelector('#ownerBannerForm [name=afterEnd]').value, event: document.querySelector('#ownerBannerEvent').value }));
  ok(persisted.text === stamp && persisted.afterEnd === 'message' && persisted.event === EV_OPEN, 'ویرایش بنر پس از بارگذاری دوبارهٔ پنل پابرجاست (از سرور)');
  const pubAfter = api('GET', '/api/public/site-content').content.banners.find(b => b.id === 'p7-banner-open'); ok(pubAfter && pubAfter.afterEndText === stamp && pubAfter.afterEnd === 'message', 'API عمومی همان تغییر را برمی‌گرداند');
  await shot(ap, '22-admin-banner-after-reload');
  ok(aerr.length === 0, 'بدون خطای جاوااسکریپت در پنل: ' + JSON.stringify(aerr));
  await actx.close();
} finally { await browser.close(); say(`\nbrowser-flow phase7: ${checks} بررسی، ${fails} خطا`); fs.writeFileSync(path.join(OUT, 'walkthrough-log.txt'), log.join('\n') + '\n'); process.exitCode = fails ? 1 : 0; }
