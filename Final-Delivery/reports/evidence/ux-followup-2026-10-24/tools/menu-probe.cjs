// Row "more" menu probe: owner + manager, mouse/keyboard, outside click, Escape, mobile position
const {launchBrowser}=require(process.env.NORA_REPO_UI+'/tools/browser-launch.cjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const browser=await launchBrowser();const page=await browser.newPage();const out=process.argv[2];
  page.on('dialog',d=>{console.log('dialog:',d.message().slice(0,60));d.dismiss()});
  for(const [label,origin] of [['owner','http://127.0.0.1:8000'],['manager','http://127.0.0.1:8080']]){
    for(const [w,h] of [[1440,900],[390,844]]){
      await page.setViewportSize({width:w,height:h});await page.goto('about:blank');await page.goto(origin+'/admin.html#events',{waitUntil:'load'});
      await page.waitForSelector('[data-ct-row]',{timeout:15000});await sleep(800);
      const rows=await page.evaluate(()=>[...document.querySelectorAll('[data-ct-row]')].slice(0,3).map(r=>({id:r.dataset.ctRow,status:(r.querySelector('.tag')||{}).textContent,visible:[...r.querySelectorAll(':scope > .row > .btn, :scope > .row > details > summary')].map(b=>b.textContent.trim()),menu:[...r.querySelectorAll('.actmenu-item')].map(b=>b.textContent.trim())})));
      console.log(label,w,JSON.stringify(rows));
      await page.screenshot({path:`${out}-${label}-closed-${w}.png`});
      const sum=page.locator('[data-ct-row] details.actmenu > summary').first();
      if(await sum.count()){
        await sum.click();await sleep(200);
        const st=await page.evaluate(()=>{const d=document.querySelector('details.actmenu[open]');if(!d)return null;const m=d.querySelector('.actmenu-menu').getBoundingClientRect();return {open:true,focus:document.activeElement&&document.activeElement.textContent.trim(),expanded:d.querySelector('summary').getAttribute('aria-expanded'),menuLeft:Math.round(m.left),menuRight:Math.round(m.right),vw:innerWidth,sw:document.documentElement.scrollWidth}});
        console.log(label,w,'opened',JSON.stringify(st));
        await page.screenshot({path:`${out}-${label}-open-${w}.png`});
        await page.keyboard.press('ArrowDown');await sleep(50);const f2=await page.evaluate(()=>document.activeElement.textContent.trim());
        await page.keyboard.press('Escape');await sleep(100);
        const afterEsc=await page.evaluate(()=>({open:!!document.querySelector('details.actmenu[open]'),focus:document.activeElement&&document.activeElement.textContent.trim()}));
        console.log(label,w,'arrow→',f2,'esc→',JSON.stringify(afterEsc));
        await sum.click();await sleep(150);await page.mouse.click(5,Math.round(h/2));await sleep(150);
        console.log(label,w,'outside click closes:',await page.evaluate(()=>!document.querySelector('details.actmenu[open]')));
        // keyboard open: focus summary and press Enter
        await sum.focus();await page.keyboard.press('Enter');await sleep(150);
        console.log(label,w,'keyboard open:',await page.evaluate(()=>!!document.querySelector('details.actmenu[open]')),'focus:',await page.evaluate(()=>document.activeElement.textContent.trim()));
        await page.keyboard.press('Escape');await sleep(100);
      }
    }
  }
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
