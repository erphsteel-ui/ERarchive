'use strict';
let precisionReview=null,precisionLoading=false,precisionSaving=false;
async function loadPrecision(fill=false){
 if(precisionLoading)return;precisionLoading=true;
 try{const r=await api('precision');
 if(fill){$('#precisionPath').value=r.config.path;$('#precisionEnabled').checked=r.config.enabled}
 $('#precisionMessage').textContent=r.status.message+(r.status.errors.length?' · '+r.status.errors.join(' / '):'');
 $('#precisionRuntime').textContent=(r.runtime.ready?'로컬 모델 파일 확인 완료':'모델 경로 확인 필요')+'\nPython: '+r.runtime.python+'\n레이아웃: '+r.runtime.layout+'\nVL: '+r.runtime.model+(r.runtime.missing.length?'\n누락: '+r.runtime.missing.join('\n'):'');
 const labels={queued:'대기 중',running:'정밀 인식 중',done:'완료 · 확인 필요',failed:'실패 · 재시도 가능',reviewed:'검토 완료'};
 $('#precisionJobs').innerHTML=r.jobs.map(j=>`<div class="schedule-intake-job"><strong>${esc(j.name)}</strong><span>${esc(labels[j.state]||j.state)}${j.seconds?' · '+Math.round(j.seconds)+'초':''}${j.decision==='keep'?' · 기존 본문 유지':j.decision==='apply'?' · 본문 적용':''}</span>${j.error?'<p>'+esc(j.error)+'</p>':''}${['done','reviewed'].includes(j.state)?'<button data-precision-review="'+esc(j.hash)+'">원본·결과 비교</button>':''}${j.state==='failed'?'<button data-precision-retry="'+esc(j.hash)+'">다시 시도</button>':''}</div>`).join('')||'<p>정밀 인식 대기 자료가 없습니다. 지정 폴더에 이미지를 넣거나, 자료 상세의 본문 OCR 화면에서 정밀 재처리를 예약하세요.</p>';
 $$('[data-precision-review]').forEach(b=>b.onclick=()=>openPrecisionReview(b.dataset.precisionReview));
 $$('[data-precision-retry]').forEach(b=>b.onclick=async()=>{try{await api('precision/'+b.dataset.precisionRetry+'/retry',{});await loadPrecision()}catch(e){$('#precisionMessage').textContent=e.message}});
 }catch(e){$('#precisionMessage').textContent=e.message}finally{precisionLoading=false}
}
async function openPrecision(){if(!$('#precisionDialog').open)$('#precisionDialog').showModal();await loadPrecision(true)}
$('#precisionButton').onclick=openPrecision;$('#precisionRefresh').onclick=()=>loadPrecision();
$('#precisionSave').onclick=async()=>{try{await api('precision/config',{path:$('#precisionPath').value.trim(),enabled:$('#precisionEnabled').checked});await loadPrecision(true)}catch(e){$('#precisionMessage').textContent=e.message}};
$('#queuePrecision').onclick=async()=>{
 if(!ocrReview)return;const b=$('#queuePrecision');b.disabled=true;
 try{const r=await api('precision/page/'+ocrReview.pid,{});$('#ocrStatus').textContent=r.created?'정밀 재처리를 예약했습니다. 브라우저를 닫아도 서버가 켜져 있으면 처리합니다. 완료 결과는 ‘정밀 인식 · 결과 검토’에서 확인하세요.':'이미 정밀 인식 대기열에 있는 자료입니다. ‘정밀 인식 · 결과 검토’에서 확인하세요.'}catch(e){$('#ocrStatus').textContent=e.message}finally{b.disabled=false}
};
async function openPrecisionReview(hash){
 try{const j=await api('precision/'+hash);precisionReview=j;
 $('#precisionReviewTitle').textContent=j.name;$('#precisionBefore').value=j.current;$('#precisionAfter').value=j.result;$('#precisionBaseline').textContent=j.baseline;
 $('#precisionImage').src='/api/precision/'+hash+'/image';$('#precisionOriginalLink').href=$('#precisionImage').src;
 $('#precisionDestinationLabel').hidden=j.target!=='new';$('#precisionAfter').readOnly=j.state!=='done';
 $('#precisionKeep').textContent=j.target==='new'?'등록하지 않고 보관':'기존 본문 유지';
 $('#precisionApply').disabled=j.state!=='done'||j.target==='busy';$('#precisionKeep').disabled=j.state!=='done';
 $('#precisionReviewMessage').textContent=j.state==='reviewed'?'검토를 완료한 결과입니다. 보존된 인식 결과와 현재 본문을 비교할 수 있습니다.':j.target==='busy'?'1차 처리가 진행 중입니다. 완료 후 다시 열어 주세요.':j.target==='new'?'아직 등록되지 않은 이미지입니다. 본문을 확인하고 등록 위치를 선택하세요.':'같은 이미지의 기존 자료를 찾았습니다. 적용하면 검색 본문이 바뀌고 일정 후보가 다시 검토됩니다.';
 if(!$('#precisionReviewDialog').open)$('#precisionReviewDialog').showModal();
 }catch(e){$('#precisionMessage').textContent=e.message}
}
async function decidePrecision(action){
 if(!precisionReview||precisionSaving)return;
 if(action==='apply'&&!$('#precisionAfter').value.trim())return $('#precisionReviewMessage').textContent='적용할 본문을 입력하세요.';
 precisionSaving=true;$('#precisionApply').disabled=true;$('#precisionKeep').disabled=true;
 try{await api('precision/'+precisionReview.hash+'/review',{action,version:precisionReview.version,token:precisionReview.token,text:$('#precisionAfter').value,destination:$('#precisionDestination').value});
 $('#precisionReviewDialog').close();precisionReview=null;await loadPrecision();await refresh();toast(action==='apply'?'검토한 본문을 적용했습니다. 일정 후보는 다음 백그라운드 검사에 반영됩니다.':'기존 본문을 유지했습니다.');
 }catch(e){$('#precisionReviewMessage').textContent=e.message}finally{precisionSaving=false;if(precisionReview){$('#precisionApply').disabled=false;$('#precisionKeep').disabled=false}}
}
$('#precisionApply').onclick=()=>decidePrecision('apply');$('#precisionKeep').onclick=()=>decidePrecision('keep');
setInterval(()=>{if(user?.role==='admin'&&$('#precisionDialog').open&&!precisionSaving)loadPrecision()},5000);
