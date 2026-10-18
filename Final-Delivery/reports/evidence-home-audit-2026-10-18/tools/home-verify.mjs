// Home banner behaviour verification in the isolated test env (real browser, real API, test data only).
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const ORIGIN = 'http://127.0.0.1:8000';
const OUT = '/tmp/qa/home-verify'; fs.mkdirSync(OUT, { recursive: true });
const PY = '/home/user/venvs/nora/bin/python';
const seed = (...args) => execFileSync(PY, ['/tmp/nora-preview/seed_site_content.py', ...args], { cwd: '/tmp/nora-preview' }).toString().trim();
const results = []; let fails = 0;
const ok = (cond, name, detail = '') => { results.push({ ok: !!cond, name, detail }); if (!cond) fails++; console.log((cond ? 'PASS ' : 'FAIL ') + name + (detail ? ' — ' + detail : '')); };

async function open(w, h, { theme = '', abortApi = false } = {}) {
  let browser; for (let i = 0; i < 4; i++) { try { browser = await launchBrowser(); break; } catch (e) { if (i === 3) throw e; await new Promise(r => setTimeout(r, 1500)); } }
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'fa-IR', serviceWorkers: 'block', isMobile: w < 600, hasTouch: w < 600 });
  const page = await ctx.newPage();
  const errors = []; page.on('pageerror', e => errors.push(String(e.message))); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  const api = []; page.on('request', r => { if (r.url().includes('/api/')) api.push(r.url().replace(ORIGIN, '')); });
  if (theme) await page.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, theme);
  if (abortApi) await page.route('**/api/public/site-content', r => r.abort());
  await page.goto(ORIGIN + '/home.html', { waitUntil: 'load' });
  await page.waitForFunction(() => window.NORA_PUBLIC_SOURCE, null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(500);
  return { browser, page, errors, api };
}
const state = page => page.evaluate(() => {
  const b = document.getElementById('bnr'); const slides = [...document.querySelectorAll('#bsdeck .bs')];
  return { source: window.NORA_PUBLIC_SOURCE, hidden: b.hidden, intro: b.classList.contains('is-intro'), n: slides.length,
    titles: slides.map(s => s.querySelector('h2').textContent), kinds: slides.map(s => [...s.querySelectorAll('.btag-kind')].map(t => t.textContent)),
    links: slides.map(s => [...s.querySelectorAll('a.bbtn')].map(a => a.getAttribute('href'))),
    navHidden: document.querySelector('#bnr .bnav').hidden, dotsHidden: document.getElementById('bdots').hidden,
    scrollW: document.documentElement.scrollWidth, innerW: innerWidth, imgs: slides.map(s => { const i = s.querySelector('.bs-media img'); return i ? { src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0 } : null; }) };
});

// 1) server content, no banners → intro (mobile + desktop, light + dark)
console.log(seed('--no-banners'));
for (const [w, h, theme] of [[390, 844, ''], [1280, 800, ''], [390, 844, 'dark'], [1280, 800, 'dark']]) {
  const { browser, page, errors, api } = await open(w, h, { theme });
  const s = await state(page);
  ok(s.source === 'server' && !s.hidden && s.intro && s.n === 1 && s.titles[0].includes('خط زندگی'), `intro banner visible ${w}x${h} ${theme || 'light'}`, JSON.stringify({ links: s.links, imgs: s.imgs }));
  ok(s.links[0][0] === 'events.html' && s.links[0][1] === 'home.html#articles', 'intro CTAs point to real pages', JSON.stringify(s.links));
  ok(s.imgs[0] && s.imgs[0].ok, 'intro background image loaded', JSON.stringify(s.imgs));
  ok(s.navHidden && s.dotsHidden, 'intro has no slide controls');
  ok(s.scrollW <= s.innerW, `no horizontal scroll ${w}`, `${s.scrollW}/${s.innerW}`);
  ok(errors.length === 0, `no JS errors ${w} ${theme || 'light'}`, errors.join(' | '));
  ok(api.filter(u => u.startsWith('/api/public/site-content')).length === 1 && api.every(u => u.startsWith('/api/public/site-content') || u.startsWith('/api/auth/') || u.startsWith('/api/health')), 'no new API calls', api.join(','));
  await page.screenshot({ path: `${OUT}/intro-${w}-${theme || 'light'}.png` });
  if (w === 390 && !theme) {
    // CTA navigation
    await page.click('#bsdeck a.bbtn:not(.ghost)');
    await page.waitForURL('**/events.html', { timeout: 10000 });
    ok(page.url().endsWith('/events.html'), 'primary CTA navigates to events.html', page.url());
    await page.goBack({ waitUntil: 'load' }); await page.waitForTimeout(800);
    const y0 = await page.evaluate(() => scrollY);
    await page.click('#bsdeck a.bbtn.ghost'); await page.waitForTimeout(1200);
    const y1 = await page.evaluate(() => ({ y: scrollY, hash: location.hash, top: document.getElementById('articles').getBoundingClientRect().top }));
    ok(y1.hash === '#articles' && y1.y > y0 && y1.top < 200, 'secondary CTA scrolls to articles section', JSON.stringify({ y0, y1 }));
    // keyboard focus visible on CTA
    await page.goto(ORIGIN + '/home.html', { waitUntil: 'load' }); await page.waitForTimeout(800);
    await page.focus('#bsdeck a.bbtn:not(.ghost)');
    const focusInfo = await page.evaluate(() => { const a = document.activeElement; const r = a.getBoundingClientRect(); return { tag: a.tagName, text: a.textContent.trim(), inView: r.top >= 0 && r.bottom <= innerHeight }; });
    ok(focusInfo.tag === 'A' && focusInfo.inView, 'CTA is keyboard focusable and in view', JSON.stringify(focusInfo));
  }
  await browser.close();
}

