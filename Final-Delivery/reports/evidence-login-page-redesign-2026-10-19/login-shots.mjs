// Login page screenshot matrix (before/after). Usage: TAG=before|after node _login_shots.mjs
// Output: /tmp/qa/login/<TAG>/<state>-<w>x<h>-<theme>.png + metrics lines on stdout
import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE = 'http://127.0.0.1:8000';
const TAG = process.env.TAG || 'before';
const OUT = `/tmp/qa/login/${TAG}`; fs.mkdirSync(OUT, { recursive: true });
const ONLY = process.env.ONLY ? process.env.ONLY.split(',') : null;
const VPS = [[360, 800], [390, 844], [768, 1024], [1280, 800], [1440, 900]];
const MOCK_OTP = { accepted: true, challenge_id: 'mock-challenge-qa', expires_in: 180, resend_in: 90 };

let cookies = [];
try {
  const pw = fs.readFileSync('/tmp/nora-preview/owner-pw.txt', 'utf8').trim();
  const r = await fetch(BASE + '/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: BASE }, body: JSON.stringify({ username: 'preview-owner', password: pw }) });
  cookies = (r.headers.getSetCookie ? r.headers.getSetCookie() : []).map(s => { const [kv] = s.split(';'); const i = kv.indexOf('='); return { name: kv.slice(0, i).trim(), value: kv.slice(i + 1).trim(), domain: '127.0.0.1', path: '/' }; });
  console.log('owner login', r.status);
} catch (e) { console.log('owner login failed', e.message); }

async function fillPhone(p, phone = '09123456789', cap = '1234') {
  await p.waitForSelector('#lgPhone', { timeout: 8000 });
  await p.fill('#lgPhone', phone);
  await p.fill('#lgCapAnswer', cap);
}
// state name -> { url, prep(page), auth }
const STATES = {
  'phone': { url: '/login.html' },
  'phone-invalid': { url: '/login.html', prep: async p => { await fillPhone(p, '123'); await p.click('#lgPhoneSubmit'); await p.waitForTimeout(400); } },
  'phone-error-503': { url: '/login.html', prep: async p => { await fillPhone(p); await p.click('#lgPhoneSubmit'); await p.waitForTimeout(1500); } },
  'phone-loading': { url: '/login.html', route: async p => { await p.route('**/api/auth/phone-otp/request', r => setTimeout(() => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_OTP) }), 4000)); }, prep: async p => { await fillPhone(p); await p.click('#lgPhoneSubmit'); await p.waitForTimeout(500); } },
  'otp-mock': { url: '/login.html', route: async p => { await p.route('**/api/auth/phone-otp/request', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_OTP) })); }, prep: async p => { await fillPhone(p); await p.click('#lgPhoneSubmit'); await p.waitForSelector('#lgPhoneCodeForm', { timeout: 8000 }); await p.waitForTimeout(400); } },
  'otp-mock-typed': { url: '/login.html', route: async p => { await p.route('**/api/auth/phone-otp/request', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_OTP) })); }, prep: async p => { await fillPhone(p); await p.click('#lgPhoneSubmit'); await p.waitForSelector('#lgOtpCode', { timeout: 8000 }); await p.focus('#lgOtpCode'); await p.keyboard.type('123'); await p.waitForTimeout(300); } },
  'staff': { url: '/login.html?mode=staff&next=admin.html%23dash' },
  'rules': { url: '/login.html', prep: async p => { await p.click('#rulesBtn'); await p.waitForTimeout(600); } },
  'authenticated': { url: '/login.html', auth: true, prep: async p => { await p.waitForSelector('#lgContinue', { timeout: 8000 }); await p.waitForTimeout(300); } },
  'keyboard-390x500': { url: '/login.html', vp: [390, 500], prep: async p => { await p.focus('#lgPhone'); await p.waitForTimeout(300); } },
};
const PLAN = [
  ['phone', VPS, ['light', 'dark']],
  ['phone-invalid', [[390, 844], [1280, 800]], ['light', 'dark']],
  ['phone-error-503', [[390, 844], [1280, 800]], ['light']],
  ['phone-loading', [[390, 844], [1280, 800]], ['light']],
  ['otp-mock', [[360, 800], [390, 844], [768, 1024], [1280, 800]], ['light', 'dark']],
  ['otp-mock-typed', [[390, 844]], ['light']],
  ['staff', [[390, 844], [1280, 800]], ['light', 'dark']],
  ['rules', [[390, 844], [1280, 800]], ['light']],
  ['authenticated', [[390, 844], [1280, 800]], ['light']],
  ['keyboard-390x500', [[390, 500]], ['light']],
];
let n = 0, bad = 0;
for (const [state, vps, themes] of PLAN) {
  if (ONLY && !ONLY.includes(state)) continue;
  const S = STATES[state];
  for (const [w, h] of vps) for (const theme of themes) {
    const b = await launchBrowser();
    try {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, serviceWorkers: 'block', locale: 'fa-IR' });
      if (S.auth && cookies.length) await ctx.addCookies(cookies);
      await ctx.addInitScript(t => { try { localStorage.setItem('nora-theme', t); } catch (e) {} }, theme);
      const p = await ctx.newPage(); const errs = [];
      p.on('pageerror', e => errs.push(String(e.message).slice(0, 100)));
      p.on('console', m => { if (m.type() === 'error' && !/401|403|404|503|favicon|Failed to load resource/.test(m.text())) errs.push(m.text().slice(0, 100)); });
      if (S.route) await S.route(p);
      await p.goto(BASE + S.url, { waitUntil: 'domcontentloaded' });
      await p.waitForTimeout(1200);
      if (S.prep) await S.prep(p);
      const m = await p.evaluate(() => {
        const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
        const q = s => document.querySelector(s);
        const rect = s => { const el = q(s); if (!el || !vis(el)) return null; const r = el.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
        const broken = [...document.querySelectorAll('use')].filter(u => { const h = u.getAttribute('href') || ''; return h.startsWith('#') && !document.getElementById(h.slice(1)); }).map(u => u.getAttribute('href'));
        const ctrls = [...document.querySelectorAll('button,a[href],input')].filter(vis);
        const small = ctrls.filter(el => { const r = el.getBoundingClientRect(); return r.width < 24 || r.height < 24; }).length;
        const primary = q('.lgbtn:not(.quiet)');
        const inView = primary && vis(primary) && primary.getBoundingClientRect().bottom <= innerHeight;
        return { title: (q('#lgTitle') || {}).textContent, overflowX: document.documentElement.scrollWidth > innerWidth + 1, broken, small, ctrls: ctrls.length,
          card: rect('#lgCard'), primaryBtn: rect('.lgbtn:not(.quiet)'), primaryInView: !!inView, tabbar: rect('.tabbar'), topbar: rect('.topbar'), status: (q('#lgStatus') && !q('#lgStatus').hidden) ? q('#lgStatus').textContent.trim().slice(0, 60) : '',
          docH: document.documentElement.scrollHeight, theme: document.documentElement.getAttribute('data-theme') };
      });
      const file = `${OUT}/${state}-${w}x${h}-${theme}.png`;
      await p.screenshot({ path: file, fullPage: false });
      n++;
      const flag = (m.overflowX || m.broken.length || errs.length) ? 'WARN' : 'ok';
      if (flag !== 'ok') bad++;
      console.log(`${flag} ${state} ${w}x${h} ${theme} ${JSON.stringify({ ...m, errs })}`);
      await ctx.close();
    } catch (e) { bad++; console.log(`ERROR ${state} ${w}x${h} ${theme}: ${e.message.slice(0, 160)}`); }
    finally { await b.close(); }
  }
}
console.log(`done ${n} shots, ${bad} warnings → ${OUT}`);
process.exit(bad ? 1 : 0);
