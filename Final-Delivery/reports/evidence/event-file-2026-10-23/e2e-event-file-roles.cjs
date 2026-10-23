// پروندهٔ رویداد — بخش دوم پذیرش مرورگری: نقش مدیر (بدون finance) + دسترسی مستقیم بدون ورود.
// ورودی: ids.json از اجرای مالک (e2e-event-file.cjs). خروجی: shots-roles/*.png + log-roles.txt
const path = require('path'); const fs = require('fs');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const OWNER = 'http://127.0.0.1:8000', MANAGER = 'http://127.0.0.1:8080', BACKEND = 'http://127.0.0.1:8001';
const out = process.argv[2]; fs.mkdirSync(out, { recursive: true });
const ids = JSON.parse(fs.readFileSync(path.join(out, '..', 'shots', 'ids.json'), 'utf8'));
const sleep = ms => new Promise(r => setTimeout(r, ms));
// نشست مدیر مستقیم روی بک‌اند: نام کاربری/گذرواژهٔ آزمایشی از فایل gitignore‌شده خوانده می‌شود و هرگز چاپ نمی‌شود
async function managerSession() {
  const text = fs.readFileSync(path.join(process.env.NORA_REPO_UI, 'PREVIEW-LOGIN.local.md'), 'utf8');
  let creds = null;
  for (const line of text.split('\n')) { if (!line.includes('مدیر')) continue; const toks = [...line.matchAll(/`([^`]+)`/g)].map(m => m[1]); if (toks.length >= 2) { creds = { username: toks[0], password: toks[1] }; break; } }
  if (!creds) throw new Error('manager test credentials not found');
  const jar = new Map();
  const store = r => { for (const c of (r.headers.getSetCookie ? r.headers.getSetCookie() : [])) { const [kv] = c.split(';'); const i = kv.indexOf('='); jar.set(kv.slice(0, i).trim(), kv.slice(i + 1).trim()); } };
  const cookie = () => [...jar].map(([k, v]) => k + '=' + v).join('; ');
  const login = await fetch(BACKEND + '/api/auth/manager-login', { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: BACKEND }, body: JSON.stringify(creds) }); store(login); creds = null;
  const csrf = jar.get('nora_account_csrf') || '';
  return { loginStatus: login.status, csrf, fetch: (p, init) => fetch(BACKEND + p, Object.assign({}, init || {}, { headers: Object.assign({ Cookie: cookie(), Origin: BACKEND }, (init && init.headers) || {}) })) };
}
const lines = []; let pass = 0, fail = 0;
const L = (...a) => { const s = a.map(x => typeof x === 'string' ? x : JSON.stringify(x)).join(' '); lines.push(s); console.log(s); };
const check = (name, ok) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + name + (ok ? '' : ' ✗')); };

(async () => {
  const browser = await launchBrowser();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fa-IR' });
  const page = await ctx.newPage(); page.on('dialog', d => d.accept());
  const shot = (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const has = sel => page.evaluate(q => !!document.querySelector(q), sel);
  const txt = sel => page.evaluate(q => { const e = document.querySelector(q); return e ? e.textContent.trim() : null; }, sel);
  const count = sel => page.evaluate(q => document.querySelectorAll(q).length, sel);
  const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (e) {} await sleep(150); } return false; };
  const api = (base, p, init) => page.evaluate(async ([p, init]) => { const r = await fetch(p, Object.assign({ credentials: 'same-origin' }, init || {})); let b = null; try { b = await r.json(); } catch (e) {} return { status: r.status, body: b }; }, [p, init]);
  const tabs = () => page.evaluate(() => [...document.querySelectorAll('[data-ei-tab]')].map(b => b.dataset.eiTab));
  const A = ids.A, Bev = ids.B;
  try {
    // ---------- مدیر (پروکسی 8080، حساب مدیر آزمایشی، بدون finance) ----------
    await page.goto('about:blank'); await page.goto(MANAGER + '/admin.html#event=' + A + '&tab=overview', { waitUntil: 'load' }); await sleep(2000);
    const me = await api(MANAGER, '/api/account/me'); L('manager me', { role: me.body && me.body.role, finance: !!(me.body && (me.body.permissions || []).includes('finance')), receipt_approve: !!(me.body && (me.body.permissions || []).includes('receipt_approve')) });
    check('manager session is a manager without finance', me.body && me.body.role === 'manager' && !(me.body.permissions || []).includes('finance'));
    check('manager: event file opens by direct URL', await waitFor(() => has('[data-ef-head]')));
    const t = await tabs(); L('manager tabs', t);
    check('manager: no «پرداخت‌ها» tab (finance needed), but registrants/forms/tickets visible', !t.includes('payments') && t.includes('regs') && t.includes('forms') && t.includes('tickets'));
    const head = await txt('[data-ef-head]'); L('manager head', head);
    // قیمت فرم ثبت‌نام اطلاعات عمومی صفحهٔ رویداد است (نه دادهٔ مالی)؛ آنچه باید پنهان بماند مبالغ پرداخت افراد و جمع‌هاست
    check('manager: head shows capacity + public form price, no per-person money', /ثبت‌نام: ۲ از ۴/.test(head) && /تنظیم‌شده در فرم ثبت‌نام/.test(head) && !/جمع پرداخت/.test(head));
    await shot('R1-manager-overview', true);
    await page.evaluate(() => document.querySelector('[data-ei-tab="regs"]').click()); await waitFor(async () => (await count('[data-ef-reg]')) === 2);
    const row = await txt('[data-ef-reg="' + ids.p1 + '"]'); L('manager row p1', row);
    check('manager: registrant row keeps payment state but hides amount', /پرداخت‌شده/.test(row || '') && !/ریال/.test(row || ''));
    await page.evaluate(id => document.querySelector('[data-ef-person="' + id + '"]').click(), ids.p2); await waitFor(() => has('[data-ef-person-file="' + ids.p2 + '"]'));
    const pf = await txt('[data-ef-person-file="' + ids.p2 + '"]'); L('manager person p2', (pf || '').slice(0, 260));
    check('manager: person file shows «رسیدی ثبت نشده», no «تأیید پرداخت» without a receipt (only cancel), no amount', /رسیدی ثبت نشده/.test(pf || '') && !(await has('[data-ef-decide="approve"]')) && await has('[data-ef-decide="reject"]') && /لغو ثبت‌نام پرداخت‌نشده/.test(pf || '') && !/ریال/.test(pf || ''));
    const approveNoReceipt = await api(MANAGER, '/api/admin/events/' + A + '/registrations/' + ids.p2 + '/payment-decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision: 'approved', reason: 'بدون رسید' }) });
    L('approve without receipt', approveNoReceipt.status, approveNoReceipt.body && approveNoReceipt.body.detail); check('server refuses approving a payment that has no receipt (409 receipt_missing)', approveNoReceipt.status === 409 && approveNoReceipt.body && approveNoReceipt.body.detail && approveNoReceipt.body.detail.code === 'receipt_missing');
    await shot('R2-manager-person-no-receipt', true);
    // API مستقیم با نشست مدیر
    const pay = await api(MANAGER, '/api/admin/events/' + A + '/payments'); L('manager GET payments', pay.status);
    check('manager: direct payments API → 403', pay.status === 403);
    const regs = await api(MANAGER, '/api/admin/events/' + A + '/registrations');
    check('manager: registrations API answers without amounts (finance_visible=false)', regs.status === 200 && regs.body.finance_visible === false && !regs.body.items.some(r => 'amount' in r));
    const det = await api(MANAGER, '/api/admin/events/' + A + '/registrations/' + ids.p1);
    check('manager: person detail has no payment amount, keeps status', det.status === 200 && det.body.payment && det.body.payment.amount == null && det.body.payment.status === 'paid_manual');
    const cross = await api(MANAGER, '/api/admin/events/' + Bev + '/registrations/' + ids.p1); L('manager cross-event', cross.status);
    check('manager: A’s registration under event B → 404', cross.status === 404);
    const rc = await page.evaluate(async p => { const r = await fetch(p, { credentials: 'same-origin' }); return { status: r.status, type: r.headers.get('content-type') }; }, '/api/admin/events/' + A + '/registrations/' + ids.p1 + '/receipt');
    L('manager receipt file', rc); check('manager (receipt_approve): receipt file readable', rc.status === 200 && /^image\//.test(rc.type || ''));
    // CSRF را نمی‌شود از پشت پروکسی سنجید (پروکسی توکن را خودش می‌گذارد)؛ پس با نشست واقعی مدیر مستقیم به بک‌اند می‌رویم
    const mgr = await managerSession();
    const csrfNone = await mgr.fetch('/api/admin/events/' + A + '/registrations/' + ids.p1 + '/payment-decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision: 'approved', reason: 'بدون توکن' }) });
    const csrfWrong = await mgr.fetch('/api/admin/events/' + A + '/registrations/' + ids.p1 + '/payment-decision', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': 'wrong-token' }, body: JSON.stringify({ decision: 'approved', reason: 'توکن غلط' }) });
    const csrfForeignOrigin = await mgr.fetch('/api/admin/events/' + A + '/registrations/' + ids.p1 + '/payment-decision', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': mgr.csrf, Origin: 'http://evil.example' }, body: JSON.stringify({ decision: 'approved', reason: 'مبدأ غریبه' }) });
    const direct = await mgr.fetch('/api/admin/events/' + A + '/registrations?limit=5'); const directBody = await direct.json();
    const okRepeat = await mgr.fetch('/api/admin/events/' + A + '/registrations/' + ids.p1 + '/payment-decision', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': mgr.csrf }, body: JSON.stringify({ decision: 'approved', reason: 'تکرار از نشست مدیر' }) }); const okRepeatBody = await okRepeat.json();
    L('manager direct backend', { login: mgr.loginStatus, csrfNone: csrfNone.status, csrfWrong: csrfWrong.status, csrfForeignOrigin: csrfForeignOrigin.status, list: direct.status, repeat: okRepeat.status, repeatChanged: okRepeatBody.changed });
    check('manager direct: decision without CSRF token → 403', csrfNone.status === 403);
    check('manager direct: decision with wrong CSRF token → 403', csrfWrong.status === 403);
    check('manager direct: decision from a foreign Origin → 403', csrfForeignOrigin.status === 403);
    check('manager direct: list readable, amounts absent', direct.status === 200 && directBody.finance_visible === false && !directBody.items.some(r => 'amount' in r));
    check('manager direct: repeating an already-approved decision is a no-op (changed:false)', okRepeat.status === 200 && okRepeatBody.changed === false);
    const sm = await api(MANAGER, '/api/admin/events/' + A + '/forms/' + ids.survey + '/summary');
    check('manager (fm_responses): survey summary readable', sm.status === 200 && sm.body.responses === 3);
    // موبایل مدیر
    await page.setViewportSize({ width: 390, height: 844 }); await page.goto('about:blank'); await page.goto(MANAGER + '/admin.html#event=' + A + '&tab=tickets', { waitUntil: 'load' }); await sleep(2000);
    check('manager mobile: tickets tab opens, one checked-in row', await waitFor(() => has('[data-ef-tickets]')) && await waitFor(async () => /حاضر/.test(await txt('[data-ef-att-row="' + ids.p1 + '"]') || '')));
    await shot('R3-manager-tickets-mobile', true);
    await page.setViewportSize({ width: 1280, height: 800 });
    // ---------- بدون ورود: مستقیم به بک‌اند ----------
    const anon = async (p, init) => { const r = await fetch(BACKEND + p, Object.assign({ headers: { Origin: BACKEND } }, init || {})); return r.status; };
    const a1 = await anon('/api/admin/events/' + A + '/overview'), a2 = await anon('/api/admin/events/' + A + '/registrations/' + ids.p1 + '/receipt'), a3 = await anon('/api/admin/events/' + A + '/registrations/' + ids.p1 + '/ticket-image'), a4 = await anon('/api/admin/events/' + A + '/payments');
    const a5 = await anon('/api/admin/events/' + A + '/registrations/' + ids.p1 + '/payment-decision', { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: BACKEND }, body: JSON.stringify({ decision: 'approved', reason: 'x' }) });
    L('anonymous', { overview: a1, receipt: a2, ticket: a3, payments: a4, decision: a5 });
    check('unauthenticated: overview/receipt/ticket/payments/decision all 401', [a1, a2, a3, a4, a5].every(s => s === 401));
    // ---------- مالک: جزئیات سریال/QR بدون PII ----------
    await page.goto('about:blank'); await page.goto(OWNER + '/admin.html#event=' + A + '&tab=regs&reg=' + ids.p1, { waitUntil: 'load' }); await sleep(2000);
    const od = await api(OWNER, '/api/admin/events/' + A + '/registrations/' + ids.p1);
    const serial = od.body && od.body.ticket && od.body.ticket.serial; L('ticket serial', serial);
    check('ticket serial is opaque (no name/mobile inside)', !!serial && !/نفر|09\d{9}/.test(serial) && serial.length >= 12);
    check('owner person file: audit shows manual decision + attendance', !!(od.body.audit || []).find(a => a.action === 'payment.manual_decision') && od.body.attendance && od.body.attendance.checked_in === true);
    await shot('R4-owner-person-final', true);
  } catch (e) { L('E2E-roles crashed: ' + (e && e.stack || e)); fail++; }
  L('TOTAL PASS ' + pass + ' / FAIL ' + fail);
  fs.writeFileSync(path.join(out, 'log-roles.txt'), lines.join('\n') + '\n');
  await browser.close();
})();
