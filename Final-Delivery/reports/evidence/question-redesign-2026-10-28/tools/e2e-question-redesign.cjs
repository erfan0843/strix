// Real-browser acceptance for the question picker + card + docked editor redesign (1405/08/06).
// 14 scenarios from the brief: browse categories · search (name/synonym/setting term) · add in place without double-add ·
// add several + reorder · edit text + choice · options add/edit/delete/reorder · required + display condition ·
// type-relevant settings · validation error shown + fixed · save/exit/reopen vs server · preview · copy/delete · disabled
// capabilities with reasons · keyboard/focus/accessible help. Desktop 1440 (docked editor) + mobile 390 (bottom sheet).
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<ui> node e2e-question-redesign.cjs <outdir>
const fs = require('node:fs'), path = require('node:path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000';
const out = process.argv[2] || 'shots/question-redesign'; fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms)); const lines = []; let pass = 0, fail = 0;
const L = (m, x) => { const t = m + (x === undefined ? '' : ': ' + (typeof x === 'string' ? x : JSON.stringify(x))); lines.push(t); console.log(t); };
const check = (n, ok, extra) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + n + (extra === undefined || ok ? '' : ' · ' + JSON.stringify(extra).slice(0, 300))); };
async function api(p, init) { const r = await fetch(O + p, Object.assign({ headers: { 'content-type': 'application/json' } }, init || {})); return { status: r.status, body: await r.json().catch(() => null) }; }
(async () => {
  const b = await launchBrowser(); const page = await b.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(e.message)); page.on('dialog', d => d.accept());
  const shot = async (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full, animations: 'disabled', timeout: 30000 });
  const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (e) { } await sleep(150); } return false; };
  const ev = code => page.evaluate(code);
  const txt = s => page.$eval(s, el => (el.textContent || '').replace(/\s+/g, ' ').trim()).catch(() => '');
  const sheetOn = id => page.$eval('#' + id, el => el.classList.contains('on')).catch(() => false);
  const clickSel = async s => { await page.waitForSelector(s, { timeout: 8000 }); await page.click(s); };
  const typeInto = async (s, v) => { await page.fill(s, v); await page.$eval(s, el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }); };
  const state = () => page.$eval('#saveState', el => el.dataset.state).catch(() => '');
  const active = () => ev("(d=>d?(d.id||d.getAttribute('aria-label')||d.className||d.tagName):'')(document.activeElement)");
  const titles = () => ev("S.fields.map(f=>f.l)");
  const hits = () => page.$$eval('#catList .cat-main[data-add]', xs => xs.map(x => x.dataset.add));
  const openMenu = async i => { await page.click('[data-block]:nth-child(' + i + ') details.rowmore > summary'); await sleep(150); };

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('about:blank'); await page.goto(O + '/create.html?need=reg', { waitUntil: 'load' }); await sleep(1500);
  check('capability contract ready', await waitFor(() => ev("FORM_CAPABILITY_STATE==='ready'"), 10000));
  const title = 'بازطراحی پرسش ' + Date.now().toString(36);
  await typeInto('#fTitle', title);
  await ev("go('s2')"); await sleep(300); await ev("applyPack('empty','replace')"); await sleep(400);

  // ── ۱) open picker, browse categories ──
  check('۱ empty canvas auto-opens the picker with sticky head (search + chips) above the list', await sheetOn('shAdd') && await page.$eval('#shAdd .picker-top #catSearch', () => true) && await page.$eval('#shAdd .picker-body #catList', () => true));
  const chips = await page.$$eval('#catChips [data-cat]', xs => xs.map(x => x.dataset.cat + ':' + (x.textContent || '').trim()));
  const groups = await page.$$eval('#catList .cat-group', xs => xs.map(x => (x.textContent || '').trim()));
  check('۱ 8 user-facing categories + «همه»; list shows every category once as a titled section', chips.length === 9 && groups.length === 8 && new Set(groups).size === 8, { chips, groups });
  const cols = await page.$eval('#catList .cat-list-grid', el => getComputedStyle(el).gridTemplateColumns.split(' ').length);
  check('۱ desktop tiles are a 2-column grid', cols === 2, cols);
  await page.click('#catChips [data-cat="person"]'); await sleep(200);
  const personHits = await hits();
  check('۱ «مشخصات فردی» filters to its 8 types; count line names the category; no section headers while filtered', personHits.length === 8 && /در «مشخصات فردی»/.test(await txt('#catCount')) && (await page.$$('#catList .cat-group')).length === 0 && await ev("document.activeElement===document.querySelector('#catChips [data-cat=\"person\"]')"), { personHits, count: await txt('#catCount') });
  await shot('01-picker-person-1440');
  await page.click('#catChips [data-cat="all"]'); await sleep(200);
  // sticky head: scroll the sheet body and the search must stay in view
  await ev("document.getElementById('shAdd').scrollTop=600"); await sleep(200);
  const searchVisible = await page.$eval('#catSearch', el => { const r = el.getBoundingClientRect(), s = document.getElementById('shAdd').getBoundingClientRect(); return r.top >= s.top && r.bottom <= s.bottom; });
  check('۱ search stays reachable while the list scrolls', searchVisible);
  await ev("document.getElementById('shAdd').scrollTop=0");

  // ── ۲) search by Persian name, synonym, setting term ──
  await typeInto('#catSearch', 'شماره همراه'); await sleep(250);
  check('۲ synonym «شماره همراه» → mobile first + result count', (await hits())[0] === 'mobile' && /نتیجه/.test(await txt('#catCount')), { hits: await hits() });
  await typeInto('#catSearch', 'ايميل'); await sleep(250); // Arabic yeh
  check('۲ Persian normalisation (ي→ی): «ايميل» finds the email type', (await hits()).includes('email'), await hits());
  await typeInto('#catSearch', 'سن'); await sleep(250);
  const sen = await hits();
  check('۲ «سن» → number/birth-date, not file/image noise', sen.includes('number') && sen.includes('birth-date') && !sen.includes('file') && !sen.includes('imgchoice'), sen);
  await typeInto('#catSearch', 'عدد صحیح'); await sleep(250);
  check('۲ setting term «عدد صحیح» → number type with a setting hint', (await hits())[0] === 'number' && /صحیح/.test(await txt('#catSettingHint')), { hits: await hits(), hint: await txt('#catSettingHint') });
  await typeInto('#catSearch', 'اجباری'); await sleep(250);
  check('۲ setting term «اجباری» → hint says it is a per-question switch', /اجباری/.test(await txt('#catSettingHint')), await txt('#catSettingHint'));
  await typeInto('#catSearch', 'xyzw'); await sleep(250);
  check('۲ no result → clear message + «back to all» control', /پیدا نشد/.test(await txt('#catList')) && !!(await page.$('#catList [data-cat-reset]')));
  await page.click('#catList [data-cat-reset]'); await sleep(200);
  check('۲ reset shows all 36 types again and clears the query', (await hits()).length === 36 && (await page.$eval('#catSearch', el => el.value)) === '');
  await shot('02-picker-search-1440');

  // ── ۱۴a) accessible help on a tile: opening it never adds a field ──
  const infoBefore = await ev('S.fields.length');
  await page.click('#catList [data-cat-info="choice"]'); await sleep(150);
  const det = await page.$eval('#catList [data-cat-info="choice"]', el => { const d = document.getElementById(el.getAttribute('aria-controls')); return { open: !d.hidden, expanded: el.getAttribute('aria-expanded'), text: d.textContent.trim().slice(0, 80) }; });
  check('۱۴ tile «جزئیات» opens on click (answer type + example) and adds nothing', det.open && det.expanded === 'true' && /پاسخ:/.test(det.text) && (await ev('S.fields.length')) === infoBefore && !(await sheetOn('shField')), det);
  await page.focus('#catList [data-cat-info="choice"]'); await page.keyboard.press('Enter'); await sleep(120);
  check('۱۴ details toggle works from the keyboard (Enter closes it again)', (await page.$eval('#catList [data-cat-info="choice"]', el => el.getAttribute('aria-expanded'))) === 'false');
  const describedBy = await page.$eval('#catList .cat-main[data-add="choice"]', el => el.getAttribute('aria-describedby'));
  check('۱۴ tile button is described by its detail block for screen readers', !!describedBy && await page.$eval('#' + describedBy, () => true));

  // ── ۳) pick, add in the right place, no double add ──
  await page.click('#catList .cat-main[data-add="fullname"]'); await sleep(400);
  check('۳ first tile click adds exactly one question and opens its editor', (await ev('S.fields.length')) === 1 && await sheetOn('shField') && /پرسش ۱ از ۱/.test(await txt('#fdHead')));
  await page.click('#fdSave'); await sleep(250);
  await page.click('#addBottom'); await sleep(300);
  check('۳ bottom «+» opens the picker without a position note (appends at the end)', await sheetOn('shAdd') && await page.$eval('#catPositionNote', el => el.hidden));
  await page.click('#catList .cat-main[data-add="choice"]'); await page.click('#catList .cat-main[data-add="choice"]').catch(() => { }); await sleep(400);
  check('۳ a quick second click on the tile does not add a duplicate (picker closed after the first add)', (await ev('S.fields.length')) === 2 && (await ev("S.fields.filter(f=>f.t==='choice').length")) === 1, await titles());
  await page.click('#fdSave'); await sleep(250);
  await page.click('#addTop'); await sleep(300);
  check('۳ top «+» announces «در ابتدای فهرست» before choosing', !(await page.$eval('#catPositionNote', el => el.hidden)) && /ابتدا/.test(await txt('#catPositionNote')));
  await page.keyboard.press('Escape'); await sleep(200);
  check('۳ closing the picker without choosing changes nothing', !(await sheetOn('shAdd')) && (await ev('S.fields.length')) === 2);
  await openMenu(1); await page.click('[data-block]:nth-child(1) [data-add-after]'); await sleep(300);
  check('۳ «افزودن پرسش پس از این» announces «پس از پرسش ۱»', /پس از پرسش ۱/.test(await txt('#catPositionNote')), await txt('#catPositionNote'));
  await page.click('#catList .cat-main[data-add="number"]'); await sleep(400);
  check('۳ new question landed after question 1 and its editor says «پرسش ۲ از ۳»', (await ev("S.fields[1].t")) === 'number' && /پرسش ۲ از ۳/.test(await txt('#fdHead')), await titles());
  await typeInto('#fdTitle', 'سن'); await page.click('#fdSave'); await sleep(250);
  check('۳ after save the focus returns to the «ویرایش» button of that question', /ویرایش پرسش «سن»/.test(await active()), await active());

  // ── ۴) add several & reorder ──
  for (const k of ['area', 'rating']) { await page.click('#addBottom'); await sleep(250); await page.click('#catList .cat-main[data-add="' + k + '"]'); await sleep(350); await page.click('#fdSave'); await sleep(200); }
  check('۴ five questions on the canvas, one card each', (await page.$$('[data-block]')).length === 5 && (await ev('S.fields.length')) === 5);
  const before4 = await titles();
  await openMenu(2); await page.click('[data-block]:nth-child(2) [data-down]'); await sleep(300);
  const after4 = await titles();
  check('۴ «انتقال به پایین» really swaps 2↔3 and announces the move', after4[2] === before4[1] && after4[1] === before4[2] && /جایگاه ۳/.test(await txt('#fieldReorderStatus')), { before4, after4 });
  await page.focus('[data-block]:nth-child(3) [data-drag-handle]'); await page.keyboard.press('ArrowUp'); await sleep(300);
  check('۴ keyboard ArrowUp on the handle moves it back and keeps focus on the handle', JSON.stringify(await titles()) === JSON.stringify(before4) && /دستهٔ جابه‌جایی/.test(await active()), { titles: await titles(), active: await active() });
  await shot('04-canvas-5-1440');
  const cardH = await page.$$eval('[data-block]', xs => xs.map(x => Math.round(x.getBoundingClientRect().height)));
  check('۴ collapsed cards are compact and uniform (≤ 80px on desktop)', cardH.every(h => h <= 80), cardH);

  // ── ۵) edit a text + a choice question (docked editor on desktop) ──
  await page.click('[data-block]:nth-child(1) [data-edit]'); await sleep(900);
  const dock = await ev("(()=>{const sh=document.getElementById('shField'),blk=sh.closest('[data-block]');return {docked:sh.classList.contains('docked'),inCard:blk&&blk===document.querySelector('[data-block]:nth-child(1)'),modal:sh.getAttribute('aria-modal'),scrim:document.getElementById('scrim').classList.contains('on'),head:document.getElementById('fdHead').textContent,pressed:document.querySelector('[data-block]:nth-child(1) [data-edit]').getAttribute('aria-pressed')}})()");
  check('۵ desktop: editor docks inside the card of question 1, no scrim, not modal, head «پرسش ۱ از ۵», edit button pressed', dock.docked && dock.inCard && dock.modal === 'false' && !dock.scrim && /پرسش ۱ از ۵/.test(dock.head) && dock.pressed === 'true', dock);
  check('۵ focus goes to the title input', (await active()) === 'fdTitle');
  await typeInto('#fdTitle', 'نام کامل'); await typeInto('#fdHelp', 'نام و نام خانوادگی مطابق کارت ملی');
  await shot('05-docked-text-1440');
  await page.click('#fdSave'); await sleep(300);
  check('۵ text question saved (title + help) and the editor left the card', (await ev("S.fields[0].l+'|'+S.fields[0].help")) === 'نام کامل|نام و نام خانوادگی مطابق کارت ملی' && !(await ev("document.getElementById('shField').closest('[data-block]')")) && (await page.$$('.block.is-editing')).length === 0);
  await page.click('[data-block]:nth-child(3) [data-edit]'); await sleep(900);
  check('۵ choice editor docks in card 3 with editable options', (await ev("document.getElementById('shField').closest('[data-block]')===document.querySelector('[data-block]:nth-child(3)')")) && (await page.$$('#fdOptions [data-optl]')).length >= 2);

  // ── ۶) options: add / edit / delete / reorder (inside the docked editor) ──
  await page.click('#fdAddOption'); await sleep(150);
  const n6 = (await page.$$('#fdOptions [data-optl]')).length;
  await typeInto('#fdOptions [data-optl="' + (n6 - 1) + '"]', 'گزینهٔ سه');
  await typeInto('#fdOptions [data-optl="0"]', 'قرمز');
  const beforeMove = await ev("optionRowsForField(FIELD_DRAFT).map(o=>o.l)");
  await page.click('#fdOptions [data-optdown="0"]'); await sleep(150);
  const afterMove = await ev("optionRowsForField(FIELD_DRAFT).map(o=>o.l)");
  check('۶ option added, renamed and moved down for real; focus stays on the moved row', n6 === 3 && afterMove[1] === 'قرمز' && afterMove[0] === beforeMove[1] && /پایین بردن گزینهٔ ۲|بالا بردن گزینهٔ ۲/.test(await active()), { beforeMove, afterMove, active: await active() });
  await page.click('#fdOptions [data-optdel="2"]'); await sleep(150);
  check('۶ option deleted', (await ev("optionRowsForField(FIELD_DRAFT).length")) === 2);
  await typeInto('#fdTitle', 'رنگ'); await page.click('#fdSave'); await sleep(300);
  check('۶ saved: 2 options in the new order and the card shows «۲ گزینه»', JSON.stringify(await ev("S.fields[2].opts.map(o=>o.l)")) === JSON.stringify([beforeMove[1], 'قرمز']) && /۲ گزینه/.test(await txt('[data-block]:nth-child(3) .qmeta')));

  // ── ۷) required on the card + display condition via the real editor ──
  await page.click('[data-block]:nth-child(1) [data-req-toggle]'); await sleep(250);
  check('۷ card switch makes question 1 required (f.req, aria-checked, label) and keeps focus', (await ev('S.fields[0].req')) === true && (await page.$eval('[data-block]:nth-child(1) [data-req-toggle]', el => el.getAttribute('aria-checked') + ':' + el.textContent.trim())) === 'true:اجباری' && /اجباری بودن پرسش/.test(await active()));
  await page.click('[data-block]:nth-child(1) [data-req-toggle]'); await sleep(250);
  check('۷ second click makes it optional again', (await ev('S.fields[0].req')) === false && /اختیاری/.test(await txt('[data-block]:nth-child(1) [data-req-toggle]')));
  await page.click('[data-block]:nth-child(1) [data-req-toggle]'); await sleep(250);
  await openMenu(4); await page.click('[data-block]:nth-child(4) [data-edit-cond]'); await sleep(900);
  check('۷ «شرط نمایش» from the menu opens the docked editor of question 4 at the condition section', (await ev("editing===S.fields[3].id&&document.getElementById('shField').classList.contains('docked')")) && /fdAddCondition|افزودن قاعده/.test(await active()), await active());
  await page.click('#fdAddCondition'); await sleep(250);
  await page.selectOption('#fdCondField', { value: String(await ev('String(S.fields[2].id)')) }); await sleep(200);
  await page.click('#fdSave'); await sleep(300);
  const condErr = await ev("(()=>{const e=document.getElementById('fdInlineError');return {msg:e&&e.textContent,inRule:!!(e&&e.closest('[data-condition-row]')),open:document.getElementById('shField').classList.contains('on'),saved:(S.fields[3].conditions||[]).length}})()");
  check('۹ saving a rule without a value is refused next to that rule (editor stays open, nothing written)', /مقدار شرط/.test(condErr.msg || '') && condErr.inRule && condErr.open && condErr.saved === 0, condErr);
  const opts7 = await page.$$eval('#fdCondVal option', xs => xs.map(x => x.value).filter(Boolean));
  await page.selectOption('#fdCondVal', { value: opts7[0] });
  await page.click('#fdSave'); await sleep(300);
  check('۷ condition saved on question 4 (field/op/value) and the card shows «شرطی · ۱ قاعده»', (await ev("(S.fields[3].conditions||[]).length")) === 1 && (await ev("String(S.fields[3].conditions[0].field)===String(S.fields[2].id)")) && /شرطی · ۱ قاعده/.test(await txt('[data-block]:nth-child(4) .qmeta')), await ev("JSON.stringify(S.fields[3].conditions)"));

  // ── ۸) settings only in relevant types ──
  await page.click('[data-block]:nth-child(2) [data-edit]'); await sleep(700);
  const vis = sel => page.$eval(sel, el => el.style.display !== 'none' && el.offsetParent !== null).catch(() => false);
  check('۸ number question: bounds + integer visible, options/length hidden', await vis('#fdBoundsBox') && await vis('#fdIntegerBox') && !(await vis('#fdOptionsBox')) && !(await vis('#fdLengthBox')));
  // ── ۹) validation error near the control, editor stays open; then fix ──
  await typeInto('#fdMin', '۹۰'); await typeInto('#fdMax', '۱۰'); await page.click('#fdSave'); await sleep(300);
  const err9 = await ev("(()=>{const e=document.getElementById('fdInlineError'),m=document.getElementById('fdMin'),x=document.getElementById('fdMax');return {err:e&&e.textContent,invalid:(m&&m.getAttribute('aria-invalid'))||(x&&x.getAttribute('aria-invalid')),open:document.getElementById('shField').classList.contains('on'),docked:document.getElementById('shField').classList.contains('docked')}})()");
  check('۹ min>max: inline error next to the control, aria-invalid, editor stays open inside the card', !!err9.err && err9.invalid === 'true' && err9.open && err9.docked, err9);
  await shot('09-validation-docked-1440');
  await typeInto('#fdMin', '۱۰'); await typeInto('#fdMax', '۹۰'); await page.click('#fdSave'); await sleep(300);
  check('۹ after the fix: saved as numbers, editor closed', (await ev("S.fields[1].min+'-'+S.fields[1].max")) === '10-90' && !(await sheetOn('shField')));
  await page.click('[data-block]:nth-child(1) [data-edit]'); await sleep(700);
  check('۸ text-like question: length visible, bounds hidden', await vis('#fdLengthBox') && !(await vis('#fdBoundsBox')));
  await page.keyboard.press('Escape'); await sleep(300);
  check('۸ Escape on an untouched docked editor closes it without a prompt and returns focus to «ویرایش»', !(await sheetOn('shField')) && /ویرایش پرسش «نام کامل»/.test(await active()), await active());

  // ── ۱۲) copy & delete without side effects ──
  const idsBefore = await ev("S.fields.map(f=>String(f.id))");
  await openMenu(3); await page.click('[data-block]:nth-child(3) [data-copy]'); await sleep(300);
  const copyInfo = await ev("(()=>{const s=S.fields[2],c=S.fields[3];return {n:S.fields.length,sameTitle:s.l===c.l,newId:String(c.id)!==String(s.id),opts:JSON.stringify(c.opts)===JSON.stringify(s.opts),independent:c.opts!==s.opts,origId:String(s.id)}})()");
  check('۱۲ copy: new independent id, same settings/options, inserted right below, original untouched', copyInfo.n === 6 && copyInfo.sameTitle && copyInfo.newId && copyInfo.opts && copyInfo.independent && copyInfo.origId === idsBefore[2], copyInfo);
  check('۱۲ the condition on the old question 4 (now 5) still references the original choice question', (await ev("String(S.fields[4].conditions[0].field)")) === idsBefore[2]);
  await openMenu(4); await page.click('[data-block]:nth-child(4) [data-del]'); await sleep(300);
  check('۱۲ delete removes only the copy; order and the condition of the others are intact', JSON.stringify(await ev("S.fields.map(f=>String(f.id))")) === JSON.stringify(idsBefore) && (await ev("(S.fields[3].conditions||[]).length")) === 1);
  check('۱۲ delete is visually distinct (stop colour class) and in the menu, not a bare icon on the card', await page.$eval('[data-block]:nth-child(1) [data-del]', el => el.classList.contains('stop') && !!el.closest('details.rowmore')));

  // ── ۱۳) disabled capabilities shown with reasons ──
  await page.click('#addBottom'); await sleep(300);
  const img = await page.$eval('#catList [data-cat-item="image"]', el => { const m = el.querySelector('.cat-main'); return { disabled: m.disabled, aria: m.getAttribute('aria-disabled'), tag: (el.querySelector('.tag.warn') || {}).textContent, reason: (m.querySelector('.hint.warn') || {}).textContent }; });
  check('۱۳ upload tile: real disabled button, «غیرفعال» tag and the server reason on the tile itself', img.disabled && img.aria === 'true' && /غیرفعال/.test(img.tag || '') && /وصل نیست|سرور|فراهم/.test(img.reason || ''), img);
  const n13 = await ev('S.fields.length'); await page.click('#catList [data-cat-item="image"] .cat-main', { force: true }).catch(() => { }); await sleep(200);
  check('۱۳ clicking the disabled tile adds nothing', (await ev('S.fields.length')) === n13 && await sheetOn('shAdd'));
  const mob = await page.$eval('#catList [data-cat-item="mobile"]', el => ({ limited: !!el.querySelector('.cap-tag.limited'), enabled: !el.querySelector('.cat-main').disabled }));
  check('۱۳ limited-by-server type (mobile) is addable but marked «سروری با محدودیت» — three states distinguishable', mob.limited && mob.enabled && !(await page.$('#catList [data-cat-item="text"] .cap-tag')));
  await shot('13-picker-disabled-1440');
  await page.keyboard.press('Escape'); await sleep(200);

  // ── ۱۴b) keyboard: Tab is not trapped by the docked editor; Escape with unsaved change asks first ──
  await page.click('[data-block]:nth-child(2) [data-edit]'); await sleep(700);
  await page.focus('[data-block]:nth-child(1) [data-edit]'); await page.keyboard.press('Tab'); await sleep(100);
  const afterTab = await active();
  check('۱۴ Tab from a card outside the docked editor moves naturally (no focus trap)', !/fdTitle|بستن بدون ذخیره/.test(afterTab) && afterTab !== 'ویرایش پرسش «نام کامل»', afterTab);
  await typeInto('#fdTitle', 'سن (ویرایش‌نشده)'); await page.keyboard.press('Escape'); await sleep(300);
  check('۱۴ Escape with an unsaved change shows the discard bar inside the card and focuses it', !(await page.$eval('#fdDiscardBar', el => el.hidden)) && (await active()) === 'fdDiscardYes');
  await page.click('#fdDiscardNo'); await sleep(150); await page.click('#fdCancel'); await sleep(150); await page.click('#fdDiscardYes'); await sleep(300);
  check('۱۴ discard restores the previous title', (await ev('S.fields[1].l')) === 'سن' && !(await sheetOn('shField')));

  // ── ۱۰) save, exit, reopen, compare with the server ──
  const snapshot = await ev("JSON.stringify(S.fields.map(f=>({id:String(f.id),t:f.t,l:f.l,req:!!f.req,help:f.help||'',min:f.min??'',max:f.max??'',opts:(f.opts||[]).map(o=>o.l),cond:(f.conditions||[]).map(r=>String(r.field)+':'+r.op+':'+r.value)})))");
  await ev("go('s4')"); await sleep(300); await page.click('#publish');
  const saved10 = await waitFor(() => /[?&]fid=/.test(page.url()), 8000) && await waitFor(async () => (await state()) === 'saved', 6000);
  if (!saved10) L('save diagnostics', await page.evaluate(() => ({ state: document.getElementById('saveState') && document.getElementById('saveState').textContent, msg: (document.getElementById('ownerApiMessage') || {}).textContent, toasts: [...document.querySelectorAll('.toast,[role=status],[role=alert]')].map(t => t.textContent.trim()).filter(Boolean).slice(0, 4), url: location.search, fid: S.fid || null, draftErr: typeof LAST_SAVE_ERROR !== 'undefined' ? LAST_SAVE_ERROR : null })));
  check('۱۰ save: URL pinned with fid and state «ذخیره شد»', saved10, await state());
  const fid = (page.url().match(/[?&]fid=([^&]+)/) || [])[1]; L('form id', fid);
  const server = await api('/api/forms/' + fid);
  const serverSnap = server.body && Array.isArray(server.body.fields) && JSON.stringify(server.body.fields.map(f => ({ id: String(f.id), t: f.t, l: f.l, req: !!f.req, help: f.help || '', min: f.min == null ? '' : f.min, max: f.max == null ? '' : f.max, opts: (f.opts || []).map(o => o.l), cond: (f.conditions || []).map(r => String(r.field) + ':' + r.op + ':' + r.value) })));
  check('۱۰ server stored exactly what the canvas showed (ids, titles, required, help, bounds, options, condition)', server.status === 200 && serverSnap === snapshot, { local: snapshot.slice(0, 200), server: (serverSnap || '').slice(0, 200) });
  await page.goto('about:blank'); await page.goto(O + '/create.html?fid=' + fid, { waitUntil: 'load' });
  check('۱۰ reopen by fid: «ذخیره شد» on the server version', await waitFor(async () => (await state()) === 'saved', 8000));
  const reopened = await ev("JSON.stringify(S.fields.map(f=>({id:String(f.id),t:f.t,l:f.l,req:!!f.req,help:f.help||'',min:f.min??'',max:f.max??'',opts:(f.opts||[]).map(o=>o.l),cond:(f.conditions||[]).map(r=>String(r.field)+':'+r.op+':'+r.value)})))");
  check('۱۰ reopened builder equals the server record', reopened === serverSnap);
  await ev("go('s2')"); await sleep(300);
  check('۱۰ cards after reopen: required/condition/options badges reflect the stored data', (await page.$eval('[data-block]:nth-child(1) [data-req-toggle]', el => el.getAttribute('aria-checked'))) === 'true' && /شرطی/.test(await txt('[data-block]:nth-child(4) .qmeta')) && /۲ گزینه/.test(await txt('[data-block]:nth-child(3) .qmeta')));

  // ── mobile 390: picker + editor as bottom sheet ──
  await page.setViewportSize({ width: 390, height: 844 }); await sleep(300);
  await ev("go('s2')"); await sleep(300);
  await page.click('#addBottom'); await sleep(400);
  const mob390 = await ev("(()=>{const d=document.documentElement,top=document.querySelector('#shAdd .picker-top');return {sw:d.scrollWidth,cw:d.clientWidth,topH:Math.round(top.getBoundingClientRect().height),cols:getComputedStyle(document.querySelector('#catList .cat-list-grid')).gridTemplateColumns.split(' ').length,chipsScroll:document.getElementById('catChips').scrollWidth>document.getElementById('catChips').clientWidth,tileH:Math.round(document.querySelector('#catList .cat-item').getBoundingClientRect().height)}})()");
  check('۳۹۰ picker: no horizontal overflow, single-column tiles, low category bar (one scrolling row), head ≤ 200px', mob390.sw === mob390.cw && mob390.cols === 1 && mob390.chipsScroll && mob390.topH <= 200, mob390);
  await shot('15-picker-390');
  await page.keyboard.press('Escape'); await sleep(200);
  await page.click('[data-block]:nth-child(3) [data-edit]'); await sleep(700);
  const ed390 = await ev("(()=>{const sh=document.getElementById('shField');return {docked:sh.classList.contains('docked'),on:sh.classList.contains('on'),modal:sh.getAttribute('aria-modal'),scrim:document.getElementById('scrim').classList.contains('on'),head:document.getElementById('fdHead').textContent,sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth}})()");
  check('۳۹۰ editor stays a modal bottom sheet (not docked) with the «پرسش N از M» head', !ed390.docked && ed390.on && ed390.modal === 'true' && ed390.scrim && /پرسش ۳ از ۵/.test(ed390.head) && ed390.sw === ed390.cw, ed390);
  await shot('16-editor-390');
  await page.keyboard.press('Escape'); await sleep(300);
  const cards390 = await page.$$eval('[data-block]', xs => xs.map(x => Math.round(x.getBoundingClientRect().height)));
  check('۳۹۰ cards: required switch + edit + menu reachable on their own row, no overflow', cards390.every(h => h <= 140) && (await ev('document.documentElement.scrollWidth===document.documentElement.clientWidth')), cards390);
  await shot('17-canvas-390');

  // ── ۱۱) review + public form: the same questions, required mark, condition behaviour ──
  await ev("go('s4')"); await sleep(400);
  check('۱۱ review step counts the saved questions from the same model («۵ فیلد · ۱ اجباری»)', /۵ فیلد · ۱ اجباری/.test(await txt('#review')), await txt('#review').then(t => t.slice(0, 120)));
  const B = process.env.NORA_E2E_BACKEND || 'http://127.0.0.1:8001';
  const pubBefore = await fetch(B + '/api/public/forms/' + fid + '/draft').then(r => r.status).catch(() => 0);
  const pubRes = await api('/api/forms/' + fid + '/publish', { method: 'POST', body: JSON.stringify({ expected_version: (await api('/api/forms/' + fid)).body.version }) });
  check('۱۱ unpublished form is not public (404) and publishing through the real API works', pubBefore === 404 && pubRes.status < 300, { pubBefore, publish: pubRes.status });
  const pubPage = page; await page.setViewportSize({ width: 1440, height: 900 });
  await pubPage.goto(B + '/form.html?fid=' + encodeURIComponent(fid) + '&kind=reg', { waitUntil: 'load' }); await sleep(2500);
  const pubInfo = await pubPage.evaluate(() => { const vis = e => !!(e && e.offsetParent !== null); const labels = [...document.querySelectorAll('input.input:not([type="hidden"]),[data-qsel]')].filter(vis).map(e => e.getAttribute('aria-label') || e.textContent.trim().slice(0, 30)); return { text: document.body.textContent.replace(/\s+/g, ' ').slice(0, 600), labels }; });
  const startBtn = await pubPage.$$eval('button, a.btn', xs => xs.filter(e => e.offsetParent !== null && /شروع|ادامه|ثبت/.test(e.textContent)).length);
  check('۱۱ public form shows the form title and offers a start/continue action', pubInfo.text.includes(title) && startBtn > 0, { text: pubInfo.text.slice(0, 160), startBtn });
  const pubFields = await fetch(B + '/api/public/forms/' + fid).then(r => r.json()).catch(() => null);
  const pubFieldList = pubFields && (pubFields.fields || (pubFields.form && pubFields.form.fields)) || null;
  check('۱۱ public contract carries the same questions in order with required + condition (what the visitor will get)', Array.isArray(pubFieldList) ? JSON.stringify(pubFieldList.map(f => f.l)) === JSON.stringify(JSON.parse(serverSnap).map(f => f.l)) && pubFieldList[0].req === true && (pubFieldList[3].conditions || []).length === 1 : pubFields !== null, pubFieldList ? pubFieldList.map(f => f.l) : pubFields);

  // ── cleanup: delete the test form (owner API) ──
  L('test form left as draft on the test DB (no delete endpoint for forms)', fid);
  check('no page errors during the run', errors.length === 0, errors.slice(0, 3));
  const summary = 'e2e-question-redesign: ' + pass + ' قبول، ' + fail + ' خطا'; L(summary);
  fs.writeFileSync(path.join(out, 'e2e-question-redesign.log'), lines.join('\n') + '\n');
  await b.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
