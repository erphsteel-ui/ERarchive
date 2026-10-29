'use strict';
let scheduleData=null, scheduleReview=false, scheduleActive=false, scheduleEditing=null, scheduleRowsDraft=[], scheduleRowsPrevious=[];
let scheduleMonth=new Date().getFullYear()+'-'+String(new Date().getMonth()+1).padStart(2,'0');
let scheduleZoom=true,scheduleAnchor='';
let scheduleRequest=0,scheduleSources=[],scheduleSourceSelected='',scheduleSourceLimit=30,scheduleSourceMode=true,sourcePreviewTicket=0;
function syncReaderTabs(schedule){for(const [id,on] of [['readerScheduleTab',schedule],['readerArchiveTab',!schedule]]){const button=$('#'+id);button.classList.toggle('active',on);button.setAttribute('aria-pressed',String(on))}}
$('#readerScheduleTab').onclick=()=>showSchedule(false);
$('#readerArchiveTab').onclick=()=>{company='';draftOnly=false;scheduleExit();render()};
function scheduleExit(){if(typeof closeRegulations==='function')closeRegulations();if($('#scheduleHoverTip'))$('#scheduleHoverTip').hidden=true;if(typeof closeFinancials==='function')closeFinancials();if(typeof closeMemos==='function')closeMemos();if(typeof closeNews==='function')closeNews();syncReaderTabs(false);document.body.classList.remove('schedule-open');scheduleActive=false;scheduleRequest++;$('#schedulePanel').hidden=true;$('#archiveContent').hidden=false;$('#scheduleNav').classList.remove('active');$('#scheduleReviewNav').classList.remove('active');$('#allNav').classList.add('active');$('#schedulePrintSheet').replaceChildren()}
async function syncScheduleHome(){if(user.role!=='admin')await showSchedule(false);else scheduleExit()}
for(const id of ['allNav','draftNav'])$('#'+id).addEventListener('click',scheduleExit);
$('#logout').addEventListener('click',()=>{$('#scheduleEventDialog').close();$('#scheduleSourceDialog').close();$('#scheduleRowsDialog').close();scheduleExit()});
$('#scheduleNav').onclick=()=>showSchedule(false);
$('#scheduleReviewNav').onclick=()=>showSchedule(true);
async function showSchedule(review=false){
 if(typeof closeRegulations==='function')closeRegulations();
 if(typeof closeFinancials==='function')closeFinancials();
 if(typeof closeMemos==='function')closeMemos();
 if(typeof closeNews==='function')closeNews();
 const ticket=++scheduleRequest;
 syncReaderTabs(true);document.body.classList.add('schedule-open');scheduleReview=review&&user.role==='admin';scheduleActive=true;$('#archiveContent').hidden=true;$('#schedulePanel').hidden=false;$('#allNav').classList.remove('active');$('#scheduleNav').classList.toggle('active',!scheduleReview);$('#scheduleReviewNav').classList.toggle('active',scheduleReview);$('#schedulePrintSheet').replaceChildren();
 $('#schedulePanel').innerHTML='<p role="status">일정표를 불러오는 중…</p>';
 try{const result=await api('schedule?month='+encodeURIComponent(scheduleMonth));if(scheduleZoom){const end=scheduleAddDays(scheduleAnchorValue(),13);if(end.slice(0,7)!==scheduleMonth){const next=await api('schedule?month='+end.slice(0,7));const seen=new Set(result.events.map(e=>e.id));result.events.push(...next.events.filter(e=>!seen.has(e.id)))}}if(user.role==='admin'){const review=await api('schedule/review-sources');if(ticket!==scheduleRequest)return;scheduleSources=review.groups||review.sources;}if(scheduleActive&&ticket===scheduleRequest){scheduleData=result;renderSchedule()}}catch(e){if(ticket!==scheduleRequest)return;$('#schedulePanel').innerHTML='<p role="alert">'+esc(e.message)+'</p><button id="scheduleTry">다시 시도</button>';$('#scheduleTry').onclick=()=>showSchedule(review)}
}

