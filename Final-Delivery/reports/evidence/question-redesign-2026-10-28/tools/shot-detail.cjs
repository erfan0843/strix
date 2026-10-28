const path=require('node:path');const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O='http://127.0.0.1:8000', out=process.argv[2];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const SH={timeout:30000,animations:'disabled',caret:'initial'};
(async()=>{const b=await launchBrowser();const page=await b.newPage();page.on('dialog',d=>d.accept());
 for(const [w,h] of (process.env.VP||'1440x900,390x844').split(',').map(x=>x.split('x').map(Number))){
  await page.setViewportSize({width:w,height:h});await page.goto('about:blank');await page.goto(O+'/create.html?need=reg',{waitUntil:'load'});await sleep(1500);
  await page.evaluate(()=>{document.querySelector('[data-model="registration"]').click();go('s2');applyPack('empty','replace');});await sleep(300);
  await page.evaluate(()=>{if(!document.getElementById('shAdd').classList.contains('on'))document.getElementById('addTop').click()});await sleep(400);
  await page.evaluate(()=>{document.querySelector('[data-cat-info="number"]').click();document.querySelector('[data-cat-info="mobile"]').click();document.querySelector('[data-cat="person"]').click()});await sleep(300);
  await page.screenshot(Object.assign({path:path.join(out,'picker-detail-'+w+'.png')},SH));
  await page.evaluate(()=>{document.querySelector('[data-cat="future"]').click()});await sleep(300);
  await page.screenshot(Object.assign({path:path.join(out,'picker-future-'+w+'.png')},SH));
  await page.evaluate(()=>{document.querySelector('[data-cat="all"]').click();const s=document.getElementById('catSearch');s.value='عدد صحیح';s.dispatchEvent(new Event('input',{bubbles:true}))});await sleep(300);
  await page.screenshot(Object.assign({path:path.join(out,'picker-hint-'+w+'.png')},SH));
  const m=await page.evaluate(()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,added:S.fields.length,top:Math.round(document.querySelector('.picker-top').getBoundingClientRect().height)}));
  console.log(w,JSON.stringify(m));
 }
 await b.close();})();
