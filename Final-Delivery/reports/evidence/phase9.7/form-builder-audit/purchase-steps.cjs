'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const { launchBrowser } = require(path.resolve(process.env.NORA_UI_DIR || '.', 'tools/browser-launch.cjs'));
const ORIGIN='http://127.0.0.1:8000', OUT=process.argv[2], BOT_TOKEN=process.env.NORA_BALE_BOT_TOKEN, FORM=process.env.PURCHASE_FORM_FULL;
fs.mkdirSync(OUT,{recursive:true}); const sleep=ms=>new Promise(r=>setTimeout(r,ms)); const log=[]; const say=l=>{log.push(l);fs.writeFileSync(path.join(OUT,'purchase-steps.txt'),log.join('\n')+'\n')};
function initData(userId){const f={auth_date:String(Math.floor(Date.now()/1000)),query_id:'p97b-'+userId+'-'+Date.now(),user:JSON.stringify({id:userId,first_name:'آزمایش'})};const c=Object.keys(f).sort().map(k=>`${k}=${f[k]}`).join('\n');const s=crypto.createHmac('sha256','WebAppData').update(BOT_TOKEN).digest();const h=crypto.createHmac('sha256',s).update(c).digest('hex');return new URLSearchParams({...f,hash:h}).toString()}
const txt=(p,s,n=240)=>p.evaluate(([s,n])=>{const e=document.querySelector(s);return e?e.innerText.replace(/\s+/g,' ').trim().slice(0,n):null},[s,n]);
const st=p=>p.evaluate(()=>({active:(document.querySelector('.screen.on')||{}).id,toast:(document.querySelector('#toast')||{innerText:''}).innerText.trim().slice(0,120),body:(document.querySelector('.screen.on')||{innerText:''}).innerText.replace(/\s+/g,' ').trim().slice(0,300)}));
(async()=>{
 for(const mobile of [false,true]){const tag=mobile?'mobile':'desktop';
  const browser=await launchBrowser(); const ctx=await browser.newContext(mobile?{viewport:{width:390,height:844},deviceScaleFactor:2,isMobile:true,hasTouch:true,reducedMotion:'reduce'}:{viewport:{width:1280,height:800},reducedMotion:'reduce'}); const page=await ctx.newPage();
  const api=[]; page.on('response',r=>{if(r.url().includes('/api/'))api.push(`${r.request().method()} ${r.url().replace(ORIGIN,'').split('?')[0].replace(FORM,'{id}')} → ${r.status()}`)});
  await page.goto(ORIGIN+'/events.html',{waitUntil:'load'}); const s=await page.evaluate(async d=>(await fetch('/api/auth/bale-mini-app',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({init_data:d})})).status,initData(91012)); say(`## ${tag} member 91012 login ${s}`);
  await page.goto(ORIGIN+'/form.html?fid='+FORM,{waitUntil:'load'}); await sleep(2500);
  await page.evaluate(()=>document.querySelector('#next').click()); await sleep(1200);
  await page.evaluate(()=>{const i=document.querySelector('.screen.on input:not([type=hidden])'); if(i){i.value='آزمایش ۹.۷ خریدار'; i.dispatchEvent(new Event('input',{bubbles:true})); i.dispatchEvent(new Event('change',{bubbles:true}))}}); await sleep(300);
  await page.evaluate(()=>document.querySelector('#next').click()); await sleep(1200);
  let c=await st(page); say(`- after name: ${c.active}`);
  const ticked=await page.evaluate(()=>{const box=[...document.querySelectorAll('#u8 input[type=checkbox], #u8 [role=checkbox], #u8 .fin-item, #u8 [data-fin]')]; const first=box[0]; if(first){first.click(); return first.outerHTML.slice(0,120)} return null}); await sleep(500);
  say(`- ticked item: ${ticked}; bill «${await txt(page,'#u8',200)}»`);
  await page.evaluate(()=>{const b=[...document.querySelectorAll('#paymentMethodList [data-method]')].find(x=>x.dataset.method==='card_transfer'); if(b)b.click()}); await sleep(500);
  await page.screenshot({path:path.join(OUT,`${tag}-p1-u8-selected.png`)});
  await page.evaluate(()=>document.querySelector('#next').click()); await sleep(1500); c=await st(page); say(`- next → ${c.active}; toast «${c.toast}»; body «${c.body}»`);
  await page.screenshot({path:path.join(OUT,`${tag}-p2-${c.active}.png`)});
  if(c.active==='u9'){ say(`  payment details: total «${await txt(page,'#paymentTransferTotal',60)}» card «${await txt(page,'#paymentBankCardWrap',200)}» note «${await txt(page,'#paymentStepNote',200)}» instr «${await txt(page,'#paymentInstructionsBox',200)}» CTA «${await txt(page,'#next',40)}»`);
    await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight)); await page.screenshot({path:path.join(OUT,`${tag}-p3-u9-bottom.png`)});
    if(!mobile){ await page.evaluate(()=>document.querySelector('#next').click()); await sleep(2500); c=await st(page); say(`- submit → ${c.active}; toast «${c.toast}»; body «${c.body}»`); await page.screenshot({path:path.join(OUT,`${tag}-p4-${c.active}.png`)});
      if(c.active==='u11') say(`  receipt step: «${await txt(page,'#u11',400)}»; upload button «${await txt(page,'#serverReceiptUpload',40)}»; bale link «${await txt(page,'#receiptReviewBaleLink',60)}»`);
      await page.reload({waitUntil:'load'}); await sleep(2500); c=await st(page); say(`- reload after submit → ${c.active}; body «${c.body.slice(0,200)}»`); await page.screenshot({path:path.join(OUT,`${tag}-p5-reload-${c.active}.png`)});
      await page.goto(ORIGIN+'/account.html#payments',{waitUntil:'load'}); await page.reload({waitUntil:'load'}); await sleep(3500); say(`- account#payments: «${await txt(page,'main, body',420)}»`); await page.screenshot({path:path.join(OUT,`${tag}-p6-account-payments.png`)});
      await page.goto(ORIGIN+'/event.html?id=ev-dbbc5c5acb',{waitUntil:'load'}); await sleep(3500); say(`- event page purchase box: «${await txt(page,'[data-recording], #recording, main',400)}»`); await page.screenshot({path:path.join(OUT,`${tag}-p7-event-after-pending.png`)});
    }
  }
  const sum={}; api.forEach(l=>sum[l]=(sum[l]||0)+1); say(`- API: ${Object.entries(sum).map(([k,v])=>`${k}×${v}`).join('; ')}`); await browser.close(); }
 say('DONE');
})().catch(e=>{say('FATAL '+e.stack);process.exit(1)});
