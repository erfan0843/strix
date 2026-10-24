// Browser flow for stage 3 (U4 registrations + U5 per-account notifications in the user file), test DB only.
// Run: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<dir-with-node_modules> node stage3-user-file-check.cjs
const fs = require('fs'); const path = require('path');
const uiRoot = path.resolve(__dirname, '../../../website/nora-ui');
const { launchBrowser } = require(path.join(uiRoot, 'tools/browser-launch.cjs'));
const BASE = 'http://127.0.0.1:8000';
const creds = (() => { const t = fs.readFileSync(path.join(uiRoot, 'PREVIEW-LOGIN.local.md'), 'utf8');
  const o = t.match(/مالک:\s*`([^`]+)`\s*\/\s*`([^`]+)`/); const m = t.match(/مدیر:\s*`([^`]+)`\s*\/\s*`([^`]+)`/);
  return { owner: { user: o[1], pass: o[2] }, manager: { user: m[1], pass: m[2] } }; })();
const out = { steps: [] }; const note = (s) => { out.steps.push(s); console.log(s); };
const shot = (page, name) => page.screenshot({ path: path.join(__dirname, name), fullPage: false });
(async () => {
  const browser = await launchBrowser(); const page = await browser.newPage(); await page.setViewportSize({ width: 1280, height: 800 });
  page.on('pageerror', (e) => note('PAGEERROR ' + e.message));
  const login = async (c) => {
    await page.goto(`${BASE}/login.html?mode=staff&next=admin.html`, { waitUntil: 'domcontentloaded' });
    await page.fill('#lgStaffUsername', c.user); await page.fill('#lgStaffPassword', c.pass); await page.click('#lgStaffSubmit');
    await page.waitForTimeout(2000); const go = page.getByText('رفتن به پنل مدیریت').first(); if (await go.count()) await go.click();
    await page.waitForURL(/admin\.html/, { timeout: 15000 }); await page.waitForTimeout(1200);
  };
  const openUsers = async () => {
    await page.evaluate(() => { const s = JSON.parse(localStorage.getItem('nora-admin') || '{}'); s.sec = 'users'; s.uHub = 'users'; s.uV = ''; s.uSel = ''; localStorage.setItem('nora-admin', JSON.stringify(s)); });
    await page.goto(`${BASE}/admin.html?_=${Date.now()}`, { waitUntil: 'domcontentloaded' }); await page.waitForTimeout(1500);
    await page.waitForSelector('[data-users-panel]', { timeout: 15000 });
  };
  const apiCount = (re) => page.evaluate((src) => performance.getEntriesByType('resource').filter((r) => new RegExp(src).test(r.name)).length, re.source);
  const txt = async (sel) => page.$eval(sel, (el) => el.textContent.replace(/\s+/g, ' ').trim()).catch(() => '');

  await login(creds.owner);
  // pick the account with the most registrations (seeded qa-buyer has a paid registration with receipt)
  const list = await page.evaluate(async () => (await fetch('/api/admin/users?limit=50&offset=0', { credentials: 'include' }).then((r) => r.json())).items.map((i) => ({ id: i.account_id, n: i.display_name, regs: i.registrations, role: i.role })));
  // prefer an account whose registration carries a payment record (paid flow: payment + receipt + masked answers)
  const probed = await page.evaluate(async (ids) => { const outp = []; for (const id of ids) { const r = await fetch(`/api/admin/users/${id}/registrations?limit=5&offset=0`, { credentials: 'include' }).then((x) => x.json()); outp.push({ id, paid: (r.items || []).some((it) => it.payment_status), regs: (r.items || []).length }); } return outp; }, list.filter((i) => !i.role).map((i) => i.id));
  const pick = probed.find((p) => p.paid) || probed.sort((a, b) => b.regs - a.regs)[0];
  const target = list.find((i) => i.id === pick.id);
  const other = list.find((i) => i.id !== target.id && !i.role);
  note('0 accounts in test DB: ' + list.length + ' → target ' + target.id.slice(0, 8) + '… (' + target.regs + ' regs), other ' + (other ? other.id.slice(0, 8) : '-') + '…');
  await openUsers();
  await page.click(`[data-user-open="${target.id}"]`);
  await page.waitForSelector('[data-uf-reg], [data-uf-regs] .empty', { timeout: 15000 }); await page.waitForTimeout(500);
  const regRows = await page.$$eval('[data-uf-reg]', (els) => els.map((e) => e.textContent.replace(/\s+/g, ' ').trim().slice(0, 120)));
  note('1 owner file: regs endpoint calls=' + (await apiCount(/\/api\/admin\/users\/[^/]+\/registrations\?/)) + ' rows=' + JSON.stringify(regRows));
  await shot(page, 'stage3-01-file-regs-d.png');
  const firstReg = await page.$eval('[data-uf-reg]', (el) => el.getAttribute('data-uf-reg')).catch(() => '');
  if (firstReg) {
    await page.click(`[data-uf-reg="${firstReg}"]`);
    await page.waitForSelector('[data-uf-reg-detail][data-uf-finance]', { timeout: 15000 }); await page.waitForTimeout(400);
    const fin = await page.$eval('[data-uf-reg-detail]', (el) => el.getAttribute('data-uf-finance'));
    const masked = await page.$$eval('[data-uf-masked]', (els) => els.map((e) => e.getAttribute('data-uf-masked') + ':' + (e.querySelector('b') || {}).textContent));
    const dtxt = await txt('[data-uf-reg-detail]');
    const leak = dtxt.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, '').match(/09\d{9}|[۰-۹]{10}|\d{10}/);
    note('2 owner detail: finance_visible=' + fin + ' masked=' + JSON.stringify(masked) + ' hasAmount=' + /ریال/.test(dtxt) + ' hasReceipt=' + /فیش واریز/.test(dtxt) + ' hasAttendance=' + /وضعیت حضور/.test(dtxt) + ' companions=' + /همراهان/.test(dtxt) + ' fullNumberLeak=' + (leak ? leak[0] : 'none'));
    await shot(page, 'stage3-02-reg-detail-owner-d.png');
    await page.click('[data-uf-reg-back]'); await page.waitForSelector('[data-uf-reg]', { timeout: 10000 });
  }
  await page.click('[data-uf-tab="notifs"]');
  await page.waitForSelector('[data-uf-notif], [data-uf-notifs] .empty', { timeout: 15000 }); await page.waitForTimeout(400);
  const notifRows = await page.$$eval('[data-uf-notif]', (els) => els.map((e) => e.getAttribute('data-uf-delivery') + ' | ' + e.textContent.replace(/\s+/g, ' ').trim().slice(0, 110)));
  note('3 owner notifs: per-account calls=' + (await apiCount(/\/api\/admin\/users\/[^/]+\/notifications\?/)) + ' generalQueueCalls=' + (await apiCount(/\/api\/admin\/notifications\?(?!limit=1)/)) + ' rows=' + JSON.stringify(notifRows));
  await shot(page, 'stage3-03-notifs-owner-d.png');
  // manager (us_view, no finance)
  await page.context().clearCookies(); await login(creds.manager);
  await openUsers();
  await page.click(`[data-user-open="${target.id}"]`);
  await page.waitForSelector('[data-uf-reg], [data-uf-regs] .empty', { timeout: 15000 }); await page.waitForTimeout(400);
  if (firstReg) {
    await page.click(`[data-uf-reg="${firstReg}"]`);
    await page.waitForSelector('[data-uf-reg-detail][data-uf-finance]', { timeout: 15000 }); await page.waitForTimeout(400);
    const fin = await page.$eval('[data-uf-reg-detail]', (el) => el.getAttribute('data-uf-finance'));
    const dtxt = await txt('[data-uf-reg-detail]');
    note('4 manager detail: finance_visible=' + fin + ' amountShown=' + /ریال/.test(dtxt) + ' trxShown=' + /شناسهٔ تراکنش/.test(dtxt) + ' hiddenNote=' + !!(await page.$('[data-uf-finance-hidden]')) + ' masked=' + (await page.$$eval('[data-uf-masked]', (els) => els.length)) + ' payStatusShown=' + /وضعیت پرداخت/.test(dtxt));
    await shot(page, 'stage3-04-reg-detail-manager-d.png');
    // cross-account: same response id under ANOTHER account → 404, nothing rendered
    if (other) {
      const cross = await page.evaluate(async ({ acc, rid }) => { const r = await fetch(`/api/admin/users/${acc}/registrations/${rid}`, { credentials: 'include' }); return { status: r.status, body: (await r.text()).slice(0, 80) }; }, { acc: other.id, rid: firstReg });
      note('5 manager cross-account response id → ' + JSON.stringify(cross));
    }
    await page.click('[data-uf-reg-back]'); await page.waitForSelector('[data-uf-reg]', { timeout: 10000 });
    await page.evaluate((rid) => document.querySelector(`[data-uf-reg="${rid}"]`).setAttribute('data-uf-reg', '99999999-9999-4999-8999-999999999999'), firstReg);
    await page.click('[data-uf-reg="99999999-9999-4999-8999-999999999999"]');
    await page.waitForFunction(() => /پیدا نشد/.test((document.querySelector('[data-uf-reg-detail]') || {}).textContent || ''), null, { timeout: 10000 });
    note('5 manager fake response id in UI → «پیدا نشد», answers rendered=' + !!(await page.$('[data-uf-answers]')));
    await page.click('[data-uf-reg-back]');
  }
  await page.click('[data-uf-tab="notifs"]');
  await page.waitForSelector('[data-uf-notif], [data-uf-notifs] .empty', { timeout: 15000 });
  note('6 manager notifs rows=' + (await page.$$eval('[data-uf-notif]', (els) => els.length)) + ' ownerApiCalls=' + (await apiCount(/\/api\/owner\//)));
  await page.setViewportSize({ width: 390, height: 844 }); await page.waitForTimeout(400);
  note('6 mobile overflowX=' + (await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)));
  await shot(page, 'stage3-05-notifs-manager-m.png');
  fs.writeFileSync(path.join(__dirname, 'stage3-user-file-check.json'), JSON.stringify(out, null, 2));
  await browser.close();
})().catch((e) => { note('FATAL ' + e.message); fs.writeFileSync(path.join(__dirname, 'stage3-user-file-check.json'), JSON.stringify(out, null, 2)); process.exit(1); });
