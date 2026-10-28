'use strict';
let scheduleData=null, scheduleReview=false, scheduleActive=false, scheduleEditing=null, scheduleRowsDraft=[], scheduleRowsPrevious=[];
let scheduleMonth=new Date().getFullYear()+'-'+String(new Date().getMonth()+1).padStart(2,'0');
let scheduleRequest=0,scheduleSources=[],scheduleSourceSelected='',scheduleSourceLimit=30,scheduleSourceMode=true,sourcePreviewTicket=0;
function syncReaderTabs(schedule){for(const [id,on] of [['readerScheduleTab',schedule],['readerArchiveTab',!schedule]]){const button=$('#'+id);button.classList.toggle('active',on);button.setAttribute('aria-pressed',String(on))}}
$('#readerScheduleTab').onclick=()=>showSchedule(false);
$('#readerArchiveTab').onclick=()=>scheduleExit();
function scheduleExit(){if(typeof closeFinancials==='function')closeFinancials();if(typeof closeMemos==='function')closeMemos();if(typeof closeNews==='function')closeNews();syncReaderTabs(false);document.body.classList.remove('schedule-open');scheduleActive=false;scheduleRequest++;$('#schedulePanel').hidden=true;$('#archiveContent').hidden=false;$('#scheduleNav').classList.remove('active');$('#scheduleReviewNav').classList.remove('active');$('#allNav').classList.add('active');$('#schedulePrintSheet').replaceChildren()}
async function syncScheduleHome(){if(user.role!=='admin')await showSchedule(false);else scheduleExit()}
for(const id of ['allNav','draftNav'])$('#'+id).addEventListener('click',scheduleExit);
$('#logout').addEventListener('click',()=>{$('#scheduleEventDialog').close();$('#scheduleSourceDialog').close();$('#scheduleRowsDialog').close();scheduleExit()});
$('#scheduleNav').onclick=()=>showSchedule(false);
$('#scheduleReviewNav').onclick=()=>showSchedule(true);
async function showSchedule(review=false){
 if(typeof closeFinancials==='function')closeFinancials();
 if(typeof closeMemos==='function')closeMemos();
 if(typeof closeNews==='function')closeNews();
 const ticket=++scheduleRequest;
 syncReaderTabs(true);document.body.classList.add('schedule-open');scheduleReview=review&&user.role==='admin';scheduleActive=true;$('#archiveContent').hidden=true;$('#schedulePanel').hidden=false;$('#allNav').classList.remove('active');$('#scheduleNav').classList.toggle('active',!scheduleReview);$('#scheduleReviewNav').classList.toggle('active',scheduleReview);$('#schedulePrintSheet').replaceChildren();
 $('#schedulePanel').innerHTML='<p role="status">일정표를 불러오는 중…</p>';
 try{const result=await api('schedule?month='+encodeURIComponent(scheduleMonth));if(user.role==='admin'){const review=await api('schedule/review-sources');if(ticket!==scheduleRequest)return;scheduleSources=review.groups||review.sources;}if(scheduleActive&&ticket===scheduleRequest){scheduleData=result;renderSchedule()}}catch(e){if(ticket!==scheduleRequest)return;$('#schedulePanel').innerHTML='<p role="alert">'+esc(e.message)+'</p><button id="scheduleTry">다시 시도</button>';$('#scheduleTry').onclick=()=>showSchedule(review)}
}

