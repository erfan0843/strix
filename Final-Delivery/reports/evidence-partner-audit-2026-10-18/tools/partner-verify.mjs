// Partner page verification in the isolated test env (real browser, real API, test data only).
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const ORIGIN = 'http://127.0.0.1:8000';
const OUT = process.env.OUT || '/tmp/qa/partner-verify'; fs.mkdirSync(OUT, { recursive: true });
const results = []; let fails = 0;
const ok = (cond, name, detail = '') => { results.push({ ok: !!cond, name, detail: typeof detail === 'string' ? detail : JSON.stringify(detail) }); if (!cond) fails++; console.log((cond ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)) : '')); };
async function launch() { let b; for (let i = 0; i < 4; i++) { try { b = await launchBrowser(); break; } catch (e) { if (i === 3) throw e; await new Promise(r => setTimeout(r, 1500)); } } return b; }
async function open(w, h, path, { theme = '', abortApi = false } = {}) {
  const browser = await launch();
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'fa-IR', serviceWorkers: 'block', isMobile: w < 600, hasTouch: w < 600 });
  const page = await ctx.newPage();
  const errors = [], dialogs = []; page.on('pageerror', e => errors.push(String(e.message))); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('dialog', d => { dialogs.push(d.message()); d.dismiss(); });
  const api = []; page.on('request', r => { if (r.url().includes('/api/')) api.push(r.url().replace(ORIGIN, '')); });
  if (theme) await page.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, theme);
  if (abortApi) await page.route('**/api/public/site-content', r => r.abort());
  const response = await page.goto(ORIGIN + path, { waitUntil: 'load' });
  await page.waitForFunction(() => window.NORA_PUBLIC_SOURCE, null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(500);
  return { browser, page, errors, dialogs, api, status: response.status() };
}
const pageState = page => page.evaluate(() => {
  const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
  const img = q('.partner-logo img');
  return { source: window.NORA_PUBLIC_SOURCE, title: document.title, h1s: qa('h1').map(h => h.textContent), type: q('.partner-heading p')?.textContent || '',
    lead: q('.partner-lead')?.textContent || '', facts: qa('.partner-facts b').map(b => b.textContent), tags: qa('.partner-tags .tag').map(t => t.textContent),
    desc: q('.partner-desc')?.textContent || '', site: q('[data-partner-site]') ? { href: q('[data-partner-site]').getAttribute('href'), rel: q('[data-partner-site]').getAttribute('rel'), target: q('[data-partner-site]').getAttribute('target'), text: q('[data-partner-site]').textContent.trim() } : null,
    contacts: qa('.partner-contact').map(a => [a.dataset.partnerContact, a.getAttribute('href'), a.getAttribute('rel')]),
    events: qa('a.partner-event').map(a => a.getAttribute('href')), eventHeads: qa('.partner-section h2').map(h => h.textContent),
    logo: img ? { src: img.getAttribute('src'), loaded: img.complete && img.naturalWidth > 0 } : null, hasImageClass: !!q('.partner-logo.has-image'), monogram: q('.partner-logo span')?.textContent || '',
    jsLinks: qa('a[href^="javascript:"]').length, scripts: qa('.partner-profile script').length, imgsInProfile: qa('.partner-profile img').length,
    notFound: q('.partner-not-found h1')?.textContent || '', back: qa('a[href="home.html#partners"]').length,
    robots: q('meta[name="robots"]')?.content, canonical: q('link[rel="canonical"]')?.getAttribute('href') || '', desc_meta: q('meta[name="description"]')?.content,
    theme: document.documentElement.dataset.theme, scrollW: document.documentElement.scrollWidth, innerW: innerWidth,
    siteTextW: q('.partner-site b') ? q('.partner-site b').getBoundingClientRect().width : 0 };
});

