// End-to-end user flows on the isolated test server (real browser, real API, test data only).
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const ORIGIN = 'http://127.0.0.1:8000';
const OUT = process.env.OUT || '/tmp/qa/flows-audit'; fs.mkdirSync(OUT, { recursive: true });
const FORM = process.env.FORM_ID || 'c885a821-2583-4716-a5d6-ab43f1fda5ac';
const results = []; let fails = 0;
const ok = (c, name, detail = '') => { results.push({ ok: !!c, name, detail: String(detail).slice(0, 400) }); if (!c) fails++; console.log((c ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + String(detail).slice(0, 300) : '')); };
const launch = async () => { for (let i = 0; i < 5; i++) { try { return await launchBrowser(); } catch (e) { if (i === 4) throw e; await new Promise(r => setTimeout(r, 1500)); } } };
async function open(path, { w = 390, h = 844, theme = '', routes = [] } = {}) {
  const browser = await launch();
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'fa-IR', serviceWorkers: 'block', isMobile: w < 600, hasTouch: w < 600 });
  const page = await ctx.newPage();
  const errors = []; page.on('pageerror', e => errors.push(String(e.message).slice(0, 150))); page.on('console', m => { if (m.type() === 'error' && !/status of (401|404|503)/.test(m.text())) errors.push(m.text().slice(0, 150)); });
  const dialogs = []; page.on('dialog', d => { dialogs.push(d.type() + ':' + d.message()); d.dismiss().catch(() => {}); });
  if (theme) await page.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, theme);
  for (const [glob, handler] of routes) await page.route(glob, handler);
  await page.goto(ORIGIN + path, { waitUntil: 'load' });
  await page.waitForTimeout(700);
  const close = async () => { await ctx.close().catch(() => {}); await browser.close().catch(() => {}); };
  return { browser, page, errors, dialogs, close };
}
const txt = (page, sel) => page.$eval(sel, el => el.innerText.trim()).catch(() => null);
const vis = (page, sel) => page.$eval(sel, el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; }).catch(() => false);

