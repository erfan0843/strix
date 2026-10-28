// Real-browser check of the field-picker journey (desktop 1440 + mobile 390):
// open from start / end / between, position note, keyboard (Escape, focus into search), type vs pattern,
// disabled reason inline, quick-add several, move a field that has dependent conditions, type change without silent loss.
// Usage: NORA_QA_BROWSER=sparticuz NORA_QA_DEPENDENCIES=<deps> NORA_REPO_UI=<ui> node e2e-picker-ux.cjs <outdir>
const fs = require('node:fs'), path = require('node:path');
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O = process.env.NORA_E2E_OWNER || 'http://127.0.0.1:8000';
const out = process.argv[2] || 'shots/picker-ux'; fs.mkdirSync(out, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms)); const lines = []; let pass = 0, fail = 0;
const L = (m, x) => { const t = m + (x === undefined ? '' : ': ' + (typeof x === 'string' ? x : JSON.stringify(x))); lines.push(t); console.log(t); };
const check = (n, ok, extra) => { ok ? pass++ : fail++; L((ok ? 'PASS ' : 'FAIL ') + n + (extra === undefined || ok ? '' : ' · ' + JSON.stringify(extra).slice(0, 300))); };
(async () => {
  const b = await launchBrowser(); const page = await b.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(e.message)); page.on('dialog', d => d.accept());
  const shot = async (n, full) => page.screenshot({ path: path.join(out, n + '.png'), fullPage: !!full });
  const waitFor = async (fn, ms = 8000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await fn()) return true; } catch (e) { } await sleep(150); } return false; };
  const ev = code => page.evaluate(code);
  const txt = s => page.$eval(s, el => (el.textContent || '').replace(/\s+/g, ' ').trim()).catch(() => '');
  const sheetOn = id => page.$eval('#' + id, el => el.classList.contains('on')).catch(() => false);
  const clickSel = async s => { await page.waitForSelector(s, { timeout: 8000 }); await page.click(s); };
  const typeInto = async (s, v) => { await page.fill(s, v); await page.$eval(s, el => { el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }); };
  const activeId = () => ev("document.activeElement&&(document.activeElement.id||document.activeElement.getAttribute('aria-label')||document.activeElement.tagName)");
  const ids = () => ev("S.fields.map(f=>String(f.id)+':'+f.t).join(' ')");

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('about:blank'); await page.goto(O + '/create.html?need=reg', { waitUntil: 'load' }); await sleep(1500);
  check('capability contract ready', await waitFor(() => ev("FORM_CAPABILITY_STATE==='ready'"), 10000));
  await ev("go('s2')"); await sleep(300); await ev("applyPack('empty','replace')"); await sleep(300);
  check('empty canvas auto-opens the picker', await sheetOn('shAdd'));
  // ── quick add several in a row (end) ──
  for (const k of ['fullname', 'mobile', 'choice']) { if (!(await sheetOn('shAdd'))) { await clickSel('#addBottom'); await sleep(200); } await clickSel('#catList [data-add="' + k + '"]'); await sleep(250); await clickSel('#fdSave'); await sleep(200); }
  check('three fields added quickly through the picker, each saved with defaults', (await ids()).split(' ').map(x => x.split(':')[1]).join() === 'fullname,mobile,choice', await ids());
  // ── open from the start ──
  await clickSel('#addTop'); await sleep(300);
  check('«+» at the top: picker opens with the position note «ابتدای فهرست»', (await sheetOn('shAdd')) && /ابتدای فهرست/.test(await txt('#catPositionNote')), await txt('#catPositionNote'));
  check('search box receives focus when the picker opens', (await activeId()) === 'catSearch', await activeId());
  await shot('01-picker-top-1440');
  await clickSel('#catList [data-add="nid"]'); await sleep(250); await clickSel('#fdSave'); await sleep(200);
  check('new field landed first', (await ids()).startsWith((await ev('String(S.fields[0].id)')) + ':nid') && (await ev('S.fields.length')) === 4, await ids());
  // ── open between (row menu) ──
  const secondId = await ev('String(S.fields[1].id)');
  await page.$eval('[data-add-after="' + secondId + '"]', el => { el.closest('details').open = true; }); await sleep(100);
  await page.click('[data-add-after="' + secondId + '"]'); await sleep(300);
  check('row menu «افزودن پرسش پس از این» opens the picker with «پس از پرسش ۲»', (await sheetOn('shAdd')) && /پس از پرسش ۲/.test(await txt('#catPositionNote')), await txt('#catPositionNote'));
  await clickSel('#catList [data-add="email"]'); await sleep(250); await clickSel('#fdSave'); await sleep(200);
  check('new field sits exactly after that row', (await ev('S.fields[2].t')) === 'email' && (await ev('S.fields.length')) === 5, await ids());
  // ── Escape closes, position forgotten ──
  await clickSel('#addTop'); await sleep(200); await page.keyboard.press('Escape'); await sleep(200);
  check('Escape closes the picker', !(await sheetOn('shAdd')));
  await clickSel('#addBottom'); await sleep(200);
  check('«+» at the bottom: no position note (append)', await page.$eval('#catPositionNote', el => el.hidden));
  // ── type vs pattern + disabled reason ──
  await typeInto('#catSearch', 'تاریخ'); await sleep(250);
  const dateRows = await page.$$eval('#catList [data-add]', xs => xs.map(x => ({ k: x.dataset.add, t: x.dataset.type, text: x.textContent.replace(/\s+/g, ' ').trim().slice(0, 80) })));
  check('«تاریخ» lists two patterns of the same technical type (birth-date / jalali-date)', dateRows.filter(r => r.t === 'date').length === 2 && dateRows.some(r => r.k === 'birth-date') && dateRows.some(r => r.k === 'jalali-date'), dateRows);
  await typeInto('#catSearch', 'عکس'); await sleep(250);
  const img = await page.$eval('#catList [data-add="image"]', el => ({ disabled: el.disabled, text: el.textContent.replace(/\s+/g, ' ').trim() })).catch(() => null);
  check('upload row is disabled with the server reason inline', img && img.disabled && /وصل نیست|غیرفعال/.test(img.text), img);
  await typeInto('#catSearch', ''); await sleep(200);
  await clickSel('#catList [data-add="birth-date"]'); await sleep(250);
  const typeChoices = await page.$$eval('#fdTypeChange option', xs => xs.map(o => o.value).filter(Boolean));
  check('type-change list offers the sibling pattern (jalali-date) explicitly, not only other types', typeChoices.includes('jalali-date') && typeChoices.includes('time'), typeChoices);
  await typeInto('#fdTitle', 'تاریخ تولد من'); await clickSel('#fdSave'); await sleep(200);
  const birthId = await ev('String(S.fields[S.fields.length-1].id)');
  await ev("editField('" + birthId + "')"); await sleep(200);
  const cons = await ev("typeChangeConsequences(FIELD_DRAFT,'jalali-date').join(' ')");
  check('pattern swap keeps the custom title (consequences say so)', /عنوان «تاریخ تولد من» حفظ می‌شود/.test(cons) && /فقط الگو/.test(cons), cons);
  await ev("applyTypeChange('jalali-date')"); await sleep(100); await clickSel('#fdSave'); await sleep(200);
  check('after the pattern swap: type still date, preset jalali-date, title unchanged', await ev("(f=>f.t==='date'&&f.preset==='jalali-date'&&f.l==='تاریخ تولد من')(S.fields[S.fields.length-1])"), await ev('JSON.stringify(S.fields[S.fields.length-1])'));
  // ── move a field with dependent conditions ──
  const choiceId = await ev("String(S.fields.find(f=>f.t==='choice').id)");
  await clickSel('#addBottom'); await sleep(200); await clickSel('#catList [data-add="text"]'); await sleep(250);
  await typeInto('#fdTitle', 'چرا؟');
  await ev("conditionDraft=[{field:'" + choiceId + "',op:'eq',value:'گزینهٔ یک'}];conditionLogicDraft='all';renderConditionEditor()"); await sleep(100);
  await clickSel('#fdSave'); await sleep(200);
  const whyId = await ev('String(S.fields[S.fields.length-1].id)');
  check('conditional question saved with its rule', await ev("conditionRulesForField(S.fields[S.fields.length-1]).length===1"));
  const before = await ev('S.fields.length');
  await ev("moveFieldById('" + whyId + "',-1)"); await sleep(200);
  check('moving the conditional question down the list but still after its reference keeps the rule', await ev("conditionRulesForField(S.fields.find(f=>String(f.id)==='" + whyId + "')).length===1") && (await ev('S.fields.length')) === before);
  // move the reference (choice) to the very end → rule would point forward → dropped with a toast (announced, not silent)
  const choiceIndex = await ev("S.fields.findIndex(f=>String(f.id)==='" + choiceId + "')");
  const whyIndex = await ev("S.fields.findIndex(f=>String(f.id)==='" + whyId + "')");
  await ev("for(let i=0;i<" + (whyIndex - choiceIndex) + ";i++)moveFieldById('" + choiceId + "',1)"); await sleep(400);
  const toast = await txt('#toast');
  check('moving the referenced question below the dependent one drops the rule and says so', await ev("conditionRulesForField(S.fields.find(f=>String(f.id)==='" + whyId + "')).length===0") && /شرط نمایش برداشته شد/.test(toast), toast);
  await shot('02-canvas-after-moves-1440', true);
  // ── mobile ──
  await page.setViewportSize({ width: 390, height: 844 }); await sleep(300);
  await ev("window.scrollTo(0,0)"); await clickSel('#addTop'); await sleep(400);
  const pickerBox = await page.$eval('#shAdd', el => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top) }; });
  check('mobile: picker is a full-width sheet', pickerBox.w >= 380 && pickerBox.h > 300, pickerBox);
  const chipsScroll = await page.$eval('#catChips', el => el.scrollWidth > el.clientWidth || el.clientHeight < 120);
  check('mobile: category chips do not stack into a tall block', chipsScroll);
  await shot('03-picker-390');
  await page.keyboard.press('Escape'); await sleep(200);
  const firstId = await ev('String(S.fields[0].id)');
  await page.$eval('[data-add-after="' + firstId + '"]', el => { el.closest('details').open = true; el.scrollIntoView(); }); await sleep(150);
  const menuBtn = await page.$eval('[data-add-after="' + firstId + '"]', el => { const r = el.getBoundingClientRect(); return { h: Math.round(r.height), visible: r.width > 0 && r.height > 0 }; });
  check('mobile: «افزودن پرسش پس از این» is a ≥40px visible menu item (no hover-only action)', menuBtn.visible && menuBtn.h >= 40, menuBtn);
  await shot('04-row-menu-390');
  await page.click('[data-add-after="' + firstId + '"]'); await sleep(300);
  check('mobile: picker opens from the row menu with the position note', (await sheetOn('shAdd')) && /پس از پرسش ۱/.test(await txt('#catPositionNote')), await txt('#catPositionNote'));
  await page.keyboard.press('Escape');
  check('no page errors in the browser', errors.length === 0, errors.slice(0, 3));
  await b.close();
  fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\n');
  console.log('e2e-picker-ux: ' + pass + ' قبول، ' + fail + ' خطا');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('CRASH', e); fs.writeFileSync(path.join(out, 'log.txt'), lines.join('\n') + '\nCRASH ' + (e && e.stack || e) + '\n'); process.exit(1); });
