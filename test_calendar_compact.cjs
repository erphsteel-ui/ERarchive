const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/static/schedule.js','utf8');
const functions=source.slice(source.indexOf('function calendarGroups(){'),source.indexOf('function renderScheduleGrid(){'));
const data={rows:[{id:'d',group:'당사',name:'당진'},{id:'s',group:'당사',name:'순천'},{id:'a',group:'계열사',name:'ITC'},{id:'b',group:'계열사',name:'IMC'}],events:[]};
for(let i=0;i<4;i++)data.events.push({id:String(i),row:'d',start:'2026-10-02',end:'2026-10-03',title:'일정'+i,status:'예정'});
data.events.push({id:'a1',row:'a',start:'2026-10-02',end:'2026-10-02',title:'교섭',status:'예정'});
const context=vm.createContext({scheduleData:data,scheduleMonth:'2026-10',scheduleZoom:false,scheduleAnchor:'',user:{role:'viewer'},esc:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))});vm.runInContext(functions,context);
assert.equal(vm.runInContext('calendarGroups().length',context),8);
assert.equal(vm.runInContext("calendarGroups()[0].rows[0].name",context),'순천');
assert.equal(vm.runInContext("calendarDayEvents(calendarGroups()[2],'2026-10-02').length",context),4);
const html=vm.runInContext('compactCalendarHTML()',context),printed=vm.runInContext('compactCalendarHTML(true)',context);
assert.equal((html.match(/<tr(?: class="[^"]*")?>/g)||[]).length,9);
assert.equal((html.match(/\+2건/g)||[]).length,1);
assert.equal((html.match(/data-event=/g)||[]).length,3);
assert.equal((printed.match(/data-event=/g)||[]).length,5);
assert(!html.includes('ITC · 교섭'));assert(html.includes('교섭'));assert(!printed.includes('calendar-more'));
assert(html.includes('(~3)'));assert.equal(vm.runInContext("calendarDayEvents(calendarGroups()[2],'2026-10-03').length",context),0);
data.events.push({id:'carry',row:'s',start:'2026-09-29',end:'2026-10-05',title:'월간 계속 일정',status:'예정'});
assert.equal(vm.runInContext("calendarDayEvents(calendarGroups()[0],'2026-10-01').length",context),1);
assert(vm.runInContext('compactCalendarHTML()',context).includes('계속 (~5)'));
console.log('PASS: 8 groups, original rows preserved, two events/day, overflow counts, start-only ranges, month carry-over and complete print output');
for(const row of [{id:'common',group:'당사',name:'공통'},{id:'p',group:'당사',name:'포항'},{id:'i',group:'당사',name:'인천'},{id:'gc',group:'그룹사',name:'공통'},{id:'ac',group:'계열사',name:'공통'},{id:'lc',group:'노동계',name:'공통'},{id:'other',group:'기타',name:'기타'}])data.rows.push(row);
const options=vm.runInContext("calendarSelectOptions('a')",context);
assert.equal((options.match(/<option /g)||[]).length,8);assert(options.includes('value="ac" selected'));assert(!options.includes('ITC'));assert(options.includes('당사 / 공통'));
console.log('PASS: eight dropdown choices and legacy affiliate automatically maps to the aggregate selection');

context.scheduleZoom=true;context.scheduleAnchor='2026-10-08';data.events.push({id:'range',row:'d',start:'2026-10-03',end:'2026-10-09',title:'교섭',status:'예정',kind:'교섭'});const zoom=vm.runInContext('compactCalendarHTML()',context);assert.equal((zoom.match(/<th data-calendar-date=/g)||[]).length,14);assert(zoom.includes('data-event="range"'));assert(zoom.includes('schedule-tone-labor'));assert.equal((vm.runInContext('compactCalendarHTML(true)',context).match(/<th data-calendar-date=/g)||[]).length,31);assert.equal(vm.runInContext("scheduleTone({title:'간담회'})",context),'meeting');assert.equal(vm.runInContext("scheduleTone({title:'품평회'})",context),'general');console.log('PASS: fourteen-day view includes ongoing events, semantic colors and full-month printing');
assert.equal(vm.runInContext("scheduleSplitTitle({id:'group'},'포스코, 하청노동자교섭').actor",context),'포스코');
assert.equal(vm.runInContext("scheduleSplitTitle({id:'group'},'현대차 본교섭').title",context),'본교섭');
assert.equal(vm.runInContext("scheduleSplitTitle({id:'common'},'포스코, 하청노동자교섭').actor",context),'');
assert.equal(vm.runInContext("scheduleSplitTitle({id:'group'},'포스코').actor",context),'');
assert.equal(vm.runInContext("scheduleTitleForSave({actor:'포스코',title:'포스코, 교섭'})",context),'포스코, 교섭');
assert.equal(vm.runInContext("scheduleTitleForSave({actor:'',title:'기존, 제목'})",context),'기존, 제목');
console.log('PASS: actor parsing is limited to applicable rows and preserves unchanged titles');

context.scheduleAnchor='2026-10-29';const cross=vm.runInContext('compactCalendarHTML()',context);assert(cross.includes('data-calendar-date="2026-10-29"'));assert(cross.includes('data-calendar-date="2026-11-11"'));assert.equal((cross.match(/<th data-calendar-date=/g)||[]).length,14);console.log('PASS: next fourteen days cross month boundaries');

assert(source.includes("let scheduleZoom=false,scheduleAnchor=''"));console.log("PASS: monthly view is the default as before the two-week default change");
context.scheduleMonth="2026-10";context.scheduleAnchor="2026-10-02";context.scheduleZoom=true;const nodes={};context.$=key=>nodes[key]||(nodes[key]={showModal(){this.open=true}});context.$$=()=>[];vm.runInContext(source.slice(source.indexOf("function openCalendarDay("),source.indexOf("function renderScheduleCandidates(")),context);vm.runInContext("openCalendarDay('dangjin','2026-10-02')",context);assert(nodes["#calendarDayDialog"].open);assert.equal((nodes["#calendarDayList"].innerHTML.match(/data-day-event/g)||[]).length,4);console.log("PASS: overflow opens all four events");

context.scheduleMonth="2026-10";context.scheduleAnchor="2026-10-02";data.events.push({id:"actor-layout",row:"a",start:"2026-10-02",end:"2026-10-02",title:"비지회, 교섭 회의",status:"예정"});context.scheduleZoom=true;const focus=vm.runInContext("compactCalendarHTML()",context);assert(focus.includes("schedule-event-meta"));assert(focus.includes("schedule-actor"));context.scheduleZoom=false;const month=vm.runInContext("compactCalendarHTML()",context);assert(!month.includes("schedule-event-meta"));console.log("PASS: focus cards use the latest layout while monthly remains the default");
