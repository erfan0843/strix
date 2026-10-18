import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE='http://127.0.0.1:8000'; const FORM=process.env.FORM_ID; const out=[];
const say=(ok,m)=>{out.push((ok?'PASS ':'FAIL ')+m); console.log(out[out.length-1]);};
async function withPage(fn, vp={width:390,height:844}){ const b=await launchBrowser(); try{ const ctx=await b.newContext({viewport:vp, serviceWorkers:'block'}); const p=await ctx.newPage(); await fn(p); }finally{ await b.close(); } }
// 1. form error state: no sample links in DOM
await withPage(async p=>{ await p.goto(BASE+'/form.html?fid=missing-form',{waitUntil:'networkidle'});
  const r=await p.evaluate(()=>({e5:[...document.querySelectorAll('a[href]')].filter(a=>/id=e5/.test(a.getAttribute('href'))).length, endLinks:(document.getElementById('endLinks')||{}).innerHTML||'', h1:document.querySelector('#unavailableTitle')?.tagName, visibleTitle:getComputedStyle(document.querySelector('#uUnavailable')).display}));
  say(r.e5===0&&r.endLinks==='','form not-found: no fixture anchor in DOM (e5='+r.e5+', endLinks empty='+(r.endLinks==='')+')'); say(r.h1==='H1','form not-found title is H1');
  await p.screenshot({path:'/tmp/qa/verify/form-missing-390.png'}); });
// 2. toast kind on form page (real page, ui.js v128)
await withPage(async p=>{ await p.goto(BASE+'/form.html?fid='+FORM,{waitUntil:'networkidle'});
  const r=await p.evaluate(()=>{const t=document.getElementById('toast'),ic=t.querySelector('svg.i'); window.toast('ذخیره انجام نشد؛ دوباره تلاش کن.','error'); const a={d:ic.style.display,cls:t.className,on:t.classList.contains('on')}; return a;});
  say(r.d==='none'&&r.on&&/is-error/.test(r.cls),'error toast hides ✓ icon on live form page '+JSON.stringify(r));
  await p.screenshot({path:'/tmp/qa/verify/form-error-toast-390.png'});
  const r2=await p.evaluate(()=>{const t=document.getElementById('toast'),ic=t.querySelector('svg.i'); window.toast('پاسخت بازیابی شد'); return {d:ic.style.display,cls:t.className};});
  say(r2.d===''&&!/is-error/.test(r2.cls),'success toast restores icon '+JSON.stringify(r2)); });
// 3. skip links: first Tab lands on skip link and it becomes visible; target exists
for (const [path,target] of [['/person.html?id=qa-p1','personPage'],['/partner.html?id=qa-partner-1','partnerPage'],['/login.html','loginMain'],['/account.html','accountMain'],['/support.html','supportMain']]){
  await withPage(async p=>{ await p.goto(BASE+path,{waitUntil:'domcontentloaded'}); await p.waitForTimeout(1200); await p.keyboard.press('Tab'); await p.waitForTimeout(400);
    const r=await p.evaluate(t=>{const a=document.activeElement; const rc=a.getBoundingClientRect(); return {cls:a.className,href:a.getAttribute('href'),top:rc.top,visible:rc.top>=0&&rc.height>0,target:!!document.getElementById(t)};},target);
    say(r.cls==='skip'&&r.href==='#'+target&&r.visible&&r.target,`skip link on ${path} → ${JSON.stringify(r)}`); if(path==='/login.html') await p.screenshot({path:'/tmp/qa/verify/login-skip-390.png'}); }); }
// 4. footer hit areas on home
await withPage(async p=>{ await p.goto(BASE+'/home.html',{waitUntil:'networkidle'}); await p.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
  const r=await p.evaluate(()=>{const l=document.querySelector('.hfoot .flogo'); if(!l) return {none:true}; const rc=l.getBoundingClientRect(); const cs=getComputedStyle(l,'::after'); const x=rc.left-2,y=rc.top-2; const hit=document.elementFromPoint(x,y); const fl=document.querySelector('.hfoot .fl a'); const frc=fl.getBoundingClientRect(); const hit2=document.elementFromPoint(frc.left+5, frc.top-4); return {w:rc.width,h:rc.height,afterInset:cs.inset,outsideHitIsLogo:hit===l,footLinkH:frc.height,aboveHitIsLink:hit2===fl};});
  say(!r.none&&r.w===28&&r.outsideHitIsLogo,'footer monogram 28px visual but ::after extends hit area '+JSON.stringify(r)); say(r.footLinkH>=32,'footer text link tap height >= 32px (was 20): '+r.footLinkH);
  await p.screenshot({path:'/tmp/qa/verify/home-footer-390.png'}); });
// 5. login rules sheet copy
await withPage(async p=>{ await p.goto(BASE+'/login.html',{waitUntil:'domcontentloaded'}); await p.waitForTimeout(1200); await p.click('#rulesBtn'); await p.waitForTimeout(400);
  const r=await p.evaluate(()=>({txt:document.querySelector('#shRules .cap').textContent.trim(), open:document.getElementById('shRules').classList.contains('on')||getComputedStyle(document.getElementById('shRules')).transform!=='none', btn:document.querySelector('#shRules a.btn').textContent.trim()}));
  say(/هنوز منتشر نشده/.test(r.txt)&&!/در صفحهٔ پشتیبانی است/.test(r.txt),'rules sheet is honest: '+r.txt.slice(0,60)); await p.screenshot({path:'/tmp/qa/verify/login-rules-390.png'}); });
// 6. og:image person/partner + 404 webp served
await withPage(async p=>{ for (const path of ['/person.html?id=qa-p1','/partner.html?id=qa-partner-1','/partner.html?id=qa partner/2 ü']){ await p.goto(BASE+encodeURI(path),{waitUntil:'networkidle'}); const og=await p.evaluate(()=>document.querySelector('meta[property="og:image"]')?.content||''); say(!!og,`og:image on ${path}: ${og}`);} 
  const reqs=[]; p.on('response',r=>{ if(/404-art/.test(r.url())) reqs.push(r.url().split('/').pop()+':'+r.status()); }); await p.goto(BASE+'/no-such-page-qa.html',{waitUntil:'networkidle'}); say(reqs.some(r=>r.startsWith('404-art.webp:200'))&&!reqs.some(r=>r.startsWith('404-art.png')),'404 page loads webp only: '+reqs.join(',')); });
console.log(out.filter(l=>l.startsWith('PASS')).length+' passed, '+out.filter(l=>l.startsWith('FAIL')).length+' failed');
