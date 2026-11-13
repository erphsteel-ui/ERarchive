"""Preview and add published schedules from a closed ERarchive SQLite backup."""
import contextlib
import datetime as dt
import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
from pathlib import Path
from flask import jsonify, request

MAX_BYTES = 50 * 1024 * 1024
MAX_EVENTS = 5000
FIELDS = ('title','start','end','time','end_time','place','kind','status','category',
          'subject','actor','description','detail','result','result_note','dday','reviewed')

class ImportErrorMessage(Exception):
    pass

def read_backup():
    files=request.files.getlist('files')
    expected={'archive.db','archive.db-wal','archive.db-shm'}
    by_name={}
    for f in files:
        name=Path(f.filename or '').name.lower()
        if name not in expected or name in by_name:
            raise ImportErrorMessage('archive.db와 같은 폴더의 -wal, -shm 파일만 선택해 주세요.')
        by_name[name]=f
    if 'archive.db' not in by_name:
        raise ImportErrorMessage('archive.db 파일을 선택해 주세요.')
    if 'archive.db-shm' in by_name and 'archive.db-wal' not in by_name:
        raise ImportErrorMessage('-shm 파일과 함께 -wal 파일도 선택해 주세요.')
    digest=hashlib.sha256();total=0
    with tempfile.TemporaryDirectory(prefix='er-schedule-import-') as folder:
        for name in sorted(by_name):
            digest.update(name.encode()+b'\0')
            with open(os.path.join(folder,name),'wb') as out:
                while True:
                    chunk=by_name[name].stream.read(256*1024)
                    if not chunk:break
                    total+=len(chunk)
                    if total>MAX_BYTES:raise ImportErrorMessage('선택한 파일의 합계는 50MB 이하여야 합니다.')
                    digest.update(chunk);out.write(chunk)
        try:
            path=Path(folder,'archive.db')
            uri=path.as_uri()+'?mode=ro'+('' if 'archive.db-wal' in by_name else '&immutable=1')
            with contextlib.closing(sqlite3.connect(uri,uri=True,timeout=3)) as source:
                source.execute('PRAGMA trusted_schema=OFF')
                source.execute('PRAGMA query_only=ON')
                for name in ('schedule_events','settings'):
                    t=source.execute("SELECT type FROM sqlite_master WHERE name=?",(name,)).fetchone()
                    if not t or t[0]!='table':raise ImportErrorMessage('ER 아카이브 일정 데이터베이스가 아닙니다.')
                record=source.execute("SELECT value FROM settings WHERE key='schedule_rows'").fetchone()
                source_rows=json.loads(record[0]) if record else []
                if not isinstance(source_rows,list) or len(source_rows)>1000:raise ValueError()
                events=source.execute("SELECT id,data FROM schedule_events WHERE state='published' LIMIT ?",(MAX_EVENTS+1,)).fetchall()
                if len(events)>MAX_EVENTS:raise ImportErrorMessage('한 번에 가져올 수 있는 일정은 5,000건까지입니다.')
        except ImportErrorMessage:raise
        except (sqlite3.Error,ValueError,TypeError,IndexError,KeyError):
            raise ImportErrorMessage('파일을 읽을 수 없습니다. 프로그램을 종료한 뒤 데이터베이스를 다시 복사해 주세요.')
    return digest.hexdigest(),source_rows,events

