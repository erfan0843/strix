// Probe builder auto-load: logs network calls to /api/* and final state per origin
const {launchBrowser}=require(process.env.NORA_REPO_UI+'/tools/browser-launch.cjs');
(async()=>{
  const browser=await launchBrowser();const page=await browser.newPage();
  for(const [label,origin,w,h] of [['owner','http://127.0.0.1:8000',1440,900],['manager','http://127.0.0.1:8080',390,844],['guest','http://127.0.0.1:8001',1024,768]]){
    await page.setViewportSize({width:w,height:h});await page.goto('about:blank');
    const calls=[];page.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.method()+' '+r.url().replace(origin,''))});
    const errors=[];page.on('pageerror',e=>errors.push(String(e.message)));
    await page.goto(origin+'/builder.html',{waitUntil:'load'});await page.waitForTimeout(300);
    const early=await page.evaluate(()=>({state:document.querySelector('#serverFormsMessage').dataset.state,skel:!!document.querySelector('[data-forms-loading]')}));
    await page.waitForTimeout(2500);
    const out=await page.evaluate(()=>({state:document.querySelector('#serverFormsMessage').dataset.state,msg:document.querySelector('#serverFormsMessageText').textContent.trim(),cards:document.querySelectorAll('#formCards [data-form]').length,empty:(document.querySelector('#formCards .empty .body')||{}).textContent||'',login:getComputedStyle(document.querySelector('#serverFormsLogin')).display,retry:document.querySelector('#serverFormsRetry').hidden,btn:document.querySelector('#syncServerForms').disabled}));
    await page.screenshot({path:process.argv[2]+'-'+label+'-'+w+'.png'});
    console.log(label,'early',JSON.stringify(early));console.log(label,'final',JSON.stringify(out));console.log(label,'calls',JSON.stringify(calls));console.log(label,'errors',JSON.stringify(errors));
    if(label==='owner'){calls.length=0;await page.click('#syncServerForms');await page.waitForTimeout(1500);console.log('owner refresh calls',JSON.stringify(calls),await page.evaluate(()=>document.querySelector('#serverFormsMessageText').textContent.trim().slice(0,60)));}
    page.removeAllListeners('request');page.removeAllListeners('pageerror');
  }
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
