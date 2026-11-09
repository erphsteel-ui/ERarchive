'use strict';
let scheduleIntakeBusy=false,scheduleIntakeLoading=false;
async function loadScheduleIntake(fill=false){
 if(scheduleIntakeLoading)return;scheduleIntakeLoading=true;
 try{const r=await api('schedule/intake');if(fill){$('#scheduleIntakePath').value=r.config.path;$('#scheduleIntakeEnabled').checked=r.config.enabled}
 $('#scheduleIntakeFolderStatus').textContent=r.status.message+(r.status.errors.length?' · '+r.status.errors.join(' / '):'');
 const labels={queued:'대기 중',running:'본문 인식 중',done:'일정 추출 완료',failed:'처리 실패'};
 $('#scheduleIntakeJobs').innerHTML=r.jobs.map(j=>`<div class="schedule-intake-job"><strong>${esc(j.name)}</strong><span>${esc(labels[j.state]||j.state)}</span>${j.error?'<p>'+esc(j.error)+'</p>':''}${j.state==='done'?'<button data-intake-source="'+esc(j.kind+':'+j.hash)+'">원본·추출 본문</button>':''}${j.state==='failed'?'<button data-intake-retry="'+esc(j.hash)+'">다시 인식</button>':''}</div>`).join('')||'<p>등록한 일정자료가 없습니다.</p>';
 $$('[data-intake-source]').forEach(b=>b.onclick=()=>openScheduleSource(b.dataset.intakeSource));
 $$('[data-intake-retry]').forEach(b=>b.onclick=async()=>{try{await api('schedule/intake/'+b.dataset.intakeRetry+'/retry',{});await loadScheduleIntake()}catch(e){$('#scheduleIntakeMessage').textContent=e.message}});
 }catch(e){$('#scheduleIntakeMessage').textContent=e.message}finally{scheduleIntakeLoading=false}
}
async function openScheduleIntake(config=false){$('#scheduleIntakeMessage').textContent='';$('#scheduleIntakeConfig').open=config;$('#scheduleIntakeDialog').showModal();await loadScheduleIntake(true)}
$('#scheduleUploadButton').onclick=()=>openScheduleIntake();$('#scheduleInboxButton').onclick=()=>openScheduleIntake(true);
$('#scheduleIntakeRefresh').onclick=()=>loadScheduleIntake();
$('#scheduleIntakeReview').onclick=()=>{$('#scheduleIntakeDialog').close();showSchedule(true)};
$('#scheduleIntakeSave').onclick=async()=>{try{await api('schedule/intake/config',{path:$('#scheduleIntakePath').value.trim(),enabled:$('#scheduleIntakeEnabled').checked});$('#scheduleIntakeMessage').textContent='일정자료 수집폴더를 저장했습니다.';await loadScheduleIntake(true)}catch(e){$('#scheduleIntakeMessage').textContent=e.message}};
$('#scheduleIntakeForm').onsubmit=async e=>{e.preventDefault();if(scheduleIntakeBusy)return;const files=[...$('#scheduleIntakeFiles').files];if(!files.length)return;
 if(files.length>20||files.some(f=>f.size>15*1024*1024)||files.reduce((s,f)=>s+f.size,0)>60*1024*1024){$('#scheduleIntakeMessage').textContent='파일당 15MB, 최대 20개·총 60MB까지 올려주세요.';return}
 scheduleIntakeBusy=true;$('#scheduleIntakeSubmit').disabled=true;$('#scheduleIntakeMessage').textContent='원본 파일을 보관하는 중…';
 try{const form=new FormData();files.forEach(f=>form.append('files',f));const r=await api('schedule/intake/upload',form,true);$('#scheduleIntakeMessage').textContent=`${r.queued}개 대기열 등록 · 중복 ${r.duplicates}개 제외. 완료 후 ‘추출 일정 검토하기’를 눌러 주세요.`;$('#scheduleIntakeForm').reset();await loadScheduleIntake()}catch(err){$('#scheduleIntakeMessage').textContent=err.message}finally{scheduleIntakeBusy=false;$('#scheduleIntakeSubmit').disabled=false}
};
setInterval(()=>{if(user?.role==='admin'&&$('#scheduleIntakeDialog').open)loadScheduleIntake()},4000);
