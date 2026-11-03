const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 for(const width of [1440,800,390])for(const viewer of [false,true]){
  const page=await browser.newPage({viewport:{width,height:900}});await page.setContent(fs.readFileSync('templates/index.html','utf8'));
  await page.addStyleTag({content:fs.readFileSync('static/style.css','utf8')});await page.addStyleTag({content:fs.readFileSync('static/theme.css','utf8')});
  await page.evaluate(viewer=>{document.querySelector('#workspace').hidden=false;document.querySelector('#login').hidden=true;document.body.className=viewer?'viewerrole':'';document.querySelector('#adminScheduleAlert').hidden=false;document.querySelector('#adminPublicationAlert').hidden=false;document.querySelector('#adminSyncStatus').textContent='최근 자동수집 시간 10:30';document.querySelector('#userLabel').textContent=viewer?'':'admin · 관리자'},viewer);
  let initial=null;for(const state of ['','schedule-open','news-open','memos-open','financials-open','regulations-open']){
   const bounds=await page.evaluate(state=>{for(const x of ['schedule-open','news-open','memos-open','financials-open','regulations-open'])document.body.classList.remove(x);if(state)document.body.classList.add(state);const get=selector=>{const r=document.querySelector(selector).getBoundingClientRect();return [r.x,r.y,r.width,r.height]};return {header:get('.global-topbar'),nav:get('#readerTabs'),brand:get('.reader-home-title'),theme:get('#themeToggle'),overflow:document.documentElement.scrollWidth>innerWidth}},state);
   if(!initial)initial=bounds;else assert.deepEqual(bounds,initial,`header moved: ${width}, ${viewer}, ${state}`);assert.equal(bounds.header[3],52);assert.equal(bounds.nav[3],44);assert.equal(bounds.overflow,false);
  }
  assert.equal(await page.locator('#archiveContent .archive-page-heading').count(),1);await page.close();
 }
 console.log('PASS: stable global header and navigation across all tabs, roles and widths');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
