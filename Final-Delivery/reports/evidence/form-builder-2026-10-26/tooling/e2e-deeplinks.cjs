// Deep links from the form center real-mode cards → admin.html, owner (:8000) and manager (:8080), light+dark, desktop+mobile.
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const fs = require('fs'), path = require('path'); const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = process.argv[2] || '<local>'; fs.mkdirSync(out, { recursive: true });
let pass = 0, fail = 0; const lines = []; const ok = (c, m) => { (c ? pass++ : fail++); const l = (c ? '✓ ' : '✗ ') + m; lines.push(l); console.log(l); };
const EXPECT = {
  users: { title: /فهرست کاربران/, owner: 'open', manager: 'open' },
  inbox: { title: /کارتابل پروفایل و فیش/, owner: 'open', manager: 'open' },
  attendance: { title: /حضور و غیاب/, owner: 'open', manager: 'open' },
  staff: { title: /مدیریت نقش حساب‌ها/, owner: 'open', manager: 'dash' },
};
(async () => {
  const b = await launchBrowser(); const p = await b.newPage(); p.on('dialog', d => d.accept());
  for (const [role, base] of [['owner', 'http://127.0.0.1:8000'], ['manager', 'http://127.0.0.1:8080']]) {
    for (const [w, h, vp] of [[1440, 900, 'desktop'], [390, 844, 'mobile']]) {
      await p.setViewportSize({ width: w, height: h });
      // builder cards: which links are offered
      await p.goto('about:blank'); await p.goto(base + '/builder.html', { waitUntil: 'load' }); await sleep(3000);
      const cards = await p.evaluate(() => { const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; }; const r = {};
        for (const [g, box] of [['fTeam', '#teamBox'], ['fKartabl', '#kartabl'], ['fAttend', '#attBody']]) { document.querySelector('[data-go="' + g + '"]').click(); r[g] = [...document.querySelectorAll(box + ' a[href]')].filter(vis).map(a => a.getAttribute('href')); }
        r.sw = document.documentElement.scrollWidth; return r; });
      ok(cards.fTeam.includes('admin.html#users') && cards.fKartabl.includes('admin.html#inbox') && cards.fAttend.includes('admin.html#attendance') && (role === 'owner') === cards.fTeam.includes('admin.html#staff') && cards.sw <= w,
        `${role}/${vp}: کارت‌ها پیوندهای درست را دارند (#staff فقط مالک)؛ بدون سرریز (sw=${cards.sw})`);
      await p.screenshot({ path: path.join(out, `${role}-${vp}-cards-attend.png`) });
      for (const theme of ['light', 'dark']) {
        for (const hsh of Object.keys(EXPECT)) {
          await p.goto('about:blank'); await p.goto(base + '/admin.html#' + hsh, { waitUntil: 'load' }); await sleep(2500);
          if (theme === 'dark') { await p.evaluate(() => { document.documentElement.setAttribute('data-theme', 'dark'); document.documentElement.classList.add('dark'); }); await sleep(300); }
          const st = await p.evaluate(() => ({ heads: [...document.querySelectorAll('#admBody h1,#admBody h2,#admBody .head,#admBody .ttl, h1, h2, .head')].filter(e => e.getBoundingClientRect().height > 0).map(e => e.textContent.trim()).join(' | '), toast: (document.getElementById('toast') || {}).textContent || '', dashboard: /داشبورد/.test(document.body.innerText.slice(0, 400)), sw: document.documentElement.scrollWidth }));
          const exp = EXPECT[hsh][role];
          const good = exp === 'open' ? EXPECT[hsh].title.test(st.heads) : (st.dashboard && /فقط برای مالک/.test(st.toast));
          ok(good && st.sw <= w, `${role}/${vp}/${theme}: admin.html#${hsh} → ${exp === 'open' ? 'بخش درست باز شد' : 'داشبورد + پیام «فقط برای مالک»'} (${(st.heads.match(EXPECT[hsh].title) || [st.toast.trim()])[0]})`);
          if (theme === 'dark' || vp === 'mobile') await p.screenshot({ path: path.join(out, `${role}-${vp}-${theme}-${hsh}.png`) });
        }
      }
    }
  }
  await b.close(); fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + `\ne2e-deeplinks: ${pass} قبول، ${fail} خطا\n`); console.log(`e2e-deeplinks: ${pass} قبول، ${fail} خطا`); process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
