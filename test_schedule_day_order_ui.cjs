const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 const page=await browser.newPage();await page.setContent('<dialog id="calendarDayDialog"><h2 id="calendarDayHeading"></h2><div id="calendarDayList"></div></dialog>');
 await page.evaluate(()=>{window.$=s=>document.querySelector(s);window.esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));window.user={role:'admin'};window.scheduleMonth='2026-11';window.scheduleData={rows:[{id:'1',group:'당사',name:'포항'}],events:['가','나','다'].map((title,i)=>({id:String(i),title,row:'1',start:'2026-11-05',end:'2026-11-05',status:'예정'})),day_orders:{}};window.scheduleVisibleDates=()=>['2026-11-01'];window.calendarEventLabel=(g,e)=>e.title;window.openScheduleEvent=()=>{};window.toast=()=>{};window.showSchedule=async()=>{};window.api=async(path,body)=>{window.sent={path,body};scheduleData.day_orders[body.date+'|'+body.group]=body.ids;return {ok:true}}});
 const js=fs.readFileSync('static/schedule.js','utf8');await page.addScriptTag({content:js.slice(js.indexOf('function calendarGroups(){'),js.indexOf('const SCHEDULE_ACTORS='))+js.slice(js.indexOf('function openCalendarDay('),js.indexOf('function renderScheduleCandidates('))});
 await page.evaluate(()=>openCalendarDay('pohang','2026-11-05'));
 await page.locator('[data-move-index="2"][data-move-direction="-1"]').click();await page.locator('[data-move-index="1"][data-move-direction="-1"]').click();
 assert.deepEqual(await page.locator('[data-day-event] b').allTextContents(),['다','가','나']);await page.locator('#scheduleOrderSave').click();
 assert.deepEqual((await page.evaluate(()=>sent)).body.ids,['2','0','1']);
 assert.deepEqual(await page.evaluate(()=>calendarDayEvents(calendarGroups().find(g=>g.id==='pohang'),'2026-11-05').map(e=>e.title).slice(0,2)),['다','가']);
 await page.evaluate(()=>{user.role='viewer';openCalendarDay('pohang','2026-11-05')});assert.equal(await page.locator('[data-move-index]').count(),0);assert.deepEqual(await page.locator('[data-day-event] b').allTextContents(),['다','가','나']);
 console.log('PASS: admin can reorder hidden events and viewer sees shared ordering');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
