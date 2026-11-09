"""Local/shared folder polling; source files are never moved or deleted."""
import io,json,hashlib,secrets,threading,time,re
from pathlib import Path
from PIL import Image,UnidentifiedImageError,PngImagePlugin
from flask import jsonify,request,abort

class FolderImporter:
    def __init__(self,a):
        self.a=a;self.lock=threading.RLock();self.snapshot=None;self.handled=None;self.changed_at=0
        self.info={'message':'수집 준비 중','last_scan':'','imported':0,'duplicates':0,'errors':[]}
    def config(self):
        with self.a.db() as c:return json.loads(c.execute("SELECT value FROM settings WHERE key='inbox'").fetchone()[0])
    def import_pdf(self,raw,name,digest):
        """Render a stable PDF into a single durable review batch; preserve its source file."""
        try:import pymupdf
        except ImportError:raise ValueError('PDF 처리 패키지 PyMuPDF가 없습니다. requirements-pdf.txt를 설치하세요.')
        a=self.a
        with a.db() as c:
            if c.execute('SELECT 1 FROM file_imports WHERE hash=?',(digest,)).fetchone():return 0
        try:
            pdf=pymupdf.open(stream=raw,filetype='pdf')
            try:
                if pdf.needs_pass:raise ValueError('암호가 설정된 PDF는 지원하지 않습니다.')
                if not 1<=pdf.page_count<=20:raise ValueError('PDF는 1~20쪽까지 지원합니다.')
                prepared=[];total=0
                for n in range(pdf.page_count):
                    page=pdf.load_page(n);rect=page.rect;scale=1.5
                    if rect.width<=0 or rect.height<=0 or rect.width*rect.height*scale*scale>40000000:raise ValueError('PDF 페이지 크기가 너무 큽니다.')
                    rendered=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False).tobytes('png')
                    metadata=PngImagePlugin.PngInfo();metadata.add_text('ERArchivePDFPage',digest+':'+str(n))
                    with Image.open(io.BytesIO(rendered)) as picture:
                        output=io.BytesIO();picture.save(output,format='PNG',pnginfo=metadata);image=output.getvalue()
                    total+=len(image)
                    if len(image)>15*1024*1024 or total>60*1024*1024:raise ValueError('변환 이미지 용량이 제한을 초과했습니다.')
                    prepared.append((image,hashlib.sha256(image).hexdigest(),f'{name} · {n+1}쪽'))
            finally:pdf.close()
        except ValueError:raise
        except Exception as exc:raise ValueError('PDF를 읽거나 변환하지 못했습니다.') from exc
        created=[];imported=0
        try:
            with a.db() as c:
                c.execute('BEGIN IMMEDIATE')
                if c.execute('SELECT 1 FROM file_imports WHERE hash=?',(digest,)).fetchone():return 0
                fresh=[];seen=set()
                for raw_page,page_hash,page_name in prepared:
                    if page_hash in seen or c.execute('SELECT 1 FROM file_imports WHERE hash=? UNION ALL SELECT 1 FROM pages WHERE hash=? UNION ALL SELECT 1 FROM batch_pages WHERE hash=?',(page_hash,page_hash,page_hash)).fetchone():continue
                    seen.add(page_hash);fresh.append((raw_page,page_hash,page_name))
                if fresh:
                    bid=secrets.token_hex(12);c.execute('INSERT INTO batches(id,state,mode,created,actor) VALUES(?,?,?,?,?)',(bid,'queued','single',a.stamp(),'수집폴더 PDF'))
                    for n,(raw_page,page_hash,page_name) in enumerate(fresh):
                        pid=secrets.token_hex(12);dest=a.DATA/'images'/(pid+'.png');dest.write_bytes(raw_page);created.append(dest)
                        c.execute('INSERT INTO batch_pages(id,batch,name,path,hash,position) VALUES(?,?,?,?,?,?)',(pid,bid,page_name,dest.name,page_hash,n));c.execute('INSERT INTO file_imports VALUES(?,?)',(page_hash,a.stamp()))
                    c.execute('INSERT INTO audit(time,actor,action,doc) VALUES(?,?,?,?)',(a.stamp(),'수집폴더','PDF 자동 수집 '+str(len(fresh))+'쪽',bid));imported=len(fresh)
                c.execute('INSERT INTO file_imports VALUES(?,?)',(digest,a.stamp()))
        except BaseException:
            for path in created:path.unlink(missing_ok=True)
            raise
        return imported
    def scan(self,now=None):
        with self.lock:self._scan(time.monotonic() if now is None else now)
    def _scan(self,now):
        a=self.a;cfg=self.config();self.info['last_scan']=a.stamp()
        if not cfg['enabled']:self.info['message']='자동 수집 꺼짐';return
        folder=Path(cfg['path'])
        try:
            if not folder.is_dir():raise OSError('수집폴더에 연결할 수 없습니다. 경로와 접근 권한을 확인하세요.')
            entries=[]
            for p in folder.iterdir():
                if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.jpg','.jpeg','.png','.webp','.pdf'):
                    st=p.stat();entries.append((p,st.st_size,st.st_mtime_ns))
            entries.sort(key=lambda x:[int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)',x[0].name)])
            signature=(str(folder),tuple((str(p),size,mtime) for p,size,mtime in entries))
            if signature!=self.snapshot:
                self.snapshot=signature;self.changed_at=now;self.info['message']='파일 복사 완료 대기 중 (15초)';return
            if now-self.changed_at<15:return
            if signature==self.handled:self.info['message']='새 이미지 대기 중';return
            prepared=[];errors=[];duplicates=0;seen=set();prepared_size=0;deferred=False;pdf_imported=0
            with a.db() as c:known={r[0] for r in c.execute('SELECT hash FROM file_imports')}
            for p,size,mtime in entries:
                if size>15*1024*1024:errors.append(p.name+' · 15MB 초과');continue
                try:
                    with p.open('rb') as f:raw=f.read(15*1024*1024+1)
                    st=p.stat()
                    if (st.st_size,st.st_mtime_ns)!=(size,mtime) or len(raw)!=size:
                        self.snapshot=None;self.info['message']='파일 변경 감지 · 복사 완료를 다시 기다립니다.';return
                    digest=hashlib.sha256(raw).hexdigest()
                    if digest in known or digest in seen:duplicates+=1;continue
                    if p.suffix.lower()=='.pdf':
                        pdf_imported+=self.import_pdf(raw,p.name,digest);seen.add(digest);continue
                    if len(prepared)>=20 or prepared_size+len(raw)>60*1024*1024:
                        deferred=True;break
                    im=Image.open(io.BytesIO(raw));fmt=im.format
                    if fmt not in ('JPEG','PNG','WEBP') or im.width*im.height>40000000:raise ValueError('지원하지 않는 이미지 또는 해상도 초과')
                    im.verify();seen.add(digest)
                    prepared_size+=len(raw)
                    prepared.append((raw,digest,{'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt],p.name))
                except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError) as e:errors.append(p.name+' · '+str(e)[:160])
            # Recheck all source signatures immediately before committing the copied bytes.
            for p,size,mtime in entries:
                st=p.stat()
                if (st.st_size,st.st_mtime_ns)!=(size,mtime):self.snapshot=None;return
            chunks=[];chunk=[];bytes_count=0
            for entry in prepared:
                if chunk and (len(chunk)>=20 or bytes_count+len(entry[0])>60*1024*1024):chunks.append(chunk);chunk=[];bytes_count=0
                chunk.append(entry);bytes_count+=len(entry[0])
            if chunk:chunks.append(chunk)
            imported=pdf_imported
            for chunk in chunks:
                created=[]
                try:
                    with a.db() as c:
                        c.execute('BEGIN IMMEDIATE')
                        fresh=[]
                        for e in chunk:
                            if c.execute('SELECT 1 FROM file_imports WHERE hash=? UNION ALL SELECT 1 FROM pages WHERE hash=? UNION ALL SELECT 1 FROM batch_pages WHERE hash=?',(e[1],e[1],e[1])).fetchone():duplicates+=1
                            else:fresh.append(e)
                        if not fresh:continue
                        bid=secrets.token_hex(12)
                        c.execute('INSERT INTO batches(id,state,mode,created,actor) VALUES(?,?,?,?,?)',(bid,'queued','auto',a.stamp(),'수집폴더'))
                        for n,(raw,digest,ext,name) in enumerate(fresh):
                            pid=secrets.token_hex(12);dest=a.DATA/'images'/(pid+ext);dest.write_bytes(raw);created.append(dest)
                            c.execute('INSERT INTO batch_pages(id,batch,name,path,hash,position) VALUES(?,?,?,?,?,?)',(pid,bid,name,dest.name,digest,n))
                            c.execute('INSERT INTO file_imports VALUES(?,?)',(digest,a.stamp()))
                        c.execute('INSERT INTO audit(time,actor,action,doc) VALUES(?,?,?,?)',(a.stamp(),'수집폴더','자동 수집 '+str(len(fresh))+'장',bid))
                    imported+=len(fresh)
                except BaseException:
                    for p in created:p.unlink(missing_ok=True)
                    raise
            self.handled=None if deferred else signature;self.info.update(message='수집 완료 · 관리자 묶음 확인' if imported else '새 이미지 대기 중',imported=imported,duplicates=duplicates,errors=errors[:50])
            if imported:
                import batches
                batches._WAKE.set()
        except OSError as e:self.info['message']='수집 오류 · '+str(e)[:250]

def install(a):
    with a.db() as c:
        c.execute("INSERT OR IGNORE INTO settings VALUES('inbox',?)",(json.dumps({'enabled':True,'path':str(a.ROOT/'수집폴더')},ensure_ascii=False),))
    monitor=FolderImporter(a);a.folder_monitor=monitor
    @a.app.get('/api/inbox')
    @a.protected(True)
    def inbox_status():
        with monitor.lock:return jsonify(config=monitor.config(),status=monitor.info)
    @a.app.post('/api/inbox')
    @a.protected(True)
    def inbox_settings():
        body=request.get_json()
        if not isinstance(body,dict) or not isinstance(body.get('enabled'),bool) or not isinstance(body.get('path'),str):abort(400)
        path=Path(body['path']).expanduser()
        if not path.is_absolute() or not path.is_dir():return jsonify(error='서버 PC에서 접근 가능한 기존 폴더의 전체 경로를 입력하세요.'),400
        path=path.resolve();data=a.DATA.resolve()
        if path==data or data in path.parents:return jsonify(error='자료실 데이터 폴더를 수집폴더로 사용할 수 없습니다.'),400
        with a.db() as c:sc=c.execute("SELECT value FROM settings WHERE key='schedule_inbox'").fetchone()
        if sc and path==Path(json.loads(sc[0])['path']).resolve():return jsonify(error='일정자료 수집폴더와 홍보물 수집폴더는 서로 다른 경로여야 합니다.'),400
        with a.db() as c:pc=c.execute("SELECT value FROM settings WHERE key='precision_inbox'").fetchone()
        if pc and path==Path(json.loads(pc[0])['path']).resolve():return jsonify(error='정밀인식폴더와 다른 경로를 지정하세요.'),400
        with monitor.lock:
            with a.db() as c:
                c.execute("UPDATE settings SET value=? WHERE key='inbox'",(json.dumps({'enabled':body['enabled'],'path':str(path)},ensure_ascii=False),));a.log(c,'수집폴더 설정 변경')
            monitor.snapshot=None;monitor.handled=None;monitor.info['message']='설정 저장 · 다음 검사 대기 중'
        return jsonify(ok=True)
    def start():
        cfg=monitor.config()
        if cfg['path']==str(a.ROOT/'수집폴더'):
            try:Path(cfg['path']).mkdir(exist_ok=True)
            except OSError:pass
        def loop():
            while True:
                try:monitor.scan()
                except Exception:a.app.logger.exception('Folder import error');monitor.info['message']='자동 수집 오류 · 서버 실행 창을 확인하세요.'
                time.sleep(5)
        threading.Thread(target=loop,daemon=True,name='folder-import').start()
    return start
