const path=require('node:path');const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O='http://127.0.0.1:8000', out=process.argv[2];const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const b=await launchBrowser();const page=await b.newPage();page.on('dialog',d=>d.accept());
 for(const [w,h] of [[1440,900],[1024,768],[390,844],[360,740]]){
  await page.setViewportSize({width:w,height:h});await page.goto('about:blank');await page.goto(O+'/create.html?need=reg',{waitUntil:'load'});await sleep(1500);
  await page.evaluate(()=>{go('s2');applyPack('empty','replace');});await sleep(300);
  await page.evaluate(()=>{if(!document.getElementById('shAdd').classList.contains('on'))document.getElementById('addTop').click()});await sleep(400);
  await page.screenshot({path:path.join(out,'picker-'+w+'.png')});
  await page.fill('#catSearch','تاریخ تولد');await page.$eval('#catSearch',el=>el.dispatchEvent(new Event('input',{bubbles:true})));await sleep(300);
  await page.screenshot({path:path.join(out,'picker-search-'+w+'.png')});
  const sheet=await page.$eval('#shAdd',el=>{const r=el.getBoundingClientRect();return {w:r.width,h:r.height,x:r.x}});console.log(w,JSON.stringify(sheet));
 }
 await b.close();})();
