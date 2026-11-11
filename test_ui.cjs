const {JSDOM}=require('jsdom');const fs=require('fs');const assert=require('node:assert/strict');
const root=__dirname;const dom=new JSDOM(fs.readFileSync(root+'/templates/index.html','utf8'),{runScripts:'outside-only',url:'http://localhost/'});const w=dom.window;
w.structuredClone=structuredClone;w.assert=assert;w.URL.createObjectURL=()=> 'blob:local-test';w.URL.revokeObjectURL=()=>{};w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};w.setTimeout=()=>{};
const outcome=w.eval(fs.readFileSync(root+'/static/app.js','utf8').replace('boot();','')+`
const sample=(id,date,pubs)=>({id,date,publishers:pubs,categories:[pubs.includes('조직B')?'그룹사':'집행부'],company:'현대제철',site:'포항',kind:'홍보물',title:id,issue:'1호',period:'',note:'관리 메모',tags:[],state:'published',created:date||'2026-01-01',version:1,pages:[{id:id+'p1',text:'앞면',status:'OCR'},{id:id+'p2',text:'주휴수당 뒷면',status:'OCR'}]});
user={role:'viewer',user:'',csrf:'x'};docs=[sample('older','2026-10-01',['조직A']),sample('newer','2026-10-21',['조직A','조직B']),sample('unknown','',['조직A']),sample('anonymous','2026-10-10',[])];render();
assert.equal(document.querySelectorAll('.category-section').length,4);assert.equal($('#publisherGroups').querySelector('img'),null);assert.equal($('.readerintro'),null);
assert.deepEqual([...document.querySelectorAll('.category-section')[0].querySelectorAll('[data-read]')].map(x=>x.dataset.read),['anonymous','older','unknown']);
assert.equal(document.querySelector('.stats'),null);
assert.equal(document.querySelector('.column-issue').textContent,'1호');
assert.equal(document.querySelector('.column-issuer').textContent,'미분류');
assert.equal(textMatches('주 휴 수 당','주휴수당',false),true);
assert.equal(textMatches('전국금속노동조합','금속노조',false),true);
assert.equal(textMatches('노사협의희','노사협의회',false),false);
assert.equal(textMatches('노사협의희','노사협의회',true),true);
assert.equal(textMatches('2026','2025',true),false);

$('#search').value='주휴수당';render();document.querySelector('[data-read]').click();assert.equal(page,1);assert.equal($('#readerInfo').querySelectorAll('input,textarea').length,0);assert.ok(!$('#readerInfo').textContent.includes('관리 메모'));
$('#search').value='';$('#publisher').value='조직B';render();assert.equal(document.querySelectorAll('.category-section').length,4);assert.equal(document.querySelectorAll('[data-read]').length,1);
$('#search').value='';$('#publisher').value='';render();document.querySelector('[data-category="그룹사"]').click();assert.equal(document.querySelectorAll('.category-section').length,1);assert.equal(document.querySelector('[data-read]').dataset.read,'newer');selectedCategory='';user.role='admin';$('#publisher').value='';render();openDoc('newer');assert.equal($('#f_company'),null);assert.equal($('#f_site'),null);assert.equal($('#f_period'),null);assert.ok($('#f_publishers').hasAttribute('list'));$('#pageOrder [data-up="1"]').click();assert.equal(current.pages[0].id,'newerp2');assert.equal($('#pageLabel').textContent,'1 / 2');assert.equal(dirty,true);assert.equal($('#ocrfields textarea').dataset.text,'newerp2');
Object.defineProperty($('#files'),'files',{value:[{name:'page_10.jpg'},{name:'page_01.jpg'},{name:'page.jpg'},{name:'page_2.jpg'}],configurable:true});$('#files').onchange();assert.deepEqual(uploadFiles.map(f=>f.name),['page.jpg','page_01.jpg','page_2.jpg','page_10.jpg']);$('#uploadOrder [data-up="1"]').click();assert.equal(uploadFiles[0].name,'page_01.jpg');

(async()=>{
 assert.equal($('#cards .cardbody').firstElementChild.className,'card-publisher');
 assert.equal($('#topSave').parentElement,$('#closeDetail').parentElement);
 let saved=null;api=async(path,body)=>{saved=body;return {ok:true}};refresh=async()=>{};
 current.state='draft';$('#f_title').value='수정 제목';await $('#topSave').onclick();assert.equal(saved.state,'draft');assert.equal(saved.title,'수정 제목');
 current.state='published';await $('#topSave').onclick();assert.equal(saved.state,'published');
 openDoc('newer');
 const pid=current.pages[0].id;const before=$('[data-text="'+pid+'"]').value;
 api=async()=>({version:current.version,run_id:'review-1',original:{text:'원문',source:'최초'},history:[],result:{selected:0,variants:[{name:'후보',text:'교정 본문',warning_count:0,warnings:[]}]}});
 await openOcr(pid);assert.equal($('#ocrBefore').value,before);assert.equal($('[data-text="'+pid+'"]').value,before);
 ocrReview.fresh=true;$('#applyOcr').onclick();assert.equal($('[data-text="'+pid+'"]').value,'교정 본문');assert.equal(pendingOcrRuns[pid],'review-1');assert.equal(dirty,true);
 openDoc('newer');const previousTitle=$('#f_title').value;api=async()=>({title:'강철의 함성',publishers:['금속노조 충남지부 현대제철지회']});window.confirm=()=>true;await $('#recognizeButton').onclick();assert.equal($('#f_title').value,'강철의 함성');assert.equal(dirty,true);
})()
`);
outcome.then(()=>{console.log('PASS: publisher grouping, latest order, unknown date last, joint issuers, search page jump, reader info, admin reorder and OCR alignment, upload filename ordering and manual arrows');dom.window.close();}).catch(e=>{console.error(e);dom.window.close();process.exitCode=1});
