import path from 'node:path'; import os from 'node:os'; import fs from 'node:fs'; import { createRequire } from 'node:module';
const dep = createRequire('/home/user/nora-node/package.json'); const { chromium: pw } = dep('playwright-core');
const B = 'http://127.0.0.1:8000', OUT = '/tmp/qa/p3/ui', log = []; const say = (m) => { log.push(m); console.log(m); };
async function launch() { const mod = dep('@sparticuz/chromium'); const chromium = mod.default || mod; const root = path.resolve(path.dirname(dep.resolve('@sparticuz/chromium')), '..'); const { inflate } = await import('file://' + path.join(root, 'build/lambdafs.js')); await inflate(path.join(root, 'bin/al2023.tar.br')); const executablePath = await chromium.executablePath(); const env = { ...process.env }; const lib = path.join(os.tmpdir(), 'al2023/lib'); if (fs.existsSync(lib)) env.LD_LIBRARY_PATH = [lib, env.LD_LIBRARY_PATH].filter(Boolean).join(path.delimiter); const fonts = path.join(os.tmpdir(), 'fonts'); if (fs.existsSync(fonts)) env.FONTCONFIG_PATH = fonts; return pw.launch({ executablePath, headless: true, args: chromium.args.filter((a) => !['--single-process', '--disable-web-security', '--allow-running-insecure-content'].includes(a)), env }); }
const managerPw = fs.readFileSync('/tmp/nora-preview/manager-pw.txt', 'utf8').trim();
const state = JSON.parse(fs.readFileSync('/tmp/qa/p3/bale/state.json', 'utf8'));
async function staffLogin(page, u, p) { await page.goto(`${B}/login.html?mode=staff&next=admin.html%23dash`, { waitUntil: 'domcontentloaded' }); await page.waitForSelector('#lgStaffUsername', { timeout: 20000 }); await page.fill('#lgStaffUsername', u); await page.fill('#lgStaffPassword', p); await page.click('#lgStaffSubmit'); await Promise.race([page.waitForSelector('#lgContinue', { timeout: 15000 }).then(() => page.click('#lgContinue')).catch(() => {}), page.waitForURL(/admin\.html/, { timeout: 15000 }).catch(() => {})]); await page.waitForURL(/admin\.html/, { timeout: 15000 }); await page.waitForSelector('#admBar .server-identity', { timeout: 15000 }); }
const shot = async (page, n) => { await page.screenshot({ path: path.join(OUT, n + '.png') }); say('shot ' + n); };
const browser = await launch();
try {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fa-IR' }); const page = await ctx.newPage();
  const errors = []; page.on('pageerror', (e) => errors.push(String(e)));
  await staffLogin(page, 'qa-manager', managerPw);
  /* حضور و غیاب: نتیجهٔ اسکن ربات پس از بارگذاری مجدد پنل */
  await page.evaluate(() => { location.hash = '#users'; }); await page.waitForTimeout(400);
  await page.waitForSelector('[data-open-attendance]', { timeout: 15000 }); await page.click('[data-open-attendance]');
  await page.waitForSelector('[data-att-form]', { timeout: 15000 });
  const formBtn = page.locator(`[data-att-form="${state.form_id}"]`); await formBtn.first().click();
  await page.waitForSelector('[data-att-people] .admlirow', { timeout: 15000 });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-att-people] .admlirow', { timeout: 20000 });
  const rowText = await page.evaluate((rid) => { const r = [...document.querySelectorAll('[data-att-people] .admlirow')].find((x) => x.querySelector(`[data-att-undo="${rid}"]`)) || document.querySelector('[data-att-people] .admlirow'); return r.innerText.replace(/\n/g, ' | '); }, state.response_id);
  say('attendance row after reload: ' + rowText);
  await shot(page, '18-manager-attendance-bot-checkin-after-reload-desktop-light');
  /* کارتابل: تاریخچهٔ تصمیم‌ها با وضعیت تحویل اعلان */
  await page.evaluate(() => { location.hash = '#inbox'; }); await page.waitForTimeout(500);
  await page.waitForSelector('[data-workflow-status="decided"]', { timeout: 15000 }); await page.click('[data-workflow-status="decided"]');
  await page.waitForSelector(`[data-workflow-card="${state.task_id}"] [data-workflow-notification]`, { timeout: 15000 });
  const n = await page.evaluate((id) => { const c = document.querySelector(`[data-workflow-card="${id}"]`); return { state: c.querySelector('[data-workflow-notification]').getAttribute('data-workflow-notification'), text: c.innerText.replace(/\n/g, ' | ') }; }, state.task_id);
  say('decided task card: ' + JSON.stringify(n));
  await page.evaluate((id) => document.querySelector(`[data-workflow-card="${id}"]`).scrollIntoView({ block: 'center' }), state.task_id);
  await shot(page, '19-manager-inbox-decided-notification-delivered-desktop-light');
  say('page errors: ' + JSON.stringify(errors));
  await ctx.close();
} finally { await browser.close(); fs.appendFileSync(path.join(OUT, 'browser-log.txt'), log.join('\n') + '\n'); }