// 2) published banners (2 live + draft + inactive + expired) → real banners only, intro absent, controls visible
console.log(seed('--with-banners'));
{
  const { browser, page, errors } = await open(390, 844);
  const s = await state(page);
  ok(!s.hidden && !s.intro && s.n === 2 && s.titles.every(t => t.includes('دادهٔ تست')) && !s.titles.some(t => /پیش‌نویس|غیرفعال|منقضی/.test(t)), 'published banners replace intro; draft/inactive/expired hidden', JSON.stringify(s.titles));
  ok(!s.navHidden && !s.dotsHidden, 'slide controls visible for 2 banners');
  await page.click('#bnr [data-bnext]'); await page.waitForTimeout(400);
  const slide = await page.evaluate(() => ({ tf: document.getElementById('bsdeck').style.transform, on: [...document.querySelectorAll('#bdots button')].findIndex(b => b.classList.contains('on')) }));
  ok(slide.on === 1, 'next control moves to slide 2', JSON.stringify(slide));
  await page.screenshot({ path: `${OUT}/published-390.png` });
  ok(errors.length === 0, 'no JS errors with published banners', errors.join(' | '));
  await browser.close();
}

// 3) sponsored kind → «تبلیغ» label
{
  execFileSync(PY, ['-c', `
import sys; sys.path.insert(0,'/tmp/nora-preview')
from owner_api import call, login
login(); st,cur=call('GET','/api/owner/site-content'); v=cur['version']
b=[{"id":"qa-ad","status":"published","active":True,"order":0,"t":"بنر تبلیغاتی آزمایشی (دادهٔ تست)","kind":"sponsored","href":"support.html","primaryLabel":"جزئیات","theme":"amber"},
   {"id":"qa-partner","status":"published","active":True,"order":1,"t":"بنر حامی آزمایشی (دادهٔ تست)","kind":"partner","theme":"plum"},
   {"id":"qa-bad-kind","status":"published","active":True,"order":2,"t":"بنر با نوع نامعتبر (دادهٔ تست)","kind":"javascript:x"}]
st,body=call('PATCH','/api/owner/site-content',{"content":{"banners":b},"expected_version":v}); print(st, [ (x['id'],x['kind']) for x in body['content']['banners']])
`], { stdio: 'inherit' });
  const { browser, page, errors } = await open(1280, 800);
  const s = await state(page);
  ok(s.n === 3 && JSON.stringify(s.kinds) === JSON.stringify([['تبلیغ'], ['حامی'], []]), 'kind labels: sponsored→تبلیغ, partner→حامی, invalid→none', JSON.stringify(s.kinds));
  await page.screenshot({ path: `${OUT}/sponsored-1280.png` });
  ok(errors.length === 0, 'no JS errors with kind labels', errors.join(' | '));
  await browser.close();
}

// 4) owner disables banner → nothing (not even intro)
console.log(seed('--no-banners', '--banners-disabled'));
{
  const { browser, page } = await open(390, 844);
  const s = await state(page);
  ok(s.hidden && s.n === 0, 'banner_settings.enabled=false hides intro too', JSON.stringify(s));
  await page.screenshot({ path: `${OUT}/disabled-390.png` });
  await browser.close();
}

// 5) API unavailable → hidden (status card explains), no fake banner
console.log(seed('--no-banners'));
{
  const { browser, page, errors } = await open(390, 844, { abortApi: true });
  const s = await state(page);
  const status = await page.evaluate(() => ({ hidden: document.getElementById('publicContentStatus').hidden, title: document.getElementById('publicContentStatusTitle').textContent }));
  ok(s.source === 'unavailable' && s.hidden && s.n === 0 && !status.hidden, 'API unavailable: banner hidden, status card shown', JSON.stringify({ s, status }));
  ok(errors.filter(e => !/net::ERR_FAILED|Failed to load resource/.test(e)).length === 0, 'no JS errors when API unavailable', errors.join(' | '));
  await page.screenshot({ path: `${OUT}/unavailable-390.png` });
  await browser.close();
}

// 6) 'empty' source (404 site_content_not_published) → intro visible
execFileSync(PY, ['-c', "import sqlite3; c=sqlite3.connect('/tmp/nora-preview/nora-preview.db'); c.execute(\"delete from site_content where id='public'\"); c.commit(); print('site_content cleared (test db)')"], { stdio: 'inherit' });
{
  const { browser, page, errors } = await open(390, 844);
  const s = await state(page);
  const status = await page.evaluate(() => ({ hidden: document.getElementById('publicContentStatus').hidden, title: document.getElementById('publicContentStatusTitle').textContent }));
  ok(s.source === 'empty' && !s.hidden && s.intro && s.n === 1 && !status.hidden, 'nothing published yet: intro visible + status card', JSON.stringify({ s: { source: s.source, hidden: s.hidden, intro: s.intro }, status }));
  ok(errors.filter(e => !/404/.test(e)).length === 0, 'no JS errors in empty state', errors.join(' | '));
  await page.screenshot({ path: `${OUT}/empty-390.png` });
  await browser.close();
}
console.log(seed('--no-banners'));
fs.writeFileSync(`${OUT}/result.json`, JSON.stringify(results, null, 2));
console.log(`\n${results.length - fails} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
