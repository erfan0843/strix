const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const base = process.argv[2] || 'http://127.0.0.1:8000', out = process.argv[3] || '<local>/shots/s4', tag = process.argv[4] || 'owner';
(async () => {
  const b = await launchBrowser(); const p = await b.newPage(); await p.setViewportSize({ width: 1024, height: 768 }); p.on('dialog', d => d.accept());
  await p.goto(base + '/builder.html', { waitUntil: 'load' }); await sleep(3000);
  for (const [go, box] of [['fTeam', '#fTeam'], ['fKartabl', '#fKartabl'], ['fAttend', '#fAttend']]) {
    await p.evaluate(g => document.querySelector('[data-go="' + g + '"]').click(), go); await sleep(700);
    const info = await p.evaluate(sel => { const s = document.querySelector(sel); const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      return { text: s.innerText.replace(/\s+/g, ' ').slice(0, 900), links: [...s.querySelectorAll('a[href]')].filter(vis).map(a => a.getAttribute('href') + ' | ' + a.textContent.trim()), buttons: [...s.querySelectorAll('button,input,select')].filter(vis).map(x => (x.id || x.className) + (x.disabled ? ' [disabled]' : '') + ' | ' + (x.textContent || x.placeholder || '').trim().slice(0, 30)) }; }, box);
    console.log('==', tag, go, JSON.stringify(info, null, 1));
    await p.screenshot({ path: `${out}/${tag}-${go}.png` });
  }
  for (const h of ['#users', '#inbox', '#attendance', '#staff']) {
    await p.goto('about:blank'); await p.goto(base + '/admin.html' + h, { waitUntil: 'load' }); await sleep(3500);
    const info = await p.evaluate(() => ({ hash: location.hash, h1: [...document.querySelectorAll('h1,h2,.head,.ttl')].filter(e => e.getBoundingClientRect().height > 0).slice(0, 4).map(e => e.textContent.trim().slice(0, 50)), toast: (document.getElementById('toast') || {}).textContent, text: document.body.innerText.replace(/\s+/g, ' ').slice(0, 400) }));
    console.log('== admin', h, JSON.stringify(info, null, 1));
    await p.screenshot({ path: `${out}/${tag}-admin-${h.slice(1)}.png` });
  }
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
