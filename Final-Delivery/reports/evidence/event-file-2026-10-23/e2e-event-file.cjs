// Real-browser E2E for the event file («پروندهٔ رویداد») — dev-only, test DB, synthetic accounts.
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<node-deps> node e2e-event-file.cjs <outdir>
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
// targets are overridable so the same acceptance runs against the SQLite and the PostgreSQL test servers
const O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000', B = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8001';
const out = process.argv[2] || 'shots/event-file';
const fs = require('node:fs'); const path = require('node:path'); fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
// a visible synthetic "receipt" (240×140 RGB stripes) so the person-file screenshot shows the image route working
function fakeReceiptPng() {
  const zlib = require('zlib'); const w = 240, h = 140; const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 3 + 1)] = 0; for (let x = 0; x < w; x++) { const o = y * (w * 3 + 1) + 1 + x * 3; const band = Math.floor(y / 20) % 2; raw[o] = band ? 230 : 40; raw[o + 1] = band ? 240 : 120; raw[o + 2] = band ? 250 : 200; if (x < 12 || x > w - 12) { raw[o] = 20; raw[o + 1] = 60; raw[o + 2] = 90; } } }
  const crcTable = []; for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; crcTable.push(c >>> 0); }
  const crc = b => { let c = 0xffffffff; for (const x of b) c = crcTable[(c ^ x) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const chunk = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
const log = []; const L = (k, v) => { const line = k + ': ' + (typeof v === 'string' ? v : JSON.stringify(v)); log.push(line); console.log(line); };
const check = (name, cond) => L((cond ? 'PASS' : 'FAIL') + ' ' + name, cond ? '' : '✗');
const stamp = new Date().toISOString().slice(11, 19).replace(/:/g, '');
// public visitor straight against the backend (own cookie jar) — registrations are made the way the public form makes them
async function visitor(formId, name, { pay = true, receipt = false } = {}) {
  const jar = {}; const hdr = () => ({ Origin: B, Cookie: Object.entries(jar).map(([k, v]) => k + '=' + v).join('; ') });
  const take = r => { for (const c of (r.headers.getSetCookie ? r.headers.getSetCookie() : [])) { const [kv] = c.split(';'); const [k, v] = kv.split('='); jar[k] = v; } };
  let r = await fetch(B + '/api/public/forms/' + formId + '/draft', { headers: hdr() }); take(r);
  const body = { answers: { 'full-name': name } }; if (pay) body.payment = { method: 'card_transfer', selection: { items: [0], coupon_code: '' } };
  r = await fetch(B + '/api/public/forms/' + formId + '/responses', { method: 'POST', headers: { ...hdr(), 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); take(r);
  const submitted = await r.json(); if (r.status !== 200) throw new Error('register ' + r.status + ' ' + JSON.stringify(submitted));
  if (receipt) {
    const png = fakeReceiptPng();
    r = await fetch(B + '/api/public/forms/' + formId + '/receipt', { method: 'POST', headers: { ...hdr(), 'Content-Type': 'image/png', 'X-File-Name': 'receipt.png' }, body: png });
    if (r.status !== 200) throw new Error('receipt ' + r.status + ' ' + await r.text());
  }
  return submitted;
}
async function surveyAnswer(formId, answers) {
  const jar = {}; const hdr = () => ({ Origin: B, Cookie: Object.entries(jar).map(([k, v]) => k + '=' + v).join('; ') });
  const take = r => { for (const c of (r.headers.getSetCookie ? r.headers.getSetCookie() : [])) { const [kv] = c.split(';'); const [k, v] = kv.split('='); jar[k] = v; } };
  let r = await fetch(B + '/api/public/forms/' + formId + '/draft', { headers: hdr() }); take(r);
  r = await fetch(B + '/api/public/forms/' + formId + '/responses', { method: 'POST', headers: { ...hdr(), 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }) });
  if (r.status !== 200) throw new Error('survey ' + r.status + ' ' + await r.text());
  return r.json();
}
(async () => {
  const browser = await launchBrowser();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'fa-IR', timezoneId: 'Asia/Tehran' });
  const page = await ctx.newPage(); page.on('dialog', d => { L('dialog', d.message().slice(0, 120)); d.accept(); });
  const perrs = []; page.on('pageerror', e => { perrs.push(e.message); L('pageerror', e.message); });
  const shot = (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const click = async sel => page.evaluate(q => { const el = document.querySelector(q); if (!el) return false; el.scrollIntoView({ block: 'center' }); el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); return true; }, sel);
  const setVal = async (sel, v) => page.evaluate(([q, val]) => { const el = document.querySelector(q); if (!el) return false; el.value = val; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); return true; }, [sel, v]);
  const has = sel => page.evaluate(q => !!document.querySelector(q), sel);
  const txt = sel => page.evaluate(q => { const el = document.querySelector(q); return el ? el.textContent.replace(/\s+/g, ' ').trim() : null; }, sel);
  const count = sel => page.evaluate(q => document.querySelectorAll(q).length, sel);
  const hash = () => page.evaluate(() => location.hash);
  const waitFor = async (fn, ms = 6000) => { const end = Date.now() + ms; while (Date.now() < end) { try { if (await fn()) return true; } catch (e) { } await sleep(120); } return false; };
  const api = (p, init) => page.evaluate(async ([pp, ii]) => { const csrf = (document.cookie.match(/nora_csrf=([^;]+)/) || [])[1] || ''; const r = await fetch(pp, Object.assign({ credentials: 'same-origin' }, ii || {}, { headers: Object.assign({ 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, (ii || {}).headers || {}) })); let b = null; try { b = await r.json(); } catch (e) { b = null; } return { status: r.status, body: b }; }, [p, init]);
  const gotoHash = async h => { await page.goto('about:blank'); await page.goto(O + '/admin.html' + h, { waitUntil: 'load' }); await sleep(1600); };
  const idem = () => ('ef-' + stamp + '-' + Math.random().toString(36).slice(2, 10)).padEnd(20, '0');

  // ── 0) fixtures through the real API (owner session via proxy) ──
  await gotoHash('#events');
  const list0 = await api('/api/admin/content/events?limit=1'); let version = list0.body.version;
  const ev = async (t, extra) => { const r = await api('/api/admin/content/events', { method: 'POST', body: JSON.stringify({ expected_version: version, status: 'published', record: Object.assign({ t, kind: 'کارگاه', d: 'رویداد آزمایشی پروندهٔ رویداد', on: '۱۴۰۵/۱۰/۲۰', time: '۱۰:۰۰', place: 'سالن آزمایش', mode: 'حضوری', cap: 50, price: 1 }, extra || {}) }) }); if (r.status !== 200) throw new Error('event ' + r.status + ' ' + JSON.stringify(r.body)); version = r.body.version; return r.body.record.id; };
  const A = await ev('رویداد الف (پرونده) ' + stamp); const Bev = await ev('رویداد ب (پرونده) ' + stamp);
  L('events', { A, B: Bev });
  const mkForm = async (payload) => { const r = await api('/api/forms', { method: 'POST', headers: { 'Idempotency-Key': idem() }, body: JSON.stringify(payload) }); if (r.status !== 201) throw new Error('form ' + r.status + ' ' + JSON.stringify(r.body)); return r.body; };
  const publish = async (id, v) => { const r = await api('/api/forms/' + id + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: v }) }); if (r.status !== 200) throw new Error('publish ' + r.status + ' ' + JSON.stringify(r.body)); return r.body; };
  const PAID = { cap: 3, wait: 0, enabledPaymentMethods: ['card_transfer'], receiptReviewRequired: true, fin: [{ l: 'ورودی', p: 500000, off: 0, req: true, d: '' }], paymentCard: { number: '4111111111111111', bank: 'بانک نمونه', holder: 'حساب سازمان' } };
  const nameField = [{ id: 'full-name', t: 'fullname', l: 'نام کامل', required: true }];
  // A: dedicated registration form — the builder is opened from the event file first (context check), the record is then written through the same API the builder uses
  await gotoHash('#event=' + A + '&tab=forms');
  check('A: forms tab empty state with create action', await waitFor(() => has('[data-ef-forms-empty]')) && await has('[data-ef-create="reg"]'));
  const createHref = await page.evaluate(() => document.querySelector('[data-ef-create="reg"]').getAttribute('href'));
  L('create reg form href', createHref);
  check('create link carries ev + need=reg + back to this event/tab', new RegExp('ev=' + A + '&need=reg').test(createHref) && /back=admin\.html%23event%3D/.test(createHref));
  await shot('01-A-forms-empty', true);
  await page.goto(O + '/' + createHref, { waitUntil: 'load' }); await sleep(1500);
  await shot('02-builder-from-event-A', false);
  const chip = await page.evaluate(() => { const c = document.getElementById('evChip'); return c ? { hidden: c.hidden, href: c.getAttribute('href'), text: c.textContent } : null; });
  L('builder chip', chip);
  check('builder shows back link to event file A (same tab)', !!chip && !chip.hidden && /^admin\.html#event=/.test(chip.href || '') && new RegExp(A).test(chip.href || ''));
  await page.goto(O + '/' + chip.href, { waitUntil: 'load' }); await sleep(1500);
  check('back link returns to event A, forms tab', (await hash()).includes('event=' + A) && (await hash()).includes('tab=forms') && await waitFor(() => has('[data-ef-forms]')));
  const regA = await mkForm({ name: 'فرم ثبت‌نام الف ' + stamp, model: 'registration', need: 'reg', ev: A, settings: PAID, fields: nameField }); await publish(regA.id, regA.version);
  const regB = await mkForm({ name: 'فرم ثبت‌نام ب ' + stamp, model: 'registration', need: 'reg', ev: Bev, settings: { cap: 5 }, fields: nameField }); await publish(regB.id, regB.version);
  const pub = await mkForm({ name: 'فرم عمومی بی‌رویداد ' + stamp, model: 'registration', need: 'reg', ev: '', settings: {}, fields: nameField });
  const survey = await mkForm({ name: 'نظرسنجی الف ' + stamp, model: 'survey', need: 'survey', ev: '', settings: {}, fields: [{ id: 'rate', t: 'rating', l: 'رضایت کلی', required: true }, { id: 'pick', t: 'choice', l: 'بهترین بخش', opts: ['محتوا', 'مدرس', 'مکان'], required: true }, { id: 'note', t: 'text', l: 'پیشنهاد', required: false }] });
  const quiz = await mkForm({ name: 'آزمون الف ' + stamp, model: 'exam', need: 'exam', ev: '', settings: {}, fields: [{ id: 'q1', t: 'choice', l: 'سیارهٔ سرخ؟', opts: ['مریخ', 'زهره'], required: true }] });
  L('forms', { regA: regA.id, regB: regB.id, pub: pub.id, survey: survey.id, quiz: quiz.id });

  // ── 1) overview: status, capacity/price from the form ──
  await gotoHash('#event=' + A + '&tab=overview');
  check('overview renders head', await waitFor(() => has('[data-ef-head]')));
  const head = await txt('[data-ef-head]'); L('head', head);
  check('head: title + ثبت‌نام باز + cap 3 + price 500,000 + source label', /رویداد الف/.test(head) && /ثبت‌نام باز/.test(head) && /۰ از ۳ نفر/.test(head) && /۵۰۰٬۰۰۰|500,000|۵۰۰,۰۰۰/.test(head.replace(/\u066c/g, '٬')) && /تنظیم‌شده در فرم ثبت‌نام/.test(head));
  check('head buttons: مشاهدهٔ صفحه / ویرایش رویداد / ویرایش تنظیمات ثبت‌نام', /مشاهدهٔ صفحه/.test(head) && /ویرایش رویداد/.test(head) && /ویرایش تنظیمات ثبت‌نام/.test(head));
  check('overview says declared event values are not the source', await has('[data-ef-declared-diff]'));
  check('overview KPI from server counts', /ثبت‌نام: ۰/.test(await txt('[data-ef-kpis]')));
  check('hash kept after load', (await hash()) === '#event=' + A + '&tab=overview');
  await shot('03-A-overview-desktop', true);
  // public page uses the same source
  const pubSnap = await api('/api/public/site-content'); const pubA = (pubSnap.body.content.events || []).find(e => e.id === A);
  check('public projection cap=3 price=500000 from form', !!pubA && pubA.cap === 3 && pubA.price === 500000 && pubA.pricing && pubA.pricing.source === 'form');

  // ── 2) forms tab: only A's forms; link survey + quiz; B/public never shown ──
  await click('[data-ei-tab="forms"]');
  check('forms tab lists reg A only', await waitFor(() => has('[data-ef-form="' + regA.id + '"]')) && !(await has('[data-ef-form="' + regB.id + '"]')) && !(await has('[data-ef-form="' + pub.id + '"]')));
  check('hash switched to tab=forms', (await hash()) === '#event=' + A + '&tab=forms');
  const readOpts = () => page.evaluate(() => [...document.querySelectorAll('[data-ef-link-pick] option')].map(o => o.value));
  await waitFor(async () => (await readOpts()).includes(survey.id));
  const opts = await readOpts(); L('picker options', opts);
  check('link picker offers unlinked survey/quiz/public form, not B’s linked form', opts.includes(survey.id) && opts.includes(quiz.id) && opts.includes(pub.id) && !opts.includes(regB.id) && !opts.includes(regA.id));
  await setVal('[data-ef-link-pick]', survey.id); await sleep(200); await click('[data-ef-link-do]');
  check('survey linked (card appears)', await waitFor(() => has('[data-ef-form="' + survey.id + '"]')));
  await setVal('[data-ef-link-pick]', quiz.id); await sleep(200); await click('[data-ef-link-do]');
  check('quiz linked (card appears)', await waitFor(() => has('[data-ef-form="' + quiz.id + '"]')));
  check('reg form card has no unlink (published) with reason', /قطع اتصال ممکن نیست/.test(await txt('[data-ef-form="' + regA.id + '"]')));
  check('cross-event link rejected by server (B form → A)', (await api('/api/forms/' + regB.id + '/event', { method: 'POST', body: JSON.stringify({ ev: A, expected_version: 2 }) })).status === 409);
  await shot('04-A-forms-linked', true);
  // builder round trip from the form card
  await click('[data-ef-form="' + survey.id + '"] a[href^="create.html?fid="]'); await sleep(1800);
  check('builder opened for the survey with fid', /create\.html\?fid=/.test(page.url()));
  await page.reload({ waitUntil: 'load' }); await sleep(1500);
  const chip2 = await page.evaluate(() => { const c = document.getElementById('evChip'); return c ? { hidden: c.hidden, href: c.getAttribute('href') } : null; });
  check('after refresh in builder, back link still points to A/forms', !!chip2 && !chip2.hidden && new RegExp('event=' + A + '&tab=forms').test(chip2.href || ''));
  await page.goBack({ waitUntil: 'load' }); await sleep(1500);
  check('browser back returns to A/forms', (await hash()).includes('event=' + A) && (await hash()).includes('tab=forms') && await waitFor(() => has('[data-ef-form="' + survey.id + '"]')));

  // ── 3) capacity/price single source: change in the form settings → event file + editor follow ──
  const regNow = (await api('/api/forms/' + regA.id)).body; L('regA version', regNow.version);
  const paused = await api('/api/forms/' + regA.id + '/pause', { method: 'POST', body: JSON.stringify({ expected_version: regNow.version }) });
  const put = await api('/api/forms/' + regA.id, { method: 'PUT', body: JSON.stringify({ name: regNow.name, model: 'registration', need: 'reg', ev: A, fields: nameField, settings: Object.assign({}, PAID, { cap: 4, fin: [{ l: 'ورودی', p: 600000, off: 0, req: true, d: '' }] }), expected_version: paused.body.version }) });
  L('form settings update', put.status);
  const rePub = await api('/api/forms/' + regA.id + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: put.body.version }) });
  L('republish', rePub.status);
  await gotoHash('#event=' + A + '&tab=overview');
  const head2 = await txt('[data-ef-head]'); L('head after form change', head2);
  check('event file follows the form: cap 4, price 600,000', /۰ از ۴ نفر/.test(head2) && /۶۰۰٬۰۰۰|۶۰۰,۰۰۰/.test(head2.replace(/\u066c/g, '٬')));
  const ov = (await api('/api/admin/events/' + A + '/overview')).body;
  check('overview.registration_settings == form settings', ov.registration_settings.cap === 4 && ov.registration_settings.price.base === 600000 && ov.declared.cap === 50);
  await click('[data-ef-head] [data-ei-edit="' + A + '"]');
  check('editor shows capacity/price read-only «تنظیم‌شده در فرم ثبت‌نام»', await waitFor(() => has('[data-ct-form-sourced="cap"]')) && /تنظیم‌شده در فرم ثبت‌نام/.test(await txt('[data-ct-form-sourced="cap"]')) && !(await has('#ctf_cap')));
  await page.evaluate(() => { const d = document.querySelector('details[data-ct-more="extra"]'); if (d) d.open = true; });
  const priceRO = await page.evaluate(() => { const i = document.querySelector('[data-ct-form-sourced="price"] input'); return i ? { value: i.value, ro: i.readOnly } : null; }); L('price field', priceRO);
  check('price field read-only too', !!priceRO && priceRO.ro && /۶۰۰٬۰۰۰|۶۰۰,۰۰۰/.test(priceRO.value.replace(/\u066c/g, '٬')));
  await shot('05-A-editor-form-sourced', true);
  await click('[data-ct-cancel]'); await sleep(500);

  // ── 4) registrations: 3 in A (receipt / no receipt / receipt), 1 in B ──
  const p1 = await visitor(regA.id, 'نفر اول پرونده', { receipt: true });
  const p2 = await visitor(regA.id, 'نفر دوم بی‌رسید', { receipt: false });
  const p3 = await visitor(regA.id, 'نفر سوم ردشدنی', { receipt: true });
  const pB = await visitor(regB.id, 'ثبت‌نام رویداد ب', { pay: false });
  // the public submit returns a tracking code, never the row id; the event file resolves people server-side
  const regsA = (await api('/api/admin/events/' + A + '/registrations?limit=50')).body.items || [];
  const regsB = (await api('/api/admin/events/' + Bev + '/registrations?limit=50')).body.items || [];
  const byName = (rows, n) => (rows.find(r => r.name === n) || {}).response_id;
  const ids = { p1: byName(regsA, 'نفر اول پرونده'), p2: byName(regsA, 'نفر دوم بی‌رسید'), p3: byName(regsA, 'نفر سوم ردشدنی'), pB: byName(regsB, 'ثبت‌نام رویداد ب') };
  L('registrations', ids);
  check('public submit returned tracking codes (no row ids)', !!p1.tracking_code && !p1.response_id && !p1.id);
  const rid = x => x === p1 ? ids.p1 : x === p2 ? ids.p2 : x === p3 ? ids.p3 : ids.pB;
  await gotoHash('#event=' + A + '&tab=regs');
  const rowsOk = await waitFor(async () => (await count('[data-ef-reg]')) === 3, 12000); if (!rowsOk) L('rows count', await count('[data-ef-reg]'));
  check('registrants tab renders rows', rowsOk);
  const sum = await txt('[data-ef-summary]'); L('summary', sum);
  check('summary: total 3, pending 3, remaining 1 of 4', /کل: ۳/.test(sum) && /در انتظار پرداخت: ۳/.test(sum) && /ظرفیت باقی‌مانده: ۱ از ۴/.test(sum));
  check('B’s registrant is not in A', !(await has('[data-ef-reg="' + rid(pB) + '"]')));
  check('row shows «رسید فرستاده شده» separate from payment state', /رسید فرستاده شده/.test(await txt('[data-ef-reg="' + rid(p1) + '"]')) && /در انتظار پرداخت/.test(await txt('[data-ef-reg="' + rid(p1) + '"]')));
  await shot('06-A-registrants', true);
  await click('[data-ef-filter="payment"][data-ef-value="paid"]');
  check('filter paid → empty state with real counts', await waitFor(() => has('[data-ef-regs-empty]')) && /کل: ۳/.test(await txt('[data-ef-summary]')));
  await click('[data-ef-filter="payment"][data-ef-value=""]'); await waitFor(async () => (await count('[data-ef-reg]')) === 3);
  await setVal('[data-ef-q]', 'سوم'); await click('[data-ef-search]');
  const oneOk = await waitFor(async () => (await count('[data-ef-reg]')) === 1, 8000); if (!oneOk) L('rows after search', await count('[data-ef-reg]'));
  check('search narrows to one row', oneOk);
  await setVal('[data-ef-q]', ''); await click('[data-ef-search]'); await waitFor(async () => (await count('[data-ef-reg]')) === 3);

  // ── 5) person file: answers, payment, receipt, decision (approve, idempotent, reject) ──
  await click('[data-ef-person="' + rid(p1) + '"]');
  check('person file opens, hash has reg=', await waitFor(() => has('[data-ef-person-file="' + rid(p1) + '"] [data-ef-decision]')) && (await hash()).includes('reg=' + rid(p1)));
  const pf = await txt('[data-ef-person-file="' + rid(p1) + '"]'); L('person file', pf.slice(0, 300));
  check('person file: answer, payment method, receipt image, no ticket yet', /نفر اول پرونده/.test(pf) && /کارت‌به‌کارت/.test(pf) && await has('[data-ef-receipt-img]') && /بلیت پس از تأیید پرداخت/.test(pf));
  const imgOk = await page.evaluate(() => { const i = document.querySelector('[data-ef-receipt-img]'); return i && i.complete && i.naturalWidth > 0; });
  check('receipt image actually loads from the access-controlled route', imgOk);
  await shot('07-A-person-file', true);
  await page.reload({ waitUntil: 'load' }); await sleep(1800);
  check('refresh keeps the person file open', await waitFor(() => has('[data-ef-person-file="' + rid(p1) + '"] [data-ef-decision]')));
  await click('[data-ef-decide="approve"]'); await sleep(200);
  await click('[data-ef-decide-go]'); await sleep(300);
  check('empty reason blocked', /دلیل لازم است/.test(await txt('[data-ef-person-file] [role="status"]') || ''));
  await setVal('[data-ef-reason]', 'رسید با مبلغ و کارت تطبیق داده شد'); await click('[data-ef-decide-go]');
  check('approved → paid + ticket image link', await waitFor(async () => /تأیید دستی رسید/.test(await txt('[data-ef-person-file="' + rid(p1) + '"]') || '')) && await waitFor(() => has('a[href*="/ticket-image"]')));
  const tk = await page.evaluate(async () => { const a = document.querySelector('a[href*="/ticket-image"]'); const r = await fetch(a.getAttribute('href'), { credentials: 'same-origin' }); return { status: r.status, type: r.headers.get('content-type') }; });
  L('ticket image', tk); check('ticket image served by the existing renderer (image/*)', tk.status === 200 && /^image\//.test(tk.type || ''));
  await shot('08-A-person-approved', true);
  const again = await api('/api/admin/events/' + A + '/registrations/' + rid(p1) + '/payment-decision', { method: 'POST', body: JSON.stringify({ decision: 'approved', reason: 'تکرار' }) });
  check('repeat approve is idempotent (changed:false)', again.status === 200 && again.body.changed === false);
  const noCsrf = await page.evaluate(async ([p]) => { const r = await fetch(p, { method: 'POST', credentials: 'same-origin', body: JSON.stringify({ decision: 'approved', reason: 'x' }) }); return r.status; }, ['/api/admin/events/' + A + '/registrations/' + rid(p3) + '/payment-decision']);
  L('decision without CSRF header', noCsrf);
  check('decision without CSRF blocked', noCsrf === 403 || noCsrf === 415 || noCsrf === 422);
  // reject p3 → cancelled, capacity freed
  await click('[data-ef-person-close]'); await waitFor(async () => (await count('[data-ef-reg]')) === 3);
  await click('[data-ef-person="' + rid(p3) + '"]'); await waitFor(() => has('[data-ef-decision]'));
  await click('[data-ef-decide="reject"]'); await sleep(200); await setVal('[data-ef-reason]', 'رسید ناخوانا است'); await click('[data-ef-decide-go]');
  check('reject → back to list, 2 rows, remaining 2 of 4', await waitFor(async () => (await count('[data-ef-reg]')) === 2) && await waitFor(async () => /ظرفیت باقی‌مانده: ۲ از ۴/.test(await txt('[data-ef-summary]') || '')));
  const sum2 = await txt('[data-ef-summary]'); L('summary after decisions', sum2);
  check('summary: paid 1, pending 1', /پرداخت‌شده: ۱/.test(sum2) && /در انتظار پرداخت: ۱/.test(sum2));
  await shot('09-A-after-decisions', true);
  // cancelled registration kept as a snapshot (identity, answers, payment, receipt) — read only with permission, audited
  check('cancelled section present, closed by default', await has('[data-ef-cancelled]') && !(await has('[data-ef-cancel]')));
  await click('[data-ef-cancel-toggle]');
  check('cancelled list shows p3 with name, reason and payment status before', await waitFor(async () => (await count('[data-ef-cancel]')) === 1) && /نفر سوم ردشدنی/.test(await txt('[data-ef-cancelled]')) && /رسید ناخوانا است/.test(await txt('[data-ef-cancelled]')) && /رسید فرستاده شده/.test(await txt('[data-ef-cancelled]')));
  check('cancelled row: receipt kept + answers collapsible', await has('[data-ef-cancel-receipt]') && /پاسخ‌های فرم/.test(await txt('[data-ef-cancelled]')));
  await click('[data-ef-cancel-receipt]');
  check('kept receipt image loads (200)', await waitFor(() => has('[data-ef-cancel-receipt-img]')) && await page.evaluate(async () => { const i = document.querySelector('[data-ef-cancel-receipt-img]'); const r = await fetch(i.getAttribute('src'), { credentials: 'same-origin' }); return r.status === 200 && /image\//.test(r.headers.get('content-type') || ''); }));
  const cancApi = (await api('/api/admin/events/' + A + '/cancellations')).body; L('cancellations api', { total: cancApi.total, name: cancApi.items && cancApi.items[0] && cancApi.items[0].name, source: cancApi.items && cancApi.items[0] && cancApi.items[0].source });
  check('cancellations API: 1 snapshot, source event_file, amount visible to owner, answers labelled', cancApi.total === 1 && cancApi.items[0].source === 'event_file' && cancApi.items[0].payment && cancApi.items[0].payment.amount === 600000 && Array.isArray(cancApi.items[0].answers) && cancApi.items[0].answers.length > 0);
  check('cancellations of B: none (no cross-event mixing)', (await api('/api/admin/events/' + Bev + '/cancellations')).body.total === 0);
  check('cancelled receipt via B’s event id → 404', (await api('/api/admin/events/' + Bev + '/cancellations/' + cancApi.items[0].id + '/receipt')).status === 404);
  check('live registration row for p3 gone (404)', (await api('/api/admin/events/' + A + '/registrations/' + rid(p3))).status === 404);
  await shot('09b-A-cancelled-kept', true);
  ids.cancellation = cancApi.items[0].id;

  // ── 6) payments tab ──
  await click('[data-ei-tab="payments"]');
  check('payments tab: 3 transactions incl. the rejected one kept', await waitFor(async () => (await count('[data-ef-pay]')) === 3));
  const tot = await txt('[data-ef-pay-totals]'); L('totals', tot);
  check('totals: paid 1 / pending 1 / failed 1 / sum 600,000', /موفق: ۱/.test(tot) && /در انتظار: ۱/.test(tot) && /ناموفق: ۱/.test(tot) && /۶۰۰٬۰۰۰|۶۰۰,۰۰۰/.test(tot.replace(/\u066c/g, '٬')));
  check('rejected payment row says registration cancelled', /ثبت‌نام لغوشده/.test(await txt('[data-ef-payments]')));
  check('rejected payment row keeps the person’s name from the snapshot + «پروندهٔ لغو»', /نفر سوم ردشدنی/.test(await txt('[data-ef-payments]')) && await has('[data-ef-cancel-open]'));
  check('p2 row: «رسیدی ثبت نشده»', /رسیدی ثبت نشده/.test(await txt('[data-ef-payments]')));
  await shot('10-A-payments', true);

  // ── 7) tickets & attendance ──
  await click('[data-ei-tab="tickets"]');
  check('tickets tab: 2 accepted rows', await waitFor(async () => (await count('[data-ef-att-row]')) === 2));
  await click('[data-ef-att-row="' + rid(p1) + '"] [data-ef-att="in"]');
  check('check-in recorded', await waitFor(async () => /حاضر ·/.test(await txt('[data-ef-att-row="' + rid(p1) + '"]') || '')));
  check('summary shows حاضر: ۱', await waitFor(async () => /حاضر: ۱/.test(await txt('[data-ef-tickets]') || '')));
  await shot('11-A-tickets', true);

  // ── 8) survey & quiz aggregate ──
  await publish(survey.id, (await api('/api/forms/' + survey.id)).body.version);
  await surveyAnswer(survey.id, { rate: 5, pick: 'مدرس', note: 'عالی بود' });
  await surveyAnswer(survey.id, { rate: 3, pick: 'مدرس', note: '' });
  await surveyAnswer(survey.id, { rate: 4, pick: 'محتوا', note: 'مکان دور بود' });
  await gotoHash('#event=' + A + '&tab=survey&form=' + survey.id);
  check('survey summary box from direct URL', await waitFor(() => has('[data-ef-summary-box="' + survey.id + '"]')));
  const sb = await txt('[data-ef-summary-box="' + survey.id + '"]'); L('summary box', sb.slice(0, 300));
  check('aggregate: 3 responses, مدرس ۲ / محتوا ۱, mean 4', /۳ پاسخ/.test(sb) && /مدرس\s*۲/.test(sb) && /محتوا\s*۱/.test(sb) && /میانگین ۴/.test(sb));
  check('quiz card says scoring needs a service (no fake score)', /نمره‌دهی آزمون نیازمند کلید پاسخ/.test(await txt('[data-ef-survey]')));
  await shot('12-A-survey-summary', true);

  // ── 9) B isolation + wrong ids ──
  await gotoHash('#event=' + Bev + '&tab=regs');
  check('B registrants: only B’s one row', await waitFor(async () => (await count('[data-ef-reg]')) === 1) && await has('[data-ef-reg="' + rid(pB) + '"]'));
  const cross = await api('/api/admin/events/' + Bev + '/registrations/' + rid(p1));
  check('A’s registration id under B → 404', cross.status === 404);
  const crossSum = await api('/api/admin/events/' + Bev + '/forms/' + survey.id + '/summary');
  check('A’s survey under B → 404', crossSum.status === 404);
  await gotoHash('#event=ev-does-not-exist&tab=overview');
  check('unknown event → Persian error + retry, no crash', await waitFor(async () => /پیدا نشد|حذف شده/.test(await txt('[data-ei-panel]') || '')) && await has('[data-ei-refresh]'));
  await shot('13-unknown-event', false);

  // ── 10) mobile ──
  await page.setViewportSize({ width: 390, height: 844 });
  await gotoHash('#event=' + A + '&tab=overview'); await waitFor(() => has('[data-ef-head]'));
  await shot('14-A-overview-mobile', true);
  await click('[data-ei-tab="regs"]'); await waitFor(async () => (await count('[data-ef-reg]')) === 2);
  await shot('15-A-registrants-mobile', true);
  await click('[data-ef-person="' + rid(p1) + '"]'); await waitFor(() => has('[data-ef-person-file="' + rid(p1) + '"]'));
  await shot('16-A-person-mobile', true);
  check('mobile: no horizontal overflow on person file', await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2));
  await page.setViewportSize({ width: 1280, height: 800 });

  check('no page errors', perrs.length === 0);
  fs.writeFileSync(path.join(out, 'log.txt'), log.join('\n') + '\n');
  fs.writeFileSync(path.join(out, 'ids.json'), JSON.stringify({ A, B: Bev, regA: regA.id, regB: regB.id, survey: survey.id, quiz: quiz.id, p1: rid(p1), p2: rid(p2), p3: rid(p3), pB: rid(pB), cancellation: ids.cancellation || '' }, null, 2));
  await browser.close();
  const fails = log.filter(l => l.startsWith('FAIL')); console.log('\nTOTAL PASS ' + log.filter(l => l.startsWith('PASS')).length + ' / FAIL ' + fails.length);
  process.exit(0);
})().catch(e => { console.error('E2E crashed:', e); fs.writeFileSync(path.join(out, 'log.txt'), log.join('\n') + '\nCRASH ' + e.stack + '\n'); process.exit(1); });