// 1) home: partner cards are real links; click navigates to the partner page; footer badges are links
for (const [w, h] of [[390, 844], [1280, 800]]) {
  const tag = w < 600 ? 'mobile' : 'desktop';
  const { browser, page, errors, api } = await open(w, h, '/home.html');
  await page.evaluate(() => document.getElementById('partners').scrollIntoView({ block: 'start' })); await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/home-partners-${tag}.png` });
  const home = await page.evaluate(() => ({ cards: [...document.querySelectorAll('#logoWall > a.logo')].map(a => a.getAttribute('href')), buttons: document.querySelectorAll('#logoWall button').length,
    foot: [...document.querySelectorAll('#footLogos > a')].map(a => [a.getAttribute('href'), a.getAttribute('aria-label'), a.getBoundingClientRect().width]), sheet: !!document.getElementById('shPartner'),
    evChip: document.querySelector('#evTop a.mi-partner')?.getAttribute('href') || '', scrollW: document.documentElement.scrollWidth, innerW: innerWidth }));
  ok(home.cards.length === 4 && home.buttons === 0 && home.cards.every(href => /^partner\.html\?id=/.test(href)) && !home.sheet, `home ${tag}: 4 partner cards are real links, no sheet`, home.cards);
  ok(home.cards.includes('partner.html?id=qa%20partner%2F2%20%C3%BC'), `home ${tag}: id with space/slash/unicode is URL-encoded`, home.cards[1]);
  ok(home.foot.length === 4 && home.foot.every(f => /^partner\.html\?id=/.test(f[0]) && f[1] && f[2] >= 24), `home ${tag}: footer badges link to partner pages with aria-label and ≥24px targets`, home.foot);
  ok(home.evChip === 'partner.html?id=qa-partner-1', `home ${tag}: event card partner chip links to partner page`, home.evChip);
  const jsErrors = errors.filter(e => !/Failed to load resource.*404/.test(e)); /* the deliberately broken test logo 404s */
  ok(home.scrollW === home.innerW && jsErrors.length === 0, `home ${tag}: no horizontal scroll, no JS errors`, { scrollW: home.scrollW, errors });
  const brokenHome = await page.evaluate(() => { const a = document.querySelector('#logoWall a[href="partner.html?id=qa-partner-broken-logo"]'); return a ? { img: !!a.querySelector('img'), mon: a.querySelector('.mon').textContent.trim() } : null; });
  ok(brokenHome && !brokenHome.img && brokenHome.mon.length > 0, `home ${tag}: broken partner logo falls back to the monogram`, brokenHome);
  const first = await page.$('#logoWall > a.logo'); const bb = await first.boundingBox(); await page.mouse.click(bb.x + bb.width / 2, bb.y + bb.height / 2);
  await page.waitForURL(/partner\.html\?id=/, { timeout: 10000 }).catch(() => {}); await page.waitForFunction(() => document.querySelector('.partner-profile h1'), null, { timeout: 10000 }).catch(() => {});
  const landed = await page.evaluate(() => ({ url: location.pathname + location.search, h1: document.querySelector('.partner-profile h1')?.textContent || '' }));
  ok(landed.url === '/partner.html?id=qa-partner-1' && landed.h1 === 'نهاد همکار آزمایشی (دادهٔ تست)', `home ${tag}: clicking the card opens the same partner's page`, landed);
  await page.goBack({ waitUntil: 'load' }); await page.waitForTimeout(600);
  const back = await page.evaluate(() => ({ url: location.pathname, partnersVisible: !document.getElementById('partners').hidden }));
  ok(back.url === '/home.html' && back.partnersVisible, `home ${tag}: browser Back returns to home with partners section`, back);
  await browser.close();
}

