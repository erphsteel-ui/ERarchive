const fs=require('fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const js=fs.readFileSync('static/schedule.js','utf8'),ctx=vm.createContext({});vm.runInContext(js.slice(js.indexOf('const scheduleKindMap='),js.indexOf('function scheduleVisibleDates(')),ctx);
for(const [title,want] of [['임단협 조인식','issue'],['교섭 교육','issue'],['통상임금 변론기일','safety-legal'],['교대제 개편 TFT','safety-legal'],['정기 회계 감사','safety-legal'],['노안담당자 수련회','event-edu'],['운영위원 교육','event-edu'],['노사안전위 회의','meeting'],['현장경영 포항','etc'],['[지회] 후보 방문','etc']]){ctx.item={title,kind:'일정'};assert.equal(vm.runInContext('scheduleTone(item)',ctx),want,title)}
console.log('PASS: 5 category keyword precedence and fallback');
