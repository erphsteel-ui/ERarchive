'use strict';
let readerZoom=1;
function resetReaderView(){readerZoom=1;$('#detailDialog').classList.remove('info-visible');$('#readerInfoToggle').setAttribute('aria-expanded','false');$('#pageImage').style.width='';$('#pageImage').style.height='';$('#imageWrap').classList.remove('reader-zoomed');$('#imageWrap').scrollTop=0;$('#imageWrap').scrollLeft=0;$('#readerZoomLabel').textContent='전체 맞춤';}
function setReaderZoom(value){readerZoom=Math.max(1,Math.min(4,value));applyReaderZoom();}
function applyReaderZoom(){
 if(user?.role==='admin')return;
 const img=$('#pageImage'),wrap=$('#imageWrap');if(!img.naturalWidth||!wrap.clientWidth||!wrap.clientHeight)return;
 wrap.classList.toggle('reader-zoomed',readerZoom>1);
 if(readerZoom===1){img.style.width='';img.style.height='';wrap.scrollTop=0;wrap.scrollLeft=0;}
 else{const scale=Math.min((wrap.clientWidth-16)/img.naturalWidth,(wrap.clientHeight-16)/img.naturalHeight)*readerZoom;img.style.width=Math.max(1,img.naturalWidth*scale)+'px';img.style.height=Math.max(1,img.naturalHeight*scale)+'px';}
 $('#readerZoomLabel').textContent=readerZoom===1?'전체 맞춤':Math.round(readerZoom*100)+'%';$('#readerZoomOut').disabled=readerZoom===1;$('#readerZoomIn').disabled=readerZoom===4;
}
$('#pageImage').addEventListener('load',applyReaderZoom);
$('#readerZoomIn').onclick=()=>setReaderZoom(readerZoom+.5);$('#readerZoomOut').onclick=()=>setReaderZoom(readerZoom-.5);$('#readerFit').onclick=()=>setReaderZoom(1);
$('#readerInfoToggle').onclick=()=>{const visible=$('#detailDialog').classList.toggle('info-visible');$('#readerInfoToggle').setAttribute('aria-expanded',String(visible));};
if(typeof ResizeObserver!=='undefined')new ResizeObserver(()=>applyReaderZoom()).observe($('#imageWrap'));
async function loadInbox(fill=false){try{const r=await api('inbox');if(fill){$('#inboxPath').value=r.config.path;$('#inboxEnabled').checked=r.config.enabled;}$('#inboxStatus').textContent=r.status.message+' · 최근 확인: '+(r.status.last_scan||'대기 중')+' · 최근 수집 '+r.status.imported+'장 / 중복 제외 '+r.status.duplicates+'장';$('#inboxErrors').innerHTML=r.status.errors.map(e=>`<p>${esc(e)}</p>`).join('');}catch(e){$('#inboxStatus').textContent=e.message;}}
$('#inboxButton').onclick=async()=>{$('#inboxDialog').showModal();await loadInbox(true);};$('#inboxRefresh').onclick=()=>loadInbox();
$('#inboxSave').onclick=async()=>{try{await api('inbox',{path:$('#inboxPath').value.trim(),enabled:$('#inboxEnabled').checked});await loadInbox(true);toast('수집폴더 설정을 저장했습니다.');}catch(e){$('#inboxStatus').textContent=e.message;}};
setInterval(()=>{if($('#inboxDialog').open&&user?.role==='admin')loadInbox();},5000);
