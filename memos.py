"""Internal trend notes with original text, source and revision history."""
import datetime as dt,json,secrets,urllib.parse
from flask import request,jsonify,abort
CATEGORIES=['교섭·노사','집회·투쟁','선거·조직','정책·외부 반응','기타']
VERIFY=['미확인','출처 확인','내용 확인']
def install(a):
    with a.db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS trend_memos(id TEXT PRIMARY KEY,title TEXT,organizations TEXT,category TEXT,received TEXT,source TEXT,original TEXT,summary TEXT,verification TEXT,links TEXT,related TEXT,important INTEGER DEFAULT 0,archived INTEGER DEFAULT 0,version INTEGER DEFAULT 1,created TEXT,updated TEXT);
        CREATE TABLE IF NOT EXISTS trend_memo_history(id INTEGER PRIMARY KEY,memo TEXT REFERENCES trend_memos(id),version INTEGER,data TEXT,changed TEXT);
        CREATE INDEX IF NOT EXISTS idx_trend_received ON trend_memos(archived,received DESC);''')
    def unpack(row):
        d=dict(row)
        for key in ('organizations','links','related'):d[key]=json.loads(d[key])
        return d
    @a.app.get('/api/memos')
    @a.protected()
    def memos_list():
        admin=a.current_role()=='admin';where=[];params=[]
        if not (admin and request.args.get('archived')=='1'):where.append('archived=0')
        for field in ('category','verification'):
            value=request.args.get(field,'')
            if value:
                if value not in (CATEGORIES if field=='category' else VERIFY):abort(400)
                where.append(field+'=?');params.append(value)
        org=request.args.get('organization','')[:100]
        if org:where.append('EXISTS (SELECT 1 FROM json_each(trend_memos.organizations) WHERE value=?)');params.append(org)
        q=request.args.get('q','')[:200]
        if q:where.append('(instr(title,?)>0 OR instr(original,?)>0 OR instr(summary,?)>0 OR instr(source,?)>0 OR instr(organizations,?)>0)');params.extend([q]*5)
        for field,op in [('from','>='),('to','<=')]:
            value=request.args.get(field,'')
            if value:
                try:dt.date.fromisoformat(value)
                except ValueError:abort(400)
                where.append('received'+op+'?');params.append(value)
        if request.args.get('important')=='1':where.append('important=1')
        try:offset=max(0,int(request.args.get('offset','0')))
        except ValueError:abort(400)
        sql=' WHERE '+' AND '.join(where) if where else ''
        with a.db() as c:
            total=c.execute('SELECT count(*) FROM trend_memos'+sql,params).fetchone()[0]
            records=[dict(r) for r in c.execute('SELECT id,title,organizations,category,received,source,substr(summary,1,300) summary,substr(original,1,1200) excerpt,verification,important,archived,version,updated FROM trend_memos'+sql+' ORDER BY received DESC,created DESC,id LIMIT 50 OFFSET ?',params+[offset])]
            orgs=sorted({org for r in c.execute('SELECT organizations FROM trend_memos'+('' if admin else ' WHERE archived=0')) for org in json.loads(r[0])})
        for row in records:row['organizations']=json.loads(row['organizations'])
        return jsonify(items=records,total=total,categories=CATEGORIES,verification_options=VERIFY,organizations=orgs)
    @a.app.get('/api/memos/<mid>')
    @a.protected()
    def memos_detail(mid):
        admin=a.current_role()=='admin'
        with a.db() as c:
            row=c.execute('SELECT * FROM trend_memos WHERE id=?',(mid,)).fetchone()
            if not row or (row['archived'] and not admin):abort(404)
            d=unpack(row)
            ids=d['related']
            d['related_memos']=[dict(r) for rid in ids for r in c.execute('SELECT id,title FROM trend_memos WHERE id=?'+('' if admin else ' AND archived=0'),(rid,))]
            d['followups']=[dict(r) for r in c.execute("SELECT id,title FROM trend_memos WHERE EXISTS(SELECT 1 FROM json_each(trend_memos.related) WHERE value=?)"+('' if admin else ' AND archived=0')+' ORDER BY received DESC LIMIT 50',(mid,))]
            if admin:d['history']=[dict(r) for r in c.execute('SELECT version,data,changed FROM trend_memo_history WHERE memo=? ORDER BY version DESC LIMIT 20',(mid,))]
        return jsonify(d)
    @a.app.post('/api/memos/save')
    @a.protected(True)
    def memos_save():
        b=request.get_json(silent=True)
        if not isinstance(b,dict):abort(400)
        if b.get('id') is not None and not isinstance(b['id'],str):abort(400)
        previous=None
        if b.get('id'):
            with a.db() as c:previous=c.execute('SELECT * FROM trend_memos WHERE id=?',(b['id'],)).fetchone()
            if not previous:abort(404)
            if type(b.get('version')) is not int or b['version']!=previous['version']:abort(409)
        defaults=unpack(previous) if previous else dict(category='기타',received=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat(),source='',summary='',verification='미확인',links=[],related=[],important=False)
        defaults['important']=bool(defaults.get('important',False))
        b={**defaults,**b}
        limits={'title':180,'category':30,'received':10,'source':500,'original':100000,'summary':5000,'verification':30}
        data={}
        for key,limit in limits.items():
            value=b.get(key,'미확인' if key=='verification' else '')
            if not isinstance(value,str) or len(value)>limit:abort(400)
            data[key]=value if key=='original' else value.strip()
        if not data['title'] or not data['original'].strip():return jsonify(error='제목과 받은 원문을 입력하세요.'),400
        if data['category'] not in CATEGORIES or data['verification'] not in VERIFY:abort(400)
        try:dt.date.fromisoformat(data['received'])
        except ValueError:abort(400)
        for key,limit,length in [('organizations',30,100),('links',20,2000),('related',30,100)]:
            values=b.get(key,[])
            if not isinstance(values,list) or len(values)>limit or any(not isinstance(v,str) or len(v)>length for v in values):abort(400)
            data[key]=list(dict.fromkeys(v.strip() for v in values if v.strip()))
        for link in data['links']:
            try:
                url=urllib.parse.urlsplit(link)
                if url.scheme not in ('http','https') or not url.hostname or url.username or url.password:abort(400)
            except ValueError:abort(400)
        mid=b.get('id') or secrets.token_hex(12)
        if not isinstance(mid,str):abort(400)
        important=b.get('important',False)
        if type(important) is not bool:abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM trend_memos WHERE id=?',(mid,)).fetchone()
            if b.get('id') and not old:abort(404)
            if old and (b.get('version')!=old['version'] or old['archived']):abort(409)
            for rid in data['related']:
                if rid==mid or not c.execute('SELECT 1 FROM trend_memos WHERE id=?',(rid,)).fetchone():return jsonify(error='연결할 메모를 확인하세요.'),400
            values=[data[k] if k not in ('organizations','links','related') else json.dumps(data[k],ensure_ascii=False) for k in ('title','organizations','category','received','source','original','summary','verification','links','related')]
            if old:
                c.execute('INSERT INTO trend_memo_history(memo,version,data,changed) VALUES(?,?,?,?)',(mid,old['version'],json.dumps(unpack(old),ensure_ascii=False),a.stamp()))
                c.execute('UPDATE trend_memos SET title=?,organizations=?,category=?,received=?,source=?,original=?,summary=?,verification=?,links=?,related=?,important=?,version=version+1,updated=? WHERE id=?',values+[int(important),a.stamp(),mid])
            else:c.execute('INSERT INTO trend_memos VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0,1,?,?)',[mid]+values+[int(important),a.stamp(),a.stamp()])
            a.log(c,'동향 메모 저장',mid)
        return jsonify(ok=True,id=mid)
    @a.app.post('/api/memos/archive')
    @a.protected(True)
    def memos_archive():
        b=request.get_json(silent=True)
        if not isinstance(b,dict) or type(b.get('archived')) is not bool or not isinstance(b.get('id'),str):abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('UPDATE trend_memos SET archived=?,version=version+1,updated=? WHERE id=? AND version=?',(int(b['archived']),a.stamp(),b['id'],b.get('version'))).rowcount:abort(409)
            a.log(c,'동향 메모 보관 변경',b['id'])
        return jsonify(ok=True)
