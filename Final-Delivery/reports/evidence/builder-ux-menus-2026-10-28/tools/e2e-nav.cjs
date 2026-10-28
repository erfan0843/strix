// ناوبری — پذیرش مرورگری (نسخهٔ ۱۴۰۵/۰۸/۰۶): گروه «مدیران» (کاربران + گزارش‌ها) با سرگروه باز/بسته در ریل پنل، «فرم‌ساز» در ریل/نوار پایین پنل و در منوی اصلی سایت
// برای نقش‌های مجاز (مالک :8000، مدیر :8080)، نبودِ آن برای عضو (:8090) و میهمان (:8001)، deep linkها و دسترسی سروری.
const path = require('path'); const fs = require('fs');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const OWNER = 'http://127.0.0.1:8000', MANAGER = 'http://127.0.0.1:8080', MEMBER = 'http://127.0.0.1:8090', GUEST = 'http://127.0.0.1:8001';
const out = process.argv[2]; fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const lines = []; let pass = 0, fail = 0;
const L = (...a) => { const s = a.map(x => typeof x === 'string' ? x : JSON.stringify(x)).join(' '); lines.push(s); console.log(s); };
const check = (name, ok, extra) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + name + (ok ? '' : ' ✗') + (extra ? ' ' + JSON.stringify(extra) : '')); };

