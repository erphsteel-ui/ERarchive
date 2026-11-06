const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const clone=x=>JSON.parse(JSON.stringify(x));
async function financial(){
 const code=fs.readFileSync(__dirname+'/static/financials.js','utf8'),nodes={'#financialFilters':{contains:()=>editing},'#financialStatus':{},'#financialPanel':{}};
 let editing=false,renders=0,requests=0,timers=0;
 const data={rows:[{values:{revenue:100}}],job:{running:true,done:1,total:8,error:'',company:'x'}};
 const c=vm.createContext({financialActive:true,financialTicket:0,financialTimer:0,financialRenderKey:'',financialData:null,financialFilter:{},URLSearchParams,document:{activeElement:{}},$:s=>nodes[s],esc:String,api:async()=>{requests++;return clone(data)},renderFinancials:()=>renders++,setTimeout:()=>++timers,clearTimeout(){}});
 vm.runInContext(code.slice(code.indexOf('async function loadFinancials('),code.indexOf('function financialMoney(')),c);
 await vm.runInContext('loadFinancials()',c);assert.equal(renders,1);
 data.job.done=2;await vm.runInContext('loadFinancials(true)',c);assert.equal(renders,1);assert(nodes['#financialStatus'].textContent.includes('2/8'));
 data.rows[0].values.revenue=200;await vm.runInContext('loadFinancials(true)',c);assert.equal(renders,2);
 editing=true;data.job.running=false;await vm.runInContext('loadFinancials(true)',c);assert.equal(renders,2);
 editing=false;await vm.runInContext('loadFinancials(true)',c);assert.equal(renders,3);
 c.api=()=>new Promise(resolve=>{c.resolve=resolve});const pending=vm.runInContext('loadFinancials()',c);c.financialActive=false;c.financialTicket++;c.resolve(clone(data));await pending;assert.equal(renders,3);
 console.log('PASS: financial unchanged polls update status only, changed data refreshes, typing preserved, stale responses ignored');
}
async function news(){
 const code=fs.readFileSync(__dirname+'/static/news.js','utf8');let editing=false,renders=0,requests=0,details=[{dataset:{newsGroup:'a'},open:true}];
 const data={items:[],headlines:[],steel_press:{},categories:[],total:0,preview_status:{running:true}};
 const nodes={'#newsFilters':{contains:()=>editing},'#newsPanel':{}};
 const c=vm.createContext({newsActive:true,newsTicket:0,newsPreviewTimer:0,newsRenderKey:'',newsFilter:{},newsOffset:0,URLSearchParams,document:{activeElement:{}},$:s=>nodes[s],$$:s=>s.includes('[open]')?details.filter(d=>d.open):details,esc:String,api:async()=>{requests++;return clone(data)},renderNews:()=>{renders++;details=[{dataset:{newsGroup:'a'},open:false}]},setTimeout:()=>1,clearTimeout(){}});
 vm.runInContext(code.slice(code.indexOf('async function loadNews('),code.indexOf('function renderNews(')),c);
 await vm.runInContext('loadNews()',c);assert.equal(renders,1);assert(details[0].open);
 await vm.runInContext('loadNews(true)',c);assert.equal(renders,1);
 editing=true;const before=requests;await vm.runInContext('loadNews(true)',c);assert.equal(requests,before);
 editing=false;data.total=1;await vm.runInContext('loadNews(true)',c);assert.equal(renders,2);assert(details[0].open);
 c.api=()=>new Promise(resolve=>{c.resolve=resolve});const pending=vm.runInContext('loadNews(true)',c);editing=true;data.total=2;c.resolve(clone(data));await pending;assert.equal(renders,2);
 console.log('PASS: news unchanged polls avoid redraw, expanded groups survive, typing protected before and during requests');
}
(async()=>{await financial();await news()})().catch(e=>{console.error(e);process.exit(1)});
