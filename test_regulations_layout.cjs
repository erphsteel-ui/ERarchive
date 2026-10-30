const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 for(const viewer of [true,false]){
  const page=await browser.newPage({viewport:{width:1440,height:900}});await page.setContent('<html><head></head><body class="regulations-open'+(viewer?' viewerrole':'')+'"><main><button id="readerRegulationsTab"></button><section id="regulationsPanel"></section></main></body></html>');
  await page.addStyleTag({content:fs.readFileSync('static/style.css','utf8')});await page.addStyleTag({content:fs.readFileSync('static/theme.css','utf8')});
  await page.evaluate(()=>{window.$=s=>document.querySelector(s);window.esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');window.user={role:'admin'};window.copied='';Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copied=text}}})});
  await page.addScriptTag({content:fs.readFileSync('static/regulations.js','utf8')});
  await page.evaluate(()=>{regulationsDocs=[{category:'agreement',body:'목 차\n제1조(목적)\n제2조(근로시간)\n제1장 총칙\n제1조(목적)\n본문 내용\n제2조(근로시간)\n근로시간 8시간\n추가 내용\n제3조(휴일)\n휴일 내용'},{category:'labor_act',body:'제1장 총칙\n제1조(목적)\n법령 본문'}];regulationsFilter='agreement';regulationsActive=true;renderRegulations();renderRegulationResults()});
  let sizes=await page.evaluate(()=>{const pane=document.querySelector('.regulations-document').getBoundingClientRect(),toc=document.querySelector('.regulations-toc').getBoundingClientRect(),main=document.querySelector('main').getBoundingClientRect();return {doc:pane.width,toc:toc.width,main:main.width,tocPos:getComputedStyle(document.querySelector('.regulations-toc')).position,hidden:!!document.querySelector('#primary-line-1'),actual:!!document.querySelector('#primary-line-4')}});
  assert(sizes.main>1400);assert(sizes.doc>900);assert.equal(sizes.toc,260);assert.equal(sizes.tocPos,'static');assert.equal(sizes.hidden,false);assert.equal(sizes.actual,true);
  await page.locator('.regulations-toc [data-line="6"]').click();await page.locator('[data-copy]').click();assert.match(await page.evaluate(()=>window.copied),/제2조\(근로시간\)\n근로시간 8시간/);
  await page.locator('[data-local-search]').fill('휴일');await page.locator('[data-local-next]').click();assert.equal(await page.locator('.reg-selected').getAttribute('data-source-line'),'9');
  await page.locator('[data-compare]').click();assert.equal(await page.locator('.regulations-document').count(),2);assert.equal(await page.locator('[data-compare-select]').inputValue(),'labor_act');
  await page.evaluate(()=>{regulationsSearch='8시간';renderRegulationResults()});await page.locator('[data-hit="0"]').click();sizes=await page.evaluate(()=>({list:document.querySelector('.regulations-result-list').getBoundingClientRect().width,viewer:document.querySelector('#regulationsViewer').getBoundingClientRect().width}));assert(sizes.list>=360&&sizes.list<=450);assert(sizes.viewer>sizes.list);
  assert(!((await page.locator('.regulations-hit pre').first().textContent()).trim().startsWith('제2조(근로시간)')));
  await page.close();
 }
 console.log('PASS: desktop admin/viewer width, TOC, scrolling, copying, search and comparison');
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
