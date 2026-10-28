'use strict';
let financialActive=false,financialTicket=0,financialTimer=null,financialData=null,financialRenderKey='';
const financialYear=new Date().getFullYear();
const financialFilter={company:'hyundai-steel',fs:'CFS',start:financialYear-5,end:financialYear,mode:'quarterly',quarter:0};
function closeFinancials(){financialActive=false;financialTicket++;clearTimeout(financialTimer);$('#financialPanel').hidden=true;document.body.classList.remove('financials-open');$('#financialNav').classList.remove('active');$('#readerFinancialTab').classList.remove('active');$('#readerFinancialTab').setAttribute('aria-pressed','false')}
$('#financialNav').onclick=showFinancials;$('#readerFinancialTab').onclick=showFinancials;
async function showFinancials(){scheduleExit();financialActive=true;$('#archiveContent').hidden=true;$('#financialPanel').hidden=false;document.body.classList.add('financials-open');$('#allNav').classList.remove('active');$('#readerArchiveTab').classList.remove('active');$('#readerArchiveTab').setAttribute('aria-pressed','false');$('#financialNav').classList.add('active');$('#readerFinancialTab').classList.add('active');$('#readerFinancialTab').setAttribute('aria-pressed','true');financialRenderKey='';$('#financialPanel').innerHTML='<p role="status">실적을 불러오는 중…</p>';await loadFinancials()}
async function loadFinancials(background=false){
 clearTimeout(financialTimer);
 const ticket=++financialTicket;
 try{
  const data=await api('financials?'+new URLSearchParams(financialFilter));
  if(!financialActive||ticket!==financialTicket)return;
  financialData=data;
  const key=JSON.stringify({...data,job:{running:data.job.running,error:data.job.error,company:data.job.company}});
  const editing=$('#financialFilters')?.contains(document.activeElement);
  if(!background||(!editing&&key!==financialRenderKey)){renderFinancials();financialRenderKey=key}
  else if($('#financialStatus'))$('#financialStatus').textContent=financialJobText(data.job);
  if(data.job.running||editing&&key!==financialRenderKey)financialTimer=setTimeout(()=>loadFinancials(true),2500);
 }catch(e){if(financialActive&&ticket===financialTicket){$('#financialPanel').innerHTML='<p role="alert">'+esc(e.message)+'</p><button id="financialRetry">다시 시도</button>';$('#financialRetry').onclick=()=>loadFinancials()}}
}
function financialJobText(job){return job.running?'수집 중 '+job.done+'/'+(job.total||'…')+'건 · 다른 탭을 열어도 서버에서 계속합니다.':job.error||''}

