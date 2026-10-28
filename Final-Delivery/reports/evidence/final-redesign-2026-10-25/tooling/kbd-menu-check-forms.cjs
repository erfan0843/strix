/* پذیرش ۱۴۰۵/۰۸/۰۳ — بند ۳: شمارش اقدام‌های مستقیمِ قابل‌دید هر ردیف فهرست رویدادها و بازکردن منوی «بیشتر» با صفحه‌کلید (مرورگر واقعی، فیکسچر ثابت) */
const path=require('path');
const {launchBrowser:launch}=require(process.env.NORA_REPO_UI+'/tools/browser-launch.cjs');
const OWNER='http://127.0.0.1:8000';
(async()=>{
  const browser=await launch();
  const out=[]; const page=await browser.newPage(); page.on('dialog',d=>d.accept());
  for(const w of [1440,390]){
    await page.setViewportSize({width:w,height:w>1000?900:844});
    await page.goto(OWNER+'/admin.html#forms',{waitUntil:'networkidle'});
    await page.waitForSelector('[data-fs-row]',{timeout:30000});
    const vis=await page.evaluate(()=>{
      const rows=[...document.querySelectorAll('[data-fs-row]')];
      const visible=el=>!!(el.offsetParent||el.getClientRects().length);
      return rows.map(r=>{
        const all=[...r.querySelectorAll('button,a.btn,summary')];
        const direct=all.filter(visible).map(e=>e.textContent.trim().replace(/\s+/g,' ').slice(0,20));
        const inMenu=[...r.querySelectorAll('details.actmenu button,details.actmenu a')].map(e=>e.textContent.trim().replace(/\s+/g,' ').slice(0,24));
        return {direct,inMenu};});
    });
    /* صفحه‌کلید: Tab تا summary «بیشتر» ردیف اول، Enter، سپس Tab به اولین گزینه و Escape */
    await page.focus('[data-fs-row] details.actmenu summary');
    await page.keyboard.press('Enter');
    const opened=await page.evaluate(()=>{const d=document.querySelector('[data-fs-row] details.actmenu'); return d&&d.open});
    const focusedOnOpen=await page.evaluate(()=>{const a=document.activeElement; return a&&a.closest('details.actmenu')?a.tagName+':'+a.textContent.trim().slice(0,24):''});
    await page.keyboard.press('Tab');
    const focusedInMenu=await page.evaluate(()=>{const a=document.activeElement; return !!(a&&a.closest('details.actmenu')&&a.tagName!=='SUMMARY')?a.textContent.trim().slice(0,24):''});
    const menuBox=await page.evaluate(()=>{const m=document.querySelector('[data-fs-row] details.actmenu[open] .menu'); if(!m) return null; const b=m.getBoundingClientRect(); return {l:Math.round(b.left),r:Math.round(b.right),w:Math.round(b.width),vw:innerWidth}});
    await page.keyboard.press('Escape');
    const closedByEsc=await page.evaluate(()=>{const d=document.querySelector('[data-fs-row] details.actmenu'); return d&&!d.open});
    await page.screenshot({path:path.join(process.argv[2]||'.',`kbd-menu-${w}.png`)});
    out.push({w,rows:vis,opened,focusedOnOpen,focusedInMenu,menuBox,closedByEsc});
    await page.goto('about:blank');
  }
  console.log(JSON.stringify(out,null,1));
  await browser.close();
})().catch(e=>{console.error('FAIL',e);process.exit(1)});
