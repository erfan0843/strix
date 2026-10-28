// Error + retry + loading-state probe for builder auto-load (owner proxy)
const {launchBrowser}=require(process.env.NORA_REPO_UI+'/tools/browser-launch.cjs');
(async()=>{
  const browser=await launchBrowser();const page=await browser.newPage();const origin='http://127.0.0.1:8000';const out=process.argv[2];
  await page.setViewportSize({width:1440,height:900});
  // 1) loading state: delay /api/forms by 2s, screenshot while skeleton visible
  await page.route('**/api/forms',async r=>{await new Promise(x=>setTimeout(x,2000));await r.continue()});
  await page.goto(origin+'/builder.html',{waitUntil:'load'});await page.waitForTimeout(500);
  const loading=await page.evaluate(()=>({state:document.querySelector('#serverFormsMessage').dataset.state,skel:!!document.querySelector('[data-forms-loading]'),busy:document.querySelector('#syncServerForms').disabled,msg:document.querySelector('#serverFormsMessageText').textContent.trim()}));
  await page.screenshot({path:out+'-loading-1440.png'});console.log('loading',JSON.stringify(loading));
  await page.waitForTimeout(2500);console.log('after delay',await page.evaluate(()=>document.querySelector('#serverFormsMessage').dataset.state+' cards='+document.querySelectorAll('#formCards [data-form]').length));
  await page.unroute('**/api/forms');
  // 2) error: abort /api/forms
  const calls=[];page.on('request',r=>{if(r.url().includes('/api/'))calls.push(r.method()+' '+r.url().replace(origin,''))});
  await page.route('**/api/forms',r=>r.abort());
  await page.goto('about:blank');await page.goto(origin+'/builder.html',{waitUntil:'load'});await page.waitForTimeout(1500);
  const err=await page.evaluate(()=>({state:document.querySelector('#serverFormsMessage').dataset.state,msg:document.querySelector('#serverFormsMessageText').textContent.trim(),retryHidden:document.querySelector('#serverFormsRetry').hidden,empty:(document.querySelector('#formCards .empty .body')||{}).textContent||'',cards:document.querySelectorAll('#formCards [data-form]').length}));
  await page.screenshot({path:out+'-error-1440.png'});console.log('error',JSON.stringify(err));
  // double click retry quickly → only one request set
  await page.unroute('**/api/forms');calls.length=0;
  await page.route('**/api/forms',async r=>{await new Promise(x=>setTimeout(x,800));await r.continue()});
  await page.click('#serverFormsRetry');await page.waitForTimeout(50);
  const second=await page.evaluate(()=>{const b=document.querySelector('#syncServerForms');const r=document.querySelector('#serverFormsRetry');return {syncDisabled:b.disabled,retryDisabled:r.disabled}});
  await page.evaluate(()=>{document.querySelector('#syncServerForms').click();document.querySelector('#serverFormsRetry').click()});
  await page.waitForTimeout(2000);
  const after=await page.evaluate(()=>({state:document.querySelector('#serverFormsMessage').dataset.state,cards:document.querySelectorAll('#formCards [data-form]').length,retryHidden:document.querySelector('#serverFormsRetry').hidden}));
  console.log('retry: during',JSON.stringify(second),'after',JSON.stringify(after),'calls',JSON.stringify(calls));
  await page.screenshot({path:out+'-retried-1440.png'});
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