def build_plan(source_rows,records,current_rows,existing_ids):
    source={r.get('id'):r for r in source_rows if isinstance(r,dict) and isinstance(r.get('id'),str)}
    target={(r['group'],r['name']):r['id'] for r in current_rows}
    added_rows=[];items=[];skipped=0;skipped_items=[];duplicates=0
    for source_id,raw in records:
        if not isinstance(source_id,str) or not source_id or len(source_id)>200:
            skipped+=1;skipped_items.append({'title':'제목 확인 불가','start':'날짜 확인 불가'});continue
        if source_id in existing_ids:
            duplicates+=1;continue
        data={}
        try:
            data=json.loads(raw)
            if not isinstance(data,dict):raise ValueError()
            title=data.get('title');start=data.get('start');end=data.get('end') or start
            if not isinstance(title,str) or not title.strip() or len(title)>180:raise ValueError()
            if not isinstance(start,str) or not isinstance(end,str) or len(start)!=10 or len(end)!=10 or dt.date.fromisoformat(start)>dt.date.fromisoformat(end):raise ValueError()
            original=source.get(data.get('row'))
            if not original:raise ValueError()
            group,name=original.get('group'),original.get('name')
            if any(not isinstance(v,str) or not v.strip() or len(v)>60 for v in (group,name)):raise ValueError()
            clean={}
            for k in FIELDS:
                if k in data:
                    value=data[k]
                    if k in ('dday','reviewed'):
                        if type(value) is not bool:raise ValueError()
                    elif not isinstance(value,str) or len(value)>2000:raise ValueError()
                    clean[k]=value
            clean.update(title=title.strip(),start=start,end=end)
            key=(group,name)
            if key not in target:
                if len(current_rows)+len(added_rows)>=100:raise ValueError()
                new_id='import-'+secrets.token_hex(8)
                target[key]=new_id;added_rows.append({'id':new_id,'group':group,'name':name})
            clean['row']=target[key]
            items.append({'id':source_id,'data':clean,'group':group,'name':name})
        except (ValueError,TypeError,KeyError,OverflowError):
            skipped+=1
            if not isinstance(data,dict):data={}
            skipped_items.append({'title':str(data.get('title') or '제목 확인 불가')[:180], 'start':str(data.get('start') or '날짜 확인 불가')[:20]})
    return {'items':items,'new_rows':added_rows,'duplicates':duplicates,'skipped':skipped,'skipped_items':skipped_items,'total':len(records)}

def install(a):
    @a.app.post('/api/schedule/import/<action>')
    @a.protected(True)
    def import_schedule(action):
        if action not in ('preview','commit'):return jsonify(error='잘못된 요청입니다.'),400
        try:
            digest,source_rows,records=read_backup()
            if action=='commit' and not secrets.compare_digest(request.form.get('digest',''),digest):
                return jsonify(error='미리 확인한 파일과 다릅니다. 다시 확인해 주세요.'),400
            with a.db() as c:
                c.execute('BEGIN IMMEDIATE' if action=='commit' else 'BEGIN')
                row=c.execute("SELECT value FROM settings WHERE key='schedule_rows'").fetchone()
                current_rows=json.loads(row[0]);ids={r[0] for r in c.execute('SELECT id FROM schedule_events')}
                plan=build_plan(source_rows,records,current_rows,ids)
                plan_signature=hashlib.sha256(json.dumps({'ids':[i['id'] for i in plan['items']],'groups':[(i['group'],i['name']) for i in plan['items']],'new_rows':[(r['group'],r['name']) for r in plan['new_rows']],'duplicates':plan['duplicates'],'skipped':plan['skipped']},ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
                if action=='commit':
                    if not secrets.compare_digest(request.form.get('plan',''),plan_signature):
                        return jsonify(error='서버 일정이 변경되었습니다. 다시 미리 확인해 주세요.'),409
                    if plan['new_rows']:
                        c.execute("UPDATE settings SET value=? WHERE key='schedule_rows'",(json.dumps(current_rows+plan['new_rows'],ensure_ascii=False),))
                    for item in plan['items']:
                        c.execute('INSERT INTO schedule_events VALUES(?,NULL,NULL,?,?,1,?,?)',(item['id'],json.dumps(item['data'],ensure_ascii=False),'published',a.stamp(),a.stamp()))
                    a.log(c,'일정 가져오기 '+str(len(plan['items']))+'건')
                result={k:plan[k] for k in ('total','duplicates','skipped','new_rows')}
                result.update(digest=digest,plan=plan_signature,count=len(plan['items']))
                if action=='preview':
                    result['items']=[{'title':x['data']['title'],'start':x['data']['start'],'end':x['data']['end'],'group':x['group'],'name':x['name']} for x in plan['items']]
                    result['skipped_items']=plan['skipped_items']
                return jsonify(result)
        except ImportErrorMessage as e:return jsonify(error=str(e)),400
