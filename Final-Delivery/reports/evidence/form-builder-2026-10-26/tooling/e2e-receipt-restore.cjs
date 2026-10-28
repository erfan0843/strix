// Browser proof for defect (پ): after a public visitor uploads a card-transfer receipt in form.html, reloading the page
// restores the «رسید در انتظار بررسی» state from the SERVER draft (no second upload asked, no localStorage dependence).
// Owner (via proxy :8000) creates+publishes a paid card-transfer form linked to a fixture event; the visitor uses the
// real public page on the backend origin (:8001) in Playwright. argv: outdir
const fs = require('fs'); const path = require('path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const O = 'http://127.0.0.1:8000', B = 'http://127.0.0.1:8001';
const log = []; let fails = 0;
const ok = (c, m) => { log.push((c ? '✓ ' : '✗ ') + m); if (!c) fails++; console.log((c ? '✓ ' : '✗ ') + m); };
const stamp = new Date().toISOString().slice(11, 19).replace(/:/g, '');
function fakeReceiptPng() {
  const zlib = require('zlib'); const w = 240, h = 140; const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 3 + 1)] = 0; for (let x = 0; x < w; x++) { const o = y * (w * 3 + 1) + 1 + x * 3; const band = Math.floor(y / 20) % 2; raw[o] = band ? 230 : 40; raw[o + 1] = band ? 240 : 120; raw[o + 2] = band ? 250 : 200; } }
  const crcTable = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; crcTable.push(c >>> 0); }
  const crc = b => { let c = 0xffffffff; for (const x of b) c = crcTable[(c ^ x) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
async function api(p, init) { const r = await fetch(O + p, Object.assign({ headers: { 'content-type': 'application/json' } }, init || {})); return { status: r.status, body: await r.json().catch(() => null) }; }
(async () => {
  const out = process.argv[2]; fs.mkdirSync(out, { recursive: true });
  const forms = (await api('/api/forms')).body.items;
  const evs = (await api('/api/admin/content/events?limit=20')).body.items; const upcoming = evs.find(e => /آینده/.test(e.t || '')) || evs[evs.length - 1]; const eventId = upcoming && upcoming.id;
  ok(!!eventId, 'رویداد fixture برای اتصال فرم پیدا شد');
  const created = await api('/api/forms', { method: 'POST', headers: { 'content-type': 'application/json', 'Idempotency-Key': ('rr-' + stamp + '-' + Math.random().toString(36).slice(2, 10)).padEnd(20, '0') },
    body: JSON.stringify({ name: 'ثبت‌نام پولی (آزمون رسید) ' + stamp, model: 'registration', need: 'reg', ev: eventId,
      settings: { cap: 5, wait: 0, enabledPaymentMethods: ['card_transfer'], receiptReviewRequired: true, fin: [{ l: 'ورودی', p: 500000, off: 0, req: true, d: '' }], paymentCard: { number: '4111111111111111', bank: 'بانک نمونه', holder: 'نورا' } },
      fields: [{ id: 'full-name', t: 'fullname', l: 'نام کامل', required: true }] }) });
  ok(created.status === 201, 'فرم پولی کارت‌به‌کارت ساخته شد (' + created.status + ')');
  const form = created.body;
  const pub = await api('/api/forms/' + form.id + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: form.version }) });
  ok(pub.status === 200, 'فرم منتشر شد (' + pub.status + ')');
  const b = await launchBrowser(); const page = await b.newPage(); page.on('dialog', d => d.accept());
  await page.setViewportSize({ width: 390, height: 844 });
  const url = B + '/form.html?fid=' + encodeURIComponent(form.id) + '&kind=reg';
  await page.goto(url, { waitUntil: 'load' }); await sleep(2500);
  let filled = false;
  // walk the public steps: «شروع» → question (fill name) → payment (card_transfer) → submit
  for (let i = 0; i < 10; i++) {
    const done = await page.evaluate(() => { const el = document.getElementById('serverReceiptUpload'); return !!el && !el.hidden; });
    if (done) break;
    const step = await page.evaluate(() => {
      const vis = e => !!(e && e.offsetParent !== null);
      const inp = [...document.querySelectorAll('input[type="text"], input:not([type])')].filter(e => vis(e) && !e.value);
      let fill = false; if (inp.length) { inp[0].focus(); inp[0].value = 'بازدیدکنندهٔ رسید'; inp[0].dispatchEvent(new Event('input', { bubbles: true })); inp[0].dispatchEvent(new Event('change', { bubbles: true })); inp[0].blur(); fill = true; }
      const fin = [...document.querySelectorAll('[data-fin]')].filter(e => vis(e) && !e.classList.contains('on')); fin.forEach(e => e.click());
      const cards = [...document.querySelectorAll('[data-pay-method="card_transfer"], [data-method="card_transfer"], [data-payment-method="card_transfer"]')].filter(vis); if (cards.length) cards[0].click();
      const btns = [...document.querySelectorAll('button:not([disabled]), a.btn')].filter(e => vis(e) && /شروع|ادامه|ثبت|پرداخت|تأیید|بعدی/.test(e.textContent) && !/انصراف|بازگشت/.test(e.textContent));
      const b = btns.find(x => /ثبت|پرداخت/.test(x.textContent)) || btns[0]; if (!b) return { fill, btn: null };
      b.click(); return { fill, btn: b.textContent.trim().slice(0, 30) };
    });
    if (step.fill) filled = true;
    await sleep(1300);
    await page.screenshot({ path: path.join(out, 'rr-1-step' + i + '.png') });
    if (!step.btn) break;
  }
  ok(filled, 'نام در فرم عمومی وارد شد');
  const draft0 = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); return { status: r.status, body: await r.json() }; }, form.id);
  ok(draft0.status === 200 && draft0.body.submitted === true, 'ثبت‌نام در فرم عمومی انجام شد (پیش‌نویس سرور submitted=true)');
  await sleep(800);
  const uploadVisible = await page.evaluate(() => { const el = document.getElementById('serverReceiptUpload'); return !!el && !el.hidden; });
  ok(uploadVisible, 'گام «ثبت فیش» پس از ثبت‌نام کارت‌به‌کارت نمایان است');
  await page.screenshot({ path: path.join(out, 'rr-2-receipt-step.png') });
  const png = fakeReceiptPng();
  await page.setInputFiles('#serverReceiptFile', { name: 'receipt.png', mimeType: 'image/png', buffer: png });
  await sleep(800);
  const goBtn = await page.evaluate(() => { const b = [...document.querySelectorAll('button')].find(x => x.offsetParent && !x.disabled && /ثبت فیش/.test(x.textContent)); if (b) { b.click(); return b.textContent.trim(); } return null; });
  await sleep(3000);
  const afterUpload = await page.evaluate(() => ({ review: !(document.getElementById('serverReceiptReview') || { hidden: true }).hidden, upload: !(document.getElementById('serverReceiptUpload') || { hidden: true }).hidden, msg: (document.getElementById('receiptReviewMessage') || {}).textContent || '', up: (document.getElementById('serverReceiptMessage') || {}).textContent || '', }));
  ok(afterUpload.review && !afterUpload.upload, 'پس از آپلود، وضعیت «در انتظار بررسی» دیده می‌شود و گام آپلود بسته شد' + (goBtn ? ' (دکمه: ' + goBtn + ')' : '') + (afterUpload.review ? '' : ' · ' + afterUpload.up));
  await page.screenshot({ path: path.join(out, 'rr-3-after-upload.png') });
  const draft = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); return { status: r.status, body: await r.json() }; }, form.id);
  ok(draft.status === 200 && draft.body.submitted === true && draft.body.receipt_uploaded === true, 'پیش‌نویس سرور receipt_uploaded=true را برمی‌گرداند (منبع بازیابی = سرور)');
  // Reload with localStorage wiped: the restored state must come from the server draft (cookie), not from the browser.
  await page.evaluate(() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} });
  await page.goto('about:blank'); await page.goto(url, { waitUntil: 'load' }); await sleep(3500);
  const restored = await page.evaluate(() => ({ review: !(document.getElementById('serverReceiptReview') || { hidden: true }).hidden, upload: !(document.getElementById('serverReceiptUpload') || { hidden: true }).hidden, msg: (document.getElementById('receiptReviewMessage') || {}).textContent || '', }));
  const draft2 = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); return { status: r.status, body: await r.json() }; }, form.id);
  ok(draft2.status === 200 && draft2.body.submitted === true && draft2.body.receipt_uploaded === true, 'پس از بارگذاری دوباره (localStorage پاک)، ثبت‌نام و رسید از سرور بازیابی شدند');
  ok(restored.review && !restored.upload, 'گام «ثبت فیش» دوباره خواسته نمی‌شود؛ پیام بررسی نمایش داده می‌شود: ' + restored.msg.slice(0, 60));
  await page.screenshot({ path: path.join(out, 'rr-4-after-reload.png') });
  // Owner side: the receipt is a real server fact — the event registration list shows payment «receipt_submitted» for this form.
  const regs = await api('/api/admin/events/' + eventId + '/registrations?limit=50&offset=0&form_id=' + form.id);
  const reg = (regs.body && regs.body.items || []).find(r => JSON.stringify(r).includes(form.id)) || (regs.body && regs.body.items || [])[0];
  ok(regs.status === 200 && !!reg && /receipt_submitted/.test(JSON.stringify(reg)), 'ثبت‌نام در فهرست مدیران با وضعیت پرداخت «رسید فرستاده شده» دیده می‌شود (' + regs.status + ')');
  await b.close();
  fs.writeFileSync(path.join(out, 'log.txt'), log.join('\n') + '\n');
  console.log('e2e-receipt-restore: ' + (log.length - fails) + ' قبول، ' + fails + ' خطا');
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(1); });
