const {JSDOM}=require('jsdom');const fs=require('fs');const assert=require('node:assert/strict');
const dom=new JSDOM(fs.readFileSync(__dirname+'/templates/index.html','utf8'),{runScripts:'outside-only',url:'http://localhost/'});const w=dom.window;
w.structuredClone=structuredClone;w.assert=assert;w.setInterval=()=>{};w.setTimeout=()=>{};w.confirm=()=>true;
w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
const code=fs.readFileSync(__dirname+'/static/app.js','utf8').replace('boot();','')+'\n'+fs.readFileSync(__dirname+'/static/batches.js','utf8');
const result=w.eval(code+`
(async()=>{
 user={role:'admin',csrf:'token'};let submitted=null;let id=0;
 const group=pages=>({pages,reason:'파일명 연속 · 확인 필요',meta:{title:'홍보물',publishers:['조직'],issue:'1호',date:'2026-10-22',kind:'홍보물'}});
 const sample={id:'job',state:'review',version:2,groups:[group(['p1','p2']),group(['p3','p4'])],pages:['p1','p2','p3','p4'].map(id=>({id,name:id+'.png',state:'done',text:'인식 본문',status:'완료',elapsed:12}))};
 api=async(path,body)=>{if(body){submitted=body;return {version:3,saved:false}}return structuredClone(sample)};
 await openBatchReview('job');assert.equal(document.querySelectorAll('.batch-group').length,2);assert.equal(document.querySelectorAll('.batch-pages article').length,4);
 const title=$('[data-field="title"]');title.value='수정 제목';title.oninput();assert.equal(batchReview.groups[0].meta.title,'수정 제목');assert.equal(batchDirty,true);
 const dest=$('[data-destination="p2"]');dest.value='new';dest.onchange();assert.equal(batchReview.groups.length,3);assert.equal(JSON.stringify(batchReview.groups.map(g=>g.pages.length)),JSON.stringify([1,2,1]));
 const merge=$('[data-destination="p2"]');merge.value='1';merge.onchange();assert.equal(batchReview.groups.length,2);assert.equal(JSON.stringify(batchReview.groups[1].pages),JSON.stringify(['p3','p4','p2']));
 $('[data-move="p2"][data-dir="-1"]').click();assert.equal(JSON.stringify(batchReview.groups[1].pages),JSON.stringify(['p3','p2','p4']));
 moveBatchPage('p4',0,'p1',false);assert.equal(JSON.stringify(batchReview.groups[0].pages),JSON.stringify(['p4','p1']));moveBatchPage('p4',0,'p1',true);assert.equal(JSON.stringify(batchReview.groups[0].pages),JSON.stringify(['p1','p4']));moveBatchPage('p4','new');assert.equal(batchReview.groups.length,3);
 await saveBatch('review');assert.equal(submitted.action,'review');assert.equal(submitted.version,2);assert.equal(batchReview.version,3);assert.equal(batchDirty,false);assert.equal(submitted.groups[0].meta.title,'수정 제목');
 submitted=null;window.confirm=()=>false;await saveBatch('published');assert.equal(submitted,null);window.confirm=()=>true;await saveBatch('published');assert.equal(submitted.action,'published');assert.equal(submitted.confirmed,true);$('#batchConfirmed').checked=true;await saveBatch('published');assert.equal(submitted.confirmed,true);assert.equal(submitted.action,'published');
})()
`);
result.then(()=>{console.log('PASS: batch metadata, split, merge, order, review save and publish confirmation');dom.window.close();}).catch(e=>{console.error(e);dom.window.close();process.exitCode=1});
