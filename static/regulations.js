'use strict';
let regulationsActive=false,regulationsTicket=0,regulationsSearch='',regulationsFilter='',regulationsDocs=[],regulationsMatches=[];
const regulationsCategories=[['union_act','노동조합법'],['labor_act','근로기준법'],['work_technical','기술직 취업규칙'],['work_general','일반직 취업규칙'],['agreement','단체협약'],['pohang_rules','노동조합 규칙'],['pohang_bylaws','노동조합 세칙']];
const regLabel=key=>regulationsCategories.find(x=>x[0]===key)?.[1]||key;
const regLines=text=>text.split(/\r\n|\r|\n/);
const regHeading=line=>/^\s*(?:제\s*\d+\s*(?:장|절)|\d+\)\s*.*세칙)/.test(line)?'chapter':/^\s*(?:제\s*\d+\s*조(?:\s*의\s*\d+)?(?:\s|[([【]|$)|\d+\.\d+\.\d+(?:\s|$)|[■▣])/.test(line)?'article':'';
// Extract only the heading label, never the text that follows an article title.
function regTocEntry(line,category){
 const chapter=line.match(/^\s*(제\s*\d+\s*(?:장|절)(?:\s*의\s*\d+)?\s*[^\n]*?)(?=\s*(?:제\s*\d+\s*조(?:\s*의\s*\d+)?\s*[([【]|[①②③④⑤⑥⑦⑧⑨⑩])|$)/);
 if(chapter)return {type:'chapter',level:1,label:chapter[1].trim()};
 const article=line.match(/^\s*(제\s*\d+\s*조(?:\s*의\s*\d+)?\s*(?:\([^)]*\)|\[[^\]]*\]|【[^】]*】))/);
 if(article)return {type:'article',level:2,label:article[1].trim()};
 // Numeric headings are restricted to work-rule documents when a category is known.
 const text=line.trim(),workRules=!category||category==='work_general'||category==='work_technical';
 if(workRules){
  const length=[...text].length;
  if(length<=40&&/^\d+\.\d+\.\d+\s+\S/.test(text))return {type:'article',level:3,label:text};
  if(length<=40&&/^\d+\.\d+\s+\S/.test(text))return {type:'article',level:2,label:text};
  if(length<=25&&/^\d+\.\s+\S/.test(text)&&!/다\.$/.test(text)&&!/["“”]/.test(text))return {type:'chapter',level:1,label:text};
 }
 const bylaws=line.match(/^\s*(\d+\)\s*[^\n]{0,80}?세칙)(?:\s*$|\s*[①②③④⑤⑥⑦⑧⑨⑩])/);
 if(bylaws)return {type:'chapter',level:1,label:bylaws[1].trim()};
 return null;
}
const regRegex=q=>new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');
function regHighlight(text,q){if(!q)return esc(text);const regex=regRegex(q);let html='',last=0,m;while((m=regex.exec(text))){html+=esc(text.slice(last,m.index))+'<mark>'+esc(m[0])+'</mark>';last=m.index+m[0].length}return html+esc(text.slice(last))}
function closeRegulations(){regulationsActive=false;regulationsTicket++;$('#regulationsPanel').hidden=true;$('#readerRegulationsTab').classList.remove('active');$('#readerRegulationsTab').setAttribute('aria-pressed','false');document.body.classList.remove('regulations-open')}
$('#readerRegulationsTab').onclick=showRegulations;
async function showRegulations(){if($('#readerRegulationsTab').disabled)return;scheduleExit();regulationsActive=true;document.body.classList.add('regulations-open');$('#archiveContent').hidden=true;$('#regulationsPanel').hidden=false;$('#readerArchiveTab').classList.remove('active');$('#readerArchiveTab').setAttribute('aria-pressed','false');$('#readerRegulationsTab').classList.add('active');$('#readerRegulationsTab').setAttribute('aria-pressed','true');renderRegulations();await loadRegulations()}
function renderRegulations(){
 $('#regulationsPanel').innerHTML=`<div class="schedule-heading"><div><h1>법령·규정 검색</h1><p class="hint">원문 전체를 검색하고 열람합니다.</p></div>${user.role==='admin'?'<button type="button" id="regulationsEdit" class="primary">+ 규정 등록/관리</button>':''}</div><div class="regulations-global-search"><label for="regulationsSearch">통합 원문 검색</label><div class="regulations-search-box"><span aria-hidden="true">🔍</span><input id="regulationsSearch" type="search" maxlength="200" placeholder="조항명, 키워드, 본문 내용 검색 (예: 근로시간, 연장근로, 휴일)" value="${esc(regulationsSearch)}"></div></div><div id="regulationsTags" class="regulations-tags" aria-label="규정 필터"></div><div id="regulationsResults" aria-live="polite"></div>`;
 let timer;$('#regulationsSearch').oninput=e=>{regulationsSearch=e.target.value;clearTimeout(timer);timer=setTimeout(renderRegulationResults,120)};$('#regulationsEdit')?.addEventListener('click',openRegulationsEditor);
}
async function loadRegulations(){const ticket=++regulationsTicket;try{const data=await api('regulations/fulltexts');if(!regulationsActive||ticket!==regulationsTicket)return;regulationsDocs=data.documents;renderRegulationResults()}catch(e){if(regulationsActive&&ticket===regulationsTicket)$('#regulationsResults').innerHTML=`<p role="alert">조회하지 못했습니다: ${esc(e.message)}</p>`}}
// Identify a leading contents list only when an empty heading repeats with real body text.
function regTocRange(lines){
 const marker=lines.findIndex((x,i)=>i<200&&/^\s*목\s*차\s*$/.test(x));
 const keyFor=line=>{const m=line.match(/^\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*[([【][^\)\]】]*[)\]】]\s*$/);return m?m[1]+':'+(m[2]||''):null};
 const first=new Map();
 for(let i=Math.max(0,marker+1);i<lines.length;i++){
  const key=keyFor(lines[i]);if(!key)continue;
  let next=i+1;while(next<lines.length&&!lines[next].trim())next++;
  const hasBody=next<lines.length&&!regHeading(lines[next])&&!/^\s*(?:부\s*칙|목\s*차)\b/.test(lines[next]);
  if(!first.has(key)){if(!hasBody)first.set(key,i);continue}
  if(hasBody){const firstIndex=first.get(key);let start=marker>=0?marker:firstIndex;
   if(marker<0){while(start>0&&(!lines[start-1].trim()||regHeading(lines[start-1])))start--}
   let end=i;while(end>firstIndex+1&&(!lines[end-1].trim()||regHeading(lines[end-1])==='chapter'))end--;
   return {start,end};}
 }
 return null;
}
function regSnippet(line,index,length){
 const start=Math.max(0,index-60),end=Math.min(line.length,index+length+60);
 return (start?'…':'')+line.slice(start,end)+(end<line.length?'…':'');
}
function regFind(docs,q){
 const results=[];if(!q)return results;
 for(const doc of docs){
  const lines=regLines(doc.body),toc=regTocRange(lines);let group=null,heading='원문';
  lines.forEach((line,i)=>{
   if(toc&&i>=toc.start&&i<toc.end)return;
   const kind=regHeading(line);
   if(kind==='article'){heading=line.trim();group=null}
   else if(kind==='chapter'){heading=line.trim();group=null}
   const regex=regRegex(q);let match;
   while((match=regex.exec(line))){
    if(!group){group={category:doc.category,line:i,heading,snippet:regSnippet(line,match.index,match[0].length),count:0};results.push(group)}
    group.count++;
   }
  });
 }
 return results;
}
let regCompare=false,regCompareCategory='',regFontSize=14;
function renderRegulationResults(){
 const q=regulationsSearch.trim();regulationsMatches=regFind(regulationsDocs,q);const counts=Object.fromEntries(regulationsCategories.map(([k])=>[k,q?regulationsMatches.filter(x=>x.category===k).length:regulationsDocs.filter(x=>x.category===k).length]));
 $('#regulationsTags').innerHTML=[['','전체'],...regulationsCategories].map(([k,label])=>`<button type="button" data-regulation-filter="${k}" aria-pressed="${k===regulationsFilter}">${esc(label)} (${k?counts[k]:Object.values(counts).reduce((a,b)=>a+b,0)})</button>`).join('');
 $('#regulationsTags').querySelectorAll('[data-regulation-filter]').forEach(b=>b.onclick=()=>{regulationsFilter=b.dataset.regulationFilter;renderRegulationResults()});
 const panel=$('#regulationsResults');
 if(!q){let doc=regulationsDocs.find(d=>d.category===regulationsFilter);if(!regulationsFilter){panel.innerHTML='<p class="hint">카테고리를 선택하면 규정 전문을 볼 수 있습니다.</p>';return}if(!doc){panel.innerHTML='<p class="regulations-empty">등록된 원문이 없습니다.</p>';return}panel.innerHTML='<div id="regulationsViewer"></div>';renderRegViewer($('#regulationsViewer'),doc,'');return}
 const visible=regulationsMatches.map((m,i)=>({m,i})).filter(x=>!regulationsFilter||x.m.category===regulationsFilter);
 panel.innerHTML=`<p class="regulations-result-count">검색 결과 ${visible.length}건</p><div class="regulations-split"><div class="regulations-result-list">${visible.map(({m,i})=>`<button class="regulations-hit" type="button" data-hit="${i}"><span class="regulation-badge">${esc(regLabel(m.category))}</span><strong>${esc(m.heading)} <small class="reg-match-count">${m.count}건</small></strong><pre>${regHighlight(m.snippet,q)}</pre></button>`).join('')||'<p class="regulations-empty">검색 결과가 없습니다.</p>'}</div><div id="regulationsViewer"><p class="hint">검색 결과를 선택하면 원문 위치로 이동합니다.</p></div></div>`;
 panel.querySelectorAll('[data-hit]').forEach(button=>button.onclick=()=>{const hit=regulationsMatches[Number(button.dataset.hit)],doc=regulationsDocs.find(d=>d.category===hit.category);if(doc)renderRegViewer($('#regulationsViewer'),doc,q,hit.line)})
}
function regCopyText(lines,index){
 let start=index;while(start>0&&regHeading(lines[start])!=='article'&&!regHeading(lines[start]))start--;
 if(regHeading(lines[start])!=='article')return lines[index];
 let end=start+1;while(end<lines.length&&!regHeading(lines[end]))end++;
 return lines.slice(start,end).join('\n');
}
function renderRegViewer(container,doc,q,lineNumber){
 const alternatives=regulationsDocs.filter(d=>d.category!==doc.category);
 if(!alternatives.some(d=>d.category===regCompareCategory))regCompareCategory=alternatives[0]?.category||'';
 container.innerHTML=`<div class="regulations-workspace"><div class="regulations-toolbar-v2"><strong>${esc(regLabel(doc.category))}</strong><button type="button" data-font="-1" aria-label="글자 크기 줄이기">가−</button><button type="button" data-font="1" aria-label="글자 크기 키우기">가+</button><button type="button" data-compare aria-pressed="${regCompare}">${regCompare?'비교 닫기':'+ 규정 나란히 비교'}</button></div><div class="regulations-compare ${regCompare?'is-comparing':''}"><div class="reg-pane" data-pane="primary"></div>${regCompare?`<div class="reg-pane" data-pane="secondary"><label class="reg-compare-label">비교 규정<select data-compare-select><option value="">규정 선택</option>${alternatives.map(d=>`<option value="${esc(d.category)}" ${d.category===regCompareCategory?'selected':''}>${esc(regLabel(d.category))}</option>`).join('')}</select></label><div class="reg-secondary-content"></div></div>`:''}</div></div>`;
 container.querySelectorAll('[data-font]').forEach(button=>button.onclick=()=>{regFontSize=Math.min(24,Math.max(11,regFontSize+Number(button.dataset.font)));container.querySelectorAll('.regulations-document').forEach(el=>el.style.fontSize=regFontSize+'px')});
 container.querySelector('[data-compare]').onclick=()=>{const primary=container.querySelector('[data-pane=primary]'),selected=primary.querySelector('.reg-selected'),scroll=primary.querySelector('.regulations-document').scrollTop;const selectedLine=selected?Number(selected.dataset.sourceLine):undefined;regCompare=!regCompare;renderRegViewer(container,doc,q,selectedLine);if(selectedLine===undefined)container.querySelector('[data-pane=primary] .regulations-document').scrollTop=scroll};
 mountRegPane(container.querySelector('[data-pane="primary"]'),doc,q,lineNumber,'primary');
 if(regCompare){const select=container.querySelector('[data-compare-select]'),target=container.querySelector('.reg-secondary-content');const renderOther=()=>{regCompareCategory=select.value;const other=alternatives.find(d=>d.category===regCompareCategory);if(other)mountRegPane(target,other,'',undefined,'secondary');else target.innerHTML='<p class="hint">비교할 규정을 선택하세요.</p>'};select.onchange=renderOther;renderOther()}
}
function mountRegPane(container,doc,q,lineNumber,prefix){
 const lines=regLines(doc.body),range=regTocRange(lines),showToc=Number.isInteger(lineNumber)&&range&&lineNumber>=range.start&&lineNumber<range.end;
 const visible=(i)=>!range||showToc||i<range.start||i>=range.end;
 const headings=lines.map((line,i)=>({i,entry:regTocEntry(line,doc.category)})).filter(x=>x.entry&&visible(x.i));
 container.innerHTML=`<div class="reg-pane-tools"><label>문서 내 검색<input type="search" data-local-search value="${esc(q)}" placeholder="이 문서에서 검색"></label><button type="button" data-local-next>다음 찾기</button><span data-local-status role="status"></span><button type="button" data-copy>현재 조항 복사</button></div><div class="regulations-viewer"><aside class="regulations-toc" aria-label="원문 목차"><strong>${esc(regLabel(doc.category))}</strong>${headings.map(x=>`<button type="button" data-line="${x.i}" class="toc-${x.entry.type} toc-level-${x.entry.level}">${esc(x.entry.label)}</button>`).join('')||'<p class="hint">인식된 제목이 없습니다.</p>'}</aside><div class="regulations-document" tabindex="0" aria-label="규정 전문">${lines.map((line,i)=>visible(i)?`<div id="${prefix}-line-${i}" data-source-line="${i}" class="reg-line ${regHeading(line)}">${regHighlight(line,q)||'&#8203;'}</div>`:'').join('')}</div></div>`;
 const documentEl=container.querySelector('.regulations-document'),local=container.querySelector('[data-local-search]'),status=container.querySelector('[data-local-status]');let selected=Number.isInteger(lineNumber)?lineNumber:0,localIndex=-1;documentEl.style.fontSize=regFontSize+'px';
 function go(i){const target=container.querySelector('[data-source-line="'+i+'"]');if(!target)return;selected=i;container.querySelectorAll('.reg-selected').forEach(x=>x.classList.remove('reg-selected'));target.classList.add('reg-selected');target.scrollIntoView({behavior:'smooth',block:'center',inline:'nearest'})}
 container.querySelectorAll('[data-line]').forEach(b=>b.onclick=()=>go(Number(b.dataset.line)));
 documentEl.onclick=e=>{const el=e.target.closest('[data-source-line]');if(el)go(Number(el.dataset.sourceLine))};
 local.oninput=()=>{localIndex=-1;const query=local.value.trim();documentEl.querySelectorAll('[data-source-line]').forEach(el=>{const i=Number(el.dataset.sourceLine);el.innerHTML=regHighlight(lines[i],query)||'&#8203;'});status.textContent=''};
 container.querySelector('[data-local-next]').onclick=()=>{const query=local.value.trim();if(!query){status.textContent='검색어를 입력하세요.';return}const found=[];lines.forEach((line,i)=>{if(visible(i)&&regRegex(query).test(line))found.push(i)});if(!found.length){status.textContent='일치하는 내용이 없습니다.';return}localIndex=(localIndex+1)%found.length;status.textContent=(localIndex+1)+' / '+found.length;go(found[localIndex])};
 container.querySelector('[data-copy]').onclick=async()=>{try{await navigator.clipboard.writeText(regCopyText(lines,selected));status.textContent='복사했습니다.'}catch{status.textContent='복사할 수 없습니다. 본문을 선택해 복사해 주세요.'}};
 if(Number.isInteger(lineNumber))requestAnimationFrame(()=>go(lineNumber));
}
async function openRegulationsEditor(){
 let dialog=$('#regulationsDialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='regulationsDialog';document.body.append(dialog)}
 dialog.innerHTML=`<div class="modalhead"><h2>규정 등록/관리</h2><button type="button" id="regulationsClose">닫기</button></div><form id="regulationsForm"><label>카테고리<select name="category" required><option value="">카테고리를 선택하세요</option>${regulationsCategories.map(([k,v])=>`<option value="${k}">${esc(v)}</option>`).join('')}</select></label><button type="button" id="regulationsDelete" hidden>선택한 규정 전체 삭제</button><label>파일 불러오기 (.docx, .txt)<input type="file" id="regulationsFile" accept=".txt,.docx"></label><label>원문 전체<textarea name="body" rows="18" maxlength="2000000" required placeholder="원문을 그대로 붙여넣으세요."></textarea></label><p class="hint">저장하면 선택한 카테고리의 기존 원문이 교체됩니다. HWP/DOC는 텍스트를 복사해 붙여넣으세요.</p><button class="primary" id="regulationsSave">원문 저장</button><p id="regulationsError" role="status"></p></form>`;
 const form=$('#regulationsForm'),category=form.elements.category,body=form.elements.body,status=$('#regulationsError'),save=$('#regulationsSave'),del=$('#regulationsDelete');let token='',ticket=0,original='',initial='';
 $('#regulationsClose').onclick=()=>dialog.close();
 category.onchange=async()=>{const choice=category.value,t=++ticket;token='';original='';initial='';body.value='';body.disabled=true;save.disabled=true;del.hidden=true;if(!choice)return;try{const data=await api('regulations/document?'+new URLSearchParams({category:choice}));if(t!==ticket||!dialog.open)return;token=data.document?.token||'';original=data.document?.body||'';body.value=original;initial=body.value;del.hidden=!data.document;body.disabled=false;save.disabled=false;status.textContent=data.document?'기존 원문을 불러왔습니다.':'원문을 입력하세요.'}catch(e){if(t===ticket)status.textContent=e.message}};
 $('#regulationsFile').onchange=async e=>{const file=e.target.files[0];if(!file||!category.value){status.textContent='먼저 카테고리를 선택하세요.';e.target.value='';return}const t=++ticket,choice=category.value,data=new FormData();data.append('file',file);body.disabled=true;save.disabled=true;try{const result=await api('regulations/extract',data,true);if(t===ticket&&choice===category.value&&dialog.open){body.value=result.text;status.textContent='파일에서 텍스트를 불러왔습니다. 저장 전 확인해 주세요.'}}catch(err){if(t===ticket)status.textContent=err.message}finally{if(t===ticket){body.disabled=false;save.disabled=false}}};
 del.onclick=async()=>{const choice=category.value;if(!token||!confirm(`‘${regLabel(choice)}’의 원문 전체를 삭제할까요? 복구하려면 백업이 필요합니다.`))return;del.disabled=true;category.disabled=true;save.disabled=true;try{await api('regulations/delete',{category:choice,token});token='';body.value='';del.hidden=true;status.textContent='원문을 삭제했습니다.';await loadRegulations()}catch(e){status.textContent=e.message}finally{del.disabled=false;category.disabled=false;save.disabled=false}};
 form.onsubmit=async e=>{e.preventDefault();if(!category.value||!body.value.trim())return;save.disabled=true;category.disabled=true;try{await api('regulations/save',{category:category.value,body:body.value===initial?original:body.value,token});dialog.close();await loadRegulations();toast('원문을 저장했습니다.')}catch(err){status.textContent=err.message}finally{save.disabled=false;category.disabled=false}};
 body.disabled=true;save.disabled=true;dialog.showModal();
}
