const {launchBrowser}=require(process.env.NORA_REPO_UI+'/tools/browser-launch.cjs');
(async()=>{const b=await launchBrowser();const page=await b.newPage();await page.setViewportSize({width:1024,height:768});
  await page.goto('http://127.0.0.1:8000/admin.html#events',{waitUntil:'load'});await page.waitForSelector('[data-ct-row]',{timeout:15000});
  await page.click('[data-ct-kind="articles"]').catch(async()=>{await page.getByText('مطالب',{exact:true}).first().click()});
  await page.waitForTimeout(1500);
  console.log(JSON.stringify(await page.evaluate(()=>[...document.querySelectorAll('[data-ct-row]')].slice(0,2).map(r=>({id:r.dataset.ctRow,visible:[...r.querySelectorAll(':scope > .row > .btn, :scope > .row > details > summary')].map(b=>b.textContent.trim()),menu:[...r.querySelectorAll('.actmenu-item')].map(b=>b.textContent.trim())})))));
  await page.screenshot({path:process.argv[2]});await b.close();})().catch(e=>{console.error(e);process.exit(1)});
