const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const opts={headless:true};if(process.env.USE_SERVER_CHROMIUM){const binary=require('@sparticuz/chromium').default;opts.executablePath=await binary.executablePath();opts.args=binary.args;}
 const browser=await chromium.launch(opts);try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto('http://127.0.0.1:8099');await page.locator('.schedule-table').waitFor();
 assert.equal(await page.locator('#archiveContent').isVisible(),true);assert.equal(await page.locator('#scheduleAdd').count(),0);
 await page.locator('#adminLogin').click();await page.locator('[name="name"]').fill('testadmin');await page.locator('[name="password"]').fill('test-password-123');await page.locator('#loginForm button.primary').click();await page.locator('#uploadButton').waitFor({state:'visible'});
 await page.locator('#scheduleReviewNav').click();await page.locator('.schedule-candidate').first().click();
 assert.equal(await page.locator('#scheduleEventForm [type="time"]').count(),0);assert.equal(await page.locator('#scheduleEventForm [name="place"]').count(),0);
 await page.locator('#scheduleEventForm [name="title"]').fill('월간 일정 테스트');await page.locator('#scheduleEventForm [name="row"]').selectOption('1');
 await page.locator('#scheduleEventForm [name="start"]').fill('2026-10-29');await page.locator('#scheduleEventForm [name="end"]').fill('2026-10-30');
 await page.locator('#scheduleEventForm button.primary').click();await page.waitForFunction(()=>!document.querySelector('#scheduleEventDialog').open);
 await page.locator('#scheduleNav').click();await page.locator('#scheduleMonth').fill('2026-10');await page.locator('#scheduleMonth').dispatchEvent('change');
 await page.locator('.schedule-event').filter({hasText:'월간 일정 테스트'}).waitFor();assert.equal(await page.locator('.schedule-event').filter({hasText:'월간 일정 테스트'}).locator('..').getAttribute('colspan'),'2');
 await page.locator('#scheduleRows').click();await page.locator('#scheduleRowAdd').click();await page.locator('#scheduleRowsBody input[aria-label="조직·사업장"]').last().fill('테스트 조직');await page.locator('#scheduleRowsSave').click();await page.waitForFunction(()=>!document.querySelector('#scheduleRowsDialog').open);
 assert.equal(await page.locator('.schedule-org').filter({hasText:'테스트 조직'}).count(),1);
 await page.locator('#scheduleAdd').click();await page.locator('#scheduleEventForm [name="title"]').fill('직접 추가 일정');await page.locator('#scheduleEventForm [name="row"]').selectOption('2');await page.locator('#scheduleEventForm button.primary').click();await page.waitForFunction(()=>!document.querySelector('#scheduleEventDialog').open);
 await page.screenshot({path:'/tmp/er-schedule-admin.png',fullPage:false});
 await page.locator('#logout').click();await page.locator('#adminLogin').waitFor({state:'visible'});await page.locator('#scheduleMonth').fill('2026-10');await page.locator('#scheduleMonth').dispatchEvent('change');
 await page.locator('.schedule-event').filter({hasText:'월간 일정 테스트'}).click();assert.equal(await page.locator('#scheduleEventForm').count(),0);assert.equal(await page.locator('#scheduleEventBody').getByText('월간 일정 테스트').count(),1);await page.locator('[data-close="scheduleEventDialog"]').click();
 await page.screenshot({path:'/tmp/er-schedule-reader.png',fullPage:false});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/tmp/er-schedule-mobile.png',fullPage:false});
 assert.equal(await page.locator('#archiveContent').isVisible(),true);
 await page.setViewportSize({width:1440,height:1000});
 assert.equal(await page.locator('#readerScheduleNav').count(),0);
 assert.equal(await page.locator('#schedulePanel').evaluate(el=>el.nextElementSibling.id),'archiveContent');
 assert.ok((await page.locator('#archiveContent').boundingBox()).y<750,'Archive must be reachable below compact grid');
 assert.equal(await page.locator('.schedule-org').filter({hasText:'당사 | 포항'}).count(),1);
 assert.equal(await page.locator('#schedulePanel').getByText('시간 미정').count(),0);
 await page.evaluate(()=>{window.print=()=>{window.printRequested=true}});await page.locator('#schedulePrint').click();assert.equal(await page.evaluate(()=>window.printRequested),true);
 await page.emulateMedia({media:'print'});
 assert.equal(await page.locator('#workspace').isVisible(),false);
 assert.equal(await page.locator('#schedulePrintSheet').isVisible(),true);
 assert.equal(await page.locator('#schedulePrintSheet thead th').count(),32);
 assert.equal(await page.locator('#schedulePrintSheet button').count(),0);
 assert.equal(await page.locator('#schedulePrintSheet').getByText('월간 일정 테스트',{exact:true}).count(),1);
 await page.pdf({path:'/tmp/er13-A3-test.pdf',preferCSSPageSize:true,printBackground:true});
 await page.emulateMedia({media:'screen'});assert.equal(await page.locator('#schedulePrintSheet').isVisible(),false);
 assert.deepEqual(errors,[]);
 console.log('PASS actual Flask + browser: combined reader home, compact grid, admin approval, no time/place fields, A3 print isolation, all 31 dates, mobile and admin regression');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
