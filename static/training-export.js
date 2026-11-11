'use strict';
let classificationReviewTicket=0,classificationReview=null;
$('#classificationExport').onclick=()=>{window.location.href='/api/classification-export'};
async function loadClassificationReview(id){
 const ticket=++classificationReviewTicket;classificationReview=null;
 const status=$('#classificationReviewStatus'),button=$('#classificationReview');
 button.disabled=true;status.textContent='확인 상태 조회 중…';
 if(user.role!=='admin')return;
 try{const data=await api('classification-review/'+encodeURIComponent(id));if(ticket!==classificationReviewTicket||current?.id!==id)return;
  classificationReview=data.review;button.disabled=false;
  const valid=data.review&&data.review.version===data.current_version;
  status.textContent=valid?'정답 확인됨':data.review?'확인 후 수정됨 · 다시 확인 필요':'아직 정답 확인 전';
  button.textContent=valid?'정답 확인 수정/취소':'분류 정답 확인';
 }catch(err){if(ticket===classificationReviewTicket)status.textContent='확인 상태 조회 실패: '+err.message}
}
$('#classificationReview').onclick=async()=>{
 if(!current||dirty){$('#detailStatus').textContent='분류와 본문을 먼저 저장한 뒤 정답을 확인하세요.';return}
 const doc=current,valid=classificationReview&&classificationReview.version===doc.version;
 const note=prompt(valid?'확인 메모를 수정하세요. 확인을 취소하려면 취소를 누른 뒤 확인 취소를 선택하세요.':'정답을 확인했습니다. 분류 근거나 메모를 입력하세요 (선택).',classificationReview?.note||'');
 let reviewed=true;if(note===null){if(!valid||!confirm('이 자료의 정답 확인 표시를 취소할까요?'))return;reviewed=false}
 const button=$('#classificationReview');button.disabled=true;
 try{await api('classification-review/'+encodeURIComponent(doc.id),{version:doc.version,note:note||'',reviewed});if(current?.id===doc.id)await loadClassificationReview(doc.id)}catch(err){$('#detailStatus').textContent=err.message;button.disabled=false}
};
