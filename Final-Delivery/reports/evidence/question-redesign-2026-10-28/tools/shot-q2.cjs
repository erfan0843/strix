// Before/after shots for the question picker + canvas + editor redesign. Usage: VP=1440x900 node shot-q2.cjs <outdir>
const path=require('node:path');const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O='http://127.0.0.1:8000', out=process.argv[2];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const SH={timeout:30000,animations:'disabled',caret:'initial'};
(async()=>{const b=await launchBrowser();const page=await b.newPage();page.on('dialog',d=>d.accept());
 for(const [w,h] of (process.env.VP||'1440x900,1024x768,390x844,360x740').split(',').map(x=>x.split('x').map(Number))){
  await page.setViewportSize({width:w,height:h});await page.goto('about:blank');await page.goto(O+'/create.html?need=reg',{waitUntil:'load'});await sleep(1500);
  await page.evaluate(()=>{document.querySelector('[data-model="registration"]').click();go('s2');applyPack('empty','replace');});await sleep(300);
  // picker (all categories)
  await page.evaluate(()=>{if(!document.getElementById('shAdd').classList.contains('on'))document.getElementById('addTop').click()});await sleep(500);
  await page.screenshot(Object.assign({path:path.join(out,'picker-'+w+'.png')},SH));
  // picker search
  await page.evaluate(()=>{const s=document.getElementById('catSearch');s.value='شماره همراه';s.dispatchEvent(new Event('input',{bubbles:true}))});await sleep(300);
  await page.screenshot(Object.assign({path:path.join(out,'picker-search-'+w+'.png')},SH));
  await page.evaluate(()=>{const s=document.getElementById('catSearch');s.value='';s.dispatchEvent(new Event('input',{bubbles:true}))});await sleep(200);
  // add several fields through the real add path
  for(const k of ['fullname','mobile','choice','area','rating']){
    await page.evaluate(()=>{if(!document.getElementById('shAdd').classList.contains('on'))document.getElementById('addBottom').click()});await sleep(250);
    await page.evaluate((kk)=>{document.querySelector('#catList [data-add="'+kk+'"]').click()},k);await sleep(300);
    await page.evaluate(()=>{const s=document.getElementById('fdSave');if(s&&document.getElementById('shField').classList.contains('on'))s.click()});await sleep(250);
  }
  await page.evaluate(()=>{closeSheets&&closeSheets();const fl=document.getElementById('fieldList');window.scrollTo(0,Math.max(0,fl.getBoundingClientRect().top+window.scrollY-160))});await sleep(300);
  await page.screenshot(Object.assign({path:path.join(out,'canvas-5-'+w+'.png')},SH));
  const m=await page.evaluate(()=>{const cards=[...document.querySelectorAll('[data-block]')].map(c=>c.getBoundingClientRect().height);return {sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,cards:cards.map(Math.round)}});
  // edit the choice question
  await page.click('[data-block]:nth-child(3) [data-edit]');await sleep(1200);
  await page.screenshot(Object.assign({path:path.join(out,'editor-choice-'+w+'.png')},SH));
  const m2=await page.evaluate(()=>{const sh=document.getElementById('shField');return {sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,sheet:sh?Math.round(sh.getBoundingClientRect().width):null,inline:!!document.querySelector('[data-block] .inline-editor, [data-block].is-editing')}});
  console.log(w,JSON.stringify(Object.assign(m,m2)));
 }
 await b.close();})();
