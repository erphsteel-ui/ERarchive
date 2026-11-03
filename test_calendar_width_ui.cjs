const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 for(const role of ['admin','viewer'])for(const theme of ['dark','light']){
  const page=await browser.newPage({viewport:{width:1550,height:900}});
  await page.setContent(`<html data-theme="${theme}"><body class="${role==='viewer'?'viewerrole':''} schedule-print-ready"><div id="schedulePanel"><div id="scheduleMain"><div class="schedule-scroll"><table class="schedule-table compact-calendar"></table></div></div></div><section id="schedulePrintSheet"><table class="schedule-table"></table></section></body></html>`);
  await page.addStyleTag({content:fs.readFileSync('static/style.css','utf8')});await page.evaluate(css=>{const s=document.createElement('style');s.media='screen';s.textContent=css;document.head.append(s)},fs.readFileSync('static/theme.css','utf8'));
  await page.evaluate(role=>{window.scheduleData={rows:[{id:'a',group:'그룹사',name:'공통'}],events:[{id:'1',row:'a',start:'2026-10-02',end:'2026-10-06',title:'[트랜시스] 가나다라마바',kind:'회의',status:'예정'}],day_orders:{}};window.scheduleMonth='2026-10';window.scheduleZoom=false;window.scheduleAnchor='';window.user={role};window.esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))},role);
  const js=fs.readFileSync('static/schedule.js','utf8');await page.addScriptTag({content:js.slice(js.indexOf('function calendarGroups(){'),js.indexOf('function renderScheduleGrid(){'))});
  await page.evaluate(()=>{const screen=document.querySelector('#scheduleMain table'),print=document.querySelector('#schedulePrintSheet table');screen.innerHTML=compactCalendarHTML();print.innerHTML=compactCalendarHTML(true);sizeScheduleColumns(screen,scheduleVisibleDates());sizeScheduleColumns(print,scheduleVisibleDates(true))});
  assert.equal(await page.locator('#scheduleMain [data-event="1"]').count(),1);assert.equal(await page.locator('#scheduleMain [data-event="1"] .schedule-actor').innerText(),'[트랜시스]');
  const screen=await page.locator('#scheduleMain [data-event="1"]').evaluate(el=>{const b=el.querySelector('b'),r=document.createRange();r.setStart(b.firstChild,0);r.setEnd(b.firstChild,5);const rects=[...r.getClientRects()];const actor=el.querySelector('.schedule-actor');return {lines:rects.length,titleTop:b.getBoundingClientRect().top,actorBottom:actor.getBoundingClientRect().bottom,actorFits:actor.scrollWidth<=actor.clientWidth,border:getComputedStyle(el).borderLeftWidth}});
  assert(screen.titleTop>=screen.actorBottom);assert.equal(screen.border,'2px');
  assert.equal(await page.locator('#scheduleMain .schedule-org').first().evaluate(e=>Math.round(e.getBoundingClientRect().width)),48);
  await page.evaluate(()=>{const event=document.querySelector('#schedulePrintSheet .schedule-event'),replacement=document.createElement('div');replacement.className=event.className;while(event.firstChild)replacement.append(event.firstChild);event.replaceWith(replacement)});
  await page.emulateMedia({media:'print'});await page.locator('#schedulePrintSheet').evaluate(e=>e.style.width='1549px');
  const printed=await page.locator('#schedulePrintSheet .schedule-event').evaluate(el=>{const b=el.querySelector('b'),r=document.createRange();r.setStart(b.firstChild,0);r.setEnd(b.firstChild,5);const a=el.querySelector('.schedule-actor');return {lines:r.getClientRects().length,actorFits:a.scrollWidth<=a.clientWidth,titleTop:b.getBoundingClientRect().top,actorBottom:a.getBoundingClientRect().bottom,border:getComputedStyle(el).borderLeftWidth}});
  assert(printed.titleTop>=printed.actorBottom);assert.equal(printed.border,'2px');await page.close();
 }
 console.log('PASS: compact monthly and A3 layouts keep prefixes on separate lines');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
