"""Manual Naver news search; credentials stay on the archive server."""
import datetime as dt
import hashlib,html,json,os,re,secrets,threading,urllib.request,urllib.parse,urllib.error
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from flask import request,jsonify,abort,send_file
from news_filter import classify,should_drop,strict_drop,demoted,VERSION as FILTER_VERSION
from news_grouping import category,group_articles,title_overlap,headline_subject,normalized,CATEGORIES,CATEGORY_VERSION
from news_preview import make_preview

def utc_now():return dt.datetime.now(dt.timezone.utc)

def clean(value):return html.unescape(re.sub(r'<[^>]*>','',str(value or ''))).strip()
def canonical(value):
    try:
        u=urllib.parse.urlsplit(value)
        if u.scheme not in ('https','http') or not u.hostname or u.username or u.password:return ''
        params=[(k,v) for k,v in urllib.parse.parse_qsl(u.query,keep_blank_values=True) if not k.lower().startswith('utm_')]
        return urllib.parse.urlunsplit((u.scheme,u.netloc.lower(),u.path,urllib.parse.urlencode(sorted(params)),''))
    except (ValueError,TypeError):return ''
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def search_terms(value):
    terms=list(dict.fromkeys(term.strip() for term in re.split(r'[,，\n\r]+',value) if term.strip()))
    if not 1<=len(terms)<=20:raise ValueError('검색어는 1~20개까지 입력하세요.')
    return terms

def fetch_news(config):
    items=[];seen=set()
    for term in search_terms(config.get('query','현대제철')):
        for item in fetch_news_term(config,term):
            if not isinstance(item,dict):continue
            url=canonical(item.get('originallink','')) or canonical(item.get('link',''))
            if url and url in seen:continue
            if url:seen.add(url)
            items.append(item)
    return items

def fetch_news_term(config,term):
    hub=config.get('mode')=='hub'
    endpoint='https://naverapihub.apigw.ntruss.com/search/v1/news' if hub else 'https://openapi.naver.com/v1/search/news.json'
    headers=({'X-NCP-APIGW-API-KEY-ID':config['client_id'],'X-NCP-APIGW-API-KEY':config['secret']} if hub else {'X-Naver-Client-Id':config['client_id'],'X-Naver-Client-Secret':config['secret']})
    query=urllib.parse.urlencode({'query':term,'display':100,'start':1,'sort':'date'})
    req=urllib.request.Request(endpoint+'?'+query,headers=headers)
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=12) as response:
        raw=response.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:raise ValueError('too large')
    data=json.loads(raw)
    if not isinstance(data,dict) or not isinstance(data.get('items'),list):raise ValueError('invalid result')
    return data['items']

def headline_company(item):
    title=item.get('title','')
    return bool(re.search(r'현대\s*제철|(?:당진|포항|인천|순천)\s*(?:제철소|공장)',title))
def headline_rank(item):
    weights={'안전':50,'노사관계':40,'경영(투자·실적)':30,'정책':20,'기타':10}
    score=weights.get(item.get('category'),0)+min(item.get('article_count',1)-1,10)*2
    return (score,bool(item.get('important')),item['published'],item['id'])
def headline_groups(records,now):
    korea=dt.timezone(dt.timedelta(hours=9));today=now.astimezone(korea).date()
    candidates={today:[],today-dt.timedelta(days=1):[]}
    for n in records:
        try:published=dt.datetime.fromisoformat(n['published'].replace('Z','+00:00'))
        except (ValueError,TypeError):continue
        if published.tzinfo is None:continue
        day=published.astimezone(korea).date()
        if day in candidates and published<=now and not n['excluded'] and (n['relevance']=='keep' or n['important']) and not should_drop(n['title']) and not strict_drop(n['title'],n.get('description',''),n.get('category')) and not demoted(n['title'],n.get('description','')):candidates[day].append(n)
    selected=candidates[today] or candidates[today-dt.timedelta(days=1)]
    groups=sorted(group_articles(selected),key=headline_rank,reverse=True);chosen=[]
    def diverse(item):
        subject=headline_subject(item['title'])
        return all(not (subject and subject==headline_subject(existing['title'])) and title_overlap(item['title'],existing['title'])<.4 and SequenceMatcher(None,normalized(item['title']),normalized(existing['title'])).ratio()<.85 for existing in chosen)
    for item in groups:
        if len(chosen)>=2:break
        if headline_company(item) and diverse(item):chosen.append(item)
    for item in groups:
        if len(chosen)>=4:break
        if item not in chosen and diverse(item):chosen.append(item)
    return chosen

