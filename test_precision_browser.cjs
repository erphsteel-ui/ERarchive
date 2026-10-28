const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const binary=require('@sparticuz/chromium');const browser=await chromium.launch({executablePath:await binary.executablePath(),args:binary.args,headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8765');await page.locator('#adminLogin').click();
 await page.locator('#loginForm [name=name]').fill('admin');await page.locator('#loginForm [name=password]').fill('test-password-123');await page.locator('#loginForm button.primary').click();
 await page.locator('#precisionButton').click();await page.locator('[data-precision-review]').first().click();
 await page.locator('#precisionBefore').waitFor({state:'visible'});
 assert.match(await page.locator('#precisionBefore').inputValue(),/교섭속보/);
 assert.match(await page.locator('#precisionAfter').inputValue(),/현대제철비정규직지회/);
 assert.equal(await page.locator('#precisionDestinationLabel').isVisible(),true);
 await page.screenshot({path:'/tmp/er-v16-precision.png'});
 // New image: schedule-only choice must not create an archive publication or batch.
 await page.locator('#precisionDestination').selectOption('schedule');await page.locator('#precisionAfter').fill('현대제철 당진지회 : 2026.11.04 단체교섭 예정');
 await page.locator('#precisionApply').click();await page.waitForFunction(()=>!document.querySelector('#precisionReviewDialog').open);
 const data=await page.evaluate(async()=>({jobs:await api('precision'),docs:await api('documents'),batches:await api('batches')}));
 assert.equal(data.jobs.jobs[0].state,'reviewed');assert.equal(data.jobs.jobs[0].decision,'apply');assert.equal(data.docs.length,0);assert.equal(data.batches.length,0);
 await page.locator('[data-precision-review]').first().click();await page.waitForFunction(()=>document.querySelector('#precisionReviewDialog').open);assert.equal(await page.locator('#precisionApply').isDisabled(),true);assert.equal(await page.locator('#precisionBefore').inputValue(),'현대제철 당진지회 : 2026.11.04 단체교섭 예정');
 assert.deepEqual(errors,[]);
 console.log('PASS: real Flask/Chromium login, VL compare, original preview, corrected schedule-only approval, no publication, readonly reviewed state');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
