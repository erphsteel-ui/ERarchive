const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
const page=await browser.newPage();await page.setContent('<html><body><div id="scheduleMain"><table class="compact-calendar"><tr><td><div class="schedule-event"><b>노무 회의</b></div></td></tr></table></div><section id="schedulePrintSheet"><div class="schedule-event"><b>노무 회의</b></div></section></body></html>');await page.addStyleTag({content:fs.readFileSync('static/style.css','utf8')});await page.evaluate(css=>{let s=document.createElement('style');s.media='screen';s.textContent=css;document.head.append(s)},fs.readFileSync('static/theme.css','utf8'));
for(const mode of ['monthly','two-week','print']){
 if(mode==='print')await page.emulateMedia({media:'print'});else await page.evaluate(m=>document.querySelector('table').classList.toggle('schedule-two-weeks',m==='two-week'),mode);
 const selector=mode==='print'?'#schedulePrintSheet b':'#scheduleMain b';const values=await page.locator(selector).evaluate(e=>{let s=getComputedStyle(e);return [s.wordBreak,s.overflowWrap]});assert.deepEqual(values,['keep-all','break-word'],mode);
}
console.log('PASS: Korean word boundaries are preferred in monthly, two-week and print layouts');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
