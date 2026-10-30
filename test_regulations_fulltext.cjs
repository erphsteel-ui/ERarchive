const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const button={onclick:null},nodes={'#readerRegulationsTab':button};const ctx={console,URLSearchParams,$:s=>nodes[s]||{},esc:s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'),document:{body:{classList:{}}}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/static/regulations.js','utf8'),ctx);
const find=(q)=>vm.runInContext(`regFind([{category:'agreement',body:'제1장 총칙\\r\\n제45조【근로시간】\\r\\n근로시간 근로시간\\r\\n다음 줄\\r\\n제46조(휴일)\\r\\n근로시간'}],${JSON.stringify(q)})`,ctx);
let hits=find('근로시간');assert.equal(hits.length,4);assert.equal(hits[1].line,2);assert.equal(hits[3].heading,'제46조(휴일)');assert.match(hits[1].snippet,/다음 줄/);
assert.equal(find('없는단어').length,0);assert.equal(vm.runInContext("regFind([{category:'a',body:'a+b a+b'}],'a+b').length",ctx),2);
assert.equal(vm.runInContext("regHeading(' 1) 임원 선거 세칙')",ctx),'chapter');assert.equal(vm.runInContext("regHeading('5.2.1 근무시간')",ctx),'article');
assert.equal(vm.runInContext("regHighlight('<script>근로시간</script>','근로시간')",ctx),'&lt;script&gt;<mark>근로시간</mark>&lt;/script&gt;');
console.log('PASS: occurrence counts, line locations, contextual snippets, heading lookup and escaped highlights');
