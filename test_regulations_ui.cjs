const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map();
const element=()=>({innerHTML:'',hidden:false,setAttribute(){},classList:{remove(){},add(){}},querySelectorAll(){return []}});
const $=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)};
const context=vm.createContext({$,console,URLSearchParams,document:{body:{classList:{remove(){},add(){}}}},esc:s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'),user:{role:'viewer'},setTimeout,clearTimeout});
vm.runInContext(fs.readFileSync(__dirname+'/static/regulations.js','utf8'),context);
(async()=>{
 await vm.runInContext(`(async()=>{
  const results=regulationDemoResults('근로시간','');
  if(results.total!==7||Object.values(results.counts).some(n=>n!==1))throw Error('sample counts');
  if(regulationDemoResults('근로시간','labor_act').items.length!==1)throw Error('category filter');
  if(regulationDemoResults('없는키워드','').total!==0)throw Error('empty state');
  if(!regulationHighlight('<script>근로시간</script>','근로시간').includes('&lt;script&gt;<mark>근로시간</mark>'))throw Error('unsafe highlighting');
  if(!regulationHighlight('근 로 시 간','근로시간').includes('<mark>근 로 시 간</mark>'))throw Error('spaced keyword');
  if(!regulationHighlight('a+b','a+b').includes('<mark>a+b</mark>'))throw Error('regex escaping');
  if(!regulationHighlight('제 50 조','50조').includes('<mark>제 50 조</mark>'))throw Error('article number highlighting');
  regulationsActive=true;regulationsDemo=true;regulationsSearch='근로시간';await loadRegulations();
 })()`,context);
 assert.match($('#regulationsTags').innerHTML,/전체 \(7\)/);
 assert.equal(($('#regulationsResults').innerHTML.match(/class="regulations-card"/g)||[]).length,7);
 await vm.runInContext(`regulationsFilter='labor_act';loadRegulations()`,context);
 assert.match($('#regulationsResults').innerHTML,/근로기준법/);
 assert.equal(($('#regulationsResults').innerHTML.match(/class="regulations-card"/g)||[]).length,1);
 // Resolve an earlier API response after a newer response: only newer results may render.
 const pending=[];context.api=()=>new Promise(resolve=>pending.push(resolve));
 const first=vm.runInContext(`regulationsDemo=false;regulationsFilter='';regulationsSearch='예전';loadRegulations()`,context);
 const latest=vm.runInContext(`regulationsSearch='최신';loadRegulations()`,context);
 const payload={items:[],counts:{},total:0};pending[1](payload);await latest;pending[0](payload);await first;
 assert.match($('#regulationsResults').innerHTML,/최신/);assert.doesNotMatch($('#regulationsResults').innerHTML,/예전/);
 console.log('PASS: 7-category counts, filtering, rendering, safe highlighting, empty state and stale response protection');
})().catch(error=>{console.error(error);process.exitCode=1});
