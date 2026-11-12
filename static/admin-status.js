'use strict';
let adminStatusBusy=false;
async function pollAdminStatus(){
 if(user?.role!=='admin'||adminStatusBusy)return;
 adminStatusBusy=true;
 try{const data=await api('admin/status');for(const [id,key] of [['scheduleReviewNav','schedule'],['batchButton','batches'],['draftNav','drafts']]){const badge=$('#'+id+' .admin-count');if(badge){const count=data.counts[key]||0;badge.textContent=String(count);badge.hidden=count===0;badge.setAttribute('aria-label',count+'건')}}for(const [id,count] of [['adminScheduleAlert',data.counts.schedule||0],['adminPublicationAlert',(data.counts.batches||0)+(data.counts.drafts||0)]]){const alert=$('#'+id);if(alert){alert.hidden=!count;alert.querySelector('span').textContent=String(count);if(id==='adminPublicationAlert')alert.dataset.hasBatches=String((data.counts.batches||0)>0)}}}
 catch(e){console.error('검토 건수를 불러오지 못했습니다.',e);}finally{adminStatusBusy=false}
}
setInterval(pollAdminStatus,5000);setTimeout(pollAdminStatus,500);

$('#adminMenuToggle').onclick=()=>{const open=document.body.classList.toggle('admin-menu-open');$('#adminMenuToggle').setAttribute('aria-expanded',String(open))};$('#adminScheduleAlert').onclick=()=>{$('#scheduleReviewNav').click()};$('#adminPublicationAlert').onclick=()=>{if($('#adminPublicationAlert').dataset.hasBatches==='true')$('#batchButton').click();else $('#draftNav').click()};$('#adminMenuPanel').addEventListener('click',e=>{if(e.target.closest('button')){document.body.classList.remove('admin-menu-open');$('#adminMenuToggle').setAttribute('aria-expanded','false')}});
