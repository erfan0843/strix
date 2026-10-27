const path=require('node:path');const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O='http://127.0.0.1:8000', out=process.argv[2];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const b=await launchBrowser();const page=await b.newPage();page.on('dialog',d=>d.accept());
 for(const [w,h] of (process.env.VP||'1440x900,1024x768,390x844,360x740').split(',').map(x=>x.split('x').map(Number))){
  await page.setViewportSize({width:w,height:h});await page.goto('about:blank');await page.goto(O+'/create.html?need=reg',{waitUntil:'load'});await sleep(1500);
  await page.evaluate(()=>{document.querySelector('[data-model="survey"]').click()});await sleep(300);
  await page.evaluate(()=>{const t=document.getElementById('tiles');t.scrollIntoView();});await sleep(200);
  await page.screenshot({timeout:30000,animations:'disabled',caret:'initial',path:path.join(out,'s1-model-survey-'+w+'.png')});
  await page.evaluate(()=>{document.querySelector('[data-model="registration"]').click();go('s2');applyPack('empty','replace');});await sleep(300);
  await page.evaluate(()=>{if(!document.getElementById('shAdd').classList.contains('on'))document.getElementById('addTop').click()});await sleep(500);
  await page.screenshot({timeout:30000,animations:'disabled',caret:'initial',path:path.join(out,'picker-'+w+'.png')});
  await page.evaluate(()=>{document.querySelector('#catList [data-add="choice"]').click()});await sleep(500);
  await page.screenshot({timeout:30000,animations:'disabled',caret:'initial',path:path.join(out,'editor-choice-'+w+'.png')});
  await page.evaluate(()=>{FIELD_DRAFT.opts=[{l:'الف'},{l:'الف'}];renderFieldOptions();saveField()});await sleep(300);
  await page.screenshot({timeout:30000,animations:'disabled',caret:'initial',path:path.join(out,'editor-inline-error-'+w+'.png')});
  const ov=await page.evaluate(()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,sheet:document.getElementById('shField').getBoundingClientRect().width}));console.log(w,JSON.stringify(ov));
 }
 await b.close();})();
