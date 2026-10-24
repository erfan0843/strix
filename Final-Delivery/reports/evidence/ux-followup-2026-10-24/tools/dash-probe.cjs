const {launchBrowser}=require(process.env.NORA_REPO_UI+'/tools/browser-launch.cjs');
(async()=>{const b=await launchBrowser();const page=await b.newPage();const out=process.argv[2];
  for(const [w,h] of [[1440,900],[390,844]]){
    await page.setViewportSize({width:w,height:h});await page.goto('about:blank');await page.goto('http://127.0.0.1:8000/admin.html#dash',{waitUntil:'load'});
    await page.waitForSelector('[data-dashx-upcoming] .sh-link--action',{timeout:15000});await page.waitForTimeout(800);
    const el=page.locator('[data-dashx-upcoming] .sh-link--action');
    const box=await el.boundingBox();
    const cs=await el.evaluate(e=>{const c=getComputedStyle(e);return {color:c.color,bg:c.backgroundColor,h:e.offsetHeight,fs:c.fontSize}});
    console.log(w,'link box',JSON.stringify(box),JSON.stringify(cs));
    await el.scrollIntoViewIfNeeded();await page.screenshot({path:`${out}-dash-${w}.png`});
    await el.hover();await page.waitForTimeout(200);
    console.log(w,'hover',JSON.stringify(await el.evaluate(e=>{const c=getComputedStyle(e);return {bg:c.backgroundColor,deco:c.textDecorationLine}})));
    const vb=await el.boundingBox();const clip={x:Math.max(0,vb.x-240),y:Math.max(0,vb.y-30),width:Math.min(w,320),height:80};
    await page.screenshot({path:`${out}-dash-link-hover-${w}.png`,clip});
    await el.focus();await page.waitForTimeout(100);await page.screenshot({path:`${out}-dash-link-focus-${w}.png`,clip});
    await page.mouse.move(0,0);await el.click();await page.waitForTimeout(1200);
    console.log(w,'after click hash=',await page.evaluate(()=>location.hash),'list rows=',await page.evaluate(()=>document.querySelectorAll('[data-ct-row]').length));
  }
  await b.close();})().catch(e=>{console.error(e);process.exit(1)});
