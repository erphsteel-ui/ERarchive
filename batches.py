"""Durable single-consumer upload queue; publications are created only after review."""
import hashlib,io,json,re,secrets,threading,time,datetime
from pathlib import Path
from PIL import Image,UnidentifiedImageError
from flask import request,jsonify,abort,send_file,session
_WAKE=threading.Event()
_THREAD=None

def group_pages(items,mode):
    from visual_grouping import similarity
    groups=[]
    def family(name):return re.sub(r'_\d{1,3}$','',Path(name).stem)
    for item in items:
        meta=item['meta'];matches=[]
        for g in groups:
            other=g['meta']
            conflict=any(meta.get(k) and other.get(k) and meta[k]!=other[k] for k in ('publishers','title','date','issue'))
            strong=meta.get('publishers') and meta.get('issue') and meta['publishers']==other.get('publishers') and meta['issue']==other.get('issue')
            filename=family(item['name'])==family(g['names'][0])
            score=similarity(item.get('visual'),g['visual'])
            # Visual-only grouping requires a distinctive header; conflicts always veto it.
            visual=score>=.90
            if mode=='single':matches.append((4,1,g,'관리자가 한 홍보물로 지정'))
            elif not conflict:
                if strong:matches.append((3,1,g,'발행처·호수 일치 · 묶음 확인 필요'))
                elif filename:matches.append((2,1,g,'파일명 연속 · 묶음 확인 필요'))
                elif visual:matches.append((1,score,g,'상단 색상·배치 유사 · 묶음 확인 필요'))
        matches.sort(key=lambda x:(x[0],x[1]),reverse=True)
        # Two similarly plausible visual groups stay separate for administrator review.
        ambiguous=len(matches)>1 and matches[0][0]==matches[1][0]==1 and matches[0][1]-matches[1][1]<.03
        if matches and not ambiguous:
            _,_,target,reason=matches[0];target['reason']=reason
        else:
            target={'pages':[],'meta':dict(meta),'names':[],'visual':item.get('visual'),'reason':'여러 묶음과 상단 유사 · 개별 확인 필요' if ambiguous else '근거 부족 · 개별 확인 필요'};groups.append(target)
        target['pages'].append(item['id']);target['names'].append(item['name'])
        for k in ('publishers','title','date','issue'):
            if not target['meta'].get(k) and meta.get(k):target['meta'][k]=meta[k]
    for g in groups:g.pop('names',None);g.pop('visual',None)
    return groups

def install(a):
    app,db,DATA=a.app,a.db,a.DATA
    with db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY,state TEXT,mode TEXT,created TEXT,actor TEXT,groups_json TEXT DEFAULT '[]',version INTEGER DEFAULT 1,documents_json TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS file_imports(hash TEXT PRIMARY KEY,created TEXT);