// 2) full partner page: both sizes, light + dark
for (const [w, h, theme] of [[390, 844, ''], [1280, 800, ''], [390, 844, 'dark'], [1280, 800, 'dark']]) {
  const tag = `${w < 600 ? 'mobile' : 'desktop'}-${theme || 'light'}`;
  const { browser, page, errors, api, status } = await open(w, h, '/partner.html?id=qa-partner-1', { theme });
  const s = await pageState(page);
  await page.screenshot({ path: `${OUT}/partner-${tag}.png` });
  await page.screenshot({ path: `${OUT}/partner-${tag}-full.png`, fullPage: true });
  ok(status === 200 && s.source === 'server' && s.h1s.length === 1 && s.h1s[0] === 'نهاد همکار آزمایشی (دادهٔ تست)', `${tag}: HTTP 200, server source, single h1`, { status, h1s: s.h1s });
  ok(s.type === 'نهاد فرهنگی · آزمایشی' && /همراه برنامه‌های آموزشی/.test(s.lead) && s.facts.join('|') === 'برگزاری کارگاه (تست)|مهر ۱۴۰۵' && s.tags.join() === 'آموزش,کارگاه,کتاب‌خوانی' && /خط دوم شرح/.test(s.desc), `${tag}: type, lead, facts, focus tags, description rendered`, { type: s.type, facts: s.facts, tags: s.tags });
  ok(s.site && s.site.href === 'https://example.org/partner-test' && s.site.rel === 'noopener noreferrer' && s.site.target === '_blank' && /example\.org/.test(s.site.text), `${tag}: official website button is a real noopener link`, s.site);
  ok(JSON.stringify(s.contacts) === JSON.stringify([['mail', 'mailto:hello@example.org', null], ['tel', 'tel:+33123456789', null], ['tg', 'https://t.me/nora_test_channel', 'noopener noreferrer']]) && s.jsLinks === 0, `${tag}: contacts allowlisted; javascript:/other dropped`, s.contacts);
  ok(s.events.join() === 'event.html?id=qa-ev-1,event.html?id=qa-ev-past' && s.eventHeads.some(t => /پیش‌رو/.test(t)) && s.eventHeads.some(t => /برگزارشده/.test(t)), `${tag}: related events come only from event.partnerId (1 upcoming + 1 past)`, s.events);
  ok(s.logo && s.logo.loaded && s.hasImageClass, `${tag}: logo image loaded in the square frame`, s.logo);
  ok(s.title === 'نهاد همکار آزمایشی (دادهٔ تست) · نهادهای همکار نورا' && s.canonical === '/partner.html?id=qa-partner-1' && s.robots === 'index,follow', `${tag}: title/canonical/robots from server + client`, { title: s.title, canonical: s.canonical, robots: s.robots });
  ok(s.scrollW === s.innerW && errors.length === 0 && api.length === 1 && api[0] === '/api/public/site-content', `${tag}: no horizontal scroll, no JS errors, one API call`, { scrollW: s.scrollW, errors, api });
  ok(!theme || s.theme === 'dark', `${tag}: theme preserved`, s.theme);
  ok(s.back >= 3, `${tag}: back links to home#partners (topbar, breadcrumb, footer nav)`, s.back);
  if (!theme && w === 1280) {
    // keyboard: Tab reaches the website link with a visible focus ring
    let focused = null;
    for (let i = 0; i < 25; i++) { await page.keyboard.press('Tab'); focused = await page.evaluate(() => { const el = document.activeElement; const cs = getComputedStyle(el); return { site: el.matches('[data-partner-site]'), outline: cs.outlineStyle, width: cs.outlineWidth, inView: el.getBoundingClientRect().top >= 0 && el.getBoundingClientRect().bottom <= innerHeight }; }); if (focused.site) break; }
    ok(focused && focused.site && focused.outline !== 'none' && focused.width !== '0px' && focused.inView, 'desktop: Tab reaches the website link with a visible focus ring', focused);
    await page.screenshot({ path: `${OUT}/partner-desktop-focus.png` });
  }
  await browser.close();
}

