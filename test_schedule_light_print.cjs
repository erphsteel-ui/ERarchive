const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 const page=await browser.newPage();const types=['event','education','meeting','bargaining','ceremony','rally','other'];
 const cards=types.map(t=>`<button class="schedule-event schedule-tone-${t}"><b>${t}</b><small class="calendar-range">(~5)</small></button>`).join('');
 await page.setContent(`<html data-theme="light"><body class="schedule-print-ready"><div id="scheduleMain"><table class="schedule-table compact-calendar"><thead><tr><th class="schedule-org">조직</th><th class="schedule-today">3<span class="schedule-today-badge">TODAY</span></th></tr></thead><tbody><tr><th class="schedule-org">포항</th><td id="weekday">${cards}</td><td id="weekend" class="weekend"></td><td id="today" class="schedule-today"></td></tr></tbody></table></div><section id="schedulePrintSheet"><table class="schedule-table"><tbody><tr><td>${cards}</td></tr></tbody></table></section></body></html>`);
 await page.addStyleTag({content:fs.readFileSync('static/style.css','utf8')});await page.evaluate(css=>{let s=document.createElement('style');s.media='screen';s.textContent=css;document.head.append(s)},fs.readFileSync('static/theme.css','utf8'));
 for(const twoWeeks of [false,true]){
  await page.evaluate(v=>document.querySelector('#scheduleMain table').classList.toggle('schedule-two-weeks',v),twoWeeks);
  const grid=await page.evaluate(()=>Object.fromEntries(['weekday','weekend','today'].map(id=>[id,getComputedStyle(document.getElementById(id)).backgroundColor])));
  assert.equal(grid.weekday,'rgb(255, 255, 255)');assert.equal(grid.weekend,'rgb(248, 250, 252)');assert.equal(grid.today,'rgba(239, 246, 255, 0.25)');
  assert.equal(await page.locator('#scheduleMain .schedule-today-badge').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(37, 99, 235)');
  const colors=await page.locator('#scheduleMain .schedule-event').evaluateAll(nodes=>nodes.map(n=>{const s=getComputedStyle(n);return [s.backgroundColor,s.borderLeftColor,s.borderLeftWidth,s.color]}));
  assert.equal(new Set(colors.map(c=>c[0])).size,7);assert.equal(new Set(colors.map(c=>c[1])).size,7);assert(colors.every(c=>c[2]==='4px'));
  assert.equal(colors[0][0],'rgba(219, 234, 254, 0.9)');
 }
 await page.evaluate(()=>document.documentElement.dataset.theme='dark');assert.equal(await page.locator('#scheduleMain .schedule-tone-event').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(23, 46, 86)');
 await page.emulateMedia({media:'print'});
 const print=await page.locator('#schedulePrintSheet .schedule-event').evaluateAll(nodes=>nodes.map(n=>{const s=getComputedStyle(n);return [s.backgroundColor,s.borderLeftColor,s.borderLeftWidth,s.printColorAdjust]}));
 assert.equal(new Set(print.map(c=>c[0])).size,7);assert.equal(new Set(print.map(c=>c[1])).size,7);assert(print.every(c=>c[2]==='4px'&&c[3]==='exact'));assert.equal(print[2][0],'rgb(237, 233, 254)');
 console.log('PASS: light grid, today, seven card colors, dark mode and print colors');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
