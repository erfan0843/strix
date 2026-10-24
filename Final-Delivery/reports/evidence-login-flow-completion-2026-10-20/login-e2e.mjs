// End-to-end member flows against the local test server.
// REAL: captcha, /api/auth/phone-otp/verify, account creation, session cookie, redirect, account page data.
// BYPASSED (no Bale/Safir in the sandbox): only the "send code" step — the challenge row is inserted into the
// test DB by mk_challenge.py exactly as the server would, and the browser's /request call is answered locally.
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000'; const OUT = '/tmp/qa/login/e2e'; fs.mkdirSync(OUT, { recursive: true });
const PY = '/home/user/venvs/nora/bin/python';
const envText = fs.readFileSync('/tmp/nora-preview/env.sh', 'utf8');
const env = { ...process.env };
for (const m of envText.matchAll(/^export ([A-Z_]+)=(.*)$/gm)) env[m[1]] = m[2].replace(/^'(.*)'$/, '$1');
delete env.NORA_PUBLIC_BASE_URL;
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0;
const ok = (c, m, extra = '') => { if (c) { pass++; console.log('PASS', m, extra); } else { fail++; console.log('FAIL', m, extra); } };
const mkChallenge = (phone, code) => JSON.parse(execFileSync(PY, ['/tmp/nora-preview/mk_challenge.py', phone, code], { env }).toString());
const dbCount = (phone) => JSON.parse(execFileSync(PY, ['-c', `
import os,sys,json; sys.path.insert(0,'/home/user/strix/Final-Delivery/website/nora-ui')
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session
from backend.models import AccountRecord, PlatformIdentityRecord, AccountSessionRecord
from backend.otp import phone_digest
e=create_engine(os.environ['NORA_DATABASE_URL'])
with Session(e) as db:
    pid=phone_digest(os.environ['NORA_OTP_PEPPER'], ${JSON.stringify(phone)})
    ids=db.scalar(select(func.count()).select_from(PlatformIdentityRecord).where(PlatformIdentityRecord.provider=='phone', PlatformIdentityRecord.provider_user_id==pid))
    print(json.dumps({'identities_for_phone': ids, 'accounts': db.scalar(select(func.count()).select_from(AccountRecord))}))
`], { env }).toString());

async function session(vp = { width: 390, height: 844 }) {
  const b = await launchBrowser();
  const ctx = await b.newContext({ viewport: vp, serviceWorkers: 'block', locale: 'fa-IR' });
  await ctx.addInitScript(() => { try { localStorage.setItem('nora-theme', 'light'); } catch (e) {} });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e.message).slice(0, 120)));
  return { b, ctx, p, errs };
}
async function loginWith(p, phone, code, challenge) {
  await p.route('**/api/auth/phone-otp/request', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ accepted: true, challenge_id: challenge.challenge_id, expires_in: 180, resend_in: 90 }) }));
  await p.fill('#lgPhone', phone); await p.fill('#lgCapAnswer', '1234'); await p.click('#lgPhoneSubmit');
  await p.waitForSelector('#lgOtpCode', { timeout: 8000 });
  await p.focus('#lgOtpCode'); await p.keyboard.type(code);
}

const SUFFIX = String(Date.now() % 100000).padStart(5, '0');
const PHONE_NEW = '0912' + '1' + SUFFIX + '0', PHONE_OLD = '0912' + '2' + SUFFIX + '0', CODE = '482913';
console.log('  test phones (unique per run):', PHONE_NEW, PHONE_OLD);