CREATE TABLE IF NOT EXISTS batch_pages(id TEXT PRIMARY KEY,batch TEXT REFERENCES batches(id) ON DELETE CASCADE,name TEXT,path TEXT,hash TEXT UNIQUE,position INTEGER,state TEXT DEFAULT 'queued',result TEXT DEFAULT '{}',meta TEXT DEFAULT '{}',elapsed REAL DEFAULT 0);
INSERT OR IGNORE INTO file_imports SELECT hash,datetime('now') FROM pages;
INSERT OR IGNORE INTO file_imports SELECT hash,datetime('now') FROM batch_pages;''')
    def fetch(bid):
        with db() as c:
            row=c.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone()
            if not row:abort(404)
            b=dict(row);b['groups']=json.loads(b.pop('groups_json'));b['documents']=json.loads(b.pop('documents_json'))
            b['pages']=[]
            for row in c.execute('SELECT * FROM batch_pages WHERE batch=? ORDER BY position',(bid,)):
                p=dict(row);r=json.loads(p.pop('result'));p.pop('hash');p.pop('path');p['meta']=json.loads(p['meta']);p['text']=r.get('variants',[{}])[r.get('selected',0)].get('text','') if r.get('variants') else '';p['status']=r.get('status','대기 중');b['pages'].append(p)
            return b
    @app.get('/api/batches')
    @a.protected(True)
    def listing():
        with db() as c:
            rows=[dict(r) for r in c.execute("SELECT b.id,b.state,b.created,count(p.id) total,sum(p.state IN ('done','failed')) done,sum(p.state='failed') failed FROM batches b LEFT JOIN batch_pages p ON p.batch=b.id GROUP BY b.id ORDER BY b.created DESC LIMIT 100")]
        return jsonify(rows)
    @app.get('/api/batches/<bid>')
    @a.protected(True)
    def detail(bid):return jsonify(fetch(bid))
    @app.get('/api/batch-image/<pid>')
    @a.protected(True)
    def image(pid):
        with db() as c:r=c.execute('SELECT path FROM batch_pages WHERE id=?',(pid,)).fetchone()
        if not r:abort(404)
        return send_file(DATA/'images'/r[0])
    @app.post('/api/batches',endpoint='batch_upload')
    @a.protected(True)
    def upload():
        files=request.files.getlist('files');mode=request.form.get('mode','auto')
        if not files or len(files)>20 or mode not in ('auto','single'):abort(400)
        entries=[];seen=set();total=0
        for f in files:
            raw=f.read();total+=len(raw)
            if len(raw)>15*1024*1024 or total>60*1024*1024:abort(413)
            digest=hashlib.sha256(raw).hexdigest()
            if digest in seen:abort(409)
            seen.add(digest)
            try:
                im=Image.open(io.BytesIO(raw));fmt=im.format
                if fmt not in ('JPEG','PNG','WEBP') or im.width*im.height>40000000:abort(400)
                im.verify()
            except (UnidentifiedImageError,OSError,Image.DecompressionBombError):abort(400)
            entries.append((raw,digest,{'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[fmt],str(f.filename)[:255]))
        bid=secrets.token_hex(12);created=[]
        try:
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                for _,digest,_,_ in entries:
                    if c.execute('SELECT 1 FROM pages WHERE hash=? UNION ALL SELECT 1 FROM batch_pages WHERE hash=? UNION ALL SELECT 1 FROM file_imports WHERE hash=?',(digest,digest,digest)).fetchone():abort(409)
                c.execute('INSERT INTO batches(id,state,mode,created,actor) VALUES(?,?,?,?,?)',(bid,'queued',mode,a.stamp(),session['user']))
                for n,(raw,digest,ext,name) in enumerate(entries):
                    pid=secrets.token_hex(12);path=DATA/'images'/(pid+ext);path.write_bytes(raw);created.append(path)
                    c.execute('INSERT INTO batch_pages(id,batch,name,path,hash,position) VALUES(?,?,?,?,?,?)',(pid,bid,name,path.name,digest,n))
                    c.execute('INSERT OR IGNORE INTO file_imports VALUES(?,?)',(digest,a.stamp()))
                a.log(c,'일괄 업로드 대기열 등록',bid)
        except BaseException:
            for p in created:p.unlink(missing_ok=True)
            raise
        _WAKE.set();return jsonify(id=bid),202
    @app.post('/api/batches/<bid>/retry')
    @a.protected(True)
    def retry(bid):
        with db() as c:
            c.execute('BEGIN IMMEDIATE');b=c.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone()
            if not b:abort(404)
            if b['state']!='review' or b['version']!=request.json.get('version'):abort(409)
            c.execute("UPDATE batch_pages SET state='queued' WHERE batch=? AND state='failed'",(bid,))
            c.execute("UPDATE batches SET state='queued',version=version+1 WHERE id=?",(bid,))
        _WAKE.set();return jsonify(ok=True)
    @app.post('/api/batches/<bid>/regroup')
    @a.protected(True)
    def regroup(bid):
        from visual_grouping import header_signature
        body=request.get_json() or {}
        with db() as c:
            b=c.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone()
            if not b:abort(404)
            if b['state']!='review' or b['version']!=body.get('version'):abort(409)
            items=[dict(p) for p in c.execute('SELECT id,name,meta,path FROM batch_pages WHERE batch=? ORDER BY position',(bid,))]
        for item in items:
            item['meta']=json.loads(item['meta']);item['visual']=header_signature(DATA/'images'/item.pop('path'))
        groups=group_pages(items,b['mode'])
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            changed=c.execute("UPDATE batches SET groups_json=?,version=version+1 WHERE id=? AND version=? AND state='review'",(json.dumps(groups,ensure_ascii=False),bid,b['version'])).rowcount
            if not changed:abort(409)
            a.log(c,'상단 디자인 포함 묶음 다시 제안',bid)
        return jsonify(ok=True)
    @app.post('/api/batches/<bid>/save')
    @a.protected(True)
    def save(bid):
        body=request.get_json();groups=body.get('groups');action=body.get('action','review')
        if action not in ('review','draft','published') or not isinstance(groups,list) or not groups or len(groups)>20:abort(400)
        with db() as c:
            c.execute('BEGIN IMMEDIATE');b=c.execute('SELECT * FROM batches WHERE id=?',(bid,)).fetchone()
            if not b:abort(404)
            if b['state']=='saved':return jsonify(documents=json.loads(b['documents_json']),saved=True)
            if b['state']!='review' or b['version']!=body.get('version'):abort(409)
            pages={p['id']:dict(p) for p in c.execute('SELECT * FROM batch_pages WHERE batch=?',(bid,))}
            order=[]
            for g in groups:
                if not isinstance(g,dict) or not isinstance(g.get('pages'),list) or not g['pages'] or not isinstance(g.get('meta'),dict):abort(400)
                if any(not isinstance(pid,str) for pid in g['pages']):abort(400)
                order.extend(g['pages']);m=g['meta']
                excluded=g.get('excluded',[])
                if not isinstance(excluded,list) or any(not isinstance(pid,str) for pid in excluded) or len(set(excluded))!=len(excluded) or any(pid not in g['pages'] for pid in excluded):abort(400)
                for k in ('title','date','issue','kind','category','note'):
                    if not isinstance(m.get(k,''),str) or len(m.get(k,''))>5000:abort(400)
                if m.get('kind') not in ('홍보물','교섭소식','성명서','담화문') or m.get('category','') not in ('',)+a.CATEGORIES:abort(400)
                if not isinstance(m.get('publishers'),list) or len(m['publishers'])>100 or any(not isinstance(x,str) or len(x)>100 for x in m['publishers']):abort(400)
                if m.get('date'):
                    try:datetime.date.fromisoformat(m['date'])
                    except ValueError:abort(400)
            if sorted(order)!=sorted(pages):return jsonify(error='모든 페이지를 빠짐없이 한 묶음에만 넣어 주세요.'),400
            if action=='published' and not body.get('confirmed'):return jsonify(error='페이지 묶음과 인식 결과 확인에 체크해 주세요.'),400
            if action!='review':
                ids=[]
                for g in groups:
                    included=[pid for pid in g['pages'] if pid not in g.get('excluded',[])]
                    if not included:continue
                    did=secrets.token_hex(12);ids.append(did);m={k:g['meta'].get(k,'') for k in a.FIELDS};m.update(publishers=g['meta']['publishers'],tags=[],state=action,title=g['meta'].get('title','').strip() or '제목 미상')
                    c.execute('INSERT INTO documents VALUES(?,?,?,?,1)',(did,json.dumps(m,ensure_ascii=False),a.stamp(),a.stamp()))
                    for n,pid in enumerate(included):
                        p=pages[pid];r=json.loads(p['result']);txt=r['variants'][r.get('selected',0)]['text'] if r.get('variants') else ''
                        c.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',(pid,did,p['path'],p['hash'],txt,r.get('status',''),n))
                        c.execute('INSERT INTO page_original VALUES(?,?,?)',(pid,r.get('raw',''),'일괄 업로드 최초 OCR'))
                        c.execute('INSERT INTO ocr_runs VALUES(?,?,?,?,?)',(secrets.token_hex(12),pid,1,p['result'],a.stamp()))
                    a.log(c,'일괄 검토 후 '+action,did)
                c.execute("UPDATE batches SET state='saved',documents_json=? WHERE id=?",(json.dumps(ids),bid))
                # Final publications now own files and hash reservations.
                c.execute('DELETE FROM batch_pages WHERE batch=?',(bid,))
            c.execute('UPDATE batches SET groups_json=?,version=version+1 WHERE id=?',(json.dumps(groups,ensure_ascii=False),bid))
        return jsonify(ok=True,version=b['version']+1,saved=action!='review')
    def process_one():
        with db() as c:
            c.execute('BEGIN IMMEDIATE');b=c.execute("SELECT * FROM batches WHERE state IN ('queued','processing') ORDER BY created LIMIT 1").fetchone()
            if not b:return False
            c.execute("UPDATE batches SET state='processing' WHERE id=?",(b['id'],))
            p=c.execute("SELECT * FROM batch_pages WHERE batch=? AND state='queued' ORDER BY position LIMIT 1",(b['id'],)).fetchone()
            if p:c.execute("UPDATE batch_pages SET state='running' WHERE id=?",(p['id'],))
        if p:
            begin=time.monotonic()
            try:r=a.recognize_body(DATA/'images'/p['path'])
            except Exception as exc:r={'raw':'','variants':[],'regions':{},'status':'처리 실패 · '+str(exc)[:250]}
            with db() as c:
                orgs=json.loads(c.execute("SELECT value FROM settings WHERE key='organizations'").fetchone()[0]);m=a.suggest(r.get('raw',''),orgs,r.get('regions',{}))
                c.execute('UPDATE batch_pages SET state=?,result=?,meta=?,elapsed=? WHERE id=?',('done' if r.get('variants') else 'failed',json.dumps(r,ensure_ascii=False),json.dumps(m,ensure_ascii=False),round(time.monotonic()-begin,1),p['id']))
        with db() as c:
            if not c.execute("SELECT 1 FROM batch_pages WHERE batch=? AND state IN ('queued','running')",(b['id'],)).fetchone():
                items=[dict(p) for p in c.execute('SELECT id,name,meta,path FROM batch_pages WHERE batch=? ORDER BY position',(b['id'],))]
                from visual_grouping import header_signature
                for item in items:
                    item['meta']=json.loads(item['meta']);item['visual']=header_signature(DATA/'images'/item.pop('path'))
                groups=group_pages(items,b['mode'])
                c.execute("UPDATE batches SET state='review',groups_json=?,version=version+1 WHERE id=?",(json.dumps(groups,ensure_ascii=False),b['id']))
        return True
    def recover():
        if hasattr(a,'recover_schedule_jobs'):a.recover_schedule_jobs()
        if hasattr(a,'recover_precision_jobs'):a.recover_precision_jobs()
        with db() as c:
            c.execute("UPDATE batch_pages SET state='queued' WHERE state='running'")
            c.execute("UPDATE batches SET state='queued' WHERE state='processing'")
    a.recover_batches=recover
    def start():
        global _THREAD
        if _THREAD and _THREAD.is_alive():return
        recover()
        def loop():
            while True:
                try:
                    worked=process_one()
                    if hasattr(a,'process_schedule_job'):worked=a.process_schedule_job() or worked
                    if hasattr(a,'process_precision_job'):worked=a.process_precision_job() or worked
                    if worked:continue
                except Exception:app.logger.exception('Batch queue error')
                _WAKE.wait(3);_WAKE.clear()
        _THREAD=threading.Thread(target=loop,daemon=True,name='archive-queue');_THREAD.start()
    return start,process_one
