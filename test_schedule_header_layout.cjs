const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 for(const width of [1600,1100,390])for(const role of ['admin','viewer']){
  const page=await browser.newPage({viewport:{width,height:900}});await page.setContent(`<html><head></head><body class="${role==='viewer'?'viewerrole':''}"><main><div id="schedulePanel"></div></main></body></html>`);
  await page.addStyleTag({content:fs.readFileSync('static/style.css','utf8')});await page.addStyleTag({content:fs.readFileSync('static/theme.css','utf8')});
  await page.evaluate(role=>{window.$=s=>document.querySelector(s);window.esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');window.user={role};window.scheduleData={pending:[]};window.scheduleReview=false;window.scheduleMonth='2026-10';window.scheduleZoom=false;window.scheduleSources=[{done:false},{done:false}];window.scheduleTodayISO=()=> '2026-10-30';window.called=[];window.showSchedule=x=>called.push('show:'+x);window.prepareSchedulePrint=()=>called.push('print');window.copyScheduleWeek=()=>called.push('copy');window.openScheduleEvent=()=>called.push('add');window.openScheduleRows=()=>called.push('rows');window.renderScheduleGrid=()=>{};window.refreshScheduleDDays=()=>{};window.armScheduleDDayTimer=()=>{};window.renderScheduleReview=()=>{}},role);
  let js=fs.readFileSync('static/schedule.js','utf8');await page.addScriptTag({content:js.slice(js.indexOf('function renderSchedule(){'),js.indexOf('function scheduleKoreanDate('))});
  await page.evaluate(()=>{renderSchedule();const d=document.querySelector('#scheduleDDays');d.hidden=false;d.innerHTML='<button class="schedule-dday-badge schedule-dday-soon"><span class="schedule-dday-title">파업</span><strong>D-3</strong></button><button class="schedule-dday-badge"><span class="schedule-dday-title">워크샵</span><strong>D-5</strong></button>'});
  assert.equal(await page.locator('#scheduleFull').getAttribute('aria-pressed'),'true');assert.equal(await page.locator('.schedule-month-group').count(),1);assert.equal(await page.locator('.schedule-utilities #scheduleCopyWeek').count(),1);
  if(role==='admin'){assert.equal(await page.locator('.schedule-review-count').textContent(),'2건');await page.locator('#scheduleView').click();assert((await page.evaluate(()=>called)).includes('show:true'))}
  if(width===1600){const x=await page.evaluate(()=>{let h=document.querySelector('.schedule-header').getBoundingClientRect(),d=document.querySelector('#scheduleDDays').getBoundingClientRect();return {delta:Math.abs((h.left+h.width/2)-(d.left+d.width/2)),display:getComputedStyle(document.querySelector('.schedule-header')).display}});assert.equal(x.display,'grid');assert(x.delta<2)}
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('#scheduleCopyWeek').click();assert((await page.evaluate(()=>called)).includes('copy'));await page.locator('#scheduleTwoWeeks').click();assert((await page.evaluate(()=>called)).includes('show:false'));
  await page.close();
 }
 console.log('PASS: header center, responsive toolbar, admin/viewer actions and active state');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