function financialMoney(value){
 if(value===null||value===undefined)return '—';
 const eok=Math.trunc(Math.abs(value)/100000000),jo=Math.floor(eok/10000),rest=eok%10000,sign=value<0&&eok?'-':'';
 return sign+(jo?jo.toLocaleString('ko-KR')+'조'+(rest?' '+rest.toLocaleString('ko-KR')+'억':''):rest.toLocaleString('ko-KR')+'억');
}
function financialPercent(value){return value===null||value===undefined?'—':value.toLocaleString('ko-KR',{maximumFractionDigits:1,minimumFractionDigits:1})+'%'}
function financialMargin(row,metric){const revenue=row.values.revenue,value=row.values[metric];return value===null||value===undefined||revenue===null||revenue===undefined||revenue===0?null:value/revenue*100}
function renderFinancialMatrix(rows,mode){
 const latest=rows.find(r=>Object.values(r.values).some(v=>v!==null))||rows[0];
 const metrics=[['매출액',r=>r.values.revenue],['영업이익',r=>r.values.operating,r=>financialMargin(r,'operating')],['당기순이익',r=>r.values.net,r=>financialMargin(r,'net')],['법인세차감전이익',r=>r.values.pretax,r=>financialMargin(r,'pretax')]];
 const active=r=>r===latest?'financial-current':'';
 return `<div class="financial-table-wrap"><table class="financial-table financial-matrix"><thead><tr><th scope="col">손익계산서</th>${rows.map(r=>`<th scope="col" data-financial-period="${r.year}-${r.quarter}" class="${active(r)}">${r.year}${mode==='annual'?'.12':' Q'+r.quarter}${r.derived?' *':''}</th>`).join('')}</tr></thead><tbody>${metrics.map(([label,get,margin])=>`<tr><th scope="row">${label}</th>${rows.map(r=>{const value=get(r);return `<td data-financial-period="${r.year}-${r.quarter}" class="${active(r)} ${value<0?'financial-negative':''}"><span>${financialMoney(value)}</span>${margin?`<small class="financial-profit-margin" title="매출액 대비 이익률">${financialPercent(margin(r))}</small>`:''}</td>`}).join('')}</tr>`).join('')}<tr class="financial-source-row"><th scope="row">자료 상태</th>${rows.map(r=>{const missing=Object.values(r.values).some(v=>v===null);const status={available:missing?'일부 값 미확인':'조회 완료',no_data:'공시 없음·API 미제공',not_collected:'미수집·미도래'}[r.status]||'미확인';return `<td data-financial-period="${r.year}-${r.quarter}" class="${active(r)}" title="${esc(r.warnings.join(' / '))}">${status}</td>`}).join('')}</tr><tr class="financial-source-row"><th scope="row">공시 원문</th>${rows.map(r=>`<td data-financial-period="${r.year}-${r.quarter}" class="${active(r)}">${r.receipts.map((id,i)=>`<a href="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=${encodeURIComponent(id)}" target="_blank" rel="noopener noreferrer">공시${r.receipts.length>1?i+1:''} ↗</a>`).join(' · ')||'—'}</td>`).join('')}</tr></tbody></table></div>`;
}
function financialPeriod(row,mode){return mode==='annual'?String(row.year):String(row.year).slice(2)+' Q'+row.quarter}
function renderFinancialCharts(rows,mode,info=''){
 const points=[...rows].sort((a,b)=>a.year-b.year||a.quarter-b.quarter);
 const controls=`<div class="financial-mode-tabs" role="group" aria-label="차트 조회 기간">${[['quarterly','분기별(QoQ)'],['annual','연간(YoY)']].map(([id,label])=>`<button type="button" data-financial-mode="${id}" class="${mode===id?'active':''}" aria-pressed="${mode===id}">${label}</button>`).join('')}<details class="financial-extra-mode"><summary>기타</summary><button type="button" data-financial-mode="cumulative" class="${mode==='cumulative'?'active':''}">분기 누적</button></details></div>`;
 function chart(title,series,rateLabel,rateValue){
  const amounts=points.flatMap(r=>series.map(s=>r.values[s.key])).filter(Number.isFinite), rates=points.map(rateValue).filter(Number.isFinite);
  if(!amounts.length&&!rates.length)return `<div class="financial-chart"><h4>${title}</h4><div class="financial-chart-empty">저장된 실적이 없습니다.</div></div>`;
  const ap=Math.max(0,...amounts),an=Math.abs(Math.min(0,...amounts)),rp=Math.max(0,...rates),rn=Math.abs(Math.min(0,...rates));
  const negative=an||rn?Math.min(.8,Math.max(.12,an/(ap+an||1),rn/(rp+rn||1))):0;
  const span=(pos,neg)=>Math.max(pos/(1-negative),negative?neg/negative:0,1)*1.1;
  const amountSpan=span(ap,an),rateSpan=span(rp,rn),amountMin=-amountSpan*negative,rateMin=-rateSpan*negative;
  const unit=Math.max(ap,an)>=1e12?1e12:Math.max(ap,an)>=1e8?1e8:Math.max(ap,an)>=1e4?1e4:1,unitName=unit===1e12?'조원':unit===1e8?'억원':unit===1e4?'만원':'원';
  const left=60,right=530,top=28,bottom=190,width=right-left,height=bottom-top,ya=v=>bottom-(v-amountMin)/amountSpan*height,yr=v=>bottom-(v-rateMin)/rateSpan*height,zero=ya(0),x=i=>left+(i+.5)*width/points.length;
  let svg=`<svg viewBox="0 0 600 230" role="img" aria-label="${title}"><title>${title}</title><desc>왼쪽 축은 금액, 오른쪽 축은 비율입니다. 기간은 과거에서 최신 순입니다. 누락된 비율은 연결하지 않습니다.</desc><text x="${left}" y="14" fill="#96aec3" font-size="11">금액 (${unitName})</text><text x="${right}" y="14" text-anchor="end" fill="#edc879" font-size="11">${rateLabel} (%)</text>`;
  for(let i=0;i<=4;i++){
   const y=bottom-i/4*height,av=(amountMin+amountSpan*i/4)/unit,rv=rateMin+rateSpan*i/4;
   svg+=`<line x1="${left}" x2="${right}" y1="${y}" y2="${y}" stroke="#2c4053"/><text x="${left-6}" y="${y+4}" text-anchor="end" fill="#93abc0" font-size="10">${esc(av.toLocaleString('ko-KR',{maximumFractionDigits:1}).replace(/^-0$/,'0'))}</text><text x="${right+6}" y="${y+4}" fill="#edc879" font-size="10">${rates.length?esc(rv.toLocaleString('ko-KR',{maximumFractionDigits:1}).replace(/^-0$/,'0'))+'%':'—'}</text>`;
  }
  svg+=`<line x1="${left}" x2="${right}" y1="${zero}" y2="${zero}" stroke="#809cb1" stroke-width="1.2"/>`;
  let path='',circles='';const step=Math.max(1,Math.ceil(points.length/7)),bar=Math.max(.8,Math.min(22,width/points.length*.7/series.length));
  points.forEach((r,i)=>{
   const px=x(i),period=financialPeriod(r,mode),key=r.year+'-'+r.quarter;
   svg+=`<rect class="financial-period-highlight" data-chart-period="${key}" x="${left+i*width/points.length}" y="${top}" width="${width/points.length}" height="${height}"/>`;
   if(i%step===0||i===points.length-1)svg+=`<text x="${px}" y="215" text-anchor="middle" fill="#98aec1" font-size="10">${esc(period)}</text>`;
   series.forEach((s,j)=>{const value=r.values[s.key];if(!Number.isFinite(value))return;const bx=px+(j-series.length/2)*bar,y=ya(value),label=esc(period+' '+s.label+' '+financialMoney(value));
    if(value===0)svg+=`<line x1="${bx}" x2="${bx+bar}" y1="${zero}" y2="${zero}" stroke="${s.color}" stroke-width="2"><title>${label}</title></line>`;
    else svg+=`<rect x="${bx}" y="${Math.min(y,zero)}" width="${bar}" height="${Math.abs(zero-y)}" rx="1" fill="${s.color}" opacity=".85"><title>${label}</title></rect>`;
   });
   const rate=rateValue(r);if(!Number.isFinite(rate))return;const py=yr(rate);path+=(i===0||!Number.isFinite(rateValue(points[i-1]))?' M':' L')+px+' '+py;circles+=`<circle cx="${px}" cy="${py}" r="3.2" fill="#f1c466"><title>${esc(period+' '+rateLabel+' '+financialPercent(rate))}</title></circle>`;
  });
  svg+=(path?`<path d="${path}" fill="none" stroke="#f1c466" stroke-width="2.2"/>`:'')+circles+'</svg>';
  return `<div class="financial-chart"><h4>${title}</h4><div class="financial-chart-legend">${series.map(s=>`<span class="legend-${s.key}">${s.label}</span>`).join('')}<span class="legend-margin">${rateLabel}</span></div>${svg}</div>`;
 }
 const latest=[...points].reverse().find(r=>['revenue','operating','net'].some(k=>Number.isFinite(r.values[k])));
 const summary=latest?`<div class="financial-chart financial-summary"><h4>최신 실적 요약</h4><p class="financial-summary-period">${latest.year}${mode==='annual'?'년':' Q'+latest.quarter}${mode==='cumulative'?' 누적':''}${latest.derived?' *':''}</p>${[['revenue','매출액'],['operating','영업이익'],['net','당기순이익']].map(([key,label])=>`<div class="financial-summary-item"><span>${label}</span><strong class="${latest.values[key]<0?'financial-negative':''}">${financialMoney(latest.values[key])}</strong><small>${mode==='quarterly'?'QoQ '+financialPercent(latest[key+'_qoq'])+' · ':''}YoY ${financialPercent(latest[key+'_yoy'])}</small></div>`).join('')}<p class="financial-summary-note">${mode==='quarterly'?'QoQ 전 분기 · ':''}YoY 전년 동기 대비 · — 비교 불가</p></div>`:`<div class="financial-chart financial-summary"><h4>최신 실적 요약</h4><div class="financial-chart-empty">저장된 실적이 없습니다.</div></div>`;
 const main=chart('매출액·영업이익 추이',[{key:'revenue',label:'매출액',color:'#50d6b4'},{key:'operating',label:'영업이익',color:'#6aaeff'}],'영업이익률',r=>financialMargin(r,'operating'));
 function profitability(){
  const lines=[{key:'operating',label:'영업이익률',color:'#f1c466'},{key:'net',label:'순이익률',color:'#c493ed'}],rates=points.flatMap(r=>lines.map(l=>financialMargin(r,l.key))).filter(Number.isFinite);
  if(!rates.length)return '<div class="financial-chart financial-profitability"><h4>수익성 비교</h4><div class="financial-chart-empty">비교할 이익률이 없습니다.</div></div>';
  const min=Math.min(0,...rates),max=Math.max(0,...rates),padding=Math.max((max-min)*.1,1),lo=min-padding,hi=max+padding,left=54,right=530,top=28,bottom=190,width=right-left,height=bottom-top,x=i=>left+(i+.5)*width/points.length,y=v=>bottom-(v-lo)/(hi-lo)*height;
  let svg='<svg viewBox="0 0 600 230" role="img" aria-label="영업이익률과 순이익률 비교"><title>수익성 비교</title><desc>매출액 대비 이익률입니다. 기간은 과거에서 최신 순이며 누락된 값은 연결하지 않습니다.</desc><text x="54" y="14" fill="#96aec3" font-size="11">이익률 (%)</text>';
  for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4,py=y(v);svg+=`<line x1="${left}" x2="${right}" y1="${py}" y2="${py}" stroke="#2c4053"/><text x="${left-6}" y="${py+4}" text-anchor="end" fill="#93abc0" font-size="10">${esc(v.toLocaleString('ko-KR',{maximumFractionDigits:1}))}%</text>`}
  const step=Math.max(1,Math.ceil(points.length/5));points.forEach((r,i)=>{svg+=`<rect class="financial-period-highlight" data-chart-period="${r.year}-${r.quarter}" x="${left+i*width/points.length}" y="${top}" width="${width/points.length}" height="${height}"/>`;if(i%step===0||i===points.length-1)svg+=`<text x="${x(i)}" y="215" text-anchor="middle" fill="#98aec1" font-size="10">${esc(financialPeriod(r,mode))}</text>`});
  lines.forEach(l=>{let path='',dots='';points.forEach((r,i)=>{const v=financialMargin(r,l.key);if(!Number.isFinite(v))return;path+=(i===0||!Number.isFinite(financialMargin(points[i-1],l.key))?' M':' L')+x(i)+' '+y(v);dots+=`<circle cx="${x(i)}" cy="${y(v)}" r="3" fill="${l.color}"><title>${esc(financialPeriod(r,mode)+' '+l.label+' '+financialPercent(v))}</title></circle>`});svg+=`<path d="${path}" fill="none" stroke="${l.color}" stroke-width="2"/>${dots}`});
  return `<div class="financial-chart financial-profitability"><h4>수익성 비교</h4><div class="financial-chart-legend"><span class="legend-margin">영업이익률</span><span class="legend-net-rate">순이익률</span></div>${svg}</svg></div>`;
 }
 return `<section class="financial-charts financial-combo"><div class="financial-charts-heading"><div class="financial-chart-heading-left"><h3>실적 추이</h3>${controls}</div>${info}</div><p class="financial-period-note">차트: 과거 → 최신 · 표: 최신 → 과거</p><div class="financial-chart-grid">${summary}${main}${profitability()}</div></section>`;
}

