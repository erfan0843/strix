const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => { const b = await launchBrowser(); const page = await b.newPage();
  await page.addInitScript(() => { window.__shifts = []; try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__shifts.push({ v: +e.value.toFixed(3), t: Math.round(e.startTime), src: (e.sources || []).slice(0, 3).map(s => { const n = s.node; if (!n) return '?'; return n.nodeName + (n.id ? '#' + n.id : '') + (n.className && typeof n.className === 'string' ? '.' + n.className.split(' ').slice(0, 2).join('.') : '') + ' ' + Math.round(s.previousRect.y) + '->' + Math.round(s.currentRect.y); }) }); }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {} });
  const RUNS = +(process.env.CLS_RUNS || 1); const TARGETS = process.env.CLS_TARGETS ? JSON.parse(process.env.CLS_TARGETS) : [['http://127.0.0.1:8000/admin.html', 1440, 900], ['http://127.0.0.1:8000/admin.html#settings', 1024, 768], ['http://127.0.0.1:8000/admin.html', 390, 844], ['http://127.0.0.1:8000/home.html', 390, 844], ['http://127.0.0.1:8000/events.html', 390, 844]];
  for (let run = 0; run < RUNS; run++) for (const [u, w, h] of TARGETS) {
    await page.setViewportSize({ width: w, height: h }); await page.goto('about:blank'); await page.goto(u, { waitUntil: 'load' }); await sleep(3500);
    const s = await page.evaluate(() => window.__shifts); console.log('\n== ' + u + ' @' + w + ' total=' + s.reduce((a, x) => a + x.v, 0).toFixed(3));
    s.filter(x => x.v >= 0.01).forEach(x => console.log('  ' + x.t + 'ms ' + x.v + ' ' + x.src.join(' | ')));
  }
  await b.close(); })().catch(e => { console.error(e); process.exit(1) });
