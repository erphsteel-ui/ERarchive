const {chromium}=require('playwright');const path=require('path');const assert=require('node:assert/strict');
(async()=>{
 const opts={headless:true};if(process.env.USE_SERVER_CHROMIUM){const binary=require('@sparticuz/chromium').default;opts.executablePath=await binary.executablePath();opts.args=binary.args;}
 const browser=await chromium.launch(opts);try{
 const page=await browser.newPage({viewport:{width:1440,height:1800}});const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());let saved=null;
 const group=pages=>({pages,reason:'자동 제안',meta:{title:'',publishers:[],date:'',issue:'',kind:'홍보물'}});
 const batch={id:'job',version:2,state:'review',groups:[group(['a','b']),group(['c','d'])],pages:['a','b','c','d'].map(id=>({id,name:id+'.jpg',text:'본문',status:'완료',elapsed:10,state:'done'}))};
 await page.route('http://archive.test/**',async route=>{const p=new URL(route.request().url()).pathname;let data;
 if(p==='/api/me')data={role:'admin',user:'admin',csrf:'token'};else if(p==='/api/documents'||p==='/api/batches')data=[];else if(p==='/api/settings')data={organizations:[]};else if(p==='/api/batches/job')data=batch;else if(p==='/api/batches/job/save'){saved=route.request().postDataJSON();data={saved:true,version:3};}
 if(data!==undefined)return route.fulfill({json:data});
 if(p.startsWith('/api/batch-image/'))return route.fulfill({path:path.join(__dirname,'../upload/KakaoTalk_20261021_080636442.jpg'),contentType:'image/jpeg'});
 if(p==='/')return route.fulfill({path:path.join(__dirname,'templates/index.html'),contentType:'text/html'});
 if(p.startsWith('/static/'))return route.fulfill({path:path.join(__dirname,p),contentType:p.endsWith('.js')?'application/javascript':'text/css'});
 return route.fulfill({status:404,body:''});});
 await page.goto('http://archive.test/');await page.locator('#uploadButton').waitFor({state:'visible'});await page.evaluate(()=>openBatchReview('job'));
 // Same group: b before a, dragging from the visible handle.
 await page.locator('[data-page-drag="b"] .drag-handle').dragTo(page.locator('[data-page-drag="a"]'),{targetPosition:{x:5,y:20}});
 assert.deepEqual(await page.evaluate(()=>batchReview.groups[0].pages),['b','a']);
 // Cross-group relocation and new-group drop zone.
 await page.locator('[data-page-drag="a"] .drag-handle').dragTo(page.locator('[data-page-drag="c"]'),{targetPosition:{x:5,y:20}});
 assert.deepEqual(await page.evaluate(()=>batchReview.groups.map(g=>g.pages)),[['b'],['a','c','d']]);
 await page.locator('[data-page-drag="d"] .drag-handle').dragTo(page.locator('#batchNewGroupDrop'));
 assert.deepEqual(await page.evaluate(()=>batchReview.groups.map(g=>g.pages)),[['b'],['a','c'],['d']]);
 await page.locator('#batchPublish').click();await page.waitForFunction(()=>!document.querySelector('#batchReviewDialog').open);
 assert.equal(saved.action,'published');assert.equal(saved.confirmed,true);assert.equal(saved.version,2);assert.deepEqual(saved.groups.map(g=>g.pages),[['b'],['a','c'],['d']]);assert.deepEqual(errors,[]);
 console.log('PASS: actual mouse drag reorder, cross-group move, new group and direct publish without draft save');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