// 3) long name / long URL / encoded id; 4) broken logo; 5) XSS; 6) missing; 7) API unavailable
{
  const { browser, page, errors, status } = await open(390, 844, '/partner.html?id=qa%20partner%2F2%20%C3%BC');
  const s = await pageState(page); await page.screenshot({ path: `${OUT}/partner-long-mobile.png`, fullPage: true });
  ok(status === 200 && /نام بسیار طولانی/.test(s.h1s[0] || '') && s.scrollW === s.innerW && s.siteTextW <= 390 && errors.length === 0, 'long name + long URL + encoded id: renders without overflow', { status, siteTextW: s.siteTextW, scrollW: s.scrollW });
  ok(!s.logo && s.monogram === 'طو' && s.events.length === 0 && s.eventHeads.every(t => !/رویداد/.test(t)), 'no logo → monogram; no related events → no empty section', { monogram: s.monogram, heads: s.eventHeads });
  await browser.close();
}
{
  const { browser, page, errors } = await open(1280, 800, '/partner.html?id=qa-partner-broken-logo');
  await page.waitForFunction(() => !document.querySelector('.partner-logo img'), null, { timeout: 8000 }).catch(() => {});
  const s = await pageState(page); await page.screenshot({ path: `${OUT}/partner-broken-logo-desktop.png` });
  ok(!s.logo && !s.hasImageClass && s.monogram.length > 0 && errors.filter(e => !/404|Failed to load resource/.test(e)).length === 0, 'broken logo → monogram fallback, no JS error', { monogram: s.monogram, errors });
  await browser.close();
}
{
  const { browser, page, errors, dialogs } = await open(1280, 800, '/partner.html?id=qa-partner-xss');
  const s = await pageState(page); await page.screenshot({ path: `${OUT}/partner-xss-desktop.png` });
  ok(s.h1s[0].startsWith('<img src=x onerror=alert(1)>') && s.imgsInProfile === 0 && s.scripts === 0 && s.jsLinks === 0 && !s.site && s.contacts.length === 0 && dialogs.length === 0 && errors.length === 0, 'malicious name/logo/href/links rendered as inert text; no dialog, image, script or link', { h1: s.h1s[0], dialogs, site: s.site });
  const ssr = await (await fetch(ORIGIN + '/partner.html?id=qa-partner-xss')).text();
  ok(!/<img src=x onerror/.test(ssr) && /&lt;img src=x onerror=alert\(1\)&gt;/.test(ssr), 'SSR fallback escapes the malicious name', '');
  await browser.close();
}
{
  const { browser, page, errors, status } = await open(390, 844, '/partner.html?id=qa-partner-does-not-exist');
  const s = await pageState(page); await page.screenshot({ path: `${OUT}/partner-missing-mobile.png` });
  ok(status === 404 && s.notFound === 'این نهاد همکار در دسترس نیست' && s.robots === 'noindex,nofollow,noarchive' && s.canonical === '' && s.back >= 1 && errors.filter(e => !/Failed to load resource.*404/.test(e)).length === 0, 'unknown id: real HTTP 404 + noindex + no canonical + human message', { status, robots: s.robots });
  await browser.close();
}
for (const id of ['qa-partner-unpublished', 'qa-partner-private', 'qa-partner-paused', 'qa-partner-pending']) {
  const res = await fetch(ORIGIN + '/partner.html?id=' + id); const text = await res.text();
  ok(res.status === 404 && !text.includes('(دادهٔ تست)') && /noindex,nofollow,noarchive/.test(text), `non-public partner ${id}: 404 and name not in SSR`, res.status);
}
{
  const pub = await (await fetch(ORIGIN + '/api/public/site-content')).json();
  const ids = pub.content.partners.map(p => p.id);
  ok(!ids.some(id => /unpublished|private|paused|pending/.test(id)) && ids.length === 4, 'public API exposes only the 4 public partners', ids);
  const ev = pub.content.events.find(e => e.id === 'qa-ev-1');
  ok(ev.partnerId === 'qa-partner-1' && !ev.partnerName, 'public API keeps event.partnerId and drops stale partnerName', ev.partnerId);
  const sitemap = await fetch(ORIGIN + '/sitemap.xml');
  ok(sitemap.status === 503, 'sitemap in test env without NORA_PUBLIC_BASE_URL answers 503 (absolute origin required; covered by pytest)', sitemap.status);
}
{
  const { browser, page, errors } = await open(390, 844, '/partner.html?id=qa-partner-1', { abortApi: true });
  const s = await pageState(page); await page.screenshot({ path: `${OUT}/partner-unavailable-mobile.png` });
  ok(s.source === 'unavailable' && s.notFound === 'محتوای زنده در دسترس نیست' && errors.filter(e => !/ERR_FAILED|Failed to load resource/.test(e)).length === 0, 'API unavailable: distinct human message, no JS error', { source: s.source, errors });
  await browser.close();
}
// 8) legacy hash + event page link + reload
{
  const { browser, page } = await open(390, 844, '/home.html#partner=qa-partner-1');
  await page.waitForURL(/partner\.html\?id=qa-partner-1/, { timeout: 10000 }).catch(() => {});
  const url = await page.evaluate(() => location.pathname + location.search);
  ok(url === '/partner.html?id=qa-partner-1', 'legacy home.html#partner=… redirects to the partner page', url);
  await page.reload({ waitUntil: 'load' }); await page.waitForFunction(() => document.querySelector('.partner-profile h1'), null, { timeout: 10000 }).catch(() => {});
  ok((await page.evaluate(() => document.querySelector('.partner-profile h1')?.textContent)) === 'نهاد همکار آزمایشی (دادهٔ تست)', 'direct URL survives reload', '');
  await page.goto(ORIGIN + '/event.html?id=qa-ev-1', { waitUntil: 'load' }); await page.waitForFunction(() => window.NORA_PUBLIC_SOURCE, null, { timeout: 15000 }).catch(() => {}); await page.waitForTimeout(400);
  const link = await page.evaluate(() => document.querySelector('a.event-partner-link')?.getAttribute('href') || '');
  ok(link === 'partner.html?id=qa-partner-1', 'event page links its partner to the partner page', link);
  await browser.close();
}
fs.writeFileSync(`${OUT}/result.json`, JSON.stringify(results, null, 2));
console.log(`${results.length - fails} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
