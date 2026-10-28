const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => { const b = await launchBrowser(); const page = await b.newPage(); page.on('dialog', d => d.accept());
  const [url, out, ...sizes] = process.argv.slice(2);
  for (const sz of sizes) { const [w, h] = sz.split('x').map(Number); await page.setViewportSize({ width: w, height: h }); await page.goto('about:blank'); await page.goto(url, { waitUntil: 'load' }); await sleep(3000);
    const sw = await page.evaluate(() => document.documentElement.scrollWidth); await page.screenshot({ path: `${out}-${w}.png` }); await page.screenshot({ path: `${out}-${w}-full.png`, fullPage: true }); console.log(`${out}@${w} sw=${sw}`); }
  await b.close(); })().catch(e => { console.error(e); process.exit(1) });
