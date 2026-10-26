// Browser proof for «ساخت از روی این فرم»: owner opens builder.html, uses «بیشتر» → «ساخت نسخهٔ تازه» on the
// published registration form that already has responses, lands in create.html on the new draft; the source form,
// its version and its responses are unchanged. Also proves the lock bar path in create.html. argv: outdir
const fs = require('fs'); const path = require('path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const O = 'http://127.0.0.1:8000', M = 'http://127.0.0.1:8080';
const log = []; let fails = 0;
const ok = (c, m) => { log.push((c ? '✓ ' : '✗ ') + m); if (!c) fails++; console.log((c ? '✓ ' : '✗ ') + m); };
async function j(url) { const r = await fetch(url); return { status: r.status, body: await r.json().catch(() => null) }; }
(async () => {
  const out = process.argv[2]; fs.mkdirSync(out, { recursive: true });
  const forms = (await j(O + '/api/forms')).body.items;
  const source = forms.find(f => f.status === 'published' && f.purpose === 'registration' && Number(f.response_count) > 0);
  ok(!!source, 'فرم منتشرشدهٔ دارای پاسخ در فهرست سرور هست');
  const before = (await j(O + '/api/forms/' + source.id)).body;
  const beforeResponses = (await j(O + '/api/forms/' + source.id + '/responses?limit=50&offset=0')).body.total;
  const countBefore = forms.length;
  const b = await launchBrowser(); const page = await b.newPage(); page.on('dialog', d => d.accept());
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(O + '/builder.html', { waitUntil: 'load' }); await sleep(2500);
  const row = `#formCards [data-form="${source.id}"]`;
  ok(await page.$(row) !== null, 'ردیف فرم مبدأ در فهرست دیده می‌شود');
  await page.evaluate(sel => { document.querySelector(sel + ' details.rowmore').open = true; }, row); await sleep(300);
  await page.screenshot({ path: path.join(out, 'dup-1-menu.png') });
  await page.evaluate(sel => document.querySelector(sel + ' [data-duplicate-form]').click(), row); await sleep(500);
  ok(await page.evaluate(() => document.getElementById('shDuplicate').classList.contains('on')), 'برگهٔ تأیید «ساخت نسخهٔ تازه» باز شد');
  const suggested = await page.evaluate(() => document.getElementById('dupName').value);
  ok(suggested.startsWith('نسخهٔ جدید از'), 'نام پیشنهادی از نام فرم مبدأ ساخته شد: ' + suggested);
  await page.fill('#dupName', 'ثبت‌نام دورهٔ بعد (آزمون مرورگر)');
  await page.screenshot({ path: path.join(out, 'dup-2-sheet.png') });
  await page.click('#dupGo'); await sleep(3500);
  const url = page.url();
  ok(/create\.html\?fid=/.test(url), 'پس از ساخت، فرم‌ساز روی نسخهٔ تازه باز شد: ' + url.replace(O, ''));
  const newId = decodeURIComponent((url.match(/fid=([^&]+)/) || [])[1] || '');
  ok(!!newId && newId !== source.id, 'شناسهٔ نسخهٔ تازه با مبدأ فرق دارد');
  await sleep(2000);
  await page.screenshot({ path: path.join(out, 'dup-3-create-new-draft.png') });
  const title = await page.evaluate(() => (document.getElementById('fTitle') || {}).value || '');
  ok(title === 'ثبت‌نام دورهٔ بعد (آزمون مرورگر)', 'عنوان نسخهٔ تازه در فرم‌ساز همان نام واردشده است: ' + title);
  const lockHidden = await page.evaluate(() => document.getElementById('lockBar').hidden);
  ok(lockHidden, 'نسخهٔ تازه قفل نیست (پیش‌نویس بدون پاسخ)');
  const copy = (await j(O + '/api/forms/' + newId)).body;
  ok(copy.status === 'draft' && copy.version === 1, 'نسخهٔ تازه در سرور: پیش‌نویس، نسخهٔ ۱');
  ok(copy.settings.source_form_id === source.id, 'settings.source_form_id به مبدأ اشاره می‌کند');
  ok(JSON.stringify(copy.fields.map(f => [f.id, f.t, f.l])) === JSON.stringify(before.fields.map(f => [f.id, f.t, f.l])), 'پرسش‌ها (شناسه، نوع، برچسب) با همان ترتیب کپی شدند');
  ok((await j(O + '/api/forms/' + newId + '/responses?limit=50&offset=0')).body.total === 0, 'نسخهٔ تازه هیچ پاسخی ندارد');
  ok((await j('http://127.0.0.1:8001/api/public/forms/' + newId)).status === 404, 'نسخهٔ تازه منتشر نیست (صفحهٔ عمومی ۴۰۴)');
  const after = (await j(O + '/api/forms/' + source.id)).body;
  ok(after.status === 'published' && after.version === before.version, 'فرم مبدأ همچنان منتشر و هم‌نسخه است');
  ok((await j(O + '/api/forms/' + source.id + '/responses?limit=50&offset=0')).body.total === beforeResponses, 'پاسخ‌های مبدأ دست نخورده‌اند (' + beforeResponses + ')');
  ok((await j(O + '/api/forms')).body.items.length === countBefore + 1, 'دقیقاً یک فرم به فهرست اضافه شد');

  // Lock bar path from create.html on the (immutable) source form.
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + encodeURIComponent(source.id), { waitUntil: 'load' }); await sleep(3000);
  ok(await page.evaluate(() => !document.getElementById('lockBar').hidden), 'نوار قفل روی فرم منتشرشدهٔ دارای پاسخ دیده می‌شود');
  ok(await page.evaluate(() => !document.getElementById('lockDuplicate').disabled), 'دکمهٔ «ساخت نسخهٔ تازه» در نوار قفل فعال است');
  await page.click('#lockDuplicate'); await sleep(400);
  ok(await page.evaluate(() => document.getElementById('shDuplicate').classList.contains('on')), 'برگهٔ تأیید از فرم‌ساز هم باز می‌شود');
  await page.screenshot({ path: path.join(out, 'dup-4-create-lockbar-sheet.png') });
  await page.evaluate(() => document.querySelector('#shDuplicate [data-close]').click()); await sleep(200);
  ok(await page.evaluate(() => !document.getElementById('shDuplicate').classList.contains('on')), 'انصراف، برگه را بدون ساخت فرم می‌بندد');
  ok((await j(O + '/api/forms')).body.items.length === countBefore + 1, 'انصراف فرمی نساخت');

  // Manager (fm_create, no finance) via the second proxy: copying a free registration form is allowed; publishing stays owner-only.
  await page.goto('about:blank'); await page.goto(M + '/builder.html', { waitUntil: 'load' }); await sleep(2500);
  ok(await page.$(row) !== null, 'مدیر هم فهرست سرور را می‌بیند');
  await page.evaluate(sel => document.querySelector(sel + ' [data-duplicate-form]').click(), row); await sleep(400);
  await page.fill('#dupName', 'نسخهٔ مدیر (آزمون مرورگر)'); await page.click('#dupGo'); await sleep(3500);
  const mgrUrl = page.url(); const mgrId = decodeURIComponent((mgrUrl.match(/fid=([^&]+)/) || [])[1] || '');
  ok(/create\.html\?fid=/.test(mgrUrl) && mgrId && mgrId !== newId, 'مدیر نسخهٔ تازهٔ خودش را ساخت و در فرم‌ساز باز شد');
  await sleep(1500);
  const pubBtn = await page.evaluate(() => { const b = document.getElementById('donePublish'); return b ? getComputedStyle(b).display : 'absent'; });
  ok(pubBtn === 'none' || pubBtn === 'absent', 'دکمهٔ انتشار برای مدیر نمایش داده نمی‌شود (انتشار فقط مالک)');
  const pubTry = await fetch(M + '/api/forms/' + mgrId + '/publish', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ expected_version: 1 }) });
  ok([401, 403].includes(pubTry.status), 'انتشار نسخهٔ مدیر از API با ' + pubTry.status + ' رد شد');
  await page.screenshot({ path: path.join(out, 'dup-5-manager-copy.png') });
  await b.close();
  fs.writeFileSync(path.join(out, 'log.txt'), log.join('\n') + '\n');
  console.log('e2e-duplicate: ' + (log.length - fails) + ' قبول، ' + fails + ' خطا');
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error('CRASH', e); process.exit(1); });
