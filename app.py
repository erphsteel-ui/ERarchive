from ocr_engine import recognize_body
import tempfile
import os, json, sqlite3, secrets, hashlib, io, subprocess, shutil, re, datetime, threading, time
from pathlib import Path
from functools import wraps
from flask import Flask, request, session, jsonify, send_file, render_template, abort
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageOps, UnidentifiedImageError
ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('ARCHIVE_DATA', ROOT / 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
(DATA / 'images').mkdir(exist_ok=True)
key = DATA / 'secret.key'
if not key.exists(): key.write_text(secrets.token_hex(32))
app = Flask(__name__)
app.config.update(SECRET_KEY=key.read_text(), MAX_CONTENT_LENGTH=65*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE')=='1', PERMANENT_SESSION_LIFETIME=datetime.timedelta(hours=8))
LOCK=threading.Lock()
ATTEMPTS={}
class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()

def db():
    c=sqlite3.connect(DATA/'archive.db', timeout=30, factory=ClosingConnection)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=30000')
    return c

def init():
    with db() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY,password TEXT,role TEXT);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,meta TEXT,created TEXT,updated TEXT,version INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS pages(id TEXT PRIMARY KEY,doc TEXT REFERENCES documents(id) ON DELETE CASCADE,path TEXT,hash TEXT UNIQUE,text TEXT,status TEXT,position INTEGER);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,time TEXT,actor TEXT,action TEXT,doc TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS page_original(page TEXT PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,text TEXT,source TEXT);
CREATE TABLE IF NOT EXISTS ocr_runs(id TEXT PRIMARY KEY,page TEXT REFERENCES pages(id) ON DELETE CASCADE,version INTEGER,result TEXT,created TEXT);
CREATE TABLE IF NOT EXISTS text_history(id INTEGER PRIMARY KEY,page TEXT REFERENCES pages(id) ON DELETE CASCADE,text TEXT,created TEXT);
INSERT OR IGNORE INTO page_original SELECT id,text,'업데이트 시 보존한 본문' FROM pages;
CREATE INDEX IF NOT EXISTS idx_pages_doc_position ON pages(doc,position);
CREATE INDEX IF NOT EXISTS idx_ocr_runs_page ON ocr_runs(page);
CREATE INDEX IF NOT EXISTS idx_text_history_page ON text_history(page);''')
        c.execute("INSERT OR IGNORE INTO settings VALUES('organizations',?)",(json.dumps(['포스코노동조합','금속노조 충남지부 현대제철지회','금속노조 현대자동차지부','전국금속노동조합','민주노동자회','신의회','신진회','한길노동자회','대진회'],ensure_ascii=False),))
init()
def stamp(): return datetime.datetime.now().astimezone().isoformat(timespec='seconds')
def log(c, action, doc=''):
    c.execute('INSERT INTO audit(time,actor,action,doc) VALUES(?,?,?,?)',(stamp(),session.get('user','CLI'),action,doc))
def protected(admin=False):
    def dec(fn):
        @wraps(fn)
        def wrap(*a,**kw):
            with db() as c: u=c.execute('SELECT role FROM users WHERE name=?',(session.get('user'),)).fetchone()
            if not u and (admin or request.method not in ('GET','HEAD')): abort(401)
            if admin and u['role']!='admin': abort(403)
            if request.method not in ('GET','HEAD') and not secrets.compare_digest(request.headers.get('X-CSRF',''),session.get('csrf','invalid')): abort(403)
            return fn(*a,**kw)
        return wrap
    return dec
@app.after_request
def headers(r):
    r.headers['Cache-Control']='no-store'; r.headers['X-Content-Type-Options']='nosniff'; r.headers['X-Frame-Options']='DENY'
    r.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    return r
@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(409)
@app.errorhandler(413)
def error(e): return jsonify(error={400:'입력값 또는 이미지 형식을 확인하세요.',401:'로그인이 필요합니다.',403:'접근 권한 또는 요청 인증을 확인하세요.',404:'자료를 찾을 수 없습니다.',409:'중복 자료 또는 다른 창의 수정 내역이 있습니다. 새로고침하세요.',413:'한 번에 60MB 이하로 올려주세요.'}.get(e.code,'오류')), e.code
@app.get('/')
def index(): return render_template('index.html')
@app.post('/api/login')
def login():
    # Cross-origin JSON POST is not permitted; no CORS enabled.
    if not request.is_json: abort(400)
    b=request.get_json(); name=str(b.get('name','')); addr=request.remote_addr; now=time.time()
    with LOCK:
        for key in list(ATTEMPTS):
            recent=[t for t in ATTEMPTS[key] if now-t<300]
            if recent:ATTEMPTS[key]=recent
            else:ATTEMPTS.pop(key,None)
        failures=ATTEMPTS.get(addr,[])
        if len(failures)>=10: return jsonify(error='로그인 시도가 많습니다. 5분 뒤 다시 시도하세요.'),429
        ATTEMPTS[addr]=failures+[now]
    with db() as c: u=c.execute('SELECT * FROM users WHERE name=?',(name,)).fetchone()
    if not u or not check_password_hash(u['password'],str(b.get('password',''))): return jsonify(error='아이디 또는 비밀번호가 맞지 않습니다.'),401
    with LOCK: ATTEMPTS.pop(addr,None)
    session.clear(); session['user']=name; session['csrf']=secrets.token_hex(24); session.permanent=True
    return jsonify(user=name,role=u['role'],csrf=session['csrf'])
@app.post('/api/change-password')
@protected(True)
def change_password():
    b=request.get_json(silent=True) or {}; old=b.get('current',''); new=b.get('new','')
    if not isinstance(old,str) or not isinstance(new,str) or not 4<=len(new)<=128:
        return jsonify(error='새 비밀번호는 4~128자로 입력하세요.'),400
    with db() as c:
        u=c.execute('SELECT password FROM users WHERE name=?',(session['user'],)).fetchone()
        if not u or not check_password_hash(u['password'],old):return jsonify(error='현재 비밀번호가 맞지 않습니다.'),400
        c.execute('UPDATE users SET password=? WHERE name=?',(generate_password_hash(new),session['user']))
        log(c,'관리자 비밀번호 변경')
    return jsonify(ok=True)

@app.get('/api/me')
@protected()
def me():
    role=current_role()
    return jsonify(user=session.get('user',''),role=role,csrf=session.get('csrf',''))

def current_role():
    with db() as c:
        u=c.execute('SELECT role FROM users WHERE name=?',(session.get('user'),)).fetchone()
    return u['role'] if u else 'viewer'
@app.post('/api/logout')
@protected()
def logout(): session.clear(); return jsonify(ok=True)

def ocr(path, psm=3):
    exe=os.environ.get('TESSERACT_CMD') or shutil.which('tesseract')
    if not exe: return '', 'OCR 미설치 · 직접 입력 가능'
    try:
        langs=subprocess.run([exe,'--list-langs'],capture_output=True,text=True,timeout=10)
        if 'kor' not in langs.stdout.split(): return '', '한국어 OCR 데이터 미설치 · 직접 입력 가능'
        r=subprocess.run([exe,str(path),'stdout','-l','kor+eng','--psm',str(psm)],capture_output=True,timeout=90)
        if r.returncode: return '', 'OCR 실패 · 원본은 보관됨'
        return r.stdout.decode('utf-8',errors='replace').strip(), 'OCR 완료 · 내용 확인 필요'
    except (OSError,subprocess.TimeoutExpired): return '', 'OCR 실행 실패 · 직접 입력 가능'

# Only confirmed mastheads map to an issuer; ambiguous titles never infer one.
MASTHEADS={
    '강철의 함성':'금속노조 충남지부 현대제철지회',
    '현자지부 소식':'금속노조 현대자동차지부',
    '쟁의대책위 속보':None,
    '연대 홍보물':None,
}
def tesseract_header_ocr(path):
    # Separate masthead, large central title and small left publisher typography.
    results={}
    try:
        with Image.open(path) as source, tempfile.TemporaryDirectory(prefix='er-header-') as tmp:
            im=ImageOps.exif_transpose(source).convert('RGB'); w,h=im.size
            regions=[('header',(0,0,w,max(1,round(h*.25))),3),
                     ('title',(round(w*.17),0,round(w*.81),max(1,round(h*.11))),7),
                     ('issuer',(0,0,max(1,round(w*.18)),max(1,round(h*.115))),11)]
            for name,box,psm in regions:
                crop=ImageOps.autocontrast(ImageOps.grayscale(im.crop(box)))
                scale=min(3,2200/max(crop.size))
                crop=crop.resize((max(1,round(crop.width*scale)),max(1,round(crop.height*scale))),Image.Resampling.LANCZOS)
                crop=ImageOps.expand(crop,border=20,fill=255)
                path_out=Path(tmp)/(name+'.png');crop.save(path_out)
                results[name]=ocr(path_out,psm)[0]
        return results
    except (OSError,ValueError): return results

def header_ocr(path):
    result=recognize_body(path)
    return result.get('regions',{})

def normalized_issuer(value):
    value=re.sub(r'\s','',value)
    return value.replace('전국금속노동조합','금속노조')

def suggest(text, orgs, header=None):
    regions=header if isinstance(header,dict) else {}
    head=regions.get('header','') if isinstance(header,dict) else (header if header is not None else '\n'.join(text.splitlines()[:6]))
    title_text=regions.get('title','')
    issuer_text=regions.get('issuer','')
    compact=re.sub(r'\s','',head)
    title_compact=re.sub(r'[^가-힣A-Za-z0-9]','',title_text+'\n'+head)
    lines=[normalized_issuer(line) for line in head.splitlines() if line.strip()]
    issuer_compact=normalized_issuer(issuer_text)
    pubs=[]
    for org in orgs:
        norm=normalized_issuer(org)
        standalone=any(line==norm or re.fullmatch(r'(?:발행처|발행조직|발행)[:：|·-]?'+re.escape(norm),line) for line in lines)
        # Only the dedicated issuer crop may join split issuer lines.
        if norm and (standalone or norm in issuer_compact): pubs.append(org)
    pubs=list({normalized_issuer(o):o for o in reversed(pubs)}.values())
    # Do not classify a parent organization separately from its full local branch.
    pubs=[o for o in pubs if not any(o!=other and normalized_issuer(o) in normalized_issuer(other) for other in pubs)]
    titles=[name for name in MASTHEADS if re.sub(r'\s','',name) in title_compact]
    title=titles[0] if len(titles)==1 else ''
    mapped=MASTHEADS.get(title)
    registered=next((o for o in orgs if mapped and normalized_issuer(o)==normalized_issuer(mapped)),None)
    if registered:
        if not pubs: pubs=[registered]
        elif registered not in pubs: pubs=[]
    # A short slogan or a branch name is not sufficient evidence for a title.
    # Unknown mastheads stay blank for manual entry.
    tags=[t for t in ['임단협','성과금','주휴수당','노사협의회','안전','복지','교대','인력','투자'] if t in text]
    date=''
    date_source=head+'\n'+'\n'.join(text.splitlines()[:14])
    match=re.search(r'(20\d{2}|\d{2})\s*[.년/-]\s*(\d{1,2})\s*[.월/-]\s*(\d{1,2})',date_source)
    if match:
        y,m,d=map(int,match.groups()); y=y+2000 if y<100 else y
        try: date=datetime.date(y,m,d).isoformat()
        except ValueError: pass
    issue_match=re.search(r'(?:제\s*)?\d{2}\s*[-–]\s*\d{1,3}(?:\s*[-–]\s*\d{1,3})?\s*호',date_source)
    kind='성명서' if '성명서' in title else '교섭소식' if '교섭소식' in re.sub(r'\s+','',title) else '홍보물'
    return dict(classification_reason=('제목과 등록된 발행처 연결' if registered and pubs else '상단·하단 발행처 표기 확인' if pubs else '발행처 근거 부족 · 관리자 선택'),publishers=pubs,tags=tags,title=title,date=date,issue=issue_match.group(0) if issue_match else '',kind=kind,note='',state='draft')
@app.get('/api/settings')
@protected()
def settings():
    with db() as c: orgs=json.loads(c.execute("SELECT value FROM settings WHERE key='organizations'").fetchone()[0])
    return jsonify(organizations=orgs)
@app.post('/api/settings')
@protected(True)
def set_settings():
    orgs=request.json.get('organizations')
    if not isinstance(orgs,list) or len(orgs)>300 or any(not isinstance(o,str) or len(o)>100 for o in orgs): abort(400)
    with db() as c: c.execute("UPDATE settings SET value=? WHERE key='organizations'",(json.dumps(orgs,ensure_ascii=False),)); log(c,'조직 명부 변경')
    return jsonify(ok=True)
@app.post('/api/upload')
@protected(True)
def upload():
    files=request.files.getlist('files')
    if not files or len(files)>20: abort(400)
    entries=[]; seen=set()
    for f in files:
        raw=f.read()
        if len(raw)>15*1024*1024: abort(413)
        digest=hashlib.sha256(raw).hexdigest()
        if digest in seen: return jsonify(error='선택한 파일 안에 같은 이미지가 있습니다.'),409
        seen.add(digest)
        try:
            im=Image.open(io.BytesIO(raw)); fmt=im.format
            if fmt not in ('JPEG','PNG','WEBP') or im.width*im.height>40000000: abort(400)
            im.verify()
        except (UnidentifiedImageError,OSError,Image.DecompressionBombError): abort(400)
        entries.append((raw,digest,{'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt]))
    with db() as c:
        for _,digest,_ in entries:
            row=c.execute('SELECT doc FROM pages WHERE hash=? UNION ALL SELECT batch FROM batch_pages WHERE hash=? UNION ALL SELECT NULL FROM file_imports WHERE hash=?',(digest,digest,digest)).fetchone()
            if row: return jsonify(error='이미 등록한 원본입니다. 기존 자료를 확인하세요.',document_id=row[0]),409
    did=secrets.token_hex(12); stored=[]; created=[]; reports=[]
    try:
        for n,(raw,digest,ext) in enumerate(entries):
            pid=secrets.token_hex(12); path=DATA/'images'/(pid+ext); path.write_bytes(raw); created.append(path)
            result=recognize_body(path);text=result['variants'][result['selected']]['text'] if result['variants'] else '';status=result['status'];stored.append((pid,did,path.name,digest,text,status,n));reports.append((pid,result))
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            for entry in entries:
                if c.execute('SELECT 1 FROM file_imports WHERE hash=?',(entry[1],)).fetchone():abort(409)
            orgs=json.loads(c.execute("SELECT value FROM settings WHERE key='organizations'").fetchone()[0]); meta=suggest('\n'.join(p[4] for p in stored),orgs,reports[0][1].get('regions',{}))
            meta['title']=meta['title'] or '제목 확인 필요'; c.execute('INSERT INTO documents VALUES(?,?,?,?,1)',(did,json.dumps(meta,ensure_ascii=False),stamp(),stamp()))
            c.executemany('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',stored)
            c.executemany('INSERT OR IGNORE INTO file_imports VALUES(?,?)',[(p[3],stamp()) for p in stored])
            for pid,result in reports:
                c.execute('INSERT INTO page_original VALUES(?,?,?)',(pid,result['raw'],'업로드 최초 OCR'))
                c.execute('INSERT INTO ocr_runs VALUES(?,?,?,?,?)',(secrets.token_hex(12),pid,1,json.dumps(result,ensure_ascii=False),stamp()))
            log(c,'이미지 업로드',did)
    except sqlite3.IntegrityError:
        for p in created: p.unlink(missing_ok=True)
        abort(409)
    except Exception:
        for p in created: p.unlink(missing_ok=True)
        raise
    return jsonify(id=did)

CATEGORIES=('회사','집행부','제조직','계열사','그룹사','기타')
def categories_for(d):
    if d.get('category') in CATEGORIES: return [d['category']]
    result=[]
    for pub in d.get('publishers',[]):
        name=re.sub(r'\s','',pub)
        if re.search(r'(?i)(?<![A-Z])(?:ITC|IMC|ISC)(?![A-Z])|비지회',name):
            category='계열사'
        elif any(company in name for company in ('현대자동차','현대차','기아','모비스','위아','트랜시스','로템','케피코')):
            category='그룹사'
        elif '현대제철' in name and ('지회' in name or '지부' in name or '노동조합' in name): category='집행부'
        elif name=='단하나' or (name.endswith('회') and not name.endswith(('지회','협의회','위원회'))): category='제조직'
        else: category='기타'
        if category not in result: result.append(category)
    return result or ['기타']

def document(c,r,pages=None):
    d=dict(r); d.update(json.loads(d.pop('meta'))); d['pages']=pages if pages is not None else [dict(p) for p in c.execute('SELECT id,text,status,position FROM pages WHERE doc=? ORDER BY position',(d['id'],))]
    for key in ('company','site','period'): d.pop(key,None)
    d['categories']=categories_for(d)
    return d
@app.get('/api/documents')
@protected()
def documents():
    with db() as c:
        role=current_role()
        page_map={}
        for p in c.execute('SELECT doc,id,text,status,position FROM pages ORDER BY doc,position'):
            page=dict(p);doc=page.pop('doc');page_map.setdefault(doc,[]).append(page)
        ds=[document(c,r,page_map.get(r['id'],[])) for r in c.execute('SELECT * FROM documents ORDER BY created DESC')]
    visible=[d for d in ds if role=='admin' or d['state']=='published']
    if role!='admin':
        for d in visible: d.pop('note',None)
    return jsonify(visible)
@app.get('/api/image/<pid>')
@protected()
def image_file(pid):
    with db() as c:
        r=c.execute('SELECT p.path,d.meta FROM pages p JOIN documents d ON d.id=p.doc WHERE p.id=?',(pid,)).fetchone()
        role=current_role()
    if not r or (json.loads(r['meta'])['state']!='published' and role!='admin'): abort(404)
    return send_file(DATA/'images'/r['path'],as_attachment=request.args.get('download')=='1')
@app.get('/api/thumbnail/<pid>')
@protected()
def thumbnail_file(pid):
    with db() as c:
        r=c.execute('SELECT p.path,p.hash,d.meta FROM pages p JOIN documents d ON d.id=p.doc WHERE p.id=?',(pid,)).fetchone()
    if not r or (json.loads(r['meta'])['state']!='published' and current_role()!='admin'):abort(404)
    size=request.args.get('size','small')
    if size not in ('small','card'):abort(400)
    folder=DATA/'thumbnails';folder.mkdir(exist_ok=True)
    digest=hashlib.sha256(str(r['hash']).encode()).hexdigest()
    target=folder/(digest+'-'+size+'-v1.jpg')
    if not target.is_file():
        source=DATA/'images'/r['path']
        if not source.is_file():abort(404)
        temporary=None
        try:
            with Image.open(source) as original:
                im=ImageOps.exif_transpose(original).convert('RGB')
                im.thumbnail((120,160) if size=='small' else (480,680))
                with tempfile.NamedTemporaryFile(dir=folder,suffix='.jpg',delete=False) as out:
                    temporary=Path(out.name)
                    im.save(out,format='JPEG',quality=82,optimize=True)
                im.close()
            os.replace(temporary,target)
        except (OSError,ValueError):abort(400)
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
    return send_file(target,mimetype='image/jpeg')

FIELDS=['title','date','issue','kind','note','state','category']
@app.post('/api/documents/<did>/title')
@protected(True)
def edit_document_title(did):
    b=request.get_json(silent=True)
    if not isinstance(b,dict) or not isinstance(b.get('title'),str) or not b['title'].strip() or len(b['title'])>5000 or type(b.get('version')) is not int:abort(400)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT meta,version FROM documents WHERE id=?',(did,)).fetchone()
        if not row:abort(404)
        if row['version']!=b['version']:abort(409)
        meta=json.loads(row['meta']);meta['title']=b['title'].strip()
        c.execute('UPDATE documents SET meta=?,updated=?,version=version+1 WHERE id=?',(json.dumps(meta,ensure_ascii=False),stamp(),did))
        log(c,'제목 수정',did)
    return jsonify(ok=True)

@app.post('/api/documents/<did>')
@protected(True)
def edit(did):
    b=request.json
    if not isinstance(b,dict): abort(400)
    for name in ('texts','ocr_runs'):
        if not isinstance(b.get(name,{}),dict) or any(not isinstance(v,str) for v in b.get(name,{}).values()): abort(400)
    if any(not isinstance(b.get(k,''),str) or len(b.get(k,''))>5000 for k in FIELDS): abort(400)
    if b.get('state') not in ('draft','published') or not b.get('title','').strip(): abort(400)
    for k in ('publishers','tags'):
        if not isinstance(b.get(k),list) or any(not isinstance(s,str) or len(s)>100 for s in b[k]): abort(400)
    if b.get('category','') not in ('',)+CATEGORIES: abort(400)
    if b.get('kind') not in ('홍보물','교섭소식','성명서','담화문'): abort(400)
    if b.get('date'):
        try: datetime.date.fromisoformat(b['date'])
        except ValueError: abort(400)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone()
        if not r: abort(404)
        if r['version']!=b.get('version'): abort(409)
        ps=c.execute('SELECT id FROM pages WHERE doc=?',(did,)).fetchall(); ids=[p[0] for p in ps]
        order=b.get('order',ids)
        if not isinstance(order,list) or any(not isinstance(p,str) for p in order): abort(400)
        if sorted(order)!=sorted(ids): abort(400)
        meta=json.loads(r['meta']); meta.update({k:b.get(k,'') for k in FIELDS}); meta.update(publishers=b['publishers'],tags=b['tags'])
        c.execute('UPDATE documents SET meta=?,updated=?,version=version+1 WHERE id=?',(json.dumps(meta,ensure_ascii=False),stamp(),did))
        for n,pid in enumerate(order): c.execute('UPDATE pages SET position=? WHERE id=?',(n,pid))
        for pid,txt in b.get('texts',{}).items():
            if pid not in ids or not isinstance(txt,str) or len(txt)>100000: abort(400)
            old_text=c.execute('SELECT text FROM pages WHERE id=?',(pid,)).fetchone()[0]
            c.execute('INSERT OR IGNORE INTO page_original VALUES(?,?,?)',(pid,old_text,'최초 보존한 본문'))
            run_id=b.get('ocr_runs',{}).get(pid)
            if run_id:
                run=c.execute('SELECT version FROM ocr_runs WHERE id=? AND page=?',(run_id,pid)).fetchone()
                if not run or run['version']!=b['version']: abort(409)
            if old_text!=txt:
                c.execute('INSERT INTO text_history(page,text,created) VALUES(?,?,?)',(pid,old_text,stamp()))
            c.execute('UPDATE pages SET text=? WHERE id=?',(txt,pid))
        log(c,'분류·본문 수정 및 '+('게시' if meta['state']=='published' else '임시저장'),did)
    return jsonify(ok=True)
@app.route('/api/pages/<pid>/ocr',methods=['GET','POST'])
@protected(True)
def page_ocr(pid):
    with db() as c:
        row=c.execute('SELECT p.*,d.version FROM pages p JOIN documents d ON p.doc=d.id WHERE p.id=?',(pid,)).fetchone()
        if not row: abort(404)
        original=c.execute('SELECT text,source FROM page_original WHERE page=?',(pid,)).fetchone()
        history=[dict(r) for r in c.execute('SELECT text,created FROM text_history WHERE page=? ORDER BY id DESC LIMIT 5',(pid,))]
        if request.method=='GET':
            run=c.execute('SELECT id,result FROM ocr_runs WHERE page=? ORDER BY rowid DESC LIMIT 1',(pid,)).fetchone()
            return jsonify(run_id=run['id'] if run else '',result=json.loads(run['result']) if run else None,
                           original=dict(original) if original else {'text':row['text'],'source':'기존 본문'},history=history,version=row['version'])
    b=request.get_json() or {}
    if b.get('version')!=row['version']: abort(409)
    if b.get('layout','auto') not in ('auto','columns'): abort(400)
    result=recognize_body(DATA/'images'/row['path'],b.get('layout','auto'))
    with db() as c:
        current=c.execute('SELECT d.version FROM documents d JOIN pages p ON p.doc=d.id WHERE p.id=?',(pid,)).fetchone()
        if not current or current['version']!=row['version']: abort(409)
        run_id=secrets.token_hex(12)
        c.execute('INSERT INTO ocr_runs VALUES(?,?,?,?,?)',(run_id,pid,row['version'],json.dumps(result,ensure_ascii=False),stamp()))
        log(c,'본문 재인식 미리보기',row['doc'])
    return jsonify(run_id=run_id,result=result,version=row['version'])

@app.get('/api/ocr-runs/<rid>/crop/<int:variant>/<int:word>')
@protected(True)
def ocr_crop(rid,variant,word):
    with db() as c:
        r=c.execute('SELECT o.result,p.path FROM ocr_runs o JOIN pages p ON p.id=o.page WHERE o.id=?',(rid,)).fetchone()
    if not r: abort(404)
    try: box=json.loads(r['result'])['variants'][variant]['warnings'][word]['box']
    except (IndexError,KeyError,TypeError): abort(404)
    with Image.open(DATA/'images'/r['path']) as source:
        im=ImageOps.exif_transpose(source).convert('RGB');w,h=im.size;x,y,bw,bh=box
        crop=im.crop((max(0,int(x*w)-35),max(0,int(y*h)-20),min(w,int((x+bw)*w)+35),min(h,int((y+bh)*h)+20)))
        crop.thumbnail((1000,500));out=io.BytesIO();crop.save(out,format='PNG');out.seek(0)
    return send_file(out,mimetype='image/png')

@app.post('/api/documents/<did>/recognize')
@protected(True)
def recognize(did):
    with db() as c:
        rows=c.execute('SELECT id,path,text FROM pages WHERE doc=? ORDER BY position',(did,)).fetchall()
        if not rows: abort(404)
        orgs=json.loads(c.execute("SELECT value FROM settings WHERE key='organizations'").fetchone()[0])
        run=c.execute('SELECT result FROM ocr_runs WHERE page=? ORDER BY rowid DESC LIMIT 1',(rows[0]['id'],)).fetchone()
    regions=json.loads(run[0]).get('regions',{}) if run else header_ocr(DATA/'images'/rows[0]['path'])
    result=suggest('\n'.join(r['text'] for r in rows),orgs,regions)
    # Preview only: this never overwrites saved metadata or publication state.
    return jsonify(title=result['title'],publishers=result['publishers'],reason=result['classification_reason'])

@app.post('/api/documents/<did>/split')
@protected(True)
def split(did):
    selected=request.json.get('pages',[])
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone()
        if not r: abort(404)
        ids=[p[0] for p in c.execute('SELECT id FROM pages WHERE doc=?',(did,))]
        if not selected or len(set(selected))!=len(selected) or not set(selected)<set(ids): abort(400)
        nid=secrets.token_hex(12); m=json.loads(r['meta']);m['state']='draft';m['title']+=' (분리)'
        c.execute('INSERT INTO documents VALUES(?,?,?,?,1)',(nid,json.dumps(m,ensure_ascii=False),stamp(),stamp()))
        for n,pid in enumerate(selected): c.execute('UPDATE pages SET doc=?,position=? WHERE id=?',(nid,n,pid))
        c.execute('UPDATE documents SET version=version+1,updated=? WHERE id=?',(stamp(),did));log(c,'페이지 분리',did)
    return jsonify(id=nid)
@app.post('/api/documents/<did>/merge')
@protected(True)
def merge(did):
    source=request.json.get('source')
    if source==did: abort(400)
    with db() as c:
        if c.execute('SELECT count(*) FROM documents WHERE id IN (?,?)',(did,source)).fetchone()[0]!=2: abort(404)
        n=c.execute('SELECT count(*) FROM pages WHERE doc=?',(did,)).fetchone()[0]
        for i,p in enumerate(c.execute('SELECT id FROM pages WHERE doc=? ORDER BY position',(source,)).fetchall()): c.execute('UPDATE pages SET doc=?,position=? WHERE id=?',(did,n+i,p[0]))
        m=json.loads(c.execute('SELECT meta FROM documents WHERE id=?',(did,)).fetchone()[0]);m['state']='draft'
        c.execute('DELETE FROM documents WHERE id=?',(source,));c.execute('UPDATE documents SET meta=?,version=version+1,updated=? WHERE id=?',(json.dumps(m,ensure_ascii=False),stamp(),did));log(c,'자료 병합: '+source,did)
    return jsonify(ok=True)
@app.post('/api/documents/<did>/delete')
@protected(True)
def delete(did):
    with db() as c:
        paths=[p[0] for p in c.execute('SELECT path FROM pages WHERE doc=?',(did,))]
        c.execute('DELETE FROM documents WHERE id=?',(did,));log(c,'자료 삭제',did)
    for p in paths: (DATA/'images'/p).unlink(missing_ok=True)
    return jsonify(ok=True)
@app.get('/api/audit')
@protected(True)
def audit():
    with db() as c: return jsonify([dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200')])

import batches
import sys
start_batches,process_batch = batches.install(sys.modules[__name__])
import steel_press
steel_press.install(sys.modules[__name__])
import news
news.install(sys.modules[__name__])
import memos
memos.install(sys.modules[__name__])
import financials
financials.install(sys.modules[__name__])
import folder_import
start_folder_import=folder_import.install(sys.modules[__name__])
import schedule
start_schedule=schedule.install(sys.modules[__name__])
import schedule_intake
schedule_intake.install(sys.modules[__name__])
import precision
precision.install(sys.modules[__name__])
import auto_sync
start_auto_sync=auto_sync.install(sys.modules[__name__])

def main():
    import argparse,getpass
    p=argparse.ArgumentParser();p.add_argument('--user');p.add_argument('--role',choices=['admin','viewer'],default='viewer');p.add_argument('--startup-sync',action='store_true');p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8080);a=p.parse_args()
    if a.user:
        pw=getpass.getpass('Password (12+ characters): ')
        if len(pw)<12: raise SystemExit('Password must be 12+ characters')
        if pw!=getpass.getpass('Confirm password: '): raise SystemExit('Passwords differ')
        with db() as c: c.execute('INSERT OR REPLACE INTO users VALUES(?,?,?)',(a.user,generate_password_hash(pw),a.role))
        print('Account saved');return
    with db() as c:
        if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone(): raise SystemExit('Create admin first: python app.py --user admin --role admin')
    # Only one server may own this data directory and its durable OCR queue.
    server_lock=open(DATA/'server.lock','a+b')
    try:
        if os.name=='nt':
            import msvcrt
            server_lock.seek(0);server_lock.write(b'0');server_lock.flush();server_lock.seek(0)
            msvcrt.locking(server_lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(server_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:raise SystemExit('Archive is already running with this data folder. Close the other server first.')
    from waitress import create_server
    server=create_server(app,host=a.host,port=a.port,threads=6,max_request_body_size=65*1024*1024)
    start_batches()
    start_folder_import()
    start_schedule()
    if a.startup_sync:start_auto_sync()
    print(f'Archive: http://{a.host}:{a.port}');server.run()
if __name__=='__main__': main()
