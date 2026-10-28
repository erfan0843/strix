const fs=require('node:fs'),path=require('node:path');
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const ORIGIN='http://127.0.0.1:8000';
const creds=fs.readFileSync('/home/user/strix/Final-Delivery/website/nora-ui/PREVIEW-LOGIN.local.md','utf8');
const pick=re=>(creds.match(re)||[])[1]; const O={user:pick(/مالک: `([^`]+)`/),pass:pick(/مالک: `[^`]+` \/ `([^`]+)`/)};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{const b=await launchBrowser(); const ctx=await b.newContext({viewport:{width:1280,height:800}}); const p=await ctx.newPage();
 await p.goto(ORIGIN+'/login.html?mode=staff&next=admin.html%23dash',{waitUntil:'load'}); await p.evaluate(()=>localStorage.removeItem('nora-admin'));
 await p.fill('#lgStaffUsername',O.user); await p.fill('#lgStaffPassword',O.pass); await p.click('#lgStaffSubmit'); await sleep(3000);
 const go=await p.$('text=رفتن به پنل مدیریت'); if(go){await p.evaluate(el=>el.click(),go); await sleep(3000);} await sleep(1500);
 const out={};
 out.dashUnnamed=await p.evaluate(()=>[...document.querySelectorAll('button')].filter(b=>!b.textContent.trim()&&!b.getAttribute('aria-label')&&!b.title).map(b=>b.outerHTML.slice(0,120)));
 out.scriptPin=await p.evaluate(()=>[...document.scripts].map(s=>s.getAttribute('src')).filter(s=>/admin\.js/.test(s)));
 for(const h of ['#nonexistent-section','#posts','#cert','#reports','#settings']){await p.goto('about:blank'); await p.goto(ORIGIN+'/admin.html'+h,{waitUntil:'load'}); await sleep(3000); out['hash '+h]=await p.evaluate(()=>location.hash+' | '+document.title);}
 await p.goto('about:blank'); await p.goto(ORIGIN+'/admin.html#dash',{waitUntil:'load'}); await sleep(3000); await p.evaluate(()=>document.querySelector('[data-dashx-map]').click()); await sleep(1500);
 out.mapUnnamed=await p.evaluate(()=>[...document.querySelectorAll('button')].filter(b=>!b.textContent.trim()&&!b.getAttribute('aria-label')&&!b.title).length);
 await p.screenshot({path:process.argv[2]+'/fix-01-map-aria.png'});
 fs.writeFileSync(process.argv[2]+'/fix-verify-results.json',JSON.stringify(out,null,2)); console.log(JSON.stringify(out,null,1)); await b.close();})();