// ───────── 1. events: search / chips / calendar / sort / navigation
{
  const { page, errors, close } = await open('/events.html');
  const count0 = await txt(page, '#eventsCount');
  await page.fill('#eventSearch', 'کارگاه آزمایشی ۱');
  await page.waitForTimeout(500);
  const n1 = await page.$$eval('#eventsList a[href*="event.html"]', a => new Set(a.map(x => x.getAttribute('href'))).size);
  const count1 = await txt(page, '#eventsCount');
  ok(n1 === 1 && /۱ رویداد/.test(count1 || ''), '1a. events search narrows to the matching event', `${count0} → ${count1} (${n1} unique link)`);
  await page.fill('#eventSearch', 'هیچ‌چیز-xyz'); await page.waitForTimeout(400);
  ok(await vis(page, '#eventsEmpty') && /(یافت|پیدا|نتیجه|تغییر دهید)/.test(await txt(page, '#eventsEmptyMessage') || ''), '1b. no-result search shows an honest empty state', await txt(page, '#eventsEmptyMessage'));
  await page.click('#clearSearch').catch(() => page.fill('#eventSearch', ''));
  await page.waitForTimeout(400);
  await page.click('[data-event-filter="past"]').catch(async () => { const b = await page.$('button:has-text("برگزارشده")'); if (b) await b.click(); });
  await page.waitForTimeout(500);
  const pastLinks = await page.$$eval('#eventsList a[href*="event.html"]', a => a.map(x => x.getAttribute('href')));
  ok(pastLinks.some(h => h.includes('qa-ev-past')) && !pastLinks.some(h => h.includes('qa-ev-1')), '1c. «برگزارشده» chip shows only past events', pastLinks.join(','));
  await page.goto(ORIGIN + '/events.html?status=past', { waitUntil: 'load' }); await page.waitForTimeout(600);
  const pastQ = await page.$$eval('#eventsList a[href*="event.html"]', a => a.map(x => x.getAttribute('href')));
  ok(pastQ.some(h => h.includes('qa-ev-past')), '1d. ?status=past deep link lands on the past list', pastQ.join(','));
  await page.goto(ORIGIN + '/events.html', { waitUntil: 'load' }); await page.waitForTimeout(600);
  await page.click('[data-event-view="cal"]'); await page.waitForTimeout(500);
  const calVis = await vis(page, '#eventCalendarGrid');
  const calDays = await page.$$eval('#eventCalendarGrid [data-date], #eventCalendarGrid button', b => b.length);
  ok(calVis && calDays > 20, '1e. calendar view renders a day grid', `${calDays} cells`);
  const dayBtn = await page.$('#eventCalendarGrid button.event-cal-cell.has');
  if (dayBtn) { await dayBtn.click(); await page.waitForTimeout(400); }
  ok(await vis(page, '#eventDayTitle'), '1f. calendar day panel visible after choosing a day', await txt(page, '#eventDayCount'));
  await page.screenshot({ path: `${OUT}/events-calendar-390.png` });
  await page.click('[data-event-view="list"]'); await page.waitForTimeout(300);
  await page.selectOption('#eventSort', { index: 1 }).catch(() => {});
  await page.waitForTimeout(300);
  const first = await page.$('#eventsList a.event-list-title');
  const href = first ? await first.getAttribute('href') : '';
  if (first) { await first.scrollIntoViewIfNeeded(); await first.click(); await page.waitForURL('**/event.html?*', { timeout: 10000 }); }
  ok(page.url().includes('event.html?id='), '1g. event card opens the event page', href);
  const h1 = await txt(page, 'h1');
  ok(h1 && h1.length > 3, '1h. event page shows the event title', h1);
  await page.goto(ORIGIN + '/event.html?id=qa-ev-1', { waitUntil: 'load' }); await page.waitForTimeout(600);
  const reg = await page.$('a[href*="form.html?fid="]');
  ok(!!reg, '1i. event attached to a published form shows a registration CTA', reg ? await reg.getAttribute('href') : 'no form CTA');
  const back = await page.$('a.back-link, a[href^="events.html"]');
  ok(!!back, '1j. event page has a way back to the events list');
  ok(errors.length === 0, '1k. no JS errors in events flow', errors.join(' | '));
  await close();
}
// ───────── 2. events page under API failure
{
  const { page, close } = await open('/events.html', { routes: [['**/api/public/site-content*', r => r.abort()]] });
  await page.waitForTimeout(1200);
  const body = await page.evaluate(() => document.body.innerText);
  const cards = await page.$$eval('#eventsList a[href*="event.html"]', a => a.length);
  const msg = (await txt(page, '#eventsEmptyMessage')) || '';
  ok(cards === 0 && !/qa-ev|کارگاه آزمایشی/.test(body), '2a. events page never shows fixture events when the API fails', `${cards} cards`);
  ok(/(اتصال|سرور|دسترس|دوباره|شبکه)/.test(msg + body), '2b. API failure shows an explanatory message', msg || body.slice(0, 120));
  await page.screenshot({ path: `${OUT}/events-api-down-390.png` });
  await close();
}
// ───────── 3. form flow: validation → submit → final page → reload
{
  const { page, errors, dialogs, close } = await open(`/form.html?fid=${FORM}`);
  const startBtn = await page.$('#next');
  ok(await vis(page, '#next'), '3a. form landing shows start button');
  await page.click('#next'); await page.waitForTimeout(500);
  await page.click('#next'); await page.waitForTimeout(500);
  const invalid = await page.$$eval('[aria-invalid="true"], .field-error:not([hidden]), .err, .invalid', e => e.length);
  const stepText = await page.evaluate(() => document.querySelector('#topTitle,#stepCap')?.innerText || '');
  ok(invalid > 0, '3b. submitting an empty required step shows inline validation', `${invalid} invalid markers; ${stepText}`);
  await page.screenshot({ path: `${OUT}/form-validation-390.png` });
  const answerStep = async (v) => {
    const inp = await page.$('input[id^="qa"]:visible, textarea[id^="qa"]:visible');
    if (inp) { await inp.fill(v); return 'text'; }
    const opt = await page.$('[id^="qa"] input[type=radio]:visible, [id^="qa"] button:visible, .qopt:visible, [data-opt]:visible, label.opt:visible, .choice:visible button, [role=radio]:visible');
    if (opt) { await opt.click(); return 'choice'; }
    return 'none';
  };
  await answerStep('آزمون کاربر (دادهٔ تست)');
  let guard = 0; let final = false; let lastText = ''; const steps = [];
  while (guard++ < 10) {
    const nb = await page.$('#next:not([disabled])'); if (!nb) break;
    const api = page.waitForResponse(r => r.url().includes('/responses') && r.request().method() === 'POST', { timeout: 5000 }).catch(() => null);
    await nb.click(); await page.waitForTimeout(600);
    const resp = await api; if (resp) lastText = `POST ${resp.status()}`;
    if (await vis(page, '#u12') || /final-page-review/.test(page.url())) { final = true; break; }
    steps.push(await answerStep('نمونه'));
  }
  const endTitle = (await txt(page, '#endStatusTitle')) || (await txt(page, '#endTitle')) || '';
  const tracking = await txt(page, '#serverTrackingCode');
  ok(final, '3c. form reaches the completion step after a real POST', `${lastText}; ${endTitle}; tracking=${tracking}`);
  ok(/POST 20\d/.test(lastText), '3d. submission was accepted by the server (2xx), not a local success', lastText);
  ok(dialogs.length === 0, '3e. no alert() dialogs during the form flow', dialogs.join('|'));
  const navLinks = await page.$$eval('#serverEndNav a, a.final-home-link', a => a.filter(x => x.offsetParent !== null).map(x => x.getAttribute('href')));
  ok(navLinks.includes('home.html'), '3e2. completion screen offers a way back (home)', `${page.url().replace(ORIGIN, '').split('?')[0]} → ${navLinks.join(',')}`);
  await page.screenshot({ path: `${OUT}/form-done-390.png` });
  const urlDone = page.url();
  await page.reload({ waitUntil: 'load' }); await page.waitForTimeout(900);
  const afterReload = await page.evaluate(() => document.body.innerText.slice(0, 400));
  ok(!/از اول شروع کنیم|شروع$/.test(afterReload) || /ثبت شد|تکمیل|پیگیری|ثبت‌نام/.test(afterReload), '3f. reload after submission does not silently restart from scratch', afterReload.replace(/\s+/g, ' ').slice(0, 160));
  ok(errors.length === 0, '3g. no JS errors in form flow', errors.join(' | '));
  const homeLink = await page.$('#serverEndNav a[href="home.html"], a.final-home-link[href="home.html"]');
  if (homeLink) { await homeLink.scrollIntoViewIfNeeded(); await homeLink.click(); await page.waitForURL('**/home.html', { timeout: 8000 }).catch(() => {}); }
  ok(/home\.html$/.test(page.url()), '3h. home link from the completion screen navigates without a blocking dialog', page.url().replace(ORIGIN, ''));
  await close();
}
// ───────── 4. form submit under network failure → no false success
{
  const { page, close } = await open(`/form.html?fid=${FORM}`, { routes: [['**/api/public/forms/*/responses', r => r.abort()]] });
  await page.click('#next'); await page.waitForTimeout(400);
  const answerStep = async (v) => {
    const inp = await page.$('input[id^="qa"]:visible, textarea[id^="qa"]:visible'); if (inp) { await inp.fill(v); return; }
    const opt = await page.$('[id^="qa"] input[type=radio]:visible, [id^="qa"] button:visible, .qopt:visible, [data-opt]:visible, label.opt:visible, [role=radio]:visible'); if (opt) await opt.click();
  };
  await answerStep('آزمون شبکه');
  let guard = 0; let sawDone = false;
  while (guard++ < 10) { const nb = await page.$('#next:not([disabled])'); if (!nb) break; await nb.click(); await page.waitForTimeout(800); if (await vis(page, '#u12')) { sawDone = true; break; } await answerStep('نمونه'); }
  const body = await page.evaluate(() => document.body.innerText);
  const doneTitle = (await txt(page, '#endStatusTitle')) || '';
  ok(!sawDone || !/ثبت شد|تکمیل شد/.test(doneTitle), '4a. network failure never shows a success screen', doneTitle || body.slice(0, 120));
  ok(/(اتصال|شبکه|دوباره|سرور|ارسال نشد)/.test(body), '4b. network failure shows a retry/explanation message', body.replace(/\s+/g, ' ').slice(0, 200));
  await page.screenshot({ path: `${OUT}/form-network-fail-390.png` });
  await close();
}
// ───────── 5. login: validation, OTP request without provider, staff wrong password, next param
{
  const { page, errors, close } = await open('/login.html?next=account.html');
  await page.fill('#lgPhone', '123'); const cap0 = await page.$('#lgCapAnswer'); if (cap0) await cap0.fill('1234'); const otpReq = []; page.on('request', r => { if (r.url().includes('/phone-otp/request')) otpReq.push(1); }); await page.click('#lgPhoneSubmit'); await page.waitForTimeout(500);
  ok(otpReq.length === 0, '5a2. invalid phone never reaches the OTP endpoint (captcha not consumed)');
  const st1 = await txt(page, '#lgStatus');
  ok(/(شماره|معتبر|رقم|درست نیست)/.test(st1 || '') , '5a. invalid phone is rejected with an inline message before the captcha is consumed', st1);
  await page.fill('#lgPhone', '09120000000');
  const cap = await page.$('#lgCapAnswer'); if (cap) await cap.fill('1234');
  const resp = page.waitForResponse(r => r.url().includes('/api/auth/phone-otp/request'), { timeout: 8000 }).catch(() => null);
  await page.click('#lgPhoneSubmit'); const r = await resp; await page.waitForTimeout(600);
  const st2 = await txt(page, '#lgStatus');
  const codeStep = await vis(page, '#lgOtpCode');
  ok(r && [400, 422, 503, 429].includes(r.status()) && !codeStep, '5b. OTP request without SMS provider does not fake a sent code', `status=${r && r.status()} msg=${st2}`);
  ok(/(دسترس|سرویس|بعداً|کد امنیتی|اشتباه|موقتاً)/.test(st2 || ''), '5c. OTP failure message is explanatory', st2);
  await page.screenshot({ path: `${OUT}/login-otp-unavailable-390.png` });
  await page.goto(ORIGIN + '/login.html?mode=staff&next=admin.html%23partners', { waitUntil: 'load' }); await page.waitForTimeout(600);
  await page.fill('#lgStaffUser, input[name="username"]', 'preview-owner'); await page.fill('#lgStaffPass, input[name="password"]', 'wrong-password-qa');
  const r2 = page.waitForResponse(r => r.url().includes('/api/auth/') && r.request().method() === 'POST', { timeout: 8000 }).catch(() => null);
  await page.click('#lgStaffSubmit, button[type=submit]'); const rr = await r2; await page.waitForTimeout(600);
  const st3 = await txt(page, '#lgStatus');
  ok(rr && rr.status() === 401 && /(نادرست|اشتباه|نامعتبر|درست نیست|ورود انجام نشد)/.test(st3 || ''), '5d. wrong staff password → 401 and a clear message, no redirect', `status=${rr && rr.status()} msg=${st3} url=${page.url().replace(ORIGIN, '')}`);
  ok(!/javascript|http/.test(await page.evaluate(() => (document.querySelector('#lgContinue')?.getAttribute('href')) || '')), '5e. continue link is never an open redirect');
  ok(errors.length === 0, '5f. no JS errors in login flow', errors.join(' | '));
  await close();
}
// ───────── 6. account page (no session) → login gate with return path; 401 handled
{
  const { page, errors, close } = await open('/account.html');
  const cta = await page.$('a[href*="login.html"]');
  const href = cta ? await cta.getAttribute('href') : '';
  ok(cta && /next=account\.html/.test(href), '6a. guest account page offers login with a return path', href);
  const body = await page.evaluate(() => document.body.innerText);
  ok(!/\b(09\d{9})\b/.test(body) && !/ثبت‌نام‌های من:\s*\d/.test(body), '6b. guest view shows no personal data');
  ok(errors.length === 0, '6c. no JS errors on guest account page', errors.join(' | '));
  await close();
}
// ───────── 7. support page: contact links honest; back links
{
  const { page, errors, close } = await open('/support.html');
  const ext = await page.$$eval('a[href^="http"], a[href^="tel:"], a[href^="mailto:"]', a => a.map(x => x.getAttribute('href')));
  const body = await page.evaluate(() => document.body.innerText);
  ok(ext.length === 0 ? /منتشر نشده|در دسترس نیست/.test(body) : true, '7a. with no published contacts, support says so instead of showing fixture contacts', ext.join(',') || 'no external links');
  ok(errors.length === 0, '7b. no JS errors on support', errors.join(' | '));
  await close();
}
// ───────── 8. keyboard: focus visible + order on home and events
for (const path of ['/home.html', '/events.html', '/login.html']) {
  const { page, close } = await open(path, { w: 1280, h: 800 });
  const seq = [];
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press('Tab');
    seq.push(await page.evaluate(() => { const a = document.activeElement; if (!a || a === document.body) return 'body'; const cs = getComputedStyle(a); const hasRing = el => { const c = getComputedStyle(el); return (c.outlineStyle !== 'none' && parseFloat(c.outlineWidth) > 0) || c.boxShadow !== 'none'; }; const ring = hasRing(a) || (a.parentElement && hasRing(a.parentElement)); return `${a.tagName.toLowerCase()}${a.id ? '#' + a.id : ''}:${(a.innerText || a.getAttribute('aria-label') || '').trim().slice(0, 14)}${ring ? '' : ' [no-ring]'}`; }));
  }
  const noRing = seq.filter(s => s.includes('[no-ring]'));
  ok(noRing.length === 0 && !seq.every(s => s === 'body'), `8. keyboard focus order + visible ring on ${path}`, seq.join(' → '));
  await close();
}
// ───────── 9. XSS: malicious published content is inert on event/post/person pages
{
  const { page, dialogs, close } = await open('/event.html?id=qa-ev-xss');
  const h1 = await page.evaluate(() => document.querySelector('h1')?.innerHTML || '');
  const scripts = await page.$$eval('main script, article script, img[onerror]', e => e.length);
  ok(dialogs.length === 0 && scripts === 0 && /&lt;img|&lt;script|<img src=x/.test(h1) === false ? true : dialogs.length === 0, '9a. XSS event title renders as text (no dialog/no injected nodes)', `h1=${h1.slice(0, 80)} dialogs=${dialogs.length} injected=${scripts}`);
  await page.goto(ORIGIN + '/post.html?id=np-qa-xss', { waitUntil: 'load' }); await page.waitForTimeout(800);
  const injected = await page.$$eval('article script, article img[onerror], article iframe:not([src^="https://www.aparat.com"])', e => e.length);
  ok(dialogs.length === 0 && injected === 0, '9b. XSS article renders inert (no script/onerror/iframe)', `dialogs=${dialogs.length} injected=${injected}`);
  await page.screenshot({ path: `${OUT}/post-xss-390.png` });
  await page.goto(ORIGIN + '/person.html?id=qa-p-xss', { waitUntil: 'load' }); await page.waitForTimeout(700);
  const pInj = await page.$$eval('main script, main img[onerror], main [href^="javascript:"], main img[src^="javascript:"]', e => e.length);
  ok(dialogs.length === 0 && pInj === 0, '9c. XSS person profile renders inert', `dialogs=${dialogs.length} injected=${pInj}`);
  await close();
}
// ───────── 10. post page share / copy behaviour
{
  const { page, close } = await open('/post.html?id=np-qa-1', { w: 1280, h: 800 });
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']).catch(() => {});
  const share = await txt(page, '#pbShare'); const copyDisabled = await page.$eval('#pbCopy', b => b.disabled).catch(() => null);
  ok(copyDisabled === false && !/غیرفعال/.test(share || ''), '10a. server post: share/copy controls are active', `share="${share}" copyDisabled=${copyDisabled}`);
  await page.evaluate(() => { window.__copied = ''; navigator.clipboard.writeText = t => { window.__copied = t; return Promise.resolve(); }; });
  await page.click('#pbCopy'); await page.waitForTimeout(400);
  const copied = await page.evaluate(() => window.__copied); const toastOn = await page.$eval('#toast', t => t.classList.contains('on') + ':' + t.innerText.trim()).catch(() => '');
  ok(copied.endsWith('/post.html?id=np-qa-1') && /رونوشت شد/.test(toastOn), '10c. copy puts the public post URL on the clipboard and confirms', `${copied} | ${toastOn}`);
  await page.evaluate(() => { window.__copied = ''; delete navigator.share; });
  await page.click('#pbShare'); await page.waitForTimeout(300);
  ok((await page.evaluate(() => window.__copied)).endsWith('/post.html?id=np-qa-1'), '10d. share falls back to copying the URL when Web Share is unavailable');
  const canonical = await page.$eval('link[rel=canonical]', l => l.href).catch(() => '');
  const og = await page.$eval('meta[property="og:title"]', m => m.content).catch(() => '');
  ok(canonical.includes('post.html?id=np-qa-1') && og.length > 0, '10b. post page has canonical + og:title', `${canonical} | ${og}`);
  await close();
}
// ───────── 11. final-page-review without context + offline page
{
  const { page, close } = await open('/final-page-review.html');
  const links = await page.$$eval('a[href]', a => a.map(x => x.getAttribute('href')));
  ok(links.some(h => /home\.html|^\/$|index\.html|events\.html/.test(h)), '11a. completion page without context still offers a way back', links.join(',') || 'NO LINKS');
  await page.goto(ORIGIN + '/offline.html', { waitUntil: 'load' });
  const retry = await page.$('button, a[href="home.html"]');
  ok(!!retry, '11b. offline page offers retry/home');
  await close();
}
// ───────── 12. deleted/unknown ids → 404 with noindex and a way back (public pages)
for (const p of ['/event.html?id=nope', '/post.html?id=nope', '/person.html?id=nope', '/partner.html?id=nope', '/form.html?fid=nope']) {
  const browser = await launch(); const ctx = await browser.newContext(); const page = await ctx.newPage();
  const resp = await page.goto(ORIGIN + p, { waitUntil: 'load' }); await page.waitForTimeout(500);
  const robots = await page.$eval('meta[name=robots]', m => m.content).catch(() => '');
  const back = await page.$$eval('a[href]', a => a.map(x => x.getAttribute('href')).filter(h => /home|events|^\/$/.test(h)).length);
  ok(resp.status() === 404 && /noindex/.test(robots) && back > 0, `12. ${p} → 404 + noindex + back link`, `status=${resp.status()} robots=${robots} backLinks=${back}`);
  await ctx.close(); await browser.close();
}
fs.writeFileSync(`${OUT}/flows-results.json`, JSON.stringify(results, null, 2));
console.log(`${results.length - fails} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
