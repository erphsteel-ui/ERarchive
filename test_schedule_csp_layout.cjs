const assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 const base=process.env.TEST_BASE_URL||'http://127.0.0.1:8098';
 for(const role of ['admin','viewer']){const context=await browser.newContext({viewport:{width:1600,height:900}}),page=await context.newPage();const violations=[];page.on('console',msg=>{if(/Applying inline style/.test(msg.text()))violations.push(msg.text())});
 if(role==='admin')assert.equal((await context.request.post(base+'/api/login',{data:{name:'layout-test',password:'layout-test-password'}})).status(),200);
 const rows=[['c','당사','공통'],['p','당사','포항'],['d','당사','당진'],['l','노동계','공통'],['a','계열사','공통'],['g','그룹사','공통'],['o','기타','기타']].map(([id,group,name])=>({id,group,name}));
 await page.route('**/api/schedule?**',route=>route.fulfill({json:{month:'2026-11',rows,events:rows.flatMap(r=>Array.from({length:4},(_,i)=>({id:r.id+i,row:r.id,title:'사무 기획 회계 감사 교육',start:'2026-11-05',end:'2026-11-06',kind:'교육',status:'예정'}))),day_orders:{}}}));
 const response=await page.goto(base);assert.match(response.headers()['content-security-policy'],/style-src 'self'/);await page.waitForFunction(()=>typeof showSchedule==='function'&&typeof user!=='undefined');await page.waitForLoadState('networkidle');await page.evaluate(async()=>{scheduleMonth='2026-11';await showSchedule(false)});await page.locator('tr[data-schedule-row="pohang"]').waitFor();await page.waitForTimeout(100);
 const sizes=await page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('#scheduleMain tr[data-schedule-row]')].map(tr=>{const td=tr.querySelector('td[data-calendar-date="2026-11-05"]'),day=td.querySelector('.calendar-day'),bottom=day.getBoundingClientRect().bottom-parseFloat(getComputedStyle(day).paddingBottom);return [tr.dataset.scheduleRow,{height:tr.getBoundingClientRect().height,slots:getComputedStyle(tr).getPropertyValue('--row-slots'),fits:[...td.querySelectorAll('.schedule-event')].every(card=>card.getBoundingClientRect().bottom<=bottom+1)}]})));
 console.log(role,sizes,'inline violations:',violations.length);
 assert(sizes.common.height>sizes.affiliate.height*2,JSON.stringify(sizes));assert(sizes.otherbranch.height>sizes.affiliate.height*2,JSON.stringify(sizes));assert(sizes.pohang.fits&&sizes.common.fits&&sizes.otherbranch.fits,'third card clipped');assert.equal(violations.length,0);
 await context.close();
 }
 console.log('PASS: full application with server CSP, admin/viewer rows and three visible cards');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