function renderSchedule(){
 const admin=user.role==='admin',pending=scheduleData.pending||[];
 $('#schedulePanel').innerHTML=`<div class="schedule-heading"><div><span class="eyebrow">노사 주요 일정</span><h1>${scheduleReview?'일정 확인 · 검토':scheduleZoom?'향후 2주 주요 일정':esc(scheduleMonth.replace('-','년 '))+'월 주요 일정'}</h1></div><div class="actions"><button id="scheduleRefresh">새로고침</button>${!scheduleReview?'<button id="schedulePrint">A3 가로 인쇄</button>':''}${admin?'<button id="scheduleRows">조직·사업장 편집</button><button id="scheduleAdd" class="primary">＋ 일정 추가</button>':''}</div></div><div class="schedule-controls"><button id="schedulePrev" aria-label="이전 달">←</button><input id="scheduleMonth" type="month" aria-label="일정 월" value="${esc(scheduleMonth)}"><button id="scheduleNext" aria-label="다음 달">→</button><button id="scheduleToday">이번 달</button><button id="scheduleCopyWeek" type="button">📋 금주 일정 요약 복사</button>${!scheduleReview?`<div class="schedule-view-toggle" role="group" aria-label="일정 보기 범위"><button id="scheduleFull" aria-pressed="${!scheduleZoom}">전체(월간)</button><button id="scheduleTwoWeeks" aria-pressed="${scheduleZoom}">오늘 기준 향후 2주</button></div>`:''}${admin?`<button id="scheduleView">${scheduleReview?'월간 일정표 보기':`검토할 자료 ${scheduleSources.filter(s=>!s.done||s.pending).length}건`}</button>`:''}</div><div id="scheduleMain"></div>`;
 $('#schedulePrint')?.addEventListener('click',()=>{prepareSchedulePrint();window.print()});
 $('#scheduleRefresh').onclick=()=>showSchedule(scheduleReview);$('#scheduleView')?.addEventListener('click',()=>showSchedule(!scheduleReview));
 $('#scheduleMonth').onchange=e=>{if(e.target.value){scheduleZoom=false;scheduleMonth=e.target.value;showSchedule(scheduleReview)}};
 function shift(delta){scheduleZoom=false;const [y,m]=scheduleMonth.split('-').map(Number),d=new Date(y,m-1+delta,1);scheduleMonth=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');showSchedule(scheduleReview)}
 $('#schedulePrev').onclick=()=>shift(-1);$('#scheduleNext').onclick=()=>shift(1);$('#scheduleToday').onclick=()=>{scheduleAnchor=scheduleTodayISO();const d=new Date();scheduleMonth=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');showSchedule(scheduleReview)};
 $('#scheduleFull')?.addEventListener('click',()=>{scheduleZoom=false;showSchedule(false)});$('#scheduleCopyWeek').onclick=copyScheduleWeek;$('#scheduleTwoWeeks')?.addEventListener('click',()=>{scheduleZoom=true;scheduleAnchor=scheduleTodayISO();scheduleMonth=scheduleAnchor.slice(0,7);showSchedule(false)});
 $('#scheduleAdd')?.addEventListener('click',()=>openScheduleEvent());$('#scheduleRows')?.addEventListener('click',openScheduleRows);
 if(scheduleReview&&admin)renderScheduleReview();else renderScheduleGrid();
}
function calendarGroups(){
 const groups=[['common','당사 / 공통'],['pohang','당사 / 포항'],['dangjin','당사 / 당진'],['incheon','당사 / 인천'],['group','그룹사'],['affiliate','계열사'],['labor','노동계'],['other','기타']].map(([id,label])=>({id,label,rows:[]}));
 for(const row of scheduleData.rows){let key='other';if(row.group==='당사')key=({'포항':'pohang','당진':'dangjin','인천':'incheon'})[row.name]||'common';else key=({'그룹사':'group','계열사':'affiliate','노동계':'labor'})[row.group]||'other';groups.find(g=>g.id===key).rows.push(row)}
 return groups;
}
function calendarSelectOptions(selected){
 const groups=calendarGroups(),selectedGroup=groups.find(g=>g.rows.some(r=>r.id===selected));
 return groups.map(g=>{const row=g.rows.find(r=>r.name==='공통')||g.rows[0];return row?`<option value="${esc(row.id)}" ${selectedGroup?.id===g.id?'selected':''}>${esc(g.label)}</option>`:''}).join('');
}
function calendarDayEvents(group,date,firstDate=scheduleMonth+'-01'){
 const ids=new Set(group.rows.map(r=>r.id));
 return scheduleData.events.filter(e=>ids.has(e.row)&&e.end>=date&&(e.start===date||(date===firstDate&&e.start<date))).sort((a,b)=>a.start.localeCompare(b.start)||a.title.localeCompare(b.title,'ko')||a.id.localeCompare(b.id));
}
const SCHEDULE_ACTORS=['현대제철내화','포항지부','민주노총','트랜시스','케피코','현대차','기아차','포스코','비지회','IMC','금속'];
function scheduleActorGroup(group){return ['group','affiliate','labor','other'].includes(group?.id)}
function scheduleSplitTitle(group,title){
 const original=String(title||'');if(!scheduleActorGroup(group))return {actor:'',title:original};
 const comma=original.indexOf(',');if(comma>0){const actor=original.slice(0,comma).trim(),rest=original.slice(comma+1).trim();if(actor&&rest)return {actor,title:rest}}
 const trimmed=original.trim(),actor=SCHEDULE_ACTORS.find(name=>trimmed.startsWith(name));if(actor){const rest=trimmed.slice(actor.length).replace(/^[\s,·:：-]+/,'').trim();if(rest)return {actor,title:rest}}
 return {actor:'',title:original};
}
function scheduleActorFields(){return `<div class="schedule-actor-fields" hidden><label>주체(회사·조직명)<input name="actor" maxlength="60" placeholder="예: 포스코"></label><div class="schedule-actor-chips" aria-label="자주 쓰는 주체">${SCHEDULE_ACTORS.map(name=>`<button type="button" data-actor-choice="${esc(name)}">${esc(name)}</button>`).join('')}</div><p class="hint">주체를 입력하면 ‘주체, 일정 내용’으로 저장됩니다.</p></div>`}
function setupScheduleActorFields(form){const fields=form.querySelector('.schedule-actor-fields'),select=form.elements.row,input=form.elements.actor;if(!fields||!select||!input)return;const update=()=>{const group=calendarGroups().find(g=>g.rows.some(r=>r.id===select.value));fields.hidden=!scheduleActorGroup(group);input.disabled=fields.hidden};select.addEventListener('change',update);fields.querySelectorAll('[data-actor-choice]').forEach(button=>button.onclick=()=>{input.value=button.dataset.actorChoice;input.focus()});update()}
function scheduleTitleForSave(values){const actor=(values.actor||'').trim(),title=(values.title||'').trim();delete values.actor;if(!actor)return title;const split=scheduleSplitTitle({id:'other'},title);return actor+', '+(split.actor===actor?split.title:title)}
function calendarEventLabel(group,event){return event.title}
function calendarRangeLabel(event){if(event.start===event.end)return '';const end=event.end.slice(0,7)===scheduleMonth?String(Number(event.end.slice(8))):Number(event.end.slice(5,7))+'/'+Number(event.end.slice(8));return (event.start<scheduleMonth+'-01'?'계속 ':'')+'(~'+end+')'}
function scheduleAddDays(value,days){const [y,m,d]=value.split('-').map(Number),date=new Date(y,m-1,d+days);return date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0')}
function scheduleTodayISO(){const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
function scheduleAnchorValue(){const today=scheduleTodayISO();return scheduleAnchor.startsWith(scheduleMonth+'-')?scheduleAnchor:today.startsWith(scheduleMonth+'-')?today:scheduleMonth+'-01'}
function scheduleTone(e){const text=(e.title||'')+' '+(e.kind||'');return /교섭|결의대회|투쟁|파업|쟁대위|잠정합의/.test(text)?'labor':/운영위|수련회|회의|간담회|토론회|집담회/.test(text)?'meeting':'general'}
function scheduleVisibleDates(all=false){
 const [y,m]=scheduleMonth.split('-').map(Number),days=new Date(y,m,0).getDate();
 if(!all&&scheduleZoom)return Array.from({length:14},(_,i)=>scheduleAddDays(scheduleAnchorValue(),i));
 return Array.from({length:days},(_,i)=>scheduleMonth+'-'+String(i+1).padStart(2,'0'));
}
function scheduleCardHTML(group,e,all=false){
 const split=scheduleSplitTitle(group,e.title),range=calendarRangeLabel(e),time=e.time||'',result=e.result||'';
 const meta=[split.actor?`<span class="schedule-actor">[${esc(split.actor)}]</span>`:'',range?`<small class="calendar-range">${esc(range)}</small>`:'',time?`<small class="schedule-time">${esc(time)}</small>`:'',result?`<small class="schedule-result-tag">${esc(result)}</small>`:''].filter(Boolean).join('');
 return `<div class="schedule-event-wrap"><button class="schedule-event schedule-tone-${scheduleTone(e)} ${['취소','보류'].includes(e.status)?'schedule-muted':''}" data-event="${esc(e.id)}"><b>${['취소','보류'].includes(e.status)?'['+esc(e.status)+'] ':''}${esc(split.title)}</b>${meta?`<span class="schedule-event-meta">${meta}</span>`:''}</button>${!all&&user.role==='admin'?`<span class="schedule-event-actions"><button type="button" data-event-edit="${esc(e.id)}">수정</button><button type="button" data-event-cancel="${esc(e.id)}">취소</button></span>`:''}</div>`;
}
function compactCalendarHTML(all=false){
 const dates=scheduleVisibleDates(all),today=scheduleTodayISO(),firstDate=dates[0];let html='<thead><tr><th class="schedule-org">구분 / 조직·사업장</th>';
 for(const date of dates){const [y,m,day]=date.split('-').map(Number),w=new Date(y,m-1,day).getDay();html+=`<th data-calendar-date="${date}" class="${w===0||w===6?'weekend':''} ${date===today?'schedule-today':''}">${scheduleZoom&&!all&&day===1?m+'/':''}${day}${date===today?'<span class="schedule-today-badge">TODAY</span>':''}<small>${'일월화수목금토'[w]}</small></th>`}html+='</tr></thead><tbody>';
 for(const group of calendarGroups()){
  const ids=new Set(group.rows.map(r=>r.id)),hasEvents=scheduleData.events.some(e=>ids.has(e.row)&&e.start<=dates[dates.length-1]&&e.end>=firstDate);
  html+=`<tr class="${hasEvents?'':'schedule-empty-row'}"><th class="schedule-org">${esc(group.label)}</th>`;
  for(const date of dates){
   const [y,m,day]=date.split('-').map(Number),events=calendarDayEvents(group,date,firstDate),w=new Date(y,m-1,day).getDay(),occupied=scheduleData.events.some(e=>ids.has(e.row)&&e.start<=date&&e.end>=date);
   html+=`<td data-calendar-date="${date}" data-calendar-group="${esc(group.id)}" data-calendar-empty="${!occupied}" class="${w===0||w===6?'weekend':''} ${date===today?'schedule-today':''}"><div class="calendar-day">${(all?events:events.slice(0,2)).map(e=>scheduleCardHTML(group,e,all)).join('')}${!all&&events.length>2?`<button class="calendar-more" data-day-group="${group.id}" data-day-date="${date}">+${events.length-2}건</button>`:''}${!all&&user.role==='admin'?`<button class="calendar-add" data-add-group="${group.id}" data-add-date="${date}" aria-label="${esc(group.label)} ${date} 일정 추가">＋</button>`:''}</div></td>`;
  }html+='</tr>';
 }return html+'</tbody>';
}
function renderScheduleGrid(){
 if($('#scheduleHoverTip'))$('#scheduleHoverTip').hidden=true;
 $('#scheduleMain').innerHTML='<p class="schedule-grid-hint">하루 최대 2개 표시 · +건수를 누르면 전체 일정 확인 · 기간 일정은 시작일에 종료일 표시 · 주말은 밝은 청보라색입니다.</p><div class="schedule-scroll '+(scheduleZoom?'schedule-zoom-scroll':'schedule-month-scroll')+'" tabindex="0" aria-label="'+(scheduleZoom?'향후 2주 일정표':'월간 일정표')+'"><table class="schedule-table compact-calendar '+(scheduleZoom?'schedule-two-weeks':'')+'">'+compactCalendarHTML()+'</table></div>';
 $$('[data-event]').forEach(b=>b.onclick=()=>openScheduleEvent(scheduleData.events.find(e=>e.id===b.dataset.event)));
 $$('[data-event-edit]').forEach(b=>b.onclick=e=>{e.stopPropagation();openScheduleEvent(scheduleData.events.find(item=>item.id===b.dataset.eventEdit))});
 $$('[data-event-cancel]').forEach(b=>b.onclick=async e=>{e.stopPropagation();const item=scheduleData.events.find(x=>x.id===b.dataset.eventCancel);if(!item||!confirm('이 일정을 취소 상태로 변경할까요?'))return;b.disabled=true;try{await api('schedule/event',{...item,status:'취소',state:'published'});await showSchedule(false);toast('일정 상태를 취소로 변경했습니다.')}catch(err){toast(err.message);b.disabled=false}});
 $$('[data-day-group]').forEach(b=>b.onclick=()=>openCalendarDay(b.dataset.dayGroup,b.dataset.dayDate));
 $$('[data-add-group]').forEach(b=>b.onclick=e=>{e.stopPropagation();openQuickSchedule(b.dataset.addGroup,b.dataset.addDate)});
 const scroll=$('#scheduleMain .schedule-scroll');scroll.onclick=e=>{if(!user.user||e.target.closest('button,a,input,select'))return;const cell=e.target.closest('td[data-calendar-group][data-calendar-empty="true"]');if(cell)openQuickSchedule(cell.dataset.calendarGroup,cell.dataset.calendarDate)};let tip=$('#scheduleHoverTip');if(!tip){tip=document.createElement('div');tip.id='scheduleHoverTip';tip.setAttribute('role','tooltip');tip.hidden=true;document.body.append(tip)}
 const clear=()=>{tip.hidden=true;scroll.querySelectorAll('.schedule-range-hover').forEach(cell=>cell.classList.remove('schedule-range-hover'))};
 scroll.onmouseover=e=>{const button=e.target.closest('[data-event]');if(!button||button.contains(e.relatedTarget))return;clear();const event=scheduleData.events.find(x=>x.id===button.dataset.event),cell=button.closest('[data-calendar-group]');if(!event||!cell)return;scroll.querySelectorAll('td[data-calendar-group]').forEach(td=>{if(td.dataset.calendarGroup===cell.dataset.calendarGroup&&td.dataset.calendarDate>=event.start&&td.dataset.calendarDate<=event.end)td.classList.add('schedule-range-hover')});const group=calendarGroups().find(g=>g.id===cell.dataset.calendarGroup),row=scheduleData.rows.find(r=>r.id===event.row);tip.innerHTML=`<strong>${esc(event.title)}</strong><p>${esc(event.start)} ~ ${esc(event.end)}</p><p>${esc(group?.label||'')}${row?.name?' · '+esc(row.name):''}${event.time?' · '+esc(event.time):''}${event.place?' · '+esc(event.place):''}</p>${event.description||event.detail?`<p>${esc(event.description||event.detail)}</p>`:''}`;tip.hidden=false;const rect=button.getBoundingClientRect(),height=tip.offsetHeight,width=tip.offsetWidth;tip.style.left=Math.max(8,Math.min(innerWidth-width-8,rect.left))+'px';tip.style.top=Math.max(8,Math.min(innerHeight-height-8,rect.bottom+6))+'px'};
 scroll.onmouseout=e=>{const button=e.target.closest('[data-event]');if(button&&!button.contains(e.relatedTarget))clear()};scroll.addEventListener('scroll',clear);
 requestAnimationFrame(fitReaderSchedule);
}
function openQuickSchedule(groupID,date){
 if(!user.user)return;
 const group=calendarGroups().find(g=>g.id===groupID);if(!group)return;
 const row=group.rows.find(r=>r.name==='공통')||group.rows[0];let d=$('#scheduleQuickDialog');if(!d){d=document.createElement('dialog');d.id='scheduleQuickDialog';document.body.append(d)}
 d.innerHTML=`<div class="modalhead"><h2>빠른 일정 등록</h2><button type="button" id="scheduleQuickClose">닫기</button></div>${row?`<form id="scheduleQuickForm"><label>일정 내용<input name="title" required maxlength="180" autocomplete="off"></label><label>조직·사업장<select name="row" required>${calendarSelectOptions(row.id)}</select></label>${scheduleActorFields()}<label>날짜<input name="start" type="date" value="${esc(date)}" required></label><label>종료일 (선택)<input name="end" type="date"></label><p class="hint">등록하면 팀원 일정표에 바로 표시됩니다.</p><p id="scheduleQuickError" role="alert"></p><button class="primary">등록</button></form>`:`<p>이 행에 연결된 조직·사업장이 없습니다. 조직·사업장 편집에서 먼저 추가해 주세요.</p>`}`;
 $('#scheduleQuickClose').onclick=()=>d.close();const form=$('#scheduleQuickForm');if(form)setupScheduleActorFields(form);if(form)form.onsubmit=async e=>{e.preventDefault();if(form.dataset.saving)return;form.dataset.saving='1';const button=form.querySelector('button[type=submit],button.primary');button.disabled=true;try{const values=Object.fromEntries(new FormData(form));values.title=scheduleTitleForSave(values);if(values.title.length>180)throw Error('주체와 일정 내용을 합쳐 180자 이하로 입력하세요.');await api('schedule/event',{...values,kind:'일정',status:'예정',state:'published'});d.close();await showSchedule(false);toast('일정을 등록했습니다.')}catch(err){$('#scheduleQuickError').textContent=err.message}finally{delete form.dataset.saving;button.disabled=false}};
 if(!d.open)d.showModal();if(form)form.elements.title.focus();
}
function openCalendarDay(groupID,date){
 const group=calendarGroups().find(g=>g.id===groupID),events=calendarDayEvents(group,date,scheduleVisibleDates()[0]);
 $('#calendarDayHeading').textContent=date+' · '+group.label;
 $('#calendarDayList').innerHTML=events.map(e=>`<button data-day-event="${esc(e.id)}"><b>${esc(calendarEventLabel(group,e))}</b><small>${esc(e.start)} ~ ${esc(e.end)} · ${esc(e.status)}</small></button>`).join('');
 $$('[data-day-event]').forEach(b=>b.onclick=()=>{ $('#calendarDayDialog').close();openScheduleEvent(scheduleData.events.find(e=>e.id===b.dataset.dayEvent))});
 $('#calendarDayDialog').showModal();
}
function renderScheduleCandidates(){
 const info=scheduleData.info||{},pending=scheduleData.pending||[];
 $('#scheduleMain').innerHTML=`<p>모든 달의 미확인 후보입니다. 날짜·주체·활동을 확인한 뒤 게시하세요. 발행일·날짜만 있는 문구·명확한 과거 보고는 제외합니다. 날짜나 활동을 확실히 읽지 못한 내용은 원문에서 확인해 주세요.</p><div class="schedule-status"><span>${esc(info.message||'')} ${esc(info.last_scan||'')}</span><button id="scheduleScan">일정 다시 검사</button><button id="scheduleRejectDuplicates">중복 의심 일괄 제외</button></div>${(info.errors||[]).map(e=>`<p class="schedule-warning">${esc(e)}</p>`).join('')}<div class="schedule-review-list">${pending.length?pending.map(e=>`<div class="schedule-candidate" data-candidate="${esc(e.id)}" role="button" tabindex="0"><button type="button" class="schedule-quick-reject" data-reject-candidate="${esc(e.id)}" aria-label="${esc(e.title)} 제외">✕ 제외</button><span>${esc(e.start)}${e.end!==e.start?' ~ '+esc(e.end):''}</span><b>${esc(e.title)}</b><small>출처: ${esc(e.source_name||'직접 입력')}</small><small>주체: ${esc(e.subject||scheduleData.rows.find(r=>r.id===e.row)?.name||'미확인 · 관리자 선택')}</small><small>${esc(e.warnings.join(' · '))}</small>${e.duplicates?.length?'<strong>같은 일정 가능성 · 중복 확인 필요</strong>':''}</div>`).join(''):'<p>확인할 일정이 없습니다. 이미지 OCR이 완료되거나 HWP를 수집하면 후보가 표시됩니다.</p>'}</div><details><summary>최근 추출 자료 · 후보가 없는 자료도 확인</summary>${(scheduleData.sources||[]).map(s=>`<p><button data-source="${esc(s.id)}">${esc(s.name)}</button> · ${esc(s.status)}</p>`).join('')||'<p>아직 추출 자료가 없습니다.</p>'}</details>`;
 $('#scheduleScan').onclick=async()=>{try{const r=await api('schedule/scan',{});toast(r.message)}catch(e){toast(e.message)}};
 async function reject(items){try{await api('schedule/reject-candidates',{items:items.map(e=>({id:e.id,version:e.version}))});await showSchedule(true);toast(items.length+'건을 제외했습니다.')}catch(e){toast(e.message);await showSchedule(true)}}
 $$('[data-reject-candidate]').forEach(b=>b.onclick=e=>{e.stopPropagation();const item=pending.find(x=>x.id===b.dataset.rejectCandidate);if(item)reject([item])});
 $('#scheduleRejectDuplicates').onclick=()=>{const items=pending.filter(e=>e.duplicates?.length);if(!items.length)return toast('중복 의심 후보가 없습니다.');if(items.length>500)return toast('한 번에 500건까지 제외할 수 있습니다.');if(confirm('중복 경고가 표시된 미확인 후보 '+items.length+'건을 모두 제외할까요? 서로 중복된 후보는 양쪽 모두 제외될 수 있습니다.'))reject(items)};
 $$('[data-candidate]').forEach(b=>{b.onclick=()=>openScheduleEvent(pending.find(e=>e.id===b.dataset.candidate));b.onkeydown=e=>{if(e.target===b&&(e.key==='Enter'||e.key===' ')){e.preventDefault();b.click()}}});
 $$('[data-source]').forEach(b=>b.onclick=()=>openScheduleSource(b.dataset.source));
}
function openScheduleEvent(event=null,date=scheduleMonth+'-01',row=''){
 scheduleEditing=event?structuredClone(event):{start:date,end:'',time:'',end_time:'',title:'',place:'',row,kind:'일정',status:'예정',state:'pending'};
 const e=scheduleEditing,admin=user.role==='admin';$('#scheduleEventHeading').textContent=admin?(e.id?'일정 확인 · 수정':'일정 추가'):'일정 상세';
 if(!admin){$('#scheduleEventBody').innerHTML=`<h2>${esc(e.title)}</h2><p>${esc(e.start)}${e.end!==e.start?' ~ '+esc(e.end):''}</p><p>${esc(scheduleData.rows.find(r=>r.id===e.row)?.name||'')} · ${esc(e.status)}</p>${e.source_name?'<p>출처: '+esc(e.source_name)+'</p>':''}${e.memo_id?'<button id="scheduleMemoLink" type="button">원본 동향 메모 보기</button>':''}`;bindScheduleMemoLink(e);appendScheduleContext(e);$('#scheduleEventDialog').showModal();return}
 const input=(key,label,type='text')=>`<label>${label}<input name="${key}" type="${type}" value="${esc(key==='end'&&e.end===e.start?'':e[key]||'')}" ${['title','start'].includes(key)?'required':''} ${type==='text'?'maxlength="180"':''}></label>`;
 $('#scheduleEventBody').innerHTML=`<form id="scheduleEventForm"><div class="schedule-form-grid">${input('title','일정 내용')}<label>표시할 조직·사업장<select name="row"><option value="">미지정 · 관리자 선택</option>${calendarSelectOptions(e.row)}</select></label>${scheduleActorFields()}${input('start','시작일','date')}${input('end','종료일 (선택 · 비우면 당일)','date')}<label>유형<select name="kind">${['일정','회의','교섭','교육','집회','마감'].map(k=>`<option ${e.kind===k?'selected':''}>${k}</option>`).join('')}</select></label><label>진행 상태<select name="status">${['예정','확정','완료','보류','취소'].map(k=>`<option ${e.status===k?'selected':''}>${k}</option>`).join('')}</select></label></div>${e.duplicates?.length?'<p class="schedule-warning">같은 일정 가능성: '+e.duplicates.map(esc).join(', ')+' · 기존 일정과 비교해 중복 후보는 제외하세요.</p>':''}${e.warnings?.length?'<p class="schedule-warning">'+e.warnings.map(esc).join(' · ')+'</p>':''}${e.quote?'<details open><summary>추출 근거 · 원문</summary><pre class="schedule-quote">'+esc(e.quote)+'</pre></details>':''}${e.source?'<p class="schedule-source-name">출처: '+esc(e.source_name||'원본 자료')+'</p><button type="button" id="scheduleOpenSource">'+(e.source_kind==='hwp'?'HWP 원문 · 원본 파일 다운로드':'원본 이미지 · 추출 본문 확인')+'</button>':''}${e.memo_id?'<button id="scheduleMemoLink" type="button">원본 동향 메모 보기</button>':''}<p id="scheduleEventError" role="alert"></p><div class="actions"><button type="button" id="scheduleReject" class="danger">${e.id?'제외 / 게시 취소':'취소'}</button><button type="button" id="scheduleDraft">검토용 저장 (비공개)</button><button class="primary">${e.state==='published'?'수정하고 게시':'확인하고 게시'}</button></div></form>`;
 setupScheduleActorFields($('#scheduleEventForm'));bindScheduleMemoLink(e);appendScheduleContext(e);
 $('#scheduleOpenSource')?.addEventListener('click',()=>openScheduleSource(e.source));
 $('#scheduleEventForm').onsubmit=ev=>{ev.preventDefault();saveScheduleEvent('published')};$('#scheduleDraft').onclick=()=>{if($('#scheduleEventForm').reportValidity())saveScheduleEvent('pending')};
 $('#scheduleReject').onclick=()=>{if(!e.id){$('#scheduleEventDialog').close();return}if(confirm('이 일정을 검토 목록과 팀원 일정표에서 제외할까요?'))saveScheduleEvent('rejected')};
 $('#scheduleEventDialog').showModal();
}
async function saveScheduleEvent(state){
 const form=$('#scheduleEventForm');if(form.dataset.saving)return;form.dataset.saving='1';form.querySelectorAll('button').forEach(b=>b.disabled=true);
 try{const data=Object.fromEntries(new FormData(form));data.title=scheduleTitleForSave(data);if(data.title.length>180)throw Error('주체와 일정 내용을 합쳐 180자 이하로 입력하세요.');await api('schedule/event',{...data,id:scheduleEditing.id,version:scheduleEditing.version,source:scheduleEditing.source,memo_id:scheduleEditing.memo_id,state});$('#scheduleEventDialog').close();await showSchedule(scheduleReview);toast(state==='published'?'일정을 게시했습니다.':'일정 검토 내용을 저장했습니다.')}catch(e){$('#scheduleEventError').textContent=e.message}finally{delete form.dataset.saving;form.querySelectorAll('button').forEach(b=>b.disabled=false)}
}
async function openScheduleSource(id){try{const data=await api('schedule/source/'+encodeURIComponent(id));$('#scheduleSourceTitle').textContent=data.name;$('#scheduleSourceText').textContent=data.text;const url='/api/schedule/source/'+encodeURIComponent(id)+'?download=1';$('#scheduleSourceDownload').href=url;$('#scheduleSourceDownload').textContent=data.kind==='hwp'?'HWP 원본 다운로드 · '+data.name:'원본 이미지 열기';$('#scheduleSourceImage').hidden=data.kind!=='image';if(data.kind==='image')$('#scheduleSourceImage').src=url;else $('#scheduleSourceImage').removeAttribute('src');$('#scheduleSourceDialog').showModal()}catch(e){toast(e.message)}}
async function copyScheduleWeek(){
 try{
  const today=scheduleTodayISO(),parts=today.split('-').map(Number),weekday=new Date(parts[0],parts[1]-1,parts[2]).getDay(),start=scheduleAddDays(today,-((weekday+6)%7)),end=scheduleAddDays(start,6);
  const months=[...new Set([start.slice(0,7),end.slice(0,7)])],results=await Promise.all(months.map(month=>api('schedule?month='+month))),seen=new Set(),events=[];
  for(const result of results)for(const event of result.events)if(!seen.has(event.id)&&event.start<=end&&event.end>=start){seen.add(event.id);events.push(event)}
  const lines=[`[금주 일정] ${start} ~ ${end}`];
  for(const group of calendarGroups()){
   const ids=new Set(group.rows.map(r=>r.id)),items=events.filter(e=>ids.has(e.row)).sort((a,b)=>a.start.localeCompare(b.start)||a.title.localeCompare(b.title,'ko'));
   if(items.length){lines.push('',`■ ${group.label}`);for(const e of items)lines.push(`- ${e.start}${e.end!==e.start?' ~ '+e.end:''} ${e.title}${e.result?' ['+e.result+']':''}`)}
  }
  if(!events.length)lines.push('등록된 일정이 없습니다.');
  const text=lines.join('\n');if(navigator.clipboard&&window.isSecureContext)await navigator.clipboard.writeText(text);else{const input=document.createElement('textarea');input.value=text;document.body.append(input);input.select();const ok=document.execCommand('copy');input.remove();if(!ok)throw Error('copy failed')}
  toast('금주 일정을 복사했습니다.');
 }catch(err){toast('일정을 복사하지 못했습니다. 다시 시도해 주세요.')}
}
function appendScheduleContext(event){
 if(!event.id||event.state!=='published')return;
 const body=$('#scheduleEventBody'),section=document.createElement('section');section.className='schedule-context';
 const resultOptions=['진행중','잠정합의','결렬','정회','특이사항 없음'];
 section.innerHTML=`<h3>일정 결과</h3><p class="schedule-result-current">${event.result?esc(event.result)+(event.result_note?' · '+esc(event.result_note):''):'등록된 결과 없음'}</p>${user.role==='admin'?`<div class="schedule-result-controls">${resultOptions.map(value=>`<button type="button" data-schedule-result="${value}" aria-pressed="${event.result===value}">${value}</button>`).join('')}<label>한 줄 메모<input id="scheduleResultNote" maxlength="180" value="${esc(event.result_note||'')}" placeholder="결과 메모 (선택)"></label><button type="button" id="scheduleResultSave">결과 저장</button><p id="scheduleResultError" role="alert"></p></div>`:''}<h3>날짜가 가까운 자료</h3><p class="hint">일정 시작일 전후 1일에 등록 또는 발행된 후보입니다. 관련 여부는 내용을 확인해 주세요.</p><div class="schedule-related" role="status">자료를 불러오는 중…</div>`;
 body.append(section);
 if(user.role==='admin'){
  let selected=event.result||'';
  section.querySelectorAll('[data-schedule-result]').forEach(button=>button.onclick=()=>{selected=button.dataset.scheduleResult;section.querySelectorAll('[data-schedule-result]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));section.querySelector('#scheduleResultSave').click()});
  section.querySelector('#scheduleResultSave').onclick=async()=>{const error=section.querySelector('#scheduleResultError');if(!selected){error.textContent='결과 상태를 선택하세요.';return}try{const note=section.querySelector('#scheduleResultNote').value;const result=await api('schedule/result',{id:event.id,version:event.version,result:selected,note});event.version=result.version;event.result=selected;event.result_note=note.trim();const live=scheduleData.events.find(e=>e.id===event.id);if(live)Object.assign(live,{version:event.version,result:selected,result_note:event.result_note});section.querySelector('.schedule-result-current').textContent=selected+(event.result_note?' · '+event.result_note:'');error.textContent='저장했습니다.';if(!scheduleReview)renderScheduleGrid()}catch(err){error.textContent=err.message}};
 }
 const start=scheduleAddDays(event.start,-1),end=scheduleAddDays(event.start,1),near=date=>date&&date.slice(0,10)>=start&&date.slice(0,10)<=end;
 Promise.all([api('memos?all=1'),api('documents')]).then(([memos,documents])=>{
  if(!section.isConnected)return;docs=documents;
  const notes=memos.items.filter(m=>near(m.received)||near(m.created)),items=documents.filter(d=>near(d.date)||near(d.created));
  const panel=section.querySelector('.schedule-related');panel.removeAttribute('role');panel.innerHTML=`<h4>동향메모 (${notes.length})</h4>${notes.map(m=>`<button type="button" data-related-memo="${esc(m.id)}">${esc(m.received)} · ${esc(m.title)}</button>`).join('')||'<p>해당 기간에 등록된 메모가 없습니다.</p>'}<h4>홍보물 (${items.length})</h4>${items.map(d=>`<button type="button" data-related-doc="${esc(d.id)}">${esc(d.date||d.created?.slice(0,10)||'날짜 미상')} · ${esc(d.title)}</button>`).join('')||'<p>해당 기간에 등록된 홍보물이 없습니다.</p>'}`;
  panel.querySelectorAll('[data-related-memo]').forEach(button=>button.onclick=()=>{$('#scheduleEventDialog').close();openMemo(button.dataset.relatedMemo)});
  panel.querySelectorAll('[data-related-doc]').forEach(button=>button.onclick=()=>{$('#scheduleEventDialog').close();openDoc(button.dataset.relatedDoc)});
 }).catch(()=>{if(section.isConnected)section.querySelector('.schedule-related').textContent='자료를 불러오지 못했습니다. 일정을 다시 열어 주세요.'});
}
function openScheduleRows(){$('#scheduleRowsError').textContent='';scheduleRowsPrevious=structuredClone(scheduleData.rows);scheduleRowsDraft=structuredClone(scheduleData.rows);renderScheduleRows();$('#scheduleRowsDialog').showModal()}
function renderScheduleRows(){
 $('#scheduleRowsBody').innerHTML=scheduleRowsDraft.map((r,i)=>`<div class="schedule-row-edit"><input aria-label="그룹" data-row-index="${i}" data-row-field="group" maxlength="60" value="${esc(r.group)}"><input aria-label="조직·사업장" data-row-index="${i}" data-row-field="name" maxlength="60" value="${esc(r.name)}"><button data-row-up="${i}" ${i===0?'disabled':''}>↑</button><button data-row-delete="${i}">삭제</button></div>`).join('');
 $$('[data-row-field]').forEach(el=>el.oninput=()=>scheduleRowsDraft[Number(el.dataset.rowIndex)][el.dataset.rowField]=el.value);
 $$('[data-row-up]').forEach(el=>el.onclick=()=>{const i=Number(el.dataset.rowUp);[scheduleRowsDraft[i-1],scheduleRowsDraft[i]]=[scheduleRowsDraft[i],scheduleRowsDraft[i-1]];renderScheduleRows()});
 $$('[data-row-delete]').forEach(el=>el.onclick=()=>{scheduleRowsDraft.splice(Number(el.dataset.rowDelete),1);renderScheduleRows()});
}
$('#scheduleRowAdd').onclick=()=>{scheduleRowsDraft.push({id:'row-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,10),group:'기타',name:'새 조직'});renderScheduleRows()};
$('#scheduleRowsSave').onclick=async()=>{try{await api('schedule/rows',{rows:scheduleRowsDraft,previous:scheduleRowsPrevious});$('#scheduleRowsDialog').close();await showSchedule(scheduleReview)}catch(e){$('#scheduleRowsError').textContent=e.message}};

function prepareSchedulePrint(){
 const sheet=$('#schedulePrintSheet');sheet.replaceChildren();document.body.classList.remove('schedule-print-ready');
 if(!scheduleActive||scheduleReview||!$('#schedulePanel .schedule-table'))return;
 document.body.classList.add('schedule-print-ready');
 const heading=document.createElement('h1');heading.textContent=(scheduleData.month||scheduleMonth).replace('-','년 ')+'월 노사 주요 일정';sheet.append(heading);
 const table=$('#schedulePanel .schedule-table').cloneNode(true);table.innerHTML=compactCalendarHTML(true);table.classList.remove('compact-calendar');
 table.querySelectorAll('.schedule-empty').forEach(el=>el.remove());
 table.querySelectorAll('.schedule-event').forEach(el=>{const span=document.createElement('div');span.className=el.className;span.textContent=[el.querySelector('b')?.textContent,...[...el.querySelectorAll('.schedule-event-meta > *')].map(item=>item.textContent)].filter(Boolean).join(' ');el.replaceWith(span)});
 sheet.append(table);
}
window.addEventListener('beforeprint',prepareSchedulePrint);

function renderScheduleReview(){
 if(!scheduleSourceMode){renderScheduleCandidates();$('#scheduleMain').insertAdjacentHTML('afterbegin','<button id="reviewModeSources">문서별로 검토</button>');$('#reviewModeSources').textContent='문서별로 검토';$('#reviewModeSources').onclick=()=>{scheduleSourceMode=true;renderScheduleReview()};return}
 const sources=scheduleSources.filter(s=>!s.done||s.pending),selected=sources.find(s=>s.id===scheduleSourceSelected)||sources[0];
 scheduleSourceSelected=selected?.id||'';
 $('#scheduleMain').innerHTML=`<div class="schedule-status"><span>미검토 문서 ${sources.length}건 · 추출 결과가 없어도 원본을 확인할 수 있습니다.</span><button id="reviewModeCandidates">일정 후보별 보기</button><button id="sourceRescan">일정 다시 검사</button></div><div class="source-review-layout"><nav class="source-review-list" aria-label="수집 문서">${sources.slice(0,scheduleSourceLimit).map(s=>`<button data-review-source="${esc(s.id)}" class="${s.id===selected?.id?'active':''}"><b>${esc(s.name)}</b><small>${esc(s.kind)} · ${(s.members||[s]).length}쪽 · 후보 ${s.pending}건</small></button>`).join('')||'<p>미검토 문서가 없습니다.</p>'}${sources.length>scheduleSourceLimit?'<button id="sourceMore">더 보기</button>':''}</nav><section id="sourceReviewDetail"></section></div>`;
 $('#reviewModeCandidates').onclick=()=>{scheduleSourceMode=false;renderScheduleReview()};
 $('#sourceRescan').onclick=async()=>{try{const r=await api('schedule/scan',{});toast(r.message)}catch(e){toast(e.message)}};
 $('#sourceMore')?.addEventListener('click',()=>{scheduleSourceLimit+=30;renderScheduleReview()});
 $$('[data-review-source]').forEach(b=>b.onclick=()=>{scheduleSourceSelected=b.dataset.reviewSource;renderScheduleReview()});
 if(selected)renderSourceReview(selected);
}
async function renderSourceReview(source){
 const members=source.members||[source],ids=new Set(members.map(m=>m.id)),candidates=(scheduleData.pending||[]).filter(e=>ids.has(e.source)),host=$('#sourceReviewDetail'),ticket=++sourcePreviewTicket;let index=0;
 host.innerHTML=`<h3>${esc(source.name)} · ${members.length}쪽</h3><div class="source-review-work"><div class="source-review-original"><div class="actions source-page-controls"><button id="reviewPagePrev">← 이전</button><span id="reviewPageCount"></span><button id="reviewPageNext">다음 →</button><button id="reviewZoomOut" type="button">−</button><span id="reviewZoomLabel">100%</span><button id="reviewZoomIn" type="button">＋</button></div><div id="reviewPagePreview"></div></div><div class="source-review-panel"><details open><summary>OCR 추출 본문</summary><pre id="reviewSourceText">불러오는 중…</pre></details><p>필요한 일정만 게시하고 나머지는 제외하세요.</p><div class="source-candidates">${candidates.map(e=>`<div><div class="source-candidate-content"><b>${esc(e.title)}</b><small>${esc(e.start)} ~ ${esc(e.end)}</small></div><button data-source-event="${esc(e.id)}">✔ 승인/추가</button><button data-source-reject="${esc(e.id)}">✕ 제외</button></div>`).join('')||'<p>추출된 미확인 일정이 없습니다. 원본에 일정이 있으면 아래에서 직접 추가하세요.</p>'}</div><div class="actions"><button id="sourceAddEvent">＋ 원본 보며 일정 추가</button><button id="sourceComplete" class="primary">검토 완료</button><button id="sourceNone">남은 후보 모두 제외 · 완료</button><button id="sourceLater">나중에 확인</button></div><p class="hint">검토 완료는 남은 후보가 없을 때 가능합니다. 게시한 일정은 문서 검토 완료 시에도 유지됩니다.</p></div></div>`;
 $$('[data-source-event]').forEach(b=>b.onclick=async()=>{const item=candidates.find(e=>e.id===b.dataset.sourceEvent);if(!item)return;if(!item.row||!scheduleData.rows.some(r=>r.id===item.row)){openScheduleEvent(item);return}b.disabled=true;try{await api('schedule/event',{...item,state:'published'});await showSchedule(true);toast('일정을 승인해 게시했습니다.')}catch(err){toast(err.message);b.disabled=false}});
 $$('[data-source-reject]').forEach(b=>b.onclick=async()=>{const e=candidates.find(x=>x.id===b.dataset.sourceReject);b.disabled=true;try{await api('schedule/reject-candidates',{items:[{id:e.id,version:e.version}]});await showSchedule(true)}catch(err){toast(err.message);b.disabled=false}});
 $('#sourceAddEvent').onclick=()=>{openScheduleEvent();scheduleEditing.source=members[index].id};
 async function finish(action){if(action==='none'&&candidates.length&&!confirm('이 문서의 남은 후보 '+candidates.length+'건을 모두 제외하고 검토 완료할까요?'))return;try{await api('schedule/review-source',{sources:members.map(m=>({source:m.id,signature:m.signature})),action,versions:Object.fromEntries(candidates.map(e=>[e.id,e.version]))});await showSchedule(true)}catch(e){toast(e.message)}}
 $('#sourceComplete').onclick=()=>finish('complete');$('#sourceNone').onclick=()=>finish('none');
 $('#sourceLater').onclick=()=>{const list=scheduleSources.filter(s=>!s.done||s.pending),i=list.findIndex(s=>s.id===source.id);scheduleSourceSelected=list[(i+1)%list.length]?.id||'';renderScheduleReview()};
 let pageRequest=0,sourceZoom=1;
 function applySourceZoom(){const img=$('#reviewPagePreview img');if(img)img.style.width=Math.round(sourceZoom*100)+'%';$('#reviewZoomLabel').textContent=Math.round(sourceZoom*100)+'%'}
 $('#reviewZoomOut').onclick=()=>{sourceZoom=Math.max(1,sourceZoom-.25);applySourceZoom()};$('#reviewZoomIn').onclick=()=>{sourceZoom=Math.min(4,sourceZoom+.25);applySourceZoom()};
 async function showPage(){
  host.querySelector('.source-review-original').scrollTop=0;
  const current=members[index],request=++pageRequest,url='/api/schedule/source/'+encodeURIComponent(current.id)+'?download=1';
  $('#reviewPagePrev').disabled=index===0;$('#reviewPageNext').disabled=index===members.length-1;$('#reviewPageCount').textContent=(index+1)+' / '+members.length+'쪽';
  $('#reviewPagePreview').innerHTML=`<a href="${url}" target="_blank" rel="noopener">원본 열기 · 다운로드</a>${current.kind==='image'?`<img src="${url}" alt="원본 ${index+1}쪽">`:'<p>HWP는 추출 본문 또는 원본 다운로드로 확인하세요.</p>'}`;
  applySourceZoom();$('#reviewSourceText').textContent='불러오는 중…';try{const data=await api('schedule/source/'+encodeURIComponent(current.id));if(host.isConnected&&ticket===sourcePreviewTicket&&request===pageRequest)$('#reviewSourceText').textContent=data.text||'인식된 본문이 없습니다. 원본을 확인하세요.'}catch(e){if(host.isConnected&&ticket===sourcePreviewTicket&&request===pageRequest)$('#reviewSourceText').textContent=e.message}
 }
 $('#reviewPagePrev').onclick=()=>{if(index>0){index--;showPage()}};$('#reviewPageNext').onclick=()=>{if(index<members.length-1){index++;showPage()}};
 showPage();
}

function fitReaderSchedule(){
 if(!scheduleActive)return;
 const scroll=$('#scheduleMain .schedule-scroll');if(!scroll)return;
 const available=Math.max(200,window.innerHeight-scroll.getBoundingClientRect().top-20);
 scroll.style.setProperty('--monthly-scroll-height',available+'px');
 if(scheduleZoom)scroll.style.setProperty('--calendar-row-height',Math.max(20,Math.min(80,(available-50)/8))+'px');
 else scroll.style.removeProperty('--calendar-row-height');
}
let readerResizeFrame=0;
window.addEventListener('resize',()=>{cancelAnimationFrame(readerResizeFrame);readerResizeFrame=requestAnimationFrame(fitReaderSchedule)});

function bindScheduleMemoLink(event){$('#scheduleMemoLink')?.addEventListener('click',()=>{$('#scheduleEventDialog').close();if(typeof openMemo==='function')openMemo(event.memo_id)})}
