const path=require('node:path');const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O='http://127.0.0.1:8000', out=process.argv[2];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const SH={timeout:30000,animations:'disabled',caret:'initial'};
(async()=>{const b=await launchBrowser();const page=await b.newPage();page.on('dialog',d=>d.accept());
 for(const [w,h] of (process.env.VP||'1440x900,390x844').split(',').map(x=>x.split('x').map(Number))){
  await page.setViewportSize({width:w,height:h});await page.goto('about:blank');await page.goto(O+'/create.html?need=reg',{waitUntil:'load'});await sleep(1500);
  await page.evaluate(()=>{document.querySelector('[data-model="registration"]').click();go('s2');applyPack('empty','replace');});await sleep(300);
  for(const k of ['fullname','mobile','choice','area','rating']){
    await page.evaluate(()=>{if(!document.getElementById('shAdd').classList.contains('on'))document.getElementById('addBottom').click()});await sleep(250);
    await page.evaluate((kk)=>{document.querySelector('#catList [data-add="'+kk+'"]').click()},k);await sleep(300);
    await page.evaluate(()=>{const s=document.getElementById('fdSave');if(s&&document.getElementById('shField').classList.contains('on'))s.click()});await sleep(250);
  }
  await page.evaluate(()=>{closeSheets&&closeSheets();window.scrollTo(0,0)});await sleep(300);
  // click the real edit button of question 3 (choice) like a user
  await page.click('[data-block]:nth-child(3) [data-edit]');await sleep(1800);
  await page.screenshot(Object.assign({path:path.join(out,'dock-edit-'+w+'.png')},SH));
  const m=await page.evaluate(()=>{const sh=document.getElementById('shField'),blk=sh.closest('.block');return {docked:sh.classList.contains('docked'),on:sh.classList.contains('on'),inCard:!!blk,isEditing:blk&&blk.classList.contains('is-editing'),modal:sh.getAttribute('aria-modal'),scrim:document.getElementById('scrim').classList.contains('on'),head:document.getElementById('fdHead').textContent,active:document.activeElement.id,sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,scrollY:window.scrollY}});
  console.log(w,JSON.stringify(m));
  if(w<900){await page.keyboard.press('Escape');await sleep(300);continue}
  // required toggle on card 1 while editor open on card 3
  await page.click('[data-block]:nth-child(1) [data-req-toggle]');await sleep(300);
  const m2=await page.evaluate(()=>{const sh=document.getElementById('shField');return {stillDocked:sh.classList.contains('docked')&&!!sh.closest('[data-block]:nth-child(3)'),req1:S.fields[0].req,toggle1:document.querySelector('[data-block]:nth-child(1) [data-req-toggle]').getAttribute('aria-checked'),active:document.activeElement.getAttribute('data-req-toggle')?'toggle':document.activeElement.tagName,titleVal:document.getElementById('fdTitle').value}});
  console.log(w,'toggle',JSON.stringify(m2));
  await page.keyboard.press('Escape');await sleep(400);
  const m3=await page.evaluate(()=>{const sh=document.getElementById('shField');return {docked:sh.classList.contains('docked'),on:sh.classList.contains('on'),parent:sh.parentElement.tagName,editing:document.querySelectorAll('.block.is-editing').length,active:document.activeElement.getAttribute('data-edit')?'edit-btn':document.activeElement.tagName}});
  console.log(w,'esc',JSON.stringify(m3));
  await page.screenshot(Object.assign({path:path.join(out,'dock-closed-'+w+'.png')},SH));
 }
 await b.close();})();
