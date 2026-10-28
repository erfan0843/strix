// Before/after shots — form-builder UX completion + menus («مدیران» group, «فرم‌ساز» tab).
// Usage: VP=1440x900,390x844 node shot-ux3.cjs <outdir>   (owner :8000, manager :8080, member :8090)
const path=require('node:path');const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const O='http://127.0.0.1:8000', M='http://127.0.0.1:8080', U='http://127.0.0.1:8090', out=process.argv[2];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));const SH={timeout:30000,animations:'disabled',caret:'initial'};
const theme=(page,t)=>page.evaluate(tt=>{document.documentElement.setAttribute('data-theme',tt);try{localStorage.setItem('nora-theme',tt)}catch(e){}},t);
(async()=>{const b=await launchBrowser();const page=await b.newPage();page.on('dialog',d=>d.accept());
 const shot=async n=>page.screenshot(Object.assign({path:path.join(out,n+'.png')},SH));
 const metrics={};
 for(const [w,h] of (process.env.VP||'1440x900,1024x768,390x844,360x740').split(',').map(x=>x.split('x').map(Number))){
  await page.setViewportSize({width:w,height:h});
  /* ── builder (owner) ── */
  await page.goto('about:blank');await page.goto(O+'/create.html?need=reg',{waitUntil:'load'});await sleep(1500);await theme(page,'light');
  await page.evaluate(()=>{document.querySelector('[data-model="registration"]').click();go('s2');applyPack('empty','replace');});await sleep(300);
  await page.evaluate(()=>{if(!document.getElementById('shAdd').classList.contains('on'))document.getElementById('addTop').click()});await sleep(500);
  await shot('picker-'+w);
  const ov=await page.evaluate(()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,top:Math.round(document.querySelector('.picker-top').getBoundingClientRect().height),tiles:[...document.querySelectorAll('.cat-item')].slice(0,12).map(t=>Math.round(t.getBoundingClientRect().height))}));
  await page.evaluate(()=>{const s=document.getElementById('catSearch');s.value='ایمیل';s.dispatchEvent(new Event('input',{bubbles:true}))});await sleep(300);
  await shot('picker-search-'+w);
  await page.evaluate(()=>{const s=document.getElementById('catSearch');s.value='qqzz';s.dispatchEvent(new Event('input',{bubbles:true}))});await sleep(300);
  await shot('picker-empty-'+w);
  await page.evaluate(()=>{const s=document.getElementById('catSearch');s.value='';s.dispatchEvent(new Event('input',{bubbles:true}))});await sleep(200);
  // details of a limited field (mobile number) then add it
  await page.evaluate(()=>{const i=document.querySelector('#catList [data-cat-item="mobile"] [data-cat-info]');i&&i.click();i&&i.scrollIntoView({block:'center'})});await sleep(300);
  await shot('picker-detail-'+w);
  for(const k of ['fullname','mobile','choice','number','area']){
    await page.evaluate(()=>{if(!document.getElementById('shAdd').classList.contains('on'))document.getElementById('addBottom').click()});await sleep(250);
    await page.evaluate((kk)=>{document.querySelector('#catList [data-add="'+kk+'"]').click()},k);await sleep(300);
    await page.evaluate(()=>{const s=document.getElementById('fdSave');if(s&&document.getElementById('shField').classList.contains('on'))s.click()});await sleep(250);
  }
  await page.evaluate(()=>{closeSheets&&closeSheets();const fl=document.getElementById('fieldList');window.scrollTo(0,Math.max(0,fl.getBoundingClientRect().top+window.scrollY-160))});await sleep(300);
  await shot('canvas-'+w);
  await page.click('[data-block]:nth-child(3) [data-edit]');await sleep(1500);
  await shot('editor-choice-'+w);
  await page.evaluate(()=>{const c=document.getElementById('fdCancel')||document.querySelector('#shField [data-fd-cancel]');c&&c.click();closeSheets&&closeSheets()});await sleep(300);
  await page.click('[data-block]:nth-child(4) [data-edit]');await sleep(1500);
  await shot('editor-number-'+w);
  await page.evaluate(()=>{const c=document.querySelector('#shField [data-edit-cond],#fdCondAdd');c&&c.click()});await sleep(400);
  await shot('editor-conditions-'+w);
  const ov2=await page.evaluate(()=>({sw2:document.documentElement.scrollWidth}));
  /* ── admin menu (owner) ── */
  await page.goto('about:blank');await page.goto(O+'/admin.html#reports',{waitUntil:'load'});await sleep(2500);await theme(page,'light');
  await shot('admin-reports-'+w);
  await page.goto(O+'/admin.html#users');await sleep(800);await shot('admin-users-'+w);
  await theme(page,'dark');await sleep(200);await shot('admin-users-dark-'+w);
  const nav=await page.evaluate(()=>({sw3:document.documentElement.scrollWidth,rail:[...document.querySelectorAll('#admNav button,#admNav a')].map(x=>x.textContent.trim()).join('|'),tabs:[...document.querySelectorAll('#admTabs a')].map(x=>x.textContent.trim()).join('|')}));
  /* ── main menu: owner home, manager account, member account ── */
  await page.goto('about:blank');await page.goto(O+'/home.html',{waitUntil:'load'});await sleep(2000);await theme(page,'light');await shot('home-owner-'+w);
  const n1=await page.evaluate(()=>({ownerForms:document.querySelectorAll('.tabbar [data-forms-nav]').length,tabs:[...document.querySelectorAll('.tabbar a')].map(a=>a.textContent.trim()).join('|')}));
  await page.goto('about:blank');await page.goto(M+'/account.html',{waitUntil:'load'});await sleep(2500);await theme(page,'light');await shot('account-manager-'+w);
  const n2=await page.evaluate(()=>({managerFormsAccount:document.querySelectorAll('.tabbar [data-forms-nav]').length}));
  await page.goto('about:blank');await page.goto(M+'/events.html',{waitUntil:'load'});await sleep(2500);await shot('events-manager-'+w);
  const n3=await page.evaluate(()=>({managerFormsEvents:document.querySelectorAll('.tabbar [data-forms-nav]').length}));
  await page.goto('about:blank');await page.goto(U+'/account.html',{waitUntil:'load'});await sleep(2500);await theme(page,'light');await shot('account-member-'+w);
  await theme(page,'dark');await sleep(200);await shot('account-member-dark-'+w);
  const n4=await page.evaluate(()=>({memberForms:document.querySelectorAll('.tabbar [data-forms-nav]').length}));
  metrics[w]=Object.assign(ov,ov2,nav,n1,n2,n3,n4);console.log(w,JSON.stringify(metrics[w]));
 }
 require('node:fs').writeFileSync(path.join(out,'metrics.json'),JSON.stringify(metrics,null,1));
 await b.close();})();
