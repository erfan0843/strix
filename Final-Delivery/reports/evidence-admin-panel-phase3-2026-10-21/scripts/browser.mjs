/* شواهد مرورگری مرحلهٔ سوم روی سرور آزمایشی محلی (127.0.0.1:8000)؛ فقط حساب‌های آزمایشی. */
import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs';
import { createRequire } from 'node:module';
const dep = createRequire('/home/user/nora-node/package.json');
const { chromium: pw } = dep('playwright-core');
const B = 'http://127.0.0.1:8000';
const OUT = '/tmp/qa/p3/ui';
const log = [];
const say = (m) => { log.push(m); console.log(m); };
async function launch() {
  const mod = dep('@sparticuz/chromium'); const chromium = mod.default || mod;
  const moduleRoot = path.resolve(path.dirname(dep.resolve('@sparticuz/chromium')), '..');
  const { inflate } = await import('file://' + path.join(moduleRoot, 'build/lambdafs.js'));
  await inflate(path.join(moduleRoot, 'bin/al2023.tar.br'));
  const executablePath = await chromium.executablePath();
  const env = { ...process.env };
  const libraries = path.join(os.tmpdir(), 'al2023/lib');
  if (fs.existsSync(libraries)) env.LD_LIBRARY_PATH = [libraries, env.LD_LIBRARY_PATH].filter(Boolean).join(path.delimiter);
  const fonts = path.join(os.tmpdir(), 'fonts'); if (fs.existsSync(fonts)) env.FONTCONFIG_PATH = fonts;
  return pw.launch({ executablePath, headless: true, args: chromium.args.filter((a) => !['--single-process', '--disable-web-security', '--allow-running-insecure-content'].includes(a)), env });
}
const ownerPw = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const managerPw = fs.readFileSync('/tmp/nora-preview/manager-pw.txt', 'utf8').trim();
const ownerUser = fs.readFileSync('/tmp/nora-preview/env.sh', 'utf8').match(/NORA_OWNER_USERNAME=(\S+)/)[1].replace(/['"]/g, '');
const state = JSON.parse(fs.readFileSync('/tmp/qa/p3/media/state.json', 'utf8'));

async function staffLogin(page, username, password) {
  await page.goto(`${B}/login.html?mode=staff&next=admin.html%23dash`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#lgStaffUsername', { timeout: 20000 });
  await page.fill('#lgStaffUsername', username);
  await page.fill('#lgStaffPassword', password);
  await page.click('#lgStaffSubmit');
  await Promise.race([
    page.waitForSelector('#lgContinue', { timeout: 15000 }).then(() => page.click('#lgContinue')).catch(() => {}),
    page.waitForURL(/admin\.html/, { timeout: 15000 }).catch(() => {}),
  ]);
  await page.waitForURL(/admin\.html/, { timeout: 15000 });
  await page.waitForSelector('#admBar .server-identity', { timeout: 15000 });
}
async function shot(page, name) { await page.screenshot({ path: path.join(OUT, name + '.png') }); say('shot ' + name); }
async function goSec(page, sec) {
  await page.evaluate((s) => { location.hash = s; }, '#' + sec);
  await page.waitForTimeout(400);
}
const text = (page) => page.evaluate(() => document.querySelector('#admBody').innerText);

const browser = await launch();
try {
  const ONLY = process.argv[2] || '';
  if (!ONLY || ONLY === 'owner') {
  /* ── مالک، دسکتاپ روشن ── */
  let ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fa-IR' });
  let page = await ctx.newPage();
  const errors = []; page.on('pageerror', (e) => errors.push(String(e)));
  await staffLogin(page, ownerUser, ownerPw);
  await goSec(page, 'users');
  await page.waitForSelector('[data-open-cert]', { timeout: 15000 });
  await page.click('[data-open-cert]');
  await page.waitForSelector('[data-cert-open]', { timeout: 15000 });
  await shot(page, '01-owner-cert-list-desktop-light');
  say('cert list rows: ' + await page.locator('[data-cert-open]').count());
  await page.click('[data-cert-status="revoked"]');
  await page.waitForFunction(() => document.querySelectorAll('[data-cert-open]').length === 1, null, { timeout: 10000 });
  await shot(page, '02-owner-cert-filter-revoked-desktop-light');
  await page.click('[data-cert-status=""]');
  await page.waitForFunction(() => document.querySelectorAll('[data-cert-open]').length > 1, null, { timeout: 10000 });
  await page.fill('#certQuery', 'NC-0003');
  await page.click('[data-cert-search]');
  await page.waitForFunction(() => document.querySelectorAll('[data-cert-open]').length === 1, null, { timeout: 10000 });
  await shot(page, '03-owner-cert-search-desktop-light');
  await page.click('[data-cert-open]');
  await page.waitForSelector('[data-cert-detail]', { timeout: 10000 });
  await page.waitForFunction(() => /کد استعلام|سریال/.test(document.querySelector('[data-cert-detail]').innerText), null, { timeout: 10000 });
  await shot(page, '04-owner-cert-detail-desktop-light');
  const fileHref = await page.evaluate(() => { const a = document.querySelector('[data-cert-file]'); return a ? a.getAttribute('href') : ''; });
  if (fileHref) {
    const probe = await page.evaluate(async (href) => { const r = await fetch(href, { credentials: 'same-origin' }); return { status: r.status, type: r.headers.get('content-type'), disp: r.headers.get('content-disposition'), cache: r.headers.get('cache-control') }; }, fileHref);
    say('cert file ' + fileHref + ' -> ' + JSON.stringify(probe));
  } else say('cert file link: none for this record');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-cert-detail]', { timeout: 15000 });
  await page.waitForFunction(() => /کد استعلام|سریال/.test(document.querySelector('[data-cert-detail]').innerText), null, { timeout: 10000 });
  await shot(page, '05-owner-cert-detail-after-reload-desktop-light');
  await page.click('[data-cert-back]');
  await page.waitForSelector('[data-cert-panel]', { timeout: 10000 });

  /* باشگاه: یادداشت صادقانه */
  await page.click('[data-uback]');
  await page.waitForSelector('[data-open-club]', { timeout: 10000 });
  await page.click('[data-open-club]');
  await page.waitForSelector('[data-club-panel]', { timeout: 10000 });
  await shot(page, '06-owner-club-note-desktop-light');

  /* ── پوستر رویداد: بارگذاری واقعی ── */
  await goSec(page, 'events');
  await page.waitForSelector('[data-ct-new]', { timeout: 15000 });
  await page.click('[data-ct-media]');
  await page.waitForSelector('[data-ct-media-panel] [data-ct-media-row]', { timeout: 15000 });
  await shot(page, '07-owner-media-list-in-use-desktop-light');
  await page.click('[data-ct-media-close]');
  await page.click('[data-ct-new]');
  await page.waitForSelector('[data-ct-image="poster"]', { state: 'attached', timeout: 10000 });
  await page.fill('#ctf_t', 'رویداد آزمایشی مرحلهٔ سوم (بارگذاری از مرورگر)');
  await page.fill('#ctf_on', '1405/09/05');
  await page.fill('#ctf_d', 'این رویداد فقط برای آزمون بارگذاری پوستر از پنل ساخته شده است.');
  await page.setInputFiles('[data-ct-image="poster"]', '/tmp/qa/p3/media/fake-image.png');
  await page.waitForSelector('[data-ct-image-state="error"]', { timeout: 15000 });
  await shot(page, '08-owner-event-editor-upload-rejected-desktop-light');
  say('rejected upload message: ' + await page.evaluate(() => document.querySelector('[data-ct-image-state="error"]').innerText));
  await page.setInputFiles('[data-ct-image="poster"]', '/tmp/qa/p3/media/poster-ok.jpg');
  await page.waitForSelector('img[src^="/api/public/media/"]', { timeout: 20000 });
  await page.waitForFunction(() => !document.querySelector('[data-ct-image-state]'), null, { timeout: 10000 });
  const posterUrl = await page.evaluate(() => document.querySelector('img[src^="/api/public/media/"]').getAttribute('src'));
  say('uploaded poster url: ' + posterUrl);
  await shot(page, '09-owner-event-editor-upload-ok-desktop-light');
  await page.click('[data-ct-save]');
  await page.waitForFunction(() => !document.querySelector('[data-ct-save]') && document.querySelector('[data-ct-panel]'), null, { timeout: 15000 });
  await shot(page, '10-owner-events-list-after-save-desktop-light');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-ct-edit]', { timeout: 15000 });
  const editId = await page.evaluate(() => { const rows = [...document.querySelectorAll('[data-ct-edit]')]; const hit = rows.find((b) => b.closest('[data-ct-row]') && b.closest('[data-ct-row]').innerText.includes('بارگذاری از مرورگر')) || rows[0]; return hit.dataset.ctEdit; });
  await page.click(`[data-ct-edit="${editId}"]`);
  await page.waitForSelector('[data-ct-image="poster"]', { state: 'attached', timeout: 10000 });
  const persisted = await page.evaluate(() => { const i = document.querySelector('img[src^="/api/public/media/"]'); return i ? i.getAttribute('src') : ''; });
  say('poster after reload: ' + persisted + (persisted === posterUrl ? ' (same)' : ' (DIFFERENT!)'));
  await shot(page, '11-owner-event-editor-after-reload-desktop-light');
  const pubProbe = await page.evaluate(async (u) => { const r = await fetch(u, { credentials: 'omit', cache: 'no-store' }); return { status: r.status, type: r.headers.get('content-type'), cache: r.headers.get('cache-control') }; }, posterUrl);
  say('public GET ' + posterUrl + ' -> ' + JSON.stringify(pubProbe));
  await page.click('[data-ct-cancel]');
  say('owner page errors: ' + JSON.stringify(errors));
  await ctx.close();

  /* ── مالک، موبایل ── */
  ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'fa-IR', isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  page = await ctx.newPage();
  await staffLogin(page, ownerUser, ownerPw);
  await goSec(page, 'users');
  await page.waitForSelector('[data-open-cert]', { timeout: 15000 });
  await page.click('[data-open-cert]');
  await page.waitForSelector('[data-cert-open]', { timeout: 15000 });
  await shot(page, '12-owner-cert-list-mobile-light');
  await page.click('[data-cert-open]');
  await page.waitForSelector('[data-cert-detail]', { timeout: 10000 });
  await shot(page, '13-owner-cert-detail-mobile-light');
  await goSec(page, 'events');
  await page.waitForSelector('[data-ct-new]', { timeout: 15000 });
  await page.click('[data-ct-new]');
  await page.waitForSelector('[data-ct-image="poster"]', { state: 'attached', timeout: 10000 });
  await page.setInputFiles('[data-ct-image="poster"]', '/tmp/qa/p3/media/poster-ok.png');
  await page.waitForSelector('img[src^="/api/public/media/"]', { timeout: 20000 });
  await shot(page, '14-owner-event-editor-upload-mobile-light');
  await page.click('[data-ct-cancel]');
  await ctx.close();
  }
  if (!ONLY || ONLY === 'manager') {
  /* ── مدیر (رمز مدیر)، موبایل تیره ── */
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'fa-IR', isMobile: true, hasTouch: true, deviceScaleFactor: 2, colorScheme: 'dark' });
  const page = await ctx.newPage();
  const mErrors = []; page.on('pageerror', (e) => mErrors.push(String(e)));
  await staffLogin(page, 'qa-manager', managerPw);
  await goSec(page, 'users');
  await page.waitForSelector('[data-open-cert]', { timeout: 15000 });
  await page.click('[data-open-cert]');
  await page.waitForSelector('[data-cert-open]', { timeout: 15000 });
  await shot(page, '15-manager-cert-list-mobile-dark');
  say('manager sees revoke/issue buttons: ' + await page.locator('[data-cert-revoke],[data-cert-issue]').count());
  await page.click('[data-cert-open]');
  await page.waitForSelector('[data-cert-detail]', { timeout: 10000 });
  await shot(page, '16-manager-cert-detail-mobile-dark');
  const mText = await text(page);
  say('manager detail leaks phone/token? ' + (/09\d{9}|token|hash/i.test(mText) ? 'YES' : 'no'));
  await goSec(page, 'events');
  await page.waitForSelector('[data-ct-media]', { timeout: 15000 });
  await page.click('[data-ct-media]');
  await page.waitForSelector('[data-ct-media-panel] [data-ct-media-row]', { timeout: 15000 });
  await shot(page, '17-manager-media-list-mobile-dark');
  say('manager delete buttons for in-use rows: ' + await page.evaluate(() => [...document.querySelectorAll('[data-ct-media-row]')].filter((r) => r.innerText.includes('در حال استفاده') && r.querySelector('[data-ct-media-del]')).length));
  /* دستکاری شناسه: جزئیات گواهی با شناسهٔ جعلی */
  const tamper = await page.evaluate(async () => { const r = await fetch('/api/admin/certificates/00000000-0000-4000-8000-000000000000', { credentials: 'same-origin' }); return { status: r.status, body: (await r.text()).slice(0, 80) }; });
  say('manager tampered cert id -> ' + JSON.stringify(tamper));
  const tamper2 = await page.evaluate(async () => { const r = await fetch('/api/admin/certificates/not-a-uuid/file', { credentials: 'same-origin' }); return r.status; });
  say('manager tampered file id -> ' + tamper2);
  say('manager page errors: ' + JSON.stringify(mErrors));
  await ctx.close();
  }
} finally {
  await browser.close();
  fs.appendFileSync(path.join(OUT, 'browser-log.txt'), log.join('\n') + '\n');
}
