const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const js=fs.readFileSync(__dirname+'/static/schedule.js','utf8');
const ctx=vm.createContext({});
vm.runInContext(js.slice(js.indexOf('const scheduleKindMap='),js.indexOf('function scheduleVisibleDates(')),ctx);
const kinds={'일정':'event','교육':'education','회의':'meeting','교섭':'bargaining','행사':'ceremony','집회':'rally','기타':'other'};
for(const [kind,tone] of Object.entries(kinds)) assert.equal(vm.runInContext(`scheduleTone({kind:${JSON.stringify(kind)},title:'교섭 회의'})`,ctx),tone);
assert.equal(vm.runInContext("scheduleTone({kind:'기존 유형'})",ctx),'other');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
const page=await browser.newPage();
await page.setContent(`<html><body><div id="scheduleMain"><table class="compact-calendar"><tbody><tr>${Object.values(kinds).map(t=>`<td><button class="schedule-event schedule-tone-${t}">${t}</button></td>`).join('')}</tr></tbody></table></div></body></html>`);
await page.addStyleTag({content:fs.readFileSync('static/theme.css','utf8')});
for(const theme of ['dark','light']) for(const view of ['monthly','two-week']){
 await page.evaluate(({theme,view})=>{document.documentElement.dataset.theme=theme;document.querySelector('table').classList.toggle('schedule-two-weeks',view==='two-week')},{theme,view});
 const colors=await page.locator('.schedule-event').evaluateAll(nodes=>nodes.map(n=>{const s=getComputedStyle(n);return [s.backgroundColor,s.borderLeftColor,s.color]}));
 assert.equal(new Set(colors.map(c=>c[0])).size,7,`${theme} ${view} backgrounds`);
 assert.equal(new Set(colors.map(c=>c[1])).size,7,`${theme} ${view} borders`);
}
console.log('PASS: seven event types have distinct colors in both themes and calendar views');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
