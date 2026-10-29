"""Persistent local schedule candidates, approval, and HWP folder ingestion."""
import datetime as dt
import hashlib
import json
import re
import unicodedata
import secrets
import threading
import time
from pathlib import Path
from flask import request, jsonify, abort, send_file
from schedule_extract import hwp_text, extract_events, EXTRACTOR_VERSION

DEFAULT_ROWS=[{'id':str(i+1),'group':g,'name':n} for i,(g,n) in enumerate([
 ('당사','포항'),('당사','당진'),('당사','인천'),('당사','당냉'),('당사','순천'),
 ('그룹사','현대차'),('그룹사','기아차'),('계열사','ITC'),('계열사','비지회'),('계열사','IMC'),('계열사','ISC'),('노동계','금속노조'),('기타','기타')])]

def event_key(data):
    def norm(value):
        return re.sub(r'\s+', '', unicodedata.normalize('NFKC',value or '')).casefold()
    return (data.get('start',''),data.get('end',''),norm(data.get('title','')),norm(data.get('subject','')))

def install(a):
    with a.db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS schedule_sources(
            id TEXT PRIMARY KEY,name TEXT,kind TEXT,text TEXT,path TEXT,created TEXT,status TEXT);
        CREATE TABLE IF NOT EXISTS schedule_events(
            id TEXT PRIMARY KEY,source TEXT REFERENCES schedule_sources(id),fingerprint TEXT UNIQUE,
            data TEXT,state TEXT,version INTEGER DEFAULT 1,created TEXT,updated TEXT);
        CREATE TABLE IF NOT EXISTS schedule_seen(id TEXT PRIMARY KEY,signature TEXT);
        CREATE TABLE IF NOT EXISTS schedule_reviews(source TEXT PRIMARY KEY REFERENCES schedule_sources(id) ON DELETE CASCADE,signature TEXT,updated TEXT);
        CREATE INDEX IF NOT EXISTS idx_schedule_events_state ON schedule_events(state);
        CREATE INDEX IF NOT EXISTS idx_schedule_events_source ON schedule_events(source);
        ''')
        if 'reference' not in {r[1] for r in c.execute('PRAGMA table_info(schedule_sources)')}:
            c.execute("ALTER TABLE schedule_sources ADD COLUMN reference TEXT DEFAULT ''")
        c.execute("INSERT OR IGNORE INTO settings VALUES('schedule_rows',?)",(json.dumps(DEFAULT_ROWS,ensure_ascii=False),))
        saved_rows=json.loads(c.execute("SELECT value FROM settings WHERE key='schedule_rows'").fetchone()[0])
        changed_rows=False
        for group,name in [('당사','공통'),('당사','포항'),('당사','당진'),('당사','인천'),('그룹사','공통'),('계열사','공통'),('노동계','공통'),('기타','기타')]:
            if not any(r['group']==group and r['name']==name for r in saved_rows):
                saved_rows.append({'id':'calendar-'+secrets.token_hex(4),'group':group,'name':name});changed_rows=True
        if changed_rows:c.execute("UPDATE settings SET value=? WHERE key='schedule_rows'",(json.dumps(saved_rows,ensure_ascii=False),))
    (a.DATA/'schedule_sources').mkdir(exist_ok=True)
    lock=threading.RLock();wake=threading.Event();stable={}
    info={'message':'일정 수집 준비 중','last_scan':'','errors':[]}
    def rows(c):return json.loads(c.execute("SELECT value FROM settings WHERE key='schedule_rows'").fetchone()[0])
    def ingest(source_id,name,kind,text,path='',reference=''):
        reference=reference or ''
        if kind=='hwp' and path:
            with a.db() as c:prior=c.execute('SELECT signature FROM schedule_seen WHERE id=?',(source_id,)).fetchone()
            if prior and not prior[0].startswith(EXTRACTOR_VERSION+':'):
                original=a.DATA/'schedule_sources'/Path(path).name
                if not original.is_file():raise ValueError('보관 HWP 원본을 찾지 못했습니다. 기존 후보를 유지합니다.')
                text=hwp_text(original.read_bytes())
        signature=EXTRACTOR_VERSION+':'+hashlib.sha256((reference+'|'+text).encode()).hexdigest()
        with a.db() as c:
            old=c.execute('SELECT signature FROM schedule_seen WHERE id=?',(source_id,)).fetchone()
            if old and old[0]==signature:return 0
        proposals=extract_events(text,name,reference)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT signature FROM schedule_seen WHERE id=?',(source_id,)).fetchone()
            if old and old[0]==signature:return 0
            c.execute('INSERT INTO schedule_sources(id,name,kind,text,path,created,status,reference) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET text=excluded.text,status=excluded.status,reference=excluded.reference',
                      (source_id,name,kind,text,path,a.stamp(),f'일정 후보 {len(proposals)}건',reference))
            # Retire only untouched cross-source duplicates; human-reviewed records are preserved.
            active=[dict(r) for r in c.execute("SELECT * FROM schedule_events WHERE state IN ('pending','published','rejected') ORDER BY created,id")]
            def is_human(r):
                d=json.loads(r['data']);return bool(d.get('reviewed') or (r['version']>1 and not d.get('automatic')) or r['state'] in ('published','rejected'))
            active.sort(key=lambda r:not is_human(r))
            unique={}
            for r in active:
                k=event_key(json.loads(r['data']))
                first=unique.get(k)
                if first and first['source']!=r['source'] and r['state']=='pending' and not is_human(r):
                    c.execute("UPDATE schedule_events SET state='superseded',version=version+1,updated=? WHERE id=?",(a.stamp(),r['id']))
                else:unique.setdefault(k,r)
            # Keep all human decisions. Only untouched machine proposals are retired.
            existing=[dict(r) for r in c.execute('SELECT * FROM schedule_events WHERE source=?',(source_id,))]
            def human(r):
                d=json.loads(r['data']);return d.get('reviewed') or (r['version']>1 and not d.get('automatic')) or r['state'] in ('published','rejected')
            protected_dates={json.loads(r['data'])['start'] for r in existing if human(r)}
            for r in existing:
                if r['state']=='pending' and not human(r):
                    d=json.loads(r['data']);d['automatic']=True
                    c.execute("UPDATE schedule_events SET state='superseded',data=?,version=version+1,updated=? WHERE id=?",(json.dumps(d,ensure_ascii=False),a.stamp(),r['id']))
            count=0
            keys={event_key(json.loads(r['data'])) for r in c.execute("SELECT data FROM schedule_events WHERE (source IS NULL OR source!=?) AND state IN ('pending','published','rejected')",(source_id,))}
            row_list=rows(c)
            for p in proposals:
                if p['start'] in protected_dates or event_key(p) in keys:continue
                p['automatic']=True
                subject=p.get('subject','')
                hits=[r for r in row_list if subject and r['name']!='기타' and r['name'] in subject]
                # A generic metal-union publisher does not imply its own calendar row.
                if len(hits)==1:p['row']=hits[0]['id']

                # Edits/rejects are retained; re-scanning never resets decisions.
                fingerprint=hashlib.sha256((source_id+'|'+p['start']+'|'+p['end']+'|'+p['title']+'|'+p.get('subject','')).encode()).hexdigest()
                previous=c.execute('SELECT * FROM schedule_events WHERE fingerprint=?',(fingerprint,)).fetchone()
                if previous and previous['state']=='superseded' and not human(previous):
                    c.execute("UPDATE schedule_events SET data=?,state='pending',updated=? WHERE id=?",(json.dumps(p,ensure_ascii=False),a.stamp(),previous['id']));continue
                count+=c.execute('INSERT OR IGNORE INTO schedule_events VALUES(?,?,?,?,?,1,?,?)',
                    (secrets.token_hex(12),source_id,fingerprint,json.dumps(p,ensure_ascii=False),'pending',a.stamp(),a.stamp())).rowcount
            remaining=c.execute("SELECT COUNT(*) FROM schedule_events WHERE source=? AND state='pending'",(source_id,)).fetchone()[0]
            c.execute('UPDATE schedule_sources SET status=? WHERE id=?',(f'v{EXTRACTOR_VERSION} · 검토 후보 {remaining}건'+(' · 직접 처리한 날짜 보존' if protected_dates else ''),source_id))
            c.execute('INSERT OR REPLACE INTO schedule_seen VALUES(?,?)',(source_id,signature))
        return count
    def scan():
        if not lock.acquire(blocking=False):return
        try:
            if hasattr(a,'scan_schedule_inbox'):a.scan_schedule_inbox()
            if hasattr(a,'scan_precision_inbox'):a.scan_precision_inbox()
            errors=[];count=0
            # Already-recognized images: no additional OCR pass or model load.
            with a.db() as c:
                images=[dict(r) for r in c.execute('SELECT p.hash,p.text,p.path,d.meta FROM pages p JOIN documents d ON d.id=p.doc')]
                pending=[dict(r) for r in c.execute("SELECT hash,name,path,result,meta FROM batch_pages WHERE state='done'")]
                saved=[dict(r) for r in c.execute('SELECT * FROM schedule_sources')]
                cfg=json.loads(c.execute("SELECT value FROM settings WHERE key='inbox'").fetchone()[0])
            live={'image:'+p['hash'] for p in images+pending}
            for source in saved:
                if source['id'] not in live:
                    try:count+=ingest(source['id'],source['name'],source['kind'],source['text'],source['path'],source.get('reference',''))
                    except (OSError,ValueError) as exc:errors.append(source['name']+' · 재검사 실패: '+str(exc)[:160])
            for p in pending:
                r=json.loads(p['result']);variants=r.get('variants',[])
                p['text']=variants[r.get('selected',0)].get('text','') if variants else ''
                images.append(p)
            for p in images:
                meta=json.loads(p['meta']);name=p.get('name') or meta.get('title') or p['path']
                count+=ingest('image:'+p['hash'],name,'image',p['text'],reference=meta.get('date',''))
            if cfg['enabled']:
                folder=Path(cfg['path'])
                if not folder.is_dir():errors.append('HWP 수집폴더에 연결할 수 없습니다.')
                else:
                    current=set()
                    for p in folder.iterdir():
                        if p.suffix.lower()!='.hwp' or p.is_symlink() or not p.is_file():continue
                        current.add(str(p));st=p.stat();sig=(st.st_size,st.st_mtime_ns);prev=stable.get(str(p));now=time.monotonic()
                        if not prev or prev[0]!=sig:stable[str(p)]=(sig,now);continue
                        if now-prev[1]<15:continue
                        if st.st_size>15*1024*1024:errors.append(p.name+' · HWP 15MB 초과');continue
                        raw=p.read_bytes();after=p.stat()
                        if (after.st_size,after.st_mtime_ns)!=sig or len(raw)!=sig[0]:stable.pop(str(p),None);continue
                        digest=hashlib.sha256(raw).hexdigest();sid='hwp:'+digest
                        with a.db() as c:
                            if c.execute('SELECT 1 FROM schedule_sources WHERE id=?',(sid,)).fetchone():continue
                        try:
                            text=hwp_text(raw);dest=a.DATA/'schedule_sources'/(digest+'.hwp');dest.write_bytes(raw)
                            count+=ingest(sid,p.name,'hwp',text,dest.name)
                        except Exception as e:
                            errors.append(p.name+' · '+str(e)[:160])
                    for k in set(stable)-current:stable.pop(k,None)
            info.update(message=f'일정 검사 완료 · 새 후보 {count}건',last_scan=a.stamp(),errors=errors[:50])
        finally:lock.release()
    a.scan_schedules=scan;a.ingest_schedule=ingest;a.schedule_lock=lock;a.request_schedule_scan=wake.set
    def event(r):
        item=json.loads(r['data']);item.update(id=r['id'],source=r['source'],state=r['state'],version=r['version']);return item
    @a.app.get('/api/schedule')
    @a.protected()
    def schedule_listing():
        month=request.args.get('month',dt.date.today().strftime('%Y-%m'))
        try:
            first=dt.date.fromisoformat(month+'-01');last=(first.replace(day=28)+dt.timedelta(days=4)).replace(day=1)-dt.timedelta(days=1)
        except ValueError:abort(400)
        admin=a.current_role()=='admin'
        with a.db() as c:
            states=('pending','published') if admin else ('published',)
            placeholders=','.join('?' for _ in states)
            all_events=[event(r) for r in c.execute('SELECT * FROM schedule_events WHERE state IN ('+placeholders+') ORDER BY created',states)]
            visible=[e for e in all_events if e['state']=='published' and e['start']<=last.isoformat() and e['end']>=first.isoformat()]
            source_meta={r['id']:dict(r) for r in c.execute('SELECT id,name,kind FROM schedule_sources')}
            for e in all_events:
                src=source_meta.get(e['source'],{});e['source_name']=src.get('name','');e['source_kind']=src.get('kind','')
            result={'rows':rows(c),'events':visible,'month':month}
            if admin:
                pending=[e for e in all_events if e['state']=='pending']
                published=[e for e in all_events if e['state']=='published']
                for e in pending:
                    e['duplicates']=[p['title'] for p in published+pending if p['id']!=e['id'] and p['start']==e['start'] and (p['title']==e['title'] or (p.get('time') and p.get('time')==e.get('time') and p.get('place') and p.get('place')==e.get('place')))][:5]
                result.update(pending=pending,info=dict(info),sources=[dict(r) for r in c.execute('SELECT id,name,kind,created,status FROM schedule_sources ORDER BY created DESC LIMIT 100')])
            else:
                for e in visible:
                    for key in ('source','quote','warnings'):e.pop(key,None)
            return jsonify(result)
    @a.app.get('/api/schedule/review-sources')
    @a.protected(True)
    def review_sources():
        with a.db() as c:
            sources=[dict(r) for r in c.execute("SELECT s.id,s.name,s.kind,s.status,s.created,v.signature,CASE WHEN r.signature=substr(v.signature,instr(v.signature,':')+1) THEN 1 ELSE 0 END AS done FROM schedule_sources s LEFT JOIN schedule_seen v ON v.id=s.id LEFT JOIN schedule_reviews r ON r.source=s.id ORDER BY s.created DESC,s.id")]
            counts={r['source']:r['n'] for r in c.execute("SELECT source,count(*) n FROM schedule_events WHERE state='pending' GROUP BY source")}
            documents=list(c.execute('SELECT p.hash,p.doc,p.position,d.meta FROM pages p JOIN documents d ON d.id=p.doc ORDER BY p.doc,p.position'))
            batch_pages={r['id']:r['hash'] for r in c.execute('SELECT id,hash FROM batch_pages')}
            batches=list(c.execute("SELECT id,groups_json FROM batches WHERE state!='saved'"))
        for s in sources:s['pending']=counts.get(s['id'],0)
        by_id={s['id']:s for s in sources};owned=set();groups=[]
        def add_group(gid,name,ids):
            members=[by_id[sid] for sid in ids if sid in by_id and sid not in owned]
            if not members:return
            owned.update(m['id'] for m in members)
            groups.append(dict(id=gid,name=name,kind=members[0]['kind'],members=members,pending=sum(m['pending'] for m in members),done=all(m['done'] for m in members),created=max(m['created'] for m in members)))
        by_doc={}
        for r in documents:by_doc.setdefault(r['doc'],[]).append(r)
        for did,pages in by_doc.items():
            meta=json.loads(pages[0]['meta']);add_group('doc:'+did,meta.get('title') or '제목 미상',['image:'+r['hash'] for r in pages])
        for b in batches:
            for index,g in enumerate(json.loads(b['groups_json'])):
                ids=['image:'+batch_pages[pid] for pid in g.get('pages',[]) if pid in batch_pages and pid not in g.get('excluded',[])]
                add_group('batch:'+b['id']+':'+str(index),(g.get('meta') or {}).get('title') or '홍보물 묶음',ids)
        for s in sources:
            if s['id'] not in owned:add_group(s['id'],s['name'],[s['id']])
        groups.sort(key=lambda g:g['created'],reverse=True)
        return jsonify(sources=sources,groups=groups)
    @a.app.post('/api/schedule/review-source')
    @a.protected(True)
    def review_source():
        b=request.get_json(silent=True) or {};action=b.get('action')
        items=b.get('sources') or [{'source':b.get('source'),'signature':b.get('signature')}]
        if action not in ('complete','none') or not isinstance(items,list) or not 1<=len(items)<=1000:abort(400)
        if any(not isinstance(x,dict) or not isinstance(x.get('source'),str) or not isinstance(x.get('signature'),str) for x in items):abort(400)
        ids=[x['source'] for x in items]
        if len(set(ids))!=len(ids):abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE');pending=[]
            for item in items:
                sid=item['source'];seen=c.execute('SELECT signature FROM schedule_seen WHERE id=?',(sid,)).fetchone()
                if not seen:abort(404)
                if seen[0]!=item['signature']:abort(409)
                pending.extend(c.execute("SELECT * FROM schedule_events WHERE source=? AND state='pending'",(sid,)).fetchall())
            versions={r['id']:r['version'] for r in pending}
            if versions!=b.get('versions'):abort(409)
            if pending and action=='complete':return jsonify(error='남은 후보를 게시하거나 제외한 뒤 완료하세요.'),400
            if action=='none':
                for r in pending:
                    data=json.loads(r['data']);data['reviewed']=True
                    c.execute("UPDATE schedule_events SET state='rejected',data=?,version=version+1,updated=? WHERE id=?",(json.dumps(data,ensure_ascii=False),a.stamp(),r['id']))
            for item in items:
                c.execute('INSERT OR REPLACE INTO schedule_reviews VALUES(?,?,?)',(item['source'],item['signature'].split(':',1)[-1],a.stamp()))
                a.log(c,'문서 일정 검토 완료',item['source'])
        return jsonify(ok=True)
    @a.app.post('/api/schedule/reject-candidates')
    @a.protected(True)
    def reject_candidates():
        b=request.get_json(silent=True);items=b.get('items') if isinstance(b,dict) else None
        if not isinstance(items,list) or not 1<=len(items)<=500 or any(not isinstance(x,dict) or not isinstance(x.get('id'),str) or type(x.get('version')) is not int for x in items):abort(400)
        if len({x['id'] for x in items})!=len(items):abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            for item in items:
                r=c.execute('SELECT * FROM schedule_events WHERE id=?',(item['id'],)).fetchone()
                if not r or r['state']!='pending' or r['version']!=item['version']:abort(409)
            for item in items:
                r=c.execute('SELECT data FROM schedule_events WHERE id=?',(item['id'],)).fetchone()
                data=json.loads(r['data']);data['reviewed']=True
                c.execute("UPDATE schedule_events SET state='rejected',data=?,version=version+1,updated=? WHERE id=?",(json.dumps(data,ensure_ascii=False),a.stamp(),item['id']))
                a.log(c,'일정 제외',item['id'])
        return jsonify(ok=True,count=len(items))
    @a.app.post('/api/schedule/scan')
    @a.protected(True)
    def schedule_rescan():wake.set();return jsonify(ok=True,message='다음 백그라운드 검사에 반영합니다. 잠시 후 새로고침하세요.')
    @a.app.get('/api/schedule/source/<path:sid>')
    @a.protected(True)
    def schedule_source(sid):
        with a.db() as c:
            row=c.execute('SELECT * FROM schedule_sources WHERE id=?',(sid,)).fetchone()
            if not row:abort(404)
            if request.args.get('download')=='1':
                if row['kind']=='hwp':return send_file(a.DATA/'schedule_sources'/row['path'],as_attachment=True,download_name=row['name'])
                if row['path'] and (a.DATA/'schedule_sources'/row['path']).is_file():return send_file(a.DATA/'schedule_sources'/row['path'])
                digest=sid.split(':',1)[1]
                image=c.execute('SELECT path FROM pages WHERE hash=? UNION ALL SELECT path FROM batch_pages WHERE hash=?',(digest,digest)).fetchone()
                if not image:abort(404)
                return send_file(a.DATA/'images'/image[0])
            return jsonify(name=row['name'],kind=row['kind'],text=row['text'])
    @a.app.post('/api/schedule/rows')
    @a.protected(True)
    def schedule_update_rows():
        b=request.get_json();items=b.get('rows') if isinstance(b,dict) else None
        if not isinstance(items,list) or not 1<=len(items)<=100:abort(400)
        ids=set()
        for r in items:
            if not isinstance(r,dict) or any(not isinstance(r.get(k),str) or not r[k].strip() or len(r[k])>60 for k in ('id','group','name')) or r['id'] in ids:abort(400)
            ids.add(r['id'])
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if b.get('previous')!=rows(c):abort(409)
            used={json.loads(r[0]).get('row') for r in c.execute("SELECT data FROM schedule_events WHERE state IN ('pending','published')")}-{''}
            if not used.issubset(ids):return jsonify(error='일정이 있는 행은 삭제할 수 없습니다. 해당 일정을 다른 행으로 옮겨 주세요.'),400
            c.execute("UPDATE settings SET value=? WHERE key='schedule_rows'",(json.dumps(items,ensure_ascii=False),));a.log(c,'일정표 조직 행 변경')
        return jsonify(ok=True)
    @a.app.post('/api/schedule/event')
    @a.protected()
    def schedule_save_event():
        b=request.get_json()
        if not isinstance(b,dict):abort(400)
        if a.current_role()!='admin':
            if set(b)-{'title','row','start','end','kind','status','state'} or b.get('state')!='published':abort(403)
            if b.get('kind')!='일정' or b.get('status')!='예정':abort(403)
        if b.get('source') is not None and not isinstance(b.get('source'),str):abort(400)
        state=b.get('state');eid=b.get('id') or secrets.token_hex(12)
        if state not in ('pending','published','rejected'):abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM schedule_events WHERE id=?',(eid,)).fetchone()
            if b.get('id') and not old:abort(404)
            if old and b.get('version')!=old['version']:abort(409)
            data=json.loads(old['data']) if old else {'quote':'','warnings':[]}
            if state!='rejected':
                for k,limit in [('title',180),('row',60),('start',10),('end',10),('time',5),('end_time',5),('place',180),('kind',30),('status',30)]:
                    if not isinstance(b.get(k,''),str) or len(b.get(k,''))>limit:abort(400)
                    data[k]=b.get(k,'').strip()
                try:
                    if not data['end']:data['end']=data['start']
                    start=dt.date.fromisoformat(data['start']);end=dt.date.fromisoformat(data['end'])
                    if start>end:raise ValueError()
                    for k in ('time','end_time'):
                        if data[k]:dt.time.fromisoformat(data[k])
                    if start==end and data['time'] and data['end_time'] and data['end_time']<data['time']:raise ValueError()
                except ValueError:return jsonify(error='시작·종료 날짜와 시간을 확인하세요.'),400
                if not data['title']:return jsonify(error='행사명을 입력하세요.'),400
                valid={r['id'] for r in rows(c)}
                if data['row'] and data['row'] not in valid:abort(400)
                if state=='published' and data['row'] not in valid:return jsonify(error='일정표에 표시할 사업장·조직을 선택하세요.'),400
            if b.get('memo_id'):
                if not isinstance(b['memo_id'],str) or not c.execute('SELECT 1 FROM trend_memos WHERE id=? AND archived=0',(b['memo_id'],)).fetchone():abort(400)
                data['memo_id']=b['memo_id']
            data['reviewed']=True
            if not old and b.get('source') and not c.execute('SELECT 1 FROM schedule_sources WHERE id=?',(b['source'],)).fetchone():abort(404)
            if old:c.execute('UPDATE schedule_events SET data=?,state=?,version=version+1,updated=? WHERE id=?',(json.dumps(data,ensure_ascii=False),state,a.stamp(),eid))
            else:c.execute('INSERT INTO schedule_events VALUES(?,?,NULL,?,?,1,?,?)',(eid,b.get('source') or None,json.dumps(data,ensure_ascii=False),state,a.stamp(),a.stamp()))
            a.log(c,'일정 '+{'published':'확정·게시','pending':'검토 저장','rejected':'제외'}[state],eid)
        return jsonify(ok=True,id=eid)
    @a.app.post('/api/schedule/result')
    @a.protected(True)
    def schedule_result():
        b=request.get_json(silent=True)
        options=('진행중','잠정합의','결렬','정회','특이사항 없음')
        if not isinstance(b,dict) or not isinstance(b.get('id'),str) or type(b.get('version')) is not int or b.get('result') not in options or not isinstance(b.get('note',''),str) or len(b.get('note',''))>180:abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute("SELECT * FROM schedule_events WHERE id=? AND state='published'",(b['id'],)).fetchone()
            if not old:abort(404)
            if old['version']!=b['version']:abort(409)
            data=json.loads(old['data']);data['result']=b['result'];data['result_note']=b.get('note','').strip()
            c.execute('UPDATE schedule_events SET data=?,version=version+1,updated=? WHERE id=?',(json.dumps(data,ensure_ascii=False),a.stamp(),b['id']))
            a.log(c,'일정 결과 변경',b['id'])
        return jsonify(ok=True,version=old['version']+1)
    def start():
        def loop():
            while True:
                try:scan()
                except Exception:
                    a.app.logger.exception('Schedule scan failed');info['message']='일정 검사 오류 · 서버 실행 창을 확인하세요.'
                wake.wait(15);wake.clear()
        threading.Thread(target=loop,daemon=True,name='schedule-import').start()
    return start