(async () => {
  const browser = await launchBrowser();
  const page = await browser.newPage(); page.on('dialog', d => d.accept());
  const shot = (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (e) {} await sleep(150); } return false; };
  const ev = (fn, arg) => page.evaluate(fn, arg);
  const goto = async (url, w = 1440, h = 900) => { await page.setViewportSize({ width: w, height: h }); await page.goto('about:blank'); await page.goto(url, { waitUntil: 'load' }); await sleep(1200); };
  const api = (p) => page.evaluate(async p => { const r = await fetch(p, { credentials: 'same-origin', headers: { Accept: 'application/json' } }); return r.status; }, p);
  try {
    for (const [role, base] of [['owner', OWNER], ['manager', MANAGER]]) {
      // ریل دسکتاپ
      await goto(base + '/admin.html#dash');
      await waitFor(() => ev(() => !!document.querySelector('#admNav [data-sec="users"]')));
      const rail = await ev(() => [...document.querySelectorAll('#admNav [data-sec],#admNav [data-center-href]')].map(x => x.dataset.sec || 'forms'));
      check(role + ': ترتیب ریل', JSON.stringify(rail) === JSON.stringify(['dash', 'newev', 'events', 'users', 'reports', 'forms', 'settings']), rail);
      const grp = await ev(() => { const g = document.querySelector('#admNav [data-nav-group="people"]'); return g ? { head: g.querySelector('.nav-group-head').textContent.trim(), kids: [...g.querySelectorAll('[data-sec]')].map(x => x.dataset.sec + ':' + (x.dataset.locked === '1' ? 'locked' : 'open')) } : null; });
      check(role + ': گروه «مدیران» با دو زیرمقصد (کاربران، گزارش‌ها)', !!grp && grp.head === 'مدیران' && grp.kids.join(',') === 'users:open,reports:open', grp);
      const headA = await ev(() => { const h = document.querySelector('#admNav button[data-nav-toggle="people"]'); return h ? { exp: h.getAttribute('aria-expanded'), ctl: h.getAttribute('aria-controls'), hidden: document.getElementById('navgrp-people').hidden } : null; });
      check(role + ': سرگروه «مدیران» دکمهٔ واقعی با aria-expanded=true و aria-controls است', !!headA && headA.exp === 'true' && headA.ctl === 'navgrp-people' && !headA.hidden, headA);
      await ev(() => document.querySelector('#admNav [data-nav-toggle="people"]').click()); await sleep(300);
      const headB = await ev(() => { const h = document.querySelector('#admNav [data-nav-toggle="people"]'); return { exp: h.getAttribute('aria-expanded'), hidden: document.getElementById('navgrp-people').hidden, focus: document.activeElement === h, kidsVisible: [...document.querySelectorAll('#navgrp-people [data-sec]')].filter(x => x.getClientRects().length).length }; });
      check(role + ': کلیک سرگروه، گروه را می‌بندد (aria-expanded=false، زیرمقصدها پنهان، فوکوس روی سرگروه)', headB.exp === 'false' && headB.hidden && headB.focus && headB.kidsVisible === 0, headB);
      if (role === 'owner') await shot('01b-admin-rail-collapsed-1440');
      await page.keyboard.press('Enter'); await sleep(300);
      check(role + ': Enter روی سرگروه دوباره باز می‌کند', await ev(() => document.querySelector('#admNav [data-nav-toggle="people"]').getAttribute('aria-expanded') === 'true' && !document.getElementById('navgrp-people').hidden));
      const forms = await ev(() => { const a = document.querySelector('#admNav a[data-center-href]'); return a ? { t: a.textContent.trim(), h: a.getAttribute('href') } : null; });
      check(role + ': «فرم‌ساز» در ریل → builder.html', !!forms && forms.t === 'فرم‌ساز' && forms.h === 'builder.html', forms);
      if (role === 'owner') await shot('01-admin-rail-1440');
      // کلیک زیرمقصدها
      await ev(() => document.querySelector('#admNav [data-sec="reports"]').click()); await sleep(800);
      const rep = await ev(() => ({ hash: location.hash, on: !!document.querySelector('#admNav [data-sec="reports"].on'), grpOn: !!document.querySelector('#admNav [data-nav-group="people"].on'), usersOn: !!document.querySelector('#admNav [data-sec="users"].on'), tab: (document.querySelector('[data-user-hub][aria-selected="true"]') || {}).textContent }));
      check(role + ': کلیک «گزارش‌ها» → #reports، فعال، والد روشن، «کاربران» خاموش', rep.hash === '#reports' && rep.on && rep.grpOn && !rep.usersOn && /گزارش/.test(rep.tab || ''), rep);
      if (role === 'owner') await shot('02-admin-reports-1440');
      await ev(() => document.querySelector('#admNav [data-sec="users"]').click()); await sleep(800);
      const us = await ev(() => ({ hash: location.hash, on: !!document.querySelector('#admNav [data-sec="users"].on'), repOn: !!document.querySelector('#admNav [data-sec="reports"].on') }));
      check(role + ': کلیک «کاربران» → #users مستقل', us.hash === '#users' && us.on && !us.repOn, us);
      // deep link مستقیم
      await goto(base + '/admin.html#reports');
      await waitFor(() => ev(() => !!document.querySelector('#admNav [data-sec="reports"].on')));
      check(role + ': deep link #reports همچنان کار می‌کند', await ev(() => !!document.querySelector('#admNav [data-sec="reports"].on') && !!document.querySelector('[data-user-hub="reports"][aria-selected="true"]')));
      await goto(base + '/admin.html#users');
      await waitFor(() => ev(() => !!document.querySelector('#admNav [data-sec="users"].on')));
      check(role + ': deep link #users همچنان کار می‌کند', await ev(() => !!document.querySelector('#admNav [data-sec="users"].on')));
      // گروه بسته + ورود مستقیم: باید باز و فعال شود
      await ev(() => document.querySelector('#admNav [data-sec="dash"]').click()); await sleep(400);
      await ev(() => document.querySelector('#admNav [data-nav-toggle="people"]').click()); await sleep(300);
      await goto(base + '/admin.html#reports');
      const deep = await ev(() => ({ exp: document.querySelector('#admNav [data-nav-toggle="people"]').getAttribute('aria-expanded'), on: !!document.querySelector('#admNav [data-sec="reports"].on'), grpOn: !!document.querySelector('#admNav [data-nav-group="people"].on') }));
      check(role + ': گروه بسته‌شده با پیوند مستقیم #reports باز می‌شود و والد/زیرمقصد فعال‌اند', deep.exp === 'true' && deep.on && deep.grpOn, deep);
      await ev(() => { location.hash = '#users'; }); await sleep(600);
      check(role + ': تغییر هش از #reports به #users (پیوند قدیمی) همان صفحه را عوض می‌کند', await ev(() => !!document.querySelector('#admNav [data-sec="users"].on') && !document.querySelector('#admNav [data-sec="reports"].on') && document.querySelector('[data-user-hub="users"]').getAttribute('aria-selected') === 'true'));
      await ev(() => { document.documentElement.setAttribute('data-theme', 'dark'); }); await sleep(200);
      if (role === 'owner') await shot('02b-admin-users-dark-1440');
      const dark = await ev(() => { const h = document.querySelector('#admNav [data-nav-toggle="people"]'); const c = getComputedStyle(h); return { color: c.color, bg: getComputedStyle(document.body).backgroundColor }; });
      check(role + ': حالت تیره، سرگروه رنگ متن دارد (نه نامرئی)', dark.color && dark.color !== 'rgba(0, 0, 0, 0)', dark);
      await ev(() => { document.documentElement.setAttribute('data-theme', 'light'); });
      // نوار پایین موبایل
      await goto(base + '/admin.html#dash', 390, 844);
      await waitFor(() => ev(() => !!document.querySelector('#admTabs a')));
      const bar = await ev(() => [...document.querySelectorAll('#admTabs a')].map(a => (a.dataset.sec || 'forms') + ':' + a.textContent.trim() + ':' + (a.getAttribute('aria-label') || '')));
      const expectBar = ['dash:داشبورد:', 'events:رویدادها:', 'users:مدیران:مدیران', 'forms:فرم‌ساز:'].concat(role === 'owner' ? ['settings:تنظیمات:'] : []);
      check(role + ': نوار پایین موبایل = داشبورد، رویدادها، مدیران، فرم‌ساز' + (role === 'owner' ? '، تنظیمات' : ' (تنظیمات برای مدیر قفل است)'), JSON.stringify(bar) === JSON.stringify(expectBar), bar);
      const ov = await ev(() => { const b = document.getElementById('admTabs'); return { sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, vis: b && getComputedStyle(b).display !== 'none', h: b && b.getBoundingClientRect().height }; });
      check(role + ': موبایل ۳۹۰ بدون سرریز افقی و نوار پایین دیده می‌شود', ov.sw <= ov.cw && ov.vis && ov.h < 90, ov);
      await page.setViewportSize({ width: 360, height: 740 }); await sleep(300);
      const ov360 = await ev(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, labels: [...document.querySelectorAll('#admTabs a span')].every(s => s.scrollWidth <= s.clientWidth + 1) }));
      check(role + ': موبایل ۳۶۰ بدون سرریز افقی و برچسب زبانه‌ها بریده نمی‌شوند', ov360.sw <= ov360.cw && ov360.labels, ov360);
      await page.setViewportSize({ width: 390, height: 844 }); await sleep(200);
      if (role === 'owner') await shot('03-admin-tabbar-390');
      await ev(() => document.querySelector('#admTabs [data-sec="users"]').click()); await sleep(800);
      check(role + ': زبانهٔ موبایل گروه → بخش کاربران با زیرزبانه‌های کاربران/گزارش‌ها', await ev(() => location.hash === '#users' && document.querySelectorAll('[data-user-hub][role="tab"]').length === 2));
      await ev(() => document.querySelector('[data-user-hub="reports"]').click()); await sleep(800);
      check(role + ': زیرزبانهٔ «گزارش‌ها» در موبایل → #reports و زبانهٔ گروه فعال', await ev(() => location.hash === '#reports' && !!document.querySelector('#admTabs [data-sec="users"].on')));
      if (role === 'owner') await shot('04-admin-reports-390');
      // منوی اصلی سایت
      await goto(base + '/home.html');
      const okTab = await waitFor(() => ev(() => !!document.querySelector('.tabbar [data-forms-nav]')), 6000);
      const tabs = await ev(() => [...document.querySelectorAll('.tabbar a')].map(a => a.querySelector('small').textContent.trim()));
      check(role + ': «فرم‌ساز» در منوی اصلی سایت (home.html) پس از تأیید سرور', okTab && tabs.includes('فرم‌ساز') && tabs.length === 4, tabs);
      if (role === 'owner') { await shot('05-home-tabbar-1440'); await page.setViewportSize({ width: 390, height: 844 }); await sleep(300); await shot('06-home-tabbar-390'); }
      const ovh = await ev(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
      check(role + ': منوی اصلی ۴زبانه‌ای بدون سرریز افقی', ovh.sw <= ovh.cw, ovh);
      for (const w of [1024, 360]) { await page.setViewportSize({ width: w, height: w > 600 ? 768 : 740 }); await sleep(300);
        const o = await ev(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, n: document.querySelectorAll('.tabbar [data-forms-nav]').length, tabH: document.querySelector('.tabbar [data-forms-nav]').getBoundingClientRect().height }));
        check(role + ': منوی اصلی در ' + w + ' بدون سرریز، یک زبانهٔ «فرم‌ساز» با ارتفاع لمسی', o.sw <= o.cw && o.n === 1 && o.tabH >= 40, o); }
      await page.setViewportSize({ width: 1440, height: 900 }); await sleep(200);
      // صفحهٔ حساب (منبع نشست = خود صفحه) هم باید زبانه را بسازد
      await goto(base + '/account.html'); await sleep(1800);
      const acc = await ev(() => ({ n: document.querySelectorAll('.tabbar [data-forms-nav]').length, href: (document.querySelector('.tabbar [data-forms-nav]') || {}).getAttribute && document.querySelector('.tabbar [data-forms-nav]').getAttribute('href'), tabs: document.querySelector('.tabbar').getAttribute('data-tabs') }));
      check(role + ': «فرم‌ساز» در نوار پایین account.html هم هست (یک‌بار، به builder.html)', acc.n === 1 && acc.href === 'builder.html' && acc.tabs === '4', acc);
      await ev(() => document.querySelector('.tabbar [data-forms-nav]').click()); await sleep(1200);
      check(role + ': از صفحهٔ حساب، «فرم‌ساز» به builder.html می‌رسد', /builder\.html/.test(page.url()));
      await goto(base + '/events.html'); await sleep(1500);
      check(role + ': events.html نیز دقیقاً یک زبانهٔ «فرم‌ساز» دارد (بدون تکرار)', (await ev(() => document.querySelectorAll('.tabbar [data-forms-nav]').length)) === 1);
      await goto(base + '/home.html');
      await waitFor(() => ev(() => !!document.querySelector('.tabbar [data-forms-nav]')), 6000);
      await ev(() => document.querySelector('.tabbar [data-forms-nav]').click()); await sleep(1500);
      check(role + ': کلیک «فرم‌ساز» → builder.html (مرکز فرم‌ها)', /builder\.html/.test(page.url()));
      const builderOk = await waitFor(() => ev(() => !!document.querySelector('#fList.on') && !/ورود/.test((document.querySelector('#fList h2, #fList .head') || {}).textContent || '')), 6000);
      check(role + ': مرکز فرم‌ها برای نقش مجاز باز شد', builderOk, page.url());
      const back = await ev(() => [...document.querySelectorAll('aside a[href="admin.html"], .quicknav a[href="admin.html"], aside a[href="create.html"], .quicknav a[href="create.html"]')].map(a => a.getAttribute('href')));
      check(role + ': راه بازگشت به پنل و راه «ساخت فرم» از مرکز فرم‌ها روشن است', back.includes('admin.html') && back.includes('create.html'), back);
    }
    // مدیر بدون rp_view: ریل باید زیرمقصد گزارش‌ها را قفل کند — در فیکسچر فعلی مدیر rp_view دارد؛ فقط ثبت می‌شود
    // عضو (:8090): منوی اصلی بدون «فرم‌ساز»، دسترسی سروری فرم‌ها بسته
    await goto(MEMBER + '/home.html'); await sleep(2500);
    const mtabs = await ev(() => [...document.querySelectorAll('.tabbar a')].map(a => a.querySelector('small').textContent.trim()));
    check('عضو: «فرم‌ساز» در منوی اصلی نیست (۳ زبانه، حساب من)', !mtabs.includes('فرم‌ساز') && mtabs.length === 3 && mtabs.includes('حساب من'), mtabs);
    await goto(MEMBER + '/account.html'); await sleep(2500);
    const macc = await ev(() => ({ n: document.querySelectorAll('.tabbar [data-forms-nav]').length, src: window.NORA_ACCOUNT_SOURCE, label: (document.querySelector('[data-account-nav-label]') || {}).textContent }));
    check('عضو: در account.html (نشست سروری عضو بدون fm_create) زبانهٔ «فرم‌ساز» ساخته نمی‌شود', macc.n === 0 && macc.src === 'server' && macc.label === 'حساب من', macc);
    await shot('07-account-member-1440');
    await ev(() => window.NORA_UI.updateAccountNavigation([])); 
    check('عضو: فراخوانی با آرایهٔ خالی (خروج) چیزی نمی‌شکند و زبانه‌ای نمی‌سازد', (await ev(() => document.querySelectorAll('.tabbar [data-forms-nav]').length)) === 0);
    check('عضو: GET /api/forms از سرور بسته است (401/403)', [401, 403].includes(await api('/api/forms')), null);
    check('عضو: GET /api/admin/users از سرور بسته است (401/403)', [401, 403].includes(await api('/api/admin/users')), null);
    await goto(MEMBER + '/builder.html'); await sleep(2000);
    const mb = await ev(() => ({ login: !!document.querySelector('a[href*="login.html"]') || /ورود/.test(document.body.textContent), list: document.querySelectorAll('[data-form-row],[data-form-id]').length }));
    check('عضو: نشانی مستقیم builder.html فهرست فرمی نشان نمی‌دهد و به ورود ارجاع می‌دهد', mb.list === 0 && mb.login, mb);
    // میهمان (:8001)
    await goto(GUEST + '/home.html'); await sleep(2500);
    const gtabs = await ev(() => [...document.querySelectorAll('.tabbar a')].map(a => a.querySelector('small').textContent.trim()));
    check('میهمان: «فرم‌ساز» در منوی اصلی نیست', !gtabs.includes('فرم‌ساز') && gtabs.length === 3, gtabs);
    check('میهمان: GET /api/forms بسته است (401)', (await api('/api/forms')) === 401);
    await goto(GUEST + '/admin.html#reports'); await sleep(2000);
    check('میهمان: admin.html#reports به ورود کارکنان می‌رسد، نه داده', await ev(() => !!document.querySelector('a[href^="login.html?mode=staff"]') && !document.querySelector('#admNav [data-sec="reports"].on')));
    // صفحه‌کلید: ریل با Tab پیمایش‌پذیر است و زیرمقصدها فوکوس می‌گیرند
    await goto(OWNER + '/admin.html#dash'); await waitFor(() => ev(() => !!document.querySelector('#admNav [data-sec="users"]')));
    check('حالت بستهٔ گروه پس از بارگذاری دوباره روی همان مقصد (داشبورد) به یاد می‌ماند', await ev(() => document.querySelector('#admNav [data-nav-toggle="people"]').getAttribute('aria-expanded') === 'false'));
    await ev(() => { const h = document.querySelector('#admNav [data-nav-toggle="people"]'); if (h.getAttribute('aria-expanded') !== 'true') h.click(); }); await sleep(300);
    await ev(() => document.querySelector('#admNav [data-sec="events"]').focus());
    await page.keyboard.press('Tab'); const f1 = await ev(() => document.activeElement.dataset.navToggle);
    await page.keyboard.press('Tab'); const f2 = await ev(() => document.activeElement.dataset.sec);
    await page.keyboard.press('Tab'); const f3 = await ev(() => document.activeElement.getAttribute('data-center-href') || document.activeElement.dataset.sec);
    await page.keyboard.press('Tab'); const f4 = await ev(() => document.activeElement.getAttribute('data-center-href') || document.activeElement.dataset.sec);
    check('صفحه‌کلید: Tab از رویدادها → سرگروه «مدیران» → کاربران → گزارش‌ها → فرم‌ساز', f1 === 'people' && f2 === 'users' && f3 === 'reports' && f4 === 'builder.html', [f1, f2, f3, f4]);
    await page.keyboard.press('Enter'); await sleep(1200);
    check('صفحه‌کلید: Enter روی «فرم‌ساز» به مرکز فرم‌ها می‌رود', /builder\.html/.test(page.url()));
  } catch (e) { L('ERROR ' + (e && e.stack || e)); fail++; }
  await browser.close();
  L('TOTAL PASS ' + pass + ' / FAIL ' + fail);
  fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\n');
  process.exit(fail ? 1 : 0);
})();
