const {chromium}=require('playwright');const fs=require('fs');const path=require('path');const assert=require('node:assert/strict');
(async()=>{
 const opts={headless:true};if(process.env.USE_SERVER_CHROMIUM){const binary=require('@sparticuz/chromium').default;opts.executablePath=await binary.executablePath();opts.args=binary.args;}const browser=await chromium.launch(opts);const page=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const doc={id:'test',title:'홍보물 전체 보기',publishers:['금속노조 현대제철지회'],date:'2026-10-22',issue:'26-30호',kind:'홍보물',tags:[],state:'published',categories:['집행부'],created:'2026-10-22',version:1,pages:[{id:'p1',text:'본문',status:'완료'},{id:'p2',text:'본문 2',status:'완료'}]};
 await page.route('http://archive.test/**',async route=>{const p=new URL(route.request().url()).pathname;let data;
 if(p==='/api/me')data={role:'viewer',user:'',csrf:''};else if(p==='/api/documents')data=[doc];else if(p==='/api/settings')data={organizations:[]};
 if(data!==undefined)return route.fulfill({json:data});
 if(p.startsWith('/api/image/'))return route.fulfill({path:path.join(__dirname,'../upload/KakaoTalk_20261021_080636442.jpg'),contentType:'image/jpeg'});
 if(p==='/')return route.fulfill({path:path.join(__dirname,'templates/index.html'),contentType:'text/html'});
 if(p.startsWith('/static/'))return route.fulfill({path:path.join(__dirname,p),contentType:p.endsWith('.js')?'application/javascript':'text/css'});
 return route.fulfill({status:404,body:''});});
 await page.goto('http://archive.test/');await page.locator('[data-read]').first().click();await page.locator('#pageImage').evaluate(img=>img.decode());
 async function checkFit(){await page.waitForTimeout(150);const r=await page.evaluate(()=>{const d=document.querySelector('#detailDialog'),w=document.querySelector('#imageWrap'),i=document.querySelector('#pageImage'),m=document.querySelector('.metadata');return {dh:d.clientHeight,ds:d.scrollHeight,wh:w.clientHeight,ws:w.scrollHeight,ww:w.clientWidth,sw:w.scrollWidth,iw:i.clientWidth,ih:i.clientHeight,display:getComputedStyle(m).display,width:d.clientWidth,viewport:innerWidth};});assert.ok(r.wh>100);assert.ok(r.ds<=r.dh+2,JSON.stringify(r));assert.ok(r.ws<=r.wh+2,JSON.stringify(r));assert.ok(r.sw<=r.ww+2);assert.equal(r.display,'none');assert.ok(r.width>r.viewport*.9);}
 await checkFit();await page.locator('#readerZoomIn').click();assert.equal(await page.locator('#readerZoomLabel').textContent(),'150%');assert.ok(await page.locator('#imageWrap').evaluate(w=>w.scrollHeight>w.clientHeight));await page.locator('#readerFit').click();await checkFit();
 await page.locator('#readerInfoToggle').click();await page.locator('#readerInfo').waitFor({state:'visible'});await page.locator('#readerInfoToggle').click();await checkFit();
 await page.locator('#readerZoomIn').click();await page.locator('#next').click();await page.locator('#pageImage').evaluate(img=>img.decode());await checkFit();assert.equal(await page.locator('#readerZoomLabel').textContent(),'전체 맞춤');
 await page.setViewportSize({width:390,height:844});await checkFit();assert.deepEqual(errors,[]);
 await browser.close();console.log('PASS: real browser desktop/mobile full-page fit, zoom, reset on page change and info overlay');
})().catch(e=>{console.error(e);process.exitCode=1});
