// Product audit: screenshots + first-viewport density metrics for many pages/roles. Args: outdir
const { launchBrowser } = require(process.env.NORA_REPO_UI + '/tools/browser-launch.cjs');
const fs=require('fs'); const sleep = ms => new Promise(r => setTimeout(r, ms));
const O={guest:'http://127.0.0.1:8001',owner:'http://127.0.0.1:8000',manager:'http://127.0.0.1:8080',member:'http://127.0.0.1:8090'};
const IDS=JSON.parse(process.env.SEED_IDS||'{}');
const PAGES=[
 ['guest','home','/home.html'],['guest','events','/events.html'],['guest','event-upcoming','/event.html?id='+IDS.upcoming],['guest','event-paid','/event.html?id='+IDS.paid],
 ['guest','account-guest','/account.html'],['guest','support','/support.html'],['guest','builder-guest','/builder.html'],['guest','login','/login.html'],
 ['member','account-member','/account.html'],['member','account-regs','/account.html#regs'],['member','account-events','/account.html#events'],
 ['owner','dash','/admin.html#dash'],['owner','events-list','/admin.html#events'],['owner','newev','/admin.html#newev'],
 ['owner','event-hub','/admin.html#event='+IDS.paid],['owner','event-regs','/admin.html#event='+IDS.paid+'&tab=regs'],['owner','event-pay','/admin.html#event='+IDS.paid+'&tab=pay'],
 ['owner','edit-main','/admin.html#edit='+IDS.upcoming+'&sec=main'],['owner','users','/admin.html#users'],['owner','forms','/admin.html#forms'],['owner','reports','/admin.html#reports'],['owner','settings','/admin.html#settings'],
 ['owner','builder','/builder.html'],['owner','person','/person.html'],
 ['manager','m-dash','/admin.html#dash'],['manager','m-events','/admin.html#events'],['manager','m-event-hub','/admin.html#event='+IDS.paid],['manager','m-users','/admin.html#users'],
];
const SIZES=[[1440,900],[1024,768],[390,844],[360,800]];
(async()=>{const out=process.argv[2]; fs.mkdirSync(out,{recursive:true}); const b=await launchBrowser(); const page=await b.newPage(); page.on('dialog',d=>d.accept());
 const rows=[];
 for(const [role,name,path] of PAGES){ for(const [w,h] of SIZES){ if((w===1024||w===360)&&!/home|dash|event-hub|account-member|events-list|builder$/.test(name)) continue;
   await page.setViewportSize({width:w,height:h}); await page.goto('about:blank'); try{ await page.goto(O[role]+path,{waitUntil:'load'}); }catch(e){ rows.push({role,name,w,err:String(e).slice(0,80)}); continue } await sleep(3000);
   const m=await page.evaluate(()=>{const vis=el=>{const r=el.getBoundingClientRect(); if(!r.width||!r.height) return false; const cs=getComputedStyle(el); return cs.visibility!=='hidden'&&cs.display!=='none'&&r.top<innerHeight&&r.bottom>0};
     const q=s=>[...document.querySelectorAll(s)].filter(vis);
     const txt=q('h1,h2,h3,.head,.sh-title,.ph-title').map(e=>e.textContent.trim().replace(/\s+/g,' ').slice(0,30));
     const dup=txt.filter((t,i)=>txt.indexOf(t)!==i);
     return {sw:document.documentElement.scrollWidth, sh:document.documentElement.scrollHeight, btn:q('button,a.btn,[role=button]').length, links:q('a[href]').length,
       cards:q('.card,.tile,.glass,.evcard,.panel,.sheet-card,.box,.stat').length, chips:q('.chip,.tag,.pill,.badge,.state-chip').length, headings:txt.length, dupHeadings:dup, tabs:q('[role=tab],.tabs>*,.seg>*,.tabbar a,.tabbar button').length,
       details:q('details').length, pTextLen:q('p,small,.desc,.sub').reduce((a,e)=>a+e.textContent.trim().length,0), nav:q('nav').length, inputs:q('input,select,textarea').length};});
   rows.push({role,name,w,...m});
   await page.screenshot({path:`${out}/${name}-${w}.png`}); if(w===1440||w===390) await page.screenshot({path:`${out}/${name}-${w}-full.png`,fullPage:true});
   console.log(role,name,w,JSON.stringify(m));
 }}
 fs.writeFileSync(out+'/metrics.json',JSON.stringify(rows,null,1)); await b.close();})().catch(e=>{console.error(e);process.exit(1)});
