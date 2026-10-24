const {launchBrowser}=require(process.env.NORA_REPO_UI+'/tools/browser-launch.cjs');
(async()=>{const b=await launchBrowser();const page=await b.newPage();const out=process.argv[2];
  for(const [label,origin] of [['guest','http://127.0.0.1:8001'],['member','http://127.0.0.1:8090']]){
    for(const [w,h] of [[1440,900],[1024,768],[390,844],[360,800]]){
      await page.setViewportSize({width:w,height:h});await page.goto('about:blank');await page.goto(origin+'/account.html',{waitUntil:'load'});await page.waitForTimeout(2500);
      const r=await page.evaluate(()=>{const sb=document.querySelector('#supBar');const tb=document.querySelector('.tabbar');const sbr=sb.getBoundingClientRect();const tbr=tb.getBoundingClientRect();
        // overlap test: scroll through page in steps; any element center under supbar? supbar is in flow now, so check fixed elements only: tabbar vs last content
        const fixed=[...document.querySelectorAll('*')].filter(e=>getComputedStyle(e).position==='fixed').map(e=>e.className||e.tagName);
        return {sw:document.documentElement.scrollWidth,vw:innerWidth,sh:document.documentElement.scrollHeight,supPos:getComputedStyle(sb).position,supHidden:sb.hidden,fixed,supTop:Math.round(sbr.top),tabTop:Math.round(tbr.top)}});
      // scroll to bottom: supbar fully visible above tabbar?
      await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));await page.waitForTimeout(300);
      const bottom=await page.evaluate(()=>{const sb=document.querySelector('#supBar').getBoundingClientRect();const tb=document.querySelector('.tabbar').getBoundingClientRect();const foot=document.querySelector('footer.hfoot').getBoundingClientRect();const tl=document.querySelector('p.trustline.center');const tlr=tl?tl.getBoundingClientRect():null;return {supBottom:Math.round(sb.bottom),footBottom:Math.round(foot.bottom),trustBottom:tlr?Math.round(tlr.bottom):null,tabTop:Math.round(tb.top),ok:sb.bottom<=tb.top&&foot.bottom<=tb.top&&(!tlr||tlr.bottom<=tb.top+1)}});
      console.log(label,w+'x'+h,JSON.stringify(r),'bottom',JSON.stringify(bottom));
      await page.evaluate(()=>window.scrollTo(0,0));await page.waitForTimeout(200);
      await page.screenshot({path:`${out}-account-${label}-${w}.png`});
      await page.screenshot({path:`${out}-account-${label}-${w}-full.png`,fullPage:true});
    }
  }
  await b.close();})().catch(e=>{console.error(e);process.exit(1)});