// ── 1) brand-new member: real verify → account created → confirmation card → account page with real session
{
  const { b, p, errs } = await session();
  const before = dbCount(PHONE_NEW);
  const ch = mkChallenge(PHONE_NEW, CODE);
  await p.goto(BASE + '/login.html?mode=server&next=account.html', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await loginWith(p, PHONE_NEW, CODE, ch);
  await p.screenshot({ path: OUT + '/new-1-code-typed.png' });
  await p.click('#lgOtpVerify'); await p.waitForSelector('#lgAuthenticated', { timeout: 8000 }); await sleep(400);
  const card = await p.evaluate(() => ({ h: document.querySelector('.lgdtitle').textContent, d: (document.querySelector('.lgdle') || {}).textContent || '', cont: document.querySelector('#lgContinue').getAttribute('href'), url: location.pathname + location.search, links: [...document.querySelectorAll('#lgAuthenticated a')].map(a => a.getAttribute('href')) }));
  ok(card.h === 'حسابت ساخته شد' && /ربات بله/.test(card.d), 'new member: REAL verify → confirmation card «حسابت ساخته شد»', JSON.stringify(card).slice(0, 160));
  ok(card.url.startsWith('/login.html'), 'new member: no auto-redirect before the user reads the card');
  ok(card.links.includes('https://ble.ir/nora_preview_bot'), 'new member: «تکمیل پروفایل در ربات بله» link comes from the server (delivery_bot_url) and stays active', JSON.stringify(card.links));
  ok(await p.evaluate(() => (document.querySelector('.tabbar [data-account-nav-label]') || {}).textContent === 'حساب من'), 'new member: tabbar label switches to «حساب من» after server session');
  const after = dbCount(PHONE_NEW);
  ok(before.identities_for_phone === 0 && after.identities_for_phone === 1 && after.accounts === before.accounts + 1, 'new member: exactly one account + identity created in DB', JSON.stringify({ before, after }));
  const cookies = await p.context().cookies(BASE);
  ok(cookies.some(c => c.name === 'nora_account_session' && c.httpOnly) && cookies.some(c => c.name === 'nora_account_csrf'), 'new member: real httpOnly session cookie set by server');
  await p.screenshot({ path: OUT + '/new-2-created-card.png' });
  await p.click('#lgContinue'); await p.waitForLoadState('domcontentloaded'); await sleep(2000);
  const acct = await p.evaluate(() => ({ url: location.pathname + location.hash, src: window.NORA_ACCOUNT_SOURCE, txt: document.body.innerText.slice(0, 2000) }));
  ok(acct.url === '/account.html' && acct.src === 'server', 'new member: lands on account page in server mode', acct.url + ' ' + acct.src);
  ok(/ورود با شمارهٔ موبایل وصل است|ورود و دسترسی از سرور تأیید شده/.test(acct.txt), 'new member: account page confirms server session');
  ok(/نام هنوز در پروفایل ثبت نشده/.test(acct.txt), 'new member: account page shows profile-not-yet-filled status (completion lives in Bale bot per v1 scope)');
  await p.screenshot({ path: OUT + '/new-3-account-page.png' });
  ok(errs.length === 0, 'new member: no page errors', errs.join('|'));
  await b.close();
}
// ── 2) returning member (same phone): real verify → same account, no duplicate, direct redirect to next
{
  const { b, p, errs } = await session();
  const before = dbCount(PHONE_NEW);
  const ch = mkChallenge(PHONE_NEW, CODE);
  await p.goto(BASE + '/login.html?mode=server&next=account.html%23notifications', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await loginWith(p, PHONE_NEW, CODE, ch);
  await p.click('#lgOtpVerify');
  await p.waitForURL(/account\.html/, { timeout: 8000 }); await sleep(1800);
  const after = dbCount(PHONE_NEW);
  ok(after.identities_for_phone === 1 && after.accounts === before.accounts, 'returning member: no second account created', JSON.stringify({ before, after }));
  const acct = await p.evaluate(() => ({ url: location.pathname + location.hash, src: window.NORA_ACCOUNT_SOURCE }));
  ok(acct.url === '/account.html#notifications' && acct.src === 'server', 'returning member: straight to requested destination with server session', JSON.stringify(acct));
  await p.screenshot({ path: OUT + '/returning-account.png' });
  ok(errs.length === 0, 'returning member: no page errors', errs.join('|'));
  await b.close();
}
// ── 3) wrong code then correct code (real attempts counter), expired/consumed challenge → honest error, code field kept usable
{
  const { b, p, errs } = await session();
  const ch = mkChallenge(PHONE_OLD, CODE);
  await p.goto(BASE + '/login.html?mode=server&next=account.html', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await loginWith(p, PHONE_OLD, '111111', ch);
  await p.click('#lgOtpVerify'); await sleep(1200);
  const wrong = await p.evaluate(() => ({ st: document.querySelector('#lgStatus').textContent, kind: document.querySelector('#lgStatus').dataset.kind, step: !!document.querySelector('#lgPhoneCodeForm'), val: document.querySelector('#lgOtpCode').value }));
  ok(wrong.kind === 'error' && /نادرست|مهلت/.test(wrong.st) && wrong.step, 'wrong code: REAL 401 shown in Persian, user stays on the code step', JSON.stringify(wrong).slice(0, 140));
  await p.screenshot({ path: OUT + '/wrong-code.png' });
  await p.fill('#lgOtpCode', ''); await p.focus('#lgOtpCode'); await p.keyboard.type(CODE); await p.click('#lgOtpVerify');
  await p.waitForSelector('#lgAuthenticated', { timeout: 8000 });
  ok(true, 'wrong then right code: same challenge still verifies (attempt counter, not lockout)');
  await b.close();
  // consumed challenge replay
  const { b: b2, p: p2 } = await session();
  await p2.goto(BASE + '/login.html?mode=server&next=account.html', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await loginWith(p2, PHONE_OLD, CODE, ch); await p2.click('#lgOtpVerify'); await sleep(1200);
  const replay = await p2.evaluate(() => ({ st: document.querySelector('#lgStatus').textContent, kind: document.querySelector('#lgStatus').dataset.kind }));
  ok(replay.kind === 'error' && /نادرست|مهلت/.test(replay.st), 'consumed/expired challenge: REAL 401 → «کد نادرست است یا مهلتش گذشته است»', replay.st);
  await p2.screenshot({ path: OUT + '/expired-code.png' });
  await b2.close();
}
// ── 4) rate limit (real 429 after too many wrong codes on fresh challenges is IP-based: 20/15min) — report only, do not trigger (shared test server)
console.log('  note: IP rate-limit (429 login_temporarily_blocked) covered by pytest, not triggered here to keep the shared test server usable');
// ── 5) network loss during verify → honest error, no fake login
{
  const { b, p } = await session();
  const ch = mkChallenge(PHONE_OLD, CODE);
  await p.goto(BASE + '/login.html?mode=server&next=account.html', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await loginWith(p, PHONE_OLD, CODE, ch);
  await p.route('**/api/auth/phone-otp/verify', r => r.abort('connectionfailed'));
  await p.click('#lgOtpVerify'); await sleep(1000);
  const r = await p.evaluate(() => ({ st: document.querySelector('#lgStatus').textContent, kind: document.querySelector('#lgStatus').dataset.kind, auth: !!document.querySelector('#lgAuthenticated'), busy: document.querySelector('#lgOtpVerify') && document.querySelector('#lgOtpVerify').disabled }));
  ok(r.kind === 'error' && /ارتباط با سرور/.test(r.st) && !r.auth && !r.busy, 'offline during verify: «ارتباط با سرور برقرار نشد»، no fake login, button re-enabled', JSON.stringify(r));
  await p.screenshot({ path: OUT + '/offline-verify.png' });
  await b.close();
}
// ── 6) desktop new-member card + dark theme snapshot (simulated verify response only for the visual; real path already proven above)
{
  const { b, p } = await session({ width: 1280, height: 800 });
  await p.route('**/api/auth/phone-otp/request', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ accepted: true, challenge_id: '6a1d2f33-8f1e-4b55-9d0c-1c2e3f4a5b6c', expires_in: 180, resend_in: 90 }) }));
  let verified = false, meCalls = 0;
  await p.route('**/api/auth/phone-otp/verify', r => { verified = true; r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: true, account_id: 'sim', provider: 'phone', created: true, profile_saved: false }) }); });
  await p.route('**/api/account/me', r => { meCalls++; if (!verified) return r.continue(); r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: true, account_id: 'sim', provider: 'phone', role: null, permissions: [], delivery_bot_url: 'https://ble.ir/nora_bot' }) }); });
  await p.goto(BASE + '/login.html?mode=server&next=account.html', { waitUntil: 'domcontentloaded' }); await sleep(1200);
  await p.fill('#lgPhone', '09123456789'); await p.fill('#lgCapAnswer', '1234'); await p.click('#lgPhoneSubmit'); await p.waitForSelector('#lgOtpCode');
  await p.focus('#lgOtpCode'); await p.keyboard.type('123456'); await p.click('#lgOtpVerify'); await p.waitForSelector('#lgAuthenticated'); await sleep(400);
  await p.screenshot({ path: OUT + '/SIMULATED-new-card-desktop-light.png' });
  await p.click('.themesw'); await sleep(400);
  await p.screenshot({ path: OUT + '/SIMULATED-new-card-desktop-dark.png' });
  const r = await p.evaluate(() => ({ bot: !!document.querySelector('#lgAuthenticated a[href="https://ble.ir/nora_bot"]'), primaries: document.querySelectorAll('#lgAuthenticated .lgbtn:not(.quiet)').length, links: [...document.querySelectorAll('#lgAuthenticated a')].map(a => a.getAttribute('href')), h: document.querySelector('.lgdtitle').textContent }));
  console.log('  meCalls', meCalls);
  ok(r.bot && r.primaries === 1, 'SIMULATED new-member card: bot link rendered from server value, single primary action', JSON.stringify(r));
  await b.close();
}
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
