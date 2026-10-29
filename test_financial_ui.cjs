const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(__dirname+'/static/financials.js','utf8'),nodes={};
const context=vm.createContext({financialData:{companies:[{id:'hyundai-steel',name:'현대제철'}],job:{running:false,error:''},resolved:null,rows:[{year:2025,quarter:4,values:{revenue:12300000000,operating:-100000000,pretax:null,net:0},operating_margin:-.81,net_margin:0,revenue_qoq:null,operating_qoq:null,revenue_yoy:null,status:'available',updated:'now',warnings:['missing'],receipts:['20260301000001'],derived:true}]},financialFilter:{company:'hyundai-steel',fs:'CFS',start:2025,end:2025,mode:'quarterly',quarter:0},financialYear:2026,financialView:'amount',user:{role:'viewer'},$:s=>nodes[s]||(nodes[s]={addEventListener(){}}),esc:s=>String(s??'').replace(/</g,'&lt;'),loadFinancials(){},openFinancialSettings(){},$$:()=>[]});
vm.runInContext(code.slice(code.indexOf('function financialCompanyHeader('),code.indexOf('async function openFinancialSettings(')),context);
vm.runInContext('renderFinancials()',context);const html=nodes['#financialPanel'].innerHTML;
assert(html.includes('123'));assert(html.includes('financial-negative'));assert(html.includes('—'));assert(html.includes('0.0%'));
assert(html.includes('rcpNo=20260301000001'));assert(!html.includes('id="financialSettings"'));assert(html.includes('분기 누적'));assert(html.includes('연간'));
const template=fs.readFileSync(__dirname+'/templates/index.html','utf8');assert(template.includes('id="readerFinancialTab"'));assert(template.includes('id="financialPanel"'));assert(template.includes('/static/financials.js'));
console.log('PASS: financial table formatting, missing values, source links, viewer controls and tab wiring');

assert(html.includes('<th scope="row">매출액</th>'));assert(html.includes('<th scope="col" data-financial-period="2025-4" class="financial-current">2025 Q4 *'));assert(html.includes('data-financial-mode="annual"'));console.log('PASS: metric rows, period columns and mode switches');

assert.equal(vm.runInContext('financialMoney(6107320000000)',context),'6조 1,073억');
assert.equal(vm.runInContext('financialMoney(-6107320000000)',context),'-6조 1,073억');
assert.equal(vm.runInContext('financialMoney(1000000000000)',context),'1조');
assert.equal(vm.runInContext('financialMoney(99999999)',context),'0억');
assert.equal(vm.runInContext('financialMoney(-199999999)',context),'-1억');
assert.equal(vm.runInContext('financialMoney(null)',context),'—');
assert.equal(vm.runInContext('financialPercent(1.25)',context),'1.3%');
console.log('PASS: trillion/eok money display truncates fractions, preserves negatives and missing values');
let table=vm.runInContext("renderFinancialMatrix(financialData.rows,'quarterly')",context);
assert(!table.includes('YoY'));assert(!table.includes('QoQ'));assert(table.includes('매출액 대비 이익률'));assert(table.includes('-0.8%'));
assert.equal(vm.runInContext("financialMargin({values:{revenue:0,operating:10}},'operating')",context),null);
assert(!html.includes('data-financial-view'));
assert(html.includes('financial-chart-info'));assert(html.includes('financial-header-bar'));assert(!html.includes('financial-company-logo'));assert(!html.includes('logo.clearbit.com'));assert(html.includes('현대제철'));assert(!html.includes('financial-company-heading'));
context.financialFilter.company='posco';context.financialData.companies.push({id:'posco',name:'포스코'});assert(vm.runInContext('financialCompanyHeader(financialData,financialFilter)',context).includes('포스코'));context.financialFilter.company='hyundai-steel';
assert(html.indexOf('financial-mode-tabs')<html.indexOf('financial-chart-info'));
assert(html.includes('단위: 조·억 원 (DART 연결 기준)'));assert(!html.includes('차트: 과거 → 최신'));assert(!html.includes('원자료는 원(KRW)으로 보관'));
assert(!html.includes('저장된 자료를 표시합니다.'));
assert.equal(vm.runInContext("financialJobText({running:false,error:'수집 오류'})",context),'수집 오류');
assert(vm.runInContext("financialJobText({running:true,done:1,total:2})",context).includes('수집 중 1/2건'));

const periods=[{year:2025,quarter:1,values:{revenue:10000000000,operating:100000000,net:50000000},revenue_yoy:5,revenue_qoq:2},{year:2025,quarter:2,values:{revenue:null,operating:200000000,net:null}},{year:2025,quarter:3,values:{revenue:10000000000,operating:-100000000,net:-50000000},revenue_yoy:-3,revenue_qoq:null},{year:2025,quarter:4,values:{revenue:null,operating:null,net:null}}];
context.periods=periods;const chart=vm.runInContext("renderFinancialCharts(periods,'quarterly')",context);
assert(!chart.includes('NaN'));assert.equal((chart.match(/<svg/g)||[]).length,2);
assert(chart.includes('최신 실적 요약'));assert(chart.includes('2025 Q3'));assert(chart.includes('QoQ — · YoY -3.0%'));assert(chart.includes('매출액·영업이익 추이'));assert(chart.includes('수익성 비교'));assert(chart.includes('순이익률'));assert(chart.includes('data-chart-period="2025-1"'));assert(chart.includes('-1.0%'));
const annual=vm.runInContext("renderFinancialCharts(periods,'annual')",context);assert(annual.includes('2025년'));assert(!annual.includes('QoQ — · YoY'));
const empty=vm.runInContext("renderFinancialCharts([],'quarterly')",context);assert(empty.includes('저장된 실적이 없습니다.'));
console.log('PASS: latest available summary, missing comparisons, annual mode and two charts with losses');
