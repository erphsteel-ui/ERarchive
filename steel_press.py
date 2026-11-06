"""Public steel-newspaper list metadata; no member-only article bodies."""
import datetime as dt,hashlib,html,re,threading,urllib.parse,urllib.request
from flask import jsonify
KST=dt.timezone(dt.timedelta(hours=9))
SOURCES={'steeldaily':('스틸데일리','www.steeldaily.co.kr'),'ferrotimes':('페로타임즈','www.ferrotimes.com')}
def utc_now():return dt.datetime.now(dt.timezone.utc)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def text(value):return html.unescape(re.sub(r'<[^>]*>','',value)).strip()
def parse_list(raw,source):
 name,domain=SOURCES[source];markup=raw.decode('utf-8',errors='replace') if isinstance(raw,bytes) else raw
 if source=='steeldaily':
  section=re.search(r'<section\b[^>]*id=["\']section-list["\'][^>]*>(.*?)</section>',markup,re.S|re.I)
  blocks=re.findall(r'<li\b[^>]*>(.*?)</li>',section[1],re.S|re.I) if section else []
  title_pattern=r'<h[234]\b[^>]*class=["\'][^"\']*\btitles\b[^"\']*["\'][^>]*>\s*<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
 else:
  blocks=re.split(r'<div\b[^>]*class=["\'](?:list-block|table-row)(?:\s+[^"\']*)?["\'][^>]*>',markup,flags=re.I)[1:]
  title_pattern=r'<div\b[^>]*class=["\'][^"\']*\blist-titles\b[^"\']*["\'][^>]*>.*?<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>'
 items=[];seen=set()
 for block in blocks:
  title=re.search(title_pattern,block,re.S|re.I);date=re.search(r'\b(20\d{2}-\d{2}-\d{2})\s+(\d{2}:\d{2})\b',block)
  if not title or not date:continue
  try:published=dt.datetime.fromisoformat(date[1]+'T'+date[2]).replace(tzinfo=KST).astimezone(dt.timezone.utc).isoformat()
  except ValueError:continue
  url=urllib.parse.urljoin('https://'+domain,html.unescape(title[1]));parts=urllib.parse.urlsplit(url)
  if parts.hostname not in (domain,domain.removeprefix('www.')) or parts.path!='/news/articleView.html':continue
  article=urllib.parse.parse_qs(parts.query).get('idxno',[''])[0]
  if not re.fullmatch(r'\d+',article) or article in seen:continue
  seen.add(article);heading=text(title[2])[:600]
  if heading:items.append(dict(id=hashlib.sha256((source+':'+article).encode()).hexdigest(),source=source,title=heading,url='https://'+domain+'/news/articleView.html?idxno='+article,published=published))
 if not items:raise ValueError('공개 기사 목록 형식을 확인하지 못했습니다.')
 return items

def fetch_page(source,page):
 domain=SOURCES[source][1];url='https://'+domain+'/news/articleList.html?view_type=sm&page='+str(page)
 req=urllib.request.Request(url,headers={'User-Agent':'ERArchive/0.38','Accept':'text/html','Accept-Encoding':'identity'})
 with urllib.request.build_opener(NoRedirect()).open(req,timeout=10) as response:raw=response.read(2*1024*1024+1)
 if len(raw)>2*1024*1024:raise ValueError('응답 크기 초과')
 return parse_list(raw,source)

def collect_source(source,now):
 today=now.astimezone(KST).date();result={}
 for page in range(1,6):
  rows=fetch_page(source,page);fresh=0
  for item in rows:
   date=dt.datetime.fromisoformat(item['published'])
   if date.astimezone(KST).date()==today and date<=now and item['id'] not in result:result[item['id']]=item;fresh+=1
  if any(dt.datetime.fromisoformat(x['published']).astimezone(KST).date()<today for x in rows) or not fresh:break
 return list(result.values())

def install(a):
 guard=threading.Lock()
 with a.db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS steel_press_articles(id TEXT PRIMARY KEY,source TEXT,title TEXT,url TEXT,published TEXT,collected TEXT);
  CREATE INDEX IF NOT EXISTS idx_steel_press_date ON steel_press_articles(published,source);
  CREATE TABLE IF NOT EXISTS steel_press_status(source TEXT PRIMARY KEY,checked TEXT,error TEXT);''')
 def listing():
  now=utc_now();today=now.astimezone(KST).date();start=dt.datetime.combine(today,dt.time(),KST).astimezone(dt.timezone.utc).isoformat()
  with a.db() as c:
   rows=[dict(r) for r in c.execute('SELECT * FROM steel_press_articles WHERE published>=? AND published<=? ORDER BY published DESC,id',(start,now.isoformat()))]
   statuses={r['source']:dict(r) for r in c.execute('SELECT * FROM steel_press_status')}
  sources=[]
  for source,(name,domain) in SOURCES.items():
   query='site:'+domain.removeprefix('www.')+' after:'+today.isoformat()+' before:'+(today+dt.timedelta(days=1)).isoformat()
   state=statuses.get(source,{})
   sources.append(dict(id=source,name=name,items=[r for r in rows if r['source']==source],checked=state.get('checked',''),error=state.get('error',''),google_url='https://www.google.com/search?'+urllib.parse.urlencode({'q':query}),list_url='https://'+domain+'/news/articleList.html?view_type=sm'))
  return dict(date=today.isoformat(),running=guard.locked(),sources=sources)
 def collect(acquired=False):
  if not acquired and not guard.acquire(blocking=False):return {'ok':False,'error':'전문지 수집이 이미 진행 중입니다.'}
  errors=[]
  try:
   now=utc_now()
   for source in SOURCES:
    error=''
    try:
     rows=collect_source(source,now)
     with a.db() as c:
      for item in rows:c.execute('INSERT OR REPLACE INTO steel_press_articles VALUES(?,?,?,?,?,?)',(item['id'],source,item['title'],item['url'],item['published'],a.stamp()))
    except Exception:
     error='공개 목록 수집 실패 · 원문 목록이나 구글 검색을 확인하세요.';errors.append(SOURCES[source][0]+': '+error)
    with a.db() as c:c.execute('INSERT OR REPLACE INTO steel_press_status VALUES(?,?,?)',(source,a.stamp(),error))
   with a.db() as c:c.execute('DELETE FROM steel_press_articles WHERE published<?',((now-dt.timedelta(days=30)).isoformat(),))
   return {'ok':not errors,'error':' · '.join(errors)}
  finally:guard.release()
 def start():
  if not guard.acquire(blocking=False):return False
  try:threading.Thread(target=collect,args=(True,),daemon=True,name='steel-press').start()
  except Exception:guard.release();raise
  return True
 a.collect_steel_press=collect
 @a.app.post('/api/news/steel-press/fetch')
 @a.protected(True)
 def steel_press_fetch():return jsonify(ok=True,started=start())
 a.start_steel_press=start;a.steel_press_listing=listing
