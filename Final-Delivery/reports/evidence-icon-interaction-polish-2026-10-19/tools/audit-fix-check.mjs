import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { launchBrowser } = require('/home/user/strix/Final-Delivery/website/nora-ui/tools/browser-launch.cjs');
const BASE='http://127.0.0.1:8000'; const OUT='/tmp/qa/fix';
const pw=fs.readFileSync('/tmp/nora-preview/owner-pw.txt','utf8').trim();
const r=await fetch(BASE+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json',Origin:BASE},body:JSON.stringify({username:'preview-owner',password:pw})});
const cookies=(r.headers.getSetCookie?r.headers.getSetCookie():[]).map(s=>{const [kv]=s.split(';');const i=kv.indexOf('=');return {name:kv.slice(0,i).trim(),value:kv.slice(i+1).trim(),domain:'127.0.0.1',path:'/'}});
console.log('login',r.status);
let fails=0;
async function shot(name,path,{w=390,h=844,theme='light',auth=false,wait=1400,check}={}){
  const b=await launchBrowser();
  const ctx=await b.newContext({viewport:{width:w,height:h},serviceWorkers:'block',locale:'fa-IR'});
  if(auth) await ctx.addCookies(cookies);
  await ctx.addInitScript(t=>{try{localStorage.setItem('nora-theme',t)}catch(e){}},theme);
  const p=await ctx.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(e.message.slice(0,100)));
  await p.goto(BASE+path,{waitUntil:'domcontentloaded'}); await p.waitForTimeout(wait);
  const m=await p.evaluate(()=>{const broken=[...document.querySelectorAll('use')].filter(u=>{const h=u.getAttribute('href')||'';return h.startsWith('#')&&!document.getElementById(h.slice(1))}).map(u=>u.getAttribute('href'));return {broken:[...new Set(broken)],url:location.pathname+location.search}});
  const extra=check?await p.evaluate(check):null;
  await p.screenshot({path:`${OUT}/${name}.png`});
  console.log(name,JSON.stringify({...m,errs,extra}));
  if(m.broken.length||errs.length) fails++;
  await ctx.close(); await b.close();
}
await shot('support-390','/support.html');
await shot('support-390-dark','/support.html',{theme:'dark'});
await shot('admin-1280','/admin.html',{w:1280,h:800,auth:true,wait:2500,check:()=>{const b=document.getElementById('admTheme');const vis=[...b.querySelectorAll('svg')].map(s=>getComputedStyle(s).display);return {vis,theme:document.documentElement.dataset.theme||''}}});
await shot('admin-1280-dark','/admin.html',{w:1280,h:800,auth:true,theme:'dark',wait:2500,check:()=>{const b=document.getElementById('admTheme');return [...b.querySelectorAll('svg')].map(s=>getComputedStyle(s).display)}});
const fcheck=()=>{const n=document.getElementById('next');if(!n)return 'no #next';const cs=getComputedStyle(n),a=getComputedStyle(n,'::after');return {overflow:cs.overflow,afterW:a.width,afterBg:a.backgroundImage.slice(0,20),afterOpacity:a.opacity,afterAnim:a.animationName,afterTransform:a.transform,start:n.closest('.botbar')?.className}};
await shot('form-start-390','/nora-pay-preview.html',{wait:2500,check:fcheck});
await shot('form-start-390-dark','/nora-pay-preview.html',{theme:'dark',wait:2500,check:fcheck});
await shot('form-start-1280','/nora-pay-preview.html',{w:1280,h:800,wait:2500,check:fcheck});
// hover on form start button must not break (hover state)
{const b=await launchBrowser();const ctx=await b.newContext({viewport:{width:1280,height:800},serviceWorkers:'block',locale:'fa-IR'});const p=await ctx.newPage();await p.goto(BASE+'/nora-pay-preview.html',{waitUntil:'domcontentloaded'});await p.waitForTimeout(2500);const n=p.locator('#next');await n.hover();await p.waitForTimeout(300);const a=await p.evaluate(()=>{const n=document.getElementById('next');const a=getComputedStyle(n,'::after');return {anim:a.animationName,w:a.width}});console.log('form-start hover',JSON.stringify(a));await p.screenshot({path:OUT+'/form-start-hover.png'});await ctx.close();await b.close();}
 console.log('fails',fails); process.exit(fails?1:0);