function renderSchedule(){
 const admin=user.role==='admin',pending=scheduleData.pending||[];
 $('#schedulePanel').innerHTML=`<div class="schedule-heading"><div><span class="eyebrow">노사 주요 일정</span><h1>${scheduleReview?'일정 확인 · 검토':esc(scheduleMonth.replace('-','년 '))+'월 주요 일정'}</h1></div><div class="actions"><button id="scheduleRefresh">새로고침</button>${!scheduleReview?'<button id="schedulePrint">A3 가로 인쇄</button>':''}${admin?'<button id="scheduleRows">조직·사업장 편집</button><button id="scheduleAdd" class="primary">＋ 일정 추가</button>':''}</div></div><div class="schedule-controls"><button id="schedulePrev" aria-label="이전 달">←</button><input id="scheduleMonth" type="month" aria-label="일정 월" value="${esc(scheduleMonth)}"><button id="scheduleNext" aria-label="다음 달">→</button><button id="scheduleToday">이번 달</button>${admin?`<button id="scheduleView">${scheduleReview?'월간 일정표 보기':`검토할 자료 ${scheduleSources.filter(s=>!s.done||s.pending).length}건`}</button>`:''}</div><div id="scheduleMain"></div>`;
 $('#schedulePrint')?.addEventListener('click',()=>{prepareSchedulePrint();window.print()});
 $('#scheduleRefresh').onclick=()=>showSchedule(scheduleReview);$('#scheduleView')?.addEventListener('click',()=>showSchedule(!scheduleReview));
 $('#scheduleMonth').onchange=e=>{if(e.target.value){scheduleMonth=e.target.value;showSchedule(scheduleReview)}};
 function shift(delta){const [y,m]=scheduleMonth.split('-').map(Number),d=new Date(y,m-1+delta,1);scheduleMonth=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');showSchedule(scheduleReview)}
 $('#schedulePrev').onclick=()=>shift(-1);$('#scheduleNext').onclick=()=>shift(1);$('#scheduleToday').onclick=()=>{const d=new Date();scheduleMonth=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');showSchedule(scheduleReview)};
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
function calendarDayEvents(group,date){
 const ids=new Set(group.rows.map(r=>r.id));
 return scheduleData.events.filter(e=>ids.has(e.row)&&e.end>=date&&(e.start===date||(date===scheduleMonth+'-01'&&e.start<date))).sort((a,b)=>a.start.localeCompare(b.start)||a.title.localeCompare(b.title,'ko')||a.id.localeCompare(b.id));
}
function calendarEventLabel(group,event){return event.title}
function calendarRangeLabel(event){if(event.start===event.end)return '';const end=event.end.slice(0,7)===scheduleMonth?String(Number(event.end.slice(8))):Number(event.end.slice(5,7))+'/'+Number(event.end.slice(8));return (event.start<scheduleMonth+'-01'?'계속 ':'')+'(~'+end+')'}
function compactCalendarHTML(all=false){
 const [year,month]=scheduleMonth.split('-').map(Number),days=new Date(year,month,0).getDate();let html='<thead><tr><th class="schedule-org">구분 / 조직·사업장</th>';
 for(let day=1;day<=days;day++){const w=new Date(year,month-1,day).getDay();html+=`<th class="${w===0||w===6?'weekend':''}">${day}<small>${'일월화수목금토'[w]}</small></th>`}html+='</tr></thead><tbody>';
 for(const group of calendarGroups()){
  html+=`<tr><th class="schedule-org">${esc(group.label)}</th>`;
  for(let day=1;day<=days;day++){
   const date=scheduleMonth+'-'+String(day).padStart(2,'0'),events=calendarDayEvents(group,date),w=new Date(year,month-1,day).getDay();
   html+=`<td class="${w===0||w===6?'weekend':''}"><div class="calendar-day">${(all?events:events.slice(0,2)).map(e=>`<button class="schedule-event ${['취소','보류'].includes(e.status)?'schedule-muted':''}" data-event="${esc(e.id)}" title="${esc(e.start)} ~ ${esc(e.end)} · ${esc(calendarEventLabel(group,e))}"><b>${['취소','보류'].includes(e.status)?'['+esc(e.status)+'] ':''}${esc(calendarEventLabel(group,e))}</b>${calendarRangeLabel(e)?`<small class="calendar-range">${esc(calendarRangeLabel(e))}</small>`:''}</button>`).join('')}${!all&&events.length>2?`<button class="calendar-more" data-day-group="${group.id}" data-day-date="${date}">+${events.length-2}건</button>`:''}${!all&&user.role==='admin'?`<button class="calendar-add" data-add-group="${group.id}" data-add-date="${date}" aria-label="${esc(group.label)} ${date} 일정 추가">＋</button>`:''}</div></td>`;
  }html+='</tr>';
 }return html+'</tbody>';
}
function renderScheduleGrid(){
 $('#scheduleMain').innerHTML='<p class="schedule-grid-hint">하루 최대 2개 표시 · +건수를 누르면 전체 일정 확인 · 기간 일정은 시작일에 종료일 표시 · 주말은 밝은 청보라색입니다.</p><div class="schedule-scroll" tabindex="0" aria-label="월간 일정표"><table class="schedule-table compact-calendar">'+compactCalendarHTML()+'</table></div>';
 $$('[data-event]').forEach(b=>b.onclick=()=>openScheduleEvent(scheduleData.events.find(e=>e.id===b.dataset.event)));
 $$('[data-day-group]').forEach(b=>b.onclick=()=>openCalendarDay(b.dataset.dayGroup,b.dataset.dayDate));
 $$('[data-add-group]').forEach(b=>b.onclick=()=>{const group=calendarGroups().find(g=>g.id===b.dataset.addGroup);openScheduleEvent(null,b.dataset.addDate,group.rows[0]?.id||'')});
 requestAnimationFrame(fitReaderSchedule);
}
function openCalendarDay(groupID,date){
 const group=calendarGroups().find(g=>g.id===groupID),events=calendarDayEvents(group,date);
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
 if(!admin){$('#scheduleEventBody').innerHTML=`<h2>${esc(e.title)}</h2><p>${esc(e.start)}${e.end!==e.start?' ~ '+esc(e.end):''}</p><p>${esc(scheduleData.rows.find(r=>r.id===e.row)?.name||'')} · ${esc(e.status)}</p>${e.source_name?'<p>출처: '+esc(e.source_name)+'</p>':''}${e.memo_id?'<button id="scheduleMemoLink" type="button">원본 동향 메모 보기</button>':''}`;bindScheduleMemoLink(e);$('#scheduleEventDialog').showModal();return}
 const input=(key,label,type='text')=>`<label>${label}<input name="${key}" type="${type}" value="${esc(key==='end'&&e.end===e.start?'':e[key]||'')}" ${['title','start'].includes(key)?'required':''} ${type==='text'?'maxlength="180"':''}></label>`;
 $('#scheduleEventBody').innerHTML=`<form id="scheduleEventForm"><div class="schedule-form-grid">${input('title','행사명')}<label>표시할 조직·사업장<select name="row"><option value="">미지정 · 관리자 선택</option>${calendarSelectOptions(e.row)}</select></label>${input('start','시작일','date')}${input('end','종료일 (선택 · 비우면 당일)','date')}<label>유형<select name="kind">${['일정','회의','교섭','교육','집회','마감'].map(k=>`<option ${e.kind===k?'selected':''}>${k}</option>`).join('')}</select></label><label>진행 상태<select name="status">${['예정','확정','완료','보류','취소'].map(k=>`<option ${e.status===k?'selected':''}>${k}</option>`).join('')}</select></label></div>${e.duplicates?.length?'<p class="schedule-warning">같은 일정 가능성: '+e.duplicates.map(esc).join(', ')+' · 기존 일정과 비교해 중복 후보는 제외하세요.</p>':''}${e.warnings?.length?'<p class="schedule-warning">'+e.warnings.map(esc).join(' · ')+'</p>':''}${e.quote?'<details open><summary>추출 근거 · 원문</summary><pre class="schedule-quote">'+esc(e.quote)+'</pre></details>':''}${e.source?'<p class="schedule-source-name">출처: '+esc(e.source_name||'원본 자료')+'</p><button type="button" id="scheduleOpenSource">'+(e.source_kind==='hwp'?'HWP 원문 · 원본 파일 다운로드':'원본 이미지 · 추출 본문 확인')+'</button>':''}${e.memo_id?'<button id="scheduleMemoLink" type="button">원본 동향 메모 보기</button>':''}<p id="scheduleEventError" role="alert"></p><div class="actions"><button type="button" id="scheduleReject" class="danger">${e.id?'제외 / 게시 취소':'취소'}</button><button type="button" id="scheduleDraft">검토용 저장 (비공개)</button><button class="primary">${e.state==='published'?'수정하고 게시':'확인하고 게시'}</button></div></form>`;
 bindScheduleMemoLink(e);
 $('#scheduleOpenSource')?.addEventListener('click',()=>openScheduleSource(e.source));
 $('#scheduleEventForm').onsubmit=ev=>{ev.preventDefault();saveScheduleEvent('published')};$('#scheduleDraft').onclick=()=>{if($('#scheduleEventForm').reportValidity())saveScheduleEvent('pending')};
 $('#scheduleReject').onclick=()=>{if(!e.id){$('#scheduleEventDialog').close();return}if(confirm('이 일정을 검토 목록과 팀원 일정표에서 제외할까요?'))saveScheduleEvent('rejected')};
 $('#scheduleEventDialog').showModal();
}
async function saveScheduleEvent(state){
 const form=$('#scheduleEventForm');if(form.dataset.saving)return;form.dataset.saving='1';form.querySelectorAll('button').forEach(b=>b.disabled=true);
 try{const data=Object.fromEntries(new FormData(form));await api('schedule/event',{...data,id:scheduleEditing.id,version:scheduleEditing.version,source:scheduleEditing.source,memo_id:scheduleEditing.memo_id,state});$('#scheduleEventDialog').close();await showSchedule(scheduleReview);toast(state==='published'?'일정을 게시했습니다.':'일정 검토 내용을 저장했습니다.')}catch(e){$('#scheduleEventError').textContent=e.message}finally{delete form.dataset.saving;form.querySelectorAll('button').forEach(b=>b.disabled=false)}
}
async function openScheduleSource(id){try{const data=await api('schedule/source/'+encodeURIComponent(id));$('#scheduleSourceTitle').textContent=data.name;$('#scheduleSourceText').textContent=data.text;const url='/api/schedule/source/'+encodeURIComponent(id)+'?download=1';$('#scheduleSourceDownload').href=url;$('#scheduleSourceDownload').textContent=data.kind==='hwp'?'HWP 원본 다운로드 · '+data.name:'원본 이미지 열기';$('#scheduleSourceImage').hidden=data.kind!=='image';if(data.kind==='image')$('#scheduleSourceImage').src=url;else $('#scheduleSourceImage').removeAttribute('src');$('#scheduleSourceDialog').showModal()}catch(e){toast(e.message)}}
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
 table.querySelectorAll('.schedule-event').forEach(el=>{const span=document.createElement('div');span.className=el.className;span.textContent=el.textContent;el.replaceWith(span)});
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
 host.innerHTML=`<h3>${esc(source.name)} · ${members.length}쪽</h3><div class="source-review-work"><div class="source-review-original"><div class="actions source-page-controls"><button id="reviewPagePrev">← 이전</button><span id="reviewPageCount"></span><button id="reviewPageNext">다음 →</button></div><div id="reviewPagePreview"></div></div><div><p>필요한 일정만 게시하고 나머지는 제외하세요.</p><div class="source-candidates">${candidates.map(e=>`<div><button data-source-event="${esc(e.id)}"><b>${esc(e.title)}</b><small>${esc(e.start)} ~ ${esc(e.end)}</small></button><button data-source-reject="${esc(e.id)}">✕ 제외</button></div>`).join('')||'<p>추출된 미확인 일정이 없습니다. 원본에 일정이 있으면 아래에서 직접 추가하세요.</p>'}</div><div class="actions"><button id="sourceAddEvent">＋ 원본 보며 일정 추가</button><button id="sourceComplete" class="primary">검토 완료</button><button id="sourceNone">남은 후보 모두 제외 · 완료</button><button id="sourceLater">나중에 확인</button></div><p class="hint">검토 완료는 남은 후보가 없을 때 가능합니다. 게시한 일정은 문서 검토 완료 시에도 유지됩니다.</p></div></div>`;
 $$('[data-source-event]').forEach(b=>b.onclick=()=>openScheduleEvent(candidates.find(e=>e.id===b.dataset.sourceEvent)));
 $$('[data-source-reject]').forEach(b=>b.onclick=async()=>{const e=candidates.find(x=>x.id===b.dataset.sourceReject);b.disabled=true;try{await api('schedule/reject-candidates',{items:[{id:e.id,version:e.version}]});await showSchedule(true)}catch(err){toast(err.message);b.disabled=false}});
 $('#sourceAddEvent').onclick=()=>{openScheduleEvent();scheduleEditing.source=members[index].id};
 async function finish(action){if(action==='none'&&candidates.length&&!confirm('이 문서의 남은 후보 '+candidates.length+'건을 모두 제외하고 검토 완료할까요?'))return;try{await api('schedule/review-source',{sources:members.map(m=>({source:m.id,signature:m.signature})),action,versions:Object.fromEntries(candidates.map(e=>[e.id,e.version]))});await showSchedule(true)}catch(e){toast(e.message)}}
 $('#sourceComplete').onclick=()=>finish('complete');$('#sourceNone').onclick=()=>finish('none');
 $('#sourceLater').onclick=()=>{const list=scheduleSources.filter(s=>!s.done||s.pending),i=list.findIndex(s=>s.id===source.id);scheduleSourceSelected=list[(i+1)%list.length]?.id||'';renderScheduleReview()};
 let pageRequest=0;
 async function showPage(){
  host.querySelector('.source-review-original').scrollTop=0;
  const current=members[index],request=++pageRequest,url='/api/schedule/source/'+encodeURIComponent(current.id)+'?download=1';
  $('#reviewPagePrev').disabled=index===0;$('#reviewPageNext').disabled=index===members.length-1;$('#reviewPageCount').textContent=(index+1)+' / '+members.length+'쪽';
  $('#reviewPagePreview').innerHTML=`<a href="${url}" target="_blank" rel="noopener">원본 열기 · 다운로드</a>${current.kind==='image'?`<img src="${url}" alt="원본 ${index+1}쪽">`:'<p>HWP는 추출 본문 또는 원본 다운로드로 확인하세요.</p>'}<details ${current.kind==='hwp'?'open':''}><summary>인식·추출 본문</summary><pre id="reviewSourceText">불러오는 중…</pre></details>`;
  try{const data=await api('schedule/source/'+encodeURIComponent(current.id));if(host.isConnected&&ticket===sourcePreviewTicket&&request===pageRequest)$('#reviewSourceText').textContent=data.text||'인식된 본문이 없습니다. 원본을 확인하세요.'}catch(e){if(host.isConnected&&ticket===sourcePreviewTicket&&request===pageRequest)$('#reviewSourceText').textContent=e.message}
 }
 $('#reviewPagePrev').onclick=()=>{if(index>0){index--;showPage()}};$('#reviewPageNext').onclick=()=>{if(index<members.length-1){index++;showPage()}};
 showPage();
}

function fitReaderSchedule(){
 if(user?.role==='admin'||!scheduleActive)return;
 const scroll=$('#scheduleMain .schedule-scroll');if(!scroll)return;
 if(window.innerWidth<900){scroll.style.removeProperty('--reader-grid-height');return}
 const available=Math.max(300,window.innerHeight-scroll.getBoundingClientRect().top-30);
 scroll.style.setProperty('--reader-grid-height',available+'px');scroll.style.setProperty('--calendar-row-height',Math.max(64,(available-34)/8)+'px');
}
let readerResizeFrame=0;
window.addEventListener('resize',()=>{cancelAnimationFrame(readerResizeFrame);readerResizeFrame=requestAnimationFrame(fitReaderSchedule)});

function bindScheduleMemoLink(event){$('#scheduleMemoLink')?.addEventListener('click',()=>{$('#scheduleEventDialog').close();if(typeof openMemo==='function')openMemo(event.memo_id)})}
