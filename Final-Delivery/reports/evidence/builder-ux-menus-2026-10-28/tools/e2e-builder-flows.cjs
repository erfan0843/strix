// پذیرش مرورگری — جریان کامل فرم‌ساز برای یک مدیر مجاز (fm_create) از منوی اصلی تا فرم عمومی (۱۴۰۵/۰۸/۰۶).
// منوی اصلی (account.html) → builder.html → create.html؛ جست‌وجوی انتخاب‌گر (مترادف/املای سرهم/یک‌حرف/بی‌نتیجه/تنظیم)؛
// جزئیات بدون افزودن؛ افزودن در ابتدا/انتها/پس از پرسش؛ دوکلیک؛ ویرایشگر داک‌شده (فوکوس، Escape، انصراف، بار انصراف)؛
// سفارشی‌سازی متن/عدد/تک‌انتخاب/چندانتخاب/شرطی؛ خطای اعتبارسنجی؛ ذخیرهٔ سروری و بازگشایی دقیق؛ انتشار؛ فرم عمومی؛ نوع‌های غیرفعال.
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<ui> node e2e-builder-flows.cjs <outdir>
const fs = require('node:fs'), path = require('node:path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const M = process.env.NORA_E2E_MANAGER || 'http://127.0.0.1:8080', O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000', B = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8001';
const out = process.argv[2] || 'shots/builder-flows'; fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms)); const lines = []; let pass = 0, fail = 0;
const L = (m, x) => { const t = m + (x === undefined ? '' : ': ' + (typeof x === 'string' ? x : JSON.stringify(x))); lines.push(t); console.log(t); };
const check = (n, ok, extra) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + n + (extra === undefined || ok ? '' : ' · ' + JSON.stringify(extra).slice(0, 300))); };
const stamp = Date.now().toString(36);
async function api(p, init, base) { const r = await fetch((base || M) + p, Object.assign({ headers: { 'content-type': 'application/json' } }, init || {})); return { status: r.status, body: await r.json().catch(() => null) }; }
(async () => {
  const b = await launchBrowser(); const page = await b.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(e.message)); page.on('dialog', d => d.accept());
  const shot = async (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (e) { } await sleep(150); } return false; };
  const ev = (code, arg) => page.evaluate(code, arg);
  const txt = s => page.$eval(s, el => (el.textContent || '').replace(/\s+/g, ' ').trim()).catch(() => '');
  const state = () => page.$eval('#saveState', el => el.dataset.state).catch(() => '');
  const clickSel = async s => { await page.waitForSelector(s, { timeout: 8000 }); await page.click(s); };
  const typeInto = async (s, v) => { await page.fill(s, v); await page.$eval(s, el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }); };
  const sheetOn = id => page.$eval('#' + id, el => el.classList.contains('on')).catch(() => false);
  const search = async q => { await typeInto('#catSearch', q); await sleep(220); return ev(() => ({ hits: [...document.querySelectorAll('#catList [data-add]')].map(x => x.dataset.add), count: (document.getElementById('catCount') || {}).textContent || '', empty: !!document.querySelector('#catList [data-cat-reset]'), hint: (h => h && !h.hidden ? h.textContent.trim() : '')(document.getElementById('catSettingHint')) })); };
  const openPicker = async (which) => { if (!(await sheetOn('shAdd'))) { await clickSel(which || '#addBottom'); await sleep(250); } };
  const types = () => ev(() => S.fields.map(f => f.t).join(','));
  const active = () => ev(() => { const a = document.activeElement; return a ? (a.id || a.getAttribute('data-edit') || a.getAttribute('data-drag-handle') || a.tagName) : ''; });

  // ── A. مسیر واقعی: منوی اصلی مدیر → مرکز فرم‌ها → ساخت فرم ──
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('about:blank'); await page.goto(M + '/account.html', { waitUntil: 'load' }); await sleep(2200);
  const navTab = await ev(() => { const a = document.querySelector('.tabbar [data-forms-nav]'); return a ? { n: document.querySelectorAll('.tabbar [data-forms-nav]').length, href: a.getAttribute('href'), label: a.textContent.trim() } : null; });
  check('مدیر با fm_create: زبانهٔ «فرم‌ساز» در نوار پایین صفحهٔ حساب (یک‌بار، به builder.html)', !!navTab && navTab.n === 1 && navTab.href === 'builder.html' && navTab.label === 'فرم‌ساز', navTab);
  await shot('01-account-manager-tabbar-1440');
  await ev(() => document.querySelector('.tabbar [data-forms-nav]').click()); await sleep(1500);
  check('کلیک «فرم‌ساز» → builder.html و فهرست فرم‌ها برای مدیر باز می‌شود', /builder\.html/.test(page.url()) && await waitFor(() => ev(() => !!document.querySelector('#fList.on')), 6000), page.url());
  const createHref = await ev(() => { const a = [...document.querySelectorAll('a[href^="create.html"]')].find(x => x.getClientRects().length); return a ? a.getAttribute('href') : ''; });
  check('راه «ساخت فرم» از مرکز فرم‌ها دیده می‌شود', /^create\.html/.test(createHref), createHref);
  await page.goto('about:blank'); await page.goto(M + '/create.html?need=reg', { waitUntil: 'load' }); await sleep(1500);
  check('قرارداد قابلیت‌ها از سرور رسید (ready)', await waitFor(() => ev("FORM_CAPABILITY_STATE==='ready'"), 10000), await ev('FORM_CAPABILITY_STATE'));
  await typeInto('#fTitle', 'جریان فرم‌ساز ' + stamp);
  await ev("go('s2')"); await sleep(300); await ev("applyPack('empty','replace')"); await sleep(400);
  check('بوم خالی؛ انتخاب‌گر برای نخستین پرسش خودش باز شد', (await ev('S.fields.length')) === 0 && await sheetOn('shAdd'));

  // ── B. جست‌وجوی انتخاب‌گر ──
  let r = await search('تلفن'); check('«تلفن» → موبایل (مترادف روزمره)', r.hits[0] === 'mobile' && r.hits.length === 1, r);
  r = await search('توضیحات'); check('«توضیحات» → متن بلند (جمع واژهٔ مترادف)', r.hits[0] === 'area', r);
  r = await search('چندگزینه'); check('«چندگزینه» (املای سرهم) → تک‌انتخاب و چندانتخاب، نه چیز دیگر', r.hits.length === 2 && r.hits.includes('choice') && r.hits.includes('multi'), r);
  r = await search('کدملی'); check('«کدملی» (سرهم) → کد ملی', r.hits[0] === 'nid' && r.hits.length === 1, r);
  r = await search('تاریخ تولد'); check('«تاریخ تولد» → الگوی تاریخ تولد (مشخصات فردی)', r.hits[0] === 'birth-date', r);
  r = await search('امتیاز'); check('«امتیاز» → ستاره در صدر و فقط سنجش‌ها', r.hits[0] === 'rating' && r.hits.every(h => ['rating', 'scale', 'bars'].includes(h)), r);
  r = await search('ا'); check('یک حرف تنها فقط نام‌هایی را می‌آورد که با آن آغاز می‌شوند (نه هر زیررشته‌ای)', r.hits.length > 0 && r.hits.length <= 8, r);
  const oneLetterNames = await ev(() => [...document.querySelectorAll('#catList [data-cat-item]')].map(x => x.querySelector('b,strong,.cat-name') ? x.querySelector('b,strong,.cat-name').textContent.trim() : x.textContent.trim().slice(0, 12)));
  check('نتایج یک‌حرفی همه با «ا» آغاز می‌شوند', oneLetterNames.length > 0 && oneLetterNames.every(n => /^[اآ]/.test(n)), oneLetterNames);
  r = await search('qqzz'); check('عبارت بی‌نتیجه: «پیدا نشد» با دکمهٔ بازنشانی، بدون نتیجهٔ تصادفی', r.hits.length === 0 && r.empty, r);
  await shot('02-picker-empty-1440');
  await ev(() => document.querySelector('#catList [data-cat-reset]').click()); await sleep(250);
  check('بازنشانی، جست‌وجو را پاک و فهرست کامل را برمی‌گرداند', (await ev(() => document.getElementById('catSearch').value)) === '' && (await ev(() => document.querySelectorAll('#catList [data-add]').length)) > 20);
  r = await search('اجباری'); check('نام یک تنظیم («اجباری») راهنمای «این یک تنظیم است، نه نوع» را نشان می‌دهد', !!r.hint, r);
  await typeInto('#catSearch', 'ایمیل'); await sleep(200); await ev(() => document.getElementById('catClear').click()); await sleep(250);
  check('دکمهٔ پاک‌کردن جست‌وجو کار می‌کند و فوکوس در جعبه می‌ماند', (await ev(() => document.getElementById('catSearch').value === '' && document.activeElement === document.getElementById('catSearch'))));

  // ── C. جزئیات بدون افزودن؛ نوع‌های غیرفعال ──
  const before = await ev('S.fields.length');
  await ev(() => document.querySelector('#catList [data-cat-item="email"] [data-cat-info]').click()); await sleep(200);
  const info = await ev(() => { const it = document.querySelector('#catList [data-cat-item="email"]'); const i = it.querySelector('[data-cat-info]'); const d = it.querySelector('.cat-detail'); return { exp: i.getAttribute('aria-expanded'), hidden: d.hidden, text: d.textContent.trim() }; });
  check('«جزئیات» باز می‌شود (aria-expanded) و چیزی اضافه نمی‌کند', info.exp === 'true' && !info.hidden && (await ev('S.fields.length')) === before, info);
  check('جزئیات اطلاعات واقعی دارد: نوع پاسخ، مثال و محدودیت سرور', /پاسخ/.test(info.text) && /مثال/.test(info.text) && /تأیید نمی‌شود|بررسی/.test(info.text), info.text.slice(0, 160));
  await shot('03-picker-detail-email-1440');
  await ev(() => document.querySelector('#catList [data-cat-item="email"] [data-cat-info]').click()); await sleep(150);
  check('کلیک دوباره، جزئیات را می‌بندد', (await ev(() => document.querySelector('#catList [data-cat-item="email"] [data-cat-info]').getAttribute('aria-expanded'))) === 'false');
  const blocked = await ev(() => [...document.querySelectorAll('#catList .cat-main[disabled]')].map(b => { const it = b.closest('[data-cat-item]'); return { k: it.dataset.catItem, reason: (it.querySelector('.hint.warn') || {}).textContent || '', tag: (it.querySelector('.tag.warn') || {}).textContent || '' }; }));
  check('نوع‌های پشتیبانی‌نشده (تصویر/فایل/صدا/امضا/قیمت/کوپن) واقعاً غیرفعال‌اند و دلیل روی کارت است', blocked.length === 6 && blocked.every(x => x.reason.length > 10 && /غیرفعال/.test(x.tag)), blocked.map(x => x.k + ':' + x.reason.slice(0, 30)));
  await page.click('#catList [data-add="image"]', { force: true }).catch(() => { }); await sleep(200);
  check('کلیک روی نوع غیرفعال چیزی اضافه نمی‌کند', (await ev('S.fields.length')) === before);

  // ── D. افزودن: ابتدا/انتها/پس از پرسش؛ دوکلیک ──
  await ev(() => document.querySelector('#catList [data-add="fullname"]').click()); await sleep(400);
  check('افزودن «نام و نام خانوادگی»: ویرایشگر همان پرسش باز شد (داک‌شده روی کارت)', await sheetOn('shField') && (await ev(() => document.querySelector('.block.is-editing #shField.docked') !== null)));
  await clickSel('#fdSave'); await sleep(250);
  check('پس از ذخیره، فوکوس به دکمهٔ «ویرایش» همان پرسش برمی‌گردد', (await active()) === (await ev('String(S.fields[0].id)')), await active());
  await openPicker('#addBottom'); await ev(() => document.querySelector('#catList [data-add="text"]').click()); await sleep(300); await clickSel('#fdSave'); await sleep(200);
  await openPicker('#addTop');
  const noteTop = await txt('#catPositionNote');
  await ev(() => document.querySelector('#catList [data-add="number"]').click()); await sleep(300); await clickSel('#fdSave'); await sleep(200);
  check('«افزودن در ابتدا»: یادداشت جایگاه و درج در ابتدای فهرست', /ابتدای/.test(noteTop) && (await types()) === 'number,fullname,text', { noteTop, types: await types() });
  await ev(() => { const d = document.querySelector('[data-block]:nth-child(2) details.rowmore'); d.open = true; document.querySelector('[data-block]:nth-child(2) [data-add-after]').click(); }); await sleep(300);
  const noteAfter = await txt('#catPositionNote');
  await ev(() => document.querySelector('#catList [data-add="choice"]').click()); await sleep(300);
  const status = await txt('#fieldReorderStatus');
  check('«افزودن پس از پرسش ۲»: یادداشت «پس از پرسش ۲»، درج در جایگاه ۳ و اعلام زنده', /پس از پرسش ۲/.test(noteAfter) && (await types()) === 'number,fullname,choice,text' && /جایگاه ۳ از ۴/.test(status), { noteAfter, status, types: await types() });
  await clickSel('#fdSave'); await sleep(200);
  await openPicker('#addBottom'); const n0 = await ev('S.fields.length');
  await ev(() => { const bt = document.querySelector('#catList [data-add="multi"]'); bt.click(); bt.click(); }); await sleep(500);
  check('دو کلیک پیاپی روی یک ردیف فقط یک پرسش می‌سازد', (await ev('S.fields.length')) === n0 + 1, await types());
  await clickSel('#fdSave'); await sleep(200);
  await openPicker('#addBottom'); await ev(() => document.querySelector('#catList [data-add="area"]').click()); await sleep(300); await clickSel('#fdSave'); await sleep(200);
  check('شش پرسش از دسته‌های مختلف (عدد، فردی، گزینه‌ای، متن، چندانتخاب، متن بلند)', (await types()) === 'number,fullname,choice,text,multi,area', await types());
  await shot('04-canvas-6-1440');

  // ── E. رفتار ویرایشگر ──
  const idText = await ev('String(S.fields[3].id)');
  await page.click('[data-edit="' + idText + '"]'); await sleep(1200);
  check('ویرایشگر روی همان کارت باز شد و سربرگ «پرسش ۴ از ۶» است', (await ev(() => document.querySelector('.block.is-editing').dataset.block)) === idText && /۴ از ۶/.test(await txt('#fdHead')), await txt('#fdHead'));
  await page.click('#fdHelp'); await sleep(150);
  check('کلیک داخل ویرایشگر، کارت دیگری را انتخاب نمی‌کند', (await ev(() => document.querySelector('.block.is-editing').dataset.block)) === idText);
  await page.keyboard.press('Escape'); await sleep(300);
  check('Escape روی ویرایشگر دست‌نخورده: بی‌پرسش بسته می‌شود و فوکوس به «ویرایش» برمی‌گردد', !(await sheetOn('shField')) && (await active()) === idText, await active());
  await page.click('[data-edit="' + idText + '"]'); await sleep(1200); await typeInto('#fdTitle', 'نام مستعار');
  await page.keyboard.press('Escape'); await sleep(250);
  check('Escape با تغییر ذخیره‌نشده: نوار «بستن بدون ذخیره / ادامهٔ ویرایش» و ویرایشگر باز می‌ماند', (await sheetOn('shField')) && !(await page.$eval('#fdDiscardBar', el => el.hidden)));
  await shot('05-editor-discard-bar-1440');
  await clickSel('#fdDiscardNo'); await sleep(150);
  check('«ادامهٔ ویرایش» متن تایپ‌شده را نگه می‌دارد', (await page.$eval('#fdTitle', el => el.value)) === 'نام مستعار' && (await page.$eval('#fdDiscardBar', el => el.hidden)));
  await clickSel('#fdCancel'); await sleep(150); await clickSel('#fdDiscardYes'); await sleep(300);
  check('«انصراف» + تأیید: پرسش به حالت پیش از ویرایش برمی‌گردد (بدون از‌دست‌رفتن دادهٔ قبلی)', !(await sheetOn('shField')) && (await ev('S.fields[3].l')) === 'متن کوتاه', await ev('S.fields[3].l'));
  // جابه‌جایی با صفحه‌کلید و دکمه‌ها
  await page.focus('[data-drag-handle="' + idText + '"]'); await page.keyboard.press('ArrowUp'); await sleep(300);
  check('ArrowUp روی دستگیره، پرسش را یک پله بالا می‌برد و فوکوس روی همان دستگیره می‌ماند', (await types()) === 'number,fullname,text,choice,multi,area' && (await active()) === idText, { types: await types(), active: await active() });
  await ev((id) => { const blk = document.querySelector('[data-block="' + id + '"]'); blk.querySelector('details.rowmore').open = true; blk.querySelector('[data-down]').click(); }, idText); await sleep(300);
  check('دکمهٔ «پایین» در منوی کارت همان پرسش را برمی‌گرداند', (await types()) === 'number,fullname,choice,text,multi,area', await types());

  // ── F. تنظیمات هر نوع ──
  const ids = await ev('S.fields.map(f=>String(f.id))');
  // متن کوتاه: طول
  await page.click('[data-edit="' + ids[3] + '"]'); await sleep(1200);
  check('متن کوتاه: تنظیم طول نمایش داده می‌شود، کران عددی نه', (await page.$eval('#fdLengthBox', el => el.style.display !== 'none')) && (await page.$eval('#fdBoundsBox', el => el.style.display === 'none')));
  await typeInto('#fdTitle', 'نام مستعار'); await typeInto('#fdMinLen', '۲'); await typeInto('#fdMaxLen', '۲۰');
  if (await page.$eval('#fdPlaceholderBox', el => el.style.display !== 'none').catch(() => false)) await typeInto('#fdPlaceholder', 'مثلاً نورا');
  await clickSel('#fdSave'); await sleep(250);
  check('طول ۲..۲۰ (رقم فارسی) روی فیلد ذخیره شد', JSON.stringify(await ev('[S.fields[3].l,S.fields[3].minLen,S.fields[3].maxLen]')) === JSON.stringify(['نام مستعار', 2, 20]), await ev('[S.fields[3].l,S.fields[3].minLen,S.fields[3].maxLen]'));
  // عدد: کران + صحیح
  await page.click('[data-edit="' + ids[0] + '"]'); await sleep(1200);
  await typeInto('#fdTitle', 'سن'); await typeInto('#fdMin', '۱۰'); await typeInto('#fdMax', '۹۰');
  await ev(() => { const s = document.getElementById('fdInteger'); if (s && !s.classList.contains('on')) s.click(); });
  await shot('06-editor-number-1440');
  await clickSel('#fdSave'); await sleep(250);
  check('عدد: کران ۱۰..۹۰ و «فقط عدد صحیح» ذخیره شد', JSON.stringify(await ev('[S.fields[0].min,S.fields[0].max,!!S.fields[0].integer]')) === JSON.stringify([10, 90, true]), await ev('[S.fields[0].min,S.fields[0].max,S.fields[0].integer]'));
  // تک‌انتخاب: گزینه‌ها
  await page.click('[data-edit="' + ids[2] + '"]'); await sleep(1200);
  await typeInto('#fdTitle', 'رنگ');
  await typeInto('#fdOptions [data-optl="0"]', 'قرمز'); await typeInto('#fdOptions [data-optl="1"]', 'آبی');
  await clickSel('#fdAddOption'); await sleep(150);
  check('«افزودن گزینه» ردیف سوم را می‌سازد و فوکوس روی آن است', (await page.$$eval('#fdOptions [data-optl]', xs => xs.length)) === 3 && /optl/.test(await ev(() => JSON.stringify(document.activeElement.dataset))));
  await typeInto('#fdOptions [data-optl="2"]', 'سبز');
  await clickSel('#fdAddOption'); await sleep(100); await typeInto('#fdOptions [data-optl="3"]', 'زرد');
  await ev(() => document.querySelector('#fdOptions [data-optdel="3"]').click()); await sleep(150);
  check('حذف گزینهٔ چهارم، سه گزینه باقی می‌گذارد', (await page.$$eval('#fdOptions [data-optl]', xs => xs.map(x => x.value)).then(v => v.join(','))) === 'قرمز,آبی,سبز');
  await ev(() => document.querySelector('#fdOptions [data-optdown="0"]').click()); await sleep(150);
  await shot('07-editor-options-1440');
  await clickSel('#fdSave'); await sleep(250);
  check('تک‌انتخاب: گزینه‌های ویرایش/جابه‌جا شده ذخیره شدند (آبی، قرمز، سبز)', (await ev('S.fields[2].opts.map(o=>o.l).join(",")')) === 'آبی,قرمز,سبز', await ev('S.fields[2].opts'));
  // چندانتخاب: حد انتخاب + خطای اعتبارسنجی
  await page.click('[data-edit="' + ids[4] + '"]'); await sleep(1200);
  check('چندانتخاب: تنظیم «حداقل/حداکثر انتخاب» نمایش داده می‌شود', await page.$eval('#fdMultiLimitsBox', el => el.style.display !== 'none'));
  await typeInto('#fdTitle', 'علاقه‌مندی‌ها'); await typeInto('#fdOptions [data-optl="0"]', 'کتاب'); await typeInto('#fdOptions [data-optl="1"]', 'فیلم');
  await clickSel('#fdAddOption'); await sleep(100); await typeInto('#fdOptions [data-optl="2"]', 'موسیقی');
  await typeInto('#fdMinSelect', '۱'); await typeInto('#fdMaxSelect', '۵');
  await clickSel('#fdSave'); await sleep(250);
  const inlineErr = await txt('#fdInlineError');
  check('حداکثر انتخاب بیش از شمار گزینه‌ها: ذخیره نمی‌شود، ویرایشگر با داده‌ها باز می‌ماند و خطا کنار کنترل است', (await sheetOn('shField')) && (await page.$eval('#fdTitle', el => el.value)) === 'علاقه‌مندی‌ها' && inlineErr.length > 0 && (await active()) === 'fdMaxSelect', { inlineErr, active: await active() });
  await shot('08-editor-multi-error-1440');
  await typeInto('#fdMaxSelect', '۲'); await clickSel('#fdSave'); await sleep(250);
  check('چندانتخاب: حد ۱..۲ و سه گزینه ذخیره شد', JSON.stringify(await ev('[S.fields[4].minSelect,S.fields[4].maxSelect,S.fields[4].opts.map(o=>o.l)]')) === JSON.stringify([1, 2, ['کتاب', 'فیلم', 'موسیقی']]), await ev('[S.fields[4].minSelect,S.fields[4].maxSelect,S.fields[4].opts]'));
  // متن بلند شرطی
  await page.click('[data-edit="' + ids[5] + '"]'); await sleep(1200);
  await typeInto('#fdTitle', 'چرا؟');
  await clickSel('#fdAddCondition'); await sleep(200);
  await page.selectOption('#fdCondField', ids[2]); await sleep(200); await page.selectOption('#fdCondOp', 'eq'); await sleep(150);
  const valueTag = await page.$eval('[data-cond-value="0"]', el => el.tagName).catch(() => '');
  if (valueTag === 'SELECT') await page.selectOption('[data-cond-value="0"]', 'قرمز'); else await typeInto('[data-cond-value="0"]', 'قرمز');
  await sleep(150);
  const condFieldOpts = await page.$$eval('#fdCondField option', xs => xs.map(x => x.value).filter(Boolean));
  check('پرسش مرجع شرط فقط از پرسش‌های پیشین انتخاب می‌شود (نه خودِ پرسش)', condFieldOpts.includes(ids[2]) && !condFieldOpts.includes(ids[5]), condFieldOpts);
  await ev(() => { const s = document.getElementById('shField'); s.scrollTop = s.scrollHeight; }); await sleep(150);
  await shot('09-editor-conditional-1440');
  await clickSel('#fdSave'); await sleep(250);
  check('شرط «رنگ = قرمز» روی پرسش ذخیره و نشان «شرطی» روی کارت است', (await ev('JSON.stringify(S.fields[5].conditions)')).includes('"value":"قرمز"') && /شرطی/.test(await txt('[data-block="' + ids[5] + '"]')));
  // اجباری با یک کلیک روی کارت
  await ev((id) => document.querySelector('[data-block="' + id + '"] [data-req-toggle]').click(), ids[1]); await sleep(200);
  check('کلید «اجباری» روی کارت با یک کلیک اعمال می‌شود (aria-checked)', (await ev('!!S.fields[1].req')) && (await ev((id) => document.querySelector('[data-block="' + id + '"] [data-req-toggle]').getAttribute('aria-checked'), ids[1])) === 'true');

  // ── G. ذخیرهٔ سروری و بازگشایی دقیق ──
  await ev("go('s4')"); await sleep(300); await page.click('#publish');
  check('ذخیرهٔ پیش‌نویس روی سرور: fid در نشانی و وضعیت «ذخیره شد»', await waitFor(() => /[?&]fid=/.test(page.url()), 8000) && await waitFor(async () => (await state()) === 'saved', 6000), { url: page.url(), state: await state() });
  const fid = (page.url().match(/[?&]fid=([^&]+)/) || [])[1]; L('form id', fid);
  const srv = await api('/api/forms/' + fid);
  const pick = f => ({ t: f.t, l: f.l, req: !!f.req, min: f.min ?? null, max: f.max ?? null, integer: !!f.integer, minLen: f.minLen ?? null, maxLen: f.maxLen ?? null, minSelect: f.minSelect ?? null, maxSelect: f.maxSelect ?? null, opts: (f.opts || []).map(o => o.l), cond: (f.conditions || []).map(c => c.op + ':' + c.value) });
  const remote = srv.body && srv.body.fields.map(pick);
  check('سرور دقیقاً شش فیلد را با طول، کران، صحیح، گزینه‌ها، حد انتخاب و شرط ذخیره کرد', srv.status === 200 && remote.length === 6 && remote[0].min === 10 && remote[0].integer && remote[3].maxLen === 20 && remote[2].opts.join() === 'آبی,قرمز,سبز' && remote[4].maxSelect === 2 && remote[5].cond[0] === 'eq:قرمز' && remote[1].req, remote);
  const v1 = srv.body.version;
  await page.click('#publish'); await waitFor(async () => (await state()) === 'saved', 6000); await sleep(400);
  const again = await api('/api/forms/' + fid);
  check('ذخیرهٔ دوباره بدون تغییر، داده را دست نمی‌زند (فیلدها یکسان؛ فقط یک رکورد فرم)', JSON.stringify(again.body.fields.map(pick)) === JSON.stringify(remote), { v1, now: again.body.version });
  L('note: re-save without changes bumps server version', { v1, now: again.body.version });
  const vNow = again.body.version;
  await page.goto('about:blank'); await page.goto(M + '/create.html?fid=' + fid, { waitUntil: 'load' });
  check('بازگشایی از سرور: وضعیت «ذخیره شد» روی نسخهٔ سرور', await waitFor(async () => (await state()) === 'saved', 8000) && (await ev('ACTIVE_SERVER_FORM&&ACTIVE_SERVER_FORM.version')) === vNow, { vNow, shown: await ev('ACTIVE_SERVER_FORM&&ACTIVE_SERVER_FORM.version') });
  const local = await ev('S.fields.map(f=>({t:f.t,l:f.l,req:!!f.req,min:f.min??null,max:f.max??null,integer:!!f.integer,minLen:f.minLen??null,maxLen:f.maxLen??null,minSelect:f.minSelect??null,maxSelect:f.maxSelect??null,opts:(f.opts||[]).map(o=>o.l),cond:(f.conditions||[]).map(c=>c.op+":"+c.value)}))');
  check('فیلدهای بازگشایی‌شده با رکورد سرور یکی‌اند', JSON.stringify(local) === JSON.stringify(remote), { local: JSON.stringify(local).slice(0, 200) });
  await ev("go('s2')"); await sleep(300);
  await page.click('[data-edit="' + ids[4] + '"]'); await sleep(1200);
  check('ویرایشگر چندانتخاب پس از بازگشایی همان مقادیر را نشان می‌دهد (۱، ۲، سه گزینه)', (await page.$eval('#fdMinSelect', el => el.value.replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))) === '1' && (await page.$eval('#fdMaxSelect', el => el.value.replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))) === '2' && (await page.$$eval('#fdOptions [data-optl]', xs => xs.length)) === 3);
  await clickSel('#fdCancel'); await sleep(200);
  check('انصراف روی ویرایشگر دست‌نخورده، بی‌پرسش بسته می‌شود (بدون «ذخیره‌نشده»ی دروغین)', !(await sheetOn('shField')) && (await page.$eval('#fdDiscardBar', el => el.hidden)) && (await state()) === 'saved', await state());
  // پیش‌نمایش
  await ev("go('s3')"); await sleep(400);
  const previewOk = await ev(() => /نام مستعار/.test(document.body.textContent) && /علاقه‌مندی‌ها/.test(document.body.textContent));
  check('پیش‌نمایش/تنظیمات پس از ذخیره، عنوان‌های سفارشی را نشان می‌دهد', previewOk);
  // موبایل: ورقهٔ ویرایشگر دکمه‌های پایین را نمی‌پوشاند
  await page.setViewportSize({ width: 390, height: 844 }); await ev("go('s2')"); await sleep(400);
  await ev((id) => editField(id), ids[2]); await sleep(1500);
  const mob = await ev(() => { const s = document.getElementById('shField'), save = document.getElementById('fdSave'); const r = save.getBoundingClientRect(); return { docked: s.classList.contains('docked'), modal: s.getAttribute('aria-modal'), saveVisible: r.top >= 0 && r.bottom <= window.innerHeight, saveH: r.height, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }; });
  check('موبایل ۳۹۰: ویرایشگر ورقهٔ پایین است، «ذخیره» در دید و لمسی، بدون سرریز افقی', !mob.docked && mob.modal === 'true' && mob.saveVisible && mob.saveH >= 40 && mob.sw <= mob.cw, mob);
  await shot('10-editor-mobile-390');
  await ev('closeSheets()'); await page.setViewportSize({ width: 1440, height: 900 });

  // ── H. انتشار و فرم عمومی ──
  await ev("go('s4')"); await sleep(600);
  const publishVisible = await page.$eval('#donePublish', el => el.style.display !== 'none' && !el.disabled).catch(() => false);
  check('انتشار برای مدیر (بدون نقش مالک) در فرم‌ساز پیشنهاد نمی‌شود؛ قرارداد سرور: فقط مالک منتشر می‌کند', !publishVisible);
  const pubTry = await api('/api/forms/' + fid + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: (await api('/api/forms/' + fid)).body.version }) });
  check('سرور هم انتشار مدیر را رد می‌کند (401/403) — پنهان‌کردن دکمه جای مجوز سرور نیست', [401, 403].includes(pubTry.status), pubTry.status);
  const pubOwner = await api('/api/forms/' + fid + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: (await api('/api/forms/' + fid)).body.version }) }, O);
  L('publish via owner API', pubOwner.status);
  const published = await api('/api/forms/' + fid);
  check('فرم با نشست مالک منتشر شد', published.body && published.body.status === 'published', { status: published.body && published.body.status, pub: pubOwner.status });
  const pub = await fetch(B + '/api/public/forms/' + fid).then(r => r.json()).catch(() => null);
  const pf = pub && pub.fields || [];
  check('فرم عمومی همان شش فیلد را با تنظیمات واقعی می‌دهد', pf.length === 6 && pf[0].min === 10 && pf[3].maxLen === 20 && pf[4].maxSelect === 2 && (pf[5].conditions || []).length === 1, pf.map(f => f.t));
  await page.goto('about:blank'); await page.goto(B + '/form.html?fid=' + encodeURIComponent(fid) + '&kind=reg', { waitUntil: 'load' }); await sleep(2500);
  const startBtn = await ev(() => { const b = [...document.querySelectorAll('button, a.btn')].find(e => e.offsetParent !== null && /شروع|ادامه/.test(e.textContent) && !/انصراف|بازگشت/.test(e.textContent)); if (b) { b.click(); return b.textContent.trim(); } return ''; }); await sleep(900);
  L('public start', startBtn);
  const reached = await waitFor(() => ev(() => !!document.querySelector('[data-qsel]') || !!document.querySelector('[data-qmul]') || [...document.querySelectorAll('input.input')].some(i => i.offsetParent !== null)), 6000);
  const condHiddenBefore = await ev(() => { const q = [...document.querySelectorAll('textarea, input')].find(e => (e.getAttribute('aria-label') || '').includes('چرا؟')); return !q || q.offsetParent === null; });
  check('فرم عمومی باز شد و پرسش شرطی «چرا؟» پیش از انتخاب «قرمز» پنهان است', reached && condHiddenBefore);
  // پر کردن: سن نامعتبر → خطا؛ چندانتخاب بیش از حد → توست؛ رنگ=قرمز → چرا؟ ظاهر می‌شود
  const fillText = (label, v) => ev(([label, v]) => { const i = [...document.querySelectorAll('input.input, textarea.input, textarea')].find(e => e.offsetParent !== null && (e.getAttribute('aria-label') || '').includes(label)); if (!i) return false; i.focus(); i.value = v; i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new Event('change', { bubbles: true })); i.blur(); return true; }, [label, v]);
  let condShown = false, rangeErr = false, multiToast = false, lenErr = false;
  for (let i = 0; i < 14; i++) {
    const done = await page.evaluate(async fid => { try { const r = await fetch('/api/public/forms/' + fid + '/draft'); const j = await r.json(); return r.status === 200 && j.submitted === true; } catch (e) { return false; } }, fid);
    if (done) break;
    await fillText('سن', rangeErr ? '25' : '5'); await fillText('نام و نام خانوادگی', 'آزمون نورا'); await fillText('نام مستعار', lenErr ? 'نورا' : 'ن');
    const sel = await ev(() => { const g = [...document.querySelectorAll('[data-qsel]')].find(e => e.offsetParent !== null); if (!g) return ''; const o = [...g.querySelectorAll('.opt')].find(x => /قرمز/.test(x.textContent)); if (o && !o.classList.contains('on')) o.click(); return o ? 'قرمز' : ''; });
    if (sel) { await sleep(300); condShown = condShown || await ev(() => { const q = [...document.querySelectorAll('textarea, input')].find(e => (e.getAttribute('aria-label') || '').includes('چرا؟')); return !!q && q.offsetParent !== null; }); }
    if (await fillText('چرا؟', 'چون دوست دارم')) condShown = true;  /* فرم عمومی گام‌به‌گام است؛ پرسش شرطی در گام خودش ظاهر می‌شود */
    const mul = await ev(() => { const g = [...document.querySelectorAll('[data-qmul]')].find(e => e.offsetParent !== null); if (!g) return null; const opts = [...g.querySelectorAll('.opt')]; opts.forEach(o => { if (!o.classList.contains('on')) o.click(); }); return opts.filter(o => o.classList.contains('on')).length; });
    if (mul != null) { await sleep(200); multiToast = multiToast || /حداکثر ۲/.test(await txt('#toast')); if (mul > 2) L('multi selected count', mul); }
    const clicked = await ev(() => { const bs = [...document.querySelectorAll('button:not([disabled]), a.btn')].filter(e => e.offsetParent !== null && /ادامه|ثبت|تأیید|بعدی/.test(e.textContent) && !/انصراف|بازگشت|کپی/.test(e.textContent)); const b = bs.find(x => /ثبت/.test(x.textContent)) || bs[0]; if (b) { b.click(); return b.textContent.trim().slice(0, 20); } return ''; });
    await sleep(900);
    const errs = await ev(() => [...document.querySelectorAll('.field-error')].filter(e => e.offsetParent !== null && e.textContent.trim()).map(e => e.textContent.trim().slice(0, 90)));
    if (errs.some(e => /۱۰|۹۰|بازه|بیشتر|کمتر|حداقل|حداکثر/.test(e) && !/نویسه/.test(e))) rangeErr = true;
    if (errs.some(e => /نویسه|دست‌کم ۲/.test(e))) lenErr = true;
    L('public step ' + i, { clicked, errs, condShown, multiToast });
    if (!clicked) break;
  }
  const draft = await page.evaluate(async fid => { const r = await fetch('/api/public/forms/' + fid + '/draft'); return { status: r.status, body: await r.json() }; }, fid);
  check('فرم عمومی: کران عدد (سن=۵ رد شد) اجرا می‌شود', rangeErr);
  check('فرم عمومی: حداقل طول «نام مستعار» (۱ نویسه رد شد) اجرا می‌شود', lenErr);
  check('فرم عمومی: پرسش شرطی پس از انتخاب «قرمز» ظاهر شد', condShown);
  check('فرم عمومی: انتخاب سومین گزینهٔ چندانتخاب با پیام «حداکثر ۲» جلوگیری شد', multiToast);
  check('ثبت پاسخ عمومی کامل شد (submitted=true)', draft.status === 200 && draft.body && draft.body.submitted === true, draft.body);
  await shot('11-public-done-1440');
  const responses = await api('/api/forms/' + fid + '/responses?limit=20');
  const flat = JSON.stringify(responses.body && responses.body.items || []);
  check('مدیر یک پاسخ با مقادیر درست می‌بیند (۲۵، قرمز، چون دوست دارم)', responses.status === 200 && (responses.body.items || []).length === 1 && /25|۲۵/.test(flat) && flat.includes('قرمز') && flat.includes('چون دوست دارم'), flat.slice(0, 300));
  check('بدون خطای جاوااسکریپت در کل زنجیره', errors.length === 0, errors.slice(0, 3));
  await b.close();
  fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\n');
  console.log('e2e-builder-flows: ' + pass + ' قبول، ' + fail + ' خطا');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\nCRASH ' + (e && e.stack || e) + '\n'); process.exit(1); });
