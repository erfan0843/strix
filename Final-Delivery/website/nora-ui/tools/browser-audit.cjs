// Optional development-only QA; never part of the application boot path.
// See AUDIT-2026-10-11.fa.md for exact dependency versions and fixture setup.
const path = require('node:path');
const os = require('node:os');
const fs = require('node:fs');
const { createRequire } = require('node:module');
const repoRoot = path.resolve(__dirname, '../../../..');
const dependencyRequire = process.env.NORA_QA_DEPENDENCIES
  ? createRequire(path.join(path.resolve(process.env.NORA_QA_DEPENDENCIES), 'package.json'))
  : createRequire(path.join(repoRoot, 'package.json'));
const { chromium: pw } = dependencyRequire('playwright-core');
const axePath = process.env.NORA_QA_AXE_DEPENDENCIES
  ? path.join(path.resolve(process.env.NORA_QA_AXE_DEPENDENCIES), 'node_modules/axe-core/axe.min.js')
  : dependencyRequire.resolve('axe-core/axe.min.js');
const qaRoot = path.resolve(__dirname, '../.local/qa');
const fixturePath = process.env.NORA_QA_FIXTURE_FILE || path.join(qaRoot, 'fixture.json');
const reportPath = process.env.NORA_QA_REPORT || path.join(qaRoot, 'browser-audit.json');
async function launchBrowser() {
  if (process.env.NORA_QA_BROWSER === 'sparticuz') {
    const mod = dependencyRequire('@sparticuz/chromium');
    const chromium = mod.default || mod;
    if (process.platform !== 'linux') throw new Error('Sparticuz fallback is Linux-only; use managed Chromium or a local Chrome executable.');
    const moduleRoot = path.resolve(path.dirname(dependencyRequire.resolve('@sparticuz/chromium')), '..');
    const { inflate } = await import(require('node:url').pathToFileURL(path.join(moduleRoot, 'build/lambdafs.js')).href);
    await inflate(path.join(moduleRoot, 'bin/al2023.tar.br'));
    const executablePath = await chromium.executablePath();
    const env = { ...process.env };
    const libraries = path.join(os.tmpdir(), 'al2023/lib');
    if (fs.existsSync(libraries)) env.LD_LIBRARY_PATH = [libraries, env.LD_LIBRARY_PATH].filter(Boolean).join(path.delimiter);
    const fonts = path.join(os.tmpdir(), 'fonts');
    if (fs.existsSync(fonts)) env.FONTCONFIG_PATH = fonts;
    return pw.launch({ executablePath, headless: true,
      args: chromium.args.filter(arg => !['--single-process', '--disable-web-security', '--allow-running-insecure-content'].includes(arg)), env });
  }
  return pw.launch({ headless: true,
    ...(process.env.NORA_QA_CHROMIUM_EXECUTABLE ? { executablePath: process.env.NORA_QA_CHROMIUM_EXECUTABLE } : {}),
    ...(process.env.NORA_QA_BROWSER_CHANNEL ? { channel: process.env.NORA_QA_BROWSER_CHANNEL } : {}) });
}
function localOrigin(value) {
  const url = new URL(value);
  if (!['http:', 'https:'].includes(url.protocol) || !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)
      || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('Browser QA requires a loopback origin, never a live external target.');
  }
  return url.origin;
}
const publicOrigin = localOrigin(process.env.NORA_QA_PUBLIC_URL || 'http://127.0.0.1:8000');
const fixtureOrigin = localOrigin(process.env.NORA_QA_FIXTURE_URL || 'http://127.0.0.1:8001');
const pages=['home.html','events.html','account.html','login.html','support.html','admin.html','builder.html','create.html','form.html','event.html','person.html','post.html','404.html','offline.html','loading-preview.html','final-page-review.html','nora-pay-preview.html','missing-audit-page.html'];
const fixture=JSON.parse(fs.readFileSync(fixturePath, 'utf8'));let browser;const results=[];
async function run(name,width,theme,actor='guest',modal){
 const origin=actor==='guest'?publicOrigin:fixtureOrigin,base=new URL(origin);
 const context=await browser.newContext({viewport:{width,height:900},colorScheme:theme==='dark'?'dark':'light',serviceWorkers:'block'});
 if(actor!=='guest')await context.addCookies([{name:fixture[actor+'_cookie_name'],value:fixture[actor+'_cookie'],url:origin,httpOnly:true,sameSite:'Strict'}]);
 await context.addInitScript(theme=>{localStorage.setItem('nora-theme',theme);if(document.documentElement)document.documentElement.dataset.theme=theme;},theme);
 const page=await context.newPage(),errors=[],writes=[],api=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/'))api.push({path:u.pathname,status:r.status()});});
 await page.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(!['GET','HEAD'].includes(r.method())){writes.push({method:r.method(),path:u.pathname});return route.abort();}if(u.origin===base.origin)return route.continue();return route.abort();});
 try{
  const response=await page.goto(origin+'/'+name,{waitUntil:'domcontentloaded',timeout:15000});
  await page.waitForFunction(()=>document.readyState==='complete',{timeout:10000}).catch(()=>{});
  await page.waitForFunction(()=>![...document.querySelectorAll('main')].some(el=>el.inert),{timeout:10000}).catch(()=>{});
  await page.evaluate(()=>document.fonts.ready);
  if(actor==='member'&&name.includes('#events'))await page.waitForSelector('.server-registration',{timeout:10000});
  await page.evaluate(theme=>{document.documentElement.dataset.theme=theme;},theme);
  await page.waitForFunction(()=>!document.getAnimations().some(a=>a.playState==='running'&&Number.isFinite(a.effect?.getTiming().iterations)),{timeout:3000}).catch(()=>{});
  let keyboard;
  if(modal){
   const opened=await page.evaluate(selector=>{const control=document.querySelector(selector),sheet=control?.closest('.sheet');if(!sheet)return false;const fn=window.NORA_UI?.uiOpen||window.NORA_UI?.sheet||window.NORA_UI?.openSheet||window.NORA_UI?.open;if(typeof fn!=='function')return false;fn(sheet.id);return sheet.id;},modal);
   if(!opened)throw new Error('modal control could not be opened: '+modal);
   await page.locator(modal).focus();const before=await page.locator(modal).getAttribute('aria-checked');await page.keyboard.press('Space');const after=await page.locator(modal).getAttribute('aria-checked');
   keyboard={opened,before,after,toggled:before!==after};
  }
  await page.addScriptTag({path:axePath});
  const info=await page.evaluate(async()=>{const a=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});return {
   lang:document.documentElement.lang,dir:document.documentElement.dir,theme:document.documentElement.dataset.theme,
   overflow:document.documentElement.scrollWidth>innerWidth,title:document.title,h1:[...document.querySelectorAll('h1')].filter(e=>e.getClientRects().length).map(e=>e.textContent.trim()),
   dataFixtureDownloaded:performance.getEntriesByType('resource').some(e=>new URL(e.name).pathname.endsWith('/data.js')),
   scripts:performance.getEntriesByType('resource').filter(e=>e.initiatorType==='script').map(e=>({file:new URL(e.name).pathname,encoded:e.encodedBodySize,decoded:e.decodedBodySize,transfer:e.transferSize})),
   closedSheetsFocusable:[...document.querySelectorAll('.sheet:not(.on)')].filter(s=>!s.inert).length,
   memberTestRecordVisible:document.body.textContent.includes('ثبت‌نام آزمون ممیزی — دادهٔ واقعی نیست'),
   violations:a.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,failureSummary:n.failureSummary}))})),incomplete:a.incomplete.map(i=>({id:i.id,count:i.nodes.length}))};});
  results.push({page:name,width,requestedTheme:theme,actor,modal,status:response.status(),...info,keyboard,errors,blockedWrites:writes,api});
  console.log(actor,width,theme,name,modal||'', 'overflow',info.overflow,'errors',errors.length,'axe',info.violations.map(v=>v.id).join(',')||'none',keyboard?'keyboard='+keyboard.toggled:'');
 }catch(e){results.push({page:name,width,requestedTheme:theme,actor,modal,error:e.message,errors,blockedWrites:writes});console.log('FAIL',actor,width,theme,name,e.message)}
 finally{await context.close();}
}
(async()=>{try{
 browser=await launchBrowser();
 console.log('Chromium',browser.version());
 for(const [width,theme]of [[390,'light'],[320,'light'],[1280,'light'],[390,'dark']])for(const name of pages)await run(name,width,theme);
 for(const width of [320,390,1280])for(const name of ['account.html','account.html#events'])await run(name,width,'light','member');
 await run('account.html#events',390,'dark','member');
 for(const name of ['admin.html','create.html','builder.html'])await run(name,390,'light','owner');
 for(const [name,control]of [['builder.html','#setWait'],['create.html','#fdReq']])await run(name,390,'light','owner',control);
 }finally{if(browser)await browser.close();fs.mkdirSync(path.dirname(reportPath), {recursive:true});fs.writeFileSync(reportPath,JSON.stringify(results,null,2));}
if(results.length!==84||results.some(r=>r.error||r.errors?.length||r.violations?.length||r.overflow||r.lang!=='fa'||r.dir!=='rtl'||r.theme!==r.requestedTheme||r.closedSheetsFocusable>0||r.page==='account.html'&&r.dataFixtureDownloaded||r.keyboard&&r.keyboard.toggled!==true||r.actor==='member'&&r.page.includes('#events')&&!r.memberTestRecordVisible))process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
