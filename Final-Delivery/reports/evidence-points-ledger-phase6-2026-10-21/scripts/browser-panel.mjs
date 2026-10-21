import path from 'node:path'; import os from 'node:os'; import fs from 'node:fs'; import { createRequire } from 'node:module';
const dep = createRequire('/home/user/nora-node/package.json'); const { chromium: pw } = dep('playwright-core');
const B = 'http://127.0.0.1:8000', OUT = '/tmp/qa/p6/ui', log = []; const say = (m) => { log.push(m); console.log(m); };
async function launch() { const mod = dep('@sparticuz/chromium'); const chromium = mod.default || mod; const root = path.resolve(path.dirname(dep.resolve('@sparticuz/chromium')), '..'); const { inflate } = await import('file://' + path.join(root, 'build/lambdafs.js')); await inflate(path.join(root, 'bin/al2023.tar.br')); const executablePath = await chromium.executablePath(); const env = { ...process.env }; const lib = path.join(os.tmpdir(), 'al2023/lib'); if (fs.existsSync(lib)) env.LD_LIBRARY_PATH = [lib, env.LD_LIBRARY_PATH].filter(Boolean).join(path.delimiter); const fonts = path.join(os.tmpdir(), 'fonts'); if (fs.existsSync(fonts)) env.FONTCONFIG_PATH = fonts; return pw.launch({ executablePath, headless: true, args: chromium.args.filter((a) => !['--single-process', '--disable-web-security', '--allow-running-insecure-content'].includes(a)), env }); }
const ownerPw = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const managerPw = fs.readFileSync('/tmp/nora-preview/manager-pw.txt', 'utf8').trim();
async function staffLogin(page, u, p) { await page.goto(`${B}/login.html?mode=staff&next=admin.html%23dash`, { waitUntil: 'domcontentloaded' }); await page.waitForSelector('#lgStaffUsername', { timeout: 20000 }); await page.fill('#lgStaffUsername', u); await page.fill('#lgStaffPassword', p); await page.click('#lgStaffSubmit'); await Promise.race([page.waitForSelector('#lgContinue', { timeout: 15000 }).then(() => page.click('#lgContinue')).catch(() => {}), page.waitForURL(/admin\.html/, { timeout: 15000 }).catch(() => {})]); await page.waitForURL(/admin\.html/, { timeout: 15000 }); await page.waitForSelector('#admBar .server-identity', { timeout: 15000 }); }
const shot = async (page, n) => { await page.screenshot({ path: path.join(OUT, n + '.png'), animations: 'disabled', timeout: 60000 }); say('shot ' + n); };
const txt = (page, sel) => page.evaluate((s) => (document.querySelector(s) || {}).innerText?.replace(/\s+/g, ' ').slice(0, 400) || '', sel);
const browser = await launch();
try {
  for (const vp of [{ name: 'desktop', width: 1280, height: 800 }, { name: 'mobile', width: 390, height: 844 }]) {
    const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, locale: 'fa-IR' }); const page = await ctx.newPage();
    const errors = []; page.on('pageerror', (e) => errors.push(String(e)));
    const noLeak = async (label) => { const body = await page.evaluate(() => document.body.innerText); const bad = ['0912', 'Bearer', 'national_id', 'phone', 'کد ملی', 'توکن'].filter((w) => body.includes(w)); say(`${label} leak-check: ${bad.length ? 'FOUND ' + bad.join(',') : 'clean'}`); };
    await staffLogin(page, 'qa-owner', ownerPw);
    await page.evaluate(() => { location.hash = '#users'; }); await page.waitForTimeout(500);
    await page.waitForSelector('[data-open-club]', { timeout: 15000 });
    await page.evaluate(() => document.querySelector('[data-open-club]').scrollIntoView({ block: 'center' }));
    await shot(page, `01-owner-users-hub-club-card-${vp.name}`);
    await page.click('[data-open-club]');
    await page.waitForSelector('[data-club-member]', { timeout: 20000 });
    say('owner members: ' + await txt(page, '[data-club-panel]'));
    await shot(page, `02-owner-club-members-${vp.name}`); await noLeak('members');
    await page.click('[data-club-member]');
    await page.waitForSelector('[data-club-member-detail]', { timeout: 20000 });
    say('owner member detail: ' + await txt(page, '[data-club-member-detail]'));
    await shot(page, `03-owner-club-member-detail-${vp.name}`); await noLeak('detail');
    await page.click('[data-club-back]'); await page.waitForSelector('[data-club-member]', { timeout: 20000 });
    await page.click('[data-club-mode="entries"]'); await page.waitForSelector('[data-club-entry]', { timeout: 20000 });
    await shot(page, `04-owner-club-entries-${vp.name}`);
    await page.click('[data-club-type="reversal"]'); await page.waitForTimeout(800);
    say('entries reversal filter: ' + await txt(page, '[data-club-panel]'));
    await shot(page, `05-owner-club-entries-filter-reversal-${vp.name}`);
    if (vp.name === 'desktop') {
      await page.fill('[data-club-search-form] input', 'redeem:4'); await page.click('[data-club-search]'); await page.waitForTimeout(800);
      say('entries search redeem:4: ' + await txt(page, '[data-club-panel]'));
      await shot(page, `06-owner-club-entries-search-${vp.name}`);
      const writeButtons = await page.evaluate(() => [...document.querySelectorAll('[data-club-panel] button')].map((b) => b.innerText.trim()).filter(Boolean));
      say('club panel buttons (no write actions expected): ' + JSON.stringify(writeButtons));
    }
    say(`owner ${vp.name} page errors: ` + JSON.stringify(errors));
    await ctx.close();
  }
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fa-IR' }); const page = await ctx.newPage();
  await staffLogin(page, 'qa-manager', managerPw);
  await page.evaluate(() => { location.hash = '#users'; }); await page.waitForTimeout(800);
  const hasCard = await page.evaluate(() => !!document.querySelector('[data-open-club]'));
  say('manager sees club card: ' + hasCard);
  await shot(page, '07-manager-users-hub-no-club-card-desktop');
  const api = await page.evaluate(async () => { const r = await fetch('/api/admin/club/points/members', { credentials: 'include' }); return { status: r.status, body: (await r.text()).slice(0, 200) }; });
  say('manager direct API /api/admin/club/points/members: ' + JSON.stringify(api));
  await ctx.close();
} finally { await browser.close(); fs.writeFileSync(path.join(OUT, 'browser-log.txt'), log.join('\n') + '\n'); }
