"""Schedule-only images/HWP, durable queue and separate watched inbox."""
import hashlib,io,json,threading,time
from pathlib import Path
from PIL import Image,UnidentifiedImageError
from flask import request,jsonify,abort
from schedule_extract import hwp_text

MAX_FILE=15*1024*1024

def install(a):
    default=a.ROOT/'일정자료수집폴더'
    with a.db() as c:
        existing=c.execute("SELECT value FROM settings WHERE key='inbox'").fetchone()
        if existing and Path(json.loads(existing[0])['path']).resolve()==default.resolve():default=a.ROOT/'일정전용수집폴더'
        c.execute('''CREATE TABLE IF NOT EXISTS schedule_jobs(
            hash TEXT PRIMARY KEY,name TEXT,kind TEXT,path TEXT,state TEXT,created TEXT,error TEXT DEFAULT '')''')
        c.execute("INSERT OR IGNORE INTO settings VALUES('schedule_inbox',?)",(json.dumps({'enabled':True,'path':str(default)},ensure_ascii=False),))
    mutex=threading.RLock();stable={};info={'message':'수집 준비 중','errors':[]}
    def config():
        with a.db() as c:return json.loads(c.execute("SELECT value FROM settings WHERE key='schedule_inbox'").fetchone()[0])
    def prepare(raw,name):
        if not raw or len(raw)>MAX_FILE:raise ValueError('파일당 15MB 이하로 올려주세요.')
        name=str(name).replace('\\','/').split('/')[-1][:255] or '이름없음'
        digest=hashlib.sha256(raw).hexdigest()
        if Path(name).suffix.lower()=='.hwp':
            if not raw.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):raise ValueError('일반 HWP 5 파일이 아닙니다. DRM 문서는 지원하지 않습니다.')
            kind='hwp';ext='.hwp'
        else:
            try:
                im=Image.open(io.BytesIO(raw));fmt=im.format
                if fmt not in ('JPEG','PNG','WEBP') or im.width*im.height>40000000:raise ValueError('JPG/PNG/WebP, 4천만 화소 이하 이미지만 지원합니다.')
                im.verify();ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt];kind='image'
            except (OSError,UnidentifiedImageError,Image.DecompressionBombError) as e:raise ValueError('지원하는 이미지 또는 HWP 파일을 선택하세요.') from e
        return raw,digest,name,kind,digest+ext
    def enqueue(entries):
        created=[];count=0;duplicates=0
        try:
            with a.db() as c:
                c.execute('BEGIN IMMEDIATE')
                for raw,digest,name,kind,path in entries:
                    if c.execute('SELECT 1 FROM schedule_jobs WHERE hash=?',(digest,)).fetchone():duplicates+=1;continue
                    # A copied original remains available even if an archive page is later deleted.
                    dest=a.DATA/'schedule_sources'/path
                    if not dest.exists():dest.write_bytes(raw);created.append(dest)
                    c.execute('INSERT INTO schedule_jobs(hash,name,kind,path,state,created) VALUES(?,?,?,?,?,?)',(digest,name,kind,path,'queued',a.stamp()))
                    c.execute('INSERT OR IGNORE INTO file_imports VALUES(?,?)',(digest,a.stamp()))
                    count+=1
        except BaseException:
            for dest in created:dest.unlink(missing_ok=True)
            raise
        if count:
            import batches
            batches._WAKE.set()
        return count,duplicates
    def process():
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE');job=c.execute("SELECT * FROM schedule_jobs WHERE state='queued' ORDER BY created,hash LIMIT 1").fetchone()
            if not job:return False
            job=dict(job);c.execute("UPDATE schedule_jobs SET state='running',error='' WHERE hash=?",(job['hash'],))
        try:
            sid=job['kind']+':'+job['hash'];path=a.DATA/'schedule_sources'/job['path']
            with a.db() as c:
                source=c.execute('SELECT text,reference FROM schedule_sources WHERE id=?',(sid,)).fetchone()
                page=c.execute('SELECT p.text,d.meta FROM pages p JOIN documents d ON d.id=p.doc WHERE p.hash=?',(job['hash'],)).fetchone()
                batch=c.execute("SELECT result,meta FROM batch_pages WHERE hash=? AND state='done'",(job['hash'],)).fetchone()
            reference=''
            if source:text,reference=source['text'],source['reference']
            elif job['kind']=='hwp':text=hwp_text(path.read_bytes())
            elif page and page['text']:
                text=page['text'];reference=json.loads(page['meta']).get('date','')
            else:
                result=json.loads(batch['result']) if batch else a.recognize_body(path)
                variants=result.get('variants',[])
                if not variants:raise ValueError(result.get('status','OCR 인식 실패'))
                text=variants[result.get('selected',0)].get('text','')
                if not text.strip():raise ValueError('인식된 본문이 없습니다. 원본 상태를 확인한 뒤 다시 시도하세요.')
                if batch:reference=json.loads(batch['meta']).get('date','')
            a.ingest_schedule(sid,job['name'],job['kind'],text,job['path'],reference)
            with a.db() as c:
                c.execute('UPDATE schedule_sources SET name=?,path=? WHERE id=?',(job['name'],job['path'],sid))
                c.execute("UPDATE schedule_jobs SET state='done',error='' WHERE hash=?",(job['hash'],))
        except Exception as e:
            with a.db() as c:c.execute("UPDATE schedule_jobs SET state='failed',error=? WHERE hash=?",(str(e)[:300],job['hash']))
        return True
    def recover():
        with a.db() as c:c.execute("UPDATE schedule_jobs SET state='queued' WHERE state='running'")
    def scan(now=None):
        with mutex:
            cfg=config()
            if not cfg['enabled']:info['message']='일정자료 자동 수집 꺼짐';return
            folder=Path(cfg['path']);now=time.monotonic() if now is None else now
            try:
                if folder==default:folder.mkdir(exist_ok=True)
                if not folder.is_dir():raise OSError('일정자료 수집폴더에 연결할 수 없습니다.')
                entries=[];errors=[];total=0;present=set()
                for p in sorted(folder.iterdir()):
                    if p.is_symlink() or not p.is_file() or p.suffix.lower() not in ('.hwp','.png','.jpg','.jpeg','.webp'):continue
                    key=str(p);present.add(key);st=p.stat();sig=(st.st_size,st.st_mtime_ns);old=stable.get(key)
                    if old is None or old[0]!=sig:stable[key]=(sig,now,False);continue
                    if now-old[1]<15 or old[2]:continue
                    if st.st_size>MAX_FILE:errors.append(p.name+' · 파일당 15MB 초과');continue
                    if len(entries)>=20 or total+st.st_size>60*1024*1024:continue
                    try:
                        if st.st_size>MAX_FILE:raise ValueError('파일당 15MB 초과')
                        with p.open('rb') as stream:raw=stream.read(MAX_FILE+1)
                        after=p.stat()
                        if (after.st_size,after.st_mtime_ns)!=sig or len(raw)!=st.st_size:stable.pop(key,None);continue
                        entries.append((key,prepare(raw,p.name)));total+=len(raw)
                    except (OSError,ValueError) as e:errors.append(p.name+' · '+str(e))
                count,dups=enqueue([e for _,e in entries])
                for key,_ in entries:stable[key]=(stable[key][0],stable[key][1],True)
                for key in set(stable)-present:stable.pop(key,None)
                info.update(message=f'일정자료 대기 · 최근 수집 {count}개 / 중복 {dups}개',errors=errors[:50])
            except OSError as e:info.update(message='일정자료 수집 오류 · '+str(e),errors=[])
    a.process_schedule_job=process;a.recover_schedule_jobs=recover;a.scan_schedule_inbox=scan
    @a.app.get('/api/schedule/intake')
    @a.protected(True)
    def schedule_intake_status():
        with a.db() as c:jobs=[dict(r) for r in c.execute('SELECT hash,name,kind,state,created,error FROM schedule_jobs ORDER BY created DESC LIMIT 100')]
        with mutex:return jsonify(config=config(),status=dict(info),jobs=jobs)
    @a.app.post('/api/schedule/intake/config')
    @a.protected(True)
    def schedule_intake_config():
        b=request.get_json()
        if not isinstance(b,dict) or not isinstance(b.get('enabled'),bool) or not isinstance(b.get('path'),str):abort(400)
        path=Path(b['path']).expanduser()
        if not path.is_absolute() or not path.is_dir():return jsonify(error='서버 PC에서 접근할 수 있는 기존 폴더 전체 경로를 입력하세요.'),400
        path=path.resolve();data=a.DATA.resolve()
        with a.db() as c:other=Path(json.loads(c.execute("SELECT value FROM settings WHERE key='inbox'").fetchone()[0])['path']).resolve()
        if path==data or data in path.parents or path==other:return jsonify(error='데이터 폴더와 홍보물 수집폴더는 일정자료 수집폴더로 지정할 수 없습니다.'),400
        with a.db() as c:pc=c.execute("SELECT value FROM settings WHERE key='precision_inbox'").fetchone()
        if pc and path==Path(json.loads(pc[0])['path']).resolve():return jsonify(error='정밀인식폴더와 다른 경로를 지정하세요.'),400
        with mutex:
            with a.db() as c:
                c.execute("UPDATE settings SET value=? WHERE key='schedule_inbox'",(json.dumps({'enabled':b['enabled'],'path':str(path)},ensure_ascii=False),));a.log(c,'일정자료 수집폴더 변경')
            stable.clear()
        return jsonify(ok=True)
    @a.app.post('/api/schedule/intake/upload')
    @a.protected(True)
    def schedule_intake_upload():
        files=request.files.getlist('files')
        if not files or len(files)>20:abort(400)
        entries=[];total=0
        try:
            for f in files:
                raw=f.read(MAX_FILE+1);total+=len(raw)
                if total>60*1024*1024:abort(413)
                entries.append(prepare(raw,f.filename))
        except ValueError as e:return jsonify(error=str(e)),400
        count,duplicates=enqueue(entries)
        return jsonify(queued=count,duplicates=duplicates),202
    @a.app.post('/api/schedule/intake/<digest>/retry')
    @a.protected(True)
    def schedule_intake_retry(digest):
        with a.db() as c:
            if not c.execute("UPDATE schedule_jobs SET state='queued',error='' WHERE hash=? AND state='failed'",(digest,)).rowcount:abort(409)
        import batches
        batches._WAKE.set();return jsonify(ok=True)