function readFinancialSelection(){const values=Object.fromEntries(new FormData($('#financialFilters')));values.start=Number(values.start);values.end=Number(values.end);values.quarter=Number(values.quarter||0);if(!Number.isInteger(values.start)||!Number.isInteger(values.end)||values.start<2015||values.end>financialYear||values.start>values.end||values.end-values.start>5){toast('시작·종료연도를 확인하세요. 한 번에 최대 6개년입니다.');return false}Object.assign(financialFilter,values);return true}
function renderFinancials(){const data=financialData,f=financialFilter,admin=user.role==='admin',job=data.job;
 const info=`<div class="financial-chart-info"><p>금액: 조·억 원 (억원 미만 버림) · 원자료는 원(KRW)으로 보관 · 한 번에 최대 6개년 · ${data.resolved?esc(data.resolved.corp_name)+' (DART '+esc(data.resolved.corp_code)+')':'DART 수집 후 회사 고유번호를 확인합니다.'}</p><p id="financialStatus" role="status">${esc(financialJobText(job))}</p></div>`;
 $('#financialPanel').innerHTML=`<div class="schedule-heading"><h1>기업실적 조회</h1><div class="actions"><button id="financialRefresh">저장 자료 새로고침</button>${admin?'<button id="financialSettings">DART 설정</button><button class="primary" id="financialFetch" '+(job.running?'disabled':'')+'>연결·별도 함께 가져오기</button>':''}</div></div><form id="financialFilters" class="financial-filters"><label>회사<select name="company">${data.companies.map(c=>`<option value="${esc(c.id)}" ${c.id===f.company?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label><label>재무제표 기준<select name="fs"><option value="CFS" ${f.fs==='CFS'?'selected':''}>연결</option><option value="OFS" ${f.fs==='OFS'?'selected':''}>별도</option></select></label><label>시작연도<input name="start" type="number" min="2015" max="${financialYear}" value="${f.start}" required></label><label>종료연도<input name="end" type="number" min="2015" max="${financialYear}" value="${f.end}" required></label><label>표시 분기<select name="quarter" ${f.mode==='annual'?'disabled':''}>${[0,1,2,3,4].map(q=>`<option value="${q}" ${q===Number(f.quarter)?'selected':''}>${q?q+'분기':'전체'}</option>`).join('')}</select></label><button>조회</button></form><div class="financial-company-heading"><div><h2>${esc(data.companies.find(c=>c.id===f.company)?.name||'기업실적')}</h2><span>${f.fs==='CFS'?'연결':'별도'} 손익계산서 · ${f.start}~${f.end}</span></div><span class="financial-unit">단위: 조·억 원</span></div>${renderFinancialCharts(data.rows,f.mode,info)}${renderFinancialMatrix(data.rows,f.mode)}<details class="financial-method"><summary>조회 기준·출처</summary><p class="hint">* 4분기 단독 실적 = 연간 − 3분기 누적. 두 공시 중 값이 없으면 계산하지 않습니다. 분기 누적 모드의 4분기는 연간입니다.</p><p class="hint">연결·별도는 자동으로 대체하지 않습니다. 비상장사의 분기 자료나 분할 전 법인의 실적은 제공되지 않을 수 있습니다. 포스코는 철강 사업회사, 동국제강은 현재 사업회사 기준이며 지주회사와 합치지 않습니다. 정정공시로 비교기간 수치가 바뀌면 공시 원문을 함께 확인하세요.</p><p>DART 정기보고서 전체 재무제표의 손익계산서(IS/CIS)에서 표준 계정 ID를 우선하고, 없으면 일치하는 계정명을 사용합니다. 계정이 중복되거나 통화가 확인되지 않으면 빈 값으로 남깁니다. 원자료의 당기순이익은 전체 순이익이며 지배주주 순이익으로 대체하지 않습니다.</p><a href="https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020" target="_blank" rel="noopener noreferrer">금융감독원 Open DART 개발가이드 ↗</a></details>`;
 const panel=$('#financialPanel');
 const highlight=target=>{const cell=target.closest?.('.financial-matrix [data-financial-period]');const period=cell?.dataset.financialPeriod;panel.querySelectorAll('[data-chart-period]').forEach(el=>el.classList.toggle('is-highlighted',!!period&&el.dataset.chartPeriod===period))};
 panel.onmouseover=e=>highlight(e.target);panel.onmouseout=e=>{if(!e.relatedTarget||!e.relatedTarget.closest?.('.financial-matrix [data-financial-period]'))highlight(panel)};
 $$('[data-financial-mode]').forEach(button=>button.onclick=()=>{if(!readFinancialSelection())return;f.mode=button.dataset.financialMode;loadFinancials()});
 $('#financialRefresh').onclick=()=>loadFinancials();$('#financialSettings')?.addEventListener('click',openFinancialSettings);
 $('#financialFilters').onsubmit=e=>{e.preventDefault();if(readFinancialSelection())loadFinancials()};
 $('#financialFetch')?.addEventListener('click',async()=>{if(!readFinancialSelection())return;try{await api('financials/fetch',{...f,both_fs:true});if(financialActive)await loadFinancials()}catch(e){toast(e.message)}});
}
async function openFinancialSettings(){try{const cfg=await api('financials/config');let d=$('#financialConfigDialog');if(!d){d=document.createElement('dialog');d.id='financialConfigDialog';document.body.append(d)}d.innerHTML=`<div class="modalhead"><h2>DART 설정</h2><button id="financialConfigClose">닫기</button></div><form id="financialConfigForm"><label>DART 인증키<input name="key" type="password" autocomplete="new-password" maxlength="40" placeholder="${cfg.configured?'저장된 키 유지 · 변경할 때만 입력':'DART 인증키 40자리'}"></label><p class="hint">뉴스 인증키와 별개입니다. 키는 서버 PC에 저장되며 백업에 포함됩니다. 팀원에게는 키를 보내지 않습니다.</p><button class="primary">저장</button><p id="financialConfigError" role="alert"></p></form>`;$('#financialConfigClose').onclick=()=>d.close();$('#financialConfigForm').onsubmit=async e=>{e.preventDefault();try{await api('financials/config',Object.fromEntries(new FormData(e.target)));e.target.reset();d.close();toast('DART 설정을 저장했습니다. 회사를 선택하고 DART에서 가져오기를 누르세요.')}catch(e){$('#financialConfigError').textContent=e.message}};d.addEventListener('close',()=>d.replaceChildren(),{once:true});d.showModal()}catch(e){toast(e.message)}}
