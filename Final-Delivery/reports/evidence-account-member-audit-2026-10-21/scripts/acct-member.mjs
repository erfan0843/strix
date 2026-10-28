// Post-login account audit on the local TEST server (worktree build). Real browser (chromium), real backend.
// REAL: captcha, /api/auth/phone-otp/verify, session cookies, account/profile/registrations/payments/notifications APIs,
//       public form registration + receipt upload (card_transfer), logout, re-login, DB session expiry.
// BYPASSED: only the OTP delivery step (Bale/Safir absent) — challenge inserted by mk_challenge.py, /request answered locally.
// MOCKED (labelled): API failure injection via route() for the "خطای API" scenario only.
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000'; const OUT = process.env.OUT || '/tmp/qa/acct/member'; fs.mkdirSync(OUT, { recursive: true });
const PY = '/home/user/venvs/nora/bin/python';
const envText = fs.readFileSync('/tmp/nora-preview/env.sh', 'utf8');
const env = { ...process.env };
for (const m of envText.matchAll(/^export ([A-Z_]+)=(.*)$/gm)) env[m[1]] = m[2].replace(/^'(.*)'$/, '$1');
delete env.NORA_PUBLIC_BASE_URL;
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const ok = (c, m, extra = '') => { if (c) { pass++; console.log('PASS', m, extra); } else { fail++; console.log('FAIL', m, extra); } };
const note = m => console.log('NOTE', m);
const py = (code) => JSON.parse(execFileSync(PY, ['-c', `import os,sys,json; sys.path.insert(0,'/home/user/strix/Final-Delivery/website/nora-ui')\nfrom sqlalchemy import create_engine, select, func, update\nfrom sqlalchemy.orm import Session\nfrom backend.models import *\nfrom backend.otp import phone_digest\nfrom datetime import datetime, timezone, timedelta\ne=create_engine(os.environ['NORA_DATABASE_URL'])\n${code}`], { env }).toString());
const mkChallenge = (phone, code) => JSON.parse(execFileSync(PY, ['/tmp/nora-preview/mk_challenge.py', phone, code], { env }).toString());
const mkSession = (phone) => JSON.parse(execFileSync(PY, ['/tmp/nora-preview/mk_phone_session.py', phone], { env }).toString());
const accountIdFor = (phone) => py(`
with Session(e) as db:
    pid=phone_digest(os.environ['NORA_OTP_PEPPER'], ${JSON.stringify(phone)})
    row=db.scalar(select(PlatformIdentityRecord).where(PlatformIdentityRecord.provider=='phone', PlatformIdentityRecord.provider_user_id==pid))
    print(json.dumps({'account_id': row.account_id if row else None}))`);
const sessionsFor = (accountId) => py(`
with Session(e) as db:
    rows=db.scalars(select(AccountSessionRecord).where(AccountSessionRecord.account_id==${JSON.stringify(accountId)})).all()
    print(json.dumps({'total': len(rows), 'active': sum(1 for r in rows if r.revoked_at is None and r.expires_at.replace(tzinfo=timezone.utc)>datetime.now(timezone.utc)), 'revoked': sum(1 for r in rows if r.revoked_at is not None)}))`);
const expireSessions = (accountId) => py(`
with Session(e) as db:
    n=db.execute(update(AccountSessionRecord).where(AccountSessionRecord.account_id==${JSON.stringify(accountId)}).values(expires_at=datetime.now(timezone.utc)-timedelta(minutes=1))).rowcount
    db.commit(); print(json.dumps({'expired': n}))`);
const countsFor = (accountId) => py(`
with Session(e) as db:
    drafts=db.scalars(select(FormResponseDraftRecord.id).where(FormResponseDraftRecord.account_id==${JSON.stringify(accountId)})).all()
    resp=db.scalar(select(func.count(FormResponseRecord.id)).where(FormResponseRecord.draft_id.in_(drafts))) if drafts else 0
    print(json.dumps({'drafts': len(drafts), 'responses': resp, 'all_responses': db.scalar(select(func.count(FormResponseRecord.id))), 'all_accounts': db.scalar(select(func.count(AccountRecord.id)))}))`);

