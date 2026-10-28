"""Durable optional VL review queue. No automatic replacement of reviewed text."""
import hashlib,io,json,secrets,threading,time
from pathlib import Path
from PIL import Image,UnidentifiedImageError
from flask import request,jsonify,abort,send_file
import vl_adapter

MAX_FILE=15*1024*1024

def selected(result):
    variants=result.get('variants',[])
    return variants[result.get('selected',0)].get('text','') if variants else ''

def install(a):
    root=a.DATA/'precision';root.mkdir(exist_ok=True)
    default=a.ROOT/'정밀인식폴더';mutex=threading.RLock();stable={}
    info={'message':'정밀 인식 대기','errors':[]}
    with a.db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS precision_jobs(
          hash TEXT PRIMARY KEY,name TEXT,path TEXT,state TEXT,created TEXT,updated TEXT,
          baseline TEXT DEFAULT '',result TEXT DEFAULT '',error TEXT DEFAULT '',seconds REAL DEFAULT 0,
          version INTEGER DEFAULT 1,decision TEXT DEFAULT '');''')
        c.execute("INSERT OR IGNORE INTO settings VALUES('precision_inbox',?)",(json.dumps({'enabled':True,'path':str(default)},ensure_ascii=False),))
    def config():
        with a.db() as c:return json.loads(c.execute("SELECT value FROM settings WHERE key='precision_inbox'").fetchone()[0])
    def target(c,digest):
        p=c.execute('SELECT p.*,d.version FROM pages p JOIN documents d ON d.id=p.doc WHERE p.hash=?',(digest,)).fetchone()
        if p:return dict(kind='page',id=p['id'],text=p['text'],version=p['version'],doc=p['doc'],path=str(a.DATA/'images'/p['path']))
        p=c.execute("SELECT p.*,b.version,b.state batch_state FROM batch_pages p JOIN batches b ON b.id=p.batch WHERE p.hash=? AND b.state!='saved'",(digest,)).fetchone()
        if p:
            if p['state'] in ('running','queued') or p['batch_state'] in ('queued','processing'):return dict(kind='busy',id=p['id'],text='',version=p['version'],path=str(a.DATA/'images'/p['path']))
            return dict(kind='batch',id=p['id'],text=selected(json.loads(p['result'])),version=p['version'],batch=p['batch'],path=str(a.DATA/'images'/p['path']))
        p=c.execute("SELECT * FROM schedule_sources WHERE id=?",('image:'+digest,)).fetchone()
        if p:return dict(kind='source',id=p['id'],text=p['text'],version=hashlib.sha256(p['text'].encode()).hexdigest(),path=str(a.DATA/'schedule_sources'/p['path']) if p['path'] else '')
        if c.execute("SELECT 1 FROM schedule_jobs WHERE hash=? AND state IN ('queued','running')",(digest,)).fetchone():return dict(kind='busy',id=digest,text='',version=0,path='')
        return dict(kind='new',id=digest,text='',version=0,path='')
    def token(t):return hashlib.sha256(json.dumps(t,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    def enqueue(raw,name):
        if not raw or len(raw)>MAX_FILE:raise ValueError('이미지는 장당 15MB 이하로 넣어주세요.')
        try:
            im=Image.open(io.BytesIO(raw));fmt=im.format
            if fmt not in ('JPEG','PNG','WEBP') or im.width*im.height>40000000:raise ValueError('JPG/PNG/WebP · 4천만 화소 이하만 지원합니다.')
            im.verify()
        except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as e:raise ValueError('이미지 파일을 확인하세요. HWP는 일정자료 수집폴더를 사용하세요.') from e
        digest=hashlib.sha256(raw).hexdigest();ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt]
        name=str(name).replace('\\','/').split('/')[-1][:255]
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM precision_jobs WHERE hash=?',(digest,)).fetchone():return digest,False
            path=digest+ext;(root/path).write_bytes(raw)
            c.execute('INSERT INTO precision_jobs(hash,name,path,state,created,updated) VALUES(?,?,?,?,?,?)',(digest,name,path,'queued',a.stamp(),a.stamp()))
        import batches
        batches._WAKE.set();return digest,True
    def scan(now=None):
        with mutex:
            cfg=config();now=time.monotonic() if now is None else now
            if not cfg['enabled']:info['message']='정밀 인식 일시정지 · 진행 중인 한 장은 완료 후 멈춥니다.';return
            try:
                folder=Path(cfg['path'])
                if folder==default:folder.mkdir(exist_ok=True)
                errors=[];present=set();count=0;total=0
                for p in sorted(folder.iterdir()):
                    if p.is_symlink() or not p.is_file() or p.suffix.lower() not in ('.jpg','.jpeg','.png','.webp'):continue
                    key=str(p);present.add(key);st=p.stat();sig=(st.st_size,st.st_mtime_ns);old=stable.get(key)
                    if not old or old[0]!=sig:stable[key]=(sig,now,False);continue
                    if old[2] or now-old[1]<15:continue
                    if st.st_size>MAX_FILE:errors.append(p.name+' · 15MB 초과');continue
                    if count>=20 or total+st.st_size>60*1024*1024:continue
                    try:
                        with p.open('rb') as f:raw=f.read(MAX_FILE+1)
                        after=p.stat()
                        if (after.st_size,after.st_mtime_ns)!=sig or len(raw)!=st.st_size:stable.pop(key,None);continue
                        enqueue(raw,p.name);count+=1;total+=len(raw);stable[key]=(sig,old[1],True)
                    except (OSError,ValueError) as e:errors.append(p.name+' · '+str(e))
                for key in set(stable)-present:stable.pop(key,None)
                info.update(message='정밀 인식 자동 수집 중 · 복사 완료 후 15초 대기',errors=errors[:50])
            except OSError as e:info.update(message='정밀 폴더 연결 오류 · '+str(e),errors=[])
    def process():
        if not config()['enabled']:return False
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE');job=None
            for row in c.execute("SELECT * FROM precision_jobs WHERE state='queued' ORDER BY created,hash").fetchall():
                t=target(c,row['hash'])
                if t['kind']!='busy':job=dict(row);break
            if not job:return False
            c.execute("UPDATE precision_jobs SET state='running',error='',updated=?,version=version+1 WHERE hash=?",(a.stamp(),job['hash']))
        try:
            baseline=t['text'] or job['baseline']
            if not baseline:
                baseline=selected(a.recognize_body(root/job['path']))
            with a.db() as c:c.execute('UPDATE precision_jobs SET baseline=? WHERE hash=?',(baseline,job['hash']))
            r=vl_adapter.recognize(root/job['path'])
            (root/(job['hash']+'.json')).write_text(json.dumps(r['raw'],ensure_ascii=False),encoding='utf-8')
            with a.db() as c:c.execute("UPDATE precision_jobs SET state='done',result=?,seconds=?,updated=?,version=version+1 WHERE hash=?",(r['text'],r['seconds'],a.stamp(),job['hash']))
        except Exception as e:
            with a.db() as c:c.execute("UPDATE precision_jobs SET state='failed',error=?,updated=?,version=version+1 WHERE hash=?",(str(e)[-1200:],a.stamp(),job['hash']))
        return True
    def recover():
        with a.db() as c:c.execute("UPDATE precision_jobs SET state='queued',version=version+1 WHERE state='running'")
    a.scan_precision_inbox=scan;a.process_precision_job=process;a.recover_precision_jobs=recover
    a.enqueue_precision=enqueue
    @a.app.get('/api/precision')
    @a.protected(True)
    def precision_listing():
        with a.db() as c:jobs=[dict(r) for r in c.execute("SELECT hash,name,state,created,updated,error,seconds,version,decision FROM precision_jobs ORDER BY state IN ('reviewed') ASC,created DESC LIMIT 200")]
        return jsonify(config=config(),status=dict(info),runtime=vl_adapter.status(),jobs=jobs)
    @a.app.post('/api/precision/config')
    @a.protected(True)
    def precision_configure():
        b=request.get_json()
        if not isinstance(b,dict) or not isinstance(b.get('enabled'),bool) or not isinstance(b.get('path'),str):abort(400)
        path=Path(b['path']).expanduser()
        if not path.is_absolute() or not path.is_dir():return jsonify(error='서버 PC에서 접근할 수 있는 기존 폴더 경로를 입력하세요.'),400
        path=path.resolve();data=a.DATA.resolve()
        with a.db() as c:other=[Path(json.loads(r[0])['path']).resolve() for r in c.execute("SELECT value FROM settings WHERE key IN ('inbox','schedule_inbox')")]
        if path==data or data in path.parents or path in other:return jsonify(error='데이터·홍보물·일정자료 폴더와 다른 폴더를 지정하세요.'),400
        with mutex:
            with a.db() as c:
                c.execute("UPDATE settings SET value=? WHERE key='precision_inbox'",(json.dumps({'enabled':b['enabled'],'path':str(path)},ensure_ascii=False),));a.log(c,'정밀 인식 설정 변경')
            stable.clear()
        return jsonify(ok=True)
    @a.app.post('/api/precision/page/<pid>')
    @a.protected(True)
    def precision_request_page(pid):
        with a.db() as c:p=c.execute('SELECT * FROM pages WHERE id=?',(pid,)).fetchone()
        if not p:abort(404)
        digest,created=enqueue((a.DATA/'images'/p['path']).read_bytes(),p['path'])
        return jsonify(hash=digest,created=created),202
    @a.app.get('/api/precision/<digest>')
    @a.protected(True)
    def precision_detail(digest):
        with a.db() as c:
            row=c.execute('SELECT * FROM precision_jobs WHERE hash=?',(digest,)).fetchone()
            if not row:abort(404)
            job=dict(row);t=target(c,digest)
        job.pop('path');job.update(current=t['text'] if t['kind']!='new' else job['baseline'],target=t['kind'],token=token(t))
        return jsonify(job)
    @a.app.get('/api/precision/<digest>/image')
    @a.protected(True)
    def precision_original(digest):
        with a.db() as c:r=c.execute('SELECT path FROM precision_jobs WHERE hash=?',(digest,)).fetchone()
        if not r:abort(404)
        return send_file(root/r[0])
    @a.app.post('/api/precision/<digest>/retry')
    @a.protected(True)
    def precision_retry(digest):
        with a.db() as c:
            if not c.execute("UPDATE precision_jobs SET state='queued',error='',version=version+1 WHERE hash=? AND state='failed'",(digest,)).rowcount:abort(409)
        return jsonify(ok=True)
    @a.app.post('/api/precision/<digest>/review')
    @a.protected(True)
    def precision_review(digest):
        b=request.get_json()
        if not isinstance(b,dict) or b.get('action') not in ('apply','keep'):abort(400)
        text=b.get('text','')
        if b['action']=='apply' and (not isinstance(text,str) or not text.strip() or len(text)>100000):abort(400)
        # Synchronize source-only approval with the schedule scanner's snapshots.
        with a.schedule_lock,a.db() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM precision_jobs WHERE hash=?',(digest,)).fetchone()
            if not r:abort(404)
            if r['state']!='done' or r['version']!=b.get('version'):abort(409)
            t=target(c,digest)
            if b.get('token')!=token(t) or t['kind']=='busy':return jsonify(error='검토 중 원문이 바뀌었습니다. 결과를 다시 열어 비교하세요.'),409
            if b['action']=='apply':
                if t['kind']=='page':
                    c.execute('INSERT OR IGNORE INTO page_original VALUES(?,?,?)',(t['id'],t['text'],'VL 적용 전 본문'))
                    c.execute('INSERT INTO text_history(page,text,created) VALUES(?,?,?)',(t['id'],t['text'],a.stamp()))
                    c.execute('UPDATE pages SET text=? WHERE id=?',(text,t['id']))
                    c.execute('UPDATE documents SET version=version+1,updated=? WHERE id=?',(a.stamp(),t['doc']))
                elif t['kind']=='batch':
                    old=json.loads(c.execute('SELECT result FROM batch_pages WHERE id=?',(t['id'],)).fetchone()[0]);variants=old.setdefault('variants',[])
                    variants.append(dict(name='VL · 관리자 확인',text=text,warnings=[],warning_count=0));old['selected']=len(variants)-1
                    c.execute("UPDATE batch_pages SET state='done',result=? WHERE id=?",(json.dumps(old,ensure_ascii=False),t['id']))
                    c.execute('UPDATE batches SET version=version+1 WHERE id=?',(t['batch'],))
                elif t['kind']=='source':
                    c.execute('UPDATE schedule_sources SET text=? WHERE id=?',(text,t['id']))
                elif b.get('destination')=='schedule':
                    dest=a.DATA/'schedule_sources'/r['path'];dest.write_bytes((root/r['path']).read_bytes())
                    c.execute('INSERT INTO schedule_sources(id,name,kind,text,path,created,status,reference) VALUES(?,?,?,?,?,?,?,?)',('image:'+digest,r['name'],'image',text,dest.name,a.stamp(),'정밀 본문 확인 · 일정 추출 대기',''))
                    c.execute('INSERT OR IGNORE INTO file_imports VALUES(?,?)',(digest,a.stamp()))
                elif b.get('destination')=='archive':
                    bid=secrets.token_hex(12);pid=secrets.token_hex(12);path=pid+Path(r['path']).suffix
                    (a.DATA/'images'/path).write_bytes((root/r['path']).read_bytes())
                    result={'raw':r['baseline'],'variants':[{'name':'PP-OCRv5 원문','text':r['baseline']},{'name':'VL · 관리자 확인','text':text}], 'selected':1,'status':'정밀 인식 검토 완료'}
                    orgs=json.loads(c.execute("SELECT value FROM settings WHERE key='organizations'").fetchone()[0]);meta=a.suggest(r['baseline'] or text,orgs,{})
                    c.execute('INSERT INTO batches(id,state,mode,created,actor) VALUES(?,?,?,?,?)',(bid,'queued','single',a.stamp(),'정밀 인식 검토'))
                    c.execute('INSERT INTO batch_pages(id,batch,name,path,hash,position,state,result,meta) VALUES(?,?,?,?,?,0,?,?,?)',(pid,bid,r['name'],path,digest,'done',json.dumps(result,ensure_ascii=False),json.dumps(meta,ensure_ascii=False)))
                    c.execute('INSERT OR IGNORE INTO file_imports VALUES(?,?)',(digest,a.stamp()))
                else:return jsonify(error='새 이미지의 등록 위치를 선택하세요.'),400
            c.execute("UPDATE precision_jobs SET state='reviewed',decision=?,updated=?,version=version+1 WHERE hash=?",(b['action'],a.stamp(),digest))
            a.log(c,'정밀 인식 '+('본문 적용' if b['action']=='apply' else '기존 본문 유지'),digest)
        import batches
        batches._WAKE.set()
        return jsonify(ok=True)
