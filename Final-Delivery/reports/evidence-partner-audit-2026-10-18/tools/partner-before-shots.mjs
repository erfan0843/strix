// BEFORE shots: home partners section + old detail sheet (run with old home.html/ui.js checked out).
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const ORIGIN = 'http://127.0.0.1:8000';
const OUT = process.env.OUT || '/tmp/qa/partner-before'; fs.mkdirSync(OUT, { recursive: true });
async function launch() { let b; for (let i = 0; i < 4; i++) { try { b = await launchBrowser(); break; } catch (e) { if (i === 3) throw e; await new Promise(r => setTimeout(r, 1500)); } } return b; }
const out = [];
for (const [w, h] of [[390, 844], [1280, 800]]) {
  const browser = await launch();
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'fa-IR', serviceWorkers: 'block', isMobile: w < 600, hasTouch: w < 600 });
  const page = await ctx.newPage(); const errors = []; page.on('pageerror', e => errors.push(String(e.message)));
  await page.goto(ORIGIN + '/home.html', { waitUntil: 'load' });
  await page.waitForFunction(() => window.NORA_PUBLIC_SOURCE, null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(400);
  await page.evaluate(() => document.getElementById('partners').scrollIntoView({ block: 'start' }));
  await page.waitForTimeout(300);
  const tag = w < 600 ? 'mobile' : 'desktop';
  await page.screenshot({ path: `${OUT}/home-partners-${tag}.png` });
  const info = await page.evaluate(() => ({ cards: [...document.querySelectorAll('#logoWall > *')].map(e => e.tagName + (e.getAttribute('href') ? ' ' + e.getAttribute('href') : '')),
    foot: [...document.querySelectorAll('#footLogos > *')].map(e => e.tagName), sheet: !!document.getElementById('shPartner') }));
  const first = await page.$('#logoWall > *');
  if (first) { const bb = await first.boundingBox(); await page.mouse.click(bb.x + bb.width / 2, bb.y + bb.height / 2); await page.waitForTimeout(500); await page.screenshot({ path: `${OUT}/home-partner-detail-${tag}.png` }); }
  const after = await page.evaluate(() => ({ url: location.href, sheetOpen: !!document.querySelector('#shPartner.on'), h1: document.querySelector('.partner-profile h1')?.textContent || '' }));
  out.push({ viewport: [w, h], ...info, after, errors });
  await browser.close();
}
fs.writeFileSync(`${OUT}/result.json`, JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, null, 1));