// ── owner seeding through the real owner API (test server) ───────────────────────────────────────
const OWNER_PW = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
const jar = {};
const setCookies = res => { for (const c of (res.headers.getSetCookie ? res.headers.getSetCookie() : [])) { const [kv] = c.split(';'); const i = kv.indexOf('='); jar[kv.slice(0, i).trim()] = kv.slice(i + 1); } };
const ownerFetch = async (path, init = {}) => {
  const headers = { Origin: BASE, 'Content-Type': 'application/json', Cookie: Object.entries(jar).map(([k, v]) => k + '=' + v).join('; '), ...(init.headers || {}) };
  if (init.method && init.method !== 'GET') headers['X-CSRF-Token'] = jar.nora_csrf || '';
  const res = await fetch(BASE + path, { ...init, headers, body: init.body ? JSON.stringify(init.body) : undefined }); setCookies(res);
  return { status: res.status, json: await res.json().catch(() => null) };
};
const RUN = String(Date.now() % 1000000);
async function seedForms() {
  const login = await ownerFetch('/api/auth/login', { method: 'POST', body: { username: env.NORA_OWNER_USERNAME || 'preview-owner', password: OWNER_PW } });
  if (login.status !== 200) throw new Error('owner login failed ' + login.status + ' ' + JSON.stringify(login.json));
  const base = (name, slug, extra = {}) => ({ name, model: 'registration', need: 'reg', slug, ev: 'event-audit-' + RUN,
    settings: { description: 'فرم آزمایشی ممیزی', confirmation: 'ثبت شد', ...extra },
    fields: [{ id: 'full-name', t: 'text', l: 'نام کامل', required: true }] });
  const make = async (payload, key) => {
    const created = await ownerFetch('/api/forms', { method: 'POST', body: payload, headers: { 'Idempotency-Key': key } });
    if (created.status !== 201) throw new Error('create form failed ' + created.status + ' ' + JSON.stringify(created.json));
    const id = created.json.id;
    const pub = await ownerFetch(`/api/forms/${id}/publish`, { method: 'POST', body: { expected_version: 1 } });
    if (pub.status !== 200) throw new Error('publish failed ' + pub.status + ' ' + JSON.stringify(pub.json));
    return id;
  };
  const free = await make(base('کارگاه رایگان ممیزی ' + RUN, 'audit/free-' + RUN), 'audit-free-' + RUN);
  const paid = await make(base('کارگاه پولی ممیزی ' + RUN, 'audit/paid-' + RUN, {
    enabledPaymentMethods: ['card_transfer'], receiptReviewRequired: true,
    fin: [{ l: 'ورودی', p: 250000, off: 0, req: true, d: '' }],
    paymentInstructions: 'مبلغ را کارت‌به‌کارت کن.', cap: 20,
    paymentCard: { number: '4111 1111 1111 1111', bank: 'بانک نمونه', holder: 'حساب آزمایشی' },
  }), 'audit-paid-' + RUN);
  return { free, paid };
}

async function session(vp = { width: 390, height: 844 }, theme = 'light', cookies = null) {
  let b; for (let i = 0; ; i++) { try { b = await launchBrowser(); break; } catch (e) { if (i >= 2) throw e; await sleep(1500); } }
  const ctx = await b.newContext({ viewport: vp, serviceWorkers: 'block', locale: 'fa-IR' });
  if (cookies) await ctx.addCookies(cookies);
  await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, theme);
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
  return { b, ctx, p, errs };
}
async function loginWith(p, phone, code, challenge) {
  await p.route('**/api/auth/phone-otp/request', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ accepted: true, challenge_id: challenge.challenge_id, expires_in: 180, resend_in: 90 }) }));
  await p.fill('#lgPhone', phone); await p.fill('#lgCapAnswer', '1234'); await p.click('#lgPhoneSubmit');
  await p.waitForSelector('#lgOtpCode', { timeout: 8000 });
  await p.focus('#lgOtpCode'); await p.keyboard.type(code);
  await p.click('#lgOtpVerify');
}
const pageState = p => p.evaluate(() => ({
  url: location.pathname + location.hash, src: window.NORA_ACCOUNT_SOURCE || '',
  member: !!document.querySelector('.server-account-head'), promo: !!document.querySelector('.account-promo'),
  tab: (document.querySelector('.tabbar [data-account-nav-label]') || {}).textContent || '',
  title: document.title, txt: document.body.innerText.replace(/\s+/g, ' '),
  viewTxt: (document.querySelector('#viewBox') || { innerText: '' }).innerText.replace(/\s+/g, ' '),
  headTxt: (document.querySelector('.server-account-head') || { innerText: '' }).innerText.replace(/\s+/g, ' '),
  toast: (document.querySelector('.toast, #toast, [role="status"]') || { textContent: '' }).textContent.replace(/\s+/g, ' '),
  ox: document.documentElement.scrollWidth > innerWidth,
}));
const apiInPage = (p, path, init = {}) => p.evaluate(async ({ path, init }) => {
  const csrf = (document.cookie.match(/(?:^|; )nora_account_csrf=([^;]+)/) || [])[1] || '';
  const headers = { ...(init.headers || {}) };
  if (init.method && init.method !== 'GET' && !headers['X-CSRF-Token']) headers['X-CSRF-Token'] = csrf;
  if (init.json) { headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(init.json); }
  const res = await fetch(path, { ...init, headers, credentials: 'same-origin' });
  let data = null; try { data = await res.json(); } catch (e) {}
  return { status: res.status, data };
}, { path, init });