def reclassify_news(c):
    old=c.execute("SELECT value FROM settings WHERE key='news_filter_version'").fetchone()
    if not old or old[0]!=FILTER_VERSION:
        for r in c.execute('SELECT id,title,description FROM news_articles').fetchall():
            relevance,reason=classify(r['title'],r['description'])
            c.execute('UPDATE news_articles SET relevance=?,filter_reason=? WHERE id=?',(relevance,reason,r['id']))
        c.execute("INSERT OR REPLACE INTO settings VALUES('news_filter_version',?)",(FILTER_VERSION,))
    old_category=c.execute("SELECT value FROM settings WHERE key='news_category_version'").fetchone()
    if not old_category or old_category[0]!=CATEGORY_VERSION:
        for row in c.execute('SELECT id,title,description FROM news_articles').fetchall():
            c.execute('UPDATE news_articles SET category=? WHERE id=?',(category(row['title'],row['description']),row['id']))
        c.execute("INSERT OR REPLACE INTO settings VALUES('news_category_version',?)",(CATEGORY_VERSION,))

def install(a):
    config_path=a.DATA/'news_config.json';guard=threading.Lock()
    with a.db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS news_articles(id TEXT PRIMARY KEY,url TEXT UNIQUE,title TEXT,description TEXT,publisher TEXT,published TEXT,category TEXT,important INTEGER DEFAULT 0,excluded INTEGER DEFAULT 0,version INTEGER DEFAULT 1,collected TEXT);
        CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published DESC);
        CREATE INDEX IF NOT EXISTS idx_news_excluded ON news_articles(excluded);''')
        columns={r[1] for r in c.execute('PRAGMA table_info(news_articles)')}
        for name in ('relevance','filter_reason','preview'):
            if name not in columns:c.execute('ALTER TABLE news_articles ADD COLUMN '+name+" TEXT DEFAULT ''")
        reclassify_news(c)
        c.execute("UPDATE news_articles SET preview='' WHERE preview='running'")
    preview_lock=threading.Lock();preview_info={'running':False,'done':0,'failed':0}
    preview_folder=a.DATA/'news_previews';preview_folder.mkdir(exist_ok=True)
    def start_previews():
        if not preview_lock.acquire(blocking=False):return False
        preview_info.update(running=True,done=0,failed=0)
        def work():
            try:
                with a.db() as c:
                    candidates=[dict(r) for r in c.execute("SELECT * FROM news_articles WHERE published>=? AND excluded=0 AND (relevance='keep' OR important=1) AND preview='' ORDER BY published DESC LIMIT 60",((utc_now()-dt.timedelta(days=14)).isoformat(),))]
                with a.db() as c:
                    recent=[dict(r) for r in c.execute("SELECT * FROM news_articles WHERE published>=? AND published<=? AND excluded=0 AND (relevance='keep' OR important=1)",((utc_now()-dt.timedelta(days=3)).isoformat(),utc_now().isoformat()))]
                priority=headline_groups(recent,utc_now())
                records=[];seen=set()
                for record in priority+group_articles(candidates):
                    if record['id'] in seen or record.get('preview') not in ('','running'):continue
                    seen.add(record['id']);records.append(record)
                    if len(records)>=20:break
                for record in records:
                    pid=record['id'];temp=None
                    try:
                        with a.db() as c:c.execute("UPDATE news_articles SET preview='running' WHERE id=?",(pid,))
                        data=make_preview(record['url']);target=preview_folder/(pid+'.jpg');temp=preview_folder/(pid+'.tmp')
                        temp.write_bytes(data);os.replace(temp,target)
                        with a.db() as c:c.execute("UPDATE news_articles SET preview='ready' WHERE id=?",(pid,))
                        preview_info['done']+=1
                    except Exception:
                        with a.db() as c:c.execute("UPDATE news_articles SET preview='unavailable' WHERE id=?",(pid,))
                        preview_info['failed']+=1
                    finally:
                        if temp is not None:temp.unlink(missing_ok=True)
            finally:preview_info['running']=False;preview_lock.release()
        threading.Thread(target=work,daemon=True,name='news-preview').start();return True
    a.start_news_previews=start_previews;a.news_preview_info=preview_info
    @a.app.post('/api/news/previews')
    @a.protected(True)
    def news_previews_start():return jsonify(ok=True,started=start_previews())
    @a.app.get('/api/news-image/<pid>')
    @a.protected()
    def news_preview_image(pid):
        if not re.fullmatch(r'[0-9a-f]{64}',pid):abort(404)
        with a.db() as c:row=c.execute('SELECT * FROM news_articles WHERE id=?',(pid,)).fetchone()
        if not row:abort(404)
        if a.current_role()!='admin' and (row['excluded'] or (row['relevance']!='keep' and not row['important'])):abort(404)
        if row['published']<(utc_now()-dt.timedelta(days=14)).isoformat():abort(404)
        file=preview_folder/(pid+'.jpg')
        if not file.is_file():abort(404)
        return send_file(file,mimetype='image/jpeg')
    def read_config():
        if not config_path.exists():return {'mode':'classic','query':'현대제철'}
        return json.loads(config_path.read_text(encoding='utf-8'))
    @a.app.get('/api/news/config')
    @a.protected(True)
    def news_config_get():
        cfg=read_config();return jsonify(mode=cfg.get('mode','classic'),query=cfg.get('query','현대제철'),configured=bool(cfg.get('client_id') and cfg.get('secret')))
    @a.app.post('/api/news/config')
    @a.protected(True)
    def news_config_save():
        b=request.get_json(silent=True)
        if not isinstance(b,dict):abort(400)
        for key in ('client_id','secret','query','mode'):
            if not isinstance(b.get(key,''),str) or len(b.get(key,''))>(1000 if key=='query' else 200) or any(ord(ch)<32 and not (key=='query' and ch in '\r\n') for ch in b.get(key,'')):abort(400)
        if b.get('mode') not in ('classic','hub') or not b.get('query','').strip():abort(400)
        try:search_terms(b['query'])
        except ValueError as exc:return jsonify(error=str(exc)),400
        if not guard.acquire(blocking=False):return jsonify(error='뉴스 수집 중입니다. 완료 후 설정을 저장하세요.'),409
        try:
            cfg=read_config()
            for key in ('client_id','secret'):
                if b.get(key):cfg[key]=b[key].strip()
            cfg.update(mode=b['mode'],query=b['query'].strip())
            temp=config_path.with_suffix('.tmp')
            try:
                with open(temp,'w',encoding='utf-8',opener=lambda path,flags:os.open(path,flags,0o600)) as f:json.dump(cfg,f,ensure_ascii=False)
                os.replace(temp,config_path)
            finally:temp.unlink(missing_ok=True)
        finally:guard.release()
        return jsonify(ok=True)
    def collect_news():
        if not guard.acquire(blocking=False):return {'error':'이미 뉴스를 가져오는 중입니다.'},409
        try:
            cfg=read_config()
            if not cfg.get('client_id') or not cfg.get('secret'):return {'error':'뉴스 설정에서 인증키를 먼저 저장하세요.'},400
            try:items=fetch_news(cfg)
            except urllib.error.HTTPError as exc:
                return {'error':f'뉴스 API 응답 {exc.code}. 인증키·API 종류·검색 권한·이용 한도를 확인하세요.'},502
            except (OSError,ValueError,KeyError):return {'error':'뉴스 서버에 연결하지 못했거나 응답 형식이 다릅니다. 외부 접속·인증 설정을 확인하세요.'},502
            added=0;skipped=0;outdated=0;filtered=0;now=utc_now();cutoff=now-dt.timedelta(days=14)
            with a.db() as c:
                for item in items:
                    if not isinstance(item,dict):skipped+=1;continue
                    url=canonical(item.get('originallink','')) or canonical(item.get('link',''))
                    title=clean(item.get('title'))[:1000]
                    if not url or not title:skipped+=1;continue
                    try:
                        published=parsedate_to_datetime(item.get('pubDate',''))
                        if published.tzinfo is None:published=published.replace(tzinfo=dt.timezone(dt.timedelta(hours=9)))
                        published=published.astimezone(dt.timezone.utc)
                        if published<cutoff or published>now:outdated+=1;continue
                        published=published.isoformat()
                    except (TypeError,ValueError,OverflowError):skipped+=1;continue
                    description=clean(item.get('description'))[:5000]
                    if should_drop(title) or strict_drop(title,description,category(title,description)):filtered+=1;continue
                    relevance,reason=classify(title,description)
                    changed=c.execute('INSERT OR IGNORE INTO news_articles(id,url,title,description,publisher,published,category,collected,relevance,filter_reason) VALUES(?,?,?,?,?,?,?,?,?,?)',(hashlib.sha256(url.encode()).hexdigest(),url,title,description,urllib.parse.urlsplit(url).hostname,published,category(title,description),a.stamp(),relevance,reason)).rowcount
                    added+=changed
                    if relevance=='exclude':filtered+=changed
                c.execute('INSERT INTO audit(time,actor,action,doc) VALUES(?,?,?,?)',(a.stamp(),'뉴스 수집','뉴스 수집 '+str(added)+'건 추가',''))
            a.start_news_previews()
            return dict(ok=True,added=added,received=len(items),skipped=skipped,outdated=outdated,filtered=filtered),200
        finally:guard.release()
    a.collect_news=collect_news
    @a.app.post('/api/news/fetch')
    @a.protected(True)
    def news_collect():
        result,status=collect_news()
        if status==200 and hasattr(a,'start_steel_press'):a.start_steel_press()
        return jsonify(result),status
    @a.app.get('/api/news')
    @a.protected()
    def news_listing():
        admin=a.current_role()=='admin'
        try:offset=max(0,int(request.args.get('offset','0')))
        except ValueError:abort(400)
        now=utc_now();where=['published>=?','published<=?'];params=[(now-dt.timedelta(days=14)).isoformat(),now.isoformat()]
        view=request.args.get('view','keep')
        if view not in ('keep','review','exclude','all'):abort(400)
        if not admin:view='keep'
        if view=='keep':where.append("(relevance='keep' OR important=1)")
        elif view!='all':where.append('relevance=?');params.append(view)
        if not (admin and request.args.get('excluded')=='1'):where.append('excluded=0')
        if request.args.get('important')=='1':where.append('important=1')
        cat=request.args.get('category','')
        if cat:
            if cat not in CATEGORIES:abort(400)
        q=request.args.get('q','')[:200]
        if q:where.append('(instr(title,?)>0 OR instr(description,?)>0)');params.extend([q,q])
        sql=' WHERE '+' AND '.join(where) if where else ''
        with a.db() as c:
            records=[dict(r) for r in c.execute('SELECT * FROM news_articles'+sql+' ORDER BY published DESC,id',params)]
        if not (admin and view=='exclude'):records=[record for record in records if not should_drop(record['title']) and not strict_drop(record['title'],record.get('description',''),record.get('category'))]
        for record in records:record['has_image']=record['preview']=='ready' and (preview_folder/(record['id']+'.jpg')).is_file()
        all_grouped=group_articles(records)
        all_grouped.sort(key=lambda row:demoted(row['title'],row.get('description','')))
        category_counts={c:sum(1 for group in all_grouped if group['category']==c) for c in CATEGORIES}
        category_counts['']=len(all_grouped)
        grouped=[group for group in all_grouped if not cat or group['category']==cat]
        filtered_records=[record for record in records if not cat or record['category']==cat]
        # Headlines use a separate global pool, independent of every list filter.
        with a.db() as c:
            recent=[dict(r) for r in c.execute("SELECT * FROM news_articles WHERE published>=? AND published<=? AND excluded=0 AND (relevance='keep' OR important=1)",((now-dt.timedelta(days=3)).isoformat(),now.isoformat()))]
        for record in recent:record['has_image']=record['preview']=='ready' and (preview_folder/(record['id']+'.jpg')).is_file()
        featured=headline_groups(recent,now)
        headline_fields=('id','title','url','publisher','published','category','description','issue_label','article_count','important','group_latest','has_image','image_id')
        headlines=[{k:n.get(k) for k in headline_fields} for n in featured]
        press=a.steel_press_listing() if hasattr(a,'steel_press_listing') else {}
        return jsonify(headlines=headlines,steel_press=press,items=grouped[offset:offset+100],total=len(grouped),article_total=len(filtered_records),category_counts=category_counts,categories=CATEGORIES,days=14,view=view,preview_status=dict(preview_info))
    @a.app.post('/api/news/group-action')
    @a.protected(True)
    def news_group_action():
        b=request.get_json(silent=True) or {};items=b.get('items')
        if type(b.get('excluded')) is not bool or not isinstance(items,list) or not 1<=len(items)<=1000:abort(400)
        if any(not isinstance(x,dict) or not isinstance(x.get('id'),str) or type(x.get('version')) is not int for x in items) or len({x['id'] for x in items})!=len(items):abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            for item in items:
                r=c.execute('SELECT version FROM news_articles WHERE id=?',(item['id'],)).fetchone()
                if not r or r[0]!=item['version']:abort(409)
            for item in items:c.execute('UPDATE news_articles SET excluded=?,version=version+1 WHERE id=?',(int(b['excluded']),item['id']))
            a.log(c,'뉴스 묶음 제외/복원 '+str(len(items))+'건')
        return jsonify(ok=True)
    @a.app.post('/api/news/article')
    @a.protected(True)
    def news_update():
        b=request.get_json(silent=True)
        if not isinstance(b,dict) or b.get('field') not in ('important','excluded') or type(b.get('value')) is not bool:abort(400)
        if not isinstance(b.get('id'),str) or not re.fullmatch(r'[0-9a-f]{64}',b['id']) or type(b.get('version')) is not int:abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            changed=c.execute('UPDATE news_articles SET '+b['field']+'=?,version=version+1 WHERE id=? AND version=?',(int(b['value']),b.get('id'),b.get('version'))).rowcount
            if not changed:abort(409)
            a.log(c,'뉴스 '+b['field']+' 변경',b.get('id'))
        return jsonify(ok=True)
