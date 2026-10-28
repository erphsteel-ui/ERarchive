const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(__dirname+'/static/news.js','utf8');
const items=[{id:'x',category:'안전',published:'2026-10-28T00:00:00Z',publisher:'example.com',title:'<script>안전</script>',description:'설명',url:'https://example.com/a',important:0,excluded:0,related_articles:[{id:'r',title:'관련 기사',url:'https://example.com/r',publisher:'other.com'}]},{id:'y',category:'노사관계',published:'2026-10-28T00:00:00Z',publisher:'example.com',title:'교섭',description:'설명',url:'https://example.com/b',important:0,excluded:0,related_articles:[]}];
const context=vm.createContext({newsItems:items,esc:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))});
vm.runInContext(code.slice(code.indexOf('function renderNewsArticle(')),context);
let html=vm.runInContext('renderNewsSections(false)',context);assert.equal((html.match(/<article /g)||[]).length,2);assert(!html.includes('<script>'));assert(html.includes('&lt;script&gt;'));assert(!html.includes('data-news-id'));assert(html.includes('이슈 기사 2건 · 경과 펼치기'));
context.newsItems=[items[0]];html=vm.runInContext('renderNewsSections(true)',context);assert(html.includes('data-news-id="x"'));assert(!html.includes('data-news-id="y"'));assert(html.includes('(묶음)'));
const template=fs.readFileSync(__dirname+'/templates/index.html','utf8'),tabs=template.slice(template.indexOf('id="readerTabs"'),template.indexOf('<section id="memoPanel"'));
assert(tabs.indexOf('readerScheduleTab')<tabs.indexOf('readerNewsTab'));assert(tabs.indexOf('readerNewsTab')<tabs.indexOf('readerArchiveTab'));assert(tabs.indexOf('readerArchiveTab')<tabs.indexOf('readerMemoTab'));
assert(template.includes('<title>ER 아카이브</title>'));console.log('PASS: news rows, related links, escaped content, admin group controls and reader tab order');
context.newsHeadlines=Array.from({length:4},(_,i)=>({...items[0],id:'headline'+i,title:i===0?'<script>headline</script>':'headline'+i,article_count:2,important:i===0}));
html=vm.runInContext('renderNewsHeadlines()',context);assert.equal((html.match(/<article /g)||[]).length,4);assert(!html.includes('<script>'));assert(html.includes('&lt;script&gt;headline'));assert(html.includes('★ 중요'));
const nodes={};Object.assign(context,{user:{role:'viewer'},newsFilter:{category:'안전',q:'',view:'keep'},newsOffset:0,newsTotal:2,newsArticleTotal:3,newsPreviewStatus:{},newsSteelPress:{},newsCategories:['안전','노사관계'],$:s=>nodes[s]||(nodes[s]={addEventListener(){}}),$$:()=>[],loadNews(){},openNewsSettings(){}});
vm.runInContext(code.slice(code.indexOf('function renderNews(){'),code.indexOf('async function openNewsSettings()')),context);vm.runInContext('renderNews()',context);
html=nodes['#newsPanel'].innerHTML;assert(!html.includes('news-card-grid'));assert(html.includes('class="news-list"'));
assert(html.indexOf('news-headlines')<html.indexOf('id="newsFilters"'));assert(html.indexOf('id="newsCategoryTabs"')<html.indexOf('class="news-list"'));
context.newsHeadlines=[];assert.equal(vm.runInContext('renderNewsHeadlines()',context),'');
console.log('PASS: four safe headline cards above horizontal rows in category tabs; empty headlines hidden');

context.newsSteelPress={date:'2026-10-28',sources:[{name:'스틸데일리',items:[{title:'<script>기사</script>',url:'https://www.steeldaily.co.kr/news/articleView.html?idxno=1',published:'2026-10-27T20:00:00Z'}],list_url:'https://www.steeldaily.co.kr/',google_url:'https://www.google.com/search?q=test',error:''}]};
html=vm.runInContext('renderSteelPress(false)',context);assert(!html.includes('<script>'));assert(html.includes('05:00'));assert(!html.includes('id="steelPressFetch"'));assert(html.includes('구글에서 찾기'));
console.log('PASS: steel press metadata escaping, Korean time and reader controls');

for(const ids of [['readerScheduleTab','readerNewsTab','readerArchiveTab','readerFinancialTab','readerMemoTab'],['scheduleNav','newsNav','allNav','financialNav','memoNav']]){
 for(let i=1;i<ids.length;i++)assert(template.indexOf('id="'+ids[i-1]+'"')<template.indexOf('id="'+ids[i]+'"'));
}
context.newsSteelPress.sources.push({...context.newsSteelPress.sources[0],name:'페로타임즈'});
vm.runInContext('renderNews()',context);html=nodes['#newsPanel'].innerHTML;
assert(html.includes('news-reader-columns'));assert(html.indexOf('class="news-list"')<html.indexOf('news-press-sidebar'));
assert(html.indexOf('스틸데일리')<html.indexOf('페로타임즈'));assert.equal((html.match(/<h2>철강 전문지<\/h2>/g)||[]).length,1);
context.user={role:'admin'};vm.runInContext('renderNews()',context);assert(nodes['#newsPanel'].innerHTML.includes('news-reader-columns'));assert(nodes['#newsPanel'].innerHTML.includes('id="steelPressFetch"'));assert(nodes['#newsPanel'].innerHTML.includes('id="newsSettings"'));
console.log('PASS: reader left news/right stacked press, admin layout matches viewer, matching five-tab order');

context.user={role:'viewer'};vm.runInContext('renderNews()',context);assert(nodes['#newsPanel'].innerHTML.includes('주요 언론 기사'));assert(!nodes['#newsPanel'].innerHTML.includes('최근 14일 기사만 표시합니다.'));console.log('PASS: renamed major press section and removed explanatory paragraph');

assert(!html.includes('한국시간'));assert(!html.includes('오늘의 철강'));