const SUFFIX = String(Date.now() % 100000).padStart(5, '0');
const PHONE_A = '0912' + '3' + SUFFIX + '1', PHONE_B = '0912' + '4' + SUFFIX + '1', CODE = '517204';
console.log('  run', RUN, 'phones', PHONE_A, PHONE_B);
const FORMS = await seedForms(); console.log('  seeded forms', JSON.stringify(FORMS));
const dbBefore = py(`
with Session(e) as db: print(json.dumps({'accounts': db.scalar(select(func.count(AccountRecord.id))), 'responses': db.scalar(select(func.count(FormResponseRecord.id))), 'forms': db.scalar(select(func.count(FormRecord.id)))}))`);
let ACCOUNT_A = null; let cookiesA = null;

// ── 1) successful login → account page (member) ─────────────────────────────────────────────────
{
  const { b, p, errs, ctx } = await session();
  const ch = mkChallenge(PHONE_A, CODE);
  await p.goto(BASE + '/login.html?mode=server&next=account.html', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await loginWith(p, PHONE_A, CODE, ch);
  await p.waitForSelector('#lgAuthenticated', { timeout: 8000 }); await sleep(400);
  await p.screenshot({ path: OUT + '/01-login-created.png' });
  await p.click('#lgContinue'); await p.waitForLoadState('domcontentloaded'); await sleep(2200);
  const s = await pageState(p);
  ok(s.url === '/account.html' && s.src === 'server' && s.member && !s.promo, '1 login: real OTP verify → account.html in server mode, member head, no guest block', JSON.stringify([s.url, s.src, s.member, s.promo]));
  ok(s.tab === 'حساب من', '1 login: tabbar label «حساب من»', s.tab);
  ok(/ورود با شمارهٔ موبایل وصل است/.test(s.headTxt) && /نام هنوز در پروفایل ثبت نشده/.test(s.headTxt), '1 login: head shows provider + honest «نام هنوز در پروفایل ثبت نشده» (incomplete account)', s.headTxt.slice(0, 160));
  const cookies = await ctx.cookies(BASE);
  ok(cookies.some(c => c.name === 'nora_account_session' && c.httpOnly) && cookies.some(c => c.name === 'nora_account_csrf'), '1 login: httpOnly session cookie + csrf cookie from server');
  ACCOUNT_A = accountIdFor(PHONE_A).account_id; ok(!!ACCOUNT_A, '1 login: account row exists in DB', ACCOUNT_A);
  cookiesA = cookies.filter(c => /^nora_account_/.test(c.name)).map(c => ({ name: c.name, value: c.value, domain: '127.0.0.1', path: '/' }));
  await p.screenshot({ path: OUT + '/02-member-home-390.png' });
  // 2) session persistence: full reload, second page, other site page
  await p.goto(BASE + '/account.html', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const r = await pageState(p);
  ok(r.member && !r.promo && r.src === 'server', '2 session: full reload keeps member state (cookie session, no localStorage login)', JSON.stringify([r.member, r.promo]));
  await p.goto(BASE + '/home.html', { waitUntil: 'domcontentloaded' }); await sleep(1800);
  const home = await p.evaluate(() => ({ tab: (document.querySelector('.tabbar [data-account-nav-label]') || {}).textContent || '', href: (document.querySelector('.tabbar a[href*="account.html"]') || {}).getAttribute?.('href') }));
  ok(home.tab === 'حساب من', '2 session: home tabbar shows «حساب من» for the signed-in member', JSON.stringify(home));
  const p2 = await ctx.newPage(); await p2.goto(BASE + '/account.html#profile', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const prof = await pageState(p2);
  ok(prof.url === '/account.html#profile' && /اطلاعات من/.test(prof.viewTxt) && /هنوز در پروفایل حساب ثبت نشده/.test(prof.viewTxt) && /ورود با شمارهٔ موبایل/.test(prof.viewTxt), '3 profile: deep link in a new tab opens profile view with server facts (name missing, provider)', prof.viewTxt.slice(0, 200));
  ok(/شمارهٔ موبایل/.test(prof.viewTxt) && !/0912|۰۹۱۲/.test(prof.viewTxt), '3 profile: phone number itself is never rendered', '');
  const ident = await p2.evaluate(() => (document.querySelector('.server-account-identities, [data-identity-link], .identity-rows') || document.querySelector('#viewBox')).innerText.replace(/\s+/g, ' '));
  ok(/بله/.test(ident) && !/وصل شد/.test(ident), '3 profile: identity card mentions Bale linking honestly (no fake «وصل شد»)', ident.slice(0, 200));
  await p2.screenshot({ path: OUT + '/03-profile-incomplete-390.png' });
  // profile completion through the real API (PUT with CSRF) → head shows the name
  const put = await apiInPage(p2, '/api/account/profile', { method: 'PUT', json: { fullName: 'کاربر آزمایشی ممیزی', city: 'تهران' } });
  ok(put.status === 200 && put.data && put.data.saved === true && put.data.fields.fullName === 'کاربر آزمایشی ممیزی', '3 profile: PUT /api/account/profile with CSRF → saved (real endpoint)', JSON.stringify(put).slice(0, 160));
  const putNoCsrf = await apiInPage(p2, '/api/account/profile', { method: 'PUT', json: { fullName: 'x' }, headers: { 'X-CSRF-Token': 'wrong' } });
  ok(putNoCsrf.status === 403, '3 profile: PUT with wrong CSRF token → 403 (no write)', String(putNoCsrf.status));
  await p2.goto(BASE + '/account.html', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  const named = await pageState(p2);
  ok(/کاربر آزمایشی ممیزی/.test(named.headTxt) && /نام از پروفایل حساب/.test(named.headTxt), '3 profile: after save the head shows the real name from the server profile', named.headTxt.slice(0, 120));
  await p2.screenshot({ path: OUT + '/04-member-named-390.png' });
  ok(errs.length === 0, '1-3: no page errors', errs.join('|'));
  await b.close();
}

// ── 4) registrations / forms / payments with REAL records created through the public form API as this member ──
{
  const { b, p, errs } = await session({ width: 390, height: 844 }, 'light', cookiesA);
  await p.goto(BASE + '/account.html#events', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  const empty = await pageState(p);
  ok(/ثبت‌نامی به حسابت وصل نیست/.test(empty.viewTxt) && /۰ ثبت‌نام/.test(empty.viewTxt), '4 registrations: empty state is honest (۰ ثبت‌نام, no sample rows)', empty.viewTxt.slice(0, 160));
  await p.screenshot({ path: OUT + '/05-events-empty-390.png' });
  // free registration (real API, same session)
  const d1 = await apiInPage(p, `/api/public/forms/${FORMS.free}/draft`);
  const r1 = await apiInPage(p, `/api/public/forms/${FORMS.free}/responses`, { method: 'POST', json: { answers: { 'full-name': 'نام ثبت‌نامی محرمانه' } } });
  ok(d1.status === 200 && r1.status === 200 && r1.data && r1.data.status === 'accepted', '4 registrations: free form registration accepted via public API with the member session', JSON.stringify([d1.status, r1.status, r1.data && r1.data.status]));
  // paid registration (card_transfer) → awaiting_receipt
  const d2 = await apiInPage(p, `/api/public/forms/${FORMS.paid}/draft`);
  const r2 = await apiInPage(p, `/api/public/forms/${FORMS.paid}/responses`, { method: 'POST', json: { answers: { 'full-name': 'نام ثبت‌نامی محرمانه' }, payment: { method: 'card_transfer', selection: { items: [0], coupon_code: '' } } } });
  ok(d2.status === 200 && r2.status === 200 && r2.data && r2.data.payment_status === 'awaiting_receipt', '4 payments: paid form (card_transfer) registration → awaiting_receipt', JSON.stringify([d2.status, r2.status, r2.data && r2.data.payment_status]));
  await p.click('[data-account-registrations-refresh]'); await sleep(1500);
  const list = await pageState(p);
  ok(/۲ ثبت‌نام در این حساب/.test(list.viewTxt) && /کارگاه رایگان ممیزی/.test(list.viewTxt) && /کارگاه پولی ممیزی/.test(list.viewTxt) && /ثبت شد/.test(list.viewTxt), '4 registrations: «رویدادهای من» lists both real registrations after refresh (۲ ثبت‌نام)', list.viewTxt.slice(0, 220));
  ok(/در انتظار رسید/.test(list.viewTxt), '4 registrations: payment status chip «در انتظار رسید» on the paid one', '');
  ok(!/نام ثبت‌نامی محرمانه/.test(list.viewTxt), '4 registrations: answers (registrant name) are not exposed in the list (API returns no answers)', '');
  await p.screenshot({ path: OUT + '/06-events-two-390.png' });
  await p.goto(BASE + '/account.html#forms', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  const forms = await pageState(p);
  ok(/فرم‌های من/.test(forms.viewTxt) && /۲ پاسخ فرم در این حساب/.test(forms.viewTxt), '4 forms: «فرم‌های من» shows ۲ پاسخ فرم', forms.viewTxt.slice(0, 120));
  await p.screenshot({ path: OUT + '/07-forms-390.png' });
  await p.goto(BASE + '/account.html#payments', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  const pay = await pageState(p);
  ok(/پرداخت‌ها و رسیدها/.test(pay.viewTxt) && /۱ ثبت‌نام دارای وضعیت پرداخت از ۲/.test(pay.viewTxt) && /کارگاه پولی ممیزی/.test(pay.viewTxt) && !/کارگاه رایگان ممیزی/.test(pay.viewTxt), '4 payments: «پرداخت‌ها» lists only the paid registration (۱ از ۲) with status', pay.viewTxt.slice(0, 200));
  await p.screenshot({ path: OUT + '/08-payments-awaiting-390.png' });
  // receipt upload through the real endpoint → receipt_submitted
  const up = await p.evaluate(async fid => {
    const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l1sAAAAASUVORK5CYII='), c => c.charCodeAt(0));
    const res = await fetch(`/api/public/forms/${fid}/receipt`, { method: 'POST', body: png, headers: { 'Content-Type': 'image/png', 'X-File-Name': 'receipt.png' }, credentials: 'same-origin' });
    return { status: res.status, data: await res.json().catch(() => null) };
  }, FORMS.paid);
  ok(up.status === 200 && up.data && up.data.uploaded === true, '4 payments: receipt upload accepted (real endpoint, uploaded:true)', JSON.stringify(up).slice(0, 160));
  await p.click('[data-account-registrations-refresh]'); await sleep(1500);
  const pay2 = await pageState(p);
  ok(/رسید ثبت شد/.test(pay2.viewTxt), '4 payments: after refresh the account shows «رسید ثبت شد» (server state, no local guess)', pay2.viewTxt.slice(0, 160));
  await p.screenshot({ path: OUT + '/09-payments-receipt-390.png' });
  // home head counters
  await p.goto(BASE + '/account.html', { waitUntil: 'domcontentloaded' }); await sleep(2400);
  const head = await pageState(p);
  ok(/۲\s*ثبت‌نام/.test(head.headTxt), '4 head: registration counter in member head = ۲ (from server)', head.headTxt.slice(0, 160));
  // notifications & files views (empty, honest)
  await p.goto(BASE + '/account.html#notifications', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const nt = await pageState(p);
  ok(/اعلان/.test(nt.viewTxt) && !/نمونه/.test(nt.viewTxt), '4 notifications: view renders from server (empty, no sample)', nt.viewTxt.slice(0, 140));
  await p.goto(BASE + '/account.html#my-files', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const fl = await pageState(p);
  ok(/فایل/.test(fl.viewTxt) && !/نمونه/.test(fl.viewTxt), '4 files: view renders from server (empty, no sample)', fl.viewTxt.slice(0, 140));
  // certificates: web v1 has no endpoint → status screen, no data
  await p.goto(BASE + '/account.html#acc-6', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const cert = await pageState(p);
  ok(/جزئیات گواهی/.test(cert.viewTxt) && /فعلاً در ربات بله/.test(cert.viewTxt) && !/گواهی شمارهٔ|صادر شد|دانلود گواهی/.test(cert.viewTxt), '4 certificates: «جزئیات گواهی» = honest status «فعلاً در ربات بله», no fake certificate data', cert.viewTxt.slice(0, 160));
  await p.screenshot({ path: OUT + '/10-certificates-status-390.png' });
  // book club view
  await p.goto(BASE + '/account.html#book', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const bk = await pageState(p);
  ok(/باشگاه/.test(bk.viewTxt) && !/امتیاز شما|۱۲۰ امتیاز/.test(bk.viewTxt), '4 book club: server view without sample points', bk.viewTxt.slice(0, 120));
  ok(!(await pageState(p)).ox, '4: no horizontal overflow on 390', '');
  ok(errs.length === 0, '4: no page errors', errs.join('|'));
  await b.close();
}

// ── 5) unauthorized access: another member (B) and a guest never see A's records ─────────────────
{
  const sb = mkSession(PHONE_B);
  const cookiesB = [{ name: 'nora_account_session', value: sb.session, domain: '127.0.0.1', path: '/' }, { name: 'nora_account_csrf', value: sb.csrf, domain: '127.0.0.1', path: '/' }];
  const { b, p, errs } = await session({ width: 390, height: 844 }, 'light', cookiesB);
  await p.goto(BASE + '/account.html#events', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  const s = await pageState(p);
  ok(s.member && /۰ ثبت‌نام/.test(s.viewTxt) && !/ممیزی/.test(s.viewTxt), '5 isolation: member B sees ۰ registrations, none of A\'s', s.viewTxt.slice(0, 120));
  const q = await apiInPage(p, '/api/account/registrations?account_id=' + encodeURIComponent(ACCOUNT_A));
  ok(q.status === 200 && q.data.total === 0 && q.data.items.length === 0, '5 isolation: ?account_id=<A> is ignored server-side (identity from session only)', JSON.stringify(q.data).slice(0, 100));
  const f = await apiInPage(p, '/api/account/files/' + encodeURIComponent('00000000-0000-4000-8000-000000000000'));
  ok(f.status === 404, '5 isolation: foreign/unknown file id → 404', String(f.status));
  // B tries A's form draft (A's draft cookie is httpOnly-scoped per form; B just gets its own fresh draft)
  const dB = await apiInPage(p, `/api/public/forms/${FORMS.paid}/draft`);
  ok(dB.status === 200 && dB.data && !dB.data.submitted && JSON.stringify(dB.data).indexOf('محرمانه') < 0, '5 isolation: B opening the same form gets an empty draft, not A\'s answers', JSON.stringify(dB.data).slice(0, 120));
  await p.screenshot({ path: OUT + '/11-member-b-isolated-390.png' });
  ok(errs.length === 0, '5: no page errors', errs.join('|'));
  await b.close();
  // guest API access
  const g = await fetch(BASE + '/api/account/registrations'); const g2 = await fetch(BASE + '/api/account/me'); const g3 = await fetch(BASE + '/api/account/profile');
  ok(g.status === 401 && g2.status === 401 && g3.status === 401, '5 guest: /registrations /me /profile without cookie → 401', [g.status, g2.status, g3.status].join(','));
  const lo = await fetch(BASE + '/api/auth/account/logout', { method: 'POST', headers: { Origin: BASE, Cookie: cookiesA.map(c => c.name + '=' + c.value).join('; ') } });
  ok(lo.status === 403, '5 csrf: logout with session cookie but no CSRF header → 403 (session stays)', String(lo.status));
}

// ── 6) API error injection (mock, labelled) → honest error + retry restores real data ─────────────
{
  const { b, p, errs } = await session({ width: 390, height: 844 }, 'light', cookiesA);
  let broken = true;
  await p.route('**/api/account/registrations**', r => broken ? r.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"boom"}' }) : r.continue());
  await p.goto(BASE + '/account.html#events', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  const e1 = await pageState(p);
  ok(e1.member && /ثبت‌نام‌ها خوانده نشدند/.test(e1.viewTxt) && /تلاش دوباره/.test(e1.viewTxt) && !/۲ ثبت‌نام/.test(e1.viewTxt), '6 api-error [mock 500]: registrations view shows error + «تلاش دوباره», no stale/sample data', e1.viewTxt.slice(0, 160));
  await p.screenshot({ path: OUT + '/12-api-error-390.png' });
  broken = false; await p.click('[data-account-registrations-refresh]'); await sleep(1600);
  const e2 = await pageState(p);
  ok(/۲ ثبت‌نام در این حساب/.test(e2.viewTxt), '6 api-error: retry after recovery loads the real list again', e2.viewTxt.slice(0, 100));
  // /me unreachable at boot → page must not pretend; shows retry; recovery → member
  let down = true;
  await p.route('**/api/account/me', r => down ? r.abort('connectionfailed') : r.continue());
  await p.goto(BASE + '/account.html', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  const e3 = await pageState(p);
  ok(!e3.member && !!(await p.$('[data-server-account-retry]')), '6 api-error [mock offline /me]: no member data shown, retry button offered', e3.txt.slice(0, 120));
  note('observation: with /api/account/me unreachable the page falls back to the guest block (with «بررسی دوباره»); a signed-in user sees the login CTA until retry succeeds.');
  down = false; await p.click('[data-server-account-retry]'); await sleep(2200);
  const e4 = await pageState(p);
  ok(e4.member && /کاربر آزمایشی ممیزی/.test(e4.headTxt), '6 api-error: «بررسی دوباره» after recovery restores the member page without reload', e4.headTxt.slice(0, 80));
  ok(errs.length === 0, '6: no page errors', errs.join('|'));
  await b.close();
}

// ── 7) session expiry (DB-side, real 401) → page drops to guest, tabbar reverts ─────────────────
{
  const { b, p, errs } = await session({ width: 390, height: 844 }, 'light', cookiesA);
  await p.goto(BASE + '/account.html#events', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  ok((await pageState(p)).member, '7 expiry: member page open before expiry');
  const ex = expireSessions(ACCOUNT_A); note('expired sessions in test DB: ' + JSON.stringify(ex));
  await p.click('[data-account-registrations-refresh]'); await sleep(1800);
  const s = await pageState(p);
  ok(!s.member && s.promo && s.src === '' && /ورود حساب پایان یافته|نیاز به ورود/.test(s.txt), '7 expiry: real 401 on refresh → member state cleared, guest/«نیاز به ورود» shown', s.txt.slice(0, 160));
  ok(s.tab === 'ورود/ثبت‌نام', '7 expiry: tabbar label reverts to «ورود/ثبت‌نام»', s.tab);
  ok(!/کاربر آزمایشی ممیزی|کارگاه پولی ممیزی/.test(s.txt), '7 expiry: no account data remains on screen', '');
  await p.screenshot({ path: OUT + '/13-session-expired-390.png' });
  await p.goto(BASE + '/account.html', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const s2 = await pageState(p);
  ok(!s2.member && s2.promo, '7 expiry: reload with expired cookie → guest page (server rejects, nothing cached)', '');
  // re-login same phone from the expired state → same account, data intact
  const ch = mkChallenge(PHONE_A, CODE);
  await p.goto(BASE + '/login.html?mode=server&next=account.html%23events', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await loginWith(p, PHONE_A, CODE, ch);
  await p.waitForURL(/account\.html/, { timeout: 8000 }); await sleep(2400);
  const s3 = await pageState(p);
  ok(s3.url === '/account.html#events' && s3.member && /۲ ثبت‌نام در این حساب/.test(s3.viewTxt), '7 re-login after expiry: back to #events with the same account and both registrations', JSON.stringify([s3.url, s3.member]));
  ok(accountIdFor(PHONE_A).account_id === ACCOUNT_A, '7 re-login: same account id (no duplicate account)', '');
  const cookies = await p.context().cookies(BASE);
  cookiesA = cookies.filter(c => /^nora_account_/.test(c.name)).map(c => ({ name: c.name, value: c.value, domain: '127.0.0.1', path: '/' }));
  ok(errs.length === 0, '7: no page errors', errs.join('|'));
  await b.close();
}

// ── 8) logout → cookies cleared, DB session revoked, guest page; re-login works again ──────────────
{
  const { b, p, errs, ctx } = await session({ width: 390, height: 844 }, 'light', cookiesA);
  await p.goto(BASE + '/account.html', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  const before = sessionsFor(ACCOUNT_A);
  await p.click('.server-account-head [data-server-account-logout]'); await sleep(1800);
  const s = await pageState(p);
  ok(!s.member && s.promo && s.src === '' && s.tab === 'ورود/ثبت‌نام', '8 logout: one click → guest page, tabbar «ورود/ثبت‌نام» (no confirm sheet, no localStorage demo path)', JSON.stringify([s.member, s.promo, s.tab]));
  const after = sessionsFor(ACCOUNT_A);
  ok(after.revoked === before.revoked + 1, '8 logout: server revoked the session (revoked_at set in DB)', JSON.stringify({ before, after }));
  const cookies = await ctx.cookies(BASE);
  ok(!cookies.some(c => c.name === 'nora_account_session'), '8 logout: session cookie deleted by server response', cookies.map(c => c.name).join(','));
  await p.screenshot({ path: OUT + '/14-after-logout-390.png' });
  await p.goto(BASE + '/account.html#payments', { waitUntil: 'domcontentloaded' }); await sleep(2000);
  const s2 = await pageState(p);
  ok(!s2.member && /نیاز به ورود/.test(s2.viewTxt) && /برای دیدن وضعیت پرداخت‌هایت وارد حساب شو/.test(s2.viewTxt), '8 logout: private deep link afterwards → «نیاز به ورود» (no data)', s2.viewTxt.slice(0, 120));
  // replaying the old revoked cookie must fail
  const replay = await fetch(BASE + '/api/account/me', { headers: { Cookie: cookiesA.map(c => c.name + '=' + c.value).join('; ') } });
  ok(replay.status === 401, '8 logout: replaying the revoked session cookie → 401', String(replay.status));
  // re-login from the «نیاز به ورود» card: returns to #payments
  const href = await p.getAttribute('#viewBox .btn.primary', 'href');
  ok(href === 'login.html?mode=server&next=account.html%23payments', '8 re-login: card CTA keeps the return target (#payments)', href);
  const ch = mkChallenge(PHONE_A, CODE);
  await p.click('#viewBox .btn.primary'); await p.waitForLoadState('domcontentloaded'); await sleep(1200);
  await loginWith(p, PHONE_A, CODE, ch);
  await p.waitForURL(/account\.html/, { timeout: 8000 }); await sleep(2400);
  const s3 = await pageState(p);
  ok(s3.url === '/account.html#payments' && s3.member && /رسید ثبت شد/.test(s3.viewTxt) && /کاربر آزمایشی ممیزی/.test(s3.txt), '8 re-login: lands on #payments with the same account, payment state and profile name intact', JSON.stringify([s3.url, s3.member]));
  await p.screenshot({ path: OUT + '/15-relogin-payments-390.png' });
  const cookies2 = await ctx.cookies(BASE);
  cookiesA = cookies2.filter(c => /^nora_account_/.test(c.name)).map(c => ({ name: c.name, value: c.value, domain: '127.0.0.1', path: '/' }));
  ok(errs.length === 0, '8: no page errors', errs.join('|'));
  await b.close();
}

// ── 9) desktop + dark member shots (real data), overflow check ───────────────────────────────────
for (const [vp, theme, tag] of [[{ width: 1280, height: 800 }, 'light', 'desktop-light'], [{ width: 1280, height: 800 }, 'dark', 'desktop-dark'], [{ width: 390, height: 844 }, 'dark', 'mobile-dark']]) {
  const { b, p, errs } = await session(vp, theme, cookiesA);
  await p.goto(BASE + '/account.html', { waitUntil: 'domcontentloaded' }); await sleep(2400);
  const s = await pageState(p);
  ok(s.member && !s.ox, `9 ${tag}: member page renders, no horizontal overflow`, '');
  await p.screenshot({ path: `${OUT}/16-member-${tag}.png` });
  await p.goto(BASE + '/account.html#events', { waitUntil: 'domcontentloaded' }); await sleep(2200);
  await p.screenshot({ path: `${OUT}/17-events-${tag}.png` });
  ok(errs.length === 0, `9 ${tag}: no page errors`, errs.join('|'));
  await b.close();
}

// ── DB footprint: only this run's test rows were created ─────────────────────────────────────────
const dbAfter = py(`
with Session(e) as db: print(json.dumps({'accounts': db.scalar(select(func.count(AccountRecord.id))), 'responses': db.scalar(select(func.count(FormResponseRecord.id))), 'forms': db.scalar(select(func.count(FormRecord.id)))}))`);
const mine = countsFor(ACCOUNT_A);
ok(dbAfter.accounts === dbBefore.accounts + 2 && dbAfter.responses === dbBefore.responses + 2, 'DB footprint: exactly 2 test accounts (A,B) + 2 responses (A) added by this run; nothing else touched', JSON.stringify({ dbBefore, dbAfter, mine }));
console.log(`\n${pass} passed / ${fail} failed`);
process.exit(fail ? 1 : 0);
